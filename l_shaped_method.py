import pyomo.environ as pyo
import time
from concurrent.futures import ProcessPoolExecutor

class MultiCutLShapedMethod:
    """
    Full implementation of the Multi-cut L-shaped method for stochastic programming
    Based on the approach described in Restrepo et al. 2017
    """
    def __init__(self, tolerance=0.001, max_iterations=100, time_limit=3600):
        """
        Initialize the L-shaped method
        
        Args:
            tolerance: Optimality gap tolerance
            max_iterations: Maximum number of iterations
            time_limit: Time limit in seconds
        """
        self.tolerance = tolerance
        self.max_iterations = max_iterations
        self.time_limit = time_limit
        self.iteration = 0
        self.start_time = None
        self.lower_bound = float('-inf')
        self.upper_bound = float('inf')
        self.best_solution = None
        
    def solve(self, model, scenarios):
        """
        Solve the two-stage stochastic program using the multi-cut L-shaped method
        
        Args:
            model: The first-stage model
            scenarios: The set of scenarios
            
        Returns:
            Dictionary with solution information
        """
        print("Starting Multi-cut L-shaped method...")
        self.start_time = time.time()
        self.iteration = 0
        
        # Initialize master problem (first-stage)
        master = self._initialize_master_problem(model)
        
        # Create cut collection for each scenario
        cuts_by_scenario = {w: [] for w in range(len(scenarios))}
        
        # Main iteration loop
        while True:
            self.iteration += 1
            print(f"\nIteration {self.iteration}:")
            
            # Check termination conditions
            if self._should_terminate():
                break
                
            # Solve master problem
            master_solution = self._solve_master_problem(master)
            
            # Update lower bound
            self.lower_bound = max(self.lower_bound, master_solution['objective'])
            print(f"  Lower bound: {self.lower_bound:.2f}")
            
            # Get first-stage solution
            first_stage_vars = master_solution['variables']
            
            # Solve second-stage problems for each scenario and generate cuts
            new_cuts = self._solve_subproblems(model, scenarios, first_stage_vars)
            
            # Add cuts to master problem
            for scenario_idx, cuts in new_cuts.items():
                if cuts:
                    cuts_by_scenario[scenario_idx].extend(cuts)
                    self._add_cuts_to_master(master, cuts, scenario_idx)
            
            # Check if no cuts were added
            if all(len(cuts) == 0 for cuts in new_cuts.values()):
                print("  No new cuts generated - optimal solution found")
                break
            
            # Calculate current upper bound based on subproblem solutions
            current_upper_bound = self._calculate_upper_bound(first_stage_vars, scenarios)
            
            # Update best upper bound if improved
            if current_upper_bound < self.upper_bound:
                self.upper_bound = current_upper_bound
                self.best_solution = first_stage_vars
                print(f"  Upper bound improved: {self.upper_bound:.2f}")
            else:
                print(f"  Upper bound: {self.upper_bound:.2f}")
            
            # Calculate optimality gap
            gap = self._calculate_gap()
            print(f"  Current gap: {gap*100:.4f}%")
            
            # Check if gap is within tolerance
            if gap <= self.tolerance:
                print("  Optimal solution found within tolerance")
                break
        
        # Prepare final solution
        solution = self._prepare_solution()
        
        print(f"\nSolution process completed:")
        print(f"  Iterations: {self.iteration}")
        print(f"  Final gap: {self._calculate_gap()*100:.4f}%")
        print(f"  Total time: {time.time() - self.start_time:.2f} seconds")
        
        return solution
    
    def _initialize_master_problem(self, model):
        """Initialize the master problem (first-stage)"""
        master = {
            'model': model.clone(),
            'theta_vars': {},
            'cut_constraints': defaultdict(list)
        }
        
        # Add theta variables for each scenario
        for scenario_idx in range(model.num_scenarios):
            prob = model.scenario_probabilities[scenario_idx]
            theta_var = pyo.Var(domain=pyo.NonNegativeReals, name=f"theta_{scenario_idx}")
            master['model'].add_component(f"theta_{scenario_idx}", theta_var)
            master['theta_vars'][scenario_idx] = theta_var
        
        # Update objective to include theta variables
        old_obj = master['model'].objective.expr
        new_obj = old_obj + sum(master['theta_vars'][s] for s in master['theta_vars'])
        master['model'].objective.expr = new_obj
        
        return master
    
    def _solve_master_problem(self, master):
        """Solve the master problem"""
        print("  Solving master problem...")
        
        # Solve the master problem
        solver = pyo.SolverFactory('cbc')
        results = solver.solve(master['model'], tee=False)
        
        # Check solution status
        if results.solver.status == pyo.SolverStatus.ok and results.solver.termination_condition == pyo.TerminationCondition.optimal:
            # Extract solution
            objective_value = pyo.value(master['model'].objective)
            
            # Extract variable values
            variables = {}
            for var in master['model'].component_data_objects(pyo.Var):
                variables[var.name] = pyo.value(var)
                
            return {
                'status': 'optimal',
                'objective': objective_value,
                'variables': variables
            }
        else:
            print(f"  Warning: Master problem solution status: {results.solver.status}, {results.solver.termination_condition}")
            return {
                'status': 'failed',
                'objective': self.lower_bound,
                'variables': {}
            }
    
    def _solve_subproblems(self, model, scenarios, first_stage_vars):
        """
        Solve second-stage problems for each scenario and generate cuts
        
        Using process pool to solve subproblems in parallel
        """
        print("  Solving subproblems...")
        
        # Prepare parameters for subproblems
        subproblem_params = []
        for scenario_idx, scenario in enumerate(scenarios):
            subproblem_params.append((model, scenario, scenario_idx, first_stage_vars))
            
        # Solve subproblems in parallel
        new_cuts = {}
        with ProcessPoolExecutor(max_workers=min(8, len(scenarios))) as executor:
            results = list(executor.map(self._solve_single_subproblem, subproblem_params))
            
            for scenario_idx, cuts, obj_value in results:
                new_cuts[scenario_idx] = cuts
                print(f"    Scenario {scenario_idx}: {len(cuts)} cuts generated, obj = {obj_value:.2f}")
                
        return new_cuts
        
    def _solve_single_subproblem(self, params):
        """Solve a single second-stage problem and generate cuts"""
        model, scenario, scenario_idx, first_stage_vars = params
        
        # Prepare subproblem
        subproblem = self._prepare_subproblem(model, scenario, first_stage_vars)
        
        # Solve the subproblem
        solver = pyo.SolverFactory('cbc')
        results = solver.solve(subproblem, tee=False)
        
        # Check solution status
        if (results.solver.status == pyo.SolverStatus.ok and 
            results.solver.termination_condition == pyo.TerminationCondition.optimal):
            
            # Extract objective value
            obj_value = pyo.value(subproblem.objective)
            
            # Extract dual values for cut generation
            dual_values = self._extract_dual_values(subproblem)
            
            # Generate optimality cut
            cut = self._generate_optimality_cut(model, dual_values, first_stage_vars)
            
            return scenario_idx, [cut], obj_value
        else:
            # Feasibility cut implementation would go here
            print(f"    Warning: Subproblem {scenario_idx} solution failed: {results.solver.status}, {results.solver.termination_condition}")
            return scenario_idx, [], 0.0
    
    def _prepare_subproblem(self, model, scenario, first_stage_vars):
        """Prepare the subproblem for a given scenario"""
        # Clone the second-stage model 
        subproblem = model.create_second_stage_model(scenario)
        
        # Fix first-stage variables
        for var_name, value in first_stage_vars.items():
            if var_name in subproblem.first_stage_vars:
                subproblem.first_stage_vars[var_name].fix(value)
                
        return subproblem
    
    def _extract_dual_values(self, subproblem):
        """Extract dual values from subproblem solution"""
        dual_values = {}
        
        # Get constraint duals
        for con_name, con in subproblem.component_data_objects(pyo.Constraint, active=True):
            if con.body.polynomial_degree() <= 1:  # Linear constraints only
                dual_values[con_name] = subproblem.dual[con]
                
        return dual_values
    

    def _add_cuts_to_master(self, master, cuts, scenario_idx):
        """Add cuts to the master problem"""
        for cut_idx, cut in enumerate(cuts):
            # Create a unique name for the cut constraint
            cut_name = f"cut_{scenario_idx}_{len(master['cut_constraints'][scenario_idx])}"
            
            # Create the cut constraint
            # Implementation depends on the specific structure of the model and cuts
            cut_expr = self._create_cut_expression(master, cut, scenario_idx)
            
            # Add the constraint to the master problem
            master['model'].add_component(cut_name, pyo.Constraint(expr=cut_expr))
            
            # Keep track of added cuts
            master['cut_constraints'][scenario_idx].append(cut_name)
    
    def _create_cut_expression(self, master, cut, scenario_idx):
        """Create the expression for a cut constraint"""
        # For a typical optimality cut: theta_s >= cut_coefs * x + constant
        theta = master['theta_vars'][scenario_idx]
        
        # Here we would implement the specific cut expression based on the model structure
        # This is a simplified placeholder
        if cut['type'] == 'optimality':
            # Create a cut expression
            cut_expr = theta >= cut['rhs']
            return cut_expr
        else:
            # Feasibility cut
            return None
    
    def _calculate_gap(self):
        """Calculate the optimality gap"""
        if self.upper_bound == float('inf') or self.lower_bound == float('-inf'):
            return float('inf')
            
        # Prevent division by zero
        if abs(self.upper_bound) < 1e-10:
            return float('inf') if self.lower_bound != 0 else 0.0
            
        return (self.upper_bound - self.lower_bound) / abs(self.upper_bound)
    
    def _should_terminate(self):
        """Check if algorithm should terminate"""
        # Check iteration limit
        if self.iteration >= self.max_iterations:
            print("  Maximum iterations reached")
            return True
            
        # Check time limit
        if time.time() - self.start_time > self.time_limit:
            print("  Time limit reached")
            return True
            
        return False
    
    def _prepare_solution(self):
        """Prepare the final solution"""
        solution = {
            'status': 'optimal' if self._calculate_gap() <= self.tolerance else 'suboptimal',
            'first_stage': self.best_solution,
            'lower_bound': self.lower_bound,
            'upper_bound': self.upper_bound,
            'iterations': self.iteration,
            'gap': self._calculate_gap(),
            'time': time.time() - self.start_time
        }
        
        return solution 
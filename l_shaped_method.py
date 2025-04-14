import pyomo.environ as pyo
import time
import numpy as np
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
class MultiCutLShapedMethod:
    """
    Complete implementation of the Multi-cut L-shaped method for stochastic programming
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
            
            # Check if any subproblems were infeasible
            if any('infeasible' in cuts for cuts in new_cuts.values()):
                print("  Some subproblems are infeasible - adding feasibility cuts")
                
                # Add feasibility cuts
                for scenario_idx, cut_info in new_cuts.items():
                    if 'infeasible' in cut_info:
                        feasibility_cut = cut_info['infeasible']
                        self._add_feasibility_cut_to_master(master, feasibility_cut, scenario_idx)
                        cuts_by_scenario[scenario_idx].append(('feasibility', feasibility_cut))
                
                # Skip to next iteration
                continue
            
            # Add optimality cuts to master problem
            any_cuts_added = False
            for scenario_idx, cut_info in new_cuts.items():
                if 'optimality' in cut_info:
                    optimality_cut = cut_info['optimality']
                    self._add_optimality_cut_to_master(master, optimality_cut, scenario_idx)
                    cuts_by_scenario[scenario_idx].append(('optimality', optimality_cut))
                    any_cuts_added = True
            
            # Calculate current upper bound based on subproblem solutions
            current_upper_bound = self._calculate_upper_bound(model, first_stage_vars, new_cuts)
            
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
            
            # Check if gap is within tolerance or no cuts were added
            if gap <= self.tolerance or not any_cuts_added:
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
        old_obj = master['model'].Objective.expr
        new_obj = old_obj + sum(prob * master['theta_vars'][s] 
                            for s, prob in enumerate(model.scenario_probabilities))
        master['model'].Objective.expr = new_obj
        
        return master

    def _solve_master_problem(self, master):
        """Solve the master problem"""
        print("  Solving master problem...")
        
        # Print the master problem
        print("\n==== MASTER PROBLEM ====")
        master['model'].pprint()
        print("==== END MASTER PROBLEM ====\n")
        
        # Set up solver
        solver = pyo.SolverFactory('cbc')
        solver.options['seconds'] = 300  # 5-minute limit for master problem
        solver.options['mipgap'] = 0.01  # 1% gap tolerance
        
        # Solve the master problem
        results = solver.solve(master['model'], tee=False)
        
        # Check solution status
        if (results.solver.status == pyo.SolverStatus.ok and 
            results.solver.termination_condition in [pyo.TerminationCondition.optimal, 
                                                    pyo.TerminationCondition.feasible]):
            # Extract solution
            objective_value = pyo.value(master['model'].Objective)
            
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
        
        Using sequential execution to ensure prints are visible
        """
        print("  Solving subproblems...")
        
        # Prepare parameters for subproblems
        subproblem_params = []
        for scenario_idx, scenario in enumerate(scenarios):
            subproblem_params.append((model, scenario, scenario_idx, first_stage_vars))
            
        # Solve subproblems sequentially to ensure print statements are visible
        new_cuts = {}
        for params in subproblem_params:
            scenario_idx, cut_info, obj_value = self._solve_single_subproblem(params)
            new_cuts[scenario_idx] = cut_info
            
            # Print appropriate message based on cut type
            if 'infeasible' in cut_info:
                print(f"    Scenario {scenario_idx}: Infeasible - adding feasibility cut")
            else:
                print(f"    Scenario {scenario_idx}: Optimality cut, obj = {obj_value:.2f}")
                
        return new_cuts
        
    def _solve_single_subproblem(self, params):
        """Solve a single second-stage problem and generate cuts"""
        model, scenario, scenario_idx, first_stage_vars = params
        
        # Create second-stage model for this scenario
        subproblem = model.create_second_stage_model(scenario_idx)
        
        # Print the subproblem
        print(f"\n==== SUBPROBLEM FOR SCENARIO {scenario_idx} ====")
        subproblem.pprint()
        print(f"==== END SUBPROBLEM FOR SCENARIO {scenario_idx} ====\n")
        
        # Set up suffix for dual variables
        subproblem.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
        
        # Fix first-stage variables - simplified approach
        print(f"  Setting first-stage variables for scenario {scenario_idx}:")
        for var_name, value in first_stage_vars.items():
            if var_name.startswith('v['):
                param_name = var_name
                if param_name in subproblem.first_stage_vars:
                    param = subproblem.first_stage_vars[param_name]
                    param.value = value  # Use the value attribute directly
                    print(f"    {param_name} = {value}")
        
        # Force parameter construction by accessing values
        for name, param in subproblem.first_stage_vars.items():
            # Access value to ensure parameter is constructed
            _ = pyo.value(param)
        
        # Solve the subproblem
        solver = pyo.SolverFactory('cbc')
        solver.options['seconds'] = 120  # 2-minute limit for each subproblem
        results = solver.solve(subproblem, tee=False)
        
        # Check solution status
        if (results.solver.status == pyo.SolverStatus.ok and 
            results.solver.termination_condition == pyo.TerminationCondition.optimal):
            
            # Extract objective value
            obj_value = pyo.value(subproblem.objective)
            
            # Extract dual values for cut generation
            dual_values = self._extract_dual_values(subproblem)
            
            # Generate optimality cut
            cut = self._generate_optimality_cut(model, subproblem, dual_values, first_stage_vars, obj_value)
            
            return scenario_idx, {'optimality': cut}, obj_value
        else:
            # Generate feasibility cut
            ray = self._find_extreme_ray(subproblem, first_stage_vars)
            feasibility_cut = self._generate_feasibility_cut(model, subproblem, ray, first_stage_vars)
            
            return scenario_idx, {'infeasible': feasibility_cut}, float('inf')

    def _extract_dual_values(self, subproblem):
        """Extract dual values from subproblem solution"""
        dual_values = {}
        
        # Get constraint duals
        for con in subproblem.component_data_objects(pyo.Constraint, active=True):
            if hasattr(subproblem, 'dual') and con in subproblem.dual:
                dual_values[con.name] = subproblem.dual[con]
                
        return dual_values

    def _find_extreme_ray(self, subproblem, first_stage_vars):
        """
        Find an extreme ray of the dual subproblem when primal is infeasible
        Implements the elastic programming approach
        """
        # Create a copy of the subproblem with elastic variables
        feas_model = subproblem.clone()
        
        # Add elastic variables to each constraint
        elastic_vars = {}
        elastic_penalties = {}
        
        # Add elastic variables to every constraint
        for con in feas_model.component_data_objects(pyo.Constraint, active=True):
            # Create elastic variables (one for shortage, one for surplus)
            shortage_var = pyo.Var(domain=pyo.NonNegativeReals, name=f"short_{con.name}")
            surplus_var = pyo.Var(domain=pyo.NonNegativeReals, name=f"surp_{con.name}")
            
            feas_model.add_component(f"short_{con.name}", shortage_var)
            feas_model.add_component(f"surp_{con.name}", surplus_var)
            
            elastic_vars[con.name] = (shortage_var, surplus_var)
            
            # Define penalty coefficients (larger for more important constraints)
            if 'DemandSatisfaction' in con.name:
                penalty = 1000  # High penalty for demand constraints
            elif 'ActivityAssignment' in con.name:
                penalty = 500   # Medium penalty for activity constraints
            else:
                penalty = 100   # Base penalty for other constraints
                
            elastic_penalties[con.name] = penalty
            
            # Modify the constraint
            if con.equality:
                # For equality constraint (body == rhs):
                # Modify to: body + shortage - surplus == rhs
                con_expr = con.body + shortage_var - surplus_var == con.lower
                
                # Replace constraint
                con_list = getattr(feas_model, con.parent_component().name)
                idx = con.index()
                con_list[idx] = con_expr
            elif con.has_lb() and not con.has_ub():
                # For lower bound (body >= lb):
                # Modify to: body + shortage >= lb
                con_expr = con.body + shortage_var >= con.lower
                
                # Replace constraint
                con_list = getattr(feas_model, con.parent_component().name)
                idx = con.index()
                con_list[idx] = con_expr
            elif not con.has_lb() and con.has_ub():
                # For upper bound (body <= ub):
                # Modify to: body - surplus <= ub
                con_expr = con.body - surplus_var <= con.upper
                
                # Replace constraint
                con_list = getattr(feas_model, con.parent_component().name)
                idx = con.index()
                con_list[idx] = con_expr
            else:
                # For range constraint (lb <= body <= ub):
                # Split into two constraints
                if con.has_lb():
                    con_expr_lb = con.body + shortage_var >= con.lower
                    # Replace constraint with lower bound
                    con_list = getattr(feas_model, con.parent_component().name)
                    idx = con.index()
                    con_list[idx] = con_expr_lb
                
                if con.has_ub():
                    # Add a new constraint for upper bound
                    con_name = f"{con.parent_component().name}_upper_{con.index()}"
                    con_expr_ub = con.body - surplus_var <= con.upper
                    feas_model.add_component(con_name, pyo.Constraint(expr=con_expr_ub))
        
        # Replace objective with elastic penalty function
        elastic_obj = sum(elastic_penalties[con_name] * (shortage + surplus) 
                        for con_name, (shortage, surplus) in elastic_vars.items())
        
        # Remove original objective
        feas_model.del_component('objective')
        
        # Add new elastic objective
        feas_model.objective = pyo.Objective(expr=elastic_obj, sense=pyo.minimize)
        
        # Solve the elastic program
        solver = pyo.SolverFactory('cbc')
        results = solver.solve(feas_model, tee=False)
        
        # Extract the values of the elastic variables
        ray = {}
        for con_name, (shortage, surplus) in elastic_vars.items():
            shortage_val = pyo.value(shortage)
            surplus_val = pyo.value(surplus)
            
            if shortage_val > 1e-6 or surplus_val > 1e-6:
                # Record the constraint and violation direction
                if shortage_val > surplus_val:
                    ray[con_name] = ('shortage', shortage_val)
                else:
                    ray[con_name] = ('surplus', surplus_val)
        
        return ray

    def _generate_optimality_cut(self, model, subproblem, dual_values, first_stage_vars, obj_value):
        """
        Generate optimality cut based on dual values
        Cut form: theta >= obj_constant + sum(dual_i * (h_i - T_i*x))
        """
        # Start with the constant term
        constant_term = obj_value
        
        # Extract linear terms for first-stage variables
        tour_coefs = defaultdict(float)  # x[t] coefficients
        shift_coefs = defaultdict(float)  # v[s] coefficients
        
        # Process dual values by constraint type
        for con_name, dual_value in dual_values.items():
            # Skip if dual value is very small (numerical issues)
            if abs(dual_value) < 1e-6:
                continue
            
            # Process demand satisfaction constraints
            if 'DemandSatisfaction' in con_name:
                # Extract indices from constraint name
                # Format typically like: DemandSatisfaction[d,i,j]
                indices = con_name.split('[')[1].split(']')[0].split(',')
                day_idx = int(indices[0])
                period_idx = int(indices[1])
                activity_idx = int(indices[2])
                
                # Demand satisfaction doesn't directly involve first-stage vars
                # But it contributes to the constant term through the RHS
                constant_term += dual_value * subproblem.demand[day_idx, period_idx, activity_idx]
                
            # Process activity assignment constraints
            elif 'ActivityAssignment' in con_name:
                # Extract day and period from constraint name
                # Format typically like: ActivityAssignment[d,i]
                indices = con_name.split('[')[1].split(']')[0].split(',')
                day_idx = int(indices[0])
                period_idx = int(indices[1])
                
                # This constraint relates to shift variables active in this period
                # For each shift that's active in this period, add its contribution
                for s_idx, shift in enumerate(model._parent().shift_shells, 1):
                    if (shift['day'] == day_idx and 
                        shift['start_time'] <= period_idx <= shift['start_time'] + shift['length'] - 1):
                        # Add coefficient for this shift variable
                        shift_coefs[s_idx] -= dual_value  # Negative because the constraint is s - y = 0
        
        # Construct the cut
        cut = {
            'tour_coefs': dict(tour_coefs),
            'shift_coefs': dict(shift_coefs),
            'constant': constant_term,
            'first_stage_vals': {k: v for k, v in first_stage_vars.items() 
                                if k.startswith('x[') or k.startswith('v[')}
        }
        
        return cut

    def _generate_feasibility_cut(self, model, subproblem, ray, first_stage_vars):
        """
        Generate feasibility cut based on extreme ray
        Cut form: 0 >= sum(ray_i * (h_i - T_i*x))
        """
        # Initial constant term
        constant_term = 0
        
        # Coefficients for first-stage variables
        tour_coefs = defaultdict(float)
        shift_coefs = defaultdict(float)
        
        # Process ray information for each constraint
        for con_name, (direction, value) in ray.items():
            # Skip if value is very small
            if value < 1e-6:
                continue
                
            # Apply ray direction
            ray_value = value if direction == 'shortage' else -value
            
            # Process demand satisfaction constraints
            if 'DemandSatisfaction' in con_name:
                # Extract indices from constraint name
                indices = con_name.split('[')[1].split(']')[0].split(',')
                day_idx = int(indices[0])
                period_idx = int(indices[1])
                activity_idx = int(indices[2])
                
                # Add contribution to constant term from RHS
                constant_term += ray_value * subproblem.demand[day_idx, period_idx, activity_idx]
                
            # Process activity assignment constraints
            elif 'ActivityAssignment' in con_name:
                # Extract day and period from constraint name
                indices = con_name.split('[')[1].split(']')[0].split(',')
                day_idx = int(indices[0])
                period_idx = int(indices[1])
                
                # This constraint relates to shift variables active in this period
                for s_idx, shift in enumerate(model._parent().shift_shells, 1):
                    if (shift['day'] == day_idx and 
                        shift['start_time'] <= period_idx <= shift['start_time'] + shift['length'] - 1):
                        # Add coefficient for this shift variable
                        shift_coefs[s_idx] -= ray_value
        
        # Construct the cut
        cut = {
            'tour_coefs': dict(tour_coefs),
            'shift_coefs': dict(shift_coefs),
            'constant': constant_term,
            'first_stage_vals': {k: v for k, v in first_stage_vars.items() 
                            if k.startswith('x[') or k.startswith('v[')}
        }
        
        return cut

    def _add_optimality_cut_to_master(self, master, cut, scenario_idx):
        """Add optimality cut to the master problem"""
        # Get the theta variable for this scenario
        theta = master['theta_vars'][scenario_idx]
        
        # Create unique cut name
        cut_name = f"opt_cut_{scenario_idx}_{len(master['cut_constraints'][scenario_idx])}"
        
        # Create cut expression: theta >= constant + sum(coef * (var - val))
        # This is the linearized Benders cut that includes the current solution point
        cut_expr = theta >= cut['constant']
        
        # Apply coefficients from the cut
        for tour_idx, coef in cut['tour_coefs'].items():
            var_name = f"x[{tour_idx}]"
            if var_name in cut['first_stage_vals']:
                for var in master['model'].component_data_objects(pyo.Var):
                    if var.name == var_name:
                        cut_expr = cut_expr + coef * (var - cut['first_stage_vals'][var_name])
                        break
        
        for shift_idx, coef in cut['shift_coefs'].items():
            var_name = f"v[{shift_idx}]"
            if var_name in cut['first_stage_vals']:
                for var in master['model'].component_data_objects(pyo.Var):
                    if var.name == var_name:
                        cut_expr = cut_expr + coef * (var - cut['first_stage_vals'][var_name])
                        break
        
        # Add the constraint to the master problem
        master['model'].add_component(cut_name, pyo.Constraint(expr=cut_expr))
        
        # Track added cuts
        master['cut_constraints'][scenario_idx].append(cut_name)

    def _add_feasibility_cut_to_master(self, master, cut, scenario_idx):
        """Add feasibility cut to the master problem"""
        # Create unique cut name
        cut_name = f"feas_cut_{scenario_idx}_{len(master['cut_constraints'][scenario_idx])}"
        
        # Create cut expression: 0 >= constant + sum(coef * (var - val))
        cut_expr = 0 >= cut['constant']
        
        # Apply coefficients from the cut
        for tour_idx, coef in cut['tour_coefs'].items():
            var_name = f"x[{tour_idx}]"
            if var_name in cut['first_stage_vals']:
                for var in master['model'].component_data_objects(pyo.Var):
                    if var.name == var_name:
                        cut_expr = cut_expr + coef * (var - cut['first_stage_vals'][var_name])
                        break
        
        for shift_idx, coef in cut['shift_coefs'].items():
            var_name = f"v[{shift_idx}]"
            if var_name in cut['first_stage_vals']:
                for var in master['model'].component_data_objects(pyo.Var):
                    if var.name == var_name:
                        cut_expr = cut_expr + coef * (var - cut['first_stage_vals'][var_name])
                        break
        
        # Add the constraint to the master problem
        master['model'].add_component(cut_name, pyo.Constraint(expr=cut_expr))
        
        # Track added cuts
        master['cut_constraints'][scenario_idx].append(cut_name)

    def _calculate_upper_bound(self, model, first_stage_vars, new_cuts):
        """Calculate the current upper bound based on first-stage costs and subproblem solutions"""
        # First-stage objective value
        # For this tour scheduling model, the first-stage costs are zero (all costs in second stage)
        first_stage_obj = 0.0
        
        # Calculate second-stage expected objective value
        second_stage_obj = 0.0
        total_prob = 0.0
        
        for scenario_idx, cut_info in new_cuts.items():
            if 'optimality' in cut_info:
                # Get objective value from the cut
                obj_value = cut_info['optimality']['constant']
                
                # Get scenario probability
                prob = model.scenario_probabilities[scenario_idx]
                
                # Add weighted objective
                second_stage_obj += prob * obj_value
                total_prob += prob
        
        # Check if all scenarios have feasible solutions
        if abs(total_prob - 1.0) > 1e-6:
            # Some scenarios were infeasible, so we can't compute a valid upper bound
            return self.upper_bound
        
        return first_stage_obj + second_stage_obj

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
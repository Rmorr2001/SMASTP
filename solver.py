import time
import pyomo.environ as pyo
from l_shaped_method import MultiCutLShapedMethod
class SolverMixin:
    def solve(self, num_scenarios=5, method='deterministic_equivalent', solver='cbc', time_limit=3600):
        """
        Solve the stochastic tour scheduling problem
        
        Args:
            num_scenarios: Number of scenarios to generate
            method: Solution method ('deterministic_equivalent' or 'multi_cut_L_shaped')
            solver: Solver to use ('cbc', 'gurobi', or 'cbc')
            time_limit: Time limit in seconds
            
        Returns:
            Solution dictionary
        """
        start_time = time.time()
        print(f"Solving stochastic tour scheduling problem with {method} method...")
        
        # Generate shift shells if not already done
        if not self.shift_shells:
            self.generate_shift_shells()
        
        # Generate tours if not already done
        if not self.tours:
            self.generate_tours()
        
        # Generate scenarios if not already done
        if not self.scenarios or len(self.scenarios) != num_scenarios:
            self.generate_scenarios(num_scenarios)
        
        # Build model if not already done
        if not hasattr(self, 'model'):
            self.build_model(self.scenarios)
        
        # Solve the model
        if method == 'deterministic_equivalent':
            solution = self._solve_deterministic_equivalent(solver, time_limit)
        elif method == 'multi_cut_L_shaped':
            solution = self._solve_multi_cut_L_shaped(time_limit)
        else:
            raise ValueError(f"Unknown solution method: {method}")
        
        self.solution = solution
        self.processing_times['solve'] = time.time() - start_time
        
        print(f"Problem solved in {self.processing_times['solve']:.2f} seconds")
        print(f"Objective value: {solution['objective_value']:.2f}")
        print(f"Gap: {solution['gap']*100:.2f}%")
        
        return solution
    
    def _solve_deterministic_equivalent(self, solver_name, time_limit):
        """Solve the deterministic equivalent formulation"""
        print("Solving deterministic equivalent...")
        
        # Create solver
        solver = pyo.SolverFactory(solver_name)
        
        # Set time limit
        if solver_name == 'cbc':
            solver.options['timelimit'] = time_limit
        elif solver_name == 'gurobi':
            solver.options['TimeLimit'] = time_limit
        else:  # CBC
            solver.options['seconds'] = time_limit
            
        # Set other solver options
        if solver_name == 'cbc':
            solver.options['mipgap'] = 0.01  # 1% gap tolerance
            
        # Solve the model
        results = solver.solve(self.model, tee=True)
        
        # Check solution status
        if (results.solver.status == pyo.SolverStatus.ok and 
            results.solver.termination_condition in [pyo.TerminationCondition.optimal, 
                                                    pyo.TerminationCondition.feasible]):
            # Extract solution
            tour_assignments = {t: int(pyo.value(self.model.x[t])) for t in self.model.Tours if pyo.value(self.model.x[t]) > 0.5}
            shift_assignments = {s: int(pyo.value(self.model.v[s])) for s in self.model.ShiftShells if pyo.value(self.model.v[s]) > 0.5}
            
            # Activity assignments by scenario
            activity_assignments = {}
            for w in self.model.Scenarios:
                activity_assignments[w] = {}
                for d in self.model.Days:
                    for i in self.model.Periods:
                        for j in self.model.Activities:
                            val = pyo.value(self.model.y[w, d, i, j])
                            if val > 0.5:
                                activity_assignments[w][(d, i, j)] = int(val)
            
            # Get MIP gap
            if hasattr(results.solver, 'gap'):
                gap = results.solver.gap
            else:
                # Calculate gap based on best bound if available
                if hasattr(results.solver, 'best_bound'):
                    obj_val = pyo.value(self.model.Objective)
                    best_bound = results.solver.best_bound
                    gap = abs(obj_val - best_bound) / abs(obj_val) if obj_val != 0 else 0
                else:
                    gap = 0.0
            
            solution = {
                'status': str(results.solver.termination_condition),
                'objective_value': pyo.value(self.model.Objective),
                'tour_assignments': tour_assignments,
                'shift_assignments': shift_assignments,
                'activity_assignments': activity_assignments,
                'gap': gap,
                'iterations': 1
            }
        else:
            print(f"Solver status: {results.solver.status}, termination condition: {results.solver.termination_condition}")
            solution = {
                'status': 'failed',
                'objective_value': float('inf'),
                'tour_assignments': {},
                'shift_assignments': {},
                'activity_assignments': {},
                'gap': 1.0,
                'iterations': 0
            }
        
        return solution
    
    def _solve_multi_cut_L_shaped(self, time_limit):
        """Solve using the multi-cut L-shaped method"""
        print("Solving with Multi-cut L-shaped method...")
        
        # Initialize L-shaped method
        l_shaped = MultiCutLShapedMethod(
            tolerance=0.01,  # 1% gap tolerance
            max_iterations=100,
            time_limit=time_limit
        )
        
        # Solve the model
        solution = l_shaped.solve(self.model, self.scenarios)
        
        # Extract meaningful solution
        first_stage_vars = solution['first_stage']
        
        # Extract tour assignments
        tour_assignments = {}
        for key, value in first_stage_vars.items():
            if key.startswith('x[') and value > 0.5:
                tour_idx = int(key.split('[')[1].split(']')[0])
                tour_assignments[tour_idx] = int(value)
        
        # Extract shift assignments
        shift_assignments = {}
        for key, value in first_stage_vars.items():
            if key.startswith('v[') and value > 0.5:
                shift_idx = int(key.split('[')[1].split(']')[0])
                shift_assignments[shift_idx] = int(value)
        
        # Prepare solution dictionary
        solution_dict = {
            'status': solution['status'],
            'objective_value': solution['upper_bound'],
            'tour_assignments': tour_assignments,
            'shift_assignments': shift_assignments,
            'gap': solution['gap'],
            'iterations': solution['iterations']
        }
        
        return solution_dict
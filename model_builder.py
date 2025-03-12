import time
import numpy as np
import pyomo.environ as pyo
from scenario_generator import ScenarioGenerator
from tour_generator import TourGenerator

class ModelBuilderMixin:
    def generate_shift_shells(self):
        """Generate shift shells using the grammar"""
        start_time = time.time()
        print("Generating shift shells...")
        
        # Build the DAG from the grammar
        shift_dag = self.grammar.build_dag(self.num_periods)
        
        # Generate shift shells from the DAG
        shift_shells = []
        shell_id = 0
        
        # Convert paths to shift shells
        for day in range(1, self.num_days + 1):
            for start_time_period in range(0, self.num_periods - 32, 4):  # Every hour, for shifts up to 8 hours
                # 8-hour shift
                if start_time_period + 32 <= self.num_periods:
                    shift_shells.append({
                        'id': shell_id,
                        'day': day,
                        'start_time': start_time_period,
                        'length': 32,
                        'working_length': 26,  # 8 hours minus breaks
                        'type': '8-hour'
                    })
                    shell_id += 1
                
                # 6-hour shift
                if start_time_period + 24 <= self.num_periods:
                    shift_shells.append({
                        'id': shell_id,
                        'day': day,
                        'start_time': start_time_period,
                        'length': 24,
                        'working_length': 23,  # 6 hours minus break
                        'type': '6-hour'
                    })
                    shell_id += 1
                
                # 4-hour shift
                if start_time_period + 16 <= self.num_periods:
                    shift_shells.append({
                        'id': shell_id,
                        'day': day,
                        'start_time': start_time_period,
                        'length': 16,
                        'working_length': 15,  # 4 hours minus break
                        'type': '4-hour'
                    })
                    shell_id += 1
        
        self.shift_shells = shift_shells
        self.processing_times['generate_shift_shells'] = time.time() - start_time
        
        print(f"Generated {len(shift_shells)} shift shells in {self.processing_times['generate_shift_shells']:.2f} seconds")
        return shift_shells
    
    def generate_tours(self, max_tours=1000, diversity_factor=0.3):
        """Generate tours from shift shells"""
        if not self.shift_shells:
            self.generate_shift_shells()
            
        start_time = time.time()
        print("Generating tours...")
        
        # Define tour generation parameters
        min_working_days = 5
        max_working_days = 6
        min_tour_length = 35 * 4  # 35 hours in 15-min periods
        max_tour_length = 40 * 4  # 40 hours in 15-min periods
        min_rest_time = 12 * 4    # 12 hours in 15-min periods
        
        # Create enhanced tour generator
        tour_generator = TourGenerator(
            self.num_days, 
            min_working_days, 
            max_working_days, 
            min_tour_length, 
            max_tour_length, 
            min_rest_time
        )
        
        # Generate tours with improved diversity
        tours = tour_generator.generate_tours(
            self.shift_shells, 
            max_tours=max_tours,
            diversity_factor=diversity_factor
        )
        
        self.tours = tours
        self.processing_times['generate_tours'] = time.time() - start_time
        
        print(f"Generated {len(tours)} valid tours in {self.processing_times['generate_tours']:.2f} seconds")
        return tours
    
    def generate_scenarios(self, num_scenarios=5, distribution='poisson'):
        """Generate demand scenarios for the stochastic model"""
        if not self.shift_shells:
            self.generate_shift_shells()
            
        start_time = time.time()
        print(f"Generating {num_scenarios} demand scenarios...")
        
        # Create base demands
        base_demands = {}
        
        # Define time-of-day factors (morning, midday, afternoon, evening)
        time_blocks = [
            (0, 24, 0.6),      # 6am-9am: 60% of peak
            (24, 48, 1.0),     # 9am-3pm: 100% (peak)
            (48, 72, 0.8),     # 3pm-6pm: 80% of peak
            (72, 96, 0.5)      # 6pm-midnight: 50% of peak
        ]
        
        time_of_day_factors = {}
        for period in range(self.num_periods):
            # Find applicable time block
            factor = 0.5  # Default
            for start, end, block_factor in time_blocks:
                if start <= period < end:
                    factor = block_factor
                    break
            time_of_day_factors[period] = factor
        
        # Define day-of-week factors
        day_factors = {
            1: 0.8,  # Monday: 80% of average
            2: 0.9,  # Tuesday: 90% of average
            3: 1.0,  # Wednesday: average
            4: 1.0,  # Thursday: average
            5: 1.2,  # Friday: 120% of average
            6: 1.5,  # Saturday: 150% of average
            7: 1.1   # Sunday: 110% of average
        }
        
        # Generate base demands
        for d in range(1, self.num_days + 1):
            for i in range(self.num_periods):
                for j in range(1, self.num_activities + 1):
                    # Base demand depends on activity
                    if j == 1:
                        # First activity has higher demand
                        base_demand = np.random.randint(3, 8)
                    else:
                        # Other activities have lower demand
                        base_demand = np.random.randint(1, 5)
                    
                    base_demands[(d, i, j)] = base_demand
        
        # Create and use enhanced scenario generator
        scenario_generator = ScenarioGenerator(
            base_demands,
            seasonality_factors=day_factors,
            time_of_day_factors=time_of_day_factors
        )
        
        scenarios = scenario_generator.generate_scenarios(
            num_scenarios,
            distribution=distribution,
            correlation=0.3
        )
        
        self.scenarios = scenarios
        self.scenario_probabilities = [s['probability'] for s in scenarios]
        self.processing_times['generate_scenarios'] = time.time() - start_time
        
        print(f"Generated {len(scenarios)} scenarios in {self.processing_times['generate_scenarios']:.2f} seconds")
        return scenarios
    
    def build_model(self, scenarios=None):
        """
        Build the deterministic equivalent model of the two-stage stochastic problem
        """
        if scenarios is None:
            if not self.scenarios:
                self.generate_scenarios()
            scenarios = self.scenarios
            
        if not self.tours:
            self.generate_tours()
            
        start_time = time.time()
        print("Building two-stage stochastic model...")
        
        model = pyo.ConcreteModel(name="Two-Stage Stochastic Tour Scheduling")
        
        # Add scenarios to model for reference
        model.num_scenarios = len(scenarios)
        model.scenario_probabilities = self.scenario_probabilities
        
        # Sets
        model.Days = pyo.RangeSet(1, self.num_days) 
        model.Periods = pyo.RangeSet(1, self.num_periods)
        model.Activities = pyo.RangeSet(1, self.num_activities)
        model.Scenarios = pyo.RangeSet(1, len(scenarios))
        model.Tours = pyo.RangeSet(1, len(self.tours))
        model.ShiftShells = pyo.RangeSet(1, len(self.shift_shells))
        
        # Parameters
        # delta_ts: 1 if tour t includes shift shell s, 0 otherwise
        model.delta = pyo.Param(model.Tours, model.ShiftShells, initialize=0, mutable=True)
        
        # Fill delta parameter
        for t_idx, tour in enumerate(self.tours, 1):
            for shift_idx in tour:
                model.delta[t_idx, shift_idx+1] = 1
        
        # Demand by scenario
        def init_demand(model, w, d, i, j):
            return scenarios[w-1]['demand'].get((d, i, j), 0)
        
        model.demand = pyo.Param(model.Scenarios, model.Days, model.Periods, model.Activities, 
                               initialize=init_demand)
        
        # Scenario probabilities
        model.probability = pyo.Param(model.Scenarios, 
                                   initialize={w: scenarios[w-1]['probability'] for w in model.Scenarios})
        
        # Cost parameters
        model.c_allocation = pyo.Param(model.Days, model.Periods, model.Activities, 
                                     initialize=lambda m, d, i, j: 15)
        
        model.c_over = pyo.Param(model.Days, model.Periods, model.Activities, 
                               initialize=lambda m, d, i, j: 20)
        
        model.c_under = pyo.Param(model.Days, model.Periods, model.Activities, 
                                initialize=lambda m, d, i, j: 60)
        
        # First-stage variables
        # x_t: Number of employees assigned to tour t
        model.x = pyo.Var(model.Tours, domain=pyo.NonNegativeIntegers)
        
        # v_s: Number of employees assigned to shift shell s
        model.v = pyo.Var(model.ShiftShells, domain=pyo.NonNegativeIntegers)
        
        # Second-stage variables
        # y_dijs: Number of employees assigned to activity j, period i, day d, scenario s
        model.y = pyo.Var(model.Scenarios, model.Days, model.Periods, model.Activities, 
                        domain=pyo.NonNegativeIntegers)
        
        # s+_dijs: Overcovering for activity j, period i, day d, scenario s
        model.s_over = pyo.Var(model.Scenarios, model.Days, model.Periods, model.Activities, 
                             domain=pyo.NonNegativeIntegers)
        
        # s-_dijs: Undercovering for activity j, period i, day d, scenario s
        model.s_under = pyo.Var(model.Scenarios, model.Days, model.Periods, model.Activities, 
                              domain=pyo.NonNegativeIntegers)
        
        # Objective function
        def objective_rule(model):
            # Expected cost across all scenarios
            expected_cost = sum(
                model.probability[w] * (
                    # Activity allocation costs
                    sum(model.c_allocation[d, i, j] * model.y[w, d, i, j] 
                        for d in model.Days for i in model.Periods for j in model.Activities) +
                    # Overcovering costs
                    sum(model.c_over[d, i, j] * model.s_over[w, d, i, j] 
                        for d in model.Days for i in model.Periods for j in model.Activities) +
                    # Undercovering costs
                    sum(model.c_under[d, i, j] * model.s_under[w, d, i, j] 
                        for d in model.Days for i in model.Periods for j in model.Activities)
                )
                for w in model.Scenarios
            )
            return expected_cost
        
        model.Objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)
        
        # Constraints
        # Linking shifts to tours
        def linking_constraint_rule(model, s):
            return model.v[s] == sum(model.delta[t, s] * model.x[t] for t in model.Tours)
        
        model.LinkingConstraint = pyo.Constraint(model.ShiftShells, rule=linking_constraint_rule)
        
        # Employee availability - with fix for empty tours
        def employee_availability_rule(model):
            if len(self.tours) == 0:
                print("WARNING: No valid tours were generated!")
                return pyo.Constraint.Skip
            return sum(model.x[t] for t in model.Tours) == self.num_employees
        
        model.EmployeeAvailability = pyo.Constraint(rule=employee_availability_rule)
        
        # Demand satisfaction with under/overcovering
        def demand_satisfaction_rule(model, w, d, i, j):
            return model.y[w, d, i, j] + model.s_under[w, d, i, j] - model.s_over[w, d, i, j] == model.demand[w, d, i, j]
        
        model.DemandSatisfaction = pyo.Constraint(model.Scenarios, model.Days, model.Periods, 
                                                model.Activities, rule=demand_satisfaction_rule)
        
        # Linking shifts to activity assignments per period
        def activity_assignment_rule(model, w, d, i):
            # For each period, the sum of employees assigned to all activities
            # should equal the number of employees working in that period
            active_shifts = []
            for s_idx, shift in enumerate(self.shift_shells, 1):
                if (shift['day'] == d and 
                    shift['start_time'] <= i <= shift['start_time'] + shift['length'] - 1):
                    active_shifts.append(s_idx)
            
            total_employees_assigned = sum(model.y[w, d, i, j] for j in model.Activities)
            total_employees_working = sum(model.v[s] for s in active_shifts)
            
            return total_employees_assigned == total_employees_working
        
        model.ActivityAssignment = pyo.Constraint(model.Scenarios, model.Days, model.Periods, 
                                                rule=activity_assignment_rule)
        
        # Add method to create a second-stage model for a specific scenario
        def create_second_stage_model(scenario_idx):
            """Create a second-stage model for a specific scenario"""
            subproblem = pyo.ConcreteModel(name=f"Second-Stage-Scenario-{scenario_idx}")
            
            # Copy sets
            subproblem.Days = model.Days
            subproblem.Periods = model.Periods
            subproblem.Activities = model.Activities
            
            # Copy parameters for this scenario
            w = scenario_idx + 1
            
            # Track first-stage variables
            subproblem.first_stage_vars = {}
            
            # Add variables
            subproblem.y = pyo.Var(model.Days, model.Periods, model.Activities, 
                                 domain=pyo.NonNegativeIntegers)
            
            subproblem.s_over = pyo.Var(model.Days, model.Periods, model.Activities, 
                                      domain=pyo.NonNegativeIntegers)
            
            subproblem.s_under = pyo.Var(model.Days, model.Periods, model.Activities, 
                                       domain=pyo.NonNegativeIntegers)
            
            # Map fixed first-stage variables
            for s in model.ShiftShells:
                subproblem.first_stage_vars[f"v[{s}]"] = pyo.Param(initialize=0, mutable=True)
            
            # Objective
            def subobj_rule(subproblem):
                return (
                    # Activity allocation costs
                    sum(model.c_allocation[d, i, j] * subproblem.y[d, i, j] 
                        for d in subproblem.Days for i in subproblem.Periods for j in subproblem.Activities) +
                    # Overcovering costs
                    sum(model.c_over[d, i, j] * subproblem.s_over[d, i, j] 
                        for d in subproblem.Days for i in subproblem.Periods for j in subproblem.Activities) +
                    # Undercovering costs
                    sum(model.c_under[d, i, j] * subproblem.s_under[d, i, j] 
                        for d in subproblem.Days for i in subproblem.Periods for j in subproblem.Activities)
                )
            
            subproblem.objective = pyo.Objective(rule=subobj_rule, sense=pyo.minimize)
            
            # Constraints
            def sub_demand_rule(subproblem, d, i, j):
                return (subproblem.y[d, i, j] + subproblem.s_under[d, i, j] - 
                        subproblem.s_over[d, i, j] == model.demand[w, d, i, j])
            
            subproblem.DemandSatisfaction = pyo.Constraint(subproblem.Days, subproblem.Periods, 
                                                         subproblem.Activities, rule=sub_demand_rule)
            
            def sub_activity_rule(subproblem, d, i):
                # For each period, the sum of employees assigned to all activities
                # should equal the number of employees working in that period
                active_shifts = []
                for s_idx, shift in enumerate(self.shift_shells, 1):
                    if (shift['day'] == d and 
                        shift['start_time'] <= i <= shift['start_time'] + shift['length'] - 1):
                        active_shifts.append(s_idx)
                
                total_employees_assigned = sum(subproblem.y[d, i, j] for j in subproblem.Activities)
                total_employees_working = sum(subproblem.first_stage_vars[f"v[{s}]"] for s in active_shifts)
                
                return total_employees_assigned == total_employees_working
            
            subproblem.ActivityAssignment = pyo.Constraint(subproblem.Days, subproblem.Periods, 
                                                        rule=sub_activity_rule)
            
            return subproblem
        
        # Add the method to the model
        model.create_second_stage_model = create_second_stage_model
        
        self.model = model
        self.processing_times['build_model'] = time.time() - start_time
        
        print(f"Model built in {self.processing_times['build_model']:.2f} seconds")
        
        return model
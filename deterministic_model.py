import numpy as np
import pyomo.environ as pyo
from collections import defaultdict

def create_deterministic_model(stochastic_model):
    """
    Create a deterministic model using average demand from the stochastic scenarios
    
    Args:
        stochastic_model: The stochastic model to derive parameters from
        
    Returns:
        Deterministic model instance
    """
    # Create deterministic model
    deterministic_model = stochastic_model.__class__(
        num_days=stochastic_model.num_days,
        num_periods=stochastic_model.num_periods,
        num_activities=stochastic_model.num_activities,
        num_employees=stochastic_model.num_employees
    )
    
    import copy
    deterministic_model.shift_shells = copy.deepcopy(stochastic_model.shift_shells)
    deterministic_model.tours = copy.deepcopy(stochastic_model.tours)
    
    # Create a single scenario with average demand
    avg_demand = {}
    for key in stochastic_model.scenarios[0]['demand'].keys():
        avg_demand[key] = np.mean([scenario['demand'].get(key, 0) for scenario in stochastic_model.scenarios])
    
    avg_scenario = {
        'id': 0,
        'probability': 1.0,
        'demand': avg_demand
    }
    
    deterministic_model.scenarios = [avg_scenario]
    deterministic_model.scenario_probabilities = [1.0]
    
    return deterministic_model

def evaluate_deterministic_solution(deterministic_solution, deterministic_model, stochastic_model):
    """
    Evaluate deterministic solution on stochastic scenarios
    
    Args:
        deterministic_solution: Solution from deterministic model
        deterministic_model: The deterministic model
        stochastic_model: The stochastic model with scenarios
        
    Returns:
        Objective value of deterministic solution on stochastic scenarios
    """
    # Build a model to evaluate deterministic tours on stochastic scenarios
    evaluation_model = pyo.ConcreteModel(name="Evaluation_Model")
    
    # Sets
    evaluation_model.Days = pyo.RangeSet(1, stochastic_model.num_days)
    evaluation_model.Periods = pyo.RangeSet(1, stochastic_model.num_periods)
    evaluation_model.Activities = pyo.RangeSet(1, stochastic_model.num_activities)
    evaluation_model.Scenarios = pyo.RangeSet(1, len(stochastic_model.scenarios))
    
    # Parameters
    # Fixed first-stage solution from deterministic model
    deterministic_shifts = {}
    for s, count in deterministic_solution['shift_assignments'].items():
        if s <= len(deterministic_model.shift_shells):
            shift = deterministic_model.shift_shells[s-1]
            deterministic_shifts[(shift['day'], shift['start_time'], shift['length'])] = count
    
    # Demand parameter
    def init_demand(model, w, d, i, j):
        return stochastic_model.scenarios[w-1]['demand'].get((d, i, j), 0)
    
    evaluation_model.demand = pyo.Param(
        evaluation_model.Scenarios, evaluation_model.Days, 
        evaluation_model.Periods, evaluation_model.Activities,
        initialize=init_demand
    )
    
    # Scenario probabilities
    evaluation_model.probability = pyo.Param(
        evaluation_model.Scenarios,
        initialize={w: stochastic_model.scenario_probabilities[w-1] for w in evaluation_model.Scenarios}
    )
    
    # Variables
    evaluation_model.y = pyo.Var(
        evaluation_model.Scenarios, evaluation_model.Days, 
        evaluation_model.Periods, evaluation_model.Activities,
        domain=pyo.NonNegativeIntegers
    )
    
    evaluation_model.s_over = pyo.Var(
        evaluation_model.Scenarios, evaluation_model.Days, 
        evaluation_model.Periods, evaluation_model.Activities,
        domain=pyo.NonNegativeIntegers
    )
    
    evaluation_model.s_under = pyo.Var(
        evaluation_model.Scenarios, evaluation_model.Days, 
        evaluation_model.Periods, evaluation_model.Activities,
        domain=pyo.NonNegativeIntegers
    )
    
    # Objective
    def evaluation_obj_rule(model):
        return sum(
            model.probability[w] * (
                # Activity allocation costs
                sum(15 * model.y[w, d, i, j] 
                    for d in model.Days for i in model.Periods for j in model.Activities) +
                # Overcovering costs
                sum(20 * model.s_over[w, d, i, j] 
                    for d in model.Days for i in model.Periods for j in model.Activities) +
                # Undercovering costs
                sum(60 * model.s_under[w, d, i, j] 
                    for d in model.Days for i in model.Periods for j in model.Activities)
            )
            for w in model.Scenarios
        )
    
    evaluation_model.Objective = pyo.Objective(rule=evaluation_obj_rule, sense=pyo.minimize)
    
    # Constraints
    # Demand satisfaction with under/overcovering
    def demand_satisfaction_rule(model, w, d, i, j):
        return model.y[w, d, i, j] + model.s_under[w, d, i, j] - model.s_over[w, d, i, j] == model.demand[w, d, i, j]
    
    evaluation_model.DemandSatisfaction = pyo.Constraint(
        evaluation_model.Scenarios, evaluation_model.Days, 
        evaluation_model.Periods, evaluation_model.Activities, 
        rule=demand_satisfaction_rule
    )
    
    # Linking shifts to activity assignments
    def activity_assignment_rule(model, w, d, i):
        # Count employees working at this period based on deterministic shifts
        working_employees = 0
        for (day, start, length), count in deterministic_shifts.items():
            if day == d and start <= i < start + length:
                working_employees += count
        
        # All working employees must be assigned to activities
        return sum(model.y[w, d, i, j] for j in model.Activities) <= working_employees
    
    evaluation_model.ActivityAssignment = pyo.Constraint(
        evaluation_model.Scenarios, evaluation_model.Days, 
        evaluation_model.Periods, rule=activity_assignment_rule
    )
    
    # Solve the evaluation model
    solver = pyo.SolverFactory('cbc')
    results = solver.solve(evaluation_model, tee=True)
    
    # Extract result
    det_on_stoch_objective = pyo.value(evaluation_model.Objective)
    
    return det_on_stoch_objective

def compare_models(stochastic_model, stochastic_solution, deterministic_model, deterministic_solution, det_on_stoch_objective):
    """
    Compare the stochastic and deterministic models
    
    Args:
        stochastic_model: Stochastic model instance
        stochastic_solution: Solution from stochastic model
        deterministic_model: Deterministic model instance
        deterministic_solution: Solution from deterministic model
        det_on_stoch_objective: Objective of deterministic solution on stochastic scenarios
        
    Returns:
        Dictionary with comparison results
    """
    # Calculate the value of stochastic solution (VSS)
    stochastic_objective = stochastic_solution['objective_value']
    vss = det_on_stoch_objective - stochastic_objective
    vss_percentage = (vss / det_on_stoch_objective) * 100 if det_on_stoch_objective != 0 else 0
    
    # Prepare comparison results
    comparison = {
        'stochastic_objective': stochastic_objective,
        'deterministic_objective': deterministic_solution['objective_value'],
        'det_on_stoch_objective': det_on_stoch_objective,
        'value_of_stochastic_solution': vss,
        'vss_percentage': vss_percentage,
        'stochastic_tours': len(stochastic_solution['tour_assignments']),
        'deterministic_tours': len(deterministic_solution['tour_assignments']),
        'stochastic_processing_time': stochastic_model.processing_times.get('solve', 0),
        'deterministic_processing_time': deterministic_model.processing_times.get('solve', 0)
    }
    
    return comparison
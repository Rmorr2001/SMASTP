import numpy as np
import pyomo.environ as pyo
from collections import defaultdict
import pandas as pd
import matplotlib.pyplot as plt
import pyomo.environ as pyo
import os
import random
import time
from Stochastic.stochastic_scheduler import StochasticTourSchedulingModel

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

def compare_stochastic_vs_deterministic(seed=42, num_employees=20, num_scenarios=5, output_dir='./comparison'):
    """
    Compare stochastic model against deterministic model
    
    Args:
        seed: Random seed for reproducibility
        num_employees: Number of employees to schedule
        num_scenarios: Number of scenarios to generate
        output_dir: Directory to save results
    
    Returns:
        Dictionary with comparison results
    """
    # Set random seed for reproducibility
    random.seed(seed)
    np.random.seed(seed)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print("Comparing stochastic vs deterministic approaches...")
    
    # Track timing information
    timing = {
        'stochastic': {
            'setup': 0,
            'solve': 0,
            'total': 0
        },
        'deterministic': {
            'setup': 0,
            'solve': 0,
            'total': 0
        },
        'evaluation': 0
    }
    
    # 1. Run stochastic model
    print("\n--- STOCHASTIC MODEL ---")
    stochastic_start = time.time()
    
    # Setup phase
    setup_start = time.time()
    stochastic_model = StochasticTourSchedulingModel(
        num_days=7,
        num_periods=96,
        num_activities=2,
        num_employees=num_employees
    )
    
    stochastic_model.generate_shift_shells()
    stochastic_model.generate_tours()
    stochastic_model.generate_scenarios(num_scenarios)
    timing['stochastic']['setup'] = time.time() - setup_start
    print(f"Stochastic model setup time: {timing['stochastic']['setup']:.2f} seconds")
    
    # Solve phase
    solve_start = time.time()
    stochastic_solution = stochastic_model.solve(
        num_scenarios=num_scenarios,
        method='deterministic_equivalent',
        time_limit=1800
    )
    timing['stochastic']['solve'] = time.time() - solve_start
    timing['stochastic']['total'] = time.time() - stochastic_start
    print(f"Stochastic model solve time: {timing['stochastic']['solve']:.2f} seconds")
    print(f"Stochastic model total time: {timing['stochastic']['total']:.2f} seconds")
    
    # 2. Run deterministic model (using average demand)
    print("\n--- DETERMINISTIC MODEL ---")
    deterministic_start = time.time()
    
    # Setup phase
    setup_start = time.time()
    deterministic_model = create_deterministic_model(stochastic_model)
    timing['deterministic']['setup'] = time.time() - setup_start
    print(f"Deterministic model setup time: {timing['deterministic']['setup']:.2f} seconds")
    
    # Solve phase
    solve_start = time.time()
    deterministic_solution = deterministic_model.solve(
        num_scenarios=1,
        method='deterministic_equivalent',
        time_limit=1800
    )
    timing['deterministic']['solve'] = time.time() - solve_start
    timing['deterministic']['total'] = time.time() - deterministic_start
    print(f"Deterministic model solve time: {timing['deterministic']['solve']:.2f} seconds")
    print(f"Deterministic model total time: {timing['deterministic']['total']:.2f} seconds")
    
    # 3. Evaluate deterministic solution on stochastic scenarios
    print("\n--- EVALUATING DETERMINISTIC SOLUTION ON STOCHASTIC SCENARIOS ---")
    eval_start = time.time()
    det_on_stoch_objective = evaluate_deterministic_solution(
        deterministic_solution, 
        deterministic_model, 
        stochastic_model
    )
    timing['evaluation'] = time.time() - eval_start
    print(f"Evaluation time: {timing['evaluation']:.2f} seconds")
    
    # 4. Compare results
    comparison = compare_models(
        stochastic_model, 
        stochastic_solution, 
        deterministic_model, 
        deterministic_solution, 
        det_on_stoch_objective
    )
    
    # Add timing information to comparison
    comparison['timing'] = timing
    comparison['speedup'] = timing['stochastic']['total'] / timing['deterministic']['total']
    
    # Print comparison results
    print("\n--- COMPARISON RESULTS ---")
    print(f"Stochastic Objective: {comparison['stochastic_objective']:.2f}")
    print(f"Deterministic Objective: {comparison['deterministic_objective']:.2f}")
    print(f"Deterministic solution evaluated on stochastic scenarios: {comparison['det_on_stoch_objective']:.2f}")
    print(f"Value of Stochastic Solution (VSS): {comparison['value_of_stochastic_solution']:.2f}")
    print(f"VSS Percentage: {comparison['vss_percentage']:.2f}%")
    print(f"Stochastic Tours Used: {comparison['stochastic_tours']}")
    print(f"Deterministic Tours Used: {comparison['deterministic_tours']}")
    
    # Print timing comparison
    print("\n--- TIMING COMPARISON ---")
    print(f"Stochastic model total time: {timing['stochastic']['total']:.2f} seconds")
    print(f"  - Setup time: {timing['stochastic']['setup']:.2f} seconds")
    print(f"  - Solve time: {timing['stochastic']['solve']:.2f} seconds")
    print(f"Deterministic model total time: {timing['deterministic']['total']:.2f} seconds")
    print(f"  - Setup time: {timing['deterministic']['setup']:.2f} seconds")
    print(f"  - Solve time: {timing['deterministic']['solve']:.2f} seconds")
    print(f"Speedup factor (Stochastic/Deterministic): {comparison['speedup']:.2f}x")
    
    # Save comparison results
    pd.DataFrame([comparison]).to_csv(os.path.join(output_dir, 'comparison_results.csv'), index=False)
    
    # Create visualizations
    # 1. Bar chart of objectives
    plt.figure(figsize=(10, 6))
    objectives = [
        comparison['deterministic_objective'], 
        comparison['det_on_stoch_objective'], 
        comparison['stochastic_objective']
    ]
    labels = [
        'Deterministic\nObjective', 
        'Deterministic Solution\non Stochastic Scenarios', 
        'Stochastic\nObjective'
    ]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    plt.bar(labels, objectives, color=colors)
    plt.ylabel('Objective Value')
    plt.title('Comparison of Solution Approaches')
    plt.grid(axis='y', alpha=0.3)
    
    # Add values on top of bars
    for i, v in enumerate(objectives):
        plt.text(i, v + 100, f"{v:.0f}", ha='center')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'objective_comparison.png'))
    
    # 2. VSS visualization
    plt.figure(figsize=(8, 5))
    plt.barh(['Value of Stochastic Solution'], [comparison['vss_percentage']], color='#2ca02c')
    plt.xlabel('Percentage Improvement (%)')
    plt.title('Value of Stochastic Solution (VSS)')
    plt.grid(axis='x', alpha=0.3)
    plt.xlim(0, max(comparison['vss_percentage'] * 1.2, 5))
    
    # Add value on bar
    plt.text(comparison['vss_percentage'] + 0.5, 0, f"{comparison['vss_percentage']:.2f}%", va='center')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'vss_visualization.png'))
    
    # 3. Timing comparison visualization
    plt.figure(figsize=(12, 6))
    
    # Prepare data for grouped bar chart
    models = ['Stochastic', 'Deterministic']
    setup_times = [timing['stochastic']['setup'], timing['deterministic']['setup']]
    solve_times = [timing['stochastic']['solve'], timing['deterministic']['solve']]
    total_times = [timing['stochastic']['total'], timing['deterministic']['total']]
    
    x = np.arange(len(models))
    width = 0.25
    
    # Create grouped bar chart
    plt.bar(x - width, setup_times, width, label='Setup Time', color='#1f77b4')
    plt.bar(x, solve_times, width, label='Solve Time', color='#ff7f0e')
    plt.bar(x + width, total_times, width, label='Total Time', color='#2ca02c')
    
    plt.ylabel('Time (seconds)')
    plt.title('Calculation Time Comparison')
    plt.xticks(x, models)
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    
    # Add values on top of bars
    for i, v in enumerate(setup_times):
        plt.text(i - width, v + 1, f"{v:.1f}s", ha='center', va='bottom', fontsize=9)
    for i, v in enumerate(solve_times):
        plt.text(i, v + 1, f"{v:.1f}s", ha='center', va='bottom', fontsize=9)
    for i, v in enumerate(total_times):
        plt.text(i + width, v + 1, f"{v:.1f}s", ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'timing_comparison.png'))
    
    # 4. Speedup factor visualization
    plt.figure(figsize=(8, 5))
    plt.barh(['Speedup Factor'], [comparison['speedup']], color='#ff7f0e')
    plt.xlabel('Speedup (Stochastic Time / Deterministic Time)')
    plt.title('Computational Efficiency Comparison')
    plt.grid(axis='x', alpha=0.3)
    
    # Add value on bar
    plt.text(comparison['speedup'] + 0.1, 0, f"{comparison['speedup']:.2f}x", va='center')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'speedup_visualization.png'))
    
    return comparison

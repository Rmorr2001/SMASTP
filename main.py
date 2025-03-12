import os
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyomo.environ as pyo
from collections import defaultdict

from stochastic_scheduler import StochasticTourSchedulingModel

from deterministic_model import create_deterministic_model, evaluate_deterministic_solution, compare_models

def run_stochastic_model(seed=42, num_employees=10, num_scenarios=5, output_dir='./results'):
    """
    Run the enhanced stochastic model with visualization and reporting
    
    Args:
        seed: Random seed for reproducibility
        num_employees: Number of employees to schedule
        num_scenarios: Number of scenarios to generate
        output_dir: Directory to save results
    
    Returns:
        Tuple of (model, solution)
    """
    # Set random seed for reproducibility
    random.seed(seed)
    np.random.seed(seed)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Create model
    print("Initializing model...")
    model = StochasticTourSchedulingModel(
        num_days=7,        # 7-day planning horizon
        num_periods=96,    # 15-minute intervals (24h × 4 periods/hour)
        num_activities=2,  # 2 work activities
        num_employees=num_employees
    )
    
    # Generate shift shells
    model.generate_shift_shells()
    
    # Generate tours
    model.generate_tours(max_tours=1000)
    
    # Generate scenarios
    model.generate_scenarios(num_scenarios=num_scenarios)
    
    # Solve model
    print("\nSolving model...")
    solution = model.solve(
        num_scenarios=num_scenarios, 
        method='deterministic_equivalent',
        time_limit=1800  # 30 minutes time limit
    )
    
    # Print results
    print("\nSolution Status:")
    print(f"Objective Value: {solution['objective_value']:.2f}")
    print(f"Optimality Gap: {solution['gap']*100:.2f}%")
    
    print("\nTour Assignments:")
    for tour, count in sorted(solution['tour_assignments'].items()):
        print(f"Tour {tour}: {count} employees")
    
    # Visualize solution
    model.visualize_solution(output_dir)
    
    # Generate reports
    model.generate_reports(output_dir)
    
    # Export solution
    model.export_solution(os.path.join(output_dir, 'solution.pkl'))
    
    return model, solution


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
    
    # 1. Run stochastic model
    print("\n--- STOCHASTIC MODEL ---")
    stochastic_model = StochasticTourSchedulingModel(
        num_days=7,
        num_periods=96,
        num_activities=2,
        num_employees=num_employees
    )
    
    stochastic_model.generate_shift_shells()
    stochastic_model.generate_tours()
    stochastic_model.generate_scenarios(num_scenarios)
    
    stochastic_solution = stochastic_model.solve(
        num_scenarios=num_scenarios,
        method='deterministic_equivalent',
        time_limit=1800
    )
    
    # 2. Run deterministic model (using average demand)
    print("\n--- DETERMINISTIC MODEL ---")
    deterministic_model = create_deterministic_model(stochastic_model)
    
    deterministic_solution = deterministic_model.solve(
        num_scenarios=1,
        method='deterministic_equivalent',
        time_limit=1800
    )
    
    # 3. Evaluate deterministic solution on stochastic scenarios
    print("\n--- EVALUATING DETERMINISTIC SOLUTION ON STOCHASTIC SCENARIOS ---")
    det_on_stoch_objective = evaluate_deterministic_solution(
        deterministic_solution, 
        deterministic_model, 
        stochastic_model
    )
    
    # 4. Compare results
    comparison = compare_models(
        stochastic_model, 
        stochastic_solution, 
        deterministic_model, 
        deterministic_solution, 
        det_on_stoch_objective
    )
    
    # Print comparison results
    print("\n--- COMPARISON RESULTS ---")
    print(f"Stochastic Objective: {comparison['stochastic_objective']:.2f}")
    print(f"Deterministic Objective: {comparison['deterministic_objective']:.2f}")
    print(f"Deterministic solution evaluated on stochastic scenarios: {comparison['det_on_stoch_objective']:.2f}")
    print(f"Value of Stochastic Solution (VSS): {comparison['value_of_stochastic_solution']:.2f}")
    print(f"VSS Percentage: {comparison['vss_percentage']:.2f}%")
    print(f"Stochastic Tours Used: {comparison['stochastic_tours']}")
    print(f"Deterministic Tours Used: {comparison['deterministic_tours']}")
    
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
    
    return comparison


if __name__ == "__main__":
    # Create a results directory
    os.makedirs("results", exist_ok=True)
    
    # Run the stochastic model
    model, solution = run_stochastic_model(
        seed=42,
        num_employees=20,
        num_scenarios=5,
        output_dir='results/stochastic_model'
    )
    
    # Compare stochastic vs. deterministic approaches
    comparison = compare_stochastic_vs_deterministic(
        seed=42,
        num_employees=40,
        num_scenarios=5,
        output_dir='results/comparison'
    )
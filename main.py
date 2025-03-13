import os
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyomo.environ as pyo
from collections import defaultdict
import time

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


def view_tours(model, num_tours=None, detailed=False, output_dir=None):
    """
    View the generated tours in a user-friendly format
    
    Args:
        model: The StochasticTourSchedulingModel instance
        num_tours: Number of tours to display (None for all)
        detailed: Whether to show detailed information for each tour
        output_dir: Directory to save tour information as CSV (optional)
    
    Returns:
        DataFrame containing tour information
    """
    if not model.tours:
        print("No tours have been generated. Please generate tours first.")
        return None
    
    # Limit the number of tours to display
    tours_to_display = model.tours[:num_tours] if num_tours else model.tours
    
    # Create a list to store tour data
    tour_data = []
    
    print(f"\nDisplaying {len(tours_to_display)} of {len(model.tours)} total tours:")
    
    # Process each tour
    for tour_idx, tour in enumerate(tours_to_display):
        # Calculate tour properties
        working_days = sorted(set(model.shift_shells[idx]['day'] for idx in tour))
        working_length = sum(model.shift_shells[idx]['working_length'] for idx in tour)
        
        # Count shift types
        shift_types = defaultdict(int)
        for idx in tour:
            shift_types[model.shift_shells[idx]['type']] += 1
        
        # Create tour data entry
        tour_entry = {
            'Tour ID': tour_idx + 1,
            'Working Days': len(working_days),
            'Days': ', '.join(map(str, working_days)),
            'Working Hours': working_length / 4,  # Convert to hours
            '8-hour Shifts': shift_types.get('8-hour', 0),
            '6-hour Shifts': shift_types.get('6-hour', 0),
            '4-hour Shifts': shift_types.get('4-hour', 0),
            'Total Shifts': len(tour)
        }
        
        # Add to data
        tour_data.append(tour_entry)
        
        # Print detailed information if requested
        if detailed:
            print(f"\nTour {tour_idx + 1}:")
            print(f"  Working Days: {len(working_days)} ({', '.join(map(str, working_days))})")
            print(f"  Working Hours: {working_length / 4:.2f}")
            print(f"  Shifts: {len(tour)} ({shift_types.get('8-hour', 0)} 8-hour, "
                  f"{shift_types.get('6-hour', 0)} 6-hour, {shift_types.get('4-hour', 0)} 4-hour)")
            print("  Detailed Schedule:")
            
            # Sort shifts by day and start time
            sorted_shifts = sorted(
                [(model.shift_shells[idx]['day'], model.shift_shells[idx]['start_time'], idx) for idx in tour]
            )
            
            for day, start_time, shift_idx in sorted_shifts:
                shift = model.shift_shells[shift_idx]
                start_hour = start_time // 4
                start_minute = (start_time % 4) * 15
                end_hour = (start_time + shift['length']) // 4
                end_minute = ((start_time + shift['length']) % 4) * 15
                
                print(f"    Day {day}: {start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d} "
                      f"({shift['type']})")
    
    # Create a DataFrame
    df = pd.DataFrame(tour_data)
    
    # Print summary if not detailed
    if not detailed:
        print("\nTour Summary:")
        print(df.to_string(index=False))
    
    # Save to CSV if output directory is provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, 'tour_information.csv')
        df.to_csv(csv_path, index=False)
        print(f"\nTour information saved to {csv_path}")
    
    return df


def view_tour_details(model, tour_id):
    """
    View detailed information for a specific tour
    
    Args:
        model: The StochasticTourSchedulingModel instance
        tour_id: ID of the tour to view (1-indexed)
    """
    if not model.tours:
        print("No tours have been generated. Please generate tours first.")
        return
    
    # Adjust for 1-indexed tour IDs
    tour_idx = tour_id - 1
    
    if tour_idx < 0 or tour_idx >= len(model.tours):
        print(f"Invalid tour ID. Please provide a tour ID between 1 and {len(model.tours)}.")
        return
    
    # Get the tour
    tour = model.tours[tour_idx]
    
    # Calculate tour properties
    working_days = sorted(set(model.shift_shells[idx]['day'] for idx in tour))
    working_length = sum(model.shift_shells[idx]['working_length'] for idx in tour)
    
    # Count shift types
    shift_types = defaultdict(int)
    for idx in tour:
        shift_types[model.shift_shells[idx]['type']] += 1
    
    # Print tour information
    print(f"\nTour {tour_id} Details:")
    print(f"  Working Days: {len(working_days)} ({', '.join(map(str, working_days))})")
    print(f"  Working Hours: {working_length / 4:.2f}")
    print(f"  Shifts: {len(tour)} ({shift_types.get('8-hour', 0)} 8-hour, "
          f"{shift_types.get('6-hour', 0)} 6-hour, {shift_types.get('4-hour', 0)} 4-hour)")
    
    # Print detailed schedule
    print("  Detailed Schedule:")
    
    # Sort shifts by day and start time
    sorted_shifts = sorted(
        [(model.shift_shells[idx]['day'], model.shift_shells[idx]['start_time'], idx) for idx in tour]
    )
    
    for day, start_time, shift_idx in sorted_shifts:
        shift = model.shift_shells[shift_idx]
        start_hour = start_time // 4
        start_minute = (start_time % 4) * 15
        end_hour = (start_time + shift['length']) // 4
        end_minute = ((start_time + shift['length']) % 4) * 15
        
        print(f"    Day {day}: {start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d} "
              f"({shift['type']})")
    
    # Visualize the tour schedule
    plt.figure(figsize=(12, 4))
    ax = plt.gca()
    
    # Define colors for different shift types
    colors = {'8-hour': '#1f77b4', '6-hour': '#ff7f0e', '4-hour': '#2ca02c'}
    
    # Plot each shift
    for day, start_time, shift_idx in sorted_shifts:
        shift = model.shift_shells[shift_idx]
        shift_type = shift['type']
        
        # Convert to hours for better visualization
        start_hour = start_time / 4
        duration = shift['length'] / 4
        
        # Plot the shift
        ax.barh(day, duration, left=start_hour, height=0.6, 
                color=colors.get(shift_type, '#7f7f7f'),
                edgecolor='black', alpha=0.7)
        
        # Add text label
        ax.text(start_hour + duration/2, day, shift_type, 
                ha='center', va='center', fontsize=8)
    
    # Set labels and title
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Day')
    ax.set_title(f'Tour {tour_id} Schedule')
    
    # Set x-axis limits and ticks
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 4))
    
    # Set y-axis limits and ticks
    ax.set_ylim(0.5, model.num_days + 0.5)
    ax.set_yticks(range(1, model.num_days + 1))
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor=color, edgecolor='black', label=shift_type)
                      for shift_type, color in colors.items()]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.show()


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
    
    # View tours
    view_tours(model, num_tours=10, detailed=True, output_dir='results')
    
    # View details for a specific tour
    view_tour_details(model, tour_id=1)
    
    # Compare stochastic vs. deterministic approaches
    comparison = compare_stochastic_vs_deterministic(
        seed=42,
        num_employees=40,
        num_scenarios=5,
        output_dir='results/comparison'
    )
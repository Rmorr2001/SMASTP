#!/usr/bin/env python3
"""
Timing Comparison - Compare calculation times between stochastic and deterministic approaches
"""

import os
import sys
import time
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from main import compare_stochastic_vs_deterministic

def run_timing_comparison(num_employees_list, num_scenarios_list, output_dir='./timing_comparison'):
    """
    Run timing comparison with different parameters
    
    Args:
        num_employees_list: List of employee counts to test
        num_scenarios_list: List of scenario counts to test
        output_dir: Directory to save results
    
    Returns:
        DataFrame with comparison results
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Store results
    results = []
    
    # Run comparisons for each parameter combination
    for num_employees in num_employees_list:
        for num_scenarios in num_scenarios_list:
            print(f"\n\n{'='*80}")
            print(f"Running comparison with {num_employees} employees and {num_scenarios} scenarios")
            print(f"{'='*80}\n")
            
            # Create subdirectory for this run
            run_dir = os.path.join(output_dir, f"emp{num_employees}_scen{num_scenarios}")
            os.makedirs(run_dir, exist_ok=True)
            
            # Run comparison
            try:
                comparison = compare_stochastic_vs_deterministic(
                    seed=42,
                    num_employees=num_employees,
                    num_scenarios=num_scenarios,
                    output_dir=run_dir
                )
                
                # Extract timing information
                timing = comparison['timing']
                
                # Add to results
                result = {
                    'num_employees': num_employees,
                    'num_scenarios': num_scenarios,
                    'stochastic_setup_time': timing['stochastic']['setup'],
                    'stochastic_solve_time': timing['stochastic']['solve'],
                    'stochastic_total_time': timing['stochastic']['total'],
                    'deterministic_setup_time': timing['deterministic']['setup'],
                    'deterministic_solve_time': timing['deterministic']['solve'],
                    'deterministic_total_time': timing['deterministic']['total'],
                    'evaluation_time': timing['evaluation'],
                    'speedup_factor': comparison['speedup'],
                    'stochastic_objective': comparison['stochastic_objective'],
                    'deterministic_objective': comparison['deterministic_objective'],
                    'det_on_stoch_objective': comparison['det_on_stoch_objective'],
                    'vss': comparison['value_of_stochastic_solution'],
                    'vss_percentage': comparison['vss_percentage']
                }
                
                results.append(result)
                
            except Exception as e:
                print(f"Error running comparison: {e}")
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    # Save results
    df.to_csv(os.path.join(output_dir, 'timing_comparison_results.csv'), index=False)
    
    # Generate summary visualizations
    generate_summary_visualizations(df, output_dir)
    
    return df

def generate_summary_visualizations(df, output_dir):
    """
    Generate summary visualizations from timing comparison results
    
    Args:
        df: DataFrame with comparison results
        output_dir: Directory to save visualizations
    """
    # 1. Speedup factor vs. number of scenarios
    plt.figure(figsize=(10, 6))
    
    # Group by number of scenarios and calculate mean speedup
    scenario_groups = df.groupby('num_scenarios')['speedup_factor'].mean().reset_index()
    
    plt.plot(scenario_groups['num_scenarios'], scenario_groups['speedup_factor'], 
             marker='o', linestyle='-', linewidth=2, markersize=8)
    
    plt.xlabel('Number of Scenarios')
    plt.ylabel('Speedup Factor (Stochastic/Deterministic)')
    plt.title('Impact of Scenario Count on Computational Efficiency')
    plt.grid(True, alpha=0.3)
    
    # Add values on points
    for x, y in zip(scenario_groups['num_scenarios'], scenario_groups['speedup_factor']):
        plt.text(x, y + 0.1, f"{y:.2f}x", ha='center')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'speedup_vs_scenarios.png'))
    
    # 2. Solve time comparison by number of scenarios
    plt.figure(figsize=(12, 6))
    
    # Group by number of scenarios and calculate mean solve times
    scenario_solve_times = df.groupby('num_scenarios')[
        ['stochastic_solve_time', 'deterministic_solve_time']].mean().reset_index()
    
    x = np.arange(len(scenario_solve_times['num_scenarios']))
    width = 0.35
    
    plt.bar(x - width/2, scenario_solve_times['stochastic_solve_time'], 
            width, label='Stochastic', color='#1f77b4')
    plt.bar(x + width/2, scenario_solve_times['deterministic_solve_time'], 
            width, label='Deterministic', color='#ff7f0e')
    
    plt.xlabel('Number of Scenarios')
    plt.ylabel('Solve Time (seconds)')
    plt.title('Solve Time Comparison by Number of Scenarios')
    plt.xticks(x, scenario_solve_times['num_scenarios'])
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    
    # Add values on bars
    for i, v in enumerate(scenario_solve_times['stochastic_solve_time']):
        plt.text(i - width/2, v + 1, f"{v:.1f}s", ha='center', va='bottom', fontsize=9)
    for i, v in enumerate(scenario_solve_times['deterministic_solve_time']):
        plt.text(i + width/2, v + 1, f"{v:.1f}s", ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'solve_time_vs_scenarios.png'))
    
    # 3. VSS percentage vs. number of scenarios
    plt.figure(figsize=(10, 6))
    
    # Group by number of scenarios and calculate mean VSS percentage
    scenario_vss = df.groupby('num_scenarios')['vss_percentage'].mean().reset_index()
    
    plt.plot(scenario_vss['num_scenarios'], scenario_vss['vss_percentage'], 
             marker='o', linestyle='-', linewidth=2, markersize=8, color='#2ca02c')
    
    plt.xlabel('Number of Scenarios')
    plt.ylabel('VSS Percentage (%)')
    plt.title('Value of Stochastic Solution by Number of Scenarios')
    plt.grid(True, alpha=0.3)
    
    # Add values on points
    for x, y in zip(scenario_vss['num_scenarios'], scenario_vss['vss_percentage']):
        plt.text(x, y + 0.2, f"{y:.2f}%", ha='center')
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'vss_vs_scenarios.png'))
    
    # 4. Efficiency vs. Value tradeoff
    plt.figure(figsize=(10, 6))
    
    plt.scatter(df['speedup_factor'], df['vss_percentage'], 
                s=df['num_scenarios']*20, alpha=0.7, c=df['num_scenarios'], cmap='viridis')
    
    plt.xlabel('Computational Cost (Speedup Factor)')
    plt.ylabel('Solution Quality (VSS Percentage)')
    plt.title('Tradeoff Between Computational Cost and Solution Quality')
    plt.grid(True, alpha=0.3)
    plt.colorbar(label='Number of Scenarios')
    
    # Add annotations
    for i, row in df.iterrows():
        plt.annotate(f"E{row['num_employees']},S{row['num_scenarios']}", 
                    (row['speedup_factor'], row['vss_percentage']),
                    xytext=(5, 5), textcoords='offset points', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'efficiency_vs_value_tradeoff.png'))

def main():
    """Main function for timing comparison"""
    parser = argparse.ArgumentParser(description='Timing Comparison for SMASTP')
    
    # Add arguments
    parser.add_argument('--employees', type=str, default='20,40,60', 
                        help='Comma-separated list of employee counts to test')
    parser.add_argument('--scenarios', type=str, default='3,5,10', 
                        help='Comma-separated list of scenario counts to test')
    parser.add_argument('--output', type=str, default='./timing_comparison', 
                        help='Directory to save results')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Convert comma-separated lists to integers
    num_employees_list = [int(x) for x in args.employees.split(',')]
    num_scenarios_list = [int(x) for x in args.scenarios.split(',')]
    
    # Run timing comparison
    results = run_timing_comparison(
        num_employees_list=num_employees_list,
        num_scenarios_list=num_scenarios_list,
        output_dir=args.output
    )
    
    # Print summary
    print("\n\n--- TIMING COMPARISON SUMMARY ---")
    print(results[['num_employees', 'num_scenarios', 'stochastic_total_time', 
                  'deterministic_total_time', 'speedup_factor', 'vss_percentage']])

if __name__ == "__main__":
    main() 
import os
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pyomo.environ as pyo
from collections import defaultdict
import time

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
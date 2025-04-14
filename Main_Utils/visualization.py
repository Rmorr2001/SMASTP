import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import os
from collections import defaultdict
import time

class VisualizationMixin:
    def visualize_solution(self, output_dir='.'):
        """
        Visualize the solution with various plots and charts
        
        Args:
            output_dir: Directory to save the visualization files
        """
        if not self.solution:
            print("No solution to visualize. Please solve the model first.")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        start_time = time.time()
        print("Generating solution visualizations...")
        
        # 1. Tour assignments visualization
        self._visualize_tour_assignments(output_dir)
        
        # 2. Shift distribution visualization
        self._visualize_shift_distribution(output_dir)
        
        # 3. Employee schedule visualization 
        self._visualize_employee_schedules(output_dir)
        
        # 4. Demand vs. coverage visualization
        self._visualize_demand_vs_coverage(output_dir)
        
        # 5. Processing times visualization
        self._visualize_processing_times(output_dir)
        
        self.processing_times['visualize'] = time.time() - start_time
        print(f"Visualizations completed in {self.processing_times['visualize']:.2f} seconds")
    
    def _visualize_tour_assignments(self, output_dir):
        """Visualize tour assignments"""
        print("Generating tour assignments visualization...")
        
        # Extract tour assignments
        tour_assignments = self.solution['tour_assignments']
        
        if not tour_assignments:
            print("No tour assignments found in solution.")
            return
        
        # Get tour properties
        tour_data = []
        for tour_idx, count in tour_assignments.items():
            # Skip if tour index is invalid
            if tour_idx > len(self.tours):
                continue
                
            # Get the tour
            tour = self.tours[tour_idx-1]
            
            # Calculate properties
            working_days = len(set(self.shift_shells[idx]['day'] for idx in tour))
            working_length = sum(self.shift_shells[idx]['working_length'] for idx in tour)
            
            # Count shift types
            shift_types = defaultdict(int)
            for idx in tour:
                shift_types[self.shift_shells[idx]['type']] += 1
            
            # Add to data
            tour_data.append({
                'tour_idx': tour_idx,
                'count': count,
                'working_days': working_days,
                'working_length': working_length / 4,  # Convert to hours
                '8-hour_shifts': shift_types.get('8-hour', 0),
                '6-hour_shifts': shift_types.get('6-hour', 0),
                '4-hour_shifts': shift_types.get('4-hour', 0)
            })
        
        # Create a DataFrame
        df = pd.DataFrame(tour_data)
        
        # Plot 1: Tour assignment counts
        plt.figure(figsize=(12, 6))
        
        if len(df) > 0:
            # Sort by count
            df_sorted = df.sort_values('count', ascending=False).head(20)
            
            # Plot
            ax = sns.barplot(x='tour_idx', y='count', data=df_sorted)
            
            # Add values above bars
            for i, v in enumerate(df_sorted['count']):
                ax.text(i, v + 0.1, str(int(v)), ha='center')
            
            plt.title('Number of Employees Assigned to Each Tour Type')
            plt.xlabel('Tour Index')
            plt.ylabel('Number of Employees')
            plt.xticks(rotation=90)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'tour_assignments.png'))
            
            # Plot 2: Tour properties
            fig, axes = plt.subplots(1, 3, figsize=(18, 5))
            
            # Working days
            sns.histplot(df, x='working_days', weights='count', ax=axes[0], discrete=True)
            axes[0].set_title('Distribution of Working Days per Tour')
            axes[0].set_xlabel('Number of Working Days')
            axes[0].set_ylabel('Number of Employees')
            
            # Working hours
            sns.histplot(df, x='working_length', weights='count', ax=axes[1], binwidth=1)
            axes[1].set_title('Distribution of Working Hours per Tour')
            axes[1].set_xlabel('Working Hours per Week')
            axes[1].set_ylabel('Number of Employees')
            
            # Shift types
            shift_counts = {
                '8-hour Shifts': df['8-hour_shifts'].sum(),
                '6-hour Shifts': df['6-hour_shifts'].sum(),
                '4-hour Shifts': df['4-hour_shifts'].sum()
            }
            
            # Calculate shift percentages
            total_shifts = sum(shift_counts.values())
            shift_percentages = {k: (v/total_shifts)*100 if total_shifts > 0 else 0 for k, v in shift_counts.items()}
            
            axes[2].pie(shift_percentages.values(), labels=shift_percentages.keys(), 
                      autopct='%1.1f%%', startangle=90)
            axes[2].set_title('Distribution of Shift Types')
            
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'tour_properties.png'))
        else:
            print("No valid tour data available for visualization.")
    
    def _visualize_shift_distribution(self, output_dir):
        """Visualize shift distribution by day and time"""
        print("Generating shift distribution visualization...")
        
        # Extract shift assignments
        shift_assignments = self.solution['shift_assignments']
        
        if not shift_assignments:
            print("No shift assignments found in solution.")
            return
        
        # Prepare data
        shift_data = []
        for shift_idx, count in shift_assignments.items():
            # Skip if shift index is invalid
            if shift_idx > len(self.shift_shells):
                continue
                
            # Get the shift
            shift = self.shift_shells[shift_idx-1]
            
            # Add to data
            shift_data.append({
                'day': shift['day'],
                'start_time': shift['start_time'],
                'length': shift['length'],
                'type': shift['type'],
                'count': count
            })
        
        # Create a DataFrame
        df = pd.DataFrame(shift_data)
        
        if len(df) > 0:
            # Plot 1: Shifts by day
            plt.figure(figsize=(12, 6))
            
            # Group by day and count
            day_counts = df.groupby('day')['count'].sum().reindex(range(1, self.num_days + 1), fill_value=0)
            
            # Plot
            ax = sns.barplot(x=day_counts.index, y=day_counts.values)
            
            # Add values above bars
            for i, v in enumerate(day_counts.values):
                ax.text(i, v + 0.1, str(int(v)), ha='center')
            
            plt.title('Number of Shifts by Day')
            plt.xlabel('Day')
            plt.ylabel('Number of Shifts')
            plt.xticks(range(7), ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'shifts_by_day.png'))
            
            # Plot 2: Shifts by time
            plt.figure(figsize=(14, 6))
            
            # Process shift start times to hourly blocks
            df['start_hour'] = df['start_time'] // 4  # Convert to hours (4 periods per hour)
            
            # Create an array for all hours
            hours = range(24)
            hour_counts = np.zeros(24)
            
            # Count shifts starting at each hour
            hour_groups = df.groupby('start_hour')['count'].sum()
            for hour, count in hour_groups.items():
                if 0 <= hour < 24:
                    hour_counts[hour] = count
            
            # Plot
            ax = sns.barplot(x=hours, y=hour_counts)
            
            # Add values above bars
            for i, v in enumerate(hour_counts):
                if v > 0:
                    ax.text(i, v + 0.1, str(int(v)), ha='center')
            
            plt.title('Number of Shifts by Starting Hour')
            plt.xlabel('Starting Hour')
            plt.ylabel('Number of Shifts')
            plt.xticks(range(24), [f"{h:02d}:00" for h in range(24)], rotation=90)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'shifts_by_hour.png'))
            
            # Plot 3: Heatmap of shifts by day and hour
            plt.figure(figsize=(14, 8))
            
            # Create a matrix for the heatmap
            heatmap_data = np.zeros((self.num_days, 24))
            
            # Fill the matrix
            for _, row in df.iterrows():
                day = int(row['day']) - 1  # 0-based index
                hour = int(row['start_hour'])
                if 0 <= day < self.num_days and 0 <= hour < 24:
                    heatmap_data[day, hour] += row['count']
            
            # Plot heatmap
            ax = sns.heatmap(heatmap_data, cmap='YlGnBu', linewidths=0.5, 
                           xticklabels=[f"{h:02d}:00" for h in range(24)],
                           yticklabels=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
            
            plt.title('Distribution of Shifts by Day and Starting Hour')
            plt.xlabel('Starting Hour')
            plt.ylabel('Day')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, 'shift_heatmap.png'))
        else:
            print("No valid shift data available for visualization.")
    
    def _visualize_employee_schedules(self, output_dir):
        """Visualize employee schedules"""
        print("Generating employee schedule visualization...")
        
        # Extract tour and shift assignments
        tour_assignments = self.solution['tour_assignments']
        
        if not tour_assignments:
            print("No tour assignments found in solution.")
            return
        
        # Create a representation of the schedule
        schedule = np.zeros((self.num_days, self.num_periods))
        
        # Fill in the schedule
        for tour_idx, count in tour_assignments.items():
            # Skip if tour index is invalid
            if tour_idx > len(self.tours):
                continue
                
            # Get the tour
            tour = self.tours[tour_idx-1]
            
            # Process each shift in the tour
            for shift_idx in tour:
                shift = self.shift_shells[shift_idx]
                day = shift['day'] - 1  # 0-based index
                
                # Add employees to each period of the shift
                for p in range(shift['length']):
                    period = shift['start_time'] + p
                    if period < self.num_periods:
                        schedule[day, period] += count
        
        # Plot 1: Employee schedule heatmap
        plt.figure(figsize=(16, 8))
        
        # Create hour labels
        hour_labels = []
        for hour in range(6, 24):  # 6am to midnight
            for quarter in range(4):
                if quarter == 0:
                    hour_labels.append(f"{hour:02d}:00")
                else:
                    hour_labels.append("")
        
        # Pick a subset of labels to avoid overcrowding
        period_ticks = np.arange(0, self.num_periods, 4)
        period_labels = [hour_labels[i] if i < len(hour_labels) else "" for i in range(0, self.num_periods, 4)]
        
        # Plot heatmap
        ax = sns.heatmap(schedule, cmap='YlGnBu', linewidths=0.5,
                       xticklabels=period_labels,
                       yticklabels=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
        
        plt.title('Number of Employees Scheduled by Day and Time')
        plt.xlabel('Time of Day')
        plt.ylabel('Day')
        plt.xticks(period_ticks, rotation=90)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'employee_schedule.png'))
    
    def _visualize_demand_vs_coverage(self, output_dir):
        """Visualize demand vs coverage for each scenario"""
        print("Generating demand vs coverage visualization...")
        
        # Extract activity assignments
        activity_assignments = self.solution.get('activity_assignments', {})
        
        if not activity_assignments:
            print("No activity assignments found in solution.")
            return
        
        # Select a subset of scenarios to visualize (up to 3)
        scenarios_to_show = list(activity_assignments.keys())[:3]
        
        for scenario in scenarios_to_show:
            # Get the scenario data
            scenario_data = activity_assignments[scenario]
            
            # Create a numpy array for coverage
            coverage = np.zeros((self.num_days, self.num_periods, self.num_activities))
            
            # Fill in the coverage
            for (d, i, j), count in scenario_data.items():
                day_idx = d - 1  # 0-based index
                period_idx = i - 1  # 0-based index
                activity_idx = j - 1  # 0-based index
                
                if (0 <= day_idx < self.num_days and 
                    0 <= period_idx < self.num_periods and 
                    0 <= activity_idx < self.num_activities):
                    coverage[day_idx, period_idx, activity_idx] = count
            
            # Create a numpy array for demand
            demand = np.zeros((self.num_days, self.num_periods, self.num_activities))
            
            # Fill in the demand
            for d in range(1, self.num_days + 1):
                for i in range(1, self.num_periods + 1):
                    for j in range(1, self.num_activities + 1):
                        demand_val = self.scenarios[scenario-1]['demand'].get((d, i, j), 0)
                        demand[d-1, i-1, j-1] = demand_val
            
            # Plot for each activity
            for j in range(1, min(4, self.num_activities + 1)):  # Up to 3 activities
                activity_idx = j - 1
                
                # Create hour labels
                hour_labels = []
                for hour in range(6, 24):  # 6am to midnight
                    hour_labels.append(f"{hour:02d}:00")
                
                # Pick a subset of labels to avoid overcrowding
                period_ticks = np.arange(0, self.num_periods, 4)
                period_labels = [hour_labels[i//4] if i % 4 == 0 and i//4 < len(hour_labels) else "" 
                              for i in range(0, self.num_periods, 4)]
                
                # Plot for each day
                fig, axes = plt.subplots(self.num_days, 1, figsize=(14, 3*self.num_days), sharex=True)
                
                if self.num_days == 1:
                    axes = [axes]  # Make it iterable
                
                for day in range(self.num_days):
                    ax = axes[day]
                    
                    # Get the data for this day and activity
                    day_demand = demand[day, :, activity_idx]
                    day_coverage = coverage[day, :, activity_idx]
                    
                    # Plot
                    x = np.arange(len(day_demand))
                    ax.plot(x, day_demand, 'r-', label='Demand', linewidth=2)
                    ax.plot(x, day_coverage, 'b-', label='Coverage', linewidth=2)
                    ax.fill_between(x, day_demand, day_coverage, 
                                  where=(day_coverage < day_demand), 
                                  color='red', alpha=0.3, label='Undercoverage')
                    ax.fill_between(x, day_demand, day_coverage, 
                                  where=(day_coverage > day_demand), 
                                  color='green', alpha=0.3, label='Overcoverage')
                    
                    # Set labels
                    ax.set_title(f"Day {day+1} - {'Mon Tue Wed Thu Fri Sat Sun'.split()[day]}")
                    ax.set_ylabel('Employees')
                    ax.set_xlim(0, len(day_demand)-1)
                    ax.grid(True, alpha=0.3)
                    
                    # Add legend to first subplot only
                    if day == 0:
                        ax.legend()
                
                # Set x-ticks for the last subplot
                axes[-1].set_xticks(period_ticks)
                axes[-1].set_xticklabels(period_labels)
                axes[-1].set_xlabel('Time of Day')
                
                # Set overall title
                fig.suptitle(f'Demand vs. Coverage for Activity {j} - Scenario {scenario}', fontsize=16)
                
                plt.tight_layout(rect=[0, 0, 1, 0.97])
                plt.savefig(os.path.join(output_dir, f'demand_vs_coverage_scenario{scenario}_activity{j}.png'))
                plt.close()
    
    def _visualize_processing_times(self, output_dir):
        """Visualize processing times for different stages"""
        print("Generating processing times visualization...")
        
        if not self.processing_times:
            print("No processing times available.")
            return
        
        # Create labels and values
        labels = []
        values = []
        
        for stage, time_taken in self.processing_times.items():
            labels.append(stage)
            values.append(time_taken)
        
        # Plot
        plt.figure(figsize=(10, 6))
        ax = sns.barplot(x=labels, y=values)
        
        # Add values above bars
        for i, v in enumerate(values):
            ax.text(i, v + 0.1, f"{v:.2f}s", ha='center')
        
        plt.title('Processing Times for Different Stages')
        plt.xlabel('Stage')
        plt.ylabel('Time (seconds)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'processing_times.png'))
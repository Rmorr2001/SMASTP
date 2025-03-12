import pandas as pd
import os
import pickle
import time
from collections import defaultdict

class ReportingMixin:
    def export_solution(self, filename):
        """
        Export the solution to a file
        
        Args:
            filename: Name of the file to save the solution
        """
        if not self.solution:
            print("No solution to export. Please solve the model first.")
            return
        
        print(f"Exporting solution to {filename}...")
        
        # Save solution using pickle
        with open(filename, 'wb') as f:
            pickle.dump(self.solution, f)
    
    def import_solution(self, filename):
        """
        Import a solution from a file
        
        Args:
            filename: Name of the file to load the solution from
        """
        print(f"Importing solution from {filename}...")
        
        # Load solution using pickle
        with open(filename, 'rb') as f:
            self.solution = pickle.load(f)
            
        print("Solution imported successfully.")
    
    def generate_reports(self, output_dir='.'):
        """
        Generate detailed reports from the solution
        
        Args:
            output_dir: Directory to save the reports
        """
        if not self.solution:
            print("No solution to report. Please solve the model first.")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        print("Generating solution reports...")
        
        # 1. Tour assignments report
        self._generate_tour_report(output_dir)
        
        # 2. Shift assignments report
        self._generate_shift_report(output_dir)
        
        # 3. Activity assignments report
        self._generate_activity_report(output_dir)
        
        # 4. Coverage analysis report
        self._generate_coverage_report(output_dir)
        
        print("Reports generation complete.")
    
    def _generate_tour_report(self, output_dir):
        """Generate tour assignments report"""
        print("Generating tour assignments report...")
        
        # Extract tour assignments
        tour_assignments = self.solution['tour_assignments']
        
        if not tour_assignments:
            print("No tour assignments found in solution.")
            return
        
        # Prepare data
        rows = []
        for tour_idx, count in tour_assignments.items():
            # Skip if tour index is invalid
            if tour_idx > len(self.tours):
                continue
                
            # Get the tour
            tour = self.tours[tour_idx-1]
            
            # Calculate properties
            # Calculate properties
            working_days = len(set(self.shift_shells[idx]['day'] for idx in tour))
            working_length = sum(self.shift_shells[idx]['working_length'] for idx in tour)
            
            # Get shift details
            shift_details = []
            for idx in tour:
                shift = self.shift_shells[idx]
                start_hour = shift['start_time'] // 4
                start_min = (shift['start_time'] % 4) * 15
                
                end_time = shift['start_time'] + shift['length']
                end_hour = end_time // 4
                end_min = (end_time % 4) * 15
                
                shift_details.append(
                    f"Day {shift['day']}: {start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d} ({shift['type']})"
                )
            
            # Add row
            rows.append({
                'Tour ID': tour_idx,
                'Employees': count,
                'Working Days': working_days,
                'Working Hours': working_length / 4,  # Convert to hours
                'Shift Details': ', '.join(shift_details)
            })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(rows)
        df.to_csv(os.path.join(output_dir, 'tour_assignments.csv'), index=False)
        
        # Also create a summary
        summary = pd.DataFrame({
            'Total Tours Used': len(rows),
            'Total Employees': sum(row['Employees'] for row in rows),
            'Avg Working Days': sum(row['Working Days'] * row['Employees'] for row in rows) / sum(row['Employees'] for row in rows),
            'Avg Working Hours': sum(row['Working Hours'] * row['Employees'] for row in rows) / sum(row['Employees'] for row in rows)
        }, index=[0])
        
        summary.to_csv(os.path.join(output_dir, 'tour_summary.csv'), index=False)
    
    def _generate_shift_report(self, output_dir):
        """Generate shift assignments report"""
        print("Generating shift assignments report...")
        
        # Extract shift assignments
        shift_assignments = self.solution['shift_assignments']
        
        if not shift_assignments:
            print("No shift assignments found in solution.")
            return
        
        # Prepare data
        rows = []
        for shift_idx, count in shift_assignments.items():
            # Skip if shift index is invalid
            if shift_idx > len(self.shift_shells):
                continue
                
            # Get the shift
            shift = self.shift_shells[shift_idx-1]
            
            # Calculate time in readable format
            start_hour = shift['start_time'] // 4
            start_min = (shift['start_time'] % 4) * 15
            
            end_time = shift['start_time'] + shift['length']
            end_hour = end_time // 4
            end_min = (end_time % 4) * 15
            
            # Add row
            rows.append({
                'Shift ID': shift_idx,
                'Day': shift['day'],
                'Day Name': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][shift['day']-1],
                'Start Time': f"{start_hour:02d}:{start_min:02d}",
                'End Time': f"{end_hour:02d}:{end_min:02d}",
                'Length (hours)': shift['length'] / 4,  # Convert to hours
                'Type': shift['type'],
                'Employees': count
            })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(rows)
        df.to_csv(os.path.join(output_dir, 'shift_assignments.csv'), index=False)
        
        # Also create a summary by day
        summary = df.groupby(['Day', 'Day Name']).agg({
            'Employees': 'sum',
            'Shift ID': 'count'
        }).reset_index()
        
        summary.columns = ['Day', 'Day Name', 'Total Employees', 'Unique Shifts']
        summary.to_csv(os.path.join(output_dir, 'shift_summary_by_day.csv'), index=False)
        
        # Create a summary by shift type
        type_summary = df.groupby('Type').agg({
            'Employees': 'sum',
            'Shift ID': 'count'
        }).reset_index()
        
        type_summary.columns = ['Shift Type', 'Total Employees', 'Unique Shifts']
        type_summary.to_csv(os.path.join(output_dir, 'shift_summary_by_type.csv'), index=False)
    
    def _generate_activity_report(self, output_dir):
        """Generate activity assignments report"""
        print("Generating activity assignments report...")
        
        # Extract activity assignments
        activity_assignments = self.solution.get('activity_assignments', {})
        
        if not activity_assignments:
            print("No activity assignments found in solution.")
            return
        
        # Process up to the first 3 scenarios
        scenarios_to_process = list(activity_assignments.keys())[:3]
        
        for scenario in scenarios_to_process:
            # Get scenario data
            scenario_data = activity_assignments[scenario]
            
            # Prepare data
            rows = []
            for (d, i, j), count in scenario_data.items():
                # Calculate time in readable format
                hour = (i - 1) // 4
                minute = ((i - 1) % 4) * 15
                
                # Add row
                rows.append({
                    'Scenario': scenario,
                    'Day': d,
                    'Day Name': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d-1],
                    'Period': i,
                    'Time': f"{hour:02d}:{minute:02d}",
                    'Activity': f"Activity {j}",
                    'Employees': count
                })
            
            # Create DataFrame and save to CSV
            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(os.path.join(output_dir, f'activity_assignments_scenario_{scenario}.csv'), index=False)
                
                # Create aggregated views
                by_day_activity = df.groupby(['Day', 'Day Name', 'Activity']).agg({
                    'Employees': ['mean', 'max', 'min']
                }).reset_index()
                
                by_day_activity.columns = ['Day', 'Day Name', 'Activity', 'Avg Employees', 'Max Employees', 'Min Employees']
                by_day_activity.to_csv(os.path.join(output_dir, f'activity_summary_by_day_scenario_{scenario}.csv'), index=False)
                
                # Summary by hour
                df['Hour'] = df['Time'].str.split(':', expand=True)[0].astype(int)
                by_hour_activity = df.groupby(['Hour', 'Activity']).agg({
                    'Employees': ['mean', 'max', 'min']
                }).reset_index()
                
                by_hour_activity.columns = ['Hour', 'Activity', 'Avg Employees', 'Max Employees', 'Min Employees']
                by_hour_activity.to_csv(os.path.join(output_dir, f'activity_summary_by_hour_scenario_{scenario}.csv'), index=False)
    
    def _generate_coverage_report(self, output_dir):
        """Generate coverage analysis report"""
        print("Generating coverage analysis report...")
        
        # Extract activity assignments
        activity_assignments = self.solution.get('activity_assignments', {})
        
        if not activity_assignments:
            print("No activity assignments found in solution.")
            return
        
        # Process up to the first 3 scenarios
        scenarios_to_process = list(activity_assignments.keys())[:3]
        
        for scenario in scenarios_to_process:
            # Get scenario data
            scenario_data = activity_assignments[scenario]
            
            # Prepare data for coverage comparison
            coverage_rows = []
            
            for d in range(1, self.num_days + 1):
                for i in range(1, self.num_periods + 1):
                    for j in range(1, self.num_activities + 1):
                        # Get demand for this scenario
                        demand = self.scenarios[scenario-1]['demand'].get((d, i, j), 0)
                        
                        # Get coverage (employees assigned)
                        coverage = scenario_data.get((d, i, j), 0)
                        
                        # Calculate gap
                        gap = coverage - demand
                        
                        # Calculate time in readable format
                        hour = (i - 1) // 4
                        minute = ((i - 1) % 4) * 15
                        
                        # Add row
                        coverage_rows.append({
                            'Scenario': scenario,
                            'Day': d,
                            'Day Name': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d-1],
                            'Period': i,
                            'Time': f"{hour:02d}:{minute:02d}",
                            'Activity': f"Activity {j}",
                            'Demand': demand,
                            'Coverage': coverage,
                            'Gap': gap,
                            'Status': 'Overcover' if gap > 0 else ('Undercover' if gap < 0 else 'Exact')
                        })
            
            # Create DataFrame and save to CSV
            if coverage_rows:
                coverage_df = pd.DataFrame(coverage_rows)
                coverage_df.to_csv(os.path.join(output_dir, f'coverage_analysis_scenario_{scenario}.csv'), index=False)
                
                # Create summaries
                # 1. By day and activity
                by_day = coverage_df.groupby(['Day', 'Day Name', 'Activity']).agg({
                    'Demand': 'sum',
                    'Coverage': 'sum',
                    'Gap': 'sum',
                    'Status': lambda x: (x == 'Overcover').sum() / len(x) * 100  # Percentage overcover
                }).reset_index()
                
                by_day.columns = ['Day', 'Day Name', 'Activity', 'Total Demand', 'Total Coverage', 
                                  'Total Gap', '% Overcover Periods']
                by_day['% Undercover Periods'] = 100 - by_day['% Overcover Periods'] - (
                    coverage_df.groupby(['Day', 'Day Name', 'Activity'])['Status']
                    .apply(lambda x: (x == 'Exact').sum() / len(x) * 100)
                    .values
                )
                
                by_day.to_csv(os.path.join(output_dir, f'coverage_summary_by_day_scenario_{scenario}.csv'), index=False)
                
                # 2. Overall summary
                summary = pd.DataFrame({
                    'Total Demand': [coverage_df['Demand'].sum()],
                    'Total Coverage': [coverage_df['Coverage'].sum()],
                    'Net Gap': [coverage_df['Gap'].sum()],
                    'Overcover Periods': [(coverage_df['Status'] == 'Overcover').sum()],
                    'Exact Cover Periods': [(coverage_df['Status'] == 'Exact').sum()],
                    'Undercover Periods': [(coverage_df['Status'] == 'Undercover').sum()],
                    '% Overcover': [(coverage_df['Status'] == 'Overcover').mean() * 100],
                    '% Exact Cover': [(coverage_df['Status'] == 'Exact').mean() * 100],
                    '% Undercover': [(coverage_df['Status'] == 'Undercover').mean() * 100]
                })
                
                summary.to_csv(os.path.join(output_dir, f'coverage_overall_summary_scenario_{scenario}.csv'), index=False)
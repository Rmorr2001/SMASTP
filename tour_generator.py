import random
import itertools
from collections import defaultdict
import numpy as np

class TourGenerator:
    """Enhanced tour generator based on stochastic programming approach"""
    
    def __init__(self, num_days, min_working_days, max_working_days, min_tour_length, max_tour_length, min_rest_time):
        """
        Initialize the tour generator with tour constraints
        """
        self.num_days = num_days
        self.min_working_days = min_working_days
        self.max_working_days = max_working_days
        self.min_tour_length = min_tour_length
        self.max_tour_length = max_tour_length
        self.min_rest_time = min_rest_time
        self.demand_profiles = None
        self.dual_values = None
        
    def generate_tours(self, shift_shells, demand_scenarios=None, max_tours=1000, diversity_factor=0.5):
        """
        Generate feasible tours by combining shift shells with enhanced diversity
        
        Args:
            shift_shells: List of shift shells
            demand_scenarios: Optional list of demand scenarios for robust tour generation
            max_tours: Maximum number of tours to generate
            diversity_factor: Factor to control diversity (0-1)
        
        Returns:
            List of valid tours
        """
        tours = []
        shift_shells_by_day = defaultdict(list)
        
        # Group shift shells by day
        for idx, shift in enumerate(shift_shells):
            shift_shells_by_day[shift['day']].append(idx)
        
        print(f"Generating tours with {len(shift_shells)} shift shells across {len(shift_shells_by_day)} days")
        
        # Store demand profiles if available
        if demand_scenarios:
            self.demand_profiles = self._process_demand_scenarios(demand_scenarios)
        
        # Generate diverse sets of working days based on improved strategy
        working_day_sets = self._generate_diverse_working_day_sets(diversity_factor)
        
        # Track created tour patterns to ensure diversity
        tour_patterns = set()
        generated_tour_metrics = []
        
        # For each set of working days
        for working_days in working_day_sets:
            # Generate day combinations with improved sampling strategy
            day_combinations = self._generate_day_combinations(working_days)
            
            # Make sure we have day combinations
            if not day_combinations:
                print(f"WARNING: No day combinations for {working_days} working days")
                continue
            
            # Sample combinations using adaptive strategy
            sampled_combinations = self._sample_combinations(
                day_combinations, 
                min(100, len(day_combinations)),
                generated_tour_metrics
            )
            
            for day_combo in sampled_combinations:
                # For each combination of working days, select shift options
                shift_options = [shift_shells_by_day[d] for d in day_combo]
                
                # Skip if any day has no shifts
                if any(not options for options in shift_options):
                    continue
                
                # Iteratively improve tours with adaptive sampling
                num_attempts = self._calculate_attempt_count(working_days, len(tours))
                
                for attempt in range(num_attempts):
                    # Generate tour with improved methods
                    tour, tour_metrics = self._generate_single_tour(
                        day_combo, shift_options, shift_shells, attempt
                    )
                    
                    if tour:
                        # Create a tour pattern string for diversity checking
                        pattern = self._get_tour_pattern(tour, shift_shells)
                        if pattern not in tour_patterns:
                            tour_patterns.add(pattern)
                            tours.append(tour)
                            generated_tour_metrics.append(tour_metrics)
                    
                    # Limit the number of tours and apply adaptive stopping
                    if len(tours) >= max_tours:
                        break
                
                if len(tours) >= max_tours:
                    break
        
        # If we couldn't generate enough tours, add fallback tours with improved fallback mechanism
        if len(tours) < min(max_tours, 100):
            self._add_fallback_tours(tours, shift_shells, generated_tour_metrics, max_tours)
        
        print(f"Tour generation complete: {len(tours)} valid tours created")
        
        # Analyze and report on tour diversity
        self._analyze_tour_diversity(tours, shift_shells)
        
        return tours
    
    def _process_demand_scenarios(self, demand_scenarios):
        """Process demand scenarios to extract useful profiles for tour generation"""
        demand_profiles = {}
        
        # Extract key patterns from demand scenarios
        for scenario in demand_scenarios:
            scenario_demand = scenario['demand']
            
            # Create day profiles
            for day in range(1, self.num_days + 1):
                if day not in demand_profiles:
                    demand_profiles[day] = {
                        'total': 0,
                        'peak_periods': set(),
                        'low_periods': set()
                    }
                
                # Identify peak and low demand periods
                day_demand = []
                for period in range(1, 96):  # Assuming 96 periods per day
                    for activity in range(1, 3):  # Assuming up to 2 activities
                        day_demand.append(scenario_demand.get((day, period, activity), 0))
                
                # Skip if no demand data for this day
                if not day_demand:
                    continue
                    
                # Update total demand
                demand_profiles[day]['total'] += sum(day_demand)
                
                # Find peak periods (top 25%)
                threshold_high = np.percentile(day_demand, 75)
                threshold_low = np.percentile(day_demand, 25)
                
                for period in range(1, 96):
                    period_demand = sum(scenario_demand.get((day, period, activity), 0) 
                                      for activity in range(1, 3))
                    
                    if period_demand >= threshold_high:
                        demand_profiles[day]['peak_periods'].add(period)
                    elif period_demand <= threshold_low:
                        demand_profiles[day]['low_periods'].add(period)
        
        # Normalize by number of scenarios
        for day in demand_profiles:
            demand_profiles[day]['total'] /= len(demand_scenarios)
        
        return demand_profiles
    
    def _generate_diverse_working_day_sets(self, diversity_factor):
        """Generate diverse sets of working days using advanced diversity strategy"""
        working_day_sets = []
        
        # Base working day sets (always include min and max)
        working_day_sets.append(self.min_working_days)
        if self.min_working_days != self.max_working_days:
            working_day_sets.append(self.max_working_days)
        
        # Calculate step size based on diversity factor 
        # (smaller step size = more diverse options)
        step = max(1, int(1 / (diversity_factor * 2)))
        
        # Add intermediate working days
        for days in range(self.min_working_days + step, self.max_working_days, step):
            working_day_sets.append(days)
            
        # If demand profiles are available, add weighted day counts
        if self.demand_profiles:
            # Sort days by total demand
            sorted_days = sorted(
                range(1, self.num_days + 1),
                key=lambda d: self.demand_profiles.get(d, {}).get('total', 0),
                reverse=True
            )
            
            # Create working day sets focused on high-demand days
            for working_days in range(self.min_working_days, self.max_working_days + 1):
                if working_days not in working_day_sets:
                    working_day_sets.append(working_days)
        
        return working_day_sets
    
    def _generate_day_combinations(self, working_days):
        """Generate day combinations with improved strategy"""
        # Basic combinations
        day_combinations = list(itertools.combinations(range(1, self.num_days + 1), working_days))
        
        # If demand profiles are available, generate additional combinations
        # focused on high-demand days
        if self.demand_profiles:
            # Sort days by total demand
            sorted_days = sorted(
                range(1, self.num_days + 1),
                key=lambda d: self.demand_profiles.get(d, {}).get('total', 0),
                reverse=True
            )
            
            # Add combinations that prioritize high-demand days
            high_demand_days = sorted_days[:working_days]
            remaining_days = sorted_days[working_days:]
            
            # Generate variations that include most high-demand days
            for i in range(min(2, working_days)):
                for removed in itertools.combinations(high_demand_days, i):
                    for added in itertools.combinations(remaining_days, i):
                        new_combo = tuple(sorted(
                            [d for d in high_demand_days if d not in removed] + list(added)
                        ))
                        if new_combo not in day_combinations and len(new_combo) == working_days:
                            day_combinations.append(new_combo)
        
        return day_combinations
    
    def _calculate_attempt_count(self, working_days, current_tour_count):
        """Adaptively calculate number of attempts based on progress"""
        # Base attempt count
        base_attempts = 15
        
        # Adjust based on working days (more attempts for key working day counts)
        if working_days == self.min_working_days or working_days == self.max_working_days:
            base_attempts += 5
            
        # Adjust based on current progress
        if current_tour_count < 10:
            # Early in the process, try harder to find diverse tours
            return base_attempts + 10
        elif current_tour_count > 500:
            # Later in the process, reduce attempts to focus on quality
            return max(5, base_attempts - 5)
            
        return base_attempts
        
    def _sample_combinations(self, combinations, sample_size, existing_tour_metrics=None):
        """Sample combinations with improved diversity and adaptive focus"""
        if len(combinations) <= sample_size:
            return combinations
        
        # Simple case - no existing metrics
        if not existing_tour_metrics:
            return self._sample_combinations_by_distance(combinations, sample_size)
        
        # Advanced case - use existing tour metrics to guide sampling
        return self._adaptive_sample_combinations(combinations, sample_size, existing_tour_metrics)
    
    def _sample_combinations_by_distance(self, combinations, sample_size):
        """Sample diverse combinations using distance-based approach"""
        selected = []
        remaining = list(combinations)
        
        # Select first combination randomly
        first_idx = random.randint(0, len(remaining) - 1)
        selected.append(remaining.pop(first_idx))
        
        # Select remaining combinations to maximize diversity
        while len(selected) < sample_size and remaining:
            # Calculate "distance" from each remaining combination to selected ones
            max_min_distance = -1
            best_idx = -1
            
            for idx, combo in enumerate(remaining):
                min_distance = min(self._combination_distance(combo, sel) for sel in selected)
                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(remaining.pop(best_idx))
            else:
                # If no good candidate found, select randomly
                rand_idx = random.randint(0, len(remaining) - 1)
                selected.append(remaining.pop(rand_idx))
        
        return selected
    
    def _adaptive_sample_combinations(self, combinations, sample_size, existing_tour_metrics):
        """
        Adaptively sample combinations focusing on promising areas
        based on existing tour performance metrics
        """
        selected = []
        
        # Extract day patterns from successful tours
        successful_day_patterns = []
        for metrics in existing_tour_metrics:
            if metrics.get('quality_score', 0) > 0.7:  # Focus on high-quality tours
                successful_day_patterns.append(metrics.get('days', []))
        
        # Split sample budget between exploration and exploitation
        exploit_size = min(int(sample_size * 0.7), len(combinations))
        explore_size = sample_size - exploit_size
        
        # Rank combinations based on similarity to successful patterns
        combo_scores = []
        for combo in combinations:
            score = 0
            # Boost score for combinations similar to successful ones
            for pattern in successful_day_patterns:
                similarity = len(set(combo).intersection(set(pattern))) / len(set(combo).union(set(pattern)))
                score += similarity
            
            # Add some randomness
            score += random.uniform(0, 0.3)
            combo_scores.append((combo, score))
        
        # Sort by score for exploitation portion
        sorted_combos = sorted(combo_scores, key=lambda x: x[1], reverse=True)
        
        # Select top-scoring combinations for exploitation
        selected = [combo for combo, _ in sorted_combos[:exploit_size]]
        
        # Add random selections for exploration
        remaining = [combo for combo, _ in sorted_combos[exploit_size:]]
        if remaining and explore_size > 0:
            selected.extend(random.sample(remaining, min(explore_size, len(remaining))))
        
        return selected
    
    def _combination_distance(self, combo1, combo2):
        """Calculate improved distance between two combinations"""
        # Use Jaccard distance (complement of Jaccard similarity)
        set1 = set(combo1)
        set2 = set(combo2)
        
        # Return Jaccard distance
        union_size = len(set1.union(set2))
        if union_size == 0:
            return 0
        
        return 1 - (len(set1.intersection(set2)) / union_size)
    
    def _generate_single_tour(self, day_combo, shift_options, shift_shells, attempt):
        """Generate a single tour with improved approach"""
        # Generate shift weights informed by attempt number and demand profiles
        shift_weights = self._generate_shift_weights(shift_options, attempt, shift_shells)
        
        # Start with an empty tour
        tour = []
        total_working_length = 0
        days_covered = set()
        tour_metrics = {
            'days': day_combo,
            'quality_score': 0,
            'shift_types': defaultdict(int)
        }
        
        # For each working day, select a shift
        for d_idx, d in enumerate(day_combo):
            available_shifts = shift_options[d_idx]
            if not available_shifts:
                continue
                
            # Use weighted sampling to select a shift
            weights = [shift_weights.get((d, shift_idx), 1.0) for shift_idx in available_shifts]
            shift_idx = self._weighted_choice(available_shifts, weights)
            shift = shift_shells[shift_idx]
            
            # Check if adding this shift respects rest time constraints
            valid = self._is_valid_shift_addition(shift, tour, shift_shells)
            
            if valid and d not in days_covered:
                tour.append(shift_idx)
                total_working_length += shift['working_length']
                days_covered.add(d)
                
                # Track shift types for metrics
                tour_metrics['shift_types'][shift['type']] += 1
        
        # Check if tour meets all requirements
        if (len(days_covered) >= self.min_working_days and
            len(days_covered) <= self.max_working_days and
            self.min_tour_length <= total_working_length <= self.max_tour_length):
            
            # Calculate tour quality score
            tour_metrics['quality_score'] = self._calculate_tour_quality(
                tour, shift_shells, total_working_length, len(days_covered)
            )
            
            return tour, tour_metrics
        
        return None, None
    
    def _generate_shift_weights(self, shift_options, attempt, shift_shells):
        """
        Generate weights for shift selection to encourage diversity
        Enhanced with demand awareness and time-of-day preferences
        """
        weights = {}
        
        # Define time-of-day period groupings (in 15-min periods)
        morning_periods = range(24, 48)     # 6am-12pm
        afternoon_periods = range(48, 72)   # 12pm-6pm
        evening_periods = range(72, 96)     # 6pm-12am
        
        # Generate different weight profiles based on attempt number
        # with more sophisticated patterns
        weight_profile = attempt % 8
        
        for d_idx, options in enumerate(shift_options):
            day = d_idx + 1
            
            # Apply different weighting strategies
            for shift_idx in options:
                # Start with base weight
                base_weight = 1.0
                
                # Adjust weight based on policy
                if weight_profile == 0:
                    # Morning shifts
                    base_weight = 2.0 if shift_idx % 3 == 0 else 0.5
                elif weight_profile == 1:
                    # Afternoon shifts
                    base_weight = 2.0 if shift_idx % 3 == 1 else 0.5
                elif weight_profile == 2:
                    # Evening shifts
                    base_weight = 2.0 if shift_idx % 3 == 2 else 0.5
                elif weight_profile == 3:
                    # 8-hour shifts
                    base_weight = 2.0 if shift_idx % 3 == 0 else 1.0
                elif weight_profile == 4:
                    # 6-hour shifts
                    base_weight = 2.0 if shift_idx % 3 == 1 else 1.0
                elif weight_profile == 5:
                    # 4-hour shifts
                    base_weight = 2.0 if shift_idx % 3 == 2 else 1.0
                elif weight_profile == 6:
                    # Even mix
                    base_weight = 1.0
                else:
                    # Random weights
                    base_weight = random.uniform(0.5, 2.0)
                
                # If demand profiles are available, boost weights for shifts covering peak periods
                if self.demand_profiles and day in self.demand_profiles:
                    shift = shift_shells[shift_idx]
                    shift_periods = range(shift['start_time'], shift['start_time'] + shift['length'])
                    
                    # Check overlap with peak demand periods
                    peak_periods = self.demand_profiles[day]['peak_periods']
                    if peak_periods:
                        overlap = len(set(shift_periods).intersection(peak_periods))
                        # Boost weight proportionally to overlap with peak periods
                        if overlap > 0:
                            base_weight *= (1 + (overlap / len(shift_periods)))
                
                weights[(day, shift_idx)] = base_weight
        
        return weights
    
    def _weighted_choice(self, options, weights):
        """Select an option using weighted random choice with improved implementation"""
        total = sum(weights)
        if total <= 0:
            return random.choice(options)
            
        # Use numpy for more efficient weighted choice
        return np.random.choice(options, p=[w/total for w in weights])
    
    def _is_valid_shift_addition(self, new_shift, current_tour, shift_shells):
        """Check if adding a new shift results in a valid tour with comprehensive checks"""
        for prev_shift_idx in current_tour:
            prev_shift = shift_shells[prev_shift_idx]
            
            # Check rest time between shifts
            if not self._check_rest_time(prev_shift, new_shift):
                return False
                
            # Check for day conflicts
            if prev_shift['day'] == new_shift['day']:
                return False
        
        return True
    
    def _check_rest_time(self, prev_shift, curr_shift):
        """
        Check if there's sufficient rest time between shifts
        Enhanced with proper handling of period calculations
        """
        # Convert everything to a common time scale (periods from start of week)
        prev_day_offset = (prev_shift['day'] - 1) * 96  # 96 periods per day
        prev_start = prev_day_offset + prev_shift['start_time']
        prev_end = prev_start + prev_shift['length']
        
        curr_day_offset = (curr_shift['day'] - 1) * 96
        curr_start = curr_day_offset + curr_shift['start_time']
        
        # Calculate rest time in periods
        if curr_start > prev_end:
            rest_time = curr_start - prev_end
        else:
            # Handle case where current shift is before previous (circular week)
            rest_time = (7 * 96) - prev_end + curr_start
        
        return rest_time >= self.min_rest_time
    
    def _get_tour_pattern(self, tour, shift_shells):
        """Create a comprehensive pattern string representing the tour structure"""
        day_to_shift = {}
        
        for shift_idx in tour:
            shift = shift_shells[shift_idx]
            shift_type = shift['type'][0]  # First character of shift type
            day_to_shift[shift['day']] = f"{shift_type}{shift['start_time']}"
            
        pattern = []
        for day in range(1, self.num_days + 1):
            if day in day_to_shift:
                pattern.append(day_to_shift[day])
            else:
                pattern.append('X')  # Day off
                
        return '-'.join(pattern)
    
    def _calculate_tour_quality(self, tour, shift_shells, working_length, working_days):
        """Calculate a quality score for a tour based on various metrics"""
        # Start with base quality
        quality = 0.5
        
        # Adjust based on working length - prefer tours closer to max
        length_ratio = (working_length - self.min_tour_length) / (self.max_tour_length - self.min_tour_length)
        quality += length_ratio * 0.2
        
        # Adjust based on working days - prefer more working days
        days_ratio = (working_days - self.min_working_days) / (self.max_working_days - self.min_working_days)
        quality += days_ratio * 0.1
        
        # Analyze shift types
        shift_types = defaultdict(int)
        for shift_idx in tour:
            shift = shift_shells[shift_idx]
            shift_types[shift['type']] += 1
        
        # Prefer tours with consistent shift types (less variety)
        shift_type_variety = len(shift_types)
        if shift_type_variety == 1:
            quality += 0.1
        elif shift_type_variety == 2:
            quality += 0.05
            
        # Limit to 0-1 range
        return max(0.0, min(1.0, quality))
    
    def _add_fallback_tours(self, tours, shift_shells, existing_tour_metrics, max_tours):
        """Add fallback tours with improved strategy to ensure diversity"""
        print("Adding fallback tours to ensure diversity...")
        
        # Sort shift shells to prioritize different days
        shift_candidates = sorted(enumerate(shift_shells), 
                               key=lambda x: (x[1]['day'], x[1]['start_time']))
        
        # Extract patterns from existing tours
        existing_patterns = defaultdict(int)
        for tour in tours:
            days = tuple(sorted(shift_shells[idx]['day'] for idx in tour))
            existing_patterns[days] += 1
        
        # Try different patterns of working days
        for working_days in range(self.min_working_days, self.max_working_days + 1):
            # Focus more attempts on underrepresented patterns
            attempts = 10
            if working_days == self.min_working_days or working_days == self.max_working_days:
                attempts = 15
                
            # Calculate combinations that are underrepresented
            all_day_combos = list(itertools.combinations(range(1, self.num_days + 1), working_days))
            # Sort by representation in existing tours
            all_day_combos.sort(key=lambda days: existing_patterns.get(days, 0))
            
            # Focus on least represented combinations
            focus_combos = all_day_combos[:min(5, len(all_day_combos))]
            
            for days_combo in focus_combos:
                for attempt in range(attempts):
                    # Create a fallback tour
                    tour = []
                    total_working_length = 0
                    days_used = set()
                    
                    # Randomly select shifts
                    for day in days_combo:
                        # Find shifts for this day
                        day_shifts = [(idx, shift) for idx, shift in shift_candidates 
                                    if shift['day'] == day]
                        
                        if not day_shifts:
                            continue
                        
                        # Try to find a shift that keeps the working length in range
                        remaining_length = self.max_tour_length - total_working_length
                        min_remaining = max(0, self.min_tour_length - total_working_length)
                        
                        # Filter shifts that would fit
                        valid_shifts = [(idx, shift) for idx, shift in day_shifts 
                                      if shift['working_length'] <= remaining_length]
                        
                        if valid_shifts:
                            # Prefer shifts that help meet minimum requirements
                            preferred_shifts = [(idx, shift) for idx, shift in valid_shifts 
                                              if shift['working_length'] >= min_remaining]
                            
                            if preferred_shifts and min_remaining > 0:
                                shift_idx, shift = random.choice(preferred_shifts)
                            else:
                                shift_idx, shift = random.choice(valid_shifts)
                                
                            # Verify rest time constraints
                            valid_addition = True
                            for prev_idx in tour:
                                if not self._check_rest_time(shift_shells[prev_idx], shift):
                                    valid_addition = False
                                    break
                            
                            if valid_addition:
                                tour.append(shift_idx)
                                total_working_length += shift['working_length']
                                days_used.add(day)
                    
                    # Check if tour meets requirements
                    if (len(days_used) >= self.min_working_days and
                        self.min_tour_length <= total_working_length <= self.max_tour_length):
                        
                        # Only add if it's different from existing tours
                        pattern = self._get_tour_pattern(tour, shift_shells)
                        tour_patterns = {self._get_tour_pattern(t, shift_shells) for t in tours}
                        
                        if pattern not in tour_patterns:
                            tours.append(tour)
                            
                            # Also add metrics for this tour
                            metrics = {
                                'days': list(days_used),
                                'quality_score': 0.5,  # Medium quality for fallback tours
                                'shift_types': defaultdict(int)
                            }
                            
                            for idx in tour:
                                metrics['shift_types'][shift_shells[idx]['type']] += 1
                                
                            existing_tour_metrics.append(metrics)
                            
                    # Stop if we've reached max tours
                    if len(tours) >= max_tours:
                        return
    
    def _analyze_tour_diversity(self, tours, shift_shells):
        """Analyze the diversity of generated tours with comprehensive metrics"""
        if not tours:
            print("No tours to analyze")
            return
            
        # Analyze working days
        working_days = [len(set(shift_shells[idx]['day'] for idx in tour)) for tour in tours]
        avg_working_days = sum(working_days) / len(working_days)
        
        # Analyze working lengths
        working_lengths = [sum(shift_shells[idx]['working_length'] for idx in tour) / 4 for tour in tours]
        avg_working_length = sum(working_lengths) / len(working_lengths)
        
        # Analyze shift types 
        shift_types = defaultdict(int)
        total_shifts = 0
        
        for tour in tours:
            for idx in tour:
                shift_type = shift_shells[idx]['type']
                shift_types[shift_type] += 1
                total_shifts += 1
        
        shift_distribution = {length: f"{(count/total_shifts)*100:.1f}%" 
                            for length, count in shift_types.items()}
        
        # Analyze day distribution
        days_distribution = defaultdict(int)
        for tour in tours:
            for idx in tour:
                days_distribution[shift_shells[idx]['day']] += 1
        
        days_distribution = {day: f"{(count/total_shifts)*100:.1f}%" 
                           for day, count in sorted(days_distribution.items())}
        
        # Analyze start time distribution
        start_time_groups = defaultdict(int)
        for tour in tours:
            for idx in tour:
                # Group into 4-hour blocks
                hour = shift_shells[idx]['start_time'] // 16  # 16 periods = 4 hours
                time_group = {
                    0: "Night (12am-4am)",
                    1: "Early Morning (4am-8am)",
                    2: "Morning (8am-12pm)",
                    3: "Afternoon (12pm-4pm)",
                    4: "Evening (4pm-8pm)",
                    5: "Night (8pm-12am)"
                }.get(hour, "Other")
                
                start_time_groups[time_group] += 1
        
        start_time_distribution = {group: f"{(count/total_shifts)*100:.1f}%" 
                                 for group, count in start_time_groups.items()}
        
        # Print comprehensive diversity analysis
        print(f"\nTour diversity analysis:")
        print(f"  - Number of unique tours: {len(tours)}")
        print(f"  - Total shifts: {total_shifts}")
        print(f"  - Average working days per tour: {avg_working_days:.2f}")
        print(f"  - Average working length per tour: {avg_working_length:.2f} hours")
        print(f"  - Shift type distribution: {shift_distribution}")
        print(f"  - Days distribution: {days_distribution}")
        print(f"  - Start time distribution: {start_time_distribution}")
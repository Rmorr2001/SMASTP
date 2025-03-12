import random
import itertools
from collections import defaultdict

class TourGenerator:
    """Enhanced tour generator with improved diversity and constraint handling"""
    
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
        
    def generate_tours(self, shift_shells, max_tours=1000, diversity_factor=0.3):
        """
        Generate feasible tours by combining shift shells with improved diversity
        
        Args:
            shift_shells: List of shift shells
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
        
        # Generate diverse sets of working days
        working_day_sets = self._generate_diverse_working_day_sets(diversity_factor)
        
        # Track created tour patterns to ensure diversity
        tour_patterns = set()
        
        # For each set of working days
        for working_days in working_day_sets:
            # Generate day combinations
            day_combinations = list(itertools.combinations(range(1, self.num_days + 1), working_days))
            
            # Make sure we have day combinations
            if not day_combinations:
                print(f"WARNING: No day combinations for {working_days} working days")
                continue
            
            # Sample some combinations to keep the problem tractable
            sampled_combinations = self._sample_combinations(day_combinations, min(100, len(day_combinations)))
            
            for day_combo in sampled_combinations:
                # For each combination of working days, select shift options
                shift_options = [shift_shells_by_day[d] for d in day_combo]
                
                # Skip if any day has no shifts
                if any(not options for options in shift_options):
                    continue
                
                # Try multiple shift patterns for this day combination
                for attempt in range(15):  # Increased attempts for better diversity
                    # Start with an empty tour
                    tour = []
                    total_working_length = 0
                    days_covered = set()
                    
                    # Use weighted sampling for shift selection to encourage diversity
                    shift_weights = self._generate_shift_weights(shift_options, attempt)
                    
                    # For each working day, select a shift
                    for d_idx, d in enumerate(day_combo):
                        available_shifts = shift_options[d_idx]
                        if not available_shifts:
                            continue
                            
                        # Use weighted sampling to select a shift
                        weights = [shift_weights.get((d, shift_idx), 1.0) for shift_idx in available_shifts]
                        shift_idx = self._weighted_choice(available_shifts, weights)
                        shift = shift_shells[shift_idx]
                        
                        # Check if adding this shift respects rest time constraints with existing shifts
                        valid = self._is_valid_shift_addition(shift, tour, shift_shells)
                        
                        if valid and d not in days_covered:
                            tour.append(shift_idx)
                            total_working_length += shift['working_length']
                            days_covered.add(d)
                    
                    # Check if tour meets all requirements
                    if (len(days_covered) >= self.min_working_days and
                        len(days_covered) <= self.max_working_days and
                        self.min_tour_length <= total_working_length <= self.max_tour_length):
                        
                        # Create a tour pattern string for diversity checking
                        pattern = self._get_tour_pattern(tour, shift_shells)
                        if pattern not in tour_patterns:
                            tour_patterns.add(pattern)
                            tours.append(tour)
                    
                    # Limit the number of tours
                    if len(tours) >= max_tours:
                        break
                
                if len(tours) >= max_tours:
                    break
        
        # If we couldn't generate enough tours, add fallback tours
        if len(tours) < min(max_tours, 100):
            self._add_fallback_tours(tours, shift_shells, max_tours)
        
        print(f"Tour generation complete: {len(tours)} valid tours created")
        
        # Analyze tour diversity
        self._analyze_tour_diversity(tours, shift_shells)
        
        return tours
    
    def _generate_diverse_working_day_sets(self, diversity_factor):
        """Generate diverse sets of working days"""
        working_day_sets = []
        
        for working_days in range(self.min_working_days, self.max_working_days + 1):
            for attempt in range(1):
                # Always include the min and max working days
                working_day_sets.append(self.min_working_days)
                if self.min_working_days != self.max_working_days:
                    working_day_sets.append(self.max_working_days)
                
                # Add intermediate values based on diversity factor
                step = max(1, int(1 / diversity_factor))
                for days in range(self.min_working_days + step, self.max_working_days, step):
                    working_day_sets.append(days)
            
        return working_day_sets
    
    def _sample_combinations(self, combinations, sample_size):
        """Sample combinations with a focus on diversity"""
        if len(combinations) <= sample_size:
            return combinations
            
        # Ensure we get a diverse sample by selecting combinations with different profiles
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
    
    def _combination_distance(self, combo1, combo2):
        """Calculate distance between two combinations"""
        # Use symmetric difference as a distance measure
        set1 = set(combo1)
        set2 = set(combo2)
        return len(set1.symmetric_difference(set2))
    
    def _generate_shift_weights(self, shift_options, attempt):
        """Generate weights for shift selection to encourage diversity"""
        weights = {}
        
        # Base weights on shift properties and attempt number to ensure diversity
        for d_idx, options in enumerate(shift_options):
            day = d_idx + 1
            
            # Generate different weight profiles based on attempt number
            weight_profile = attempt % 5
            
            for shift_idx in options:
                if weight_profile == 0:
                    # Prefer morning shifts
                    weights[(day, shift_idx)] = 2.0 if shift_idx % 3 == 0 else 1.0
                elif weight_profile == 1:
                    # Prefer afternoon shifts
                    weights[(day, shift_idx)] = 2.0 if shift_idx % 3 == 1 else 1.0
                elif weight_profile == 2:
                    # Prefer evening shifts
                    weights[(day, shift_idx)] = 2.0 if shift_idx % 3 == 2 else 1.0
                elif weight_profile == 3:
                    # Prefer 8-hour shifts
                    weights[(day, shift_idx)] = 2.0 if shift_idx % 3 == 0 else 1.0
                else:
                    # Prefer shorter shifts
                    weights[(day, shift_idx)] = 2.0 if shift_idx % 3 != 0 else 1.0
        
        return weights
    
    def _weighted_choice(self, options, weights):
        """Select an option using weighted random choice"""
        total = sum(weights)
        if total == 0:
            return random.choice(options)
            
        r = random.uniform(0, total)
        cumulative_weight = 0
        
        for option, weight in zip(options, weights):
            cumulative_weight += weight
            if r <= cumulative_weight:
                return option
                
        return options[-1]  # Fallback
    
    def _is_valid_shift_addition(self, new_shift, current_tour, shift_shells):
        """Check if adding a new shift results in a valid tour"""
        for prev_shift_idx in current_tour:
            prev_shift = shift_shells[prev_shift_idx]
            
            # Check rest time between shifts
            if not self._check_rest_time(prev_shift, new_shift):
                return False
                
        return True
    
    def _check_rest_time(self, prev_shift, curr_shift):
        """Check if there's sufficient rest time between shifts"""
        # If shifts are on the same day, they can't be part of the same tour
        if prev_shift['day'] == curr_shift['day']:
            return False
        
        # Calculate actual periods between shifts
        if prev_shift['day'] < curr_shift['day']:
            # Forward direction
            prev_end_time = prev_shift['start_time'] + prev_shift['length']
            curr_start_time = curr_shift['start_time']
            
            # Calculate rest time in periods
            rest_time = (curr_shift['day'] - prev_shift['day'] - 1) * 96  # Full days between
            rest_time += curr_start_time + (96 - prev_end_time)
        else:
            # Backward direction (for completeness)
            curr_end_time = curr_shift['start_time'] + curr_shift['length']
            prev_start_time = prev_shift['start_time']
            
            # Calculate rest time in periods
            rest_time = (prev_shift['day'] - curr_shift['day'] - 1) * 96  # Full days between
            rest_time += prev_start_time + (96 - curr_end_time)
        
        return rest_time >= self.min_rest_time
    
    def _get_tour_pattern(self, tour, shift_shells):
        """Create a pattern string representing the tour structure"""
        day_to_shift = {}
        for shift_idx in tour:
            shift = shift_shells[shift_idx]
            day_to_shift[shift['day']] = f"{shift['start_time']}:{shift['length']}"
            
        pattern = []
        for day in range(1, self.num_days + 1):
            if day in day_to_shift:
                pattern.append(day_to_shift[day])
            else:
                pattern.append('X')  # Day off
                
        return '-'.join(pattern)
    
    def _add_fallback_tours(self, tours, shift_shells, max_tours):
        """Add fallback tours to ensure we have enough diversity"""
        print("Adding fallback tours to ensure diversity...")
        
        # Sort shift shells to prioritize different days
        shift_candidates = sorted(enumerate(shift_shells), 
                                key=lambda x: (x[1]['day'], x[1]['start_time']))
        
        # Try different patterns of working days
        for working_days in range(self.min_working_days, self.max_working_days + 1):
            for attempt in range(5):
                # Create a fallback tour
                tour = []
                total_working_length = 0
                days_used = set()
                
                # Randomly select days to work
                work_days = sorted(random.sample(range(1, self.num_days + 1), working_days))
                
                for day in work_days:
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
                            
                        tour.append(shift_idx)
                        total_working_length += shift['working_length']
                        days_used.add(day)
                
                # Check if tour meets requirements
                if (len(days_used) >= self.min_working_days and
                    self.min_tour_length <= total_working_length <= self.max_tour_length):
                    
                    # Only add if it's different from existing tours
                    if tour not in tours:
                        tours.append(tour)
                        
                # Stop if we've reached max tours
                if len(tours) >= max_tours:
                    return
    
    def _analyze_tour_diversity(self, tours, shift_shells):
        """Analyze the diversity of generated tours"""
        if not tours:
            print("No tours to analyze")
            return
            
        # Analyze working days
        working_days = [sum(1 for idx in tour if shift_shells[idx]['day']) for tour in tours]
        avg_working_days = sum(working_days) / len(working_days)
        
        # Analyze working lengths
        working_lengths = [sum(shift_shells[idx]['working_length'] for idx in tour) for tour in tours]
        avg_working_length = sum(working_lengths) / len(working_lengths)
        
        # Analyze shift types (by length)
        shift_types = defaultdict(int)
        for tour in tours:
            for idx in tour:
                length = shift_shells[idx]['length']
                shift_types[length] += 1
                
        total_shifts = sum(shift_types.values())
        shift_distribution = {length: count/total_shifts for length, count in shift_types.items()}
        
        print(f"Tour diversity analysis:")
        print(f"  - Average working days per tour: {avg_working_days:.2f}")
        print(f"  - Average working length per tour: {avg_working_length:.2f}")
        print(f"  - Shift length distribution: {shift_distribution}") 
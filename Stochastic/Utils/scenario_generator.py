import numpy as np

class ScenarioGenerator:
    """
    Improved scenario generator for stochastic demand modeling
    """
    def __init__(self, base_demands, seasonality_factors=None, time_of_day_factors=None):
        """
        Initialize scenario generator
        
        Args:
            base_demands: Base demand values for each (day, period, activity)
            seasonality_factors: Optional dict of factors for different days
            time_of_day_factors: Optional dict of factors for different times of day
        """
        self.base_demands = base_demands
        self.seasonality_factors = seasonality_factors or {}
        self.time_of_day_factors = time_of_day_factors or {}
        
    def generate_scenarios(self, num_scenarios, distribution='poisson', correlation=0.3):
        """
        Generate demand scenarios 
        
        Args:
            num_scenarios: Number of scenarios to generate
            distribution: 'poisson', 'normal', or 'uniform'
            correlation: Correlation between activities (0-1)
            
        Returns:
            List of scenario dictionaries
        """
        print(f"Generating {num_scenarios} scenarios with {distribution} distribution...")
        scenarios = []
        
        # Generate correlated random factors for scenarios
        scenario_factors = self._generate_correlated_factors(num_scenarios, correlation)
        
        for s in range(num_scenarios):
            scenario = {
                'id': s,
                'probability': 1.0 / num_scenarios,
                'demand': {}
            }
            
            # Extract factors for this scenario
            factors = scenario_factors[s]
            
            # Generate demand for each day, period, and activity
            for (d, i, j), base_demand in self.base_demands.items():
                # Apply seasonality and time-of-day factors
                adjusted_demand = base_demand * self._get_seasonality_factor(d)
                adjusted_demand *= self._get_time_of_day_factor(i)
                
                # Apply scenario-specific factor
                adjusted_demand *= factors.get(j, 1.0)
                
                # Generate demand value based on distribution
                if distribution == 'poisson':
                    # Poisson distribution (count data)
                    demand = np.random.poisson(adjusted_demand)
                elif distribution == 'normal':
                    # Normal distribution with coefficient of variation = 0.2
                    cv = 0.2  # Coefficient of variation
                    std_dev = adjusted_demand * cv
                    demand = max(1, int(round(np.random.normal(adjusted_demand, std_dev))))
                else:  # uniform
                    # Uniform distribution ±30% around mean
                    low = max(1, int(adjusted_demand * 0.7))
                    high = max(2, int(adjusted_demand * 1.3) + 1)
                    demand = np.random.randint(low, high)
                
                scenario['demand'][(d, i, j)] = demand
            
            scenarios.append(scenario)
        
        # Analyze scenarios
        self._analyze_scenarios(scenarios)
        
        return scenarios
    
    def _generate_correlated_factors(self, num_scenarios, correlation):
        """Generate correlated random factors for activities across scenarios"""
        # Determine number of activities
        activities = set(j for _, _, j in self.base_demands.keys())
        num_activities = len(activities)
        
        # Create correlation matrix
        cor_matrix = np.ones((num_activities, num_activities)) * correlation
        np.fill_diagonal(cor_matrix, 1.0)
        
        # Ensure positive definiteness
        min_eig = np.min(np.linalg.eigvals(cor_matrix))
        if min_eig < 0:
            cor_matrix += np.eye(num_activities) * (abs(min_eig) + 0.01)
        
        # Generate correlated normal random variables
        mean = np.ones(num_activities)
        cv = 0.2  # Coefficient of variation for factors
        std_dev = mean * cv
        
        # Calculate the covariance matrix from correlation matrix
        cov_matrix = np.zeros((num_activities, num_activities))
        for i in range(num_activities):
            for j in range(num_activities):
                cov_matrix[i, j] = cor_matrix[i, j] * std_dev[i] * std_dev[j]
        
        # Generate multivariate normal samples
        random_samples = np.random.multivariate_normal(mean, cov_matrix, num_scenarios)
        
        # Ensure all factors are positive
        random_samples = np.maximum(random_samples, 0.5)
        
        # Convert to dictionary format
        factors = []
        for s in range(num_scenarios):
            scenario_factors = {j: random_samples[s, j-1] for j in activities}
            factors.append(scenario_factors)
            
        return factors
    
    def _get_seasonality_factor(self, day):
        """Get seasonality factor for a given day"""
        return self.seasonality_factors.get(day, 1.0)
    
    def _get_time_of_day_factor(self, period):
        """Get time-of-day factor for a given period"""
        return self.time_of_day_factors.get(period, 1.0)
    
    def _analyze_scenarios(self, scenarios):
        """Analyze generated scenarios"""
        if not scenarios:
            return
            
        # Calculate statistics for each (day, period, activity)
        stats = {}
        
        for key in scenarios[0]['demand'].keys():
            values = [s['demand'][key] for s in scenarios]
            stats[key] = {
                'mean': np.mean(values),
                'std': np.std(values),
                'min': np.min(values),
                'max': np.max(values),
                'cv': np.std(values) / np.mean(values) if np.mean(values) > 0 else 0
            }
        
        # Print summary statistics
        print(f"Scenario statistics:")
        print(f"  Average coefficient of variation: {np.mean([s['cv'] for s in stats.values()]):.3f}")
        print(f"  Min/max demand ratio: {np.min([s['min'] for s in stats.values()])}/{np.max([s['max'] for s in stats.values()])}") 
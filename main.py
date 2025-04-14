import os
from Stochastic.stochastic_scheduler import StochasticTourSchedulingModel, run_stochastic_model
from Main_Utils.deterministic_model import compare_stochastic_vs_deterministic
from Main_Utils.utils_tourviews import view_tours, view_tour_details


if __name__ == "__main__":
    # Create a results directory
    os.makedirs("results", exist_ok=True)
    
    # Run the stochastic model
 
    #"""
    model, solution = run_stochastic_model(
        seed=42,
        num_employees=10,
        num_scenarios=5,
        output_dir='results/stochastic_model'
    )

    
    # View tours
    view_tours(model, num_tours=10, detailed=True, output_dir='results')
    
    # View details for a specific tour
    view_tour_details(model, tour_id=1)
    """
    
    # Compare stochastic vs. deterministic approaches
    comparison = compare_stochastic_vs_deterministic(
        seed=42,
        num_employees=20,
        num_scenarios=5,
        output_dir='results/comparison'
    )

    """
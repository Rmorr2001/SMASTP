#!/usr/bin/env python3
"""
Tour Viewer - A command-line interface to view tours in the SMASTP model
"""

import os
import sys
import argparse
import pickle
import matplotlib.pyplot as plt
from collections import defaultdict

# Import from main.py
from main import view_tours, view_tour_details, StochasticTourSchedulingModel

def load_model(model_path=None):
    """
    Load a model from a pickle file or create a new one
    
    Args:
        model_path: Path to the model pickle file
        
    Returns:
        StochasticTourSchedulingModel instance
    """
    if model_path and os.path.exists(model_path):
        try:
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            print(f"Model loaded from {model_path}")
            return model
        except Exception as e:
            print(f"Error loading model: {e}")
            return None
    else:
        # Create a new model
        model = StochasticTourSchedulingModel(
            num_days=7,
            num_periods=96,
            num_activities=2,
            num_employees=20
        )
        
        # Generate shift shells
        model.generate_shift_shells()
        
        # Generate tours
        model.generate_tours(max_tours=1000)
        
        print("Created a new model with default parameters")
        return model

def save_model(model, output_path):
    """
    Save the model to a pickle file
    
    Args:
        model: StochasticTourSchedulingModel instance
        output_path: Path to save the model
    """
    try:
        with open(output_path, 'wb') as f:
            pickle.dump(model, f)
        print(f"Model saved to {output_path}")
    except Exception as e:
        print(f"Error saving model: {e}")

def main():
    """Main function for the tour viewer"""
    parser = argparse.ArgumentParser(description='Tour Viewer for SMASTP')
    
    # Add arguments
    parser.add_argument('--model', type=str, help='Path to the model pickle file')
    parser.add_argument('--save', type=str, help='Path to save the model')
    parser.add_argument('--list', action='store_true', help='List all tours')
    parser.add_argument('--view', type=int, help='View details for a specific tour ID')
    parser.add_argument('--num', type=int, default=10, help='Number of tours to display (default: 10)')
    parser.add_argument('--detailed', action='store_true', help='Show detailed information for each tour')
    parser.add_argument('--output', type=str, help='Directory to save tour information as CSV')
    parser.add_argument('--generate', action='store_true', help='Generate new tours')
    parser.add_argument('--max-tours', type=int, default=1000, help='Maximum number of tours to generate (default: 1000)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load or create model
    model = load_model(args.model)
    
    if not model:
        print("Failed to load or create model. Exiting.")
        sys.exit(1)
    
    # Generate new tours if requested
    if args.generate:
        print(f"Generating new tours (max: {args.max_tours})...")
        model.generate_tours(max_tours=args.max_tours)
    
    # List tours
    if args.list:
        view_tours(model, num_tours=args.num, detailed=args.detailed, output_dir=args.output)
    
    # View specific tour
    if args.view:
        view_tour_details(model, tour_id=args.view)
    
    # Save model if requested
    if args.save:
        save_model(model, args.save)
    
    # If no action specified, show help
    if not (args.list or args.view or args.generate):
        parser.print_help()

if __name__ == "__main__":
    main() 
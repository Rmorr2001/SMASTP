import pyomo.environ as pyo
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict

from grammar import ContextFreeGrammar




# Import our decomposed functionality
from model_builder import ModelBuilderMixin
from solver import SolverMixin
from visualization import VisualizationMixin
from reporting import ReportingMixin

class StochasticTourSchedulingModel(ModelBuilderMixin, SolverMixin, VisualizationMixin, ReportingMixin):
    """
    Enhanced stochastic tour scheduling model with improved performance and visualization
    """
    def __init__(self, num_days=7, num_periods=96, num_activities=2, num_employees=20):
        """
        Initialize the model parameters
        
        Args:
            num_days: Number of days in the planning horizon
            num_periods: Number of periods per day
            num_activities: Number of work activities
            num_employees: Number of employees to schedule
        """
        self.num_days = num_days
        self.num_periods = num_periods
        self.num_activities = num_activities
        self.num_employees = num_employees
        
        # Define the grammar for shift generation
        self.grammar = self._define_grammar()
        
        # Initialize model components
        self.shift_shells = []
        self.tours = []
        self.scenarios = []
        self.scenario_probabilities = []
        self.solution = None
        self.processing_times = {}
        
        print(f"Initialized SMATSP model with {num_days} days, {num_periods} periods/day, " +
              f"{num_activities} activities, and {num_employees} employees")
        
    def _define_grammar(self):
        """Define the context-free grammar for shift generation"""
        # Terminal symbols: activities, breaks, lunch, rest
        terminal_symbols = ['a' + str(j) for j in range(1, self.num_activities + 1)] + ['b', 'l', 'r']
        
        # Non-terminal symbols
        non_terminal_symbols = ['S', 'F', 'Q', 'N', 'W'] + ['A' + str(j) for j in range(1, self.num_activities + 1)] + ['B', 'L', 'R']
        
        # Productions based on the paper
        productions = {
            'S': [('R', 'F', 'R'), ('F', 'R'), ('R', 'F'), ('R', 'Q', 'R'), ('Q', 'R'), ('R', 'Q'), 
                 ('R', 'N', 'R'), ('N', 'R'), ('R', 'N')],
            'F': [('N', 'L', 'N')],
            'Q': [('W', 'B', 'W')],
            'N': [('W', 'B', 'W')],
            'R': [('R', 'r'), 'r'],
            'W': [('A1',)],
            'A1': [('A1', 'a1'), 'a1'],
            'B': ['b'],
            'L': ['l', 'l', 'l', 'l']  # 4 consecutive lunch periods
        }
        
        # Add activity productions for additional activities
        if self.num_activities > 1:
            productions['W'].extend([('A'+str(j),) for j in range(2, self.num_activities+1)])
            for j in range(2, self.num_activities+1):
                productions[f'A{j}'] = [(f'A{j}', f'a{j}'), f'a{j}']
        
        # Create and return the grammar
        return ContextFreeGrammar(terminal_symbols, non_terminal_symbols, 'S', productions)
import networkx as nx
import matplotlib.pyplot as plt

class ContextFreeGrammar:
    """
    Enhanced implementation of a context-free grammar for shift generation
    Based on the grammar approach described in Restrepo et al. 2017
    """
    def __init__(self, terminal_symbols, non_terminal_symbols, start_symbol, productions):
        """
        Initialize grammar with terminals, non-terminals, start symbol and productions
        """
        self.terminals = terminal_symbols
        self.non_terminals = non_terminal_symbols
        self.start = start_symbol
        self.productions = productions
        
    def build_dag(self, day_length):
        """Build a comprehensive directed acyclic graph representing valid shifts"""
        dag = nx.DiGraph()
        
        # Add root node
        root = (self.start, 0, day_length)
        dag.add_node(root)
        
        # Generate comprehensive shift patterns based on productions
        shift_lengths = [32, 24, 16]  # 8-hour, 6-hour, 4-hour shifts in 15-min periods
        
        # For each shift length, create nodes representing shifts with break patterns
        for length in shift_lengths:
            # Create shift nodes
            self._expand_node(dag, root, length)
        
        # Add metadata to the DAG
        dag.graph['name'] = 'Shift Generation DAG'
        dag.graph['day_length'] = day_length
        dag.graph['shift_lengths'] = shift_lengths
        
        return dag
    
    def _expand_node(self, dag, parent_node, length):
        """Recursive function to expand nodes in the DAG based on productions"""
        symbol, start, _ = parent_node
        
        # Create a shift node
        shift_node = ('shift', start, length)
        dag.add_edge(parent_node, shift_node)
        
        # Add break patterns based on shift length
        if length == 32:  # 8-hour shift
            self._add_break_pattern_8hour(dag, shift_node)
        elif length == 24:  # 6-hour shift
            self._add_break_pattern_6hour(dag, shift_node)
        elif length == 16:  # 4-hour shift
            self._add_break_pattern_4hour(dag, shift_node)
    
    def _add_break_pattern_8hour(self, dag, shift_node):
        """Add 8-hour shift break pattern: 1-hr lunch, two 15-min breaks"""
        _, start, _ = shift_node
        
        # Morning work (3 hours)
        work_morning = ('work', start, 12)
        dag.add_edge(shift_node, work_morning)
        
        # Morning break (15 min)
        break_morning = ('break', start+12, 1)
        dag.add_edge(work_morning, break_morning)
        
        # Mid-morning work (1.5 hours)
        work_mid = ('work', start+13, 6)
        dag.add_edge(break_morning, work_mid)
        
        # Lunch (1 hour)
        lunch = ('lunch', start+19, 4)
        dag.add_edge(work_mid, lunch)
        
        # Afternoon work (1.5 hours)
        work_afternoon = ('work', start+23, 6)
        dag.add_edge(lunch, work_afternoon)
        
        # Afternoon break (15 min)
        break_afternoon = ('break', start+29, 1)
        dag.add_edge(work_afternoon, break_afternoon)
        
        # Late afternoon work (0.5 hour)
        work_late = ('work', start+30, 2)
        dag.add_edge(break_afternoon, work_late)

    def _add_break_pattern_6hour(self, dag, shift_node):
        """Add 6-hour shift break pattern: one 15-min break"""
        _, start, _ = shift_node
        
        # First work segment (3 hours)
        work_first = ('work', start, 12)
        dag.add_edge(shift_node, work_first)
        
        # Break (15 min)
        break_mid = ('break', start+12, 1)
        dag.add_edge(work_first, break_mid)
        
        # Second work segment (2.75 hours)
        work_second = ('work', start+13, 11)
        dag.add_edge(break_mid, work_second)

    def _add_break_pattern_4hour(self, dag, shift_node):
        """Add 4-hour shift break pattern: one 15-min break"""
        _, start, _ = shift_node
        
        # First work segment (2 hours)
        work_first = ('work', start, 8)
        dag.add_edge(shift_node, work_first)
        
        # Break (15 min)
        break_mid = ('break', start+8, 1)
        dag.add_edge(work_first, break_mid)
        
        # Second work segment (1.75 hours)
        work_second = ('work', start+9, 7)
        dag.add_edge(break_mid, work_second)
    
    def visualize_dag(self, dag, filename=None):
        """Visualize the DAG for debugging and analysis"""
        plt.figure(figsize=(12, 8))
        pos = nx.spring_layout(dag)
        
        # Draw nodes with different colors based on type
        node_colors = []
        for node in dag.nodes:
            if node[0] == self.start:
                node_colors.append('lightblue')
            elif node[0] == 'shift':
                node_colors.append('lightgreen')
            elif node[0] == 'work':
                node_colors.append('salmon')
            elif node[0] in ['break', 'lunch']:
                node_colors.append('yellow')
            else:
                node_colors.append('gray')
        
        nx.draw(dag, pos, with_labels=True, labels={n: f"{n[0]}:{n[1]}-{n[2]}" for n in dag.nodes},
                node_color=node_colors, node_size=2000, font_size=8, font_weight='bold')
        
        if filename:
            plt.savefig(filename)
        plt.show()
# Timing Comparison for SMASTP

This tool allows you to compare the calculation times between stochastic and deterministic solution approaches for the Stochastic Multi-Activity Tour Scheduling Problem (SMASTP).

## Features

- Compare calculation times between stochastic and deterministic approaches
- Analyze the impact of different parameters (number of employees, number of scenarios)
- Visualize the tradeoff between computational cost and solution quality
- Generate comprehensive reports and visualizations

## Usage

### Basic Usage

To run a timing comparison with default parameters:

```bash
python compare_timing.py
```

This will run comparisons with the following default parameters:
- Employee counts: 20, 40, 60
- Scenario counts: 3, 5, 10

### Advanced Options

You can customize the parameters using command-line arguments:

```bash
python compare_timing.py --employees 10,20,30 --scenarios 2,4,6 --output ./custom_timing_comparison
```

- `--employees`: Comma-separated list of employee counts to test
- `--scenarios`: Comma-separated list of scenario counts to test
- `--output`: Directory to save results

## Output

The tool generates the following outputs:

### CSV Reports

- `timing_comparison_results.csv`: Detailed results for all parameter combinations

### Visualizations

1. **Timing Comparison**: Bar chart comparing setup, solve, and total times for stochastic and deterministic approaches
2. **Speedup vs. Scenarios**: Line chart showing how the speedup factor changes with the number of scenarios
3. **Solve Time vs. Scenarios**: Bar chart comparing solve times for different numbers of scenarios
4. **VSS vs. Scenarios**: Line chart showing how the Value of Stochastic Solution (VSS) changes with the number of scenarios
5. **Efficiency vs. Value Tradeoff**: Scatter plot showing the tradeoff between computational cost and solution quality

## Understanding the Results

### Key Metrics

- **Speedup Factor**: Ratio of stochastic solution time to deterministic solution time (higher values indicate greater computational cost for the stochastic approach)
- **VSS Percentage**: Value of Stochastic Solution as a percentage (higher values indicate greater benefit from using the stochastic approach)

### Interpreting the Tradeoff

The efficiency vs. value tradeoff visualization helps you understand:

1. **Computational Cost**: How much more time the stochastic approach requires compared to the deterministic approach
2. **Solution Quality**: How much better the stochastic solution is compared to the deterministic solution
3. **Parameter Impact**: How different parameters (number of employees, number of scenarios) affect this tradeoff

## Integration with SMASTP

This tool integrates with the main SMASTP model and can be used to:

1. Determine the appropriate number of scenarios for your problem
2. Understand the computational requirements for different problem sizes
3. Make informed decisions about which solution approach to use based on your specific requirements 
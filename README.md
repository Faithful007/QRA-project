# QRA Project - Quantitative Risk Assessment System

**FDS-EVAC-QRA-RESULTS**: A comprehensive system for evacuation simulation, statistical analysis, and quantitative risk assessment.

## Overview

This QRA (Quantitative Risk Assessment) system provides tools for:
- **Evacuation Simulation**: Agent-based modeling of building evacuations
- **Statistical Analysis**: Comprehensive statistical calculations including ASET/RSET analysis
- **Visualization**: Graphs and plots for evacuation time distributions, risk curves, and safety margins
- **Report Generation**: Automated HTML and text reports with analysis results

## Features

### 1. Evacuation Simulation
- Agent-based evacuation modeling
- Configurable building layouts with multiple exits
- Realistic agent behaviors (variable walking speeds, pre-movement times)
- Multiple simulation runs for statistical validity

### 2. Statistical Analysis
- Descriptive statistics (mean, median, percentiles, etc.)
- Distribution fitting (Normal, Lognormal, Weibull)
- Confidence intervals
- ASET/RSET comparison
- Risk probability calculations

### 3. Visualizations
- Evacuation time histograms with KDE
- Cumulative distribution plots
- Risk curves (probability of failure vs ASET)
- Safety margin distributions
- Percentile comparison charts
- Summary dashboards

### 4. Report Generation
- Detailed HTML reports with embedded visualizations
- Text reports for easy parsing
- Summary statistics and risk metrics

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Faithful007/QRA-project.git
cd QRA-project
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run a simple analysis with default parameters:
```bash
python main.py
```

### Advanced Usage

Customize the analysis parameters:
```bash
python main.py \
  --num-agents 200 \
  --building-width 60.0 \
  --building-height 40.0 \
  --num-exits 3 \
  --num-simulations 20 \
  --aset 180.0 \
  --output-dir my_results
```

### Parameters

- `--num-agents`: Number of occupants (default: 100)
- `--building-width`: Building width in meters (default: 50.0)
- `--building-height`: Building height in meters (default: 30.0)
- `--num-exits`: Number of exits (default: 2)
- `--num-simulations`: Number of simulations to run (default: 10)
- `--aset`: Available Safe Egress Time in seconds (optional)
- `--mean-speed`: Mean walking speed in m/s (default: 1.2)
- `--std-speed`: Standard deviation of walking speed (default: 0.3)
- `--mean-pre-movement`: Mean pre-movement time in seconds (default: 30.0)
- `--std-pre-movement`: Standard deviation of pre-movement time (default: 10.0)
- `--output-dir`: Output directory for results (default: outputs)

## Project Structure

```
QRA-project/
├── main.py                          # Main application entry point
├── requirements.txt                 # Python dependencies
├── README.md                       # This file
├── src/
│   └── qra_system/
│       ├── __init__.py
│       ├── evacuation_simulation.py  # Evacuation simulation module
│       ├── statistical_analysis.py   # Statistical analysis module
│       ├── visualization.py          # Visualization module
│       └── report_generator.py       # Report generation module
└── outputs/                         # Generated outputs (created at runtime)
    ├── plots/                       # Visualization plots
    └── reports/                     # Generated reports
```

## Example Output

When you run the system, it generates:

1. **Visualizations** (in `outputs/plots/`):
   - `evacuation_time_histogram.png`
   - `cumulative_distribution.png`
   - `risk_curve.png`
   - `safety_margin_distribution.png`
   - `percentile_comparison.png`
   - `summary_dashboard.png`

2. **Reports** (in `outputs/reports/`):
   - `qra_report_YYYYMMDD_HHMMSS.txt` - Text report
   - `qra_report_YYYYMMDD_HHMMSS.html` - HTML report with embedded visualizations

## Python API Usage

You can also use the system programmatically:

```python
from main import QRASystem

# Create QRA system instance
qra = QRASystem(output_dir="my_outputs")

# Run analysis
results = qra.run_analysis(
    num_agents=150,
    building_width=60.0,
    building_height=40.0,
    num_exits=2,
    num_simulations=15,
    aset=200.0
)

# Access results
print(f"Mean evacuation time: {results['descriptive_statistics']['mean']:.2f}s")
print(f"Risk probability: {results['risk_analysis']['risk_probability']:.2%}")
```

## Key Concepts

### ASET vs RSET
- **ASET** (Available Safe Egress Time): Time until conditions become untenable
- **RSET** (Required Safe Egress Time): Time needed for all occupants to evacuate
- **Safety Margin**: ASET - RSET (positive values indicate safe evacuation)

### Risk Metrics
- **Probability of Success**: Percentage of simulations where all occupants evacuate before ASET
- **Risk (Probability of Failure)**: 1 - Probability of Success
- **Individual Risk**: Probability that any given individual fails to evacuate in time

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is provided as-is for research and educational purposes.

## References

This system is designed for fire safety engineering and quantitative risk assessment based on evacuation simulation principles. It complements tools like FDS (Fire Dynamics Simulator) and its EVAC module.

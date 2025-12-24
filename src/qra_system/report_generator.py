"""
Report Generator Module
Generates HTML and text reports for QRA analysis
"""

import os
from datetime import datetime
from typing import Dict, Optional, List
from jinja2 import Template
import numpy as np


class ReportGenerator:
    """
    Generates comprehensive QRA reports
    """
    
    def __init__(self, output_dir: str = "reports"):
        """
        Initialize report generator
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_text_report(self, analysis_results: Dict, 
                           simulation_params: Dict,
                           save_path: Optional[str] = None) -> str:
        """
        Generate a text report
        
        Args:
            analysis_results: Dictionary with analysis results
            simulation_params: Dictionary with simulation parameters
            save_path: Path to save report (optional)
            
        Returns:
            Path to saved report
        """
        if save_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(self.output_dir, f'qra_report_{timestamp}.txt')
        
        with open(save_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("QUANTITATIVE RISK ASSESSMENT (QRA) REPORT\n")
            f.write("Evacuation Simulation Analysis\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Simulation Parameters
            f.write("-" * 80 + "\n")
            f.write("SIMULATION PARAMETERS\n")
            f.write("-" * 80 + "\n")
            for key, value in simulation_params.items():
                f.write(f"{key}: {value}\n")
            f.write("\n")
            
            # Descriptive Statistics
            if 'descriptive_statistics' in analysis_results:
                stats = analysis_results['descriptive_statistics']
                f.write("-" * 80 + "\n")
                f.write("DESCRIPTIVE STATISTICS\n")
                f.write("-" * 80 + "\n")
                f.write(f"Mean Evacuation Time:      {stats['mean']:.2f} seconds\n")
                f.write(f"Median Evacuation Time:    {stats['median']:.2f} seconds\n")
                f.write(f"Standard Deviation:        {stats['std']:.2f} seconds\n")
                f.write(f"Minimum Time:              {stats['min']:.2f} seconds\n")
                f.write(f"Maximum Time:              {stats['max']:.2f} seconds\n")
                f.write(f"25th Percentile:           {stats['q25']:.2f} seconds\n")
                f.write(f"75th Percentile:           {stats['q75']:.2f} seconds\n")
                f.write(f"95th Percentile:           {stats['q95']:.2f} seconds\n")
                f.write(f"99th Percentile:           {stats['q99']:.2f} seconds\n")
                f.write(f"Interquartile Range:       {stats['iqr']:.2f} seconds\n")
                f.write("\n")
            
            # Percentiles
            if 'percentiles' in analysis_results:
                f.write("-" * 80 + "\n")
                f.write("PERCENTILE ANALYSIS\n")
                f.write("-" * 80 + "\n")
                for percentile, value in sorted(analysis_results['percentiles'].items()):
                    f.write(f"{percentile:>5}th Percentile: {value:>8.2f} seconds\n")
                f.write("\n")
            
            # Risk Analysis
            if 'risk_analysis' in analysis_results:
                risk = analysis_results['risk_analysis']
                f.write("-" * 80 + "\n")
                f.write("RISK ANALYSIS (ASET/RSET)\n")
                f.write("-" * 80 + "\n")
                f.write(f"ASET (Available Safe Egress Time): {risk['aset']:.2f} seconds\n")
                f.write(f"Mean RSET (Required Safe Egress Time): {risk['mean_rset']:.2f} seconds\n")
                f.write(f"Maximum RSET: {risk['max_rset']:.2f} seconds\n")
                f.write(f"Mean Safety Margin (ASET - RSET): {risk['mean_safety_margin']:.2f} seconds\n")
                f.write(f"Minimum Safety Margin: {risk['min_safety_margin']:.2f} seconds\n")
                f.write(f"Probability of Successful Evacuation: {risk['probability_success']:.2%}\n")
                f.write(f"Risk (Probability of Failure): {risk['risk_probability']:.2%}\n")
                f.write("\n")
            
            # Distribution Fitting
            if 'distributions' in analysis_results:
                f.write("-" * 80 + "\n")
                f.write("DISTRIBUTION FITTING\n")
                f.write("-" * 80 + "\n")
                for dist_name, dist_info in analysis_results['distributions'].items():
                    if 'error' not in dist_info:
                        f.write(f"\n{dist_name.upper()} Distribution:\n")
                        f.write(f"  KS Statistic: {dist_info['ks_statistic']:.4f}\n")
                        f.write(f"  P-value: {dist_info['p_value']:.4f}\n")
                f.write("\n")
            
            f.write("=" * 80 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 80 + "\n")
        
        return save_path
    
    def generate_html_report(self, analysis_results: Dict, 
                           simulation_params: Dict,
                           plot_paths: Dict[str, str] = None,
                           save_path: Optional[str] = None) -> str:
        """
        Generate an HTML report
        
        Args:
            analysis_results: Dictionary with analysis results
            simulation_params: Dictionary with simulation parameters
            plot_paths: Dictionary mapping plot names to file paths
            save_path: Path to save report (optional)
            
        Returns:
            Path to saved report
        """
        if save_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(self.output_dir, f'qra_report_{timestamp}.html')
        
        # HTML template
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>QRA Report - Evacuation Analysis</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background-color: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 5px;
            margin-bottom: 30px;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
        }
        .header p {
            margin: 10px 0 0 0;
            font-size: 1.1em;
        }
        .section {
            background-color: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-top: 0;
        }
        .section h3 {
            color: #34495e;
            margin-top: 20px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .metric {
            display: inline-block;
            background-color: #ecf0f1;
            padding: 15px;
            margin: 10px;
            border-radius: 5px;
            min-width: 200px;
        }
        .metric-label {
            font-size: 0.9em;
            color: #7f8c8d;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
        }
        .plot {
            text-align: center;
            margin: 20px 0;
        }
        .plot img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        .success {
            color: #27ae60;
            font-weight: bold;
        }
        .warning {
            color: #f39c12;
            font-weight: bold;
        }
        .danger {
            color: #e74c3c;
            font-weight: bold;
        }
        .footer {
            text-align: center;
            color: #7f8c8d;
            margin-top: 30px;
            padding: 20px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Quantitative Risk Assessment Report</h1>
        <p>Evacuation Simulation Analysis</p>
        <p>Generated: {{ generation_time }}</p>
    </div>
    
    <div class="section">
        <h2>Simulation Parameters</h2>
        <table>
            {% for key, value in simulation_params.items() %}
            <tr>
                <td><strong>{{ key }}</strong></td>
                <td>{{ value }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    
    {% if descriptive_stats %}
    <div class="section">
        <h2>Key Metrics</h2>
        <div style="text-align: center;">
            <div class="metric">
                <div class="metric-label">Mean Evacuation Time</div>
                <div class="metric-value">{{ "%.2f"|format(descriptive_stats.mean) }}s</div>
            </div>
            <div class="metric">
                <div class="metric-label">95th Percentile</div>
                <div class="metric-value">{{ "%.2f"|format(descriptive_stats.q95) }}s</div>
            </div>
            <div class="metric">
                <div class="metric-label">Maximum Time</div>
                <div class="metric-value">{{ "%.2f"|format(descriptive_stats.max) }}s</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Descriptive Statistics</h2>
        <table>
            <tr>
                <th>Statistic</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Mean</td>
                <td>{{ "%.2f"|format(descriptive_stats.mean) }} seconds</td>
            </tr>
            <tr>
                <td>Median</td>
                <td>{{ "%.2f"|format(descriptive_stats.median) }} seconds</td>
            </tr>
            <tr>
                <td>Standard Deviation</td>
                <td>{{ "%.2f"|format(descriptive_stats.std) }} seconds</td>
            </tr>
            <tr>
                <td>Minimum</td>
                <td>{{ "%.2f"|format(descriptive_stats.min) }} seconds</td>
            </tr>
            <tr>
                <td>Maximum</td>
                <td>{{ "%.2f"|format(descriptive_stats.max) }} seconds</td>
            </tr>
            <tr>
                <td>25th Percentile</td>
                <td>{{ "%.2f"|format(descriptive_stats.q25) }} seconds</td>
            </tr>
            <tr>
                <td>75th Percentile</td>
                <td>{{ "%.2f"|format(descriptive_stats.q75) }} seconds</td>
            </tr>
            <tr>
                <td>95th Percentile</td>
                <td>{{ "%.2f"|format(descriptive_stats.q95) }} seconds</td>
            </tr>
            <tr>
                <td>99th Percentile</td>
                <td>{{ "%.2f"|format(descriptive_stats.q99) }} seconds</td>
            </tr>
        </table>
    </div>
    {% endif %}
    
    {% if risk_analysis %}
    <div class="section">
        <h2>Risk Analysis (ASET/RSET)</h2>
        <div style="text-align: center;">
            <div class="metric">
                <div class="metric-label">ASET</div>
                <div class="metric-value">{{ "%.2f"|format(risk_analysis.aset) }}s</div>
            </div>
            <div class="metric">
                <div class="metric-label">Success Probability</div>
                <div class="metric-value {{ 'success' if risk_analysis.probability_success > 0.95 else 'warning' if risk_analysis.probability_success > 0.9 else 'danger' }}">
                    {{ "%.1f"|format(risk_analysis.probability_success * 100) }}%
                </div>
            </div>
            <div class="metric">
                <div class="metric-label">Risk (Failure Probability)</div>
                <div class="metric-value {{ 'danger' if risk_analysis.risk_probability > 0.1 else 'warning' if risk_analysis.risk_probability > 0.05 else 'success' }}">
                    {{ "%.2f"|format(risk_analysis.risk_probability * 100) }}%
                </div>
            </div>
        </div>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>ASET (Available Safe Egress Time)</td>
                <td>{{ "%.2f"|format(risk_analysis.aset) }} seconds</td>
            </tr>
            <tr>
                <td>Mean RSET (Required Safe Egress Time)</td>
                <td>{{ "%.2f"|format(risk_analysis.mean_rset) }} seconds</td>
            </tr>
            <tr>
                <td>Maximum RSET</td>
                <td>{{ "%.2f"|format(risk_analysis.max_rset) }} seconds</td>
            </tr>
            <tr>
                <td>Mean Safety Margin</td>
                <td>{{ "%.2f"|format(risk_analysis.mean_safety_margin) }} seconds</td>
            </tr>
            <tr>
                <td>Minimum Safety Margin</td>
                <td>{{ "%.2f"|format(risk_analysis.min_safety_margin) }} seconds</td>
            </tr>
        </table>
    </div>
    {% endif %}
    
    {% if plot_paths %}
    <div class="section">
        <h2>Visualizations</h2>
        {% for plot_name, plot_path in plot_paths.items() %}
        <div class="plot">
            <h3>{{ plot_name }}</h3>
            <img src="{{ plot_path }}" alt="{{ plot_name }}">
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    <div class="footer">
        <p>Generated by QRA System - Evacuation Simulation and Risk Assessment</p>
        <p>&copy; {{ year }} - All rights reserved</p>
    </div>
</body>
</html>
        """
        
        # Prepare template data
        template = Template(html_template)
        
        descriptive_stats = analysis_results.get('descriptive_statistics')
        risk_analysis = analysis_results.get('risk_analysis')
        
        html_content = template.render(
            generation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            simulation_params=simulation_params,
            descriptive_stats=descriptive_stats,
            risk_analysis=risk_analysis,
            plot_paths=plot_paths or {},
            year=datetime.now().year
        )
        
        with open(save_path, 'w') as f:
            f.write(html_content)
        
        return save_path
    
    def generate_summary(self, analysis_results: Dict) -> str:
        """
        Generate a brief text summary
        
        Args:
            analysis_results: Dictionary with analysis results
            
        Returns:
            Summary text
        """
        summary = []
        summary.append("QRA ANALYSIS SUMMARY")
        summary.append("=" * 50)
        
        if 'descriptive_statistics' in analysis_results:
            stats = analysis_results['descriptive_statistics']
            summary.append(f"\nMean Evacuation Time: {stats['mean']:.2f}s")
            summary.append(f"95th Percentile: {stats['q95']:.2f}s")
            summary.append(f"Maximum Time: {stats['max']:.2f}s")
        
        if 'risk_analysis' in analysis_results:
            risk = analysis_results['risk_analysis']
            summary.append(f"\nASET: {risk['aset']:.2f}s")
            summary.append(f"Success Rate: {risk['probability_success']:.1%}")
            summary.append(f"Risk: {risk['risk_probability']:.2%}")
        
        summary.append("\n" + "=" * 50)
        
        return "\n".join(summary)

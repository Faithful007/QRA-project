"""
Main QRA System Application
Orchestrates evacuation simulation, analysis, visualization, and reporting
"""

import sys
import os
import argparse
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from qra_system.evacuation_simulation import (
    EvacuationSimulation, 
    create_simple_building
)
from qra_system.statistical_analysis import (
    StatisticalAnalysis,
    RiskAnalysis,
    analyze_multiple_simulations
)
from qra_system.visualization import QRAVisualizer
from qra_system.report_generator import ReportGenerator


class QRASystem:
    """
    Main QRA System class that orchestrates all components
    """
    
    def __init__(self, output_dir: str = "outputs"):
        """
        Initialize QRA System
        
        Args:
            output_dir: Base output directory
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        self.visualizer = QRAVisualizer(os.path.join(output_dir, "plots"))
        self.report_generator = ReportGenerator(os.path.join(output_dir, "reports"))
    
    def run_analysis(self, 
                    num_agents: int = 100,
                    building_width: float = 50.0,
                    building_height: float = 30.0,
                    num_exits: int = 2,
                    num_simulations: int = 10,
                    aset: Optional[float] = None,
                    mean_speed: float = 1.2,
                    std_speed: float = 0.3,
                    mean_pre_movement: float = 30.0,
                    std_pre_movement: float = 10.0) -> dict:
        """
        Run complete QRA analysis
        
        Args:
            num_agents: Number of occupants
            building_width: Building width in meters
            building_height: Building height in meters
            num_exits: Number of exits
            num_simulations: Number of simulations to run
            aset: Available Safe Egress Time (seconds)
            mean_speed: Mean walking speed (m/s)
            std_speed: Standard deviation of walking speed
            mean_pre_movement: Mean pre-movement time (seconds)
            std_pre_movement: Standard deviation of pre-movement time
            
        Returns:
            Dictionary with all results
        """
        print("=" * 70)
        print("QRA SYSTEM - EVACUATION SIMULATION AND RISK ASSESSMENT")
        print("=" * 70)
        print()
        
        # Create building
        print(f"Building Configuration:")
        print(f"  Dimensions: {building_width}m x {building_height}m")
        print(f"  Number of Exits: {num_exits}")
        print(f"  Occupants: {num_agents}")
        print()
        
        building = create_simple_building(building_width, building_height, num_exits)
        
        # Run simulations
        print(f"Running {num_simulations} evacuation simulations...")
        simulation = EvacuationSimulation(
            building=building,
            num_agents=num_agents,
            mean_speed=mean_speed,
            std_speed=std_speed,
            mean_pre_movement=mean_pre_movement,
            std_pre_movement=std_pre_movement
        )
        
        simulation_results = simulation.run_multiple_simulations(num_simulations)
        print(f"✓ Completed {num_simulations} simulations")
        print()
        
        # Analyze results
        print("Performing statistical analysis...")
        analysis = analyze_multiple_simulations(simulation_results)
        evacuation_times = analysis['all_evacuation_times']
        
        stats_analyzer = StatisticalAnalysis(evacuation_times)
        descriptive_stats = stats_analyzer.calculate_descriptive_statistics()
        percentiles = stats_analyzer.calculate_percentiles()
        
        print(f"✓ Statistical analysis complete")
        print(f"  Mean evacuation time: {descriptive_stats['mean']:.2f}s")
        print(f"  95th percentile: {descriptive_stats['q95']:.2f}s")
        print()
        
        # Risk analysis
        risk_analysis_results = None
        if aset is not None:
            print(f"Performing risk analysis (ASET = {aset}s)...")
            risk_analyzer = RiskAnalysis(evacuation_times)
            risk_analysis_results = risk_analyzer.calculate_aset_rset_comparison(aset)
            print(f"✓ Risk analysis complete")
            print(f"  Success probability: {risk_analysis_results['probability_success']:.1%}")
            print(f"  Risk (failure probability): {risk_analysis_results['risk_probability']:.2%}")
            print()
        
        # Generate visualizations
        print("Generating visualizations...")
        plot_paths = {}
        
        plot_paths['histogram'] = self.visualizer.plot_evacuation_time_histogram(
            evacuation_times, aset=aset
        )
        
        plot_paths['cumulative'] = self.visualizer.plot_cumulative_distribution(
            evacuation_times, aset=aset
        )
        
        plot_paths['percentiles'] = self.visualizer.plot_percentile_comparison(
            percentiles, aset=aset
        )
        
        if aset is not None and risk_analysis_results:
            risk_analyzer = RiskAnalysis(evacuation_times)
            fn_curve = risk_analyzer.calculate_fntds_curve()
            plot_paths['risk_curve'] = self.visualizer.plot_risk_curve(
                fn_curve['aset_values'], fn_curve['cumulative_risk']
            )
            
            plot_paths['safety_margin'] = self.visualizer.plot_safety_margin_distribution(
                risk_analysis_results['safety_margins']
            )
        
        plot_paths['dashboard'] = self.visualizer.create_summary_dashboard(
            evacuation_times, aset=aset
        )
        
        print(f"✓ Generated {len(plot_paths)} visualization plots")
        print()
        
        # Generate reports
        print("Generating reports...")
        
        simulation_params = {
            'Number of Agents': num_agents,
            'Building Width': f'{building_width} m',
            'Building Height': f'{building_height} m',
            'Number of Exits': num_exits,
            'Number of Simulations': num_simulations,
            'Mean Walking Speed': f'{mean_speed} m/s',
            'Std Walking Speed': f'{std_speed} m/s',
            'Mean Pre-movement Time': f'{mean_pre_movement} s',
            'Std Pre-movement Time': f'{std_pre_movement} s',
        }
        
        if aset:
            simulation_params['ASET'] = f'{aset} s'
        
        report_data = {
            'descriptive_statistics': descriptive_stats,
            'percentiles': percentiles,
            'distributions': analysis['distributions']
        }
        
        if risk_analysis_results:
            report_data['risk_analysis'] = risk_analysis_results
        
        text_report_path = self.report_generator.generate_text_report(
            report_data, simulation_params
        )
        
        html_report_path = self.report_generator.generate_html_report(
            report_data, simulation_params, plot_paths
        )
        
        print(f"✓ Generated reports")
        print(f"  Text report: {text_report_path}")
        print(f"  HTML report: {html_report_path}")
        print()
        
        # Print summary
        print("=" * 70)
        print("ANALYSIS SUMMARY")
        print("=" * 70)
        summary = self.report_generator.generate_summary(report_data)
        print(summary)
        
        return {
            'simulation_results': simulation_results,
            'analysis': analysis,
            'descriptive_statistics': descriptive_stats,
            'percentiles': percentiles,
            'risk_analysis': risk_analysis_results,
            'plot_paths': plot_paths,
            'text_report': text_report_path,
            'html_report': html_report_path
        }


def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(
        description='QRA System - Evacuation Simulation and Risk Assessment',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--num-agents', type=int, default=100,
                       help='Number of occupants/agents')
    parser.add_argument('--building-width', type=float, default=50.0,
                       help='Building width in meters')
    parser.add_argument('--building-height', type=float, default=30.0,
                       help='Building height in meters')
    parser.add_argument('--num-exits', type=int, default=2,
                       help='Number of exits')
    parser.add_argument('--num-simulations', type=int, default=10,
                       help='Number of simulations to run')
    parser.add_argument('--aset', type=float, default=None,
                       help='Available Safe Egress Time in seconds')
    parser.add_argument('--mean-speed', type=float, default=1.2,
                       help='Mean walking speed in m/s')
    parser.add_argument('--std-speed', type=float, default=0.3,
                       help='Standard deviation of walking speed')
    parser.add_argument('--mean-pre-movement', type=float, default=30.0,
                       help='Mean pre-movement time in seconds')
    parser.add_argument('--std-pre-movement', type=float, default=10.0,
                       help='Standard deviation of pre-movement time')
    parser.add_argument('--output-dir', type=str, default='outputs',
                       help='Output directory for results')
    
    args = parser.parse_args()
    
    # Create QRA system
    qra_system = QRASystem(output_dir=args.output_dir)
    
    # Run analysis
    results = qra_system.run_analysis(
        num_agents=args.num_agents,
        building_width=args.building_width,
        building_height=args.building_height,
        num_exits=args.num_exits,
        num_simulations=args.num_simulations,
        aset=args.aset,
        mean_speed=args.mean_speed,
        std_speed=args.std_speed,
        mean_pre_movement=args.mean_pre_movement,
        std_pre_movement=args.std_pre_movement
    )
    
    print()
    print("=" * 70)
    print("Analysis complete! Check the output directory for results.")
    print("=" * 70)
    
    return results


if __name__ == '__main__':
    main()

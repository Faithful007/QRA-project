"""
Visualization Module
Creates graphs and plots for QRA analysis
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from typing import List, Dict, Optional, Tuple
import os


class QRAVisualizer:
    """
    Creates visualizations for QRA analysis
    """
    
    def __init__(self, output_dir: str = "outputs"):
        """
        Initialize visualizer
        
        Args:
            output_dir: Directory to save plots
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (10, 6)
        plt.rcParams['font.size'] = 10
    
    def plot_evacuation_time_histogram(self, evacuation_times: np.ndarray, 
                                      aset: Optional[float] = None,
                                      save_path: Optional[str] = None) -> str:
        """
        Plot histogram of evacuation times
        
        Args:
            evacuation_times: Array of evacuation times
            aset: Optional ASET value to mark on plot
            save_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Create histogram
        n, bins, patches = ax.hist(evacuation_times, bins=30, 
                                   alpha=0.7, color='skyblue', 
                                   edgecolor='black', density=True)
        
        # Add KDE
        kde = stats.gaussian_kde(evacuation_times)
        x_range = np.linspace(evacuation_times.min(), evacuation_times.max(), 200)
        ax.plot(x_range, kde(x_range), 'r-', linewidth=2, label='KDE')
        
        # Mark ASET if provided
        if aset is not None:
            ax.axvline(aset, color='red', linestyle='--', linewidth=2, 
                      label=f'ASET = {aset:.1f}s')
        
        # Mark mean
        mean_time = np.mean(evacuation_times)
        ax.axvline(mean_time, color='green', linestyle='--', linewidth=2, 
                  label=f'Mean = {mean_time:.1f}s')
        
        ax.set_xlabel('Evacuation Time (seconds)', fontsize=12)
        ax.set_ylabel('Probability Density', fontsize=12)
        ax.set_title('Distribution of Evacuation Times', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Save plot
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'evacuation_time_histogram.png')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_cumulative_distribution(self, evacuation_times: np.ndarray,
                                    aset: Optional[float] = None,
                                    save_path: Optional[str] = None) -> str:
        """
        Plot cumulative distribution of evacuation times
        
        Args:
            evacuation_times: Array of evacuation times
            aset: Optional ASET value to mark on plot
            save_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Sort data
        sorted_times = np.sort(evacuation_times)
        cumulative_prob = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
        
        # Plot
        ax.plot(sorted_times, cumulative_prob * 100, 'b-', linewidth=2)
        
        # Mark ASET if provided
        if aset is not None:
            prob_at_aset = np.mean(evacuation_times <= aset) * 100
            ax.axvline(aset, color='red', linestyle='--', linewidth=2, 
                      label=f'ASET = {aset:.1f}s ({prob_at_aset:.1f}% evacuated)')
            ax.axhline(prob_at_aset, color='red', linestyle=':', alpha=0.5)
        
        # Mark percentiles
        for p in [50, 95, 99]:
            percentile_value = np.percentile(evacuation_times, p)
            ax.axhline(p, color='gray', linestyle=':', alpha=0.5)
            ax.text(evacuation_times.max() * 0.95, p, f'{p}th', 
                   verticalalignment='center')
        
        ax.set_xlabel('Evacuation Time (seconds)', fontsize=12)
        ax.set_ylabel('Cumulative Probability (%)', fontsize=12)
        ax.set_title('Cumulative Distribution of Evacuation Times', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        if aset is not None:
            ax.legend()
        
        # Save plot
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'cumulative_distribution.png')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_risk_curve(self, aset_values: np.ndarray, risk_values: np.ndarray,
                       save_path: Optional[str] = None) -> str:
        """
        Plot risk curve showing probability of failure vs ASET
        
        Args:
            aset_values: Array of ASET values
            risk_values: Array of corresponding risk probabilities
            save_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot risk curve
        ax.plot(aset_values, risk_values * 100, 'b-', linewidth=2)
        ax.fill_between(aset_values, 0, risk_values * 100, alpha=0.3)
        
        # Add horizontal lines for risk levels
        risk_levels = {
            'High Risk': 10,
            'Medium Risk': 1,
            'Low Risk': 0.1
        }
        
        colors = ['red', 'orange', 'green']
        for (label, risk_level), color in zip(risk_levels.items(), colors):
            ax.axhline(risk_level, color=color, linestyle='--', alpha=0.5, label=label)
        
        ax.set_xlabel('ASET - Available Safe Egress Time (seconds)', fontsize=12)
        ax.set_ylabel('Risk - Probability of Failure (%)', fontsize=12)
        ax.set_title('Risk Curve (ASET vs Probability of Failure)', fontsize=14, fontweight='bold')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3, which='both')
        ax.legend()
        
        # Save plot
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'risk_curve.png')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_safety_margin_distribution(self, safety_margins: np.ndarray,
                                       save_path: Optional[str] = None) -> str:
        """
        Plot distribution of safety margins (ASET - RSET)
        
        Args:
            safety_margins: Array of safety margin values
            save_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Create histogram
        ax.hist(safety_margins, bins=30, alpha=0.7, color='lightgreen', 
               edgecolor='black', density=True)
        
        # Add KDE
        kde = stats.gaussian_kde(safety_margins)
        x_range = np.linspace(safety_margins.min(), safety_margins.max(), 200)
        ax.plot(x_range, kde(x_range), 'g-', linewidth=2, label='KDE')
        
        # Mark zero line
        ax.axvline(0, color='red', linestyle='--', linewidth=2, 
                  label='Zero Safety Margin')
        
        # Mark mean
        mean_margin = np.mean(safety_margins)
        ax.axvline(mean_margin, color='blue', linestyle='--', linewidth=2, 
                  label=f'Mean = {mean_margin:.1f}s')
        
        # Color regions
        negative_prob = np.mean(safety_margins < 0) * 100
        
        ax.set_xlabel('Safety Margin (ASET - RSET) (seconds)', fontsize=12)
        ax.set_ylabel('Probability Density', fontsize=12)
        ax.set_title(f'Distribution of Safety Margins ({negative_prob:.1f}% negative)', 
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Save plot
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'safety_margin_distribution.png')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def plot_percentile_comparison(self, percentiles: Dict[float, float],
                                   aset: Optional[float] = None,
                                   save_path: Optional[str] = None) -> str:
        """
        Plot bar chart of evacuation time percentiles
        
        Args:
            percentiles: Dictionary mapping percentile to value
            aset: Optional ASET value to mark on plot
            save_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Prepare data
        percentile_labels = [f'{p}th' for p in percentiles.keys()]
        values = list(percentiles.values())
        
        # Create bar plot
        bars = ax.bar(percentile_labels, values, alpha=0.7, color='steelblue', 
                     edgecolor='black')
        
        # Color bars based on ASET
        if aset is not None:
            for bar, value in zip(bars, values):
                if value > aset:
                    bar.set_color('red')
                    bar.set_alpha(0.7)
            
            # Add ASET line
            ax.axhline(aset, color='red', linestyle='--', linewidth=2, 
                      label=f'ASET = {aset:.1f}s')
        
        ax.set_xlabel('Percentile', fontsize=12)
        ax.set_ylabel('Evacuation Time (seconds)', fontsize=12)
        ax.set_title('Evacuation Time Percentiles', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
        if aset is not None:
            ax.legend()
        
        # Add value labels on bars
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value:.1f}s', ha='center', va='bottom', fontsize=9)
        
        # Save plot
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'percentile_comparison.png')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return save_path
    
    def create_summary_dashboard(self, evacuation_times: np.ndarray, 
                                aset: Optional[float] = None,
                                save_path: Optional[str] = None) -> str:
        """
        Create a summary dashboard with multiple plots
        
        Args:
            evacuation_times: Array of evacuation times
            aset: Optional ASET value
            save_path: Path to save plot (optional)
            
        Returns:
            Path to saved plot
        """
        fig = plt.figure(figsize=(16, 10))
        gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)
        
        # 1. Histogram
        ax1 = fig.add_subplot(gs[0, 0])
        ax1.hist(evacuation_times, bins=30, alpha=0.7, color='skyblue', edgecolor='black')
        if aset:
            ax1.axvline(aset, color='red', linestyle='--', linewidth=2, label=f'ASET={aset:.1f}s')
        ax1.set_xlabel('Evacuation Time (s)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Evacuation Time Distribution')
        ax1.grid(True, alpha=0.3)
        if aset:
            ax1.legend()
        
        # 2. Cumulative Distribution
        ax2 = fig.add_subplot(gs[0, 1])
        sorted_times = np.sort(evacuation_times)
        cumulative_prob = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
        ax2.plot(sorted_times, cumulative_prob * 100, 'b-', linewidth=2)
        if aset:
            prob_at_aset = np.mean(evacuation_times <= aset) * 100
            ax2.axvline(aset, color='red', linestyle='--', linewidth=2)
        ax2.set_xlabel('Evacuation Time (s)')
        ax2.set_ylabel('Cumulative Probability (%)')
        ax2.set_title('Cumulative Distribution')
        ax2.grid(True, alpha=0.3)
        
        # 3. Box Plot
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.boxplot(evacuation_times, vert=True, patch_artist=True,
                   boxprops=dict(facecolor='lightblue', alpha=0.7))
        if aset:
            ax3.axhline(aset, color='red', linestyle='--', linewidth=2, label=f'ASET={aset:.1f}s')
        ax3.set_ylabel('Evacuation Time (s)')
        ax3.set_title('Box Plot')
        ax3.grid(True, alpha=0.3)
        if aset:
            ax3.legend()
        
        # 4. Statistics Table
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.axis('tight')
        ax4.axis('off')
        
        stats_data = [
            ['Statistic', 'Value'],
            ['Mean', f'{np.mean(evacuation_times):.2f} s'],
            ['Median', f'{np.median(evacuation_times):.2f} s'],
            ['Std Dev', f'{np.std(evacuation_times):.2f} s'],
            ['Min', f'{np.min(evacuation_times):.2f} s'],
            ['Max', f'{np.max(evacuation_times):.2f} s'],
            ['95th Percentile', f'{np.percentile(evacuation_times, 95):.2f} s'],
            ['99th Percentile', f'{np.percentile(evacuation_times, 99):.2f} s']
        ]
        
        if aset:
            prob_success = np.mean(evacuation_times < aset) * 100
            stats_data.extend([
                ['ASET', f'{aset:.2f} s'],
                ['Success Rate', f'{prob_success:.2f}%']
            ])
        
        table = ax4.table(cellText=stats_data, cellLoc='left', loc='center',
                         colWidths=[0.6, 0.4])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        
        # Style header row
        for i in range(2):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')
        
        ax4.set_title('Summary Statistics', pad=20)
        
        # Save plot
        if save_path is None:
            save_path = os.path.join(self.output_dir, 'summary_dashboard.png')
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return save_path

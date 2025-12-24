"""
Statistical Analysis Module
Performs statistical calculations for quantitative risk assessment
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Tuple, Optional


class StatisticalAnalysis:
    """
    Performs statistical analysis on evacuation simulation results
    """
    
    def __init__(self, evacuation_times: np.ndarray):
        """
        Initialize statistical analysis
        
        Args:
            evacuation_times: Array of evacuation times from simulations
        """
        self.evacuation_times = evacuation_times
    
    def calculate_descriptive_statistics(self) -> Dict[str, float]:
        """
        Calculate descriptive statistics
        
        Returns:
            Dictionary with statistical measures
        """
        return {
            'mean': np.mean(self.evacuation_times),
            'median': np.median(self.evacuation_times),
            'std': np.std(self.evacuation_times),
            'variance': np.var(self.evacuation_times),
            'min': np.min(self.evacuation_times),
            'max': np.max(self.evacuation_times),
            'q25': np.percentile(self.evacuation_times, 25),
            'q75': np.percentile(self.evacuation_times, 75),
            'q95': np.percentile(self.evacuation_times, 95),
            'q99': np.percentile(self.evacuation_times, 99),
            'iqr': np.percentile(self.evacuation_times, 75) - np.percentile(self.evacuation_times, 25)
        }
    
    def fit_distribution(self, distribution: str = 'lognormal') -> Dict[str, any]:
        """
        Fit a probability distribution to the evacuation times
        
        Args:
            distribution: Distribution type ('normal', 'lognormal', 'weibull')
            
        Returns:
            Dictionary with distribution parameters and goodness of fit
        """
        if distribution == 'normal':
            params = stats.norm.fit(self.evacuation_times)
            dist = stats.norm(*params)
            dist_name = 'Normal'
        elif distribution == 'lognormal':
            # Filter out zeros for lognormal
            data = self.evacuation_times[self.evacuation_times > 0]
            params = stats.lognorm.fit(data, floc=0)
            dist = stats.lognorm(*params)
            dist_name = 'Lognormal'
        elif distribution == 'weibull':
            params = stats.weibull_min.fit(self.evacuation_times, floc=0)
            dist = stats.weibull_min(*params)
            dist_name = 'Weibull'
        else:
            raise ValueError(f"Unknown distribution: {distribution}")
        
        # Perform Kolmogorov-Smirnov test
        ks_statistic, p_value = stats.kstest(self.evacuation_times, dist.cdf)
        
        return {
            'distribution': dist_name,
            'parameters': params,
            'ks_statistic': ks_statistic,
            'p_value': p_value,
            'dist_object': dist
        }
    
    def calculate_percentiles(self, percentiles: List[float] = None) -> Dict[float, float]:
        """
        Calculate specific percentiles
        
        Args:
            percentiles: List of percentiles to calculate (0-100)
            
        Returns:
            Dictionary mapping percentile to value
        """
        if percentiles is None:
            percentiles = [5, 10, 25, 50, 75, 90, 95, 99]
        
        return {p: np.percentile(self.evacuation_times, p) for p in percentiles}
    
    def calculate_confidence_intervals(self, confidence: float = 0.95) -> Dict[str, Tuple[float, float]]:
        """
        Calculate confidence intervals for mean and percentiles
        
        Args:
            confidence: Confidence level (default 0.95 for 95% CI)
            
        Returns:
            Dictionary with confidence intervals
        """
        n = len(self.evacuation_times)
        mean = np.mean(self.evacuation_times)
        std_err = stats.sem(self.evacuation_times)
        
        # CI for mean
        ci_mean = stats.t.interval(confidence, n-1, loc=mean, scale=std_err)
        
        # Bootstrap CI for median
        bootstrap_medians = []
        for _ in range(1000):
            sample = np.random.choice(self.evacuation_times, size=n, replace=True)
            bootstrap_medians.append(np.median(sample))
        
        alpha = 1 - confidence
        ci_median = (
            np.percentile(bootstrap_medians, alpha/2 * 100),
            np.percentile(bootstrap_medians, (1 - alpha/2) * 100)
        )
        
        return {
            'mean_ci': ci_mean,
            'median_ci': ci_median
        }


class RiskAnalysis:
    """
    Performs risk calculations including ASET/RSET analysis
    """
    
    def __init__(self, evacuation_times: np.ndarray):
        """
        Initialize risk analysis
        
        Args:
            evacuation_times: Array of evacuation times (RSET - Required Safe Egress Time)
        """
        self.evacuation_times = evacuation_times
    
    def calculate_aset_rset_comparison(self, aset: float) -> Dict[str, any]:
        """
        Calculate ASET/RSET comparison
        
        ASET: Available Safe Egress Time (time until untenable conditions)
        RSET: Required Safe Egress Time (time to evacuate)
        
        Args:
            aset: Available Safe Egress Time in seconds
            
        Returns:
            Dictionary with risk metrics
        """
        # Calculate safety margin (ASET - RSET)
        safety_margins = aset - self.evacuation_times
        
        # Calculate probability of successful evacuation
        prob_success = np.mean(self.evacuation_times < aset)
        
        # Calculate risk (probability of failure)
        risk = 1 - prob_success
        
        return {
            'aset': aset,
            'mean_rset': np.mean(self.evacuation_times),
            'max_rset': np.max(self.evacuation_times),
            'mean_safety_margin': np.mean(safety_margins),
            'min_safety_margin': np.min(safety_margins),
            'probability_success': prob_success,
            'risk_probability': risk,
            'safety_margins': safety_margins
        }
    
    def calculate_fntds_curve(self, aset_values: np.ndarray = None) -> Dict[str, np.ndarray]:
        """
        Calculate FN curve (Frequency-Number of Deaths)
        Simplified version showing cumulative risk
        
        Args:
            aset_values: Array of ASET values to evaluate
            
        Returns:
            Dictionary with FN curve data
        """
        if aset_values is None:
            aset_values = np.linspace(
                np.min(self.evacuation_times) * 0.5,
                np.max(self.evacuation_times) * 1.5,
                100
            )
        
        cumulative_risk = []
        for aset in aset_values:
            risk = np.mean(self.evacuation_times > aset)
            cumulative_risk.append(risk)
        
        return {
            'aset_values': aset_values,
            'cumulative_risk': np.array(cumulative_risk)
        }
    
    def calculate_individual_risk(self, aset: float, population: int) -> Dict[str, float]:
        """
        Calculate individual risk metrics
        
        Args:
            aset: Available Safe Egress Time
            population: Building population
            
        Returns:
            Dictionary with individual risk metrics
        """
        prob_failure = np.mean(self.evacuation_times > aset)
        
        return {
            'individual_risk': prob_failure,
            'expected_fatalities': prob_failure * population,
            'aset': aset,
            'population': population
        }


def analyze_multiple_simulations(simulation_results: List[Dict]) -> Dict[str, any]:
    """
    Analyze results from multiple simulations
    
    Args:
        simulation_results: List of simulation result dictionaries
        
    Returns:
        Combined statistical analysis
    """
    # Combine all evacuation times
    all_times = []
    for result in simulation_results:
        all_times.extend(result['evacuation_times'])
    
    all_times = np.array(all_times)
    
    # Perform statistical analysis
    stats_analysis = StatisticalAnalysis(all_times)
    descriptive_stats = stats_analysis.calculate_descriptive_statistics()
    percentiles = stats_analysis.calculate_percentiles()
    
    # Fit distributions
    distributions = {}
    for dist_type in ['normal', 'lognormal', 'weibull']:
        try:
            distributions[dist_type] = stats_analysis.fit_distribution(dist_type)
        except Exception as e:
            distributions[dist_type] = {'error': str(e)}
    
    return {
        'all_evacuation_times': all_times,
        'descriptive_statistics': descriptive_stats,
        'percentiles': percentiles,
        'distributions': distributions,
        'num_simulations': len(simulation_results),
        'total_evacuations': len(all_times)
    }

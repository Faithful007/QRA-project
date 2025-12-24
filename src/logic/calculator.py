import math
from src.models import TunnelConfiguration, VehicleClassification, HAREVACAnalysis
from src.models.qra_results import QRAResult

class QRACalculator:
    """
    Core logic for Quantitative Risk Analysis calculations, including
    FED (Fractional Effective Dose), ASET (Available Safe Egress Time),
    RSET (Required Safe Egress Time), and F-N Curve Risk Evaluation.
    """

    def __init__(self, session):
        self.session = session
        # F-N Curve Criteria (Hardcoded based on the provided image)
        # Unacceptable Boundary: log10(F) = UNACCEPTABLE_A + UNACCEPTABLE_B * log10(N)
        # Acceptable Boundary: log10(F) = ACCEPTABLE_C + ACCEPTABLE_D * log10(N)
        # These values are estimated from the log-log plot in the image.
        self.UNACCEPTABLE_A = -2.0  # log10(F) intercept at N=1
        self.UNACCEPTABLE_B = -1.0  # Slope (log10(F) vs log10(N))
        self.ACCEPTABLE_C = -4.0    # log10(F) intercept at N=1
        self.ACCEPTABLE_D = -1.0    # Slope (log10(F) vs log10(N))

    def calculate_total_pcu(self, tunnel_config_id):
        """
        Calculates the total Passenger Car Unit (PCU) volume for the tunnel.
        """
        tunnel = self.session.get(TunnelConfiguration, tunnel_config_id)
        if not tunnel:
            return 0.0

        total_pcu = 0.0
        for v_class in tunnel.vehicle_classifications:
            # Assuming the total PCU is the sum of PCU * Volume for both directions
            total_pcu += v_class.pcu * (v_class.volume_plus + v_class.volume_minus)
            
        return total_pcu

    def calculate_accident_frequency(self, tunnel_config_id):
        """
        Calculates the Accident Frequency (F) per year (Accidents/Year).
        Simplified: F = Annual Traffic * Tunnel Length (km) * Accident Rate
        """
        tunnel = self.session.get(TunnelConfiguration, tunnel_config_id)
        if not tunnel:
            return 0.0
            
        # Simplified total daily traffic (vehicles/day)
        total_daily_traffic = sum(
            (v.volume_plus + v.volume_minus) for v in tunnel.vehicle_classifications
        )
        
        # Convert to annual traffic (vehicles/year)
        annual_traffic = total_daily_traffic * 365
        
        # Simplified accident rate (accidents/vehicle-km)
        ACCIDENT_RATE = 1.0e-7
        
        # F = Annual Traffic * Tunnel Length (km) * Accident Rate
        # Assuming tunnel length is in meters, convert to km
        tunnel_length_km = tunnel.length / 1000.0
        
        accident_frequency = annual_traffic * tunnel_length_km * ACCIDENT_RATE
        
        return accident_frequency

    def calculate_fatalities(self, tunnel_config_id, aset_s, rset_s):
        """
        Calculates the average number of fatalities (N) per accident.
        Simplified: N is proportional to the number of people trapped and the safety margin.
        """
        tunnel = self.session.get(TunnelConfiguration, tunnel_config_id)
        
        # Total occupancy (simplified: sum of max occupancy of all vehicle types)
        total_occupancy = sum(
            v.occupancy * (v.volume_plus + v.volume_minus) for v in tunnel.vehicle_classifications
        )
        
        # Simplified Fatality Ratio: based on safety margin (ASET - RSET)
        safety_margin = aset_s - rset_s
        
        if safety_margin > 0:
            # If ASET > RSET, fatality ratio is low (e.g., 1%)
            fatality_ratio = 0.01
        else:
            # If ASET < RSET, fatality ratio is high (e.g., 10% + penalty for negative margin)
            fatality_ratio = 0.10 + (abs(safety_margin) / 1000.0) # Penalty for delay
            
        # N = Total Occupancy * Fatality Ratio
        fatalities = total_occupancy * fatality_ratio
        
        # Ensure N is at least 1 for the F-N curve
        return max(1.0, fatalities)

    def calculate_fed(self, co_ppm, temp_c, visibility_m, time_s):
        """
        Calculates the Fractional Effective Dose (FED) based on simplified
        exposure to CO, heat, and smoke.
        """
        # ... (Simplified FED calculation logic - unchanged)
        
        # Lethal Limits (highly simplified constants for demonstration)
        CO_LETHAL = 12500.0  # ppm*min (approx)
        TEMP_LETHAL = 100.0  # C
        VIS_LETHAL = 0.5     # m (inverse)

        # Simplified exposure calculation (not time-integrated)
        co_exposure = (co_ppm / CO_LETHAL) * (time_s / 60)
        temp_exposure = (temp_c / TEMP_LETHAL) * (time_s / 60)
        smoke_exposure = (1 / visibility_m) * VIS_LETHAL * (time_s / 60)
        
        # Total FED is the sum of fractional doses
        total_fed = co_exposure + temp_exposure + smoke_exposure
        
        return total_fed

    def calculate_aset(self, tunnel_config_id, hrr_mw, growth_rate_type):
        """
        Calculates Available Safe Egress Time (ASET).
        """
        har_evac = self.session.get(HAREVACAnalysis, tunnel_config_id)
        if not har_evac:
            return 0.0

        # Simplified t-squared fire growth model approximation: Q = alpha * t^2
        growth_factors = {
            "Slow": 0.00293, "Medium": 0.01172, "Fast": 0.04688, "Ultra-Fast": 0.1875
        }
        alpha = growth_factors.get(growth_rate_type, 0.01172) # Default to Medium

        # Time to reach peak HRR (t_peak)
        t_peak = math.sqrt((hrr_mw * 1000) / alpha) # Convert MW to kW

        tunnel = self.session.get(TunnelConfiguration, tunnel_config_id)
        if not tunnel:
            return 0.0

        # ASET is the minimum of the time to reach each critical condition
        t_temp = t_peak * (har_evac.temperature_limit / 60.0)
        t_vis = t_peak * (har_evac.visibility_limit / 10.0)
        t_fed = t_peak * 0.8 # Assume FED limit is reached slightly before peak HRR

        aset_value = min(t_temp, t_vis, t_fed)
        
        # Return ASET in seconds, capped at 30 minutes (1800s) for realism
        return max(60.0, min(aset_value, 1800.0))

    def calculate_rset(self, tunnel_config_id):
        """
        Calculates Required Safe Egress Time (RSET).
        RSET = Detection + Alarm + Pre-movement + Travel Time
        """
        har_evac = self.session.get(HAREVACAnalysis, tunnel_config_id)
        if not har_evac:
            return 0.0

        tunnel = self.session.get(TunnelConfiguration, tunnel_config_id)
        if not tunnel:
            return 0.0

        # 1. Detection and Alarm Time (Simplified)
        t_detect_alarm = 30.0 # seconds

        # 2. Pre-movement Time (Reaction + Hesitation)
        t_pre_movement = har_evac.reaction_time + har_evac.hesitation_time

        # 3. Travel Time (Simplified: distance / speed)
        travel_distance = tunnel.length / 2.0
        travel_speed = har_evac.evac_speed_walking
        
        if travel_speed <= 0:
            t_travel = float('inf')
        else:
            t_travel = travel_distance / travel_speed

        # Total RSET
        rset_value = t_detect_alarm + t_pre_movement + t_travel
        
        return rset_value

    def _compare_risk_to_criteria(self, F, N):
        """
        Compares the calculated (F, N) point to the F-N curve criteria.
        """
        # Handle edge cases where F or N might be zero or negative
        if F <= 0 or N <= 0:
            return "Error", True

        # Convert to log-log scale for comparison
        log_F = math.log10(F)
        log_N = math.log10(N)
        
        # Unacceptable Boundary: log10(F) = UNACCEPTABLE_A + UNACCEPTABLE_B * log10(N)
        unacceptable_threshold = self.UNACCEPTABLE_A + self.UNACCEPTABLE_B * log_N
        
        # Acceptable Boundary: log10(F) = ACCEPTABLE_C + ACCEPTABLE_D * log10(N)
        acceptable_threshold = self.ACCEPTABLE_C + self.ACCEPTABLE_D * log_N
        
        if log_F > unacceptable_threshold:
            # Above the Unacceptable line
            return "Unacceptable", True
        elif log_F > acceptable_threshold:
            # Between Unacceptable and Acceptable lines (ALARP)
            return "ALARP", True
        else:
            # Below the Acceptable line
            return "Acceptable", False

    def generate_fn_curve_data(self):
        """
        Generates the data points for plotting the F-N curve boundaries.
        """
        # N values from 1 to 10000 for the plot
        N_values = [1, 10, 100, 1000, 10000]
        
        unacceptable_F = [
            10**(self.UNACCEPTABLE_A + self.UNACCEPTABLE_B * math.log10(N)) for N in N_values
        ]
        acceptable_F = [
            10**(self.ACCEPTABLE_C + self.ACCEPTABLE_D * math.log10(N)) for N in N_values
        ]
        
        return {
            "N_values": N_values,
            "unacceptable_F": unacceptable_F,
            "acceptable_F": acceptable_F
        }

    def run_simulation(self, tunnel_config_id):
        """
        Runs a full QRA simulation for the given tunnel configuration, following the flowchart.
        """
        tunnel = self.session.get(TunnelConfiguration, tunnel_config_id)
        har_evac = self.session.get(HAREVACAnalysis, tunnel_config_id)
        
        if not tunnel or not har_evac:
            return {"error": "Configuration data missing."}

        # Use placeholder values for HRR and growth rate from the HAR EVAC model
        hrr_mw = har_evac.heat_release_rate
        growth_rate_type = har_evac.fire_growth_rate
        
        # 1. CFD & FED Analysis (Simplified to ASET/RSET)
        aset = self.calculate_aset(tunnel_config_id, hrr_mw, growth_rate_type)
        rset = self.calculate_rset(tunnel_config_id)
        safety_margin = aset - rset
        
        # 2. Fatality Analysis (N)
        fatalities_per_accident = self.calculate_fatalities(tunnel_config_id, aset, rset)
        
        # 3. Accident Frequency Prediction (F)
        accident_frequency_per_year = self.calculate_accident_frequency(tunnel_config_id)
        
        # 4. QRA Analysis (F-N Curve Comparison)
        risk_status, improvement_required = self._compare_risk_to_criteria(
            accident_frequency_per_year, fatalities_per_accident
        )
        
        # 5. Save Results
        qra_result = self.session.query(QRAResult).filter_by(tunnel_config_id=tunnel_config_id).first()
        if not qra_result:
            qra_result = QRAResult(tunnel_config_id=tunnel_config_id)
            self.session.add(qra_result)
            
        qra_result.accident_frequency_per_year = accident_frequency_per_year
        qra_result.fatalities_per_accident = fatalities_per_accident
        qra_result.risk_status = risk_status
        qra_result.improvement_required = improvement_required
        self.session.commit()
        
        # 6. Formal End / Return Results
        return {
            "tunnel_name": tunnel.name,
            "total_pcu": self.calculate_total_pcu(tunnel_config_id),
            "aset_s": aset,
            "rset_s": rset,
            "safety_margin_s": safety_margin,
            "is_safe": safety_margin > 0,
            "accident_frequency_per_year": accident_frequency_per_year,
            "fatalities_per_accident": fatalities_per_accident,
            "risk_status": risk_status,
            "improvement_required": improvement_required,
            "simulation_status": "Completed (Full QRA Procedure)"
        }

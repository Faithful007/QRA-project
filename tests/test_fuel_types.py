#!/usr/bin/env python3
"""
Test script to verify FDS generation with different fuel types
"""

import sys
from pathlib import Path

# Add fds_workflow to path
sys.path.insert(0, str(Path(__file__).parent / "fds_workflow"))

from fds_generator import FDSInputGenerator, TunnelGeometry, FireScenario

def test_diesel_fds6():
    """Test FDS6 generation with Diesel fuel (≥20MW)"""
    print("\n" + "="*60)
    print("TEST 1: FDS6 with Diesel (30MW)")
    print("="*60)
    
    tunnel = TunnelGeometry(
        name="TEST_TUNNEL",
        length=2000.0,
        radius=7.2
    )
    
    scenario = FireScenario(
        hrr_type="030",
        hrr_value=30000,  # 30 MW
        fire_position=1000,
        flashover_time=450,
        traffic_condition="Normal",
        ventilation_condition="NVC",
        t_end=900.0,
        # Diesel fuel properties
        fuel_type="Diesel",
        fuel_id="DIESEL",
        fuel="C12H23",
        soot_yield=0.133,
        co_yield=0.168,
        heat_of_combustion=4.3e7,
        fds_version="FDS6"
    )
    
    generator = FDSInputGenerator(tunnel)
    output_file = "/home/ubuntu/qra_system_v2/test_diesel_fds6.fds"
    generator.generate_fds_input(scenario, output_file)
    
    print(f"✓ Generated: {output_file}")
    
    # Read and display REAC section
    with open(output_file, 'r') as f:
        lines = f.readlines()
        in_reac = False
        print("\nREAC Namelist:")
        for line in lines:
            if '&REAC' in line:
                in_reac = True
            if in_reac:
                print(f"  {line.rstrip()}")
            if in_reac and '/' in line:
                break

def test_petrol_fds6():
    """Test FDS6 generation with Petrol fuel (<20MW)"""
    print("\n" + "="*60)
    print("TEST 2: FDS6 with Petrol (10MW)")
    print("="*60)
    
    tunnel = TunnelGeometry(
        name="TEST_TUNNEL",
        length=2000.0,
        radius=7.2
    )
    
    scenario = FireScenario(
        hrr_type="010",
        hrr_value=10000,  # 10 MW
        fire_position=1000,
        flashover_time=450,
        traffic_condition="Normal",
        ventilation_condition="NVC",
        t_end=900.0,
        # Petrol fuel properties
        fuel_type="Petrol",
        fuel_id="PETROL_CAR_FIRE",
        fuel="ISO_OCTANE",
        soot_yield=0.08,
        co_yield=0.025,
        heat_of_combustion=4.4e7,
        fds_version="FDS6"
    )
    
    generator = FDSInputGenerator(tunnel)
    output_file = "/home/ubuntu/qra_system_v2/test_petrol_fds6.fds"
    generator.generate_fds_input(scenario, output_file)
    
    print(f"✓ Generated: {output_file}")
    
    # Read and display REAC section
    with open(output_file, 'r') as f:
        lines = f.readlines()
        in_reac = False
        print("\nREAC Namelist:")
        for line in lines:
            if '&REAC' in line:
                in_reac = True
            if in_reac:
                print(f"  {line.rstrip()}")
            if in_reac and '/' in line:
                break

def test_fds5():
    """Test FDS5 generation"""
    print("\n" + "="*60)
    print("TEST 3: FDS5 format")
    print("="*60)
    
    tunnel = TunnelGeometry(
        name="TEST_TUNNEL",
        length=2000.0,
        radius=7.2
    )
    
    scenario = FireScenario(
        hrr_type="020",
        hrr_value=20000,
        fire_position=1000,
        flashover_time=450,
        traffic_condition="Normal",
        ventilation_condition="NVC",
        t_end=900.0,
        fds_version="FDS5"
    )
    
    generator = FDSInputGenerator(tunnel)
    output_file = "/home/ubuntu/qra_system_v2/test_fds5.fds"
    generator.generate_fds_input(scenario, output_file)
    
    print(f"✓ Generated: {output_file}")
    
    # Read and display REAC section
    with open(output_file, 'r') as f:
        lines = f.readlines()
        in_reac = False
        print("\nREAC Namelist:")
        for line in lines:
            if '&REAC' in line:
                in_reac = True
            if in_reac:
                print(f"  {line.rstrip()}")
            if in_reac and '/' in line:
                break

if __name__ == "__main__":
    print("\n" + "="*60)
    print("QRA System - Fuel Type Configuration Test")
    print("="*60)
    
    test_diesel_fds6()
    test_petrol_fds6()
    test_fds5()
    
    print("\n" + "="*60)
    print("All tests completed successfully!")
    print("="*60)

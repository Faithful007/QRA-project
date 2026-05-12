import sys
import os
from pathlib import Path

# Add project path to sys.path
project_path = "/home/ubuntu/projects/qra-evacuation-engine-optimizati-0b0c6213"
sys.path.append(project_path)

from evc_engine import EVCEngine, RunResult

def test_output_format():
    evc_path = Path(project_path) / "020CFV0_P1.evc"
    fdb_path = Path(project_path) / "020CFV0.FDB"
    
    # Initialize engine
    engine = EVCEngine(evc_path, fdb_path)
    
    # Create a dummy average result
    avg = RunResult(
        run_no=0,
        ev_time=365.0,
        evacuees=100,
        fed=[10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01],
        eq_fatal=0.5,
        pct_safe=86.3507,
        pct_fed=[0.334472, 6.258895, 6.518645, 0.352263, 0.00004625676, 0.1387703],
        n_occ_zone=1000,
        n_occ_total=1081,
        n_evac_zone=863
    )
    
    # Create a dummy run list
    runs = [avg]
    
    # Output path for testing
    test_evc_path = Path("/home/ubuntu/test_output.evc")
    # Copy original to test path first
    import shutil
    shutil.copy(evc_path, test_evc_path)
    
    # Update engine path
    engine.evc_path = test_evc_path
    
    # Manually update the first line to the Korean name to simulate qra_main_app.py
    lines = test_evc_path.read_bytes().split(b"\r\n")
    lines[0] = "율곡터널".encode("cp949")
    test_evc_path.write_bytes(b"\r\n".join(lines))

    # Write results
    engine.write_results_to_evc(avg, runs)
    
    # Read back and check
    content = test_evc_path.read_bytes()
    print(f"File size: {len(content)} bytes")
    
    # Check first line
    try:
        first_line = content.split(b"\r\n")[0].decode("cp949")
        print(f"First line: {first_line}")
    except Exception as e:
        print(f"Error decoding first line: {e}")
        
    # Check row 24 (pct_safe)
    lines = content.split(b"\r\n")
    print(f"Row 24: {lines[23].decode('cp949')}")
    print(f"Row 29: {lines[28].decode('cp949')}")

if __name__ == "__main__":
    test_output_format()
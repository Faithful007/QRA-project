import os
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

try:
    from fds_generator import FDSInputGenerator, TunnelGeometry, FireScenario
except ImportError:
    from .fds_generator import FDSInputGenerator, TunnelGeometry, FireScenario

try:
    from fds_runner import FDSRunner, create_batch_script
except ImportError:
    from .fds_runner import FDSRunner, create_batch_script

try:
    from smv_to_fdb_converter import SMVtoFDBConverter, convert_directory, create_convert_des_file
except ImportError:
    from .smv_to_fdb_converter import SMVtoFDBConverter, convert_directory, create_convert_des_file


class FDSWorkflow:
    """Complete FDS workflow manager"""
    
    def __init__(self, project_dir: str, fds_executable: str = "fds"):
        """
        Initialize workflow
        
        Args:
            project_dir: Base directory for the project
            fds_executable: Path to FDS executable
        """
        self.project_dir = Path(project_dir)
        self.fds_executable = fds_executable
        
        # Create directory structure
        self.input_dir = self.project_dir / "fds_inputs"

        self.fdb_dir = self.project_dir / "fdb_files"
        self.log_dir = self.project_dir / "logs"
        
        for dir_path in [self.input_dir, self.fdb_dir, self.log_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.tunnel = TunnelGeometry()
        self.generator = FDSInputGenerator(self.tunnel)
        self.runner = FDSRunner(fds_executable)
        
        # Workflow state
        self.scenarios = []
        self.workflow_log = []
    
    def define_scenarios(self, 
                        hrr_types: List[tuple] = None,
                        fire_positions: List[float] = None,
                        flashover_times: List[int] = None,
                        traffic_conditions: List[str] = None,
                        ventilation_conditions: List[str] = None):
        """
        Define fire scenarios to simulate
        
        Args:
            hrr_types: List of (type_code, hrr_value) tuples
            fire_positions: List of fire positions along tunnel (meters)
            flashover_times: List of flashover times (seconds)
            traffic_conditions: List of traffic conditions
            ventilation_conditions: List of ventilation conditions
        """
        
        # Default values
        if hrr_types is None:
            hrr_types = [("020", 20000), ("030", 30000), ("100", 100000)]
        
        if fire_positions is None:
            fire_positions = [500, 750, 1000, 1250, 1500, 1750]
        
        if flashover_times is None:
            flashover_times = [450]  # Use only medium growth
        
        if traffic_conditions is None:
            traffic_conditions = ["Normal", "Congested"]
        
        if ventilation_conditions is None:
            ventilation_conditions = ["NVC", "NV0", "FV0"]
        
        # Generate all combinations
        self.scenarios = []
        
        for hrr_type, hrr_value in hrr_types:
            for fire_pos in fire_positions:
                for flashover in flashover_times:
                    for traffic in traffic_conditions:
                        for vent in ventilation_conditions:
                            scenario = FireScenario(
                                hrr_type=hrr_type,
                                hrr_value=hrr_value,
                                fire_position=fire_pos,
                                flashover_time=flashover,
                                traffic_condition=traffic,
                                ventilation_condition=vent
                            )
                            
                            self.scenarios.append(scenario)
        
        print(f"Defined {len(self.scenarios)} fire scenarios")
        self._log_event("scenarios_defined", {"count": len(self.scenarios)})
    
    def generate_inputs(self):
        """Generate FDS input files for all scenarios"""
        
        print(f"\n{'='*60}")
        print("Generating FDS Input Files")
        print(f"{'='*60}\n")
        
        generated_files = []
        
        for i, scenario in enumerate(self.scenarios, 1):
            # Create filename
            pos_index = [500, 750, 1000, 1250, 1500, 1750].index(scenario.fire_position) + 1
            filename = (f"{scenario.hrr_type}_{scenario.traffic_condition[0]}_"
                       f"{scenario.ventilation_condition}_P{pos_index}_F{scenario.flashover_time}.fds")
            
            # Create subdirectory structure
            subdir = self.input_dir / scenario.hrr_type / scenario.traffic_condition / scenario.ventilation_condition
            output_path = subdir / filename
            
            # Generate input file
            try:
                self.generator.generate_fds_input(scenario, str(output_path))
                generated_files.append(str(output_path))
                
                if i % 10 == 0:
                    print(f"  Generated {i}/{len(self.scenarios)} files...")
                
            except Exception as e:
                print(f"Error generating {filename}: {e}")
        
        print(f"\n✓ Generated {len(generated_files)} FDS input files")
        self._log_event("inputs_generated", {"count": len(generated_files)})
        
        return generated_files
    
    def run_simulations(self, input_files: List[str] = None, 
                       max_parallel: int = 1,
                       create_batch: bool = True):
        """
        Run FDS simulations
        
        Args:
            input_files: List of input files to run (default: all generated)
            max_parallel: Maximum parallel simulations
            create_batch: Whether to create batch script
        """
        
        if input_files is None:
            input_files = list(self.input_dir.glob("**/*.fds"))
            input_files = [str(f) for f in input_files]
        
        if len(input_files) == 0:
            print("No input files to run")
            return [], []
        
        print(f"\n{'='*60}")
        print("Running FDS Simulations")
        print(f"{'='*60}\n")
        print(f"Total simulations: {len(input_files)}")
        
        # Create batch script
        if create_batch:
            batch_file = self.project_dir / "run_all_simulations.bat"
            create_batch_script(input_files, str(batch_file))
            print(f"\nBatch script created: {batch_file}")
            print("You can run simulations manually using this script")
        
        # Check if FDS is available
        if not self.runner.check_fds_available():
            print("\n⚠ FDS executable not found")
            print(f"  Looking for: {self.fds_executable}")
            print("  Please install FDS or specify correct path")
            print("  You can use the batch script to run simulations manually")
            return
        
        # Run simulations
        # Pass log_dir to runner for each simulation
        results = []
        simulation_working_dirs = []
        if max_parallel == 1:
            for input_file in input_files:
                # Determine unique output directory for this simulation
                input_file_path = Path(input_file)
                simulation_working_dir = input_file_path.parent
                simulation_working_dir.mkdir(parents=True, exist_ok=True)

                result = self.runner.run_simulation(input_file, working_dir=str(simulation_working_dir), log_dir=str(simulation_working_dir))
                results.append(result)
                simulation_working_dirs.append(simulation_working_dir)
        else:
            # Parallel execution not implemented, fallback to sequential
            for input_file in input_files:
                # Determine unique output directory for this simulation
                input_file_path = Path(input_file)
                simulation_working_dir = input_file_path.parent
                simulation_working_dir.mkdir(parents=True, exist_ok=True)

                result = self.runner.run_simulation(input_file, working_dir=str(simulation_working_dir), log_dir=str(simulation_working_dir))
                results.append(result)
                simulation_working_dirs.append(simulation_working_dir)
                successful = sum(1 for r in results if r.returncode == 0)
        self._log_event("simulations_run", {
            "total": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "output_dirs": [str(d) for d in simulation_working_dirs]
        })
        return results, simulation_working_dirs
    
    def convert_to_fdb(self, simulation_output_dirs: List[str]):
        """Convert SMV output files to FDB format"""
        
        print(f"\n{'='*60}")
        print("Converting SMV to FDB Format")
        print(f"{'='*60}\n")
        
        # Find all SMV files in output directory
        smv_files = []
        for sim_dir in simulation_output_dirs:
            smv_files.extend(list(Path(sim_dir).glob("*.smv")))
        
        if len(smv_files) == 0:
            print("No SMV files found to convert")
            print(f"Looking in: {simulation_output_dirs}")
            return
        
        print(f"Found {len(smv_files)} SMV files")
        
        # Create CONVERT.DES file
        convert_des = self.project_dir / "CONVERT.DES"
        create_convert_des_file(str(convert_des))
        
        # Convert each SMV file
        converted_count = 0
        
        for smv_file in smv_files:
            # Determine output path (maintain directory structure)
            # The relative path should be from the project_dir, not input_dir, as smv_file is now in simulation_output_dir
            rel_path = smv_file.relative_to(self.project_dir)
            output_fdb = self.fdb_dir / rel_path.with_suffix(".fdb")
            output_fdb.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                converter = SMVtoFDBConverter(str(smv_file), str(output_fdb))
                if converter.convert():
                    converted_count += 1
            except Exception as e:
                print(f"Error converting {smv_file.name}: {e}")
        
        print(f"\n✓ Converted {converted_count}/{len(smv_files)} files to FDB format")
        self._log_event("fdb_conversion", {
            "total": len(smv_files),
            "converted": converted_count
        })
    
    def run_complete_workflow(self):
        """Run the complete FDS workflow"""
        
        self._log_event("workflow_start", {"timestamp": datetime.now().isoformat()})
        
        # 1. Define scenarios
        self.define_scenarios()
        
        # 2. Generate FDS input files
        input_files = self.generate_inputs()
        
        # 3. Run FDS simulations
        _, simulation_output_dirs = self.run_simulations(input_files)
        
        # 4. Convert SMV to FDB
        self.convert_to_fdb(simulation_output_dirs)
        
        self._log_event("workflow_end", {"timestamp": datetime.now().isoformat()})
        
        print("\nComplete workflow finished.")
        
    def _log_event(self, event_type: str, data: Dict):
        self.workflow_log.append({
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        })
        
    def save_workflow_log(self, filename: str = "workflow_log.json"):
        log_path = self.project_dir / filename
        with open(log_path, "w") as f:
            json.dump(self.workflow_log, f, indent=4)
        print(f"Workflow log saved to {log_path}")


if __name__ == "__main__":
    # Example Usage:
    project_root = Path("./fds_project")
    project_root.mkdir(exist_ok=True)

    workflow = FDSWorkflow(str(project_root))
    workflow.run_complete_workflow()
    workflow.save_workflow_log()


# """
# FDS Workflow Orchestrator
# Complete workflow from FDS input generation to FDB conversion
# """

# import os
# import json
# from pathlib import Path
# from typing import Dict, List, Optional
# from datetime import datetime

# try:
#     from fds_generator import FDSInputGenerator, TunnelGeometry, FireScenario
# except ImportError:
#     from .fds_generator import FDSInputGenerator, TunnelGeometry, FireScenario

# try:
#     from fds_runner import FDSRunner, create_batch_script
# except ImportError:
#     from .fds_runner import FDSRunner, create_batch_script

# try:
#     from smv_to_fdb_converter import SMVtoFDBConverter, convert_directory, create_convert_des_file
# except ImportError:
#     from .smv_to_fdb_converter import SMVtoFDBConverter, convert_directory, create_convert_des_file


# class FDSWorkflow:
#     """Complete FDS workflow manager"""
    
#     def __init__(self, project_dir: str, fds_executable: str = "fds"):
#         """
#         Initialize workflow
        
#         Args:
#             project_dir: Base directory for the project
#             fds_executable: Path to FDS executable
#         """
#         self.project_dir = Path(project_dir)
#         self.fds_executable = fds_executable
        
#         # Create directory structure
#         self.input_dir = self.project_dir / "fds_inputs"
#         self.output_dir = self.project_dir / "fds_outputs"
#         self.fdb_dir = self.project_dir / "fdb_files"
#         self.log_dir = self.project_dir / "logs"
        
#         for dir_path in [self.input_dir, self.output_dir, self.fdb_dir, self.log_dir]:
#             dir_path.mkdir(parents=True, exist_ok=True)
        
#         # Initialize components
#         self.tunnel = TunnelGeometry()
#         self.generator = FDSInputGenerator(self.tunnel)
#         self.runner = FDSRunner(fds_executable)
        
#         # Workflow state
#         self.scenarios = []
#         self.workflow_log = []
    
#     def define_scenarios(self, 
#                         hrr_types: List[tuple] = None,
#                         fire_positions: List[float] = None,
#                         flashover_times: List[int] = None,
#                         traffic_conditions: List[str] = None,
#                         ventilation_conditions: List[str] = None):
#         """
#         Define fire scenarios to simulate
        
#         Args:
#             hrr_types: List of (type_code, hrr_value) tuples
#             fire_positions: List of fire positions along tunnel (meters)
#             flashover_times: List of flashover times (seconds)
#             traffic_conditions: List of traffic conditions
#             ventilation_conditions: List of ventilation conditions
#         """
        
#         # Default values
#         if hrr_types is None:
#             hrr_types = [("020", 20000), ("030", 30000), ("100", 100000)]
        
#         if fire_positions is None:
#             fire_positions = [500, 750, 1000, 1250, 1500, 1750]
        
#         if flashover_times is None:
#             flashover_times = [450]  # Use only medium growth
        
#         if traffic_conditions is None:
#             traffic_conditions = ["Normal", "Congested"]
        
#         if ventilation_conditions is None:
#             ventilation_conditions = ["NVC", "NV0", "FV0"]
        
#         # Generate all combinations
#         self.scenarios = []
        
#         for hrr_type, hrr_value in hrr_types:
#             for fire_pos in fire_positions:
#                 for flashover in flashover_times:
#                     for traffic in traffic_conditions:
#                         for vent in ventilation_conditions:
#                             scenario = FireScenario(
#                                 hrr_type=hrr_type,
#                                 hrr_value=hrr_value,
#                                 fire_position=fire_pos,
#                                 flashover_time=flashover,
#                                 traffic_condition=traffic,
#                                 ventilation_condition=vent
#                             )
                            
#                             self.scenarios.append(scenario)
        
#         print(f"Defined {len(self.scenarios)} fire scenarios")
#         self._log_event("scenarios_defined", {"count": len(self.scenarios)})
    
#     def generate_inputs(self):
#         """Generate FDS input files for all scenarios"""
        
#         print(f"\n{'='*60}")
#         print("Generating FDS Input Files")
#         print(f"{'='*60}\n")
        
#         generated_files = []
        
#         for i, scenario in enumerate(self.scenarios, 1):
#             # Create filename
#             pos_index = [500, 750, 1000, 1250, 1500, 1750].index(scenario.fire_position) + 1
#             filename = (f"{scenario.hrr_type}_{scenario.traffic_condition[0]}_"
#                        f"{scenario.ventilation_condition}_P{pos_index}_F{scenario.flashover_time}.fds")
            
#             # Create subdirectory structure
#             subdir = self.input_dir / scenario.hrr_type / scenario.traffic_condition / scenario.ventilation_condition
#             output_path = subdir / filename
            
#             # Generate input file
#             try:
#                 self.generator.generate_fds_input(scenario, str(output_path))
#                 generated_files.append(str(output_path))
                
#                 if i % 10 == 0:
#                     print(f"  Generated {i}/{len(self.scenarios)} files...")
                
#             except Exception as e:
#                 print(f"Error generating {filename}: {e}")
        
#         print(f"\n✓ Generated {len(generated_files)} FDS input files")
#         self._log_event("inputs_generated", {"count": len(generated_files)})
        
#         return generated_files
    
#     def run_simulations(self, input_files: List[str] = None, 
#                        max_parallel: int = 1,
#                        create_batch: bool = True):
#         """
#         Run FDS simulations
        
#         Args:
#             input_files: List of input files to run (default: all generated)
#             max_parallel: Maximum parallel simulations
#             create_batch: Whether to create batch script
#         """
        
#         if input_files is None:
#             input_files = list(self.input_dir.glob("**/*.fds"))
#             input_files = [str(f) for f in input_files]
        
#         if len(input_files) == 0:
#             print("No input files to run")
#             return
        
#         print(f"\n{'='*60}")
#         print("Running FDS Simulations")
#         print(f"{'='*60}\n")
#         print(f"Total simulations: {len(input_files)}")
        
#         # Create batch script
#         if create_batch:
#             batch_file = self.project_dir / "run_all_simulations.bat"
#             create_batch_script(input_files, str(batch_file))
#             print(f"\nBatch script created: {batch_file}")
#             print("You can run simulations manually using this script")
        
#         # Check if FDS is available
#         if not self.runner.check_fds_available():
#             print("\n⚠ FDS executable not found")
#             print(f"  Looking for: {self.fds_executable}")
#             print("  Please install FDS or specify correct path")
#             print("  You can use the batch script to run simulations manually")
#             return
        
#         # Run simulations
#         # Pass log_dir to runner for each simulation
#         results = []
#         if max_parallel == 1:
#             for input_file in input_files:
#                 result = self.runner.run_simulation(input_file, log_dir=str(self.log_dir))
#                 results.append(result)
#         else:
#             # Parallel execution not implemented, fallback to sequential
#             for input_file in input_files:
#                 result = self.runner.run_simulation(input_file, log_dir=str(self.log_dir))
#                 results.append(result)
        
#         successful = sum(1 for r in results if r.returncode == 0)
#         self._log_event("simulations_run", {
#             "total": len(results),
#             "successful": successful,
#             "failed": len(results) - successful
#         })
    
#     def convert_to_fdb(self):
#         """Convert SMV output files to FDB format"""
        
#         print(f"\n{'='*60}")
#         print("Converting SMV to FDB Format")
#         print(f"{'='*60}\n")
        
#         # Find all SMV files in output directory
#         smv_files = list(self.output_dir.glob("**/*.smv"))
        
#         if len(smv_files) == 0:
#             print("No SMV files found to convert")
#             print(f"Looking in: {self.output_dir}")
#             return
        
#         print(f"Found {len(smv_files)} SMV files")
        
#         # Create CONVERT.DES file
#         convert_des = self.project_dir / "CONVERT.DES"
#         create_convert_des_file(str(convert_des))
        
#         # Convert each SMV file
#         converted_count = 0
        
#         for smv_file in smv_files:
#             # Determine output path (maintain directory structure)
#             rel_path = smv_file.relative_to(self.output_dir)
#             output_fdb = self.fdb_dir / rel_path.with_suffix('.fdb')
#             output_fdb.parent.mkdir(parents=True, exist_ok=True)
            
#             try:
#                 converter = SMVtoFDBConverter(str(smv_file), str(output_fdb))
#                 if converter.convert():
#                     converted_count += 1
#             except Exception as e:
#                 print(f"Error converting {smv_file.name}: {e}")
        
#         print(f"\n✓ Converted {converted_count}/{len(smv_files)} files to FDB format")
#         self._log_event("fdb_conversion", {
#             "total": len(smv_files),
#             "converted": converted_count
#         })
    
#     def run_complete_workflow(self):
#         """Run complete workflow from input generation to FDB conversion"""
        
#         print(f"\n{'='*70}")
#         print("FDS WORKFLOW - COMPLETE EXECUTION")
#         print(f"{'='*70}")
#         print(f"Project Directory: {self.project_dir}")
#         print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#         print(f"{'='*70}\n")
        
#         # Step 1: Define scenarios
#         self.define_scenarios()
        
#         # Step 2: Generate input files
#         input_files = self.generate_inputs()
        
#         # Step 3: Run simulations
#         self.run_simulations(input_files, create_batch=True)
        
#         # Step 4: Convert to FDB
#         self.convert_to_fdb()
        
#         # Save workflow log
#         self._save_workflow_log()
        
#         print(f"\n{'='*70}")
#         print("WORKFLOW COMPLETE")
#         print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#         print(f"{'='*70}\n")
        
#         # Print summary
#         self._print_summary()
    
#     def _log_event(self, event_type: str, data: Dict):
#         """Log workflow event"""
#         self.workflow_log.append({
#             "timestamp": datetime.now().isoformat(),
#             "event": event_type,
#             "data": data
#         })
    
#     def _save_workflow_log(self):
#         """Save workflow log to file"""
#         log_file = self.log_dir / f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
#         with open(log_file, 'w') as f:
#             json.dump({
#                 "project_dir": str(self.project_dir),
#                 "fds_executable": self.fds_executable,
#                 "scenario_count": len(self.scenarios),
#                 "events": self.workflow_log
#             }, f, indent=2)
        
#         print(f"\nWorkflow log saved: {log_file}")
    
#     def _print_summary(self):
#         """Print workflow summary"""
#         print("\n📊 WORKFLOW SUMMARY")
#         print("─" * 70)
        
#         for event in self.workflow_log:
#             event_type = event['event']
#             data = event['data']
            
#             if event_type == "scenarios_defined":
#                 print(f"  Scenarios Defined: {data['count']}")
#             elif event_type == "inputs_generated":
#                 print(f"  Input Files Generated: {data['count']}")
#             elif event_type == "simulations_run":
#                 print(f"  Simulations Run: {data['total']} (✓ {data['successful']}, ✗ {data['failed']})")
#             elif event_type == "fdb_conversion":
#                 print(f"  FDB Files Created: {data['converted']}/{data['total']}")
        
#         print("─" * 70)
#         print(f"\n📁 Output Locations:")
#         print(f"  FDS Inputs: {self.input_dir}")
#         print(f"  FDS Outputs: {self.output_dir}")
#         print(f"  FDB Files: {self.fdb_dir}")
#         print(f"  Logs: {self.log_dir}")


# def main():
#     """Main entry point"""
    
#     # Configuration
#     project_dir = "./qra_fds_project"
#     fds_executable = "fds"  # Change to full path if not in PATH
    
#     # Create workflow
#     workflow = FDSWorkflow(project_dir, fds_executable)
    
#     # Define scenarios (customize as needed)
#     workflow.define_scenarios(
#         hrr_types=[("020", 20000), ("030", 30000)],  # Start with 2 HRR levels for testing
#         fire_positions=[1000],  # Single position for testing
#         flashover_times=[450],
#         traffic_conditions=["Normal"],
#         ventilation_conditions=["NVC"]
#     )
    
#     # Run workflow
#     workflow.run_complete_workflow()


# if __name__ == "__main__":
#     main()



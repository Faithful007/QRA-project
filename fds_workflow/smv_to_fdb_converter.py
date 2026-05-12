"""
SMV to FDB Converter
Converts FDS Smokeview output files to FDB format for EVC simulation
"""

import os
import struct
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import csv


class SMVReader:
    """Reader for FDS Smokeview (.smv) files"""
    
    def __init__(self, smv_file: str):
        """
        Initialize SMV reader
        
        Args:
            smv_file: Path to .smv file
        """
        self.smv_file = Path(smv_file)
        self.base_dir = self.smv_file.parent
        self.chid = self.smv_file.stem
        
        self.grid_info = {}
        self.slice_files = []
        self.device_files = []
        
        self._parse_smv()
    
    def _parse_smv(self):
        """Parse SMV file to extract metadata"""
        
        with open(self.smv_file, 'r', errors='ignore') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Parse grid information
            if line.startswith('GRID'):
                parts = line.split()
                if len(parts) >= 7:
                    self.grid_info = {
                        'nx': int(parts[1]),
                        'ny': int(parts[2]),
                        'nz': int(parts[3])
                    }
            
            # Parse slice file information
            if line.startswith('SLCF'):
                # Next line contains filename
                if i + 1 < len(lines):
                    filename = lines[i + 1].strip()
                    self.slice_files.append(filename)
            
            # Parse device file information
            if line.startswith('CSVF'):
                if i + 1 < len(lines):
                    filename = lines[i + 1].strip()
                    self.device_files.append(filename)
    
    def read_slice_file(self, slice_file: str) -> Optional[np.ndarray]:
        """
        Read FDS slice file (binary format)
        
        Args:
            slice_file: Path to slice file
            
        Returns:
            Numpy array with slice data or None if error
        """
        
        slice_path = self.base_dir / slice_file
        
        if not slice_path.exists():
            print(f"Slice file not found: {slice_path}")
            return None
        
        try:
            with open(slice_path, 'rb') as f:
                # FDS slice files are in Fortran unformatted binary
                # Format varies by FDS version - this is a simplified reader
                
                # Read header
                data = f.read()
                
                # This is a placeholder - actual implementation would need
                # to parse the specific FDS binary format
                print(f"Read {len(data)} bytes from {slice_file}")
                
                return None  # Placeholder
                
        except Exception as e:
            print(f"Error reading slice file: {e}")
            return None
    
    def read_device_file(self, device_file: str) -> Optional[Dict]:
        """
        Read FDS device output file (CSV format)
        
        Args:
            device_file: Path to device CSV file
            
        Returns:
            Dictionary with device data
        """
        
        device_path = self.base_dir / device_file
        
        if not device_path.exists():
            print(f"Device file not found: {device_path}")
            return None
        
        try:
            data = {'time': [], 'devices': {}}
            
            with open(device_path, 'r') as f:
                reader = csv.reader(f)
                
                # Read header
                headers = next(reader)
                headers = [h.strip() for h in headers]
                
                # Initialize device data
                for header in headers[1:]:  # Skip time column
                    data['devices'][header] = []
                
                # Read data
                for row in reader:
                    if len(row) > 0:
                        data['time'].append(float(row[0]))
                        for i, header in enumerate(headers[1:], 1):
                            if i < len(row):
                                try:
                                    data['devices'][header].append(float(row[i]))
                                except:
                                    data['devices'][header].append(0.0)
            
            return data
            
        except Exception as e:
            print(f"Error reading device file: {e}")
            return None


class FDBWriter:
    """Writer for FDB (Fire Database) files"""
    
    def __init__(self, output_file: str):
        """
        Initialize FDB writer
        
        Args:
            output_file: Path to output .fdb file
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
    
    def write_fdb(self, data: Dict, grid_info: Dict):
        """
        Write FDB file
        
        Args:
            data: Dictionary containing time-series data
            grid_info: Grid information (nx, ny, nz, dx, dy, dz)
        """
        
        with open(self.output_file, 'wb') as f:
            # FDB Header
            # This is a custom format - structure based on QRA system requirements
            
            # Write magic number
            f.write(b'FDB1')  # File format identifier
            
            # Write version
            f.write(struct.pack('i', 1))  # Version 1
            
            # Write grid dimensions
            f.write(struct.pack('iii', grid_info['nx'], grid_info['ny'], grid_info['nz']))
            
            # Write grid spacing
            f.write(struct.pack('fff', grid_info['dx'], grid_info['dy'], grid_info['dz']))
            
            # Write number of time steps
            n_times = len(data['time'])
            f.write(struct.pack('i', n_times))
            
            # Write time array
            for t in data['time']:
                f.write(struct.pack('f', t))
            
            # Write data fields
            # Expected fields: temperature, CO, CO2, O2, visibility
            fields = ['temperature', 'co', 'co2', 'o2', 'visibility']
            
            for field in fields:
                if field in data:
                    field_data = data[field]
                    
                    # Write field identifier
                    f.write(field.encode('utf-8').ljust(32, b'\x00'))
                    
                    # Write field data (time x space)
                    for time_step in field_data:
                        # Flatten spatial data
                        flat_data = np.array(time_step).flatten()
                        for value in flat_data:
                            f.write(struct.pack('f', value))
        
        print(f"FDB file written: {self.output_file}")


class SMVtoFDBConverter:
    """Converter from SMV format to FDB format"""
    
    def __init__(self, smv_file: str, output_fdb: str):
        """
        Initialize converter
        
        Args:
            smv_file: Path to input .smv file
            output_fdb: Path to output .fdb file
        """
        self.smv_reader = SMVReader(smv_file)
        self.fdb_writer = FDBWriter(output_fdb)
    
    def convert(self, sample_height: float = 1.7):
        """
        Convert SMV data to FDB format
        
        Args:
            sample_height: Height at which to sample data (meters)
        """
        
        print(f"Converting {self.smv_reader.smv_file.name} to FDB format...")
        
        # Read device data (simpler than slice files)
        device_data = None
        for device_file in self.smv_reader.device_files:
            if 'devc' in device_file.lower():
                device_data = self.smv_reader.read_device_file(device_file)
                break
        
        if device_data is None:
            print("No device data found")
            return False
        
        # Prepare data for FDB
        fdb_data = {
            'time': device_data['time'],
            'temperature': [],
            'co': [],
            'co2': [],
            'o2': [],
            'visibility': []
        }
        
        # Extract relevant device data
        # This is simplified - actual implementation would need to map
        # device IDs to physical quantities
        
        for device_name, device_values in device_data['devices'].items():
            device_lower = device_name.lower()
            
            if 'temp' in device_lower:
                fdb_data['temperature'] = device_values
            elif 'co' in device_lower and 'co2' not in device_lower:
                fdb_data['co'] = device_values
            elif 'co2' in device_lower:
                fdb_data['co2'] = device_values
            elif 'o2' in device_lower or 'oxygen' in device_lower:
                fdb_data['o2'] = device_values
            elif 'vis' in device_lower:
                fdb_data['visibility'] = device_values
        
        # Fill missing data with defaults
        n_times = len(fdb_data['time'])
        for field in ['temperature', 'co', 'co2', 'o2', 'visibility']:
            if len(fdb_data[field]) == 0:
                fdb_data[field] = [0.0] * n_times
        
        # Grid info
        grid_info = {
            'nx': self.smv_reader.grid_info.get('nx', 100),
            'ny': self.smv_reader.grid_info.get('ny', 36),
            'nz': self.smv_reader.grid_info.get('nz', 26),
            'dx': 0.8,  # Default values
            'dy': 0.4,
            'dz': 0.57
        }
        
        # Write FDB file
        self.fdb_writer.write_fdb(fdb_data, grid_info)
        
        print("Conversion complete")
        return True


def convert_directory(input_dir: str, output_dir: str):
    """
    Convert all SMV files in a directory to FDB format
    
    Args:
        input_dir: Directory containing SMV files
        output_dir: Directory for output FDB files
    """
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    smv_files = list(input_path.glob("*.smv"))
    
    if len(smv_files) == 0:
        print(f"No SMV files found in {input_dir}")
        return
    
    print(f"Found {len(smv_files)} SMV files")
    
    for smv_file in smv_files:
        output_fdb = output_path / f"{smv_file.stem}.fdb"
        
        try:
            converter = SMVtoFDBConverter(str(smv_file), str(output_fdb))
            converter.convert()
        except Exception as e:
            print(f"Error converting {smv_file.name}: {e}")


def create_convert_des_file(output_file: str = "CONVERT.DES"):
    """
    Create CONVERT.DES configuration file for FDSCFDB.EXE
    
    This file is used by the original FDSCFDB.EXE utility
    
    Args:
        output_file: Path to output CONVERT.DES file
    """
    
    with open(output_file, 'w') as f:
        f.write("# FDSCFDB Configuration File\n")
        f.write("# Converts FDS output to FDB format\n\n")
        
        f.write("# Input file (SMV)\n")
        f.write("INPUT_FILE = *.smv\n\n")
        
        f.write("# Output file (FDB)\n")
        f.write("OUTPUT_FILE = *.fdb\n\n")
        
        f.write("# Sampling height (meters)\n")
        f.write("SAMPLE_HEIGHT = 1.7\n\n")
        
        f.write("# Variables to extract\n")
        f.write("VARIABLES = TEMPERATURE, CO, CO2, O2, VISIBILITY\n\n")
        
        f.write("# Time interval (seconds)\n")
        f.write("TIME_INTERVAL = 1.0\n")
    
    print(f"CONVERT.DES file created: {output_file}")


if __name__ == "__main__":
    # Example usage
    
    # Create CONVERT.DES file
    create_convert_des_file()
    
    # Example: Convert a single SMV file
    # converter = SMVtoFDBConverter("test_020_N_NVC.smv", "test_020_N_NVC.fdb")
    # converter.convert()
    
    # Example: Convert all SMV files in a directory
    # convert_directory("./fds_outputs", "./fdb_outputs")


# """
# SMV to FDB Converter
# Converts FDS Smokeview output files to FDB format for EVC simulation
# """

# import os
# import struct
# import numpy as np
# from pathlib import Path
# from typing import Dict, List, Tuple, Optional
# import csv


# class SMVReader:
#     """Reader for FDS Smokeview (.smv) files"""
    
#     def __init__(self, smv_file: str):
#         """
#         Initialize SMV reader
        
#         Args:
#             smv_file: Path to .smv file
#         """
#         self.smv_file = Path(smv_file)
#         self.base_dir = self.smv_file.parent
#         self.chid = self.smv_file.stem
        
#         self.grid_info = {}
#         self.slice_files = []
#         self.device_files = []
        
#         self._parse_smv()
    
#     def _parse_smv(self):
#         """Parse SMV file to extract metadata"""
        
#         with open(self.smv_file, 'r', errors='ignore') as f:
#             lines = f.readlines()
        
#         for i, line in enumerate(lines):
#             line = line.strip()
            
#             # Parse grid information
#             if line.startswith('GRID'):
#                 parts = line.split()
#                 if len(parts) >= 7:
#                     self.grid_info = {
#                         'nx': int(parts[1]),
#                         'ny': int(parts[2]),
#                         'nz': int(parts[3])
#                     }
            
#             # Parse slice file information
#             if line.startswith('SLCF'):
#                 # Next line contains filename
#                 if i + 1 < len(lines):
#                     filename = lines[i + 1].strip()
#                     self.slice_files.append(filename)
            
#             # Parse device file information
#             if line.startswith('CSVF'):
#                 if i + 1 < len(lines):
#                     filename = lines[i + 1].strip()
#                     self.device_files.append(filename)
    
#     def read_slice_file(self, slice_file: str) -> Optional[np.ndarray]:
#         """
#         Read FDS slice file (binary format)
        
#         Args:
#             slice_file: Path to slice file
            
#         Returns:
#             Numpy array with slice data or None if error
#         """
        
#         slice_path = self.base_dir / slice_file
        
#         if not slice_path.exists():
#             print(f"Slice file not found: {slice_path}")
#             return None
        
#         try:
#             with open(slice_path, 'rb') as f:
#                 # FDS slice files are in Fortran unformatted binary
#                 # Format varies by FDS version - this is a simplified reader
                
#                 # Read header
#                 data = f.read()
                
#                 # This is a placeholder - actual implementation would need
#                 # to parse the specific FDS binary format
#                 print(f"Read {len(data)} bytes from {slice_file}")
                
#                 return None  # Placeholder
                
#         except Exception as e:
#             print(f"Error reading slice file: {e}")
#             return None
    
#     def read_device_file(self, device_file: str) -> Optional[Dict]:
#         """
#         Read FDS device output file (CSV format)
        
#         Args:
#             device_file: Path to device CSV file
            
#         Returns:
#             Dictionary with device data
#         """
        
#         device_path = self.base_dir / device_file
        
#         if not device_path.exists():
#             print(f"Device file not found: {device_path}")
#             return None
        
#         try:
#             data = {'time': [], 'devices': {}}
            
#             with open(device_path, 'r') as f:
#                 reader = csv.reader(f)
                
#                 # Read header
#                 headers = next(reader)
#                 headers = [h.strip() for h in headers]
                
#                 # Initialize device data
#                 for header in headers[1:]:  # Skip time column
#                     data['devices'][header] = []
                
#                 # Read data
#                 for row in reader:
#                     if len(row) > 0:
#                         data['time'].append(float(row[0]))
#                         for i, header in enumerate(headers[1:], 1):
#                             if i < len(row):
#                                 try:
#                                     data['devices'][header].append(float(row[i]))
#                                 except:
#                                     data['devices'][header].append(0.0)
            
#             return data
            
#         except Exception as e:
#             print(f"Error reading device file: {e}")
#             return None


# class FDBWriter:
#     """Writer for FDB (Fire Database) files"""
    
#     def __init__(self, output_file: str):
#         """
#         Initialize FDB writer
        
#         Args:
#             output_file: Path to output .fdb file
#         """
#         self.output_file = Path(output_file)
#         self.output_file.parent.mkdir(parents=True, exist_ok=True)
    
#     def write_fdb(self, data: Dict, grid_info: Dict):
#         """
#         Write FDB file
        
#         Args:
#             data: Dictionary containing time-series data
#             grid_info: Grid information (nx, ny, nz, dx, dy, dz)
#         """
        
#         with open(self.output_file, 'wb') as f:
#             # FDB Header
#             # This is a custom format - structure based on QRA system requirements
            
#             # Write magic number
#             f.write(b'FDB1')  # File format identifier
            
#             # Write version
#             f.write(struct.pack('i', 1))  # Version 1
            
#             # Write grid dimensions
#             f.write(struct.pack('iii', grid_info['nx'], grid_info['ny'], grid_info['nz']))
            
#             # Write grid spacing
#             f.write(struct.pack('fff', grid_info['dx'], grid_info['dy'], grid_info['dz']))
            
#             # Write number of time steps
#             n_times = len(data['time'])
#             f.write(struct.pack('i', n_times))
            
#             # Write time array
#             for t in data['time']:
#                 f.write(struct.pack('f', t))
            
#             # Write data fields
#             # Expected fields: temperature, CO, CO2, O2, visibility
#             fields = ['temperature', 'co', 'co2', 'o2', 'visibility']
            
#             for field in fields:
#                 if field in data:
#                     field_data = data[field]
                    
#                     # Write field identifier
#                     f.write(field.encode('utf-8').ljust(32, b'\x00'))
                    
#                     # Write field data (time x space)
#                     for time_step in field_data:
#                         # Flatten spatial data
#                         flat_data = np.array(time_step).flatten()
#                         for value in flat_data:
#                             f.write(struct.pack('f', value))
        
#         print(f"FDB file written: {self.output_file}")


# class SMVtoFDBConverter:
#     """Converter from SMV format to FDB format"""
    
#     def __init__(self, smv_file: str, output_fdb: str):
#         """
#         Initialize converter
        
#         Args:
#             smv_file: Path to input .smv file
#             output_fdb: Path to output .fdb file
#         """
#         self.smv_reader = SMVReader(smv_file)
#         self.fdb_writer = FDBWriter(output_fdb)
    
#     def convert(self, sample_height: float = 1.7):
#         """
#         Convert SMV data to FDB format
        
#         Args:
#             sample_height: Height at which to sample data (meters)
#         """
        
#         print(f"Converting {self.smv_reader.smv_file.name} to FDB format...")
        
#         # Read device data (simpler than slice files)
#         device_data = None
#         for device_file in self.smv_reader.device_files:
#             if 'devc' in device_file.lower():
#                 device_data = self.smv_reader.read_device_file(device_file)
#                 break
        
#         if device_data is None:
#             print("No device data found")
#             return False
        
#         # Prepare data for FDB
#         fdb_data = {
#             'time': device_data['time'],
#             'temperature': [],
#             'co': [],
#             'co2': [],
#             'o2': [],
#             'visibility': []
#         }
        
#         # Extract relevant device data
#         # This is simplified - actual implementation would need to map
#         # device IDs to physical quantities
        
#         for device_name, device_values in device_data['devices'].items():
#             device_lower = device_name.lower()
            
#             if 'temp' in device_lower:
#                 fdb_data['temperature'] = device_values
#             elif 'co' in device_lower and 'co2' not in device_lower:
#                 fdb_data['co'] = device_values
#             elif 'co2' in device_lower:
#                 fdb_data['co2'] = device_values
#             elif 'o2' in device_lower or 'oxygen' in device_lower:
#                 fdb_data['o2'] = device_values
#             elif 'vis' in device_lower:
#                 fdb_data['visibility'] = device_values
        
#         # Fill missing data with defaults
#         n_times = len(fdb_data['time'])
#         for field in ['temperature', 'co', 'co2', 'o2', 'visibility']:
#             if len(fdb_data[field]) == 0:
#                 fdb_data[field] = [0.0] * n_times
        
#         # Grid info
#         grid_info = {
#             'nx': self.smv_reader.grid_info.get('nx', 100),
#             'ny': self.smv_reader.grid_info.get('ny', 36),
#             'nz': self.smv_reader.grid_info.get('nz', 26),
#             'dx': 0.8,  # Default values
#             'dy': 0.4,
#             'dz': 0.57
#         }
        
#         # Write FDB file
#         self.fdb_writer.write_fdb(fdb_data, grid_info)
        
#         print("Conversion complete")
#         return True


# def convert_directory(input_dir: str, output_dir: str):
#     """
#     Convert all SMV files in a directory to FDB format
    
#     Args:
#         input_dir: Directory containing SMV files
#         output_dir: Directory for output FDB files
#     """
    
#     input_path = Path(input_dir)
#     output_path = Path(output_dir)
#     output_path.mkdir(parents=True, exist_ok=True)
    
#     smv_files = list(input_path.glob("*.smv"))
    
#     if len(smv_files) == 0:
#         print(f"No SMV files found in {input_dir}")
#         return
    
#     print(f"Found {len(smv_files)} SMV files")
    
#     for smv_file in smv_files:
#         output_fdb = output_path / f"{smv_file.stem}.fdb"
        
#         try:
#             converter = SMVtoFDBConverter(str(smv_file), str(output_fdb))
#             converter.convert()
#         except Exception as e:
#             print(f"Error converting {smv_file.name}: {e}")


# def create_convert_des_file(output_file: str = "CONVERT.DES"):
#     """
#     Create CONVERT.DES configuration file for FDSCFDB.EXE
    
#     This file is used by the original FDSCFDB.EXE utility
    
#     Args:
#         output_file: Path to output CONVERT.DES file
#     """
    
#     with open(output_file, 'w') as f:
#         f.write("# FDSCFDB Configuration File\n")
#         f.write("# Converts FDS output to FDB format\n\n")
        
#         f.write("# Input file (SMV)\n")
#         f.write("INPUT_FILE = *.smv\n\n")
        
#         f.write("# Output file (FDB)\n")
#         f.write("OUTPUT_FILE = *.fdb\n\n")
        
#         f.write("# Sampling height (meters)\n")
#         f.write("SAMPLE_HEIGHT = 1.7\n\n")
        
#         f.write("# Variables to extract\n")
#         f.write("VARIABLES = TEMPERATURE, CO, CO2, O2, VISIBILITY\n\n")
        
#         f.write("# Time interval (seconds)\n")
#         f.write("TIME_INTERVAL = 1.0\n")
    
#     print(f"CONVERT.DES file created: {output_file}")


# if __name__ == "__main__":
#     # Example usage
    
#     # Create CONVERT.DES file
#     create_convert_des_file()
    
#     # Example: Convert a single SMV file
#     # converter = SMVtoFDBConverter("test_020_N_NVC.smv", "test_020_N_NVC.fdb")
#     # converter.convert()
    
#     # Example: Convert all SMV files in a directory
#     # convert_directory("./fds_outputs", "./fdb_outputs")

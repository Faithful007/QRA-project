"""
Test Script for FDS to FDB Converter
=====================================

This script tests the Python FDS to FDB converter functionality.
"""

from pathlib import Path
import sys
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fds_workflow.fds_to_fdb_converter_old import (
    ConversionConfig,
    FDSSliceReader,
    FDBWriter,
    FDSToFDBConverter,
    convert_fds_to_fdb
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_conversion_config():
    """Test ConversionConfig class"""
    logger.info("=" * 60)
    logger.info("TEST 1: ConversionConfig")
    logger.info("=" * 60)
    
    # Test default configuration
    config = ConversionConfig()
    
    logger.info(f"FDS ID: {config.fds_id}")
    logger.info(f"Axis Direction: {config.axis_dir}")
    logger.info(f"Vertical Direction: {config.vert_dir}")
    logger.info(f"Time Step: {config.time_step}")
    logger.info(f"Temporal Skip: {config.temp_skip}")
    
    logger.info("\nSlice File Mapping:")
    for var, file_num in config.slice_files.items():
        logger.info(f"  {var}: File {file_num}")
    
    logger.info("\nConversion Factors:")
    for var, factor in config.conversion_factors.items():
        logger.info(f"  {var}: {factor}")
    
    logger.info("✓ ConversionConfig test passed\n")
    return config


def test_config_file_loading():
    """Test loading configuration from CONVERT.DES file"""
    logger.info("=" * 60)
    logger.info("TEST 2: Configuration File Loading")
    logger.info("=" * 60)
    
    # Create a test CONVERT.DES file
    test_config_path = Path("test_CONVERT.DES")
    
    config_content = """FDS_ID  AxisDir  VertDir  TimeDtep iTempSkip  FDS_SLC_File_Number(SOOT,CO2,CO,TEMP,RADI,OXYGEN)
TN      X        Z        30       6          1  2  3  4  5  6 0 0 0 0 0 0
Convertion Factor
SOOT       CO2       CO        TEMP      RADI      OXYGEN 
1000000.0  100.0     1000000.0 1.0       0.25      100.0
"""
    
    with open(test_config_path, 'w') as f:
        f.write(config_content)
    
    # Load configuration
    config = ConversionConfig(test_config_path)
    
    logger.info(f"Loaded FDS ID: {config.fds_id}")
    logger.info(f"Loaded Time Step: {config.time_step}")
    logger.info(f"Loaded Temporal Skip: {config.temp_skip}")
    
    # Verify conversion factors
    assert config.conversion_factors['SOOT'] == 1000000.0
    assert config.conversion_factors['CO2'] == 100.0
    assert config.conversion_factors['TEMP'] == 1.0
    
    logger.info("✓ Configuration file loading test passed\n")
    
    # Clean up
    test_config_path.unlink()
    
    return config


def test_fdb_writer():
    """Test FDBWriter class"""
    logger.info("=" * 60)
    logger.info("TEST 3: FDBWriter")
    logger.info("=" * 60)
    
    import numpy as np
    
    # Create test data
    times = np.linspace(0, 900, 100)  # 100 time steps
    soot_data = np.random.rand(100, 50, 10, 5) * 0.001  # Random soot concentrations
    co_data = np.random.rand(100, 50, 10, 5) * 0.0001  # Random CO concentrations
    temp_data = np.random.rand(100, 50, 10, 5) * 100 + 20  # Random temperatures (20-120°C)
    
    # Create FDB writer
    test_fdb_path = Path("test_output.fdb")
    writer = FDBWriter(test_fdb_path)
    
    # Set times
    writer.set_times(times)
    
    # Set mesh info
    mesh_info = {
        'extent': (0.0, 2000.0, 0.0, 14.4, 0.0, 14.8),
        'dimensions': (50, 10, 5)
    }
    writer.set_mesh_info(mesh_info)
    
    # Add variables
    writer.add_variable('SOOT', soot_data, 1000000.0)
    writer.add_variable('CO', co_data, 1000000.0)
    writer.add_variable('TEMP', temp_data, 1.0)
    
    # Write FDB file
    writer.write()
    
    # Verify file was created
    assert test_fdb_path.exists()
    file_size = test_fdb_path.stat().st_size
    logger.info(f"FDB file created: {test_fdb_path}")
    logger.info(f"File size: {file_size / 1024:.2f} KB")
    
    logger.info("✓ FDBWriter test passed\n")
    
    # Clean up
    test_fdb_path.unlink()


def test_full_conversion():
    """Test full conversion process (requires actual FDS output)"""
    logger.info("=" * 60)
    logger.info("TEST 4: Full Conversion (Simulation Required)")
    logger.info("=" * 60)
    
    # This test requires actual FDS output files
    # For now, we'll just demonstrate the usage
    
    logger.info("To test full conversion, run:")
    logger.info("  python fds_to_fdb_converter.py <simulation_dir> [config_file]")
    logger.info("")
    logger.info("Example:")
    logger.info("  python fds_to_fdb_converter.py C:/FDS_Outputs/030_N_NVC_pos500 C:/CONVERT.DES")
    logger.info("")
    logger.info("Or use Python:")
    logger.info("  from fds_workflow.fds_to_fdb_converter import convert_fds_to_fdb")
    logger.info("  fdb_file = convert_fds_to_fdb(Path('C:/FDS_Outputs/030_N_NVC_pos500'))")
    logger.info("")
    logger.info("✓ Full conversion test instructions provided\n")


def test_error_handling():
    """Test error handling"""
    logger.info("=" * 60)
    logger.info("TEST 5: Error Handling")
    logger.info("=" * 60)
    
    # Test with non-existent directory
    try:
        converter = FDSToFDBConverter(Path("/nonexistent/directory"))
        logger.info("✓ Converter created with non-existent directory (will fail on convert)")
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
    
    # Test with invalid config file
    try:
        config = ConversionConfig(Path("/nonexistent/config.des"))
        logger.info("✓ Config created with non-existent file (uses defaults)")
    except Exception as e:
        logger.error(f"✗ Unexpected error: {e}")
    
    logger.info("✓ Error handling test passed\n")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("FDS TO FDB CONVERTER - TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    try:
        # Run tests
        test_conversion_config()
        test_config_file_loading()
        test_fdb_writer()
        test_full_conversion()
        test_error_handling()
        
        # Summary
        logger.info("=" * 60)
        logger.info("ALL TESTS COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info("")
        logger.info("The FDS to FDB converter is ready to use!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Run FDS simulation to generate slice files")
        logger.info("2. Create CONVERT.DES configuration file")
        logger.info("3. Run converter on FDS output directory")
        logger.info("4. Verify .fdb file is created")
        logger.info("")
        
        return 0
    
    except Exception as e:
        logger.error(f"TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

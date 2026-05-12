@echo off
REM ========================================
REM FDS6 Batch Execution Script
REM ========================================
REM This script sets up the FDS6 environment and runs FDS6 simulations
REM Usage: run_fds6.bat <input_file.fds>
REM ========================================

REM Set FDS6 PATH (isolates from FDS5)
set PATH=C:\FDS6\FDS6\bin;C:\FDS6\SMV6;%PATH%

REM Check if input file is provided
if "%~1"=="" (
    echo ERROR: No FDS input file specified
    echo Usage: run_fds6.bat input_file.fds
    exit /b 1
)

REM Check if input file exists
if not exist "%~1" (
    echo ERROR: Input file not found: %~1
    exit /b 1
)

REM Get the full path and filename
set FDS_INPUT=%~1
set FDS_DIR=%~dp1
set FDS_FILE=%~nx1

REM Change to the directory containing the FDS file
cd /d "%FDS_DIR%"

REM Display execution info
echo ========================================
echo FDS6 Simulation Starting
echo ========================================
echo Input file: %FDS_FILE%
echo Directory:  %FDS_DIR%
echo FDS6 Path:  C:\FDS6\FDS6\bin
echo ========================================

REM Try fds_openmp.exe first (parallel processing - faster)
if exist "C:\FDS6\FDS6\bin\fds_openmp.exe" (
    echo Using FDS6 OpenMP (parallel processing)
    "C:\FDS6\FDS6\bin\fds_openmp.exe" "%FDS_FILE%"
    set FDS_EXIT_CODE=%ERRORLEVEL%
) else if exist "C:\FDS6\FDS6\bin\fds.exe" (
    echo Using FDS6 (single core processing)
    "C:\FDS6\FDS6\bin\fds.exe" "%FDS_FILE%"
    set FDS_EXIT_CODE=%ERRORLEVEL%
) else (
    echo ERROR: FDS6 executable not found in C:\FDS6\FDS6\bin
    echo Please check your FDS6 installation
    exit /b 1
)

REM Check exit code
if %FDS_EXIT_CODE% EQU 0 (
    echo ========================================
    echo FDS6 Simulation Completed Successfully
    echo ========================================
) else (
    echo ========================================
    echo FDS6 Simulation Failed (Exit Code: %FDS_EXIT_CODE%)
    echo ========================================
)

exit /b %FDS_EXIT_CODE%

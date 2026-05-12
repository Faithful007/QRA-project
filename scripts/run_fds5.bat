@echo off
setlocal enabledelayedexpansion
REM ========================================
REM FDS5 Batch Execution Script
REM ========================================
REM This script sets up the FDS5 environment and runs FDS5 simulations
REM Usage: run_fds5.bat <input_file.fds>
REM ========================================

REM Set FDS5 PATH (isolates from FDS6)
set PATH=C:\FDS5\bin;%PATH%

REM Check if input file is provided
if "%~1"=="" (
    echo ERROR: No FDS input file specified
    echo Usage: run_fds5.bat input_file.fds
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
echo FDS5 Simulation Starting
echo ========================================
echo Input file: %FDS_FILE%
echo Directory:  %FDS_DIR%
echo FDS5 Path:  C:\FDS5\bin
echo ========================================

REM Build ordered list:  MPI exe first, then non-MPI fallback
set FDS5_MPI=
set FDS5_NOMPI=

if exist "C:\FDS5\bin\fds5_mpi_win_64.exe" set "FDS5_MPI=C:\FDS5\bin\fds5_mpi_win_64.exe"
if exist "C:\FDS5\bin\fds5_win_64.exe"     set "FDS5_NOMPI=C:\FDS5\bin\fds5_win_64.exe"

REM PATH fallback for anything not found above
if "!FDS5_MPI!"=="" (
    for %%F in (fds5_mpi_win_64.exe fds5_mpi.exe) do (
        if "!FDS5_MPI!"=="" for %%P in ("%%~$PATH:F") do if not "%%~P"=="" set "FDS5_MPI=%%~P"
    )
)
if "!FDS5_NOMPI!"=="" (
    for %%F in (fds5_win_64.exe fds5.exe) do (
        if "!FDS5_NOMPI!"=="" for %%P in ("%%~$PATH:F") do if not "%%~P"=="" set "FDS5_NOMPI=%%~P"
    )
)

REM Must have at least one exe
if "!FDS5_MPI!!FDS5_NOMPI!"=="" (
    echo ERROR: FDS5 executable not found
    echo Searched: C:\FDS5\bin  and  PATH
    exit /b 1
)

REM ---------- Try MPI version first ----------
set FDS_EXIT_CODE=1
if not "!FDS5_MPI!"=="" (
    echo Trying MPI: !FDS5_MPI!
    "!FDS5_MPI!" "%FDS_FILE%"
    set FDS_EXIT_CODE=!ERRORLEVEL!
)

REM 0xC0000135 = -1073741515 = DLL NOT FOUND  (MPI runtime missing)
REM 0xC000007B = -1073741189 = BAD IMAGE
REM If MPI failed with a DLL/loader error, fall back to non-MPI
if !FDS_EXIT_CODE! EQU -1073741515 goto :TRY_NOMPI
if !FDS_EXIT_CODE! EQU -1073741189 goto :TRY_NOMPI
REM Also handle unsigned representation on some builds
if !FDS_EXIT_CODE! EQU 3221225781 goto :TRY_NOMPI
if !FDS_EXIT_CODE! EQU 3221225659 goto :TRY_NOMPI
REM If MPI was not found at all, also try non-MPI
if "!FDS5_MPI!"=="" goto :TRY_NOMPI
REM Otherwise we are done (success or real FDS error)
goto :REPORT

:TRY_NOMPI
if "!FDS5_NOMPI!"=="" (
    echo ERROR: MPI version failed ^(missing DLL^) and no non-MPI fallback found.
    echo Install MPICH2 or place fds5_win_64.exe in C:\FDS5\bin
    goto :REPORT
)
echo MPI version unavailable ^(missing DLL^) - falling back to: !FDS5_NOMPI!
"!FDS5_NOMPI!" "%FDS_FILE%"
set FDS_EXIT_CODE=!ERRORLEVEL!

:REPORT
if !FDS_EXIT_CODE! EQU 0 (
    echo ========================================
    echo FDS5 Simulation Completed Successfully
    echo ========================================
) else (
    echo ========================================
    echo FDS5 Simulation Finished ^(Exit Code: !FDS_EXIT_CODE!^)
    echo ========================================
)

exit /b !FDS_EXIT_CODE!

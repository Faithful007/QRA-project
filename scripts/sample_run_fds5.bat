@echo off
REM ========================================
REM FDS5 Batch File for QRA System
REM ========================================
REM This batch file sets up the PATH environment
REM for FDS5 to avoid conflicts with FDS6
REM
REM INSTRUCTIONS:
REM 1. Copy this file to your FDS5 installation directory
REM 2. Edit the paths below to match your installation
REM 3. Configure this file path in QRA System Tab 3
REM ========================================

REM Set FDS5 paths (EDIT THESE PATHS TO MATCH YOUR INSTALLATION)
set FDS5_BIN=C:\FDS5
set FDS5_NIST=C:\Program Files (x86)\NIST\FDS

REM Add FDS5 to PATH (prepend to avoid conflicts)
set PATH=%FDS5_BIN%;%FDS5_NIST%;%PATH%

REM Optional: Set OpenMP threads (adjust based on your CPU cores)
REM set OMP_NUM_THREADS=4

REM Launch command shell with FDS5 environment
cmd

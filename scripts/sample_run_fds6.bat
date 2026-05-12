@echo off
REM ========================================
REM FDS6 Batch File for QRA System
REM ========================================
REM This batch file sets up the PATH environment
REM for FDS6 to avoid conflicts with FDS5
REM
REM INSTRUCTIONS:
REM 1. Copy this file to your FDS6 installation directory
REM 2. Edit the paths below to match your installation
REM 3. Configure this file path in QRA System Tab 3
REM ========================================

REM Set FDS6 paths (EDIT THESE PATHS TO MATCH YOUR INSTALLATION)
set FDS6_BIN=C:\FDS6\FDS6\bin
set FDS6_SMV=C:\FDS6\SMV6

REM Add FDS6 to PATH (prepend to avoid conflicts)
set PATH=%FDS6_BIN%;%FDS6_SMV%;%PATH%

REM Optional: Set OpenMP threads (adjust based on your CPU cores)
REM set OMP_NUM_THREADS=8

REM Optional: Set Intel MPI root
REM set I_MPI_ROOT=%FDS6_BIN%\mpi

REM Launch command shell with FDS6 environment
cmd

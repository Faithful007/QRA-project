@echo off
echo Setting up QRA Program environment...

:: Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python not found. Please install Python 3.8+ and ensure it is added to your PATH.
    echo.
    pause
    exit /b 1
)

:: Create Virtual Environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate Virtual Environment
call venv\Scripts\activate

:: Install Dependencies
echo Installing dependencies...
pip install -r requirements.txt

:: Initialize Database
echo Initializing database...
python main.py --init-db

echo.
echo Setup Complete!
echo You can now run the application using run.bat
echo.
pause

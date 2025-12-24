@echo off
echo Starting QRA Program...

:: Activate Virtual Environment
call venv\Scripts\activate

:: Run the application
python main.py

echo.
echo Application closed.
pause

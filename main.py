import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.ui.main_window import QRACalculatorApp
from src.database.connection import init_db, get_engine, Base

def main():
    """
    Main entry point for the QRA Calculator application.
    """
    # Initialize QApplication
    app = QApplication(sys.argv)

    # Initialize the database
    engine = init_db()
    
    # Import all models to ensure they are registered with Base
    from src.models import ALL_MODELS
    
    # Create tables
    Base.metadata.create_all(engine)

    # Initialize the main application windows (main tab window stays hidden initially)
    main_window = QRACalculatorApp()

    # Start the PyQt event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

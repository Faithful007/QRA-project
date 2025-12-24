from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Use SQLite for simplicity in this implementation
DATABASE_URL = "sqlite:///qra_data.db"

# Base class for declarative class definitions
from .base import Base

def get_engine():
    """Returns the SQLAlchemy engine."""
    return create_engine(DATABASE_URL)

def get_session():
    """Returns a configured SQLAlchemy session."""
    engine = get_engine()

    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """Initializes the database and creates tables."""
    engine = get_engine()

    print(f"Database initialized at {DATABASE_URL}")
    return engine

if __name__ == '__main__':
    init_db()

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

engine = None
SessionLocal = None


def init_db(app: Flask):
    global engine, SessionLocal, db
    
    engine = create_engine(
        app.config['SQLALCHEMY_DATABASE_URI'],
        poolclass=NullPool,
        **app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
    )
    
    SessionLocal = scoped_session(
        sessionmaker(autocommit=False, autoflush=False, bind=engine)
    )
    db = SessionLocal  # For compatibility


def get_db():
    """Get database session"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return SessionLocal()


db = None  # Will be set to SessionLocal after init_db()


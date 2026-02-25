import pytest
from app import create_app
from app.config import Config
from app.db import init_db, get_db
from app.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def app():
    """테스트용 Flask 앱"""
    # 테스트용 설정
    # Use same DB as .env (schema.sql tables + existing tables coexist)
    class TestConfig(Config):
        TESTING = True
        # DB_NAME / SQLALCHEMY_DATABASE_URI inherited from Config (.env)
    
    app = create_app(TestConfig)
    
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """테스트용 클라이언트"""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """테스트용 DB 세션"""
    db = get_db()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


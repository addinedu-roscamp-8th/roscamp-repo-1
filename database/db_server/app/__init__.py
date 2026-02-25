from flask import Flask
from flasgger import Swagger
from app.config import Config
from app.db import db, init_db
from app.routes import health, orders, inventory, analytics, dashboard, orders_ui, ingredients, menu_recipe
from app.routes.kitchmatic import (
    menus_bp,
    ingredients_bp,
    recipes_bp,
    robots_bp,
    inventory_bp as kitchmatic_inventory_bp,
    inventory_txn_bp,
    orders_bp as kitchmatic_orders_bp,
    quality_checks_bp,
)
# Kitchmatic models (schema.sql) - register with Base.metadata for Flasgger/refs
import app.models_kitchmatic  # noqa: F401


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize database (에러가 발생해도 서버는 시작)
    try:
        init_db(app)
    except Exception as e:
        app.logger.warning(f"Database initialization failed: {e}. Server will start but DB operations may fail.")
    
    # Swagger 설정
    swagger_config = {
        "headers": [],
        "specs": [
            {
                "endpoint": "apispec",
                "route": "/apispec.json",
                "rule_filter": lambda rule: True,
                "model_filter": lambda tag: True,
            }
        ],
        "static_url_path": "/flasgger_static",
        "swagger_ui": True,
        "specs_route": "/api-docs"
    }
    
    swagger_template = {
        "swagger": "2.0",
        "info": {
            "title": "Sandwich Server API",
            "description": "음식 판매점의 주문(store_order)과 재고 변동 원장(store_inventory_txn)을 관리하는 REST API",
            "version": "1.0.0",
            "contact": {
                "name": "API Support"
            }
        },
        "basePath": "/",
        "schemes": ["http", "https"],
        "tags": [
            {
                "name": "Health",
                "description": "헬스체크 및 서버 상태"
            },
            {
                "name": "Orders",
                "description": "주문 관리 API"
            },
            {
                "name": "Inventory",
                "description": "재고 이벤트 관리 API"
            },
            {
                "name": "Analytics",
                "description": "분석 및 대시보드 API (TimescaleDB Continuous Aggregates 활용)"
            },
            {
                "name": "Ingredients",
                "description": "원재료 마스터 및 거래 관리 API"
            },
            {
                "name": "Menu Recipe",
                "description": "메뉴 레시피 BOM 관리 API"
            },
            {"name": "Kitchmatic - Menus", "description": "Kitchmatic 메뉴 CRUD (/kitchmatic/menus)"},
            {"name": "Kitchmatic - Ingredients", "description": "Kitchmatic 식재료 CRUD (/kitchmatic/ingredients)"},
            {"name": "Kitchmatic - Recipes", "description": "Kitchmatic 레시피·단계 CRUD (/kitchmatic/recipes)"},
            {"name": "Kitchmatic - Robots", "description": "Kitchmatic 로봇 CRUD (/kitchmatic/robots)"},
            {"name": "Kitchmatic - Inventory", "description": "Kitchmatic 재고·거래 CRUD (/kitchmatic/inventory)"},
            {"name": "Kitchmatic - Orders", "description": "Kitchmatic 주문 CRUD (/kitchmatic/orders)"},
            {"name": "Kitchmatic - Quality", "description": "Kitchmatic 품질검사 CRUD (/kitchmatic/quality-check-results)"},
        ]
    }
    
    Swagger(app, config=swagger_config, template=swagger_template)
    
    # Register blueprints
    app.register_blueprint(health.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(inventory.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(orders_ui.bp)
    app.register_blueprint(ingredients.bp)
    app.register_blueprint(menu_recipe.bp)
    # Kitchmatic (schema.sql) REST API
    app.register_blueprint(menus_bp)
    app.register_blueprint(ingredients_bp)
    app.register_blueprint(recipes_bp)
    app.register_blueprint(robots_bp)
    app.register_blueprint(kitchmatic_inventory_bp)
    app.register_blueprint(inventory_txn_bp)
    app.register_blueprint(kitchmatic_orders_bp)
    app.register_blueprint(quality_checks_bp)

    return app


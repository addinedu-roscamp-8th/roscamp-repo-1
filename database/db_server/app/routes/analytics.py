from flask import Blueprint, request, jsonify
from app.db import get_db
from app.services.analytics_service import AnalyticsService
from datetime import datetime, timedelta
from sqlalchemy import text

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@bp.route('/daily/inventory-change', methods=['GET'])
def daily_inventory_change():
    """
    일별 재고 변동량 조회
    TimescaleDB continuous aggregate (cagg_daily_inventory_change)를 활용하여 일별 재고 변동량을 조회합니다.
    ---
    tags:
      - Analytics
    parameters:
      - in: query
        name: sku
        type: string
        description: "SKU 필터 (선택사항)"
      - in: query
        name: from
        type: string
        format: date-time
        description: "시작 날짜 (ISO 8601, 기본값: 30일 전)"
      - in: query
        name: to
        type: string
        format: date-time
        description: "종료 날짜 (ISO 8601, 기본값: 현재)"
    responses:
      200:
        description: 일별 재고 변동량 데이터
        schema:
          type: object
          properties:
            from_date:
              type: string
              format: date-time
            to_date:
              type: string
              format: date-time
            sku:
              type: string
            data:
              type: array
              items:
                type: object
                properties:
                  day:
                    type: string
                    format: date
                  sku:
                    type: string
                  display_name:
                    type: string
                  unit:
                    type: string
                  net_qty_change:
                    type: number
      500:
        description: 서버 오류
    """
    sku = request.args.get('sku')
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    
    service = AnalyticsService()
    try:
        result = service.get_daily_inventory_change(sku, from_date, to_date)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/daily/sales', methods=['GET'])
def daily_sales():
    """
    일별 판매량 조회
    TimescaleDB continuous aggregate (cagg_daily_sales_qty)를 활용하여 일별 판매량을 조회합니다.
    ---
    tags:
      - Analytics
    parameters:
      - in: query
        name: sku
        type: string
        description: "SKU 필터 (선택사항)"
      - in: query
        name: from
        type: string
        format: date-time
        description: "시작 날짜 (ISO 8601, 기본값: 30일 전)"
      - in: query
        name: to
        type: string
        format: date-time
        description: "종료 날짜 (ISO 8601, 기본값: 현재)"
    responses:
      200:
        description: 일별 판매량 데이터
        schema:
          type: object
          properties:
            from_date:
              type: string
              format: date-time
            to_date:
              type: string
              format: date-time
            sku:
              type: string
            data:
              type: array
              items:
                type: object
                properties:
                  day:
                    type: string
                    format: date
                  sku:
                    type: string
                  display_name:
                    type: string
                  unit:
                    type: string
                  sold_qty:
                    type: number
      500:
        description: 서버 오류
    """
    sku = request.args.get('sku')
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    
    service = AnalyticsService()
    try:
        result = service.get_daily_sales(sku, from_date, to_date)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/top-sales', methods=['GET'])
def top_sales():
    """
    TOP 판매 상품 조회
    TimescaleDB continuous aggregate를 활용하여 기간 내 판매량 기준 상위 상품을 조회합니다.
    ---
    tags:
      - Analytics
    parameters:
      - in: query
        name: days
        type: integer
        default: 30
        description: "조회 기간 (일)"
      - in: query
        name: limit
        type: integer
        default: 20
        description: "상위 N개 (기본값: 20)"
    responses:
      200:
        description: TOP 판매 상품 목록
        schema:
          type: object
          properties:
            days:
              type: integer
            from_date:
              type: string
              format: date-time
            to_date:
              type: string
              format: date-time
            top_products:
              type: array
              items:
                type: object
                properties:
                  sku:
                    type: string
                  display_name:
                    type: string
                  unit:
                    type: string
                  total_sold_qty:
                    type: number
      500:
        description: 서버 오류
    """
    days = request.args.get('days', default=30, type=int)
    limit = request.args.get('limit', default=20, type=int)
    
    service = AnalyticsService()
    try:
        result = service.get_top_sales(days, limit)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


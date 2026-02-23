from flask import Blueprint, jsonify, current_app
from app.db import get_db
from sqlalchemy import text

bp = Blueprint('health', __name__)


@bp.route('/', methods=['GET'])
def root():
    """
    루트 경로 - API 정보
    API 기본 정보와 주요 엔드포인트를 반환합니다.
    ---
    tags:
      - Health
    responses:
      200:
        description: API 정보
        schema:
          type: object
          properties:
            name:
              type: string
            version:
              type: string
            swagger_ui:
              type: string
              description: Swagger UI URL
            endpoints:
              type: object
    """
    return jsonify({
        "name": "Sandwich Server API",
        "version": "1.0.0",
        "swagger_ui": "/api-docs",
        "api_spec": "/apispec.json",
        "endpoints": {
            "health": "/health",
            "db_status": "/db/status",
            "orders": "/orders",
            "inventory": "/inventory/txn",
            "analytics": "/analytics"
        }
    })


@bp.route('/health', methods=['GET'])
def health():
    """
    헬스체크
    서버 상태를 확인합니다.
    ---
    tags:
      - Health
    responses:
      200:
        description: 서버가 정상 작동 중입니다
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
    """
    return jsonify({"status": "ok"})


@bp.route('/routes', methods=['GET'])
def list_routes():
    """등록된 모든 라우트 목록"""
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify({'routes': routes})


@bp.route('/db/status', methods=['GET'])
def db_status():
    """
    TimescaleDB 상태 확인
    TimescaleDB jobs와 continuous aggregates 정보를 조회합니다.
    ---
    tags:
      - Health
    responses:
      200:
        description: TimescaleDB 상태 정보
        schema:
          type: object
          properties:
            jobs:
              type: array
              items:
                type: object
            continuous_aggregates:
              type: array
              items:
                type: object
      500:
        description: 데이터베이스 연결 오류
        schema:
          type: object
          properties:
            error:
              type: string
            jobs:
              type: array
            continuous_aggregates:
              type: array
    """
    db = get_db()
    try:
        # TimescaleDB jobs 조회
        jobs_query = text("""
            SELECT job_id, application_name, scheduled, schedule_interval, 
                   max_runtime, max_retries, retry_period, proc_name, 
                   config, next_start, hypertable_schema, hypertable_name
            FROM timescaledb_information.jobs
            ORDER BY job_id DESC
            LIMIT 20
        """)
        jobs_result = db.execute(jobs_query)
        jobs = []
        for row in jobs_result:
            jobs.append({
                'job_id': row.job_id,
                'application_name': row.application_name,
                'scheduled': row.scheduled,
                'schedule_interval': str(row.schedule_interval) if row.schedule_interval else None,
                'max_runtime': str(row.max_runtime) if row.max_runtime else None,
                'max_retries': row.max_retries,
                'retry_period': str(row.retry_period) if row.retry_period else None,
                'proc_name': row.proc_name,
                'config': row.config,
                'next_start': row.next_start.isoformat() if row.next_start else None,
                'hypertable_schema': row.hypertable_schema,
                'hypertable_name': row.hypertable_name,
            })
        
        # Continuous aggregates 조회
        # materializer_hypertable_id는 일부 TimescaleDB 버전에만 존재하므로 제외
        cagg_query = text("""
            SELECT view_name, view_owner, materialized_only, finalized, 
                   compression_enabled
            FROM timescaledb_information.continuous_aggregates
            ORDER BY view_name
        """)
        cagg_result = db.execute(cagg_query)
        continuous_aggregates = []
        for row in cagg_result:
            cagg_info = {
                'view_name': row.view_name,
                'view_owner': row.view_owner,
                'materialized_only': row.materialized_only,
                'finalized': row.finalized,
                'compression_enabled': row.compression_enabled,
            }
            # materializer_hypertable_id가 존재하는 경우에만 추가
            # (컬럼이 없으면 AttributeError가 발생할 수 있으므로 try-except 사용)
            try:
                if hasattr(row, 'materializer_hypertable_id'):
                    cagg_info['materializer_hypertable_id'] = row.materializer_hypertable_id
            except:
                pass
            continuous_aggregates.append(cagg_info)
        
        return jsonify({
            'jobs': jobs,
            'continuous_aggregates': continuous_aggregates
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'jobs': [],
            'continuous_aggregates': []
        }), 500
    finally:
        db.close()


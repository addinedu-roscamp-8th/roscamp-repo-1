#!/bin/bash
# PostgreSQL 데이터베이스 접속 헬퍼 스크립트
# 사용법: ./connect_db.sh [database_name]

set -e

# .env 파일이 있으면 로드
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 환경 변수 또는 기본값 사용
PGHOST=${DB_HOST:-192.168.0.27}
PGPORT=${DB_PORT:-5432}
PGDATABASE=${1:-${DB_NAME:-pinky_robot_store}}
PGUSER=${DB_USER:-deepdive}

echo "=========================================="
echo "PostgreSQL 접속 정보"
echo "=========================================="
echo "Host: $PGHOST:$PGPORT"
echo "Database: $PGDATABASE"
echo "User: $PGUSER"
echo "=========================================="
echo ""

# 비밀번호가 환경 변수에 없으면 요청
if [ -z "$PGPASSWORD" ] && [ -z "$DB_PASSWORD" ]; then
    read -sp "Enter password for $PGUSER: " PGPASSWORD
    export PGPASSWORD
    echo ""
else
    export PGPASSWORD=${PGPASSWORD:-$DB_PASSWORD}
fi

# psql 접속
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE


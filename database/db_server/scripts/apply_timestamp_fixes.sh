#!/bin/bash
# Timestamp 수정 스크립트 실행
# 실행 방법: ./scripts/apply_timestamp_fixes.sh

set -e

# .env 파일이 있으면 로드
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 환경 변수 또는 기본값 사용
PGHOST=${DB_HOST:-192.168.0.27}
PGPORT=${DB_PORT:-5432}
PGDATABASE=${DB_NAME:-pinky_robot_store}
PGUSER=${DB_USER:-deepdive}

echo "=========================================="
echo "Timestamp 수정 스크립트 실행"
echo "=========================================="
echo "Database: $PGDATABASE"
echo "Host: $PGHOST:$PGPORT"
echo "User: $PGUSER"
echo "=========================================="
echo ""

# 비밀번호 입력 요청
if [ -z "$PGPASSWORD" ] && [ -z "$DB_PASSWORD" ]; then
    read -sp "Enter password for $PGUSER: " PGPASSWORD
    export PGPASSWORD
    echo ""
else
    export PGPASSWORD=${PGPASSWORD:-$DB_PASSWORD}
fi

echo ""
echo "1. 문제가 있는 데이터 확인 중..."
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "
SELECT 
    COUNT(*) AS problem_count,
    MIN(ordered_at) AS min_ordered_at,
    MAX(ordered_at) AS max_ordered_at
FROM store_order
WHERE updated_at < ordered_at;
"

echo ""
echo "2. 데이터 수정 중..."
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f scripts/fix_timestamp_data.sql

echo ""
echo "3. 트리거 생성 중..."
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -f scripts/create_timestamp_triggers.sql

echo ""
echo "4. 최종 검증 중..."
FIXED_COUNT=$(psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -t -c "
SELECT COUNT(*) FROM store_order WHERE updated_at < ordered_at;
" | xargs)

if [ "$FIXED_COUNT" = "0" ]; then
    echo "✅ 모든 데이터가 정상입니다!"
else
    echo "⚠️  아직 $FIXED_COUNT 개의 문제가 있습니다."
fi

echo ""
echo "=========================================="
echo "완료!"
echo "=========================================="

# 비밀번호 제거
unset PGPASSWORD


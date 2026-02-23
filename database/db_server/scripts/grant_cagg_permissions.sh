#!/bin/bash
# Continuous Aggregates 뷰에 대한 SELECT 권한 부여 스크립트
# 사용법: ./grant_cagg_permissions.sh [DB_USER]

set -e

# 환경 변수 또는 기본값 사용
PGHOST=${DB_HOST:-192.168.0.27}
PGPORT=${DB_PORT:-5432}
PGDATABASE=${DB_NAME:-pinky_robot_store}
PGUSER=${DB_ADMIN_USER:-postgres}
TARGET_USER=${1:-deepdive}

echo "=========================================="
echo "Continuous Aggregates 권한 부여 스크립트"
echo "=========================================="
echo "Database: $PGDATABASE"
echo "Host: $PGHOST:$PGPORT"
echo "Admin User: $PGUSER"
echo "Target User: $TARGET_USER"
echo "=========================================="
echo ""

# 비밀번호 입력 요청
read -sp "Enter password for $PGUSER: " PGPASSWORD
export PGPASSWORD
echo ""

# 뷰 소유자 확인
echo "1. 뷰 소유자 확인 중..."
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE -c "
SELECT view_name, view_owner 
FROM timescaledb_information.continuous_aggregates 
WHERE view_name IN ('cagg_daily_inventory_change', 'cagg_daily_sales_qty');
"

echo ""
echo "2. 권한 부여 중..."
psql -h $PGHOST -p $PGPORT -U $PGUSER -d $PGDATABASE << SQL
-- 권한 부여
GRANT SELECT ON public.cagg_daily_inventory_change TO $TARGET_USER;
GRANT SELECT ON public.cagg_daily_sales_qty TO $TARGET_USER;

-- 권한 확인
SELECT 
    grantee, 
    table_name, 
    privilege_type 
FROM information_schema.table_privileges 
WHERE table_schema = 'public' 
  AND table_name IN ('cagg_daily_inventory_change', 'cagg_daily_sales_qty')
  AND grantee = '$TARGET_USER'
ORDER BY table_name, privilege_type;
SQL

echo ""
echo "=========================================="
echo "권한 부여 완료!"
echo "=========================================="

# 비밀번호 제거
unset PGPASSWORD


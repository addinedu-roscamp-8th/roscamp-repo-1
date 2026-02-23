# Sandwich Server 문서

팀원들을 위한 Sandwich Server 프로젝트 문서 모음입니다.

## 문서 목차

### 📋 프로젝트 개요
- [개발 현황](./development-status.md) - 현재 프로젝트의 개발 현황 및 기능 목록
- [프로젝트 구조](../README.md) - 프로젝트 구조 및 기술 스택

### 🗄️ 데이터베이스
- [데이터베이스 가이드](./database-guide.md) - DB 접속, 테이블 구조, 쿼리 방법
- [Continuous Aggregates 설정](./database-guide.md#continuous-aggregates) - TimescaleDB 뷰 생성 및 권한 설정

### 🖥️ 서버 운영
- [서버 사용 가이드](./server-guide.md) - 서버 실행, 환경 설정, 웹 UI 사용법
- [인프라 가이드](./infrastructure.md) - 환경 설정, DB 접속, 문제 해결

### 🔌 API 레퍼런스
- [API 레퍼런스](./api-reference.md) - 모든 REST API 엔드포인트 상세 설명
- [Swagger UI](../README.md#api-문서화-swagger) - 인터랙티브 API 문서 (`http://192.168.0.27:5000/api-docs`)

## 빠른 시작

### 1. 환경 설정
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp env.example .env
# .env 파일 편집 (DB 접속 정보 입력)
```

### 2. 서버 실행
```bash
python run.py
```

### 3. 접속
- **API 문서**: http://192.168.0.27:5000/api-docs
- **대시보드**: http://192.168.0.27:5000/dashboard
- **주문 관리**: http://192.168.0.27:5000/orders-ui

## 주요 기능

- ✅ 주문 관리 (생성, 조회, 상태 변경)
- ✅ 원재료 관리 (마스터, 거래 이벤트)
- ✅ 메뉴 레시피 BOM 관리
- ✅ 실시간 대시보드
- ✅ 분석 API (일별 판매량, TOP 상품)
- ✅ Swagger API 문서화

## 데이터베이스 정보

- **Host**: 192.168.0.27
- **Port**: 5432
- **Database**: pinky_robot_store
- **User**: deepdive
- **Version**: PostgreSQL 16.11 + TimescaleDB

## 문의

문제가 발생하거나 질문이 있으면 팀 채널로 문의하세요.


# Kitchmatic Database Setup

## PostgreSQL 설치 및 초기화

### 1. PostgreSQL 설치
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### 2. 데이터베이스 생성
```bash
sudo -u postgres psql

# PostgreSQL 프롬프트에서:
CREATE DATABASE kitchmatic;
CREATE USER kitchmatic_user WITH PASSWORD 'your_password_here';  # TODO: 비밀번호 설정
GRANT ALL PRIVILEGES ON DATABASE kitchmatic TO kitchmatic_user;
\q
```

### 3. 스키마 적용
```bash
psql -U kitchmatic_user -d kitchmatic -f schema.sql
```

### 4. 연결 확인
```bash
psql -U kitchmatic_user -d kitchmatic -c "SELECT * FROM menus;"
```

## 환경 변수 설정

Main Server에서 사용할 DB 연결 정보:

```bash
export DB_HOST=localhost  # TODO: DB 서버 IP 입력
export DB_PORT=5432
export DB_NAME=kitchmatic
export DB_USER=kitchmatic_user
export DB_PASSWORD=your_password_here  # TODO: 비밀번호 입력
```

## 주의사항

- 실제 운영 환경에서는 강력한 비밀번호를 사용하세요
- DB 서버가 별도 PC인 경우, `/etc/postgresql/*/main/postgresql.conf`에서 `listen_addresses` 설정 변경
- `/etc/postgresql/*/main/pg_hba.conf`에서 네트워크 접근 권한 설정

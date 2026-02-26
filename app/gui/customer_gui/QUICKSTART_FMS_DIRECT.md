# Quick Start - Customer GUI (FMS Direct)

Backend 없이 FMS로 직접 주문 전달하는 기능 빠른 시작 가이드

## 1분 Quick Start

### 1. Mock 모드로 GUI 테스트 (FMS 서버 불필요)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui
python3 src/main_fms_direct.py --mock
```

### 2. CLI로 메시지 형식 확인

```bash
python3 test_gui_to_fms.py --format
```

### 3. Mock 모드로 전체 플로우 테스트

```bash
python3 test_gui_to_fms.py --mock
```

## 실제 FMS 연결

### 1. FMS 서버 실행 (터미널 1)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/fms
python -m fms.fms_node
```

### 2. GUI 실행 (터미널 2)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1/app/gui/customer_gui
python3 src/main_fms_direct.py
```

### 3. CLI 테스트 (터미널 2)

```bash
python3 test_gui_to_fms.py
```

## 편의 스크립트

```bash
# GUI 실행 (실제 FMS)
./run_fms_direct.sh

# GUI 실행 (Mock 모드)
./run_fms_direct.sh --mock

# CLI 테스트
./run_fms_direct.sh --test

# CLI 테스트 (Mock)
./run_fms_direct.sh --test --mock

# 메시지 형식만 확인
./run_fms_direct.sh --test --format
```

## 주요 기능

### Mock 메뉴 (테스트용)

- 햄버거: 8,000원
- 치즈버거: 9,000원
- 피자: 15,000원
- 샌드위치: 6,000원

### 주문 플로우

1. "주문 시작" 클릭
2. 메뉴 선택 (수량 조정 가능)
3. "주문 확인" 클릭
4. FMS로 주문 전송
5. 주문 접수 완료 메시지
6. (배달 알림 대기)
7. 배달 알림 화면 표시
8. "수령 완료" 클릭
9. 감사 메시지

## FMS 통신 설정

FMS 주소는 `/home/gw/kitchmatics/roscamp-repo-1/fms/config/network_config.yaml`에서 설정:

```yaml
master:
  host: "192.168.1.3"
  tcp_port: 9000
```

## 트러블슈팅

### FMS 연결 실패

```bash
# FMS 서버 실행 여부 확인
ps aux | grep fms_node

# 포트 사용 여부 확인
netstat -tlnp | grep 9000

# 네트워크 연결 확인
ping 192.168.1.3
```

해결 방법:
1. FMS 서버 실행
2. 또는 Mock 모드 사용: `--mock` 옵션

### PyQt5 없음

```bash
pip install PyQt5 pyyaml python-dotenv
```

## 다음 단계

- 상세 문서: `README_FMS_DIRECT.md`
- 아키텍처: Clean Architecture 구조 참조
- 코드 위치: `src/fms_client.py`, `src/main_fms_direct.py`

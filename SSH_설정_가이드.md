# SSH 접근 설정 가이드

## 현재 상태
- ✅ pinky1, pinky2: SSH 키 인증 설정됨 (비밀번호 없이 접속 가능)
- ❌ jetcobot A, jetcobot B: SSH 키 미설정 (비밀번호 필요)

---

## 방법 1: SSH 키 복사 (권장)

이 방법을 사용하면 비밀번호 없이 자동으로 SSH 접속할 수 있습니다.

### 1-1. jetcobot A (192.168.1.4)에 SSH 키 복사

```bash
# SSH 키가 없다면 먼저 생성
# (이미 있으면 이 단계 스킵)
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi

# jetcobot A에 SSH 키 복사
ssh-copy-id jetcobot@192.168.1.4
# 비밀번호 입력: 1

# 테스트
ssh jetcobot@192.168.1.4 'echo "Connection successful!"'
```

### 1-2. jetcobot B (192.168.1.10)에 SSH 키 복사

```bash
# jetcobot B에 SSH 키 복사
ssh-copy-id jetcobot@192.168.1.10
# 비밀번호 입력: 1

# 테스트
ssh jetcobot@192.168.1.10 'echo "Connection successful!"'
```

---

## 방법 2: sshpass 설치 (빠른 임시 방법)

SSH 키 설정 없이 비밀번호를 스크립트로 전달할 수 있습니다.

### 2-1. sshpass 설치

```bash
sudo apt-get update
sudo apt-get install -y sshpass
```

### 2-2. 사용 예제

```bash
# jetcobot A 접속
sshpass -p 1 ssh jetcobot@192.168.1.4 'echo "Test"'

# jetcobot B 접속
sshpass -p 1 ssh jetcobot@192.168.1.10 'echo "Test"'
```

**주의**: 이 방법은 비밀번호가 명령어에 노출되므로 보안에 취약합니다.
테스트 목적으로만 사용하고, 프로덕션에서는 방법 1(SSH 키)를 권장합니다.

---

## 방법 3: 한 번에 모든 로봇에 SSH 키 설정

```bash
#!/bin/bash
# 모든 로봇에 SSH 키 복사

# SSH 키 생성 (없는 경우)
if [ ! -f ~/.ssh/id_rsa ]; then
    echo "SSH 키 생성 중..."
    ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
fi

echo "======================================"
echo "SSH 키를 모든 로봇에 복사합니다"
echo "각 로봇의 비밀번호는 1입니다"
echo "======================================"

# pinky1 (이미 설정되어 있을 수 있음)
echo "1. pinky1 설정 중..."
ssh-copy-id -o StrictHostKeyChecking=no pinky@192.168.1.7 2>/dev/null || echo "pinky1 이미 설정됨 또는 스킵"

# pinky2 (이미 설정되어 있을 수 있음)
echo "2. pinky2 설정 중..."
ssh-copy-id -o StrictHostKeyChecking=no pinky@192.168.1.6 2>/dev/null || echo "pinky2 이미 설정됨 또는 스킵"

# pinky3 (선택사항)
echo "3. pinky3 설정 중..."
ssh-copy-id -o StrictHostKeyChecking=no pinky@192.168.1.11 2>/dev/null || echo "pinky3 이미 설정됨 또는 스킵"

# jetcobot A
echo "4. jetcobot A 설정 중..."
ssh-copy-id -o StrictHostKeyChecking=no jetcobot@192.168.1.4

# jetcobot B
echo "5. jetcobot B 설정 중..."
ssh-copy-id -o StrictHostKeyChecking=no jetcobot@192.168.1.10

echo ""
echo "======================================"
echo "설정 완료! 연결 테스트 중..."
echo "======================================"

# 연결 테스트
ssh pinky@192.168.1.7 'hostname' && echo "✅ pinky1 연결 성공" || echo "❌ pinky1 연결 실패"
ssh pinky@192.168.1.6 'hostname' && echo "✅ pinky2 연결 성공" || echo "❌ pinky2 연결 실패"
ssh jetcobot@192.168.1.4 'hostname' && echo "✅ jetcobot A 연결 성공" || echo "❌ jetcobot A 연결 실패"
ssh jetcobot@192.168.1.10 'hostname' && echo "✅ jetcobot B 연결 성공" || echo "❌ jetcobot B 연결 실패"

echo ""
echo "모든 로봇에 비밀번호 없이 SSH 접속이 가능합니다!"
```

위 스크립트를 복사하여 실행하거나, 아래 명령어로 실행하세요:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
bash scripts/setup_ssh_keys.sh
```

---

## 권장 방법

**방법 1 (SSH 키 복사)**를 권장합니다:
- ✅ 보안 강화
- ✅ 자동화 스크립트에 안전
- ✅ 비밀번호 입력 불필요
- ✅ 한 번만 설정하면 영구 사용

다음 명령어로 빠르게 설정할 수 있습니다:

```bash
# jetcobot A
ssh-copy-id jetcobot@192.168.1.4

# jetcobot B
ssh-copy-id jetcobot@192.168.1.10
```

각각 비밀번호 `1`을 입력하면 완료됩니다.

---

## 확인 방법

설정 후 다음 명령어로 비밀번호 없이 접속되는지 확인:

```bash
# 모든 로봇 연결 테스트
ssh pinky@192.168.1.7 'echo "pinky1 OK"'
ssh pinky@192.168.1.6 'echo "pinky2 OK"'
ssh jetcobot@192.168.1.4 'echo "jetcobot A OK"'
ssh jetcobot@192.168.1.10 'echo "jetcobot B OK"'
```

모두 비밀번호 입력 없이 "OK" 메시지가 출력되면 성공입니다!

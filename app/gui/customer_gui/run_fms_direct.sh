#!/bin/bash
# Customer GUI 실행 스크립트 (FMS Direct Mode)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/pyqt"

# 가상환경 활성화
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
else
    echo "Error: 가상환경을 찾을 수 없습니다: $VENV_PATH"
    echo "먼저 가상환경을 생성하세요:"
    echo "  python3 -m venv pyqt"
    echo "  source pyqt/bin/activate"
    echo "  pip install PyQt5 python-dotenv pyyaml"
    exit 1
fi

# 실행 모드 확인
if [ "$1" = "--mock" ]; then
    echo "========================================="
    echo "Customer GUI (FMS Direct - Mock Mode)"
    echo "========================================="
    python "$SCRIPT_DIR/src/main_fms_direct.py" --mock
elif [ "$1" = "--test" ]; then
    echo "========================================="
    echo "FMS Connection Test"
    echo "========================================="
    python "$SCRIPT_DIR/test_gui_to_fms.py" "${@:2}"
else
    echo "========================================="
    echo "Customer GUI (FMS Direct Mode)"
    echo "========================================="
    python "$SCRIPT_DIR/src/main_fms_direct.py"
fi

#!/bin/bash
# =========================================================
# Backend(Main Server) 실행 - 리포지토리 루트 ROS2 워크스페이스 사용
# - fleet_interfaces, main_server를 루트에서 colcon 빌드 후 실행
# - build/ install/ log/ 는 .gitignore 되어 git에 올라가지 않음
# =========================================================

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ROS2 환경
if [ -f /opt/ros/jazzy/setup.bash ]; then
    source /opt/ros/jazzy/setup.bash
elif [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
else
    echo "ROS2 setup.bash not found (jazzy/humble). Install ROS2 or set path."
    exit 1
fi

# robot_arm/.../venv 안의 setup.py가 colcon에 잡히지 않도록 COLCON_IGNORE 생성
[ -d "$REPO_ROOT/robot_arm/image_streaming_server/venv" ] && touch "$REPO_ROOT/robot_arm/image_streaming_server/venv/COLCON_IGNORE"

# 워크스페이스 미빌드 시 루트에서 colcon 빌드 (패키지명 fleet_interfaces 주의)
if [ ! -f "$REPO_ROOT/install/setup.bash" ]; then
    echo "Building ROS2 workspace at repo root (fleet_interfaces, main_server)..."
    colcon build --packages-select fleet_interfaces main_server
fi
if [ ! -f "$REPO_ROOT/install/setup.bash" ]; then
    echo "Build failed or install/setup.bash missing. Run from repo root:"
    echo "  colcon build --packages-select fleet_interfaces main_server"
    exit 1
fi
source "$REPO_ROOT/install/setup.bash"

# install/setup.bash가 설정한 PYTHONPATH만 사용 (소스 디렉터리 fleet_interfaces는 생성된 .py 없어 사용 금지)
# 필요 시 install 쪽 fleet_interfaces 경로만 명시 (REPO_ROOT는 넣지 않음 - 소스가 먼저 잡히면 ImportError 발생)
if [ -d "$REPO_ROOT/install/fleet_interfaces/lib/python3.12/site-packages" ]; then
  export PYTHONPATH="$REPO_ROOT/install/fleet_interfaces/lib/python3.12/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi
if [ -d "$REPO_ROOT/install/fleet_interfaces/lib/site-packages" ]; then
  export PYTHONPATH="$REPO_ROOT/install/fleet_interfaces/lib/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

# Backend 의존성(sqlalchemy 등)이 설치된 venv 우선 사용 (없으면 현재 python3)
PYTHON_BIN="python3"
if [ -x "$REPO_ROOT/app/backend/venv/bin/python3" ]; then
  PYTHON_BIN="$REPO_ROOT/app/backend/venv/bin/python3"
fi

# Backend 실행 (워크스페이스 source + PYTHONPATH 로 fleet_interfaces 등 경로 적용)
echo "Starting Main Server..."
exec "$PYTHON_BIN" "$REPO_ROOT/app/backend/run_main_server.py"

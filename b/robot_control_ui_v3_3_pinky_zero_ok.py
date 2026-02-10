#!/usr/bin/env python3
# coding: utf-8
"""
MyCobot280 PyQt6 제어 UI  ─  v3.3
────────────────────────────────────────
수정 내용 (v3.3):
  ⑪ 식자재 검증 워크플로우 확장 (5~9번)
  ⑫ 수직 진입 값 수정 (PDF 오류 수정)
  ⑬ 티칭 모드 확장 (소스1~3 + 검증 포즈 저장)
  ⑭ 트레이 잡기 추가 (4단계 경유 + 그리퍼)
  ⑮ 각도읽기 실행 버튼 추가

키보드 단축키:
  [0] 트레이잡기 (4단계)
  [1~4] 소스·뿌리기
  [5] 검증위치   [6] 검증OK   [7] 불량
  [8] 핑키전달   [9] 초기위치
"""

import sys, time, threading, glob
from functools import partial

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox, QMessageBox, QFrame,
    QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette

# ─── pymycobot ───────────────────────────────────────────────────────────
try:
    from pymycobot.mycobot280 import MyCobot280
    ROBOT_LIB  = True
    IMPORT_ERR = None
except Exception as e:
    MyCobot280 = None
    ROBOT_LIB  = False
    IMPORT_ERR = e
    print("[WARN] pymycobot import 실패:", e)

# ═══════════════════════════════════════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════════════════════════════════════
DEFAULT_PORT  = '/dev/ttyJETCOBOT'
BAUD          = 1000000
SPEED         = 30
GRIPPER_SPEED = 30
SAFE_POSE     = [0, 0, 0, 0, 0, 0]

ANGLE_MIN = [-168, -135, -150, -145, -165, -180]
ANGLE_MAX = [ 168,  135,  150,  145,  165,  180]

# ─── 포즈 정의 ───────────────────────────────────────────────────────────
APPROACH_READY  = [-90,   0,   0,   0,  4,  0]
APPROACH_DOWN   = [-90, -20, -40,  20,  4,  0]
RETRACT_POSE    = [-90,  50,-100,   0,  4,  0]

SOURCE_1_PICK   = [-95, -40, -44,  -5,  4,  0]
SOURCE_2_PICK   = [-82, -38, -45,  -8,  4, 10]
SOURCE_3_PICK   = [-71, -38, -45,  -8,  4,-10]

# ─── 수직 진입 중간 경유 포즈 (수동 조정 가능) ────────────────────────
# ⚠️ PDF 값 오류 수정: VERTICAL_MID2_J2 = 20 (양수) → -35 (음수)
VERTICAL_MID1_J2 = -25   # 중간1의 관절2
VERTICAL_MID2_J2 =  20   # 중간2의 관절2 (더 내리려면 -40, -45)
VERTICAL_MID2_J3 = -88   # 중간2의 관절3 (더 내리려면 -50)
VERTICAL_MID2_J4 =   0   # 중간2의 관절4

def calc_vertical_approach(pick_pose):
    """
    수직 진입 경로 생성
    
    조정 가이드:
    - 소스통이 앞쪽에 떨어지면: VERTICAL_MID2_J2를 더 음수로 (-40, -45)
    - 소스통이 뒤쪽에 떨어지면: VERTICAL_MID2_J2를 덜 음수로 (-30, -25)
    """
    mid1 = [pick_pose[0], VERTICAL_MID1_J2, -40, 20, 4, 0]
    mid2 = [pick_pose[0], VERTICAL_MID2_J2, VERTICAL_MID2_J3,
            VERTICAL_MID2_J4, 4, pick_pose[5]]
    return [mid1, mid2]

# ─── 식자재 검증 관련 포즈 (티칭 모드로 실제 위치 기록 필요) ──────────
# 검증위치 [5] - 3단계 경유
VERIFY_STEP1         = [  -29,    -5, -90,  11,  0, -29]   # 검증 1단계
VERIFY_STEP2         = [-0.43, 24.34, -66.44,-42.53,5.18,  1.58]   # 검증 2단계
VERIFY_STEP3         = [-0.61, 17.13, -50,-56, 5.0,-84.81] #
#[-0.61, 17.13, -66.88,-37.52, 5.0,-84.81]   # 검증 3단계 (최종)

# 검증 OK [6] - 3단계 경유
VERIFY_OK_STEP1      = [ 29,    -5, -90,  11,  0, -29]   # OK 1단계
VERIFY_OK_STEP2      = [ -0.43, 24.34, -66.44,-42.53,5.18,  1.58]   # OK 2단계
VERIFY_OK_STEP3      = [ -0.61, 17.13, -66.88,-37.52, 5.0,-84.81]   # OK 3단계 (최종)

# 불량 [7] - 3단계 경유
VERIFY_DEFECT_STEP1  = [-10,  50, -70,   5,  0,  0]   # 불량 1단계
VERIFY_DEFECT_STEP2  = [-15,  55, -75,   8,  0,  0]   # 불량 2단계
VERIFY_DEFECT_STEP3  = [-20,  60, -80,  10,  0,  0]   # 불량 3단계 (최종)

# 핑키 전달 [8] - 4단계 경유 + 그리퍼 열기
PINKY_STEP1          = [-0.61, 17.13, -50, -40, 5.0, -84.81]     # 핑키 1단계
PINKY_STEP2          = [31.02, 26.19,-66.44,-27.94,-2.98,-50.88] # 핑키 2단계
PINKY_STEP3          = [29.0, 23.99,-76.55,-18.45,3.33,-53.17]   # 핑키 3단계
PINKY_STEP4          = [29.0, 20.0,-80.0,-15.0,3.33,-53.17]      # 핑키 4단계 (최종 전달 위치)

# 초기 위치 [9]
INITIAL_POSITION     = [  0,   0,   0,   0,  0,  0]   # 초기 위치

# 트레이 잡기 [0] - 4단계 경유 + 그리퍼
TRAY_GRAB_STEP1      = [  0,  30, -105,  13,  4,  5]   # 트레이 1단계
TRAY_GRAB_STEP2      = [  0, -20, -105,  42,  4,  2]   # 트레이 2단계
TRAY_GRAB_STEP3      = [  0, -28, -105,  46,  4,  2]   # 트레이 3단계
TRAY_GRAB_STEP4      = [  0,  30, -105, -13,  4,  5]   # 트레이 4단계 (최종)

# ─── 뿌리기 포즈 시퀀스 ──────────────────────────────────────────────────
POUR_SEQ = [
    ([  0,  80,-100,  0,  0,  0],  1.0),
    ([  0, -10, -80, 20,  0,  0],  1.8),
    ([ -5, -34, -62, 23,  0, 10],  0.7),
    ([ 11, -29, -62, 15,  3, 13],  0.6),
    ([-12, -29, -62, 18,  3, 13],  0.7),
    ([ 13, -29, -62,  2,  2, 13],  0.7),
    ([-14, -28, -62,  8,  3, 13],  0.7),
    ([  3, -29, -62, 10, -3,  3],  0.6),
]

# ═══════════════════════════════════════════════════════════════════════════
# 전역 상태
# ═══════════════════════════════════════════════════════════════════════════
mc                = None
_stop_event       = threading.Event()
_full_mode_thread = None

# ═══════════════════════════════════════════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════════════════════════════════════════
def find_port_candidates():
    return (glob.glob('/dev/ttyJETCOBOT*') +
            glob.glob('/dev/ttyUSB*') +
            glob.glob('/dev/ttyACM*'))

def clamp_angles(angles):
    return [max(ANGLE_MIN[i], min(angles[i], ANGLE_MAX[i])) for i in range(6)]

def verify_move(target, timeout=2.5, poll=0.15, tol=2.0):
    if mc is None:
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            cur = mc.get_angles()
            if cur and all(abs(cur[i] - target[i]) <= tol for i in range(6)):
                return True
        except Exception:
            pass
        time.sleep(poll)
    return False

def gripper_open():
    if mc: mc.set_gripper_value(100, GRIPPER_SPEED)

def gripper_close():
    if mc: mc.set_gripper_value(0, GRIPPER_SPEED)

def safe_return():
    if mc:
        try:
            mc.send_angles(SAFE_POSE, SPEED)
        except Exception as e:
            print("[SAFE] 오류:", e)

# ═══════════════════════════════════════════════════════════════════════════
# 핵심 실행 함수
# ═══════════════════════════════════════════════════════════════════════════
def _send(pose, wait=None):
    if _stop_event.is_set():
        raise RuntimeError("중단 요청")
    angles = clamp_angles(pose)
    mc.send_angles(angles, SPEED)
    print(f"  → send {angles}")
    if wait:
        _stop_event.wait(timeout=wait)
        if _stop_event.is_set():
            raise RuntimeError("중단 요청")

def execute_pour():
    print("[POUR] 시작")
    for idx, (pose, wait) in enumerate(POUR_SEQ, 1):
        if _stop_event.is_set():
            raise RuntimeError("중단 요청")
        print(f"[POUR] step{idx}/{len(POUR_SEQ)}")
        _send(pose, wait)
    print("[POUR] 완료")

def run_source(pick_pose, source_name):
    print(f"\n{'='*50}")
    print(f" {source_name} 시퀀스 시작")
    print(f"{'='*50}")

    _send(APPROACH_READY, 1.2)
    _send(APPROACH_DOWN,  1.0)

    waypoints = calc_vertical_approach(pick_pose)
    print("[접근] 수직 진입")
    _send(waypoints[0], 0.5)
    _send(waypoints[1], 0.5)
    _send(pick_pose,    0.6)
    gripper_close()
    time.sleep(0.4)

    _send(RETRACT_POSE, 1.2)
    execute_pour()

    print("[복귀] 소스통 되돌리기 (수직 진입)")
    _send(APPROACH_READY, 1.2)
    _send(APPROACH_DOWN,  1.0)
    _send(waypoints[0], 0.5)
    _send(waypoints[1], 0.5)
    _send(pick_pose,    0.6)

    gripper_open()
    time.sleep(0.5)

    _send(RETRACT_POSE, 1.2)
    _send(SAFE_POSE, 1.0)
    print(f" {source_name} 완료\n")

def run_pour_only():
    print("\n[소스4] 단독 뿌리기")
    _send(POUR_SEQ[0][0], 1.0)
    gripper_open()
    time.sleep(0.3)
    execute_pour()
    _send(SAFE_POSE, 1.0)
    print("[소스4] 완료\n")

def run_tray_grab():
    """트레이 잡기 - 4단계 경유 후 그리퍼 닫기"""
    print("\n[트레이 잡기] 시작")
    
    # 그리퍼 열기
    gripper_open()
    time.sleep(0.5)
    
    # 4단계 경유
    print("  → 1단계 이동")
    _send(TRAY_GRAB_STEP1, 1.0)
    
    print("  → 2단계 이동")
    _send(TRAY_GRAB_STEP2, 0.8)
    
    print("  → 3단계 이동")
    _send(TRAY_GRAB_STEP3, 0.8)
    
    #print("  → 4단계 이동 (최종)")
    #_send(TRAY_GRAB_STEP4, 0.8)
    
    # 그리퍼 닫기
    print("  → 트레이 잡기")
    gripper_close()
    time.sleep(0.8)
    
    print("  → 4단계 이동 (최종)")
    _send(TRAY_GRAB_STEP4, 0.8)
    
    print("[트레이 잡기] 완료\n")

def run_pinky_delivery():
    """핑키 전달 - 4단계 경유 후 그리퍼 열기, 제로 위치 복귀"""
    print("\n[핑키 전달] 시작")
    
    # 4단계 경유
    print("  → 1단계 이동")
    _send(PINKY_STEP1, 0.8)
    
    print("  → 2단계 이동")
    _send(PINKY_STEP2, 0.8)
    
    print("  → 3단계 이동")
    _send(PINKY_STEP3, 0.8)
    
    print("  → 4단계 이동 (최종)")
    _send(PINKY_STEP4, 0.8)
    
    # 그리퍼 열기
    print("  → 그리퍼 열기 (전달)")
    gripper_open()
    time.sleep(0.5)
    
    # 제로 위치로 복귀
    print("  → 제로 위치로 복귀")
    _send(INITIAL_POSITION, 1.0)
    
    print("[핑키 전달] 완료\n")

# ═══════════════════════════════════════════════════════════════════════════
# SEQUENCES 맵
# ═══════════════════════════════════════════════════════════════════════════
SEQUENCES = {
    "0": {"name": "트레이 잡기",      "icon": "🍱", "color": "#e67e22", "fn": None},
    "1": {"name": "소스 1",          "icon": "🥗", "color": "#e74c3c", "fn": None},
    "2": {"name": "소스 2",          "icon": "🥙", "color": "#e67e22", "fn": None},
    "3": {"name": "소스 3",          "icon": "🥘", "color": "#27ae60", "fn": None},
    "4": {"name": "뿌리기",          "icon": "💧", "color": "#3498db", "fn": None},
    "5": {"name": "식자재 검증위치", "icon": "🔍", "color": "#9b59b6", "fn": None},
    "6": {"name": "검증 OK",        "icon": "✅", "color": "#27ae60", "fn": None},
    "7": {"name": "불량",           "icon": "❌", "color": "#e74c3c", "fn": None},
    "8": {"name": "핑키 전달",      "icon": "🤝", "color": "#1abc9c", "fn": None},
    "9": {"name": "초기 위치",      "icon": "🏠", "color": "#34495e", "fn": None},
}

def _init_seq_map():
    SEQUENCES["0"]["fn"] = run_tray_grab
    SEQUENCES["1"]["fn"] = partial(run_source, SOURCE_1_PICK, "소스1")
    SEQUENCES["2"]["fn"] = partial(run_source, SOURCE_2_PICK, "소스2")
    SEQUENCES["3"]["fn"] = partial(run_source, SOURCE_3_PICK, "소스3")
    SEQUENCES["4"]["fn"] = run_pour_only
    SEQUENCES["5"]["fn"] = lambda: (
        _send(VERIFY_STEP1, 0.8),
        _send(VERIFY_STEP2, 0.8),
        _send(VERIFY_STEP3, 1.0),
        print("[5] 검증위치 완료")
    )
    SEQUENCES["6"]["fn"] = lambda: (
        _send(VERIFY_OK_STEP1, 0.8),
        _send(VERIFY_OK_STEP2, 0.8),
        _send(VERIFY_OK_STEP3, 1.0),
        print("[6] 검증OK 완료")
    )
    SEQUENCES["7"]["fn"] = lambda: (
        _send(VERIFY_DEFECT_STEP1, 0.8),
        _send(VERIFY_DEFECT_STEP2, 0.8),
        _send(VERIFY_DEFECT_STEP3, 1.0),
        print("[7] 불량 완료")
    )
    SEQUENCES["8"]["fn"] = run_pinky_delivery
    SEQUENCES["9"]["fn"] = lambda: (_send(INITIAL_POSITION, 1.0), print("[9] 초기위치 완료"))

# ═══════════════════════════════════════════════════════════════════════════
# 연결
# ═══════════════════════════════════════════════════════════════════════════
def connect_robot(port=None):
    global mc
    if not ROBOT_LIB:
        raise RuntimeError(f"pymycobot 없음: {IMPORT_ERR}")
    if not port or not port.strip():
        cands = find_port_candidates()
        port  = cands[0] if cands else DEFAULT_PORT
    try:
        mc = MyCobot280(port, BAUD)
        mc.thread_lock = True
        time.sleep(0.3)
        test = mc.get_angles()
        print(f"[CONNECT] 성공: {port}")
        return True, f"연결 완료: {port}"
    except Exception as e:
        mc = None
        return False, str(e)

def disconnect_robot():
    global mc
    if mc:
        try:
            mc.servo_off()
        except Exception:
            pass
        mc = None

def run_full_mode():
    global _full_mode_thread
    if mc is None or (_full_mode_thread and _full_mode_thread.is_alive()):
        return
    _stop_event.clear()
    def worker():
        try:
            for k in ["1","2","3"]:
                if _stop_event.is_set(): break
                SEQUENCES[k]["fn"]()
        except Exception as e:
            print(f"[FULL] 오류: {e}")
            safe_return()
    _full_mode_thread = threading.Thread(target=worker, daemon=True)
    _full_mode_thread.start()

# ═══════════════════════════════════════════════════════════════════════════
# PyQt6 UI
# ═══════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    log_sig    = pyqtSignal(str)
    status_sig = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.connected  = False
        self.is_running = False
        self._btns      = {}
        self.saved_angles = None  # 현재위치 버튼으로 읽은 각도 저장

        _init_seq_map()
        self._build_ui()
        self.log_sig.connect(self._append_log)
        self.status_sig.connect(self._on_status)

        if not ROBOT_LIB:
            self._log("❌ pymycobot 패키지 없음")
        else:
            self._log("📌 [🔗 연결] 버튼을 클릭하세요")

    def _build_ui(self):
        self.setWindowTitle("🤖  MyCobot280 제어 UI  v3.3")
        self.setMinimumSize(750, 850)
        self.setStyleSheet(self._css())

        # 메인 컨테이너
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 상단 헤더 (고정)
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)
        header_layout.setSpacing(6)
        header_layout.addWidget(self._lbl("🤖  MyCobot280 로봇팔 제어", 16, "#ecf0f1", True))
        self.conn_lbl = self._lbl("● 연결 안됨", 10, "#e74c3c", True)
        header_layout.addWidget(self.conn_lbl)
        header_layout.addWidget(self._sep())
        main_layout.addWidget(header)

        # 스크롤 영역 (중간 버튼들)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background:#1e1e2e; width:8px; border-radius:4px; }
            QScrollBar::handle:vertical { background:#3a3a52; border-radius:4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0px; }
        """)
        
        scroll_content = QWidget()
        R = QVBoxLayout(scroll_content)
        R.setContentsMargins(16, 5, 16, 5)
        R.setSpacing(6)

        R.addWidget(self._connection_card())
        R.addWidget(self._sep())
        R.addWidget(self._seq_card("🍱  트레이", ["0"]))
        R.addWidget(self._seq_card("📦  소스 & 뿌리기", ["1","2","3","4"]))
        R.addWidget(self._seq_card("🔍  식자재 검증", ["5","6","7"]))
        R.addWidget(self._seq_card("🏠  전달 & 위치", ["8","9"]))
        R.addWidget(self._teaching_card())
        R.addStretch()

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        # 하단 버튼들 (고정)
        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 5, 16, 10)
        footer_layout.setSpacing(6)
        
        footer_layout.addWidget(self._sep())
        row = QHBoxLayout(); row.setSpacing(10)
        self.btn_full = self._btn("▶▶ 전체모드", "#8e44ad", self._on_full_mode)
        self.btn_full.setFixedHeight(36); self.btn_full.setEnabled(False)
        row.addWidget(self.btn_full)
        self.btn_stop = self._btn("⏹ 안전정지", "#c0392b", self._on_stop)
        self.btn_stop.setFixedHeight(36)
        row.addWidget(self.btn_stop)
        self.btn_read = self._btn("📍 각도읽기", "#34495e", self._on_read)
        self.btn_read.setFixedHeight(36); self.btn_read.setEnabled(False)
        row.addWidget(self.btn_read)
        footer_layout.addLayout(row)
        footer_layout.addWidget(self._sep())

        footer_layout.addWidget(self._lbl("📋  실행 로그", 11, "#95a5a6", True))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFont(QFont("Consolas", 9))
        self.log_box.setMinimumHeight(100)
        self.log_box.setMaximumHeight(120)
        self.log_box.setStyleSheet("""
            QTextEdit { background:#1a1a2e; color:#a8d8ea;
                        border:1px solid #16213e; border-radius:6px; padding:6px; }
        """)
        footer_layout.addWidget(self.log_box)
        footer_layout.addWidget(self._lbl(
            "단축키: [0] 트레이  [1~4] 소스  [5] 검증  [6] OK  [7] 불량  [8] 핑키  [9] 초기",
            8, "#637074", True))
        
        main_layout.addWidget(footer)

    def _connection_card(self):
        frame = QFrame(); frame.setObjectName("card")
        L = QVBoxLayout(frame)
        L.setContentsMargins(16,12,16,12); L.setSpacing(8)
        L.addWidget(self._lbl("🔌  로봇 연결 & 서보", 13, "#bdc3c7", True))

        r1 = QHBoxLayout(); r1.setSpacing(8)
        r1.addWidget(self._lbl_left("포트:", 11, "#ecf0f1"))
        self.port_combo = QComboBox()
        self.port_combo.setFont(QFont("Segoe UI", 11))
        self.port_combo.setEditable(True)
        self.port_combo.setStyleSheet("""
            QComboBox { background:#2a2a3d; color:#ecf0f1; border:1px solid #3a3a52;
                        border-radius:6px; padding:4px 8px; }
            QComboBox QAbstractItemView { background:#2a2a3d; color:#ecf0f1; }
        """)
        for p in find_port_candidates():
            self.port_combo.addItem(p)
        if self.port_combo.count() == 0:
            self.port_combo.addItem(DEFAULT_PORT)
        r1.addWidget(self.port_combo, stretch=1)
        L.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(8)
        self.btn_conn = self._btn("🔗 연결", "#2980b9", self._on_connect)
        self.btn_conn.setFixedHeight(30)
        self.btn_disc = self._btn("🔗 해제", "#7f8c8d", self._on_disconnect)
        self.btn_disc.setFixedHeight(30); self.btn_disc.setEnabled(False)
        self.btn_son = self._btn("⚡ 서보ON", "#f39c12", self._on_servo_on)
        self.btn_son.setFixedHeight(30); self.btn_son.setEnabled(False)
        self.btn_soff = self._btn("🔋 서보OFF", "#95a5a6", self._on_servo_off)
        self.btn_soff.setFixedHeight(30); self.btn_soff.setEnabled(False)
        for b in (self.btn_conn, self.btn_disc, self.btn_son, self.btn_soff):
            r2.addWidget(b)
        L.addLayout(r2)
        return frame

    def _teaching_card(self):
        frame = QFrame(); frame.setObjectName("card")
        L = QVBoxLayout(frame)
        L.setContentsMargins(12,8,12,8); L.setSpacing(6)
        L.addWidget(self._lbl("🎯  티칭 모드", 12, "#bdc3c7", True))

        info = QLabel("① 티칭시작 → ② 손으로 이동 → ③ 위치 저장")
        info.setFont(QFont("Segoe UI", 8))
        info.setStyleSheet("color:#95a5a6; padding:2px;")
        L.addWidget(info)

        r1 = QHBoxLayout(); r1.setSpacing(6)
        self.btn_teach_off = self._btn("🔓 티칭시작", "#e67e22", self._on_teach_start)
        self.btn_teach_off.setFixedHeight(28); self.btn_teach_off.setEnabled(False)
        r1.addWidget(self.btn_teach_off)

        self.btn_teach_read = self._btn("📖 현재위치", "#3498db", self._on_teach_read)
        self.btn_teach_read.setFixedHeight(28); self.btn_teach_read.setEnabled(False)
        r1.addWidget(self.btn_teach_read)

        self.btn_angle_exec = self._btn("▶️ 각도읽기 실행", "#16a085", self._on_angle_exec)
        self.btn_angle_exec.setFixedHeight(28); self.btn_angle_exec.setEnabled(False)
        r1.addWidget(self.btn_angle_exec)
        L.addLayout(r1)

        # 소스 1~3
        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.teach_btns = []
        for i, (name, color) in enumerate([("소스1","#e74c3c"), ("소스2","#e67e22"), ("소스3","#27ae60")], 1):
            b = self._btn(f"💾 {name}", color, lambda n=i: self._on_teach_save_source(n))
            b.setFixedHeight(28); b.setEnabled(False)
            r2.addWidget(b)
            self.teach_btns.append(b)
        L.addLayout(r2)

        # 트레이 [0]
        r2_5 = QHBoxLayout(); r2_5.setSpacing(6)
        b_tray = self._btn("💾 트레이[0]", "#f39c12", lambda: self._on_teach_save_tray(0))
        b_tray.setFixedHeight(28); b_tray.setEnabled(False)
        r2_5.addWidget(b_tray)
        self.teach_btns.append(b_tray)
        L.addLayout(r2_5)

        # 검증 5~9
        r3 = QHBoxLayout(); r3.setSpacing(6)
        for i, (name, color) in enumerate([("검증[5]","#9b59b6"), ("OK[6]","#27ae60"), 
                                            ("불량[7]","#e74c3c"), ("핑키[8]","#1abc9c"),
                                            ("초기[9]","#34495e")], 5):
            b = self._btn(f"{name}", color, lambda n=i: self._on_teach_save_verify(n))
            b.setFixedHeight(28); b.setEnabled(False)
            r3.addWidget(b)
            self.teach_btns.append(b)
        L.addLayout(r3)
        return frame

    def _seq_card(self, title, keys):
        frame = QFrame(); frame.setObjectName("card")
        L = QVBoxLayout(frame)
        L.setContentsMargins(12,8,12,8); L.setSpacing(6)
        L.addWidget(self._lbl(title, 12, "#bdc3c7", True))
        row = QHBoxLayout(); row.setSpacing(8)
        for k in keys:
            s = SEQUENCES[k]
            b = QPushButton(f"[{k}] {s['icon']} {s['name']}")
            b.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            b.setFixedHeight(42)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            col = s["color"]
            b.setStyleSheet(f"""
                QPushButton {{ background:{col}; color:#fff; border:none; border-radius:8px; }}
                QPushButton:hover {{ background:{col}dd; }}
                QPushButton:pressed {{ background:{col}88; }}
                QPushButton:disabled {{ background:#3d3d3d; color:#666; }}
            """)
            b.clicked.connect(lambda _, key=k: self._run_seq(key))
            b.setEnabled(False)
            row.addWidget(b)
            self._btns[k] = b
        L.addLayout(row)
        return frame

    def _on_connect(self):
        port = self.port_combo.currentText().strip()
        self._log(f"\n🔗 연결 시도: {port}")
        ok, msg = connect_robot(port)
        if ok:
            self.connected = True
            self._log(f"✅ {msg}")
            self._update_conn_ui()
        else:
            self._log(f"❌ 실패: {msg}")

    def _on_disconnect(self):
        disconnect_robot()
        self.connected = False
        self._log("\n🔗 연결 해제")
        self._update_conn_ui()

    def _on_servo_on(self):
        if mc is None: return
        self._log("\n⚡ 서보 ON")
        try:
            mc.focus_all_servos(); time.sleep(0.3)
            self._log("  ✅ 완료")
        except Exception as e:
            self._log(f"  ❌ {e}")

    def _on_servo_off(self):
        if mc is None: return
        self._log("\n🔋 서보 OFF")
        try:
            mc.release_all_servos(); time.sleep(0.3)
            self._log("  ✅ 완료")
        except Exception as e:
            self._log(f"  ❌ {e}")

    def _on_teach_start(self):
        if mc is None:
            self._log("⚠️ 연결 안됨"); return
        self._log("\n🔓 티칭 시작 (서보 OFF)")
        try:
            mc.release_all_servos(); time.sleep(0.3)
            self._log("  ✅ 로봇을 손으로 움직일 수 있습니다")
            self._log("  → [📖 현재위치]로 확인 후 [💾] 저장")
            self.btn_teach_read.setEnabled(True)
            for b in self.teach_btns:
                b.setEnabled(True)
        except Exception as e:
            self._log(f"  ❌ {e}")

    def _on_teach_read(self):
        if mc is None: return
        try:
            angles = mc.get_angles()
            self.saved_angles = angles  # 각도 저장
            self._log(f"\n📖 현재 각도: {angles}")
            self._log("   ✅ 각도 저장 완료")
            self._log("   → [💾] 버튼으로 포즈 저장 또는 [▶️ 각도읽기 실행]으로 이동")
        except Exception as e:
            self._log(f"  ❌ {e}")

    def _on_teach_save_source(self, num):
        global SOURCE_1_PICK, SOURCE_2_PICK, SOURCE_3_PICK
        if mc is None: return
        try:
            angles = mc.get_angles()
            if num == 1:
                SOURCE_1_PICK = angles
                self._log(f"\n💾 소스1 저장: {angles}")
            elif num == 2:
                SOURCE_2_PICK = angles
                self._log(f"\n💾 소스2 저장: {angles}")
            elif num == 3:
                SOURCE_3_PICK = angles
                self._log(f"\n💾 소스3 저장: {angles}")
            self._finish_teaching()
        except Exception as e:
            self._log(f"  ❌ {e}")

    def _on_teach_save_tray(self, num):
        """트레이 잡기 위치 저장 - 4단계"""
        global TRAY_GRAB_STEP1, TRAY_GRAB_STEP2, TRAY_GRAB_STEP3, TRAY_GRAB_STEP4
        
        if mc is None: return
        
        # 각 번호별 저장할 단계 확인
        if not hasattr(self, '_teach_step_count'):
            self._teach_step_count = {}
        
        if num not in self._teach_step_count:
            self._teach_step_count[num] = 1
        
        step = self._teach_step_count[num]
        
        try:
            angles = mc.get_angles()
            
            if step == 1:
                TRAY_GRAB_STEP1 = angles
                self._log(f"\n💾 트레이 1단계 저장: {angles}")
                self._log("   → 2단계 위치로 이동 후 다시 [트레이[0]] 클릭")
                self._teach_step_count[0] = 2
                return
            elif step == 2:
                TRAY_GRAB_STEP2 = angles
                self._log(f"\n💾 트레이 2단계 저장: {angles}")
                self._log("   → 3단계 위치로 이동 후 다시 [트레이[0]] 클릭")
                self._teach_step_count[0] = 3
                return
            elif step == 3:
                TRAY_GRAB_STEP3 = angles
                self._log(f"\n💾 트레이 3단계 저장: {angles}")
                self._log("   → 4단계(최종) 위치로 이동 후 다시 [트레이[0]] 클릭")
                self._teach_step_count[0] = 4
                return
            else:
                TRAY_GRAB_STEP4 = angles
                self._log(f"\n💾 트레이 4단계(최종) 저장: {angles}")
                self._teach_step_count[0] = 1  # 리셋
                
            self._finish_teaching()
        except Exception as e:
            self._log(f"  ❌ {e}")


    def _on_teach_save_verify(self, num):
        global VERIFY_STEP1, VERIFY_STEP2, VERIFY_STEP3
        global VERIFY_OK_STEP1, VERIFY_OK_STEP2, VERIFY_OK_STEP3
        global VERIFY_DEFECT_STEP1, VERIFY_DEFECT_STEP2, VERIFY_DEFECT_STEP3
        global PINKY_STEP1, PINKY_STEP2, PINKY_STEP3, PINKY_STEP4, INITIAL_POSITION
        
        if mc is None: return
        
        # 각 번호별 저장할 단계 확인
        if not hasattr(self, '_teach_step_count'):
            self._teach_step_count = {}
        
        if num not in self._teach_step_count:
            self._teach_step_count[num] = 1
        
        step = self._teach_step_count[num]
        
        try:
            angles = mc.get_angles()
            names = {5:"검증위치", 6:"검증OK", 7:"불량", 8:"핑키전달", 9:"초기위치"}
            
            if num == 5:  # 검증위치 3단계
                if step == 1:
                    VERIFY_STEP1 = angles
                    self._log(f"\n💾 검증위치 1단계 저장: {angles}")
                    self._log("   → 2단계 위치로 이동 후 다시 [검증[5]] 클릭")
                    self._teach_step_count[5] = 2
                    return
                elif step == 2:
                    VERIFY_STEP2 = angles
                    self._log(f"\n💾 검증위치 2단계 저장: {angles}")
                    self._log("   → 3단계(최종) 위치로 이동 후 다시 [검증[5]] 클릭")
                    self._teach_step_count[5] = 3
                    return
                else:
                    VERIFY_STEP3 = angles
                    self._log(f"\n💾 검증위치 3단계(최종) 저장: {angles}")
                    self._teach_step_count[5] = 1  # 리셋
                    
            elif num == 6:  # 검증 OK 3단계
                if step == 1:
                    VERIFY_OK_STEP1 = angles
                    self._log(f"\n💾 검증OK 1단계 저장: {angles}")
                    self._log("   → 2단계 위치로 이동 후 다시 [OK[6]] 클릭")
                    self._teach_step_count[6] = 2
                    return
                elif step == 2:
                    VERIFY_OK_STEP2 = angles
                    self._log(f"\n💾 검증OK 2단계 저장: {angles}")
                    self._log("   → 3단계(최종) 위치로 이동 후 다시 [OK[6]] 클릭")
                    self._teach_step_count[6] = 3
                    return
                else:
                    VERIFY_OK_STEP3 = angles
                    self._log(f"\n💾 검증OK 3단계(최종) 저장: {angles}")
                    self._teach_step_count[6] = 1  # 리셋
                    
            elif num == 7:  # 불량 3단계
                if step == 1:
                    VERIFY_DEFECT_STEP1 = angles
                    self._log(f"\n💾 불량 1단계 저장: {angles}")
                    self._log("   → 2단계 위치로 이동 후 다시 [불량[7]] 클릭")
                    self._teach_step_count[7] = 2
                    return
                elif step == 2:
                    VERIFY_DEFECT_STEP2 = angles
                    self._log(f"\n💾 불량 2단계 저장: {angles}")
                    self._log("   → 3단계(최종) 위치로 이동 후 다시 [불량[7]] 클릭")
                    self._teach_step_count[7] = 3
                    return
                else:
                    VERIFY_DEFECT_STEP3 = angles
                    self._log(f"\n💾 불량 3단계(최종) 저장: {angles}")
                    self._teach_step_count[7] = 1  # 리셋
                    
            elif num == 8:  # 핑키 전달 4단계
                if step == 1:
                    PINKY_STEP1 = angles
                    self._log(f"\n💾 핑키전달 1단계 저장: {angles}")
                    self._log("   → 2단계 위치로 이동 후 다시 [핑키[8]] 클릭")
                    self._teach_step_count[8] = 2
                    return
                elif step == 2:
                    PINKY_STEP2 = angles
                    self._log(f"\n💾 핑키전달 2단계 저장: {angles}")
                    self._log("   → 3단계 위치로 이동 후 다시 [핑키[8]] 클릭")
                    self._teach_step_count[8] = 3
                    return
                elif step == 3:
                    PINKY_STEP3 = angles
                    self._log(f"\n💾 핑키전달 3단계 저장: {angles}")
                    self._log("   → 4단계(최종) 위치로 이동 후 다시 [핑키[8]] 클릭")
                    self._teach_step_count[8] = 4
                    return
                else:
                    PINKY_STEP4 = angles
                    self._log(f"\n💾 핑키전달 4단계(최종) 저장: {angles}")
                    self._teach_step_count[8] = 1  # 리셋
                    
            elif num == 9:  # 초기 위치 (1단계만)
                INITIAL_POSITION = angles
                self._log(f"\n💾 초기위치 저장: {angles}")
                
            self._finish_teaching()
        except Exception as e:
            self._log(f"  ❌ {e}")

    def _finish_teaching(self):
        self._log("  ✅ 저장 완료 (재시작 시 초기화됨)")
        mc.focus_all_servos(); time.sleep(0.3)
        self._log("  ✅ 서보 ON (티칭 종료)")
        self.btn_teach_read.setEnabled(False)
        for b in self.teach_btns:
            b.setEnabled(False)

    def _on_angle_exec(self):
        """각도읽기 실행 버튼 - 저장된 각도로 로봇 이동"""
        if mc is None:
            self._log("⚠️ 연결 안됨"); return
        if self.is_running:
            self._log("⚠️ 실행 중"); return
        if not hasattr(self, 'saved_angles') or self.saved_angles is None:
            self._log("⚠️ 먼저 [📖 현재위치] 버튼으로 각도를 읽어주세요")
            return
        
        try:
            self._log("\n▶️ 각도읽기 실행 시작")
            self._log(f"   📍 목표 각도: {self.saved_angles}")
            
            self.is_running = True
            self._set_action_en(False)
            
            self._log(f"   🔄 이동 중...")
            mc.send_angles(self.saved_angles, SPEED)
            
            # 이동 완료 대기
            time.sleep(2.0)
            
            self._log("   ✅ 이동 완료")
            
        except Exception as e:
            self._log(f"  ❌ 오류: {e}")
        finally:
            self.is_running = False
            self._set_action_en(True)


    def _update_conn_ui(self):
        if self.connected:
            self.conn_lbl.setText("● 연결 완료")
            self.conn_lbl.setStyleSheet("color:#2ecc71; font-weight:bold;")
            self.btn_conn.setEnabled(False)
            self.btn_disc.setEnabled(True)
            self.btn_son.setEnabled(True)
            self.btn_soff.setEnabled(True)
            self.btn_teach_off.setEnabled(True)
            self.btn_angle_exec.setEnabled(True)
            self._set_action_en(True)
        else:
            self.conn_lbl.setText("● 연결 안됨")
            self.conn_lbl.setStyleSheet("color:#e74c3c; font-weight:bold;")
            self.btn_conn.setEnabled(True)
            self.btn_disc.setEnabled(False)
            self.btn_son.setEnabled(False)
            self.btn_soff.setEnabled(False)
            self.btn_teach_off.setEnabled(False)
            self.btn_teach_read.setEnabled(False)
            self.btn_angle_exec.setEnabled(False)
            for b in self.teach_btns:
                b.setEnabled(False)
            self._set_action_en(False)

    def _run_seq(self, key):
        if not self.connected:
            self._log("⚠️ 연결 안됨"); return
        if self.is_running:
            self._log("⚠️ 실행 중"); return
        seq = SEQUENCES.get(key)
        if not seq or not seq["fn"]:
            self._log("⚠️ 시퀀스 없음"); return

        self._log(f"\n▶ [{key}] {seq['icon']} {seq['name']}")
        _stop_event.clear()
        self.status_sig.emit("running")

        def worker():
            try:
                seq["fn"]()
                self.log_sig.emit(f"  ✅ [{key}] 완료")
            except Exception as e:
                self.log_sig.emit(f"  ❌ [{key}] 오류: {e}")
                safe_return()
            finally:
                self.status_sig.emit("idle")
        threading.Thread(target=worker, daemon=True).start()

    def _on_full_mode(self):
        if not self.connected or self.is_running:
            return
        self._log("\n▶▶ 전체모드 (1→2→3)")
        _stop_event.clear()
        self.status_sig.emit("running")

        def worker():
            try:
                for k in ["1","2","3"]:
                    if _stop_event.is_set(): break
                    self.log_sig.emit(f"\n  ── {SEQUENCES[k]['name']} ──")
                    SEQUENCES[k]["fn"]()
                self.log_sig.emit("  ✅ 전체모드 완료")
            except Exception as e:
                self.log_sig.emit(f"  ❌ {e}")
                safe_return()
            finally:
                self.status_sig.emit("idle")
        global _full_mode_thread
        _full_mode_thread = threading.Thread(target=worker, daemon=True)
        _full_mode_thread.start()

    def _on_stop(self):
        _stop_event.set()
        self._log("\n⏹ 안전 정지")
        def do():
            safe_return()
            self.log_sig.emit("  ✅ 완료")
            self.status_sig.emit("idle")
        threading.Thread(target=do, daemon=True).start()

    def _on_read(self):
        if mc is None: return
        def do():
            try:
                self.log_sig.emit(f"\n📍 각도: {mc.get_angles()}")
                self.log_sig.emit(f"📍 좌표: {mc.get_coords()}")
            except Exception as e:
                self.log_sig.emit(f"  ❌ {e}")
        threading.Thread(target=do, daemon=True).start()

    @pyqtSlot(str)
    def _on_status(self, s):
        self.is_running = (s == "running")
        self._set_action_en(not self.is_running and self.connected)

    def _set_action_en(self, en):
        for b in self._btns.values():
            b.setEnabled(en)
        self.btn_full.setEnabled(en)
        self.btn_read.setEnabled(en)

    def keyPressEvent(self, ev):
        m = {Qt.Key.Key_1:"1", Qt.Key.Key_2:"2", Qt.Key.Key_3:"3",
             Qt.Key.Key_4:"4", Qt.Key.Key_5:"5", Qt.Key.Key_6:"6",
             Qt.Key.Key_7:"7", Qt.Key.Key_8:"8", Qt.Key.Key_9:"9",
             Qt.Key.Key_0:"0"}
        k = m.get(ev.key())
        if k and k in "0123456789":
            self._run_seq(k)
        else:
            super().keyPressEvent(ev)

    def _log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    @pyqtSlot(str)
    def _append_log(self, msg):
        self._log(msg)

    @staticmethod
    def _lbl(text, size, color, bold=False):
        l = QLabel(text)
        l.setFont(QFont("Segoe UI", size, QFont.Weight.Bold if bold else QFont.Weight.Normal))
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.setStyleSheet(f"color:{color};")
        return l

    @staticmethod
    def _lbl_left(text, size, color):
        l = QLabel(text)
        l.setFont(QFont("Segoe UI", size))
        l.setStyleSheet(f"color:{color};")
        return l

    @staticmethod
    def _btn(text, color, cb):
        b = QPushButton(text)
        b.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        b.setStyleSheet(f"""
            QPushButton {{ background:{color}; color:#fff; border:none; border-radius:8px; }}
            QPushButton:hover {{ background:{color}dd; }}
            QPushButton:pressed {{ background:{color}88; }}
            QPushButton:disabled {{ background:#3d3d3d; color:#666; }}
        """)
        b.clicked.connect(cb)
        return b

    @staticmethod
    def _sep():
        f = QFrame(); f.setFrameShape(QFrame.Shape.HLine)
        f.setStyleSheet("color:#2c3e50;"); f.setFixedHeight(1)
        return f

    @staticmethod
    def _css():
        return """
        QMainWindow, QWidget { background-color:#1e1e2e; }
        QFrame[objectName="card"] {
            background:#2a2a3d; border:1px solid #3a3a52; border-radius:12px;
        }
        QScrollBar:vertical { background:#1e1e2e; width:10px; }
        QScrollBar::handle:vertical { background:#3a3a52; border-radius:5px; min-height:20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(30,30,46))
    p.setColor(QPalette.ColorRole.WindowText, QColor(236,240,241))
    p.setColor(QPalette.ColorRole.Base, QColor(26,26,46))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(30,30,46))
    p.setColor(QPalette.ColorRole.Text, QColor(236,240,241))
    p.setColor(QPalette.ColorRole.BrightText, QColor(255,255,255))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(236,240,241))
    p.setColor(QPalette.ColorRole.Button, QColor(42,42,61))
    app.setPalette(p)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())

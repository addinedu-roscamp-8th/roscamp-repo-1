"""
서빙 로봇 Fleet 모니터링 화면
Closed Network (WiFi: kitchmatics)에서 로봇 상태를 실시간으로 모니터링

Mobile Robots (PinkyPro):
  - pinky_b4bc: 192.168.1.7
  - pinky_e2a8: 192.168.1.6
  - pinky_d29d: 보류중

Cobot Arms (JetCobot):
  - jetcobot_aa1f: 192.168.1.4
  - jetcobot_aa85: 192.168.0.59
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'common'))

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QGridLayout,
    QTabWidget, QFrame, QSplitter, QTextEdit
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPalette
from datetime import datetime

from fleet_client import FleetClient, MockFleetClient
from config import Config


class FleetMonitorWidget(QWidget):
    """서빙 로봇 Fleet 모니터링 위젯"""

    def __init__(self, use_mock=True, parent=None):
        super().__init__(parent)
        self.use_mock = use_mock

        # Load network config
        self.network_config = Config._network_config

        # Fleet 클라이언트 초기화
        if use_mock:
            self.client = MockFleetClient()
        else:
            # FMS TCP Server 주소 (from network_config.yaml)
            self.client = FleetClient(
                host=Config.FMS_HOST,
                port=Config.FMS_PORT
            )

        # UI 설정
        self.setup_ui()

        # 클라이언트 시그널 연결
        self.connect_signals()

        # Main Server에 연결
        self.client.connect()

        # Fleet 상태 조회 타이머 (1초마다)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_fleet_status)
        self.status_timer.start(1000)

        print('[FleetMonitor] 서빙 로봇 모니터링 화면 초기화 완료')

    def setup_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)

        # 헤더
        header_layout = QHBoxLayout()
        header_label = QLabel('Fleet 모니터링 - Closed Network')
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)

        # 네트워크 상태 표시
        self.network_status_label = QLabel(f'WiFi: {Config.WIFI_SSID} | Server: {Config.FMS_HOST}:{Config.FMS_PORT}')
        self.network_status_label.setStyleSheet("color: #666; font-size: 12px;")
        header_layout.addStretch()
        header_layout.addWidget(self.network_status_label)
        layout.addLayout(header_layout)

        # 탭 위젯 생성
        tab_widget = QTabWidget()

        # 탭 1: Mobile Robots (PinkyPro)
        mobile_tab = QWidget()
        mobile_layout = QVBoxLayout(mobile_tab)

        # Mobile Robot 통계
        mobile_stats = self.create_mobile_stats_section()
        mobile_layout.addWidget(mobile_stats)

        # Mobile Robot 테이블
        self.mobile_robot_table = self.create_mobile_robot_table()
        mobile_layout.addWidget(self.mobile_robot_table)
        tab_widget.addTab(mobile_tab, "Mobile Robots (PinkyPro)")

        # 탭 2: Cobot Arms (JetCobot)
        cobot_tab = QWidget()
        cobot_layout = QVBoxLayout(cobot_tab)

        # Cobot 통계
        cobot_stats = self.create_cobot_stats_section()
        cobot_layout.addWidget(cobot_stats)

        # Cobot 테이블
        self.cobot_table = self.create_cobot_table()
        cobot_layout.addWidget(self.cobot_table)
        tab_widget.addTab(cobot_tab, "Cobot Arms (JetCobot)")

        # 탭 3: 전체 통계
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        stats_group = self.create_stats_section()
        stats_layout.addWidget(stats_group)

        # 이벤트 로그
        log_group = QGroupBox('이벤트 로그')
        log_layout = QVBoxLayout(log_group)
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumHeight(200)
        log_layout.addWidget(self.event_log)
        stats_layout.addWidget(log_group)
        stats_layout.addStretch()
        tab_widget.addTab(stats_tab, "전체 통계")

        layout.addWidget(tab_widget)

        # 기존 robot_table 호환성 유지
        self.robot_table = self.mobile_robot_table

        # 하단 버튼
        button_layout = QHBoxLayout()

        # 연결 상태 표시
        self.connection_status = QLabel('연결 대기중...')
        self.connection_status.setStyleSheet("color: orange; font-weight: bold;")
        button_layout.addWidget(self.connection_status)

        button_layout.addStretch()

        refresh_btn = QPushButton('새로고침')
        refresh_btn.clicked.connect(self.refresh_fleet_status)
        button_layout.addWidget(refresh_btn)

        layout.addLayout(button_layout)

    def create_mobile_stats_section(self) -> QGroupBox:
        """Mobile Robot 통계 섹션"""
        group = QGroupBox('Mobile Robot 상태')
        layout = QGridLayout()

        self.mobile_total_label = QLabel('0')
        self.mobile_connected_label = QLabel('0')
        self.mobile_idle_label = QLabel('0')
        self.mobile_busy_label = QLabel('0')

        stat_font = QFont()
        stat_font.setPointSize(20)
        stat_font.setBold(True)

        for label in [self.mobile_total_label, self.mobile_connected_label,
                     self.mobile_idle_label, self.mobile_busy_label]:
            label.setFont(stat_font)
            label.setAlignment(Qt.AlignCenter)

        layout.addWidget(QLabel('전체:'), 0, 0)
        layout.addWidget(self.mobile_total_label, 0, 1)
        layout.addWidget(QLabel('연결됨:'), 0, 2)
        layout.addWidget(self.mobile_connected_label, 0, 3)
        layout.addWidget(QLabel('대기:'), 0, 4)
        layout.addWidget(self.mobile_idle_label, 0, 5)
        layout.addWidget(QLabel('작업중:'), 0, 6)
        layout.addWidget(self.mobile_busy_label, 0, 7)

        group.setLayout(layout)
        return group

    def create_cobot_stats_section(self) -> QGroupBox:
        """Cobot 통계 섹션"""
        group = QGroupBox('Cobot Arm 상태')
        layout = QGridLayout()

        self.cobot_total_label = QLabel('0')
        self.cobot_connected_label = QLabel('0')
        self.cobot_idle_label = QLabel('0')
        self.cobot_cooking_label = QLabel('0')

        stat_font = QFont()
        stat_font.setPointSize(20)
        stat_font.setBold(True)

        for label in [self.cobot_total_label, self.cobot_connected_label,
                     self.cobot_idle_label, self.cobot_cooking_label]:
            label.setFont(stat_font)
            label.setAlignment(Qt.AlignCenter)

        layout.addWidget(QLabel('전체:'), 0, 0)
        layout.addWidget(self.cobot_total_label, 0, 1)
        layout.addWidget(QLabel('연결됨:'), 0, 2)
        layout.addWidget(self.cobot_connected_label, 0, 3)
        layout.addWidget(QLabel('대기:'), 0, 4)
        layout.addWidget(self.cobot_idle_label, 0, 5)
        layout.addWidget(QLabel('조리중:'), 0, 6)
        layout.addWidget(self.cobot_cooking_label, 0, 7)

        group.setLayout(layout)
        return group

    def create_mobile_robot_table(self) -> QTableWidget:
        """Mobile Robot (PinkyPro) 테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            '로봇명', 'Robot ID', 'IP 주소', '상태', '연결',
            '배터리 (V)', '현재 작업', '최종 업데이트'
        ])

        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        header = table.horizontalHeader()
        for i in range(8):
            header.setSectionResizeMode(i, QHeaderView.Stretch if i in [3, 6] else QHeaderView.ResizeToContents)

        # 설정된 Mobile Robot 목록 로드
        mobile_robots = self.network_config.get('mobile_robots', {})
        table.setRowCount(len(mobile_robots))

        for row, (name, cfg) in enumerate(mobile_robots.items()):
            enabled = cfg.get('enabled', False)
            robot_id = cfg.get('robot_id', '-')
            ip_addr = cfg.get('ip_address', '-')

            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(robot_id))
            table.setItem(row, 2, QTableWidgetItem(ip_addr))
            table.setItem(row, 3, QTableWidgetItem('대기중' if enabled else '비활성화'))
            table.setItem(row, 4, QTableWidgetItem('연결 대기...' if enabled else '보류'))
            table.setItem(row, 5, QTableWidgetItem('-'))
            table.setItem(row, 6, QTableWidgetItem('-'))
            table.setItem(row, 7, QTableWidgetItem('-'))

            # 비활성화된 로봇은 회색 처리
            if not enabled:
                for col in range(8):
                    item = table.item(row, col)
                    if item:
                        item.setBackground(QColor(220, 220, 220))
                        item.setForeground(QColor(128, 128, 128))

        return table

    def create_cobot_table(self) -> QTableWidget:
        """Cobot Arm (JetCobot) 테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels([
            '로봇명', 'Robot ID', 'IP 주소', '상태', '연결',
            '온도', '현재 작업', '최종 업데이트'
        ])

        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        header = table.horizontalHeader()
        for i in range(8):
            header.setSectionResizeMode(i, QHeaderView.Stretch if i in [3, 6] else QHeaderView.ResizeToContents)

        # 설정된 Cobot 목록 로드
        cobot_arms = self.network_config.get('cobot_arms', {})
        table.setRowCount(len(cobot_arms))

        for row, (name, cfg) in enumerate(cobot_arms.items()):
            enabled = cfg.get('enabled', False)
            robot_id = cfg.get('robot_id', '-')
            ip_addr = cfg.get('ip_address', '-')

            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(robot_id))
            table.setItem(row, 2, QTableWidgetItem(ip_addr))
            table.setItem(row, 3, QTableWidgetItem('대기중' if enabled else '비활성화'))
            table.setItem(row, 4, QTableWidgetItem('연결 대기...' if enabled else '보류'))
            table.setItem(row, 5, QTableWidgetItem('-'))
            table.setItem(row, 6, QTableWidgetItem('-'))
            table.setItem(row, 7, QTableWidgetItem('-'))

        return table

    def create_stats_section(self) -> QGroupBox:
        """Fleet 통계 섹션 생성"""
        group = QGroupBox('Fleet 통계')
        layout = QGridLayout()

        # 라벨 생성
        self.total_robots_label = QLabel('3')
        self.idle_robots_label = QLabel('0')
        self.busy_robots_label = QLabel('0')
        self.pending_orders_label = QLabel('0')
        self.active_orders_label = QLabel('0')

        # 스타일 설정
        stat_font = QFont()
        stat_font.setPointSize(24)
        stat_font.setBold(True)

        for label in [self.total_robots_label, self.idle_robots_label,
                     self.busy_robots_label, self.pending_orders_label,
                     self.active_orders_label]:
            label.setFont(stat_font)
            label.setAlignment(Qt.AlignCenter)

        # 레이아웃 배치
        row = 0
        layout.addWidget(QLabel('전체 로봇:'), row, 0)
        layout.addWidget(self.total_robots_label, row, 1)
        layout.addWidget(QLabel('대기 로봇:'), row, 2)
        layout.addWidget(self.idle_robots_label, row, 3)

        row += 1
        layout.addWidget(QLabel('작업 중 로봇:'), row, 0)
        layout.addWidget(self.busy_robots_label, row, 1)
        layout.addWidget(QLabel('대기 주문:'), row, 2)
        layout.addWidget(self.pending_orders_label, row, 3)

        row += 1
        layout.addWidget(QLabel('진행 중 주문:'), row, 0)
        layout.addWidget(self.active_orders_label, row, 1)

        group.setLayout(layout)
        return group

    def create_robot_table(self) -> QTableWidget:
        """로봇 상태 테이블 생성"""
        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            '로봇 ID', '상태', '배터리 (V)', '배터리 상태',
            '현재 작업', '최종 업데이트'
        ])

        # 테이블 스타일 설정
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 컬럼 너비 조정
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        # 초기 3개 로봇 행 생성
        table.setRowCount(3)
        for row in range(3):
            robot_id = f'pinky{row + 1}'
            table.setItem(row, 0, QTableWidgetItem(robot_id))
            table.setItem(row, 1, QTableWidgetItem('연결 대기 중...'))
            table.setItem(row, 2, QTableWidgetItem('-'))
            table.setItem(row, 3, QTableWidgetItem('-'))
            table.setItem(row, 4, QTableWidgetItem('-'))
            table.setItem(row, 5, QTableWidgetItem('-'))

        return table

    def connect_signals(self):
        """클라이언트 시그널 연결"""
        self.client.connected_signal.connect(self.on_connected)
        self.client.disconnected_signal.connect(self.on_disconnected)
        self.client.error_signal.connect(self.on_error)
        self.client.fleet_status_updated.connect(self.on_fleet_status_updated)
        self.client.robot_status_updated.connect(self.on_robot_status_updated)

    def on_connected(self):
        """FMS Server 연결 성공"""
        self.connection_status.setText('연결됨')
        self.connection_status.setStyleSheet("color: green; font-weight: bold;")
        self.log_event(f'FMS Server 연결됨 ({Config.FMS_HOST}:{Config.FMS_PORT})')
        print('[FleetMonitor] FMS Server 연결됨')

    def on_disconnected(self):
        """FMS Server 연결 끊김"""
        self.connection_status.setText('연결 끊김')
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.log_event('FMS Server 연결 끊김')
        print('[FleetMonitor] FMS Server 연결 끊김')

    def on_error(self, error_msg: str):
        """에러 발생"""
        self.log_event(f'에러: {error_msg}')
        print(f'[FleetMonitor] 에러: {error_msg}')

    def log_event(self, message: str):
        """이벤트 로그에 메시지 추가"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        if hasattr(self, 'event_log'):
            self.event_log.append(f'[{timestamp}] {message}')

    def on_fleet_status_updated(self, fleet_data: dict):
        """
        Fleet 상태 업데이트 수신

        fleet_data 구조:
        {
            'robots': [
                {
                    'robot_id': 'pinky1',
                    'status': 'IDLE',
                    'battery_voltage': 24.5,
                    'battery_present': True
                },
                ...
            ],
            'pending_orders': 2,
            'active_orders': 1
        }
        """
        # 통계 업데이트
        robots = fleet_data.get('robots', [])
        pending_orders = fleet_data.get('pending_orders', 0)
        active_orders = fleet_data.get('active_orders', 0)

        total_robots = len(robots)
        idle_robots = sum(1 for r in robots if r.get('status') == 'IDLE')
        busy_robots = total_robots - idle_robots

        self.total_robots_label.setText(str(total_robots))
        self.idle_robots_label.setText(str(idle_robots))
        self.busy_robots_label.setText(str(busy_robots))
        self.pending_orders_label.setText(str(pending_orders))
        self.active_orders_label.setText(str(active_orders))

        # 로봇 테이블 업데이트
        self.update_robot_table(robots)

    def on_robot_status_updated(self, robot_data: dict):
        """개별 로봇 상태 업데이트 수신"""
        # Fleet 전체 상태에서 처리하므로 여기서는 로깅만
        print(f'[FleetMonitor] 로봇 상태 업데이트: {robot_data}')

    def update_robot_table(self, robots: list):
        """로봇 테이블 업데이트"""
        for row, robot in enumerate(robots):
            if row >= self.robot_table.rowCount():
                continue

            robot_id = robot.get('robot_id', '-')
            status = robot.get('status', '-')
            battery_voltage = robot.get('battery_voltage', 0.0)
            battery_present = robot.get('battery_present', False)

            # 로봇 ID
            self.robot_table.setItem(row, 0, QTableWidgetItem(robot_id))

            # 상태 (색상 적용)
            status_item = QTableWidgetItem(self.translate_status(status))
            status_item.setBackground(self.get_status_color(status))
            self.robot_table.setItem(row, 1, status_item)

            # 배터리 전압
            battery_text = f'{battery_voltage:.1f}V' if battery_voltage > 0 else '-'
            self.robot_table.setItem(row, 2, QTableWidgetItem(battery_text))

            # 배터리 상태 (색상 적용)
            battery_status = self.get_battery_status(battery_voltage, battery_present)
            battery_item = QTableWidgetItem(battery_status)
            battery_item.setBackground(self.get_battery_color(battery_voltage, battery_present))
            self.robot_table.setItem(row, 3, battery_item)

            # 현재 작업 (TODO: 작업 정보 표시)
            task_text = self.get_task_description(status)
            self.robot_table.setItem(row, 4, QTableWidgetItem(task_text))

            # 최종 업데이트 시간
            current_time = datetime.now().strftime('%H:%M:%S')
            self.robot_table.setItem(row, 5, QTableWidgetItem(current_time))

    def translate_status(self, status: str) -> str:
        """로봇 상태를 한글로 변환"""
        status_map = {
            'IDLE': '대기 중',
            'MOVING_TO_PICKUP': '픽업 이동 중',
            'LOADED': '음식 적재됨',
            'MOVING_TO_TABLE': '테이블 이동 중',
            'DELIVERING': '배달 중',
            'RETURNING': '복귀 중',
            'ERROR': '에러'
        }
        return status_map.get(status, status)

    def get_status_color(self, status: str) -> QColor:
        """상태에 따른 배경색 반환"""
        color_map = {
            'IDLE': QColor(200, 255, 200),  # 연한 초록
            'MOVING_TO_PICKUP': QColor(255, 255, 200),  # 연한 노랑
            'LOADED': QColor(200, 230, 255),  # 연한 파랑
            'MOVING_TO_TABLE': QColor(255, 230, 200),  # 연한 주황
            'DELIVERING': QColor(255, 200, 200),  # 연한 빨강
            'RETURNING': QColor(220, 220, 220),  # 연한 회색
            'ERROR': QColor(255, 100, 100)  # 진한 빨강
        }
        return color_map.get(status, QColor(255, 255, 255))

    def get_battery_status(self, voltage: float, present: bool) -> str:
        """배터리 상태 텍스트 반환"""
        if not present:
            return '미연결'
        elif voltage >= 24.0:
            return '충분'
        elif voltage >= 22.0:
            return '보통'
        elif voltage >= 20.0:
            return '부족'
        else:
            return '위험'

    def get_battery_color(self, voltage: float, present: bool) -> QColor:
        """배터리 상태에 따른 색상 반환"""
        if not present:
            return QColor(200, 200, 200)  # 회색
        elif voltage >= 24.0:
            return QColor(200, 255, 200)  # 초록
        elif voltage >= 22.0:
            return QColor(255, 255, 200)  # 노랑
        elif voltage >= 20.0:
            return QColor(255, 200, 100)  # 주황
        else:
            return QColor(255, 100, 100)  # 빨강

    def get_task_description(self, status: str) -> str:
        """상태에 따른 작업 설명 반환"""
        task_map = {
            'IDLE': '작업 대기',
            'MOVING_TO_PICKUP': '픽업 위치로 이동',
            'LOADED': '음식 적재 완료, 배달 대기',
            'MOVING_TO_TABLE': '테이블로 배달 진행',
            'DELIVERING': '고객에게 음식 전달 중',
            'RETURNING': '주차 위치로 복귀',
            'ERROR': '에러 발생, 관리자 개입 필요'
        }
        return task_map.get(status, '-')

    def refresh_fleet_status(self):
        """Fleet 상태 새로고침"""
        if self.client.is_connected:
            self.client.query_fleet_status()

    def closeEvent(self, event):
        """위젯 종료 시 클라이언트 연결 해제"""
        self.status_timer.stop()
        self.client.disconnect()
        event.accept()

"""
서빙 로봇 Fleet 모니터링 화면
3대의 서빙 로봇 상태를 실시간으로 모니터링
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from datetime import datetime

from fleet_client import FleetClient, MockFleetClient


class FleetMonitorWidget(QWidget):
    """서빙 로봇 Fleet 모니터링 위젯"""

    def __init__(self, use_mock=True, parent=None):
        super().__init__(parent)
        self.use_mock = use_mock

        # Fleet 클라이언트 초기화
        if use_mock:
            self.client = MockFleetClient()
        else:
            # TODO: 실제 Main Server IP 주소 설정
            self.client = FleetClient(host='localhost', port=9999)

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
        header_label = QLabel('🚗 서빙 로봇 Fleet 모니터링')
        header_font = QFont()
        header_font.setPointSize(18)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # Fleet 통계 섹션
        stats_group = self.create_stats_section()
        layout.addWidget(stats_group)

        # 로봇 상태 테이블
        self.robot_table = self.create_robot_table()
        layout.addWidget(self.robot_table)

        # 하단 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        refresh_btn = QPushButton('🔄 새로고침')
        refresh_btn.clicked.connect(self.refresh_fleet_status)
        button_layout.addWidget(refresh_btn)

        layout.addLayout(button_layout)

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
        """Main Server 연결 성공"""
        print('[FleetMonitor] Main Server 연결됨')

    def on_disconnected(self):
        """Main Server 연결 끊김"""
        print('[FleetMonitor] Main Server 연결 끊김')

    def on_error(self, error_msg: str):
        """에러 발생"""
        print(f'[FleetMonitor] 에러: {error_msg}')

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

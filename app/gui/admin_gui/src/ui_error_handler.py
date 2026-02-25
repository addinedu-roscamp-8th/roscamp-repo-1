"""
로봇 에러 핸들링 UI 컴포넌트
서빙 오류 감지, 알림, 운영자 개입 인터페이스

Features:
- 실시간 에러 감지 및 표시
- 에러 상세 정보 표시
- 운영자 액션 버튼 (재시도, 복귀, 정지, 해제)
- 에러 히스토리 로그
"""

import sys
import os
from typing import Dict, Callable, Optional
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QGroupBox, QGridLayout,
    QDialog, QTextEdit, QMessageBox, QComboBox, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QBrush, QIcon, QPixmap


class ErrorAlertDialog(QDialog):
    """Error alert dialog showing detailed error information"""

    def __init__(self, robot_id: str, error_type: str, error_message: str,
                 battery_voltage: float = 0.0, pose: Dict = None, parent=None):
        """
        Initialize error alert dialog

        Args:
            robot_id: Robot ID
            error_type: Type of error
            error_message: Error message
            battery_voltage: Robot battery voltage
            pose: Robot pose {x, y, z}
            parent: Parent widget
        """
        super().__init__(parent)
        self.robot_id = robot_id
        self.error_type = error_type
        self.error_message = error_message
        self.battery_voltage = battery_voltage
        self.pose = pose or {}
        self.selected_action = None

        self.setWindowTitle(f"로봇 에러 알림 - {robot_id}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.setup_ui()

    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)

        # Header with robot name and error type
        header_layout = QHBoxLayout()
        robot_label = QLabel(f"로봇: {self.robot_id}")
        robot_font = QFont()
        robot_font.setPointSize(14)
        robot_font.setBold(True)
        robot_label.setFont(robot_font)

        error_type_label = QLabel(f"[{self.error_type}]")
        error_type_color = self._get_error_type_color()
        error_type_label.setStyleSheet(f"color: {error_type_color}; font-weight: bold;")

        header_layout.addWidget(robot_label)
        header_layout.addWidget(error_type_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Error details
        details_group = QGroupBox("에러 상세")
        details_layout = QVBoxLayout()

        # Error message
        msg_label = QLabel("메시지:")
        msg_text = QTextEdit()
        msg_text.setText(self.error_message)
        msg_text.setReadOnly(True)
        msg_text.setMaximumHeight(80)
        details_layout.addWidget(msg_label)
        details_layout.addWidget(msg_text)

        # Battery and position
        info_layout = QGridLayout()
        info_layout.addWidget(QLabel("배터리 (V):"), 0, 0)
        info_layout.addWidget(QLabel(f"{self.battery_voltage:.1f}"), 0, 1)

        if self.pose:
            info_layout.addWidget(QLabel("위치 (X, Y):"), 0, 2)
            x = self.pose.get('x', 0.0)
            y = self.pose.get('y', 0.0)
            info_layout.addWidget(QLabel(f"({x:.2f}, {y:.2f})"), 0, 3)

        details_layout.addLayout(info_layout)
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Operator actions
        action_group = QGroupBox("운영자 액션")
        action_layout = QVBoxLayout()

        # Action selection
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("선택된 액션:"))
        self.action_combo = QComboBox()
        self.action_combo.addItems([
            "선택...",
            "재시도 (RETRY)",
            "복귀 (RETURN_HOME)",
            "정지 (EMERGENCY_STOP)",
            "해제 (CLEAR_ERROR)"
        ])
        self.action_combo.currentIndexChanged.connect(self._on_action_changed)
        select_layout.addWidget(self.action_combo)
        select_layout.addStretch()
        action_layout.addLayout(select_layout)

        # Action description
        self.description_label = QLabel("액션을 선택하세요")
        self.description_label.setStyleSheet("color: #666; font-size: 11px;")
        action_layout.addWidget(self.description_label)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        confirm_btn = QPushButton("확인 (선택한 액션 실행)")
        confirm_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        confirm_btn.clicked.connect(self.accept)
        button_layout.addWidget(confirm_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def _get_error_type_color(self) -> str:
        """Get color for error type"""
        colors = {
            'NAV_FAILED': '#FF5252',      # Red
            'COMM_LOST': '#FF9800',       # Orange
            'LOW_BATTERY': '#FFC107',     # Amber
            'TIMEOUT': '#F44336',         # Deep Red
            'OBSTACLE': '#9C27B0',        # Purple
        }
        return colors.get(self.error_type, '#666666')

    def _on_action_changed(self, index: int):
        """Handle action selection change"""
        descriptions = {
            0: "액션을 선택하세요",
            1: "현재 작업을 다시 시도합니다",
            2: "로봇을 주차 위치로 복귀시킵니다",
            3: "로봇을 긴급 정지합니다 (위험!)",
            4: "에러 상태를 해제합니다"
        }
        self.description_label.setText(descriptions.get(index, ""))

    def get_selected_action(self) -> Optional[str]:
        """Get selected action"""
        action_map = {
            1: 'RETRY',
            2: 'RETURN_HOME',
            3: 'EMERGENCY_STOP',
            4: 'CLEAR_ERROR'
        }
        index = self.action_combo.currentIndex()
        return action_map.get(index)


class ErrorHandlerWidget(QWidget):
    """Robot error handling widget"""

    # Signals
    error_action_triggered = pyqtSignal(str, str)  # robot_id, action

    def __init__(self, parent=None):
        """
        Initialize error handler widget

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.active_errors: Dict[str, Dict] = {}  # {robot_id: error_info}
        self.error_history = []

        self.setup_ui()

        # Timer for periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_error_display)
        self.update_timer.start(1000)  # Update every 1 second

        print('[ErrorHandler] Error handler widget initialized')

    def setup_ui(self):
        """Setup UI"""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel('서빙 에러 관리')
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_layout.addWidget(header_label)

        # Error counter
        self.error_count_label = QLabel('에러: 0')
        self.error_count_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        header_layout.addStretch()
        header_layout.addWidget(self.error_count_label)
        layout.addLayout(header_layout)

        # Active errors section
        errors_group = QGroupBox("활성 에러 (클릭하면 상세 정보)")
        errors_layout = QVBoxLayout()

        self.error_table = QTableWidget()
        self.error_table.setColumnCount(7)
        self.error_table.setHorizontalHeaderLabels([
            '로봇', '에러 타입', '메시지', '배터리 (V)', '위치', '발생 시간', '액션'
        ])
        self.error_table.setAlternatingRowColors(True)
        self.error_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.error_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.error_table.setMaximumHeight(200)
        self.error_table.cellDoubleClicked.connect(self._on_error_row_clicked)

        header = self.error_table.horizontalHeader()
        for i in range(7):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        errors_layout.addWidget(self.error_table)
        errors_group.setLayout(errors_layout)
        layout.addWidget(errors_group)

        # Quick action buttons
        quick_action_group = QGroupBox("빠른 액션 (선택된 로봇)")
        quick_action_layout = QHBoxLayout()

        retry_btn = QPushButton("재시도 (RETRY)")
        retry_btn.setStyleSheet("background-color: #2196F3; color: white;")
        retry_btn.clicked.connect(lambda: self._quick_action_triggered('RETRY'))
        quick_action_layout.addWidget(retry_btn)

        return_btn = QPushButton("복귀 (RETURN_HOME)")
        return_btn.setStyleSheet("background-color: #FF9800; color: white;")
        return_btn.clicked.connect(lambda: self._quick_action_triggered('RETURN_HOME'))
        quick_action_layout.addWidget(return_btn)

        stop_btn = QPushButton("정지 (EMERGENCY_STOP)")
        stop_btn.setStyleSheet("background-color: #F44336; color: white;")
        stop_btn.clicked.connect(lambda: self._quick_action_triggered('EMERGENCY_STOP'))
        quick_action_layout.addWidget(stop_btn)

        clear_btn = QPushButton("해제 (CLEAR_ERROR)")
        clear_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        clear_btn.clicked.connect(lambda: self._quick_action_triggered('CLEAR_ERROR'))
        quick_action_layout.addWidget(clear_btn)

        quick_action_group.setLayout(quick_action_layout)
        layout.addWidget(quick_action_group)

        # Error history section
        history_group = QGroupBox("에러 히스토리 (최근 20개)")
        history_layout = QVBoxLayout()

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels([
            '로봇', '에러 타입', '메시지', '발생 시간', '상태'
        ])
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setMaximumHeight(150)

        header = self.history_table.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.Stretch)

        history_layout.addWidget(self.history_table)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

    def register_error(self, robot_id: str, error_type: str, error_message: str,
                      battery_voltage: float = 0.0, pose: Dict = None):
        """
        Register a robot error

        Args:
            robot_id: Robot ID
            error_type: Type of error
            error_message: Error message
            battery_voltage: Battery voltage
            pose: Robot pose {x, y, z}
        """
        error_info = {
            'robot_id': robot_id,
            'error_type': error_type,
            'message': error_message,
            'battery_voltage': battery_voltage,
            'pose': pose or {},
            'timestamp': datetime.now(),
            'resolved': False
        }

        self.active_errors[robot_id] = error_info
        self.error_history.append(error_info)

        # Keep only last 20 items in history
        if len(self.error_history) > 20:
            self.error_history.pop(0)

        print(f'[ErrorHandler] Error registered: {robot_id} - {error_type}')

        # Show alert dialog
        self._show_error_alert(robot_id, error_type, error_message, battery_voltage, pose)

    def clear_error(self, robot_id: str):
        """
        Clear error for robot

        Args:
            robot_id: Robot ID
        """
        if robot_id in self.active_errors:
            self.active_errors[robot_id]['resolved'] = True
            del self.active_errors[robot_id]
            print(f'[ErrorHandler] Error cleared for {robot_id}')

    def update_error_display(self):
        """Update error table display"""
        # Update active errors table
        self.error_table.setRowCount(len(self.active_errors))

        for row, (robot_id, error_info) in enumerate(self.active_errors.items()):
            # Robot ID
            robot_item = QTableWidgetItem(robot_id)
            robot_item.setBackground(QBrush(QColor('#FFE0E0')))
            self.error_table.setItem(row, 0, robot_item)

            # Error type
            error_type = error_info['error_type']
            type_item = QTableWidgetItem(error_type)
            color = self._get_error_color(error_type)
            type_item.setBackground(QBrush(color))
            self.error_table.setItem(row, 1, type_item)

            # Message
            msg = error_info['message'][:60] + '...' if len(error_info['message']) > 60 else error_info['message']
            self.error_table.setItem(row, 2, QTableWidgetItem(msg))

            # Battery
            battery = error_info.get('battery_voltage', 0.0)
            battery_item = QTableWidgetItem(f"{battery:.1f}")
            if battery < 20.0:
                battery_item.setBackground(QBrush(QColor('#FFEB3B')))
            self.error_table.setItem(row, 3, battery_item)

            # Position
            pose = error_info.get('pose', {})
            x = pose.get('x', 0.0)
            y = pose.get('y', 0.0)
            self.error_table.setItem(row, 4, QTableWidgetItem(f"({x:.2f}, {y:.2f})"))

            # Timestamp
            ts = error_info['timestamp'].strftime('%H:%M:%S')
            self.error_table.setItem(row, 5, QTableWidgetItem(ts))

            # Action button
            action_btn = QPushButton('상세 정보')
            action_btn.clicked.connect(lambda checked, rid=robot_id: self._show_error_alert_for_robot(rid))
            self.error_table.setCellWidget(row, 6, action_btn)

        # Update error count
        error_count = len(self.active_errors)
        self.error_count_label.setText(f'에러: {error_count}')
        if error_count > 0:
            self.error_count_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        else:
            self.error_count_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")

        # Update history table
        self.history_table.setRowCount(len(self.error_history))

        for row, error_info in enumerate(self.error_history[-20:]):
            self.history_table.setItem(row, 0, QTableWidgetItem(error_info['robot_id']))

            type_item = QTableWidgetItem(error_info['error_type'])
            color = self._get_error_color(error_info['error_type'])
            type_item.setBackground(QBrush(color))
            self.history_table.setItem(row, 1, type_item)

            msg = error_info['message'][:50] + '...' if len(error_info['message']) > 50 else error_info['message']
            self.history_table.setItem(row, 2, QTableWidgetItem(msg))

            ts = error_info['timestamp'].strftime('%H:%M:%S')
            self.history_table.setItem(row, 3, QTableWidgetItem(ts))

            status = '해결됨' if error_info['resolved'] else '활성'
            status_item = QTableWidgetItem(status)
            if error_info['resolved']:
                status_item.setBackground(QBrush(QColor('#C8E6C9')))
            else:
                status_item.setBackground(QBrush(QColor('#FFE0B2')))
            self.history_table.setItem(row, 4, status_item)

    def _show_error_alert(self, robot_id: str, error_type: str, error_message: str,
                         battery_voltage: float, pose: Dict):
        """Show error alert dialog"""
        dialog = ErrorAlertDialog(robot_id, error_type, error_message, battery_voltage, pose, self)
        if dialog.exec_() == QDialog.Accepted:
            action = dialog.get_selected_action()
            if action:
                self._execute_action(robot_id, action)

    def _show_error_alert_for_robot(self, robot_id: str):
        """Show error alert for specific robot"""
        if robot_id in self.active_errors:
            error = self.active_errors[robot_id]
            self._show_error_alert(robot_id, error['error_type'], error['message'],
                                 error.get('battery_voltage', 0.0), error.get('pose'))

    def _on_error_row_clicked(self, row: int, col: int):
        """Handle error table row click"""
        if row >= 0 and row < self.error_table.rowCount():
            robot_item = self.error_table.item(row, 0)
            if robot_item:
                robot_id = robot_item.text()
                self._show_error_alert_for_robot(robot_id)

    def _quick_action_triggered(self, action: str):
        """Handle quick action button"""
        selected_rows = self.error_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "경고", "로봇을 선택하세요")
            return

        row = selected_rows[0].row()
        robot_item = self.error_table.item(row, 0)
        if robot_item:
            robot_id = robot_item.text()
            self._execute_action(robot_id, action)

    def _execute_action(self, robot_id: str, action: str):
        """Execute operator action"""
        # Confirm action (especially for dangerous actions)
        if action == 'EMERGENCY_STOP':
            reply = QMessageBox.critical(self, "확인",
                f"로봇 {robot_id}을(를) 긴급 정지하시겠습니까?\n(위험한 작업입니다!)",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        self.error_action_triggered.emit(robot_id, action)
        QMessageBox.information(self, "성공", f"액션 '{action}'이(가) {robot_id}에 전송되었습니다")

    def _get_error_color(self, error_type: str) -> QColor:
        """Get color for error type"""
        colors = {
            'NAV_FAILED': QColor('#FFCDD2'),      # Light red
            'COMM_LOST': QColor('#FFE0B2'),       # Light orange
            'LOW_BATTERY': QColor('#FFF9C4'),     # Light yellow
            'TIMEOUT': QColor('#EF9A9A'),         # Red
            'OBSTACLE': QColor('#E1BEE7'),        # Light purple
        }
        return colors.get(error_type, QColor('#E0E0E0'))

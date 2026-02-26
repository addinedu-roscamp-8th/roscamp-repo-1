#!/usr/bin/env python3
"""
Customer GUI 푸시 알림 테스트
Main Server 없이 로컬에서 메시지를 시뮬레이션하여 테스트
"""
import sys
import os
import json
import socket
import threading
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel
from PyQt5.QtCore import pyqtSignal, QTimer

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(__file__))
from src.tcp_client import OrderServiceClient, MockOrderServiceClient
from common import Config, Order, MenuItem


class TestWindow(QWidget):
    """푸시 알림 테스트 윈도우"""

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.order_client = None
        self.test_server = None

    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle('Customer GUI 푸시 알림 테스트')
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        # 상태 텍스트
        self.status_label = QLabel('테스트 준비 중...')
        layout.addWidget(self.status_label)

        # 로그 텍스트
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # 버튼
        self.connect_btn = QPushButton('1. 서버 연결')
        self.connect_btn.clicked.connect(self.on_connect)
        layout.addWidget(self.connect_btn)

        self.send_btn = QPushButton('2. 푸시 알림 전송')
        self.send_btn.clicked.connect(self.on_send_notification)
        self.send_btn.setEnabled(False)
        layout.addWidget(self.send_btn)

        self.disconnect_btn = QPushButton('3. 연결 종료')
        self.disconnect_btn.clicked.connect(self.on_disconnect)
        self.disconnect_btn.setEnabled(False)
        layout.addWidget(self.disconnect_btn)

        self.setLayout(layout)

    def log(self, message: str):
        """로그 추가"""
        print(message)
        self.log_text.append(message)

    def on_connect(self):
        """서버 연결"""
        self.log('[Test] 서버에 연결 중...')

        # TCP 클라이언트 생성
        self.order_client = OrderServiceClient()

        # 시그널 연결
        self.order_client.delivery_notification_signal.connect(
            self.on_notification_received
        )
        self.order_client.error_signal.connect(self.on_error)

        # 연결 시도
        if self.order_client.connect():
            self.log('[Test] 서버 연결 성공')
            self.status_label.setText('상태: 연결됨 (푸시 알림 대기 중)')
            self.connect_btn.setEnabled(False)
            self.send_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(True)

            # 테스트 메시지 전송 시뮬레이션
            self.start_test_simulation()
        else:
            self.log('[Test] 서버 연결 실패')
            self.status_label.setText('상태: 연결 실패')

    def start_test_simulation(self):
        """테스트 시뮬레이션 시작"""
        self.log('[Test] 3초 후 푸시 알림 시뮬레이션 시작...')
        QTimer.singleShot(3000, self.on_send_notification)

    def on_send_notification(self):
        """푸시 알림 전송"""
        self.log('[Test] 푸시 알림을 Main Server에서 수신했다고 가정')

        # 시뮬레이션 메시지
        notification = {
            'type': 'delivery_notification',
            'data': {
                'order_id': 'ORD-TEST-001',
                'status': 'AT_TABLE',
                'table_number': Config.TABLE_NUMBER,
                'robot_id': 'robot-01',
                'timestamp': '2024-02-25T12:34:56'
            }
        }

        self.log(f'[Test] 알림 전송: {json.dumps(notification, indent=2, ensure_ascii=False)}')

        # 직접 시그널 emit (실제 서버 대신)
        if self.order_client:
            self.order_client.delivery_notification_signal.emit(notification)

    def on_notification_received(self, notification: dict):
        """알림 수신"""
        self.log('[Test] === 배달 알림 수신됨 ===')
        self.log(json.dumps(notification, indent=2, ensure_ascii=False))

        data = notification.get('data', {})
        self.log(f"[Test] Order ID: {data.get('order_id')}")
        self.log(f"[Test] Table: {data.get('table_number')}")
        self.log(f"[Test] Robot: {data.get('robot_id')}")
        self.log('[Test] === 알림 처리 완료 ===')

        self.status_label.setText('상태: 알림 수신됨')

    def on_error(self, error_msg: str):
        """오류"""
        self.log(f'[Test] 오류: {error_msg}')
        self.status_label.setText(f'상태: 오류 - {error_msg}')

    def on_disconnect(self):
        """연결 종료"""
        self.log('[Test] 연결 종료 중...')

        if self.order_client:
            self.order_client.disconnect()
            self.log('[Test] 연결 종료됨')

        self.status_label.setText('상태: 연결 종료')
        self.connect_btn.setEnabled(True)
        self.send_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)

    def closeEvent(self, event):
        """종료"""
        if self.order_client:
            self.order_client.disconnect()
        event.accept()


def main():
    """메인 함수"""
    app = QApplication(sys.argv)

    window = TestWindow()
    window.show()

    print('Customer GUI 푸시 알림 테스트 시작')
    print(f'테이블 번호: {Config.TABLE_NUMBER}')
    print(f'주문 MS 주소: {Config.get_order_ms_address()}')

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

"""
조리 상태 모니터링
SR-12: 조리 모니터링
SR-13: 조리 완료 알림, 음식 검수
SR-15: 서빙 출발 제어
"""
import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QApplication, QTableWidgetItem, QMessageBox
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config
from tcp_client import MockAdminServiceClient, AdminServiceClient


class CookingMonitorWidget(QWidget):
    """조리 상태 모니터링 위젯"""

    def __init__(self, use_mock=True):
        super().__init__()
        self.use_mock = use_mock
        self.current_filter = 'cooking'
        self.selected_order_id = None
        self.orders_data = []

        # TCP 클라이언트 초기화
        if use_mock:
            self.client = MockAdminServiceClient()
        else:
            self.client = AdminServiceClient()

        self.setup_ui()
        self.connect_signals()
        self.connect_to_server()

        # 자동 새로고침 타이머 (3초마다)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_orders)
        self.refresh_timer.start(3000)

        # 초기 데이터 로드
        self.load_orders()

    def setup_ui(self):
        """UI 초기화"""
        ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'cooking_monitor.ui')
        loadUi(ui_path, self)

        # 테이블 컬럼 너비 설정
        self.table_cooking.setColumnWidth(0, 120)  # 주문번호
        self.table_cooking.setColumnWidth(1, 80)   # 테이블
        self.table_cooking.setColumnWidth(2, 300)  # 메뉴
        self.table_cooking.setColumnWidth(3, 120)  # 조리 상태
        self.table_cooking.setColumnWidth(4, 120)  # 경과 시간

    def connect_signals(self):
        """시그널 연결"""
        # 필터 버튼
        self.btn_filter_cooking.clicked.connect(lambda: self.set_filter('cooking'))
        self.btn_filter_ready.clicked.connect(lambda: self.set_filter('ready'))
        self.btn_filter_inspected.clicked.connect(lambda: self.set_filter('inspected'))

        # 새로고침 버튼
        self.btn_refresh.clicked.connect(self.load_orders)

        # 액션 버튼
        self.btn_confirm_inspection.clicked.connect(self.confirm_inspection)
        self.btn_start_serving.clicked.connect(self.start_serving)

        # 테이블 선택 변경
        self.table_cooking.itemSelectionChanged.connect(self.on_selection_changed)

        # TCP 클라이언트 시그널
        self.client.order_updated_signal.connect(self.on_order_updated)
        self.client.error_signal.connect(self.on_error)

    def connect_to_server(self):
        """서버 연결"""
        if self.client.connect():
            print('[CookingMonitor] 서버 연결 성공')
        else:
            print('[CookingMonitor] 서버 연결 실패')

    def set_filter(self, status):
        """필터 설정"""
        self.current_filter = status

        # 버튼 체크 상태 업데이트
        self.btn_filter_cooking.setChecked(status == 'cooking')
        self.btn_filter_ready.setChecked(status == 'ready')
        self.btn_filter_inspected.setChecked(status == 'inspected')

        self.load_orders()

    def load_orders(self):
        """주문 목록 로드"""
        orders = self.client.get_orders(status=self.current_filter)
        self.orders_data = orders
        self.display_orders(orders)

    def display_orders(self, orders):
        """주문 목록 표시"""
        self.table_cooking.setRowCount(0)

        for order in orders:
            row = self.table_cooking.rowCount()
            self.table_cooking.insertRow(row)

            # 주문번호
            self.table_cooking.setItem(row, 0, QTableWidgetItem(order['order_id']))

            # 테이블 번호
            self.table_cooking.setItem(row, 1, QTableWidgetItem(str(order['table_number'])))

            # 메뉴
            items = order.get('items', [])
            menu_text = ', '.join([
                f"{item['menu_name']}"
                f"{' (' + item.get('sauce', '') + ')' if item.get('sauce') else ''}"
                f" x{item['quantity']}"
                for item in items
            ])
            self.table_cooking.setItem(row, 2, QTableWidgetItem(menu_text))

            # 조리 상태
            status = order['status']
            status_text = self.get_status_text(status)
            status_item = QTableWidgetItem(status_text)

            # 상태별 색상
            if status == 'cooking':
                status_item.setBackground(QColor(255, 204, 128))  # 주황색
            elif status == 'ready':
                status_item.setBackground(QColor(165, 214, 167))  # 녹색
            elif status == 'inspected':
                status_item.setBackground(QColor(144, 202, 249))  # 파란색

            self.table_cooking.setItem(row, 3, status_item)

            # 경과 시간
            created_at = order.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    elapsed = datetime.now() - dt
                    minutes = int(elapsed.total_seconds() / 60)
                    time_text = f'{minutes}분'
                except:
                    time_text = '-'
            else:
                time_text = '-'

            self.table_cooking.setItem(row, 4, QTableWidgetItem(time_text))

    def get_status_text(self, status):
        """상태 코드를 한글 텍스트로 변환"""
        status_map = {
            'cooking': '조리중',
            'ready': '조리완료',
            'inspected': '검수완료'
        }
        return status_map.get(status, status)

    def on_selection_changed(self):
        """테이블 선택 변경 시"""
        selected_rows = self.table_cooking.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            order_id_item = self.table_cooking.item(row, 0)
            if order_id_item:
                self.selected_order_id = order_id_item.text()

                # 선택된 주문 가져오기
                order = next((o for o in self.orders_data if o['order_id'] == self.selected_order_id), None)
                if order:
                    status = order['status']

                    # 상태에 따라 버튼 활성화
                    self.btn_confirm_inspection.setEnabled(status == 'ready')
                    self.btn_start_serving.setEnabled(status == 'inspected')
        else:
            self.selected_order_id = None
            self.btn_confirm_inspection.setEnabled(False)
            self.btn_start_serving.setEnabled(False)

    def confirm_inspection(self):
        """검수 완료"""
        if not self.selected_order_id:
            return

        reply = QMessageBox.question(
            self, '확인', f'주문 {self.selected_order_id}의 검수를 완료하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.client.confirm_inspection(self.selected_order_id):
                QMessageBox.information(self, '성공', '검수가 완료되었습니다.')
                # 검수완료 필터로 자동 전환
                self.set_filter('inspected')
            else:
                QMessageBox.warning(self, '실패', '검수 완료 처리에 실패했습니다.')

    def start_serving(self):
        """서빙 출발"""
        if not self.selected_order_id:
            return

        reply = QMessageBox.question(
            self, '확인', f'주문 {self.selected_order_id}의 서빙을 시작하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.client.start_serving(self.selected_order_id):
                QMessageBox.information(self, '성공', '서빙이 시작되었습니다.\n주문 관제 대시보드에서 배달 상태를 확인하세요.')
                self.load_orders()
            else:
                QMessageBox.warning(self, '실패', '서빙 출발 처리에 실패했습니다.')

    def on_order_updated(self, order):
        """주문 업데이트 알림"""
        status = order.get('status')
        if status == 'ready':
            # 조리 완료 알림
            QMessageBox.information(
                self, '조리 완료 알림',
                f"주문 {order.get('order_id')}의 조리가 완료되었습니다!"
            )

    def on_error(self, error_msg):
        """에러 발생 시"""
        print(f'[CookingMonitor] 에러: {error_msg}')

    def closeEvent(self, event):
        """위젯 종료 시"""
        self.refresh_timer.stop()
        self.client.disconnect()
        event.accept()


# 테스트 코드
if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = CookingMonitorWidget(use_mock=True)
    window.show()

    sys.exit(app.exec_())

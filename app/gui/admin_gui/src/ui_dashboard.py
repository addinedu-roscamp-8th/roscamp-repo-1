"""
주문 관제 대시보드
SR-07: 주문 모니터링, 정렬, 강제 개입
SR-08: 주문 취소
"""
import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QApplication, QTableWidgetItem, QMessageBox, QInputDialog
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config
from tcp_client import MockAdminServiceClient, AdminServiceClient


class DashboardWidget(QWidget):
    """주문 관제 대시보드 위젯"""

    def __init__(self, use_mock=True):
        super().__init__()
        self.use_mock = use_mock
        self.current_filter = None
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

        # 자동 새로고침 타이머 (5초마다)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_orders)
        self.refresh_timer.start(5000)

        # 초기 데이터 로드
        self.load_orders()

    def setup_ui(self):
        """UI를 초기화합니다."""
        # UI 파일 로드
        ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'dashboard.ui')
        loadUi(ui_path, self)

        # 테이블 컬럼 너비 설정
        self.table_orders.setColumnWidth(0, 120)  # 주문번호
        self.table_orders.setColumnWidth(1, 80)   # 테이블
        self.table_orders.setColumnWidth(2, 180)  # 주문시간
        self.table_orders.setColumnWidth(3, 120)  # 상태
        self.table_orders.setColumnWidth(4, 100)  # 메뉴 수량
        self.table_orders.setColumnWidth(5, 120)  # 금액

    def connect_signals(self):
        """시그널을 연결합니다."""
        # 필터 버튼
        self.btn_filter_all.clicked.connect(lambda: self.set_filter(None))
        self.btn_filter_pending.clicked.connect(lambda: self.set_filter('pending'))
        self.btn_filter_cooking.clicked.connect(lambda: self.set_filter('cooking'))
        self.btn_filter_ready.clicked.connect(lambda: self.set_filter('ready'))
        self.btn_filter_delivering.clicked.connect(lambda: self.set_filter('delivering'))

        # 새로고침 버튼
        self.btn_refresh.clicked.connect(self.load_orders)

        # 액션 버튼
        self.btn_view_detail.clicked.connect(self.view_order_detail)
        self.btn_update_status.clicked.connect(self.update_order_status)
        self.btn_halt.clicked.connect(self.halt_order)
        self.btn_cancel.clicked.connect(self.cancel_order)

        # 테이블 선택 변경
        self.table_orders.itemSelectionChanged.connect(self.on_selection_changed)

        # TCP 클라이언트 시그널
        self.client.order_updated_signal.connect(self.on_order_updated)
        self.client.error_signal.connect(self.on_error)

    def connect_to_server(self):
        """서버에 연결합니다."""
        if self.client.connect():
            print('[Dashboard] 서버 연결 성공')
        else:
            print('[Dashboard] 서버 연결 실패')

    def set_filter(self, status):
        """필터를 설정합니다."""
        self.current_filter = status

        # 버튼 체크 상태 업데이트
        self.btn_filter_all.setChecked(status is None)
        self.btn_filter_pending.setChecked(status == 'pending')
        self.btn_filter_cooking.setChecked(status == 'cooking')
        self.btn_filter_ready.setChecked(status == 'ready')
        self.btn_filter_delivering.setChecked(status == 'delivering')

        self.load_orders()

    def load_orders(self):
        """주문 목록을 로드합니다."""
        orders = self.client.get_orders(status=self.current_filter)
        self.orders_data = orders
        self.display_orders(orders)

    def display_orders(self, orders):
        """주문 목록을 표시합니다."""
        self.table_orders.setRowCount(0)

        for order in orders:
            row = self.table_orders.rowCount()
            self.table_orders.insertRow(row)

            # 주문번호
            self.table_orders.setItem(row, 0, QTableWidgetItem(order['order_id']))

            # 테이블 번호
            self.table_orders.setItem(row, 1, QTableWidgetItem(str(order['table_number'])))

            # 주문시간
            created_at = order.get('created_at', '')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at)
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = created_at
            else:
                time_str = '-'
            self.table_orders.setItem(row, 2, QTableWidgetItem(time_str))

            # 상태
            status = order['status']
            status_text = self.get_status_text(status)
            status_item = QTableWidgetItem(status_text)

            # 상태별 색상
            if status == 'pending' or status == 'confirmed':
                status_item.setBackground(QColor(255, 245, 157))  # 노란색
            elif status == 'cooking':
                status_item.setBackground(QColor(255, 204, 128))  # 주황색
            elif status == 'ready' or status == 'inspected':
                status_item.setBackground(QColor(165, 214, 167))  # 녹색
            elif status == 'delivering':
                status_item.setBackground(QColor(144, 202, 249))  # 파란색
            elif status == 'delivered' or status == 'completed':
                status_item.setBackground(QColor(200, 200, 200))  # 회색
            elif status == 'cancelled' or status == 'halted':
                status_item.setBackground(QColor(239, 154, 154))  # 빨간색

            self.table_orders.setItem(row, 3, status_item)

            # 메뉴 수량
            items_count = len(order.get('items', []))
            self.table_orders.setItem(row, 4, QTableWidgetItem(f'{items_count}개'))

            # 금액
            total_price = order.get('total_price', 0)
            self.table_orders.setItem(row, 5, QTableWidgetItem(f'{total_price:,}원'))

        # 주문 개수 업데이트
        self.label_order_count.setText(f'주문: {len(orders)}건')

    def get_status_text(self, status):
        """상태 코드를 한글 텍스트로 변환합니다."""
        status_map = {
            'pending': '대기중',
            'confirmed': '확인됨',
            'cooking': '조리중',
            'ready': '조리완료',
            'inspected': '검수완료',
            'delivering': '배달중',
            'delivered': '배달완료',
            'completed': '수령완료',
            'cancelled': '취소됨',
            'halted': '일시중지'
        }
        return status_map.get(status, status)

    def on_selection_changed(self):
        """테이블 선택 변경 시 호출됩니다."""
        selected_rows = self.table_orders.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            order_id_item = self.table_orders.item(row, 0)
            if order_id_item:
                self.selected_order_id = order_id_item.text()

                # 액션 버튼 활성화
                self.btn_view_detail.setEnabled(True)
                self.btn_update_status.setEnabled(True)
                self.btn_halt.setEnabled(True)
                self.btn_cancel.setEnabled(True)
        else:
            self.selected_order_id = None
            self.btn_view_detail.setEnabled(False)
            self.btn_update_status.setEnabled(False)
            self.btn_halt.setEnabled(False)
            self.btn_cancel.setEnabled(False)

    def view_order_detail(self):
        """주문 상세보기를 표시합니다."""
        if not self.selected_order_id:
            return

        order = self.client.get_order(self.selected_order_id)
        if not order:
            QMessageBox.warning(self, '오류', '주문 정보를 불러올 수 없습니다.')
            return

        # 주문 상세 정보 다이얼로그
        items_text = '\n'.join([
            f"- {item['menu_name']} x{item['quantity']}"
            f"{' (소스: ' + item.get('sauce', '') + ')' if item.get('sauce') else ''}"
            f" = {item['subtotal']:,}원"
            for item in order.get('items', [])
        ])

        detail_text = f"""
주문번호: {order['order_id']}
테이블: {order['table_number']}
상태: {self.get_status_text(order['status'])}
주문시간: {order.get('created_at', '-')}

[주문 내역]
{items_text}

총 금액: {order['total_price']:,}원
        """

        QMessageBox.information(self, '주문 상세', detail_text)

    def update_order_status(self):
        """주문 상태를 변경합니다."""
        if not self.selected_order_id:
            return

        # 상태 선택 다이얼로그
        statuses = ['confirmed', 'cooking', 'ready', 'inspected', 'delivering', 'delivered', 'completed']
        status_texts = [self.get_status_text(s) for s in statuses]

        status_text, ok = QInputDialog.getItem(
            self, '상태 변경', '새로운 상태를 선택하세요:', status_texts, 0, False
        )

        if ok and status_text:
            # 텍스트를 상태 코드로 변환
            status_idx = status_texts.index(status_text)
            new_status = statuses[status_idx]

            if self.client.update_order_status(self.selected_order_id, new_status):
                QMessageBox.information(self, '성공', f'주문 상태가 "{status_text}"(으)로 변경되었습니다.')
                self.load_orders()
            else:
                QMessageBox.warning(self, '실패', '주문 상태 변경에 실패했습니다.')

    def halt_order(self):
        """주문을 일시중지합니다."""
        if not self.selected_order_id:
            return

        reply = QMessageBox.question(
            self, '확인', f'주문 {self.selected_order_id}을(를) 일시중지하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.client.halt_order(self.selected_order_id):
                QMessageBox.information(self, '성공', '주문이 일시중지되었습니다.')
                self.load_orders()
            else:
                QMessageBox.warning(self, '실패', '주문 일시중지에 실패했습니다.')

    def cancel_order(self):
        """주문을 취소합니다."""
        if not self.selected_order_id:
            return

        reason, ok = QInputDialog.getText(
            self, '주문 취소', '취소 사유를 입력하세요:'
        )

        if ok:
            reply = QMessageBox.question(
                self, '확인', f'주문 {self.selected_order_id}을(를) 취소하시겠습니까?',
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                if self.client.cancel_order(self.selected_order_id, reason):
                    QMessageBox.information(self, '성공', '주문이 취소되었습니다.')
                    self.load_orders()
                else:
                    QMessageBox.warning(self, '실패', '주문 취소에 실패했습니다.')

    def on_order_updated(self, order):
        """주문 업데이트 알림을 처리합니다."""
        print(f'[Dashboard] 주문 업데이트: {order.get("order_id")} -> {order.get("status")}')
        # 자동으로 목록 새로고침은 타이머가 처리함

    def on_error(self, error_msg):
        """에러 발생 시 호출됩니다."""
        print(f'[Dashboard] 에러: {error_msg}')

    def closeEvent(self, event):
        """위젯 종료 시 호출됩니다."""
        self.refresh_timer.stop()
        self.client.disconnect()
        event.accept()


# 테스트 코드
if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = DashboardWidget(use_mock=True)
    window.show()

    sys.exit(app.exec_())

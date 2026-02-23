"""
재고 관리
SR-19: 재고 알림, 재고 수정
SR-20: 재고 조회
"""
import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QApplication, QTableWidgetItem, QMessageBox, QInputDialog
)
from PyQt5.uic import loadUi
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config
from tcp_client import MockAdminServiceClient, AdminServiceClient


class StockManagementWidget(QWidget):
    """재고 관리 위젯"""

    def __init__(self, use_mock=True):
        super().__init__()
        self.use_mock = use_mock
        self.show_low_stock_only = False
        self.selected_stock_id = None
        self.stocks_data = []

        # TCP 클라이언트 초기화
        if use_mock:
            self.client = MockAdminServiceClient()
        else:
            self.client = AdminServiceClient()

        self.setup_ui()
        self.connect_signals()
        self.connect_to_server()

        # 자동 새로고침 타이머 (10초마다)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_stocks)
        self.refresh_timer.start(10000)

        # 초기 데이터 로드
        self.load_stocks()

    def setup_ui(self):
        """UI 초기화"""
        ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'stock_management.ui')
        loadUi(ui_path, self)

        # 테이블 컬럼 너비 설정
        self.table_stocks.setColumnWidth(0, 100)  # 재고 ID
        self.table_stocks.setColumnWidth(1, 200)  # 재료명
        self.table_stocks.setColumnWidth(2, 120)  # 현재 수량
        self.table_stocks.setColumnWidth(3, 120)  # 임계값
        self.table_stocks.setColumnWidth(4, 80)   # 단위
        self.table_stocks.setColumnWidth(5, 120)  # 상태
        self.table_stocks.setColumnWidth(6, 200)  # 공급업체

    def connect_signals(self):
        """시그널 연결"""
        # 필터 버튼
        self.btn_filter_all.clicked.connect(lambda: self.set_filter(False))
        self.btn_filter_low.clicked.connect(lambda: self.set_filter(True))

        # 새로고침 버튼
        self.btn_refresh.clicked.connect(self.load_stocks)

        # 액션 버튼
        self.btn_update_stock.clicked.connect(self.update_stock)

        # 테이블 선택 변경
        self.table_stocks.itemSelectionChanged.connect(self.on_selection_changed)

        # TCP 클라이언트 시그널
        self.client.stock_alert_signal.connect(self.on_stock_alert)
        self.client.error_signal.connect(self.on_error)

    def connect_to_server(self):
        """서버 연결"""
        if self.client.connect():
            print('[StockManagement] 서버 연결 성공')
        else:
            print('[StockManagement] 서버 연결 실패')

    def set_filter(self, low_stock_only):
        """필터 설정"""
        self.show_low_stock_only = low_stock_only

        # 버튼 체크 상태 업데이트
        self.btn_filter_all.setChecked(not low_stock_only)
        self.btn_filter_low.setChecked(low_stock_only)

        self.load_stocks()

    def load_stocks(self):
        """재고 목록 로드"""
        if self.show_low_stock_only:
            stocks = self.client.get_low_stocks()
        else:
            stocks = self.client.get_stocks()

        self.stocks_data = stocks
        self.display_stocks(stocks)

        # 재고 부족 개수 업데이트
        low_stock_count = sum(1 for s in stocks if s.get('is_low_stock', False))
        self.label_low_stock_count.setText(f'재고 부족: {low_stock_count}건')

    def display_stocks(self, stocks):
        """재고 목록 표시"""
        self.table_stocks.setRowCount(0)

        for stock in stocks:
            row = self.table_stocks.rowCount()
            self.table_stocks.insertRow(row)

            # 재고 ID
            self.table_stocks.setItem(row, 0, QTableWidgetItem(stock['stock_id']))

            # 재료명
            ingredient = stock.get('ingredient', {})
            self.table_stocks.setItem(row, 1, QTableWidgetItem(ingredient.get('name', '-')))

            # 현재 수량 (3단계 재고 시스템 반영)
            total_qty = stock.get('total_quantity', stock.get('quantity', 0))
            stock_area = stock.get('stock_area_boxes', 0)
            bed_qty = stock.get('bed_remaining', 0)

            # "총 94개 (영역:15박스, 밧드:4개)" 형식으로 표시
            if stock_area > 0 or bed_qty > 0:
                qty_text = f"{total_qty} (영역:{stock_area}박스, 밧드:{bed_qty})"
            else:
                qty_text = str(total_qty)

            quantity_item = QTableWidgetItem(qty_text)
            quantity_item.setToolTip(f"재고 영역: {stock_area}박스\n식재료 밧드: {bed_qty}개\n총 수량: {total_qty}")
            self.table_stocks.setItem(row, 2, quantity_item)

            # 임계값
            threshold = stock.get('threshold', 0)
            self.table_stocks.setItem(row, 3, QTableWidgetItem(str(threshold)))

            # 단위
            unit = ingredient.get('unit', '-')
            self.table_stocks.setItem(row, 4, QTableWidgetItem(unit))

            # 상태
            is_low_stock = stock.get('is_low_stock', False)
            status_text = '⚠️ 부족' if is_low_stock else '정상'
            status_item = QTableWidgetItem(status_text)

            if is_low_stock:
                status_item.setBackground(QColor(239, 154, 154))  # 빨간색
            else:
                status_item.setBackground(QColor(165, 214, 167))  # 녹색

            self.table_stocks.setItem(row, 5, status_item)

            # 공급업체
            supplier = stock.get('supplier', {})
            supplier_name = supplier.get('name', '-') if supplier else '-'
            self.table_stocks.setItem(row, 6, QTableWidgetItem(supplier_name))

    def on_selection_changed(self):
        """테이블 선택 변경 시"""
        selected_rows = self.table_stocks.selectedItems()
        if selected_rows:
            row = selected_rows[0].row()
            stock_id_item = self.table_stocks.item(row, 0)
            if stock_id_item:
                self.selected_stock_id = stock_id_item.text()
                self.btn_update_stock.setEnabled(True)
        else:
            self.selected_stock_id = None
            self.btn_update_stock.setEnabled(False)

    def update_stock(self):
        """재고 수량 변경"""
        if not self.selected_stock_id:
            return

        # 현재 재고 정보 가져오기
        stock = next((s for s in self.stocks_data if s['stock_id'] == self.selected_stock_id), None)
        if not stock:
            return

        ingredient_name = stock.get('ingredient', {}).get('name', '')
        current_quantity = stock.get('quantity', 0)
        unit = stock.get('ingredient', {}).get('unit', '')

        # 새 수량 입력
        new_quantity, ok = QInputDialog.getDouble(
            self, '재고 수량 변경',
            f'{ingredient_name} 재고 수량을 입력하세요 ({unit}):',
            value=current_quantity,
            min=0,
            max=999999,
            decimals=1
        )

        if ok:
            if self.client.update_stock(self.selected_stock_id, new_quantity):
                QMessageBox.information(
                    self, '성공',
                    f'{ingredient_name} 재고가 {new_quantity}{unit}(으)로 변경되었습니다.'
                )
                self.load_stocks()
            else:
                QMessageBox.warning(self, '실패', '재고 수량 변경에 실패했습니다.')

    def on_stock_alert(self, stock):
        """재고 부족 알림"""
        ingredient_name = stock.get('ingredient', {}).get('name', '')
        quantity = stock.get('quantity', 0)
        threshold = stock.get('threshold', 0)
        unit = stock.get('ingredient', {}).get('unit', '')

        QMessageBox.warning(
            self, '재고 부족 알림',
            f"⚠️ {ingredient_name} 재고가 부족합니다!\n\n"
            f"현재 수량: {quantity}{unit}\n"
            f"임계값: {threshold}{unit}"
        )

    def on_error(self, error_msg):
        """에러 발생 시"""
        print(f'[StockManagement] 에러: {error_msg}')

    def closeEvent(self, event):
        """위젯 종료 시"""
        self.refresh_timer.stop()
        self.client.disconnect()
        event.accept()


# 테스트 코드
if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = StockManagementWidget(use_mock=True)
    window.show()

    sys.exit(app.exec_())

"""
주문 확인 화면 (영수증 형태)
SR-05: 주문 내용 확인
SR-06: 주문 전송
"""
import sys
import os
from datetime import datetime
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSignal

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, Order


class OrderConfirmationWidget(QWidget):
    """주문 확인 위젯"""

    # 시그널 정의
    order_submitted_signal = pyqtSignal(Order)  # 주문 전송 시그널
    back_signal = pyqtSignal()  # 뒤로가기 시그널

    def __init__(self):
        super().__init__()
        self.order = None
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """UI 설정"""
        ui_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ui',
            'order_confirmation.ui'
        )
        loadUi(ui_path, self)

        # 윈도우 설정
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

    def connect_signals(self):
        """시그널 연결"""
        self.btn_submit.clicked.connect(self.on_submit_order)
        self.btn_back.clicked.connect(self.on_back)

    def set_order(self, order: Order):
        """주문 정보 설정 및 표시"""
        self.order = order
        self.update_receipt()

    def update_receipt(self):
        """영수증 내용 업데이트"""
        if not self.order:
            return

        # 테이블 번호
        self.label_table.setText(f'테이블: {self.order.table_number}')

        # 날짜/시간
        now = datetime.now()
        self.label_datetime.setText(now.strftime('%Y-%m-%d %H:%M'))

        # 주문 항목 리스트
        items_text = ''
        for order_item in self.order.items:
            sauce_text = f'\n  소스: {order_item.sauce}' if order_item.sauce else ''
            item_line = (
                f'{order_item.menu_item.name}{sauce_text}\n'
                f'  {order_item.quantity}개 x {order_item.menu_item.price:,}원 '
                f'= {order_item.get_subtotal():,}원\n\n'
            )
            items_text += item_line

        self.text_items.setPlainText(items_text)

        # 합계
        self.order.calculate_total()
        self.label_total.setText(f'합계: {self.order.total_price:,}원')

    def on_submit_order(self):
        """주문하기 버튼 클릭 - SR-06: 주문 전송"""
        if not self.order or len(self.order.items) == 0:
            QMessageBox.warning(
                self,
                '주문 오류',
                '주문 내용이 없습니다.',
                QMessageBox.Ok
            )
            return

        # 확인 다이얼로그
        reply = QMessageBox.question(
            self,
            '주문 확인',
            f'총 {self.order.total_price:,}원을 주문하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 주문 시간 설정
            self.order.created_at = datetime.now()

            print(f'[OrderConfirmation] 주문 전송 - 테이블 {self.order.table_number}, '
                  f'총액 {self.order.total_price:,}원')

            # 주문 전송 시그널 발생
            self.order_submitted_signal.emit(self.order)

    def on_back(self):
        """뒤로가기 버튼 클릭"""
        print('[OrderConfirmation] 뒤로가기')
        self.back_signal.emit()


def main():
    """테스트 실행"""
    from common import MenuItem, Order, OrderItem

    app = QApplication(sys.argv)

    # 테스트 주문 데이터
    test_order = Order(table_number=1)
    test_order.items.append(OrderItem(MenuItem('M001', '햄치즈샌드위치', 5000, '재료: 빵, 치즈, 토마토, 양상추, 햄', '', True, '샌드위치'), 2, '마요네즈'))
    test_order.items.append(OrderItem(MenuItem('M002', '비건샌드위치', 5000, '재료: 빵, 토마토, 양상추, 버섯', '', True, '샌드위치'), 1, '케찹'))
    test_order.calculate_total()

    widget = OrderConfirmationWidget()
    widget.set_order(test_order)
    widget.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

"""
음식 도착 알림 및 수령 확인 화면
SR-16: 음식 수령 확인 / 도착 알림
"""
import sys
import os
from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QPalette, QColor

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, Order


class DeliveryNotificationWidget(QWidget):
    """음식 도착 알림 위젯"""

    # 시그널 정의
    delivery_confirmed_signal = pyqtSignal(str)  # 수령 완료 시그널 (order_id)

    def __init__(self):
        super().__init__()
        self.order = None
        self.blink_timer = None
        self.blink_state = False
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """UI 설정"""
        ui_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ui',
            'delivery_notification.ui'
        )
        loadUi(ui_path, self)

        # 윈도우 설정
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

        # 텍스트 편집기 중앙 정렬
        layout = self.layout()
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() == self.text_order_items:
                item.setAlignment(Qt.AlignHCenter)
                break

    def connect_signals(self):
        """시그널 연결"""
        self.btn_confirm_delivery.clicked.connect(self.on_confirm_delivery)

    def set_order(self, order: Order):
        """주문 정보 설정 및 표시"""
        self.order = order
        self.update_notification()
        self.start_blink_animation()

    def update_notification(self):
        """알림 내용 업데이트"""
        if not self.order:
            return

        # 주문 번호
        if self.order.order_id:
            self.label_order_info.setText(f'주문 번호: {self.order.order_id}')
        else:
            self.label_order_info.setText('')

        # 주문 항목 리스트
        items_text = '주문하신 메뉴:\n\n'
        for order_item in self.order.items:
            items_text += f'• {order_item.menu_item.name} x {order_item.quantity}\n'

        self.text_order_items.setPlainText(items_text)

    def start_blink_animation(self):
        """깜빡이는 애니메이션 시작 (시각적 알림)"""
        if self.blink_timer:
            self.blink_timer.stop()

        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.toggle_blink)
        self.blink_timer.start(500)  # 500ms 간격

    def toggle_blink(self):
        """깜빡임 토글"""
        self.blink_state = not self.blink_state

        if self.blink_state:
            # 강조 색상
            self.label_notification.setStyleSheet(
                'color: #FF6B6B; background-color: #FFF3CD;'
            )
        else:
            # 기본 색상
            self.label_notification.setStyleSheet('')

    def stop_blink_animation(self):
        """깜빡임 애니메이션 중지"""
        if self.blink_timer:
            self.blink_timer.stop()
            self.label_notification.setStyleSheet('')

    def on_confirm_delivery(self):
        """수령 완료 버튼 클릭 - SR-16: 음식 수령 확인"""
        if not self.order:
            return

        print(f'[DeliveryNotification] 수령 완료 - 주문 {self.order.order_id}')

        # 깜빡임 중지
        self.stop_blink_animation()

        # 수령 완료 시그널 발생
        self.delivery_confirmed_signal.emit(self.order.order_id or '')

    def showEvent(self, event):
        """위젯이 표시될 때"""
        super().showEvent(event)
        if self.order:
            self.start_blink_animation()

    def hideEvent(self, event):
        """위젯이 숨겨질 때"""
        super().hideEvent(event)
        self.stop_blink_animation()


def main():
    """테스트 실행"""
    from common import MenuItem, Order

    app = QApplication(sys.argv)

    # 테스트 주문 데이터
    test_order = Order(table_number=1)
    test_order.order_id = 'ORD-001'
    test_order.add_item(MenuItem('M001', '닭가슴살포케', 12000, '신선한 닭가슴살과 채소를 곁들인 건강한 포케', '', True, '포케'), 2)
    test_order.add_item(MenuItem('M002', '연어포케', 14000, '신선한 연어와 다양한 토핑의 포케', '', True, '포케'), 1)

    widget = DeliveryNotificationWidget()
    widget.set_order(test_order)
    widget.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

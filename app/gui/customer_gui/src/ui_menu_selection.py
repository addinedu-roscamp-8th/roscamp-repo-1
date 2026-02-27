"""
메뉴 선택 화면
SR-01: 메뉴 제공
SR-03a: 화면 주문 (메뉴 선택, 수량 조절, 장바구니 구성)
SR-04: 무효 주문 차단
"""
import sys
import os
from PyQt5.QtWidgets import (QWidget, QApplication, QListWidgetItem,
                             QMessageBox, QDialog, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QSpinBox)
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config, MenuItem, Order


class MenuItemDialog(QDialog):
    """메뉴 아이템 상세/수량/소스 선택 다이얼로그"""

    def __init__(self, menu_item: MenuItem, parent=None):
        super().__init__(parent)
        self.menu_item = menu_item
        self.quantity = 1
        self.selected_sauce = "소스선택x"
        self.setup_ui()

    def setup_ui(self):
        """UI 설정"""
        self.setWindowTitle('메뉴 선택')
        self.setMinimumSize(500, 450)

        layout = QVBoxLayout()

        # 메뉴 정보
        label_name = QLabel(f'<h2>{self.menu_item.name}</h2>')
        layout.addWidget(label_name)

        label_price = QLabel(f'가격: {self.menu_item.price:,}원')
        label_price.setStyleSheet('font-size: 18px;')
        layout.addWidget(label_price)

        if self.menu_item.description:
            label_desc = QLabel(self.menu_item.description)
            label_desc.setWordWrap(True)
            layout.addWidget(label_desc)

        layout.addWidget(QLabel(''))  # 빈 줄

        # 소스 선택
        layout.addWidget(QLabel('<b>소스 선택 (무료)</b>'))

        from PyQt5.QtWidgets import QRadioButton, QButtonGroup
        self.sauce_group = QButtonGroup()

        sauces = ["소스선택x", "마요네즈", "케찹", "머스타드"]
        for i, sauce in enumerate(sauces):
            radio = QRadioButton(sauce)
            if i == 0:
                radio.setChecked(True)
            radio.setStyleSheet('font-size: 16px; padding: 5px;')
            self.sauce_group.addButton(radio, i)
            layout.addWidget(radio)

        layout.addWidget(QLabel(''))  # 빈 줄

        # 수량 선택
        quantity_layout = QHBoxLayout()
        quantity_layout.addWidget(QLabel('수량:'))

        self.spin_quantity = QSpinBox()
        self.spin_quantity.setMinimum(1)
        self.spin_quantity.setMaximum(99)
        self.spin_quantity.setValue(1)
        self.spin_quantity.setStyleSheet('font-size: 18px; padding: 5px;')
        quantity_layout.addWidget(self.spin_quantity)
        quantity_layout.addStretch()

        layout.addLayout(quantity_layout)

        layout.addStretch()

        # 버튼
        button_layout = QHBoxLayout()

        btn_add = QPushButton('장바구니에 추가')
        btn_add.setMinimumHeight(50)
        btn_add.setStyleSheet('font-size: 16px; font-weight: bold;')
        btn_add.clicked.connect(self.accept)
        button_layout.addWidget(btn_add)

        btn_cancel = QPushButton('취소')
        btn_cancel.setMinimumHeight(50)
        btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(btn_cancel)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_quantity(self):
        """선택된 수량을 반환합니다."""
        return self.spin_quantity.value()

    def get_sauce(self):
        """선택된 소스를 반환합니다."""
        sauces = ["소스선택x", "마요네즈", "케찹", "머스타드"]
        selected_id = self.sauce_group.checkedId()
        return sauces[selected_id] if selected_id >= 0 else "소스선택x"


class MenuSelectionWidget(QWidget):
    """메뉴 선택 위젯"""

    # 시그널 정의
    order_confirmed_signal = pyqtSignal(Order)  # 주문 확인 버튼 클릭
    cancel_signal = pyqtSignal()  # 취소 버튼 클릭

    def __init__(self):
        super().__init__()
        self.order = Order(table_number=Config.TABLE_NUMBER)
        self.menu_items = []  # 메뉴 리스트
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """UI를 설정합니다."""
        ui_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ui',
            'menu_selection.ui'
        )
        loadUi(ui_path, self)

        # 윈도우 설정
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

    def connect_signals(self):
        """시그널을 연결합니다."""
        self.list_menu.itemDoubleClicked.connect(self.on_menu_item_clicked)
        self.list_cart.itemDoubleClicked.connect(self.on_cart_item_clicked)
        self.btn_confirm_order.clicked.connect(self.on_confirm_order)
        self.btn_cancel.clicked.connect(self.on_cancel)

    def set_menu_items(self, menu_items: list):
        """메뉴 리스트를 설정합니다."""
        self.menu_items = menu_items
        self.update_menu_list()

    def update_menu_list(self):
        """메뉴 리스트를 업데이트합니다."""
        self.list_menu.clear()

        for menu_item in self.menu_items:
            item_text = f'{menu_item.name}\n{menu_item.price:,}원'

            if not menu_item.available:
                item_text += '\n(품절)'

            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, menu_item)

            # 품절 메뉴는 회색으로 표시
            if not menu_item.available:
                list_item.setForeground(Qt.gray)

            self.list_menu.addItem(list_item)

    def update_cart_list(self):
        """장바구니 리스트를 업데이트합니다."""
        self.list_cart.clear()

        for order_item in self.order.items:
            sauce_text = f' (소스: {order_item.sauce})' if order_item.sauce else ''
            item_text = (f'{order_item.menu_item.name}{sauce_text}\n'
                        f'{order_item.quantity}개 x {order_item.menu_item.price:,}원 = '
                        f'{order_item.get_subtotal():,}원')

            list_item = QListWidgetItem(item_text)
            list_item.setData(Qt.UserRole, order_item)
            self.list_cart.addItem(list_item)

        # 합계 업데이트
        self.order.calculate_total()
        self.label_total.setText(f'합계: {self.order.total_price:,}원')

    def on_menu_item_clicked(self, item):
        """메뉴 아이템 클릭을 처리합니다."""
        menu_item = item.data(Qt.UserRole)

        # SR-04: 무효 주문 차단 - 품절 메뉴 선택 시 경고
        if not menu_item.available:
            QMessageBox.warning(
                self,
                '품절',
                f'{menu_item.name}은(는) 현재 품절되었습니다.',
                QMessageBox.Ok
            )
            return

        # 메뉴 선택 다이얼로그 표시
        dialog = MenuItemDialog(menu_item, self)
        if dialog.exec_() == QDialog.Accepted:
            quantity = dialog.get_quantity()
            sauce = dialog.get_sauce()

            # 소스 정보를 포함한 OrderItem 생성
            from common import OrderItem
            order_item = OrderItem(menu_item, quantity, sauce)

            # 같은 메뉴와 같은 소스 조합이 있으면 수량만 증가
            found = False
            for item in self.order.items:
                if item.menu_item.menu_id == menu_item.menu_id and item.sauce == sauce:
                    item.quantity += quantity
                    found = True
                    break

            if not found:
                self.order.items.append(order_item)

            self.order.calculate_total()
            self.update_cart_list()
            print(f'[MenuSelection] 메뉴 추가: {menu_item.name} x {quantity}, 소스: {sauce}')

    def on_cart_item_clicked(self, item):
        """장바구니 아이템 클릭을 처리합니다 - 수량 변경 또는 삭제."""
        order_item = item.data(Qt.UserRole)

        # 수량 변경 다이얼로그
        dialog = QDialog(self)
        dialog.setWindowTitle('수량 변경')
        dialog.setMinimumSize(300, 200)

        layout = QVBoxLayout()

        label = QLabel(f'{order_item.menu_item.name}')
        label.setStyleSheet('font-size: 18px; font-weight: bold;')
        layout.addWidget(label)

        # 수량 선택
        quantity_layout = QHBoxLayout()
        quantity_layout.addWidget(QLabel('수량:'))

        spin_quantity = QSpinBox()
        spin_quantity.setMinimum(0)  # 0으로 설정하면 삭제
        spin_quantity.setMaximum(99)
        spin_quantity.setValue(order_item.quantity)
        spin_quantity.setStyleSheet('font-size: 18px; padding: 5px;')
        quantity_layout.addWidget(spin_quantity)
        quantity_layout.addStretch()

        layout.addLayout(quantity_layout)

        hint_label = QLabel('* 수량을 0으로 설정하면 삭제됩니다')
        hint_label.setStyleSheet('color: gray;')
        layout.addWidget(hint_label)

        layout.addStretch()

        # 버튼
        button_layout = QHBoxLayout()

        btn_ok = QPushButton('확인')
        btn_ok.setMinimumHeight(50)
        btn_ok.clicked.connect(dialog.accept)
        button_layout.addWidget(btn_ok)

        btn_cancel = QPushButton('취소')
        btn_cancel.setMinimumHeight(50)
        btn_cancel.clicked.connect(dialog.reject)
        button_layout.addWidget(btn_cancel)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

        if dialog.exec_() == QDialog.Accepted:
            new_quantity = spin_quantity.value()
            self.order.update_quantity(order_item.menu_item.menu_id, new_quantity)
            self.update_cart_list()
            print(f'[MenuSelection] 수량 변경: {order_item.menu_item.name} -> {new_quantity}')

    def on_confirm_order(self):
        """주문 확인 버튼 클릭을 처리합니다."""
        if len(self.order.items) == 0:
            QMessageBox.warning(
                self,
                '주문 없음',
                '장바구니가 비어있습니다.\n메뉴를 선택해주세요.',
                QMessageBox.Ok
            )
            return

        print(f'[MenuSelection] 주문 확인 - 총 {len(self.order.items)}개 항목')
        self.order_confirmed_signal.emit(self.order)

    def on_cancel(self):
        """취소 버튼 클릭을 처리합니다."""
        reply = QMessageBox.question(
            self,
            '주문 취소',
            '주문을 취소하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.order.clear()
            self.update_cart_list()
            print('[MenuSelection] 주문 취소')
            self.cancel_signal.emit()


def main():
    """테스트를 실행합니다."""
    app = QApplication(sys.argv)

    # 테스트 메뉴 데이터
    test_menus = [
        MenuItem('M001', '햄치즈 샌드위치', 5000, '재료: 빵, 양상추, 토마토, 치즈, 햄', '', True, '샌드위치'),
        MenuItem('M002', '버섯 샌드위치', 5500, '재료: 빵, 버섯, 토마토, 치즈', '', True, '샌드위치'),
        MenuItem('M003', '올인원 샌드위치', 6500, '재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추', '', True, '샌드위치'),
    ]

    widget = MenuSelectionWidget()
    widget.set_menu_items(test_menus)
    widget.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

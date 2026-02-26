"""
주문 시작 화면 (메인 윈도우)
SR-02: 주문 시작
테이블 1~4 선택 UI 제공.
"""
import sys
import os
from PyQt5.QtWidgets import QMainWindow, QApplication, QHBoxLayout, QLabel, QComboBox, QWidget
from PyQt5.uic import loadUi
from PyQt5.QtCore import pyqtSignal

# 프로젝트 루트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config


class MainWindow(QMainWindow):
    """주문 시작 화면"""

    # 시그널 정의
    start_order_signal = pyqtSignal()  # 주문 시작 버튼 클릭 시그널

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """UI 설정"""
        # .ui 파일 로드
        ui_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'ui',
            'main_window.ui'
        )
        loadUi(ui_path, self)

        # 윈도우 설정
        self.setWindowTitle('주문 시작')
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

        # 테이블 번호 표시
        self.label_table.setText(f'테이블 번호: {Config.TABLE_NUMBER}')

        # 테이블 선택 UI (1~4)
        table_row = QWidget()
        table_layout = QHBoxLayout(table_row)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.addWidget(QLabel('테이블 선택:'))
        self.combo_table = QComboBox()
        self.combo_table.addItems(['1', '2', '3', '4'])
        idx = max(0, min(Config.TABLE_NUMBER - 1, 3))
        self.combo_table.setCurrentIndex(idx)
        self.combo_table.setMinimumWidth(80)
        table_layout.addWidget(self.combo_table)
        table_layout.addStretch()
        # verticalLayout에 label_table 다음에 테이블 선택 행 삽입
        layout = self.centralwidget.layout()
        layout.insertWidget(3, table_row)

    def connect_signals(self):
        """시그널 연결"""
        self.btn_start_order.clicked.connect(self.on_start_order)
        self.combo_table.currentIndexChanged.connect(self.on_table_changed)

    def on_table_changed(self, index: int):
        """테이블 번호 변경 시 Config 반영 및 라벨 갱신."""
        table_num = index + 1
        Config.TABLE_NUMBER = table_num
        self.label_table.setText(f'테이블 번호: {table_num}')
        print(f'[MainWindow] 테이블 번호 변경: {table_num}')

    def on_start_order(self):
        """주문 시작 버튼 클릭"""
        # 콤보에서 선택된 값으로 동기화
        Config.TABLE_NUMBER = self.combo_table.currentIndex() + 1
        self.label_table.setText(f'테이블 번호: {Config.TABLE_NUMBER}')
        print(f'[MainWindow] 주문 시작 - 테이블 {Config.TABLE_NUMBER}')
        self.start_order_signal.emit()


def main():
    """테스트 실행"""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

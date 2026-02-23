"""
주문 시작 화면 (메인 윈도우)
SR-02: 주문 시작
"""
import sys
import os
from PyQt5.QtWidgets import QMainWindow, QApplication
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

    def connect_signals(self):
        """시그널 연결"""
        self.btn_start_order.clicked.connect(self.on_start_order)

    def on_start_order(self):
        """주문 시작 버튼 클릭"""
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

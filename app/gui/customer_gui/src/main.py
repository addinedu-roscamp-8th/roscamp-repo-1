"""
고객용 GUI 메인 애플리케이션
화면 전환 및 통합 관리
"""
import sys
import os
from PyQt5.QtWidgets import QApplication, QStackedWidget, QMessageBox
from PyQt5.QtCore import Qt

# 프로젝트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from common import Config, Order
from ui_main_window import MainWindow
from ui_menu_selection import MenuSelectionWidget
from ui_order_confirmation import OrderConfirmationWidget
from ui_delivery_notification import DeliveryNotificationWidget
from voice_feedback_widget import VoiceFeedbackWidget
from tcp_client import MockOrderServiceClient


class CustomerGUIApp(QStackedWidget):
    """고객용 GUI 메인 애플리케이션"""

    def __init__(self):
        super().__init__()

        # 현재 주문
        self.current_order = None

        # TCP 클라이언트 (Mock 사용)
        self.order_client = MockOrderServiceClient()

        # 화면 위젯들
        self.main_window = None
        self.menu_selection = None
        self.order_confirmation = None
        self.delivery_notification = None
        self.voice_feedback = None

        self.setup_ui()
        self.setup_client()
        self.connect_signals()

    def setup_ui(self):
        """UI 초기화"""
        # 윈도우 설정
        self.setWindowTitle('주문 키오스크')
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            self.resize(Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT)

        # 스타일시트 로드
        # self.load_stylesheet()

        # 화면 위젯 생성 및 추가
        self.main_window = MainWindow()
        self.addWidget(self.main_window)

        self.menu_selection = MenuSelectionWidget()
        self.addWidget(self.menu_selection)

        self.order_confirmation = OrderConfirmationWidget()
        self.addWidget(self.order_confirmation)

        self.delivery_notification = DeliveryNotificationWidget()
        self.addWidget(self.delivery_notification)

        # 음성 피드백 위젯 (오버레이로 사용)
        self.voice_feedback = VoiceFeedbackWidget(self)
        self.voice_feedback.setGeometry(
            (Config.SCREEN_WIDTH - 500) // 2,
            Config.SCREEN_HEIGHT - 350,
            500,
            300
        )
        self.voice_feedback.hide()

        # 처음 화면은 메인 윈도우
        self.setCurrentWidget(self.main_window)

    def load_stylesheet(self):
        """스타일시트 로드"""
        style_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'resources',
            'style_customer_poke_theme3.qss'
        )

        try:
            with open(style_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
                self.setStyleSheet(stylesheet)
                print('[App] 스타일시트 로드 성공')
        except Exception as e:
            print(f'[App] 스타일시트 로드 실패: {e}')

    def setup_client(self):
        """TCP 클라이언트 설정"""
        # 서버 연결
        if self.order_client.connect():
            print('[App] 주문 서버 연결 성공')
        else:
            print('[App] 주문 서버 연결 실패 (Mock 모드)')

    def connect_signals(self):
        """시그널 연결"""
        # 메인 윈도우
        self.main_window.start_order_signal.connect(self.on_start_order)

        # 메뉴 선택 화면
        self.menu_selection.order_confirmed_signal.connect(self.on_order_confirmed)
        self.menu_selection.cancel_signal.connect(self.on_cancel_order)

        # 주문 확인 화면
        self.order_confirmation.order_submitted_signal.connect(self.on_order_submitted)
        self.order_confirmation.back_signal.connect(self.on_back_to_menu_selection)

        # 수령 확인 화면
        self.delivery_notification.delivery_confirmed_signal.connect(self.on_delivery_confirmed)

        # TCP 클라이언트
        self.order_client.error_signal.connect(self.on_client_error)

    def on_start_order(self):
        """주문 시작"""
        print('[App] 주문 시작')

        # 메뉴 조회
        menus = self.order_client.fetch_menus()
        if not menus:
            QMessageBox.warning(
                self,
                '오류',
                '메뉴를 불러올 수 없습니다.',
                QMessageBox.Ok
            )
            return

        # 메뉴 선택 화면으로 전환
        self.menu_selection.set_menu_items(menus)
        self.setCurrentWidget(self.menu_selection)

    def on_order_confirmed(self, order: Order):
        """주문 확인 (메뉴 선택 완료)"""
        print(f'[App] 주문 확인 - {len(order.items)}개 항목')

        self.current_order = order

        # 주문 확인 화면으로 전환
        self.order_confirmation.set_order(order)
        self.setCurrentWidget(self.order_confirmation)

    def on_order_submitted(self, order: Order):
        """주문 전송"""
        print('[App] 주문 전송 중...')

        # 주문 전송
        order_id = self.order_client.submit_order(order)

        if not order_id:
            QMessageBox.critical(
                self,
                '주문 실패',
                '주문 전송에 실패했습니다.\n다시 시도해주세요.',
                QMessageBox.Ok
            )
            return

        # 주문 번호 설정
        order.order_id = order_id

        # 주문 성공 메시지
        QMessageBox.information(
            self,
            '주문 완료',
            f'주문이 접수되었습니다.\n주문 번호: {order_id}\n\n'
            f'음식이 준비되면 로봇이 배달해드립니다.',
            QMessageBox.Ok
        )

        # 메인 화면으로 돌아가기
        self.go_to_main()

        # 시뮬레이션: 5초 후 배달 알림 (실제로는 TCP로 알림 수신)
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(5000, lambda: self.show_delivery_notification(order))

    def on_back_to_menu_selection(self):
        """메뉴 선택으로 돌아가기"""
        print('[App] 메뉴 선택으로 돌아가기')
        self.setCurrentWidget(self.menu_selection)

    def on_cancel_order(self):
        """주문 취소"""
        print('[App] 주문 취소')
        self.current_order = None
        self.go_to_main()

    def on_delivery_confirmed(self, order_id: str):
        """수령 확인"""
        print(f'[App] 수령 확인 - 주문 {order_id}')

        # 수령 확인 전송
        if self.order_client.confirm_delivery(order_id):
            QMessageBox.information(
                self,
                '감사합니다',
                '맛있게 드세요!',
                QMessageBox.Ok
            )
        else:
            QMessageBox.warning(
                self,
                '오류',
                '수령 확인 처리 중 오류가 발생했습니다.',
                QMessageBox.Ok
            )

        # 메인 화면으로 돌아가기
        self.go_to_main()

    def show_delivery_notification(self, order: Order):
        """배달 알림 표시 (SR-16: 도착 알림)"""
        print(f'[App] 배달 알림 - 주문 {order.order_id}')

        # 배달 알림 화면으로 전환
        self.delivery_notification.set_order(order)
        self.setCurrentWidget(self.delivery_notification)

    def on_client_error(self, error_msg: str):
        """TCP 클라이언트 오류"""
        print(f'[App] 클라이언트 오류: {error_msg}')
        QMessageBox.warning(
            self,
            '통신 오류',
            f'서버 통신 중 오류가 발생했습니다:\n{error_msg}',
            QMessageBox.Ok
        )

    def go_to_main(self):
        """메인 화면으로 돌아가기"""
        print('[App] 메인 화면으로 돌아가기')
        self.current_order = None
        self.setCurrentWidget(self.main_window)

    def keyPressEvent(self, event):
        """키 이벤트 처리 (ESC로 전체화면 종료)"""
        if event.key() == Qt.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """종료 이벤트"""
        # TCP 클라이언트 연결 종료
        self.order_client.disconnect()
        print('[App] 애플리케이션 종료')
        event.accept()


def main():
    """메인 함수"""
    # QApplication 생성
    app = QApplication(sys.argv)

    # 애플리케이션 설정
    app.setApplicationName('주문 키오스크')
    app.setOrganizationName('Restaurant')

    # 메인 윈도우 생성 및 표시
    window = CustomerGUIApp()
    window.show()

    print('[App] 고객용 GUI 시작')
    print(f'[App] 테이블 번호: {Config.TABLE_NUMBER}')
    print(f'[App] 화면 크기: {Config.SCREEN_WIDTH}x{Config.SCREEN_HEIGHT}')
    print(f'[App] 전체화면: {Config.FULLSCREEN}')

    # 이벤트 루프 실행
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

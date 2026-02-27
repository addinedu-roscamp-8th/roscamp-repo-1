"""
고객용 GUI 메인 애플리케이션
화면 전환 및 통합 관리

실행 모드:
- 기본: Backend(주문 MS)를 통한 통신
- FMS 직접: Backend 없이 FMS와 직접 TCP 통신 (--fms-direct 옵션)
"""
import sys
import os
import argparse
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
from tcp_client import OrderServiceClient, MockOrderServiceClient
from fms_direct_client import FMSDirectClient, MockFMSDirectClient


class CustomerGUIApp(QStackedWidget):
    """고객용 GUI 메인 애플리케이션"""

    def __init__(self, fms_direct_mode: bool = False, use_mock: bool = False):
        super().__init__()

        # 실행 모드
        self._fms_direct_mode = fms_direct_mode
        self._use_mock = use_mock

        # 현재 주문
        self.current_order = None
        self.pending_order = None  # 배달 대기 중인 주문 (주문 제출 후 배달 알림 수신까지)

        # 클라이언트 초기화 (모드에 따라 다름)
        self.order_client = None

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
        """클라이언트 설정 (모드에 따라 다름)"""
        if self._fms_direct_mode:
            # FMS 직접 연결 모드
            self._setup_fms_direct_client()
        else:
            # Backend(주문 MS) 통신 모드
            self._setup_order_ms_client()

    def _setup_fms_direct_client(self):
        """FMS 직접 연결 클라이언트 설정"""
        if self._use_mock:
            print('[App] FMS Direct 모드 - Mock 사용')
            self.order_client = MockFMSDirectClient()
            self.order_client.connect()
        else:
            print(f'[App] FMS Direct 모드 - {Config.FMS_HOST}:{Config.FMS_PORT}')
            self.order_client = FMSDirectClient()
            if self.order_client.connect():
                print('[App] FMS 직접 연결 성공')
            else:
                print('[App] FMS 연결 실패 - Mock 모드로 전환')
                self._use_mock = True
                self.order_client = MockFMSDirectClient()
                self.order_client.connect()

    def _setup_order_ms_client(self):
        """주문 MS 클라이언트 설정 (기존 방식)"""
        self.order_client = OrderServiceClient()
        if self.order_client.connect():
            print('[App] 주문 서버 연결 성공')
        else:
            print('[App] 주문 서버 연결 실패 - Mock 모드로 전환')
            self._use_mock = True
            self.order_client = MockOrderServiceClient()
            self.order_client.connect()

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
        # 배달 알림 푸시 수신
        self.order_client.delivery_notification_signal.connect(self.on_delivery_notification_received)

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

        # 주문을 pending_order에 저장 (배달 알림 수신 시 사용)
        self.pending_order = self.current_order
        # 메인 화면으로 돌아가기 (배달 알림은 TCP 푸시 알림으로 수신)
        self.go_to_main()

    def on_back_to_menu_selection(self):
        """메뉴 선택으로 돌아가기"""
        print('[App] 메뉴 선택으로 돌아가기')
        self.setCurrentWidget(self.menu_selection)

    def on_cancel_order(self):
        """주문 취소"""
        print('[App] 주문 취소')
        self.current_order = None
        self.go_to_main()

    def on_delivery_notification_received(self, notification: dict):
        """배달 알림 수신 (Main Server로부터 푸시) - SR-16: 도착 알림"""
        print(f'[App] 배달 알림 수신: {notification}')

        try:
            order_data = notification.get('data', {})
            order_id = order_data.get('order_id', '')
            table_number = order_data.get('table_number', '')
            robot_id = order_data.get('robot_id', '')
            status = order_data.get('status', '')

            if not order_id:
                print('[App] 오류: 배달 알림에서 order_id를 찾을 수 없음')
                return

            # 테이블 번호 확인 - 이 GUI의 테이블과 일치하는지 확인
            try:
                notification_table = int(table_number) if table_number else 0
            except (ValueError, TypeError):
                notification_table = 0

            if notification_table != Config.TABLE_NUMBER:
                print(f'[App] 다른 테이블({notification_table})의 알림, 이 테이블({Config.TABLE_NUMBER})과 무관')
                return

            # 현재 주문 또는 대기 중인 주문이 있으면 배달 알림 표시
            active_order = self.current_order or self.pending_order
            if active_order:
                print(f'[App] 배달 알림 - 테이블 {table_number}, 로봇 {robot_id}, 주문 {order_id}')
                # 배달 알림 화면 표시
                self.show_delivery_notification(active_order)
            else:
                print(f'[App] 현재 주문이 없음, 배달 알림 무시: {order_id}')
        except Exception as e:
            print(f'[App] 배달 알림 처리 오류: {e}')

    def on_delivery_confirmed(self, delivery_data: dict):
        """수령 확인 - SC-185: 수령 확인 API"""
        order_id = delivery_data.get('order_id', '')
        table_number = delivery_data.get('table_number', '')
        print(f'[App] 수령 확인 - 주문 {order_id}, 테이블 {table_number}')

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

        # pending_order 초기화 후 메인 화면으로 돌아가기
        self.pending_order = None
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


def parse_args():
    """커맨드라인 인자 파싱"""
    parser = argparse.ArgumentParser(description='고객용 GUI 키오스크')
    parser.add_argument(
        '--fms-direct',
        action='store_true',
        help='FMS 직접 연결 모드 (Backend 없이 FMS와 직접 통신)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Mock 모드 (실제 서버 연결 없이 테스트)'
    )
    parser.add_argument(
        '--table',
        type=int,
        default=None,
        help='테이블 번호 설정'
    )
    return parser.parse_args()


def main():
    """메인 함수"""
    # 커맨드라인 인자 파싱
    args = parse_args()

    # 테이블 번호 설정
    if args.table is not None:
        Config.TABLE_NUMBER = args.table

    # QApplication 생성
    app = QApplication(sys.argv)

    # 애플리케이션 설정
    app.setApplicationName('주문 키오스크')
    app.setOrganizationName('Restaurant')

    # 메인 윈도우 생성 및 표시
    window = CustomerGUIApp(
        fms_direct_mode=args.fms_direct,
        use_mock=args.mock
    )
    window.show()

    print('[App] 고객용 GUI 시작')
    print(f'[App] 모드: {"FMS 직접 연결" if args.fms_direct else "Backend(주문 MS) 통신"}')
    print(f'[App] Mock: {args.mock}')
    print(f'[App] 테이블 번호: {Config.TABLE_NUMBER}')
    print(f'[App] 화면 크기: {Config.SCREEN_WIDTH}x{Config.SCREEN_HEIGHT}')
    print(f'[App] 전체화면: {Config.FULLSCREEN}')

    if args.fms_direct:
        print(f'[App] FMS 주소: {Config.FMS_HOST}:{Config.FMS_PORT}')

    # 이벤트 루프 실행
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

"""
고객용 GUI - FMS 직접 통신 버전
Backend 없이 FMS로 직접 주문 전송

Architecture:
- Domain: Order, MenuItem (common/models.py)
- Application: FMSOrderServiceClient (fms_client.py)
- Infrastructure: FMSTCPClient (fms_client.py)
- Presentation: 이 파일 (main UI)

SOLID Principles:
- Dependency Inversion: OrderServiceClient 인터페이스에 의존
- Open/Closed: 새로운 클라이언트 추가 가능 (FMS, Mock)
"""
import sys
import os
from PyQt5.QtWidgets import QApplication, QStackedWidget, QMessageBox
from PyQt5.QtCore import Qt

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from common import Config, Order, MenuItem
from ui_main_window import MainWindow
from ui_menu_selection import MenuSelectionWidget
from ui_order_confirmation import OrderConfirmationWidget
from ui_delivery_notification import DeliveryNotificationWidget
from voice_feedback_widget import VoiceFeedbackWidget
from fms_client import FMSOrderServiceClient, MockFMSOrderServiceClient
from styles import MAIN_STYLESHEET, SCREEN_WIDTH, SCREEN_HEIGHT


# Mock 메뉴 데이터 (테스트용)
MOCK_MENUS = [
    MenuItem('M001', '햄치즈 샌드위치', 5000, '재료: 빵, 양상추, 토마토, 치즈, 햄', '', True, '샌드위치'),
    MenuItem('M002', '버섯 샌드위치', 5500, '재료: 빵, 버섯, 토마토, 치즈', '', True, '샌드위치'),
    MenuItem('M003', '올인원 샌드위치', 6500, '재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추', '', True, '샌드위치'),
]


class CustomerGUIApp(QStackedWidget):
    """
    고객용 GUI 메인 애플리케이션 (FMS 직접 통신)

    Responsibilities:
    - 화면 전환 관리
    - FMS 클라이언트 생명주기 관리
    - 주문 플로우 오케스트레이션
    """

    def __init__(self, use_mock: bool = False):
        super().__init__()

        # 현재 주문
        self.current_order = None
        self.pending_order = None  # 배달 대기 중인 주문

        # FMS 클라이언트 선택 (실제 vs Mock)
        self.use_mock = use_mock
        if use_mock:
            print('[App] Mock FMS 클라이언트 사용')
            self.fms_client = MockFMSOrderServiceClient()
        else:
            print('[App] 실제 FMS 클라이언트 사용')
            self.fms_client = FMSOrderServiceClient()

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
        self.setWindowTitle('주문 키오스크 (FMS Direct)')
        if Config.FULLSCREEN:
            self.showFullScreen()
        else:
            # 38cm x 23cm 화면에 최적화된 크기 사용
            self.resize(SCREEN_WIDTH, SCREEN_HEIGHT)

        # 화면 위젯 생성 및 추가
        self.main_window = MainWindow()
        self.addWidget(self.main_window)

        self.menu_selection = MenuSelectionWidget()
        self.addWidget(self.menu_selection)

        self.order_confirmation = OrderConfirmationWidget()
        self.addWidget(self.order_confirmation)

        self.delivery_notification = DeliveryNotificationWidget()
        self.addWidget(self.delivery_notification)

        # 음성 피드백 위젯 (오버레이)
        self.voice_feedback = VoiceFeedbackWidget(self)
        self.voice_feedback.setGeometry(
            (SCREEN_WIDTH - 500) // 2,
            SCREEN_HEIGHT - 350,
            500,
            300
        )
        self.voice_feedback.hide()

        # 처음 화면은 메인 윈도우
        self.setCurrentWidget(self.main_window)

    def setup_client(self):
        """FMS 클라이언트 설정"""
        if self.fms_client.connect():
            print(f'[App] FMS 연결 성공: {Config.FMS_HOST}:{Config.FMS_PORT}')
        else:
            print('[App] FMS 연결 실패')
            QMessageBox.warning(
                self,
                '연결 오류',
                f'FMS 서버에 연결할 수 없습니다.\n'
                f'주소: {Config.FMS_HOST}:{Config.FMS_PORT}\n\n'
                f'Mock 모드로 전환하려면 --mock 옵션을 사용하세요.',
                QMessageBox.Ok
            )

    def connect_signals(self):
        """시그널 연결 (이벤트 구독)"""
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

        # FMS 클라이언트
        self.fms_client.error_signal.connect(self.on_client_error)
        self.fms_client.delivery_notification_signal.connect(self.on_delivery_notification_received)

    # ==================== 이벤트 핸들러 ====================

    def on_start_order(self):
        """주문 시작 - Mock 메뉴 제공"""
        print('[App] 주문 시작')

        # Mock 메뉴 데이터 사용
        menus = MOCK_MENUS

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
        """주문 전송 (FMS로 직접)"""
        print('[App] 주문 전송 중...')

        # FMS로 주문 전송
        order_id = self.fms_client.submit_order(order)

        if not order_id:
            QMessageBox.critical(
                self,
                '주문 실패',
                'FMS로 주문 전송에 실패했습니다.\n다시 시도해주세요.',
                QMessageBox.Ok
            )
            return

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
        """
        배달 알림 수신 (FMS로부터 푸시)

        메시지 형식:
        {
            'type': 'delivery_notification',
            'data': {
                'order_id': 'ORD-XXX',
                'table_number': '1',
                'robot_id': 'pinky1'
            }
        }
        """
        print(f'[App] 배달 알림 수신: {notification}')

        try:
            order_data = notification.get('data', {})
            order_id = order_data.get('order_id', '')
            table_number = order_data.get('table_number', '')
            robot_id = order_data.get('robot_id', '')

            if not order_id:
                print('[App] 오류: 배달 알림에서 order_id를 찾을 수 없음')
                return

            # 테이블 번호 확인 - 이 GUI의 테이블과 일치하는지 확인
            notification_table = int(table_number) if table_number else 0
            if notification_table != Config.TABLE_NUMBER:
                print(f'[App] 다른 테이블({notification_table})의 알림, 이 테이블({Config.TABLE_NUMBER})과 무관')
                return

            # 현재 주문 또는 대기 중인 주문이 있으면 배달 알림 표시
            active_order = self.current_order or self.pending_order
            if active_order:
                print(f'[App] 배달 알림 - 테이블 {table_number}, 로봇 {robot_id}')
                self.show_delivery_notification(active_order)
            else:
                print(f'[App] 현재 주문이 없음, 배달 알림 무시: {order_id}')

        except Exception as e:
            print(f'[App] 배달 알림 처리 오류: {e}')

    def on_delivery_confirmed(self, delivery_data: dict):
        """수령 확인 (FMS로 전송)"""
        order_id = delivery_data.get('order_id', '')
        table_number = int(delivery_data.get('table_number', Config.TABLE_NUMBER))
        print(f'[App] 수령 확인 - 주문 {order_id}, 테이블 {table_number}')

        # FMS로 수령 확인 전송
        if self.fms_client.confirm_delivery(order_id, table_number):
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

        # pending_order 초기화 후 메인 화면으로
        self.pending_order = None
        self.go_to_main()

    def show_delivery_notification(self, order: Order):
        """배달 알림 표시"""
        print(f'[App] 배달 알림 - 주문 {order.order_id}')
        self.delivery_notification.set_order(order)
        self.setCurrentWidget(self.delivery_notification)

    def on_client_error(self, error_msg: str):
        """FMS 클라이언트 오류"""
        print(f'[App] 클라이언트 오류: {error_msg}')
        QMessageBox.warning(
            self,
            '통신 오류',
            f'FMS 통신 중 오류가 발생했습니다:\n{error_msg}',
            QMessageBox.Ok
        )

    def go_to_main(self):
        """메인 화면으로 돌아가기"""
        print('[App] 메인 화면으로 돌아가기')
        self.current_order = None
        self.setCurrentWidget(self.main_window)

    # ==================== Qt 이벤트 핸들러 ====================

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
        """종료 이벤트 (리소스 정리)"""
        self.fms_client.disconnect()
        print('[App] 애플리케이션 종료')
        event.accept()


def main():
    """메인 함수"""
    import argparse

    # 명령줄 인자 파서
    parser = argparse.ArgumentParser(description='고객용 GUI (FMS Direct)')
    parser.add_argument('--table', type=int, default=1, help='테이블 번호 (기본값: 1)')
    parser.add_argument('--mock', action='store_true', help='Mock 모드 사용')

    # PyQt의 sys.argv 처리를 위해 알려진 인자만 파싱
    args, unknown = parser.parse_known_args()

    # 테이블 번호 설정
    Config.TABLE_NUMBER = args.table

    # QApplication 생성
    app = QApplication(sys.argv)

    # 애플리케이션 설정
    app.setApplicationName(f'주문 키오스크 (테이블 {args.table})')
    app.setOrganizationName('Kitchmatics')

    # 스타일시트 적용 (하늘색 헤더, 연노란 배경)
    app.setStyleSheet(MAIN_STYLESHEET)

    # 메인 윈도우 생성 및 표시
    window = CustomerGUIApp(use_mock=args.mock)
    window.show()

    print('=' * 60)
    print('[App] 고객용 GUI 시작 (FMS Direct)')
    print(f'[App] 테이블 번호: {Config.TABLE_NUMBER}')
    print(f'[App] FMS 주소: {Config.FMS_HOST}:{Config.FMS_PORT}')
    print(f'[App] Mock 모드: {args.mock}')
    print('=' * 60)

    # 이벤트 루프 실행
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

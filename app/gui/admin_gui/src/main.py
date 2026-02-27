"""
Admin GUI 메인 애플리케이션
식당 관리자용 통합 관제 시스템
"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import Config

# 각 화면 위젯 import
from ui_dashboard import DashboardWidget
from ui_cooking_monitor import CookingMonitorWidget
from ui_recipe_management import RecipeManagementWidget
from ui_stock_management import StockManagementWidget
from ui_fleet_monitor import FleetMonitorWidget


class AdminGUIApp(QMainWindow):
    """Admin GUI 메인 애플리케이션"""

    def __init__(self, use_mock=True):
        super().__init__()
        self.use_mock = use_mock
        self.setup_ui()

    def setup_ui(self):
        """UI를 초기화합니다."""
        # 윈도우 설정
        self.setWindowTitle('식당 관리 시스템 - Admin')
        self.resize(1400, 900)

        # 중앙 위젯 및 레이아웃
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 탭 위젯 생성
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # 각 화면을 탭으로 추가
        self.dashboard = DashboardWidget(use_mock=self.use_mock)
        self.tab_widget.addTab(self.dashboard, '📊 주문 관제')

        self.cooking_monitor = CookingMonitorWidget(use_mock=self.use_mock)
        self.tab_widget.addTab(self.cooking_monitor, '🍳 조리 모니터')

        self.recipe_management = RecipeManagementWidget(use_mock=self.use_mock)
        self.tab_widget.addTab(self.recipe_management, '📖 레시피 관리')

        self.stock_management = StockManagementWidget(use_mock=self.use_mock)
        self.tab_widget.addTab(self.stock_management, '📦 재고 관리')

        self.fleet_monitor = FleetMonitorWidget(use_mock=self.use_mock)
        self.tab_widget.addTab(self.fleet_monitor, '🚗 서빙 로봇')

        # 탭 스타일 설정
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(False)

        print('[AdminGUI] 모든 화면 초기화 완료')

    def keyPressEvent(self, event):
        """키보드 이벤트를 처리합니다."""
        if event.key() == Qt.Key_Escape:
            # ESC 키로 전체화면 해제 또는 종료
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
        elif event.key() == Qt.Key_F11:
            # F11 키로 전체화면 토글
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()

    def closeEvent(self, event):
        """애플리케이션 종료 시 호출됩니다."""
        print('[AdminGUI] 애플리케이션 종료')
        event.accept()


def load_stylesheet():
    """스타일시트를 로드합니다."""
    style_path = os.path.join(os.path.dirname(__file__), '..', 'resources', 'style_admin.qss')
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        print('[AdminGUI] 스타일시트 파일을 찾을 수 없습니다.')
        return ""


def main():
    """메인 함수를 실행합니다."""
    app = QApplication(sys.argv)

    # 스타일시트 적용
    # stylesheet = load_stylesheet()
    # if stylesheet:
    #     app.setStyleSheet(stylesheet)
    #     print('[AdminGUI] 스타일시트 로드 성공')

    # Mock 모드 설정 (.env에서 USE_MOCK 읽기, 기본값 True)
    use_mock = os.getenv('USE_MOCK', 'true').lower() == 'true'
    print(f'[AdminGUI] Mock 모드: {use_mock}')

    # 메인 윈도우 생성 및 표시
    window = AdminGUIApp(use_mock=use_mock)
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

"""
FMS Customer GUI Style
1280 x 800 터치 키오스크 최적화
연노랑 배경 + 하늘색 헤더 + 큰 폰트
"""

# ===============================
# 화면 크기
# ===============================
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800


# ===============================
# 컬러 팔레트
# ===============================
COLORS = {
    "background": "#FFF8DC",     # 연노랑 크림톤
    "header": "#87CEEB",         # 하늘색
    "header_dark": "#5CACEE",    # 진한 하늘색
    "header_light": "#E0F7FF",   # 아주 연한 하늘색
    "card_bg": "#FFFFFF",        # 카드 배경
    "text_main": "#333333",
    "danger": "#E74C3C",
    "border": "#E6D8A8",
}


# ===============================
# 메인 스타일시트
# ===============================
MAIN_STYLESHEET = f"""
/* ================= 전체 ================= */
QWidget {{
    background-color: {COLORS['background']};
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    font-size: 26px;
    color: {COLORS['text_main']};
}}

/* ================= 헤더 ================= */
QLabel#label_title,
QLabel#label_menu_title,
QLabel#label_cart_title {{
    background-color: {COLORS['header']};
    color: #1F2D3D;
    font-size: 44px;
    font-weight: 700;
    padding: 24px;
    border-radius: 18px;
}}

/* ================= 환영 문구 ================= */
QLabel#label_welcome {{
    font-size: 72px;
    font-weight: bold;
    color: {COLORS['header_dark']};
    padding: 40px;
}}

/* ================= 테이블 번호 ================= */
QLabel#label_table {{
    font-size: 48px;
    font-weight: bold;
}}

/* ================= 카드 ================= */
QFrame#card {{
    background-color: {COLORS['card_bg']};
    border-radius: 20px;
    border: 1px solid {COLORS['border']};
}}

/* ================= 리스트 ================= */
QListWidget {{
    background-color: transparent;
    border: none;
}}

QListWidget::item {{
    background-color: {COLORS['card_bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 16px;
    padding: 35px;
    margin: 14px;
    font-size: 30px;
}}

QListWidget::item:hover {{
    background-color: {COLORS['header_light']};
    border: 1px solid {COLORS['header']};
}}

QListWidget::item:selected {{
    background-color: {COLORS['header']};
    color: #1F2D3D;
    border: none;
}}

/* ================= 메인 버튼 ================= */
QPushButton#btn_confirm_order,
QPushButton#btn_start_order {{
    background-color: {COLORS['header_dark']};
    color: white;
    font-size: 36px;
    font-weight: 700;
    border-radius: 20px;
    padding: 28px;
    min-height: 90px;
}}

QPushButton#btn_confirm_order:hover,
QPushButton#btn_start_order:hover {{
    background-color: {COLORS['header']};
}}

QPushButton#btn_confirm_order:pressed,
QPushButton#btn_start_order:pressed {{
    padding-top: 32px;
}}

/* ================= 취소 버튼 ================= */
QPushButton#btn_cancel {{
    background-color: {COLORS['danger']};
    color: white;
    font-size: 28px;
    border-radius: 16px;
    padding: 18px;
    min-height: 70px;
}}

QPushButton#btn_cancel:hover {{
    background-color: #C0392B;
}}

/* ================= 일반 버튼 ================= */
QPushButton {{
    background-color: {COLORS['card_bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    font-size: 26px;
    padding: 18px 24px;
    min-height: 60px;
}}

QPushButton:hover {{
    background-color: {COLORS['header_light']};
    border: 1px solid {COLORS['header']};
}}

/* ================= 합계 박스 ================= */
QLabel#label_total {{
    background-color: {COLORS['header_light']};
    border: 2px solid {COLORS['header_dark']};
    border-radius: 20px;
    font-size: 38px;
    font-weight: bold;
    padding: 30px;
}}

/* ================= 콤보박스 ================= */
QComboBox {{
    background-color: {COLORS['card_bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    padding: 14px;
    font-size: 26px;
    min-height: 60px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['card_bg']};
    selection-background-color: {COLORS['header']};
    font-size: 26px;
}}

/* ================= 스핀박스 ================= */
QSpinBox {{
    background-color: {COLORS['card_bg']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    padding: 10px;
    font-size: 28px;
    min-height: 60px;
    min-width: 120px;
}}

/* ================= 라디오 버튼 ================= */
QRadioButton {{
    font-size: 28px;
    spacing: 15px;
}}

QRadioButton::indicator {{
    width: 28px;
    height: 28px;
}}

/* ================= 스크롤바 ================= */
QScrollBar:vertical {{
    background: transparent;
    width: 14px;
}}

QScrollBar::handle:vertical {{
    background: {COLORS['header_dark']};
    border-radius: 7px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS['header']};
}}

/* ================= 다이얼로그 ================= */
QDialog {{
    background-color: {COLORS['background']};
    border-radius: 20px;
}}

QMessageBox QLabel {{
    font-size: 26px;
}}

QMessageBox QPushButton {{
    font-size: 24px;
    min-height: 60px;
}}
"""
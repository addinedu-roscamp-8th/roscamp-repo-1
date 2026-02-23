"""
환경 변수 로드 및 설정 관리
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Config:
    """애플리케이션 설정"""

    # TCP 통신 설정
    ORDER_MS_HOST = os.getenv('ORDER_MS_HOST', '127.0.0.1')
    ORDER_MS_PORT = int(os.getenv('ORDER_MS_PORT', '5000'))

    FMS_HOST = os.getenv('FMS_HOST', '127.0.0.1')
    FMS_PORT = int(os.getenv('FMS_PORT', '5001'))

    ROBOT_SERVICE_HOST = os.getenv('ROBOT_SERVICE_HOST', '127.0.0.1')
    ROBOT_SERVICE_PORT = int(os.getenv('ROBOT_SERVICE_PORT', '5002'))

    # GUI 설정
    SCREEN_WIDTH = int(os.getenv('SCREEN_WIDTH', '1024'))
    SCREEN_HEIGHT = int(os.getenv('SCREEN_HEIGHT', '768'))
    FULLSCREEN = os.getenv('FULLSCREEN', 'true').lower() == 'true'

    # 테이블 번호
    TABLE_NUMBER = int(os.getenv('TABLE_NUMBER', '1'))

    # 로그 레벨
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def get_order_ms_address(cls):
        """주문 MS 주소 반환"""
        return (cls.ORDER_MS_HOST, cls.ORDER_MS_PORT)

    @classmethod
    def get_fms_address(cls):
        """FMS 주소 반환"""
        return (cls.FMS_HOST, cls.FMS_PORT)

    @classmethod
    def get_robot_service_address(cls):
        """로봇 서비스 주소 반환"""
        return (cls.ROBOT_SERVICE_HOST, cls.ROBOT_SERVICE_PORT)

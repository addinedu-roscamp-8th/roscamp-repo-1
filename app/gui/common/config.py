"""
환경 변수 로드 및 설정 관리
Kitchmatics FMS - Closed Network Configuration
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional

# .env 파일 로드 (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv가 없어도 환경 변수에서 직접 읽을 수 있음
    pass

# Project root path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.absolute()
NETWORK_CONFIG_PATH = PROJECT_ROOT / "fms" / "config" / "network_config.yaml"


def load_network_config() -> dict:
    """YAML에서 네트워크 설정을 로드합니다."""
    if NETWORK_CONFIG_PATH.exists():
        with open(NETWORK_CONFIG_PATH, 'r') as f:
            return yaml.safe_load(f)
    return {}


class Config:
    """애플리케이션 설정"""

    # Load network config
    _network_config = load_network_config()

    # TCP 통신 설정
    ORDER_MS_HOST = os.getenv('ORDER_MS_HOST', '127.0.0.1')
    ORDER_MS_PORT = int(os.getenv('ORDER_MS_PORT', '5000'))

    # FMS Closed Network 설정 (from network_config.yaml)
    FMS_HOST = _network_config.get('master', {}).get('host', '192.168.1.3')
    FMS_PORT = _network_config.get('master', {}).get('tcp_port', 9000)

    ROBOT_SERVICE_HOST = os.getenv('ROBOT_SERVICE_HOST', '127.0.0.1')
    ROBOT_SERVICE_PORT = int(os.getenv('ROBOT_SERVICE_PORT', '5002'))

    # GUI 설정
    SCREEN_WIDTH = int(os.getenv('SCREEN_WIDTH', '1024'))
    SCREEN_HEIGHT = int(os.getenv('SCREEN_HEIGHT', '768'))
    FULLSCREEN = os.getenv('FULLSCREEN', 'true').lower() == 'true'

    # 테이블 번호
    TABLE_NUMBER = int(os.getenv('TABLE_NUMBER', '1'))

    # Voice 처리 서버 URL (음성 주문 GUI가 STT/웨이크업/order_turn/TTS 호출 시 사용)
    # 미설정 시 로컬 기본값. 다른 호스트/포트 사용 시 예: VOICE_SERVER_URL=http://192.168.1.10:8000
    VOICE_SERVER_URL = os.getenv('VOICE_SERVER_URL', 'http://127.0.0.1:8000').rstrip('/')

    # 로그 레벨
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Network settings from config
    WIFI_SSID = _network_config.get('network', {}).get('wifi_ssid', 'kitchmatics')
    CONNECTION_TIMEOUT = _network_config.get('network', {}).get('connection_timeout', 5.0)
    HEARTBEAT_INTERVAL = _network_config.get('network', {}).get('heartbeat_interval', 1.0)

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

    @classmethod
    def get_mobile_robots(cls) -> Dict[str, dict]:
        """모든 mobile robot 설정을 가져옵니다."""
        return cls._network_config.get('mobile_robots', {})

    @classmethod
    def get_cobot_arms(cls) -> Dict[str, dict]:
        """모든 cobot arm 설정을 가져옵니다."""
        return cls._network_config.get('cobot_arms', {})

    @classmethod
    def get_enabled_robots(cls) -> List[dict]:
        """활성화된 로봇 목록을 가져옵니다."""
        robots = []
        for name, cfg in cls.get_mobile_robots().items():
            if cfg.get('enabled', False):
                cfg['name'] = name
                robots.append(cfg)
        for name, cfg in cls.get_cobot_arms().items():
            if cfg.get('enabled', False):
                cfg['name'] = name
                robots.append(cfg)
        return robots

    @classmethod
    def get_robot_by_id(cls, robot_id: str) -> Optional[dict]:
        """robot_id로 로봇 설정을 가져옵니다."""
        for name, cfg in cls.get_mobile_robots().items():
            if cfg.get('robot_id') == robot_id:
                cfg['name'] = name
                return cfg
        for name, cfg in cls.get_cobot_arms().items():
            if cfg.get('robot_id') == robot_id:
                cfg['name'] = name
                return cfg
        return None

    @classmethod
    def reload_config(cls):
        """네트워크 설정을 다시 로드합니다."""
        cls._network_config = load_network_config()
        cls.FMS_HOST = cls._network_config.get('master', {}).get('host', '192.168.1.3')
        cls.FMS_PORT = cls._network_config.get('master', {}).get('tcp_port', 9000)

from enum import Enum, auto


class DockState(Enum):
    # -------------------------
    # 기본 상태
    # -------------------------
    IDLE = auto()          # 대기
    SEARCH = auto()        # 마커 탐색

    # -------------------------
    # [UPDATED] 정렬 단계 세분화
    # -------------------------
    CENTERING = auto()     # 화면 중앙 맞추기 (center_x_err)

    FACE_ALIGN_TRANSLATE = auto()   # [NEW] 위치 이동으로 법선 각도 줄이기
    FACE_ALIGN_ROTATE = auto()      # [NEW] 회전만으로 법선 미세 정렬
    
    VERIFY_POSE = auto()   # 정렬 안정성 검증

    # -------------------------
    # 접근 / 완료
    # -------------------------
    APPROACH = auto()      # 거리 접근
    FINAL_ALIGN = auto()   # (선택) 최종 미세 정렬
    DOCKED = auto()        # 도킹 완료

    # -------------------------
    # 예외
    # -------------------------
    FAILSAFE = auto()      # 마커 유실 / 타임아웃

#!/usr/bin/env python3
"""
Kitchmatics Presentation PDF Generator - Full Version (75 slides)
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

MAIN_COLOR = colors.HexColor('#2C3E50')
ACCENT_COLOR = colors.HexColor('#E74C3C')
SECONDARY_COLOR = colors.HexColor('#3498DB')
SUCCESS_COLOR = colors.HexColor('#27AE60')
WARNING_COLOR = colors.HexColor('#F39C12')

class PDFPresentation:
    def __init__(self, filename):
        self.filename = filename
        self.slides = []

    def add_slide(self, title, content, slide_type="normal", notes=""):
        self.slides.append({
            'title': title,
            'content': content,
            'type': slide_type,
            'notes': notes
        })

    def draw_slide(self, c, slide, page_num):
        c.setFillColor(colors.white)
        c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1)

        if slide['type'] == 'title':
            self._draw_title_slide(c, slide)
        elif slide['type'] == 'section':
            self._draw_section_slide(c, slide)
        elif slide['type'] == 'problem':
            self._draw_problem_slide(c, slide, page_num)
        elif slide['type'] == 'solution':
            self._draw_solution_slide(c, slide, page_num)
        else:
            self._draw_normal_slide(c, slide, page_num)

    def _draw_title_slide(self, c, slide):
        c.setFillColor(MAIN_COLOR)
        c.setFont("Helvetica-Bold", 48)
        c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT / 2 + 50, slide['title'])

        c.setFillColor(SECONDARY_COLOR)
        c.setFont("Helvetica", 28)
        for i, line in enumerate(slide['content']):
            c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT / 2 - 30 - (i * 35), line)

    def _draw_section_slide(self, c, slide):
        c.setFillColor(MAIN_COLOR)
        c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica", 24)
        c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT / 2 + 60, slide['content'][0] if slide['content'] else "")

        c.setFont("Helvetica-Bold", 44)
        c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT / 2, slide['title'])

        if len(slide['content']) > 1:
            c.setFont("Helvetica", 20)
            c.setFillColor(colors.HexColor('#CCCCCC'))
            c.drawCentredString(PAGE_WIDTH / 2, PAGE_HEIGHT / 2 - 50, slide['content'][1])

    def _draw_problem_slide(self, c, slide, page_num):
        c.setFillColor(ACCENT_COLOR)
        c.rect(0, PAGE_HEIGHT - 70, PAGE_WIDTH, 70, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(40, PAGE_HEIGHT - 45, "⚠️ " + slide['title'])

        self._draw_content(c, slide['content'], page_num)

    def _draw_solution_slide(self, c, slide, page_num):
        c.setFillColor(SUCCESS_COLOR)
        c.rect(0, PAGE_HEIGHT - 70, PAGE_WIDTH, 70, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(40, PAGE_HEIGHT - 45, "✓ " + slide['title'])

        self._draw_content(c, slide['content'], page_num)

    def _draw_normal_slide(self, c, slide, page_num):
        c.setFillColor(MAIN_COLOR)
        c.rect(0, PAGE_HEIGHT - 70, PAGE_WIDTH, 70, fill=1)

        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 26)
        c.drawString(40, PAGE_HEIGHT - 45, slide['title'])

        self._draw_content(c, slide['content'], page_num)

    def _draw_content(self, c, content, page_num):
        y = PAGE_HEIGHT - 100
        for line in content:
            if y < 50:
                break
            if line.startswith('##'):
                c.setFont("Helvetica-Bold", 18)
                c.setFillColor(SECONDARY_COLOR)
                c.drawString(50, y, line.replace('##', '').strip())
                y -= 30
            elif line.startswith('-'):
                c.setFont("Helvetica", 14)
                c.setFillColor(MAIN_COLOR)
                c.drawString(60, y, "• " + line[1:].strip())
                y -= 22
            elif line.startswith('  -'):
                c.setFont("Helvetica", 12)
                c.setFillColor(colors.HexColor('#555555'))
                c.drawString(80, y, "◦ " + line[3:].strip())
                y -= 20
            elif line == '':
                y -= 10
            else:
                c.setFont("Helvetica", 14)
                c.setFillColor(MAIN_COLOR)
                c.drawString(50, y, line)
                y -= 22

        c.setFillColor(colors.HexColor('#888888'))
        c.setFont("Helvetica", 10)
        c.drawRightString(PAGE_WIDTH - 40, 25, f"{page_num} / {len(self.slides)}")

    def generate(self):
        c = canvas.Canvas(self.filename, pagesize=landscape(A4))
        for i, slide in enumerate(self.slides, 1):
            self.draw_slide(c, slide, i)
            if i < len(self.slides):
                c.showPage()
        c.save()
        print(f"PDF generated: {self.filename}")


def main():
    pdf = PDFPresentation("/home/gw/kitchmatics/roscamp-repo-1/presentation/kitchmatics_presentation_full.pdf")

    # Part 1: Introduction
    pdf.add_slide("🍔 Kitchmatics", ["AI-Powered Autonomous Restaurant System", "Multi-Robot Fleet Management | Computer Vision | Voice AI"], "title")
    pdf.add_slide("📋 Agenda", ["## Part 1-3", "- 프로젝트 소개, 시스템 아키텍처, FMS 설계", "", "## Part 4-5", "- 모바일 로봇, 문제 해결 사례 (4건)", "", "## Part 6-11", "- AI 서버, 로봇팔, GUI, 테스트, 성능, 결론"])
    pdf.add_slide("👥 팀 소개", ["## 팀 구성", "- 6명 팀원, 8주 개발", "", "## 역할 분담", "- FMS/Backend: 중앙 관제 시스템", "- Navigation: 로봇 네비게이션, SLAM", "- AI Integration: YOLO, 음성인식", "- HW/Embedded: 로봇팔 제어"])
    pdf.add_slide("🎯 프로젝트 배경", ["## 문제 인식", "- 외식업계 인력난 심화", "- 서빙 로봇 도입 증가", "", "## 우리의 접근", "- 주문 → 조리 → 서빙 전 과정 자동화", "- 다중 로봇 협업", "- AI 기반 품질 관리"])
    pdf.add_slide("🎯 프로젝트 목표", ["## 1. 다중 로봇 관제", "- 3대 이상의 서빙 로봇 관리", "", "## 2. End-to-End 자동화", "- 주문 접수부터 배달 완료까지", "", "## 3. AI 품질 관리", "- 컴퓨터 비전으로 검증", "", "## 4. 음성 주문", "- 자연어 명령 처리"])
    pdf.add_slide("📊 프로젝트 지표", ["## 코드베이스", "- 10,225+ Lines of Code", "- 155 Test Cases", "- 23 ROS2 Nodes", "", "## 하드웨어", "- 3 Mobile Robots (TurtleBot3)", "- 2 Robot Arms (MyCobot 280)", "- 5 Domain IDs"])
    pdf.add_slide("🛠 기술 스택", ["## Core Platform", "- ROS2 Humble, CycloneDDS, Nav2, Python 3.10+", "", "## AI/ML", "- YOLOv8, OpenAI Whisper, GPT-4", "", "## Backend & Frontend", "- FastAPI, PostgreSQL, PyQt5, TCP/JSON"])

    # Part 2: System Architecture
    pdf.add_slide("System Architecture", ["Part 2", "시스템 아키텍처"], "section")
    pdf.add_slide("🏗 전체 시스템 구성", ["## 핵심 구성요소", "- Customer GUI (Kiosk) - 고객 주문", "- Admin GUI - 관리자 모니터링", "- AI Server - YOLO/Voice", "- FMS - 중앙 관제", "- Mobile Robots - pinky1, pinky2, pinky3", "- Robot Arms - 조리"])
    pdf.add_slide("🤖 하드웨어 구성", ["## Mobile Robots (3대)", "- TurtleBot3 Burger, LiDAR, Raspberry Pi 4", "", "## Robot Arms (2대)", "- MyCobot 280, 6축, 250g 페이로드", "", "## Master PC", "- Ubuntu 22.04, ROS2 Humble"])
    pdf.add_slide("🌐 네트워크 토폴로지", ["## Master PC (192.168.1.3)", "- FMS Node, AI Server", "", "## Mobile Robots", "- pinky1: 192.168.1.7 (Domain 11)", "- pinky2: 192.168.1.6 (Domain 12)", "- pinky3: 192.168.1.11 (Domain 13)", "", "## Robot Arm: 192.168.1.4 (Domain 20)"])
    pdf.add_slide("🔗 ROS2 Multi-Domain 설계", ["## Domain ID 배정", "- Domain 25: FMS (Master)", "- Domain 11: pinky1", "- Domain 12: pinky2", "- Domain 13: pinky3", "- Domain 20: Robot Arms", "", "## Why Multi-Domain?", "- 동일 토픽명 충돌 방지"])
    pdf.add_slide("🌉 Domain Bridge 구조", ["## 토픽 리매핑", "- /cmd_vel (Domain 11) → /pinky1/cmd_vel (Domain 25)", "- /odom (Domain 11) → /pinky1/odom (Domain 25)", "", "## 설정", "- domain_bridge.yaml에서 매핑 정의"])
    pdf.add_slide("🏛 Clean Architecture 적용", ["## 레이어 구조", "- Presentation: FMS Node, GUI", "- Application: OrderHandler, FleetController", "- Domain: Order, Robot Entities", "- Infrastructure: ROS2, TCP, Database", "", "## 의존성 규칙", "- 안쪽 → 바깥쪽 방향만 의존"])

    # Part 3: FMS Deep Dive
    pdf.add_slide("FMS Deep Dive", ["Part 3", "Fleet Management System 심층 분석"], "section")
    pdf.add_slide("🎛 FMS 개요", ["## 핵심 기능", "- 주문 수신 및 처리", "- 로봇 배차 및 경로 지정", "- 조리-서빙 동기화", "- 에러 감지 및 복구", "", "## 주요 모듈", "- fms_node.py, order_handler.py", "- fleet_controller.py, error_detector.py"])
    pdf.add_slide("📦 FMS Node 구조", ["## 주요 컴포넌트", "- Application Layer: OrderHandler, FleetController", "- Infrastructure: GUITCPServer (port=9000)", "- ROS2: Navigation Action Clients", "", "## Dependency Injection", "- 콜백으로 의존성 주입"])
    pdf.add_slide("📋 Order Handler", ["## 책임", "- 주문 Workflow 관리", "- 상태 전이 제어", "", "## 상태 전이", "- RECEIVED → COOKING → LOADING", "- → LOADED → DELIVERING", "- → ARRIVED → COMPLETED"])
    pdf.add_slide("🚗 Fleet Controller", ["## 로봇 상태", "- IDLE, MOVING, BUSY, ERROR", "", "## 배차 알고리즘", "- 우선순위: IDLE 상태 로봇", "- 거리 기반: 주방에 가까운 로봇"])
    pdf.add_slide("🔄 Order State Machine", ["## 상태 흐름", "- RECEIVED: 주문 접수", "- COOKING: 조리 중 + 로봇 이동", "- LOADING: 조리 완료 대기", "- LOADED: 적재 완료", "- DELIVERING: 테이블로 이동", "- ARRIVED: 도착, 고객 확인 대기", "- COMPLETED: 완료"])
    pdf.add_slide("⚠️ Error Detector", ["## 감지 항목", "- Navigation Timeout: 목적지 미도착", "- Robot Stuck: 이동 중 정지", "- Communication Loss: 통신 두절", "", "## 복구 옵션", "- RETRY, SKIP, MANUAL"])

    # Part 4: Mobile Robots
    pdf.add_slide("Mobile Robots", ["Part 4", "모바일 로봇 시스템"], "section")
    pdf.add_slide("🧭 Navigation Stack", ["## Nav2 구성요소", "- Nav2 BT Navigator: Behavior Tree", "- Planner (NavFn): 전역 경로", "- Controller (DWB): 지역 경로", "- Costmap 2D: 장애물 맵"])
    pdf.add_slide("📍 AMCL 위치 추정", ["## 특징", "- Particle Filter 기반", "- LiDAR + Odometry 융합", "", "## 주요 파라미터", "- min/max_particles: 500/2000", "- update_min_d: 0.2m"])
    pdf.add_slide("📌 Waypoint 관리", ["## 정의된 Waypoints", "- kitchen (point13): 음식 픽업", "- table1 ~ table4: 서빙 위치", "- pinky1_spot ~ pinky3_spot: 대기 위치", "", "## 설정", "- waypoints.yaml에서 좌표 관리"])

    # Part 5: Problems & Solutions
    pdf.add_slide("Problems & Solutions", ["Part 5", "문제 해결 사례"], "section")

    # Problem 1
    pdf.add_slide("Problem #1: DDS Discovery 실패", ["## 증상", "- Master PC에서 ros2 topic list 실행", "- 로봇의 토픽이 전혀 보이지 않음", "- SSH, ping은 정상 동작", "", "## 이상한 점", "- 네트워크는 연결되어 있음", "- ROS2만 통신 안됨"], "problem")
    pdf.add_slide("Problem #1: 조사 과정", ["## 디버깅 단계", "- 1. 로봇에서 직접 확인 → 로컬 정상", "- 2. Domain ID 확인 → 같은 ID", "- 3. Wireshark → Multicast 미수신!", "- 4. Router 확인 → Multicast 차단 발견"])
    pdf.add_slide("Problem #1: 근본 원인", ["## ROS2 DDS 기본 동작", "- 노드 발견에 Multicast UDP 사용", "- 주소: 239.255.0.1, 포트: 7400-7500", "", "## 문제점", "- WiFi AP가 Multicast 차단/제한"], "problem")
    pdf.add_slide("Solution #1: Unicast Discovery", ["## 해결 접근", "- CycloneDDS Unicast Peer Discovery", "", "## 설정", "- XML 파일에 Peer IP 명시", "- <Peer address='192.168.1.7'/>", "", "## 환경 변수", "- RMW_IMPLEMENTATION=rmw_cyclonedds_cpp"], "solution")
    pdf.add_slide("Solution #1: 구현", ["## CycloneDDS XML", "- cyclonedds_main.xml에 모든 Peer 등록", "- 각 로봇도 Master PC를 Peer로 등록", "", "## 결과", "- 모든 WiFi 환경에서 안정적 통신"], "solution")
    pdf.add_slide("Solution #1: 결과", ["## Before (Multicast)", "- WiFi AP에서 차단 → 토픽 발견 불가", "", "## After (Unicast)", "- 직접 IP-to-IP 통신 → 모든 토픽 정상", "", "## 성과", "- 모든 WiFi 환경에서 ROS2 통신 확보"], "solution")

    # Problem 2
    pdf.add_slide("Problem #2: Topic Name Collision", ["## 증상", "- 모든 로봇이 /cmd_vel, /odom 사용", "- 데이터 혼선, 구분 불가", "", "## 영향", "- 잘못된 로봇에 명령 전달", "- Fleet 관리 불가능"], "problem")
    pdf.add_slide("Problem #2: 영향", ["## 운영상 문제", "- ❌ 잘못된 로봇에 명령", "- ❌ 위치 추정 오류", "- ❌ 충돌 위험", "", "## 기술적 한계", "- ❌ TurtleBot3 펌웨어 수정 어려움", "- ❌ Nav2 토픽명 하드코딩"], "problem")
    pdf.add_slide("Solution #2: Multi-Domain Architecture", ["## 핵심 아이디어", "- 각 로봇을 별도 Domain에서 실행", "- Domain Bridge로 연결", "", "## 구조", "- Domain 11 (pinky1): /cmd_vel", "- Domain 25 (FMS): /pinky1/cmd_vel"], "solution")
    pdf.add_slide("Solution #2: Domain Bridge 설정", ["## YAML 설정", "- from_domain: 11, to_domain: 25", "- topic: /cmd_vel → /pinky1/cmd_vel", "", "## 실행", "- ros2 run domain_bridge domain_bridge"], "solution")
    pdf.add_slide("Solution #2: 결과", ["## FMS Domain 토픽 목록", "- /pinky1/cmd_vel, /pinky1/odom", "- /pinky2/cmd_vel, /pinky2/odom", "", "## 성과", "- ✅ 로봇별 명확한 토픽 구분", "- ✅ 확장 용이"], "solution")

    # Problem 3
    pdf.add_slide("Problem #3: 조리-로봇 동기화", ["## Case A: 로봇 먼저 도착", "- 음식 아직 조리 중 → 대기", "", "## Case B: 음식 먼저 완성", "- 로봇 아직 이동 중 → 품질 저하"], "problem")
    pdf.add_slide("Problem #3: 실패한 접근", ["## Approach 1: 타이머", "- 30초 대기 후 로봇 호출", "- ❌ 시간 가변적", "", "## Approach 2: 폴링", "- 주기적 상태 확인", "- ❌ CPU 낭비, 반응 지연"], "problem")
    pdf.add_slide("Solution #3: Event-Driven State Machine", ["## 핵심 원칙", "- 독립적 이벤트로 처리", "- AND 조건으로 다음 단계", "", "## 구현", "- cooking_complete + robot_at_kitchen", "- 둘 다 True면 LOADED로 전이"], "solution")
    pdf.add_slide("Solution #3: 상태 다이어그램", ["## COOKING 상태에서 분기", "- Event A: Robot Arrived", "- Event B: Cooking Done", "", "## AND 조건", "- A AND B 만족 시 LOADED 전이"])
    pdf.add_slide("Solution #3: 결과", ["## 측정 지표", "- Race Conditions: 0", "- 동기화 성공률: 100%", "- 대기 시간 감소: -40%", "", "## 추가 이점", "- 디버깅 용이, 테스트 용이"], "solution")

    # Problem 4
    pdf.add_slide("Problem #4: GUI-FMS 통신", ["## 요구사항", "- 주문 전송, 도착 알림 (Push)", "- 수령 확인, 실시간 업데이트", "", "## 제약사항", "- ❌ GUI에 ROS2 설치 불가", "- ✅ TCP/IP 사용 가능"], "problem")
    pdf.add_slide("Solution #4: TCP/JSON Protocol", ["## 메시지 포맷", "- 4-byte length header + JSON", "", "## 메시지 타입", "- new_order: 주문", "- delivery_notification: Push", "- delivery_complete: 수령 확인"], "solution")
    pdf.add_slide("Solution #4: 서버 구현", ["## GUITCPServer", "- Thread-per-client 모델", "- Handler 패턴으로 확장", "- broadcast()로 Push 알림"])
    pdf.add_slide("Solution #4: 결과", ["## 성능", "- 주문 처리: <100ms", "- Push 알림: <50ms", "", "## 장점", "- ✅ ROS2 없이 실시간 통신", "- ✅ 다양한 클라이언트 지원"], "solution")

    # Part 6: AI Integration
    pdf.add_slide("AI Integration", ["Part 6", "AI 서버 통합"], "section")
    pdf.add_slide("🤖 AI 서버 구성", ["## YOLO Server", "- YOLOv8, 음식 품질 검사, FastAPI", "", "## Voice Server", "- Whisper STT, GPT-4 Function Calling", "- OpenAI TTS"])
    pdf.add_slide("📸 YOLOv8: 학습 데이터", ["## 데이터셋", "- 빵, 패티, 치즈, 양상추, 토마토", "- 각 350~500장", "", "## 학습 설정", "- YOLOv8n, 100 epochs, 640x640"])
    pdf.add_slide("📸 YOLOv8: 통합", ["## API", "- POST /detect", "- 입력: 이미지, 출력: detections", "", "## FMS 연동", "- 필요한 재료 모두 감지 시 조리 완료"])
    pdf.add_slide("🎤 음성 인식 파이프라인", ["## 처리 흐름", "- Microphone → Whisper → Text", "- → GPT-4 Function Calling → JSON", "- → TTS → Speaker", "", "## 예시", "- '치즈버거 두 개' → {menu, qty}"])
    pdf.add_slide("🎤 GPT-4 Function Calling", ["## Function 정의", "- name: create_order", "- parameters: menu_name, quantity", "", "## 동작", "- 자연어 → 구조화된 JSON"])

    # Part 7: Robot Arm
    pdf.add_slide("Robot Arm", ["Part 7", "로봇팔 시스템"], "section")
    pdf.add_slide("🦾 로봇팔 하드웨어", ["## MyCobot 280", "- 6축, 250g 페이로드, 280mm 도달", "", "## End Effector", "- Gripper, 0-70mm"])
    pdf.add_slide("🦾 FMS 연동", ["## 토픽 인터페이스", "- /arm/command: 조리 명령", "- /arm/status: 상태 보고", "", "## 명령 형식", "- job_id, operation, order"])
    pdf.add_slide("🦾 레시피 실행", ["## RecipeExecutor", "- YAML 레시피 로드", "- step별 순차 실행", "", "## 레시피 단계", "- 하단빵 → 패티 → 치즈 → 양상추 → 상단빵"])

    # Part 8: GUI
    pdf.add_slide("GUI Development", ["Part 8", "사용자 인터페이스"], "section")
    pdf.add_slide("📱 Customer GUI", ["## 주요 화면", "- 메뉴 선택, 장바구니, 결제", "- 대기, 도착 알림", "", "## 기술", "- PyQt5, TCP/JSON"])
    pdf.add_slide("📱 주문 플로우", ["## 단계", "- 1. 메뉴 선택", "- 2. 장바구니", "- 3. 결제", "- 4. 주문 대기", "- 5. 도착 알림", "- 6. 수령 확인"])
    pdf.add_slide("🖥 Admin GUI", ["## 모니터링", "- Fleet 상태, 주문 현황, 에러 알림", "", "## 제어", "- 수동 배차, 긴급 정지, 복귀 명령"])

    # Part 9: Testing
    pdf.add_slide("Testing Strategy", ["Part 9", "테스트 전략"], "section")
    pdf.add_slide("🧪 테스트 아키텍처", ["## 테스트 피라미드", "- Integration Tests: E2E Flow", "- Component Tests: FMS, Nav, AI", "- Unit Tests: Functions & Classes"])
    pdf.add_slide("🧪 Skip Mode", ["## 문제", "- 물리적 로봇 없이 테스트 필요", "", "## 해결", "- skip_mode 파라미터", "- 타이머로 완료 시뮬레이션"])
    pdf.add_slide("🧪 테스트 커버리지", ["## 전체 지표", "- 155 Test Cases", "- 78% Code Coverage", "- 100% Critical Path", "", "## 모듈별", "- Order Handler: 92%", "- State Machine: 100%"])

    # Part 10: Performance
    pdf.add_slide("Performance & Scalability", ["Part 10", "성능 및 확장성"], "section")
    pdf.add_slide("📈 성능 지표", ["## Latency", "- 주문: <100ms, Push: <50ms", "- Navigation: <200ms, YOLO: <100ms", "", "## Throughput", "- 동시 주문: 10+", "- 평균 배달: ~60s"])
    pdf.add_slide("🗄 데이터베이스 설계", ["## Core Tables", "- orders, order_items, menu_items", "- robots, delivery_history", "", "## 특징", "- PostgreSQL, 정규화, 인덱스 최적화"])
    pdf.add_slide("📈 확장성 설계", ["## 수평 확장", "- 로봇 추가: Domain ID만 할당", "- FMS 이중화 가능", "", "## 성능 개선", "- Redis 캐싱, AsyncIO"])

    # Part 11: Conclusion
    pdf.add_slide("Conclusion", ["Part 11", "결론 및 향후 계획"], "section")
    pdf.add_slide("📚 기술적 교훈", ["## ROS2/DDS", "- WiFi → Unicast 필수", "- Multi-Domain으로 분리", "", "## Architecture", "- Clean Architecture", "- State Machine"])
    pdf.add_slide("📚 프로세스 교훈", ["## 조기 통합 테스트", "- 인터페이스 먼저 정의", "", "## 문서화", "- API 문서, 아키텍처 다이어그램", "", "## 시뮬레이션", "- Skip Mode로 HW 없이 개발"])
    pdf.add_slide("🚀 향후 계획: 단기", ["## 3개월 내", "- 로봇 5대 확장", "- 웹 Admin Dashboard", "", "## 6개월 내", "- Mobile App", "- 분석 대시보드"])
    pdf.add_slide("🚀 향후 계획: 장기", ["## 1년 내", "- 다층 건물 네비게이션", "- 자동 충전 시스템", "", "## 2년 내", "- 멀티 매장 관리", "- 완전 무인 매장"])
    pdf.add_slide("📌 요약", ["## 달성 목표", "- ✅ 다중 로봇 관제 (3대)", "- ✅ End-to-End 자동화", "- ✅ AI 품질 관리", "- ✅ 음성 주문", "", "## 핵심 성과", "- DDS Discovery 해결", "- Multi-Domain Architecture"])
    pdf.add_slide("감사합니다", ["Q&A", "", "📧 kitchmatics@example.com"], "title")

    pdf.generate()
    print(f"Total slides: {len(pdf.slides)}")


if __name__ == "__main__":
    main()

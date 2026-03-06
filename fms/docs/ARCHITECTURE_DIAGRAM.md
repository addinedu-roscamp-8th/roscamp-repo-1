# FMS GUI 주문 통합 - 아키텍처 다이어그램

## 시스템 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Customer GUI (Port 9000)                        │
│                         (고객 키오스크 / 태블릿)                          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ TCP (4바이트 헤더 + JSON)
                                   │
                    ┌──────────────▼─────────────┐
                    │   new_order (명령)          │
                    │   delivery_complete        │
                    └──────────────┬─────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────────────┐
│                          FMS Node (마스터 PC)                            │
│                        ROS_DOMAIN_ID = 25/11                             │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              프레젠테이션 레이어 (fms_node.py)                   │   │
│  │  - 컴포넌트 초기화                                              │   │
│  │  - 콜백 등록                                                    │   │
│  │  - ROS2 통신 조율                                               │   │
│  └────────────┬────────────────────────────────────┬────────────────┘   │
│               │                                     │                     │
│  ┌────────────▼──────────────────┐   ┌────────────▼──────────────┐     │
│  │   애플리케이션 레이어          │   │  인프라스트럭처 레이어      │     │
│  │  (order_handler.py)            │   │  (gui_tcp_server.py)       │     │
│  │                                │   │                            │     │
│  │  - OrderWorkflow (도메인)      │   │  - TCP 서버 (Port 9000)    │     │
│  │  - handle_new_order()          │   │  - 메시지 라우팅            │     │
│  │  - handle_cooking_complete()   │   │  - 푸시 알림               │     │
│  │  - handle_robot_arrived_*()    │   │  - 클라이언트 관리          │     │
│  │  - handle_delivery_confirm()   │   │                            │     │
│  │                                │   │                            │     │
│  │  의존성 (콜백):                │   │  핸들러:                    │     │
│  │  - send_cooking_command        │   │  - new_order               │     │
│  │  - navigate_robot              │   │  - delivery_complete       │     │
│  │  - send_gui_notification       │   │                            │     │
│  │  - fleet_controller            │   │                            │     │
│  └────────────┬───────────────────┘   └────────────┬───────────────┘     │
│               │                                     │                     │
│               └─────────────────┬───────────────────┘                     │
│                                 │                                         │
└─────────────────────────────────┼─────────────────────────────────────────┘
                                  │
                  ┌───────────────┼───────────────┐
                  │               │               │
        ┌─────────▼─────────┐  ┌─▼──────────┐  ┌▼────────────────┐
        │   로봇 팔          │  │   pinky1   │  │  플릿 상태       │
        │ (ROS2 토픽)        │  │ 내비게이션  │  │  발행            │
        │                   │  │ (Action)   │  │  (ROS2 토픽)     │
        │ /cooking/order    │  │            │  │                 │
        │   ↓               │  │ /navigate_ │  │ /fms/fleet_     │
        │ CookingOrder      │  │ to_pose    │  │ status          │
        │   - order_id      │  │            │  │                 │
        │   - menu_id       │  │ 목표:      │  │                 │
        │   - quantity      │  │ - point13  │  └─────────────────┘
        │   - sauce_type    │  │ - table1   │
        │   - robot_id      │  │ - pinky1_  │
        │                   │  │   spot     │
        │ /cooking/loading_ │  │            │
        │ complete          │  │            │
        │   ↑               │  │            │
        │ LoadingComplete   │  │            │
        └───────────────────┘  └────────────┘
```

## 데이터 흐름: 주문 처리

```
1. 주문 수신
   ════════════════
   Customer GUI
      │
      │ TCP: new_order
      │ {"command": "new_order", "table_number": 1, "order": {...}}
      ▼
   GUITCPServer._process_message()
      │
      │ 핸들러로 라우팅
      ▼
   FMSNode._handle_gui_new_order()
      │
      │ 애플리케이션 레이어에 위임
      ▼
   OrderHandler.handle_new_order()
      │
      ├─→ OrderWorkflow 생성 (RECEIVED 상태)
      │
      ├─→ COOKING으로 전이
      │   └─→ 콜백: send_cooking_command
      │       └─→ /cooking/order 발행
      │
      └─→ LOADING으로 전이
          └─→ 콜백: navigate_robot('pinky1', 'point13')
              └─→ pinky1을 point13으로 내비게이션


2. 조리 & 내비게이션 (병렬)
   ════════════════════════════════
   로봇 팔                          pinky1
      │                                │
      │ 조리 중...                     │ point13으로 이동 중...
      │                                │
      ▼                                ▼
   조리 완료                         point13 도착
      │                                │
      │ /cooking/                     │ 포즈 업데이트
      │ loading_complete 발행          │
      │                                │
      ▼                                ▼
   FMSNode.loading_complete_callback()
      │
      │ 주문 핸들러에 알림
      ▼
   OrderHandler.handle_cooking_complete()
      │
      ├─→ 로봇이 point13에 있는지 확인
      │
      ├─→ LOADED로 전이
      │
      └─→ 정밀 제어 생략 (3초 지연)
          └─→ 콜백: navigate_robot('pinky1', 'table1')


3. 테이블 배달
   ═══════════════
   pinky1
      │
      │ table1로 이동 중...
      │
      ▼
   table1 도착
      │
      │ 포즈 업데이트가 내비게이션 확인을 트리거
      ▼
   FMSNode._check_navigation_status_with_order_handler()
      │
      │ 테이블 도착 감지
      ▼
   OrderHandler.handle_robot_arrived_table()
      │
      ├─→ ARRIVED로 전이
      │
      └─→ 콜백: send_gui_notification
          │
          │ 푸시 알림
          ▼
   GUITCPServer.broadcast()
      │
      │ TCP: delivery_notification
      │ {"type": "delivery_notification", "data": {...}}
      ▼
   Customer GUI (푸시 알림 수신)


4. 배달 확인
   ═══════════════════════
   Customer GUI
      │
      │ 고객이 수령 확인
      │
      │ TCP: delivery_complete
      │ {"command": "delivery_complete", "order_id": "...", "table_number": 1}
      ▼
   GUITCPServer._process_message()
      │
      │ 핸들러로 라우팅
      ▼
   FMSNode._handle_gui_delivery_complete()
      │
      │ 애플리케이션 레이어에 위임
      ▼
   OrderHandler.handle_delivery_confirmation()
      │
      ├─→ COMPLETED로 전이
      │
      ├─→ 콜백: fleet_controller('pinky1', 'complete_delivery')
      │   └─→ 로봇 상태를 RETURNING으로 업데이트
      │
      └─→ 콜백: navigate_robot('pinky1', 'pinky1_spot')
          │
          │ 홈으로 내비게이션
          ▼
   pinky1 주차 지점으로 복귀
      │
      │ 포즈 업데이트가 내비게이션 확인을 트리거
      ▼
   로봇 상태 → IDLE (다음 주문 대기)
```

## 상태 머신: OrderWorkflow

```
┌─────────────┐
│  RECEIVED   │  ← 초기 상태 (GUI 주문 수신)
└──────┬──────┘
       │ send_cooking_command()
       │ navigate_robot('point13')
       ▼
┌─────────────┐
│   COOKING   │  ← 로봇 팔 조리 중, pinky1이 point13으로 이동 중
└──────┬──────┘
       │ 로봇이 point13에 도착
       ▼
┌─────────────┐
│   LOADING   │  ← 조리 완료 대기 중
└──────┬──────┘
       │ cooking_complete()
       ▼
┌─────────────┐
│   LOADED    │  ← 음식 준비 완료, 정밀 제어 생략
└──────┬──────┘
       │ navigate_robot('table1')
       │ (3초 지연 후)
       ▼
┌─────────────┐
│ DELIVERING  │  ← 로봇이 테이블로 이동 중
└──────┬──────┘
       │ 로봇이 테이블에 도착
       │ send_gui_notification()
       ▼
┌─────────────┐
│   ARRIVED   │  ← 고객 확인 대기 중
└──────┬──────┘
       │ GUI에서 delivery_complete 수신
       │ navigate_robot('pinky1_spot')
       ▼
┌─────────────┐
│  COMPLETED  │  ← 주문 완료, 로봇 홈으로 복귀 중
└─────────────┘
       │
       ▼
   로봇 IDLE (다음 주문 대기)


오류 흐름:
┌─────────────┐
│    FAILED   │  ← 워크플로우 중 오류 발생
└─────────────┘
```

## 컴포넌트 상호작용: SOLID 원칙

```
┌────────────────────────────────────────────────────────────────┐
│                    의존성 역전 원칙                              │
│                                                                  │
│  애플리케이션 레이어 (OrderHandler)가                            │
│  구체 클래스가 아닌 추상화(콜백)에 의존                          │
│                                                                  │
│  register_callbacks(                                            │
│      send_cooking_command: Callable,    ← 추상 의존성            │
│      navigate_robot: Callable,          ← 추상 의존성            │
│      send_gui_notification: Callable,   ← 추상 의존성            │
│      fleet_controller: Callable         ← 추상 의존성            │
│  )                                                               │
│                                                                  │
│  구현은 FMSNode (인프라스트럭처 레이어)가 제공                    │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    단일 책임 원칙                                │
│                                                                  │
│  OrderHandler:        주문 워크플로우 오케스트레이션              │
│  GUITCPServer:        TCP 통신                                   │
│  FMSNode:             ROS2 통합 및 조율                          │
│  FleetController:     로봇 플릿 관리                             │
│  OrderWorkflow:       도메인 엔티티 (상태 머신)                  │
│                                                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                    개방/폐쇄 원칙                                │
│                                                                  │
│  기존 코드를 수정하지 않고 새 메시지 타입 추가 가능              │
│                                                                  │
│  gui_tcp_server.register_handler('new_message_type', handler)   │
│                                                                  │
│  OrderWorkflow를 확장하여 새 워크플로우 상태 추가 가능           │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

## 네트워크 토폴로지

```
┌─────────────────────────────────────────────────────────────────┐
│                    kitchmatics WiFi 네트워크                      │
│                         192.168.1.x                              │
│                                                                   │
│  ┌──────────────┐         ┌──────────────┐                      │
│  │ 마스터 PC     │         │ Customer GUI │                      │
│  │ 192.168.1.3  │◄────────┤ (태블릿)      │                      │
│  │              │  TCP    │              │                      │
│  │ FMS Node     │  :9000  └──────────────┘                      │
│  │              │                                                │
│  │ DOMAIN_ID:25 │         ┌──────────────┐                      │
│  │   (FMS)      │◄────────┤ 로봇 팔       │                      │
│  │              │  ROS2   │ 192.168.1.4  │                      │
│  │ DOMAIN_ID:11 │  토픽   │              │                      │
│  │   (pinky1)   │         │ DOMAIN_ID:20 │                      │
│  └──────┬───────┘         └──────────────┘                      │
│         │                                                         │
│         │ ROS2 Action                                            │
│         │ (Domain Bridge를 통한 크로스 도메인)                     │
│         │                                                         │
│         ▼                                                         │
│  ┌──────────────┐                                                │
│  │ pinky1       │                                                │
│  │ 192.168.1.7  │                                                │
│  │              │                                                │
│  │ DOMAIN_ID:11 │                                                │
│  └──────────────┘                                                │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

## 기술 스택

```
┌─────────────────────────────────────────────────────────────────┐
│                         기술 스택                                 │
├─────────────────────────────────────────────────────────────────┤
│  언어:               Python 3.10+                                │
│  프레임워크:          ROS2 Humble                                 │
│  통신:               TCP (커스텀 프로토콜)                         │
│                      ROS2 토픽/액션                                │
│  직렬화:             JSON (UTF-8)                                │
│  동시성:             스레딩 (Python)                               │
│  내비게이션:          Nav2                                        │
│  로컬라이제이션:      AMCL                                        │
│  아키텍처:           클린 아키텍처                                  │
│  원칙:               SOLID                                       │
└─────────────────────────────────────────────────────────────────┘
```

## 성능 특성

```
┌─────────────────────────────────────────────────────────────────┐
│                    성능 지표                                      │
├─────────────────────────────────────────────────────────────────┤
│  TCP 서버:           멀티 스레드 (클라이언트당 1 스레드)           │
│  메시지 처리:         비동기 (논블로킹)                            │
│  내비게이션:          동시 수행 (복수 로봇 가능)                    │
│  주문 처리:           ~30-60초 (조리 + 배달)                       │
│  지연 시간:           < 100ms (주문 접수)                          │
│                      < 50ms (푸시 알림)                           │
│  처리량:             로봇 대수에 의해 제한 (현재 1대)               │
│  확장성:             수평 확장 (로봇/FMS 인스턴스 추가)             │
└─────────────────────────────────────────────────────────────────┘
```

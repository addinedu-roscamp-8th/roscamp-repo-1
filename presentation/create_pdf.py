#!/usr/bin/env python3
"""
Kitchmatics Presentation PDF Generator
Uses reportlab to create a professional PDF presentation
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Page size
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)

# Colors
MAIN_COLOR = colors.HexColor('#2C3E50')
ACCENT_COLOR = colors.HexColor('#E74C3C')
SECONDARY_COLOR = colors.HexColor('#3498DB')
SUCCESS_COLOR = colors.HexColor('#27AE60')
LIGHT_BG = colors.HexColor('#ECF0F1')

class PDFPresentation:
    def __init__(self, filename):
        self.filename = filename
        self.slides = []

    def add_slide(self, title, content, speaker_notes=""):
        self.slides.append({
            'title': title,
            'content': content,
            'notes': speaker_notes
        })

    def draw_slide(self, canvas, slide, page_num):
        # Background
        canvas.setFillColor(colors.white)
        canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1)

        # Header bar
        canvas.setFillColor(MAIN_COLOR)
        canvas.rect(0, PAGE_HEIGHT - 80, PAGE_WIDTH, 80, fill=1)

        # Title
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 28)
        canvas.drawString(40, PAGE_HEIGHT - 55, slide['title'])

        # Content area
        y_position = PAGE_HEIGHT - 120
        canvas.setFillColor(MAIN_COLOR)
        canvas.setFont("Helvetica", 14)

        for line in slide['content']:
            if line.startswith('##'):
                # Subheading
                canvas.setFont("Helvetica-Bold", 18)
                canvas.setFillColor(SECONDARY_COLOR)
                canvas.drawString(50, y_position, line.replace('##', '').strip())
                y_position -= 35
            elif line.startswith('-'):
                # Bullet point
                canvas.setFont("Helvetica", 14)
                canvas.setFillColor(MAIN_COLOR)
                canvas.drawString(60, y_position, "•")
                canvas.drawString(80, y_position, line[1:].strip())
                y_position -= 25
            elif line.startswith('  -'):
                # Sub-bullet
                canvas.setFont("Helvetica", 12)
                canvas.setFillColor(colors.HexColor('#555555'))
                canvas.drawString(90, y_position, "◦")
                canvas.drawString(105, y_position, line[3:].strip())
                y_position -= 22
            elif line.startswith('[BOX]'):
                # Highlight box
                box_text = line.replace('[BOX]', '').strip()
                canvas.setFillColor(LIGHT_BG)
                canvas.roundRect(45, y_position - 15, PAGE_WIDTH - 90, 40, 5, fill=1)
                canvas.setFillColor(ACCENT_COLOR)
                canvas.setFont("Helvetica-Bold", 14)
                canvas.drawCentredString(PAGE_WIDTH / 2, y_position, box_text)
                y_position -= 55
            elif line.startswith('[SUCCESS]'):
                box_text = line.replace('[SUCCESS]', '').strip()
                canvas.setFillColor(colors.HexColor('#D5F5E3'))
                canvas.roundRect(45, y_position - 15, PAGE_WIDTH - 90, 40, 5, fill=1)
                canvas.setFillColor(SUCCESS_COLOR)
                canvas.setFont("Helvetica-Bold", 14)
                canvas.drawCentredString(PAGE_WIDTH / 2, y_position, box_text)
                y_position -= 55
            elif line.startswith('[CODE]'):
                code_text = line.replace('[CODE]', '').strip()
                canvas.setFillColor(colors.HexColor('#2C3E50'))
                canvas.roundRect(45, y_position - 10, PAGE_WIDTH - 90, 30, 3, fill=1)
                canvas.setFillColor(colors.HexColor('#2ECC71'))
                canvas.setFont("Courier", 11)
                canvas.drawString(55, y_position, code_text)
                y_position -= 45
            elif line == '':
                y_position -= 15
            else:
                canvas.setFont("Helvetica", 14)
                canvas.setFillColor(MAIN_COLOR)
                canvas.drawString(50, y_position, line)
                y_position -= 28

        # Page number
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.setFont("Helvetica", 10)
        canvas.drawRightString(PAGE_WIDTH - 40, 30, f"{page_num} / {len(self.slides)}")

        # Speaker notes indicator
        if slide['notes']:
            canvas.setFillColor(colors.HexColor('#AAAAAA'))
            canvas.setFont("Helvetica-Oblique", 9)
            canvas.drawString(40, 30, "[Speaker Notes Available]")

    def generate(self):
        c = canvas.Canvas(self.filename, pagesize=landscape(A4))

        for i, slide in enumerate(self.slides, 1):
            self.draw_slide(c, slide, i)
            if i < len(self.slides):
                c.showPage()

        c.save()
        print(f"PDF generated: {self.filename}")


def main():
    pdf = PDFPresentation("/home/gw/kitchmatics/roscamp-repo-1/presentation/kitchmatics_presentation.pdf")

    # Slide 1: Title
    pdf.add_slide(
        "Kitchmatics",
        [
            "",
            "",
            "## AI-Powered Autonomous Restaurant System",
            "",
            "- Multi-Robot Fleet Management",
            "- Computer Vision Food Inspection",
            "- Voice-Activated Ordering",
            "",
            "",
            "[BOX]ROS2 Humble | Nav2 | YOLOv8 | OpenAI APIs",
        ],
        "Kitchmatics 프로젝트 소개. AI 기반 자율 식당 운영 시스템입니다."
    )

    # Slide 2: Team & Project Overview
    pdf.add_slide(
        "Project Overview",
        [
            "## Team Composition",
            "- 6 Members: SW Developers + HW Integration",
            "- Development Period: 8 weeks",
            "",
            "## Key Metrics",
            "- 10,225+ Lines of Code",
            "- 155 Test Cases",
            "- 3 Mobile Robots (TurtleBot3)",
            "- 2 Robot Arms (MyCobot 280)",
            "",
            "[BOX]Full Stack: ROS2 + Backend + AI + GUI",
        ]
    )

    # Slide 3: System Architecture
    pdf.add_slide(
        "System Architecture",
        [
            "## Core Components",
            "",
            "- FMS (Fleet Management System) - Central Control",
            "- Mobile Robots - pinky1, pinky2, pinky3",
            "- Robot Arms - Sandwich Assembly",
            "- AI Servers - YOLO + Voice Recognition",
            "- GUI - Customer Kiosk + Admin Panel",
            "",
            "[CODE]Master PC (192.168.1.3) → Domain Bridge → Robots",
        ]
    )

    # Slide 4: Multi-Domain Architecture
    pdf.add_slide(
        "ROS2 Multi-Domain Architecture",
        [
            "## Domain ID Assignment",
            "",
            "- Domain 25: FMS (Master)",
            "- Domain 11: pinky1",
            "- Domain 12: pinky2",
            "- Domain 13: pinky3",
            "- Domain 20: Robot Arms",
            "",
            "[BOX]Domain Bridge for Cross-Domain Communication",
        ]
    )

    # Slide 5: Problem 1 - DDS Discovery
    pdf.add_slide(
        "Problem #1: DDS Discovery Failure",
        [
            "## Symptom",
            "- ros2 topic list shows nothing from robots",
            "- SSH connection works fine",
            "- ping successful but no ROS2 communication",
            "",
            "## Discovery Process",
            "- Wireshark: No multicast packets on WiFi",
            "- Router logs: Multicast UDP blocked",
            "",
            "[BOX]WiFi AP blocks multicast by default!",
        ]
    )

    # Slide 6: Solution 1 - Unicast Discovery
    pdf.add_slide(
        "Solution: CycloneDDS Unicast Discovery",
        [
            "## Configuration",
            "[CODE]<Peer address='192.168.1.7'/>  <!-- pinky1 -->",
            "[CODE]<Peer address='192.168.1.6'/>  <!-- pinky2 -->",
            "",
            "## Environment Setup",
            "[CODE]export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp",
            "[CODE]export CYCLONEDDS_URI=file:///path/to/cyclonedds.xml",
            "",
            "[SUCCESS]Direct IP-to-IP communication - Works on any WiFi!",
        ]
    )

    # Slide 7: Problem 2 - Topic Collision
    pdf.add_slide(
        "Problem #2: ROS2 Topic Name Collision",
        [
            "## Issue",
            "- All robots publish /cmd_vel, /odom, /scan",
            "- Single domain = mixed data",
            "- Which /amcl_pose belongs to which robot?",
            "",
            "## Impact",
            "- Navigation commands sent to wrong robot",
            "- Localization data corrupted",
            "- Fleet management impossible",
            "",
            "[BOX]Same topic names, different robots!",
        ]
    )

    # Slide 8: Solution 2 - Domain Bridge
    pdf.add_slide(
        "Solution: Domain Bridge Architecture",
        [
            "## Approach",
            "- Separate Domain ID per robot",
            "- Domain Bridge remaps topics",
            "",
            "## Topic Remapping",
            "[CODE]/cmd_vel (Domain 11) → /pinky1/cmd_vel (Domain 25)",
            "[CODE]/amcl_pose (Domain 11) → /pinky1/amcl_pose (Domain 25)",
            "",
            "[SUCCESS]Clean namespace isolation with centralized control",
        ]
    )

    # Slide 9: Navigation Stack
    pdf.add_slide(
        "Navigation: Nav2 + AMCL",
        [
            "## Stack Components",
            "- AMCL: Adaptive Monte Carlo Localization",
            "- Nav2: Path Planning + Obstacle Avoidance",
            "- TF2: Coordinate Frame Management",
            "",
            "## Waypoints",
            "- Kitchen: point13 (food pickup)",
            "- Tables: table1 ~ table4",
            "- Parking: pinky1_spot, pinky2_spot, pinky3_spot",
        ]
    )

    # Slide 10: Problem 3 - State Synchronization
    pdf.add_slide(
        "Problem #3: Robot-Cooking Synchronization",
        [
            "## Challenge",
            "- Robot arrives at kitchen before food ready",
            "- Food ready but robot still en route",
            "- Race condition in order workflow",
            "",
            "## Failed Approaches",
            "- Simple timer-based waiting",
            "- Polling status repeatedly",
            "",
            "[BOX]Need: Precise state machine coordination",
        ]
    )

    # Slide 11: Solution 3 - Event-Driven State Machine
    pdf.add_slide(
        "Solution: Event-Driven Order Workflow",
        [
            "## State Transitions",
            "- RECEIVED → COOKING → LOADING → LOADED",
            "- LOADED → DELIVERING → ARRIVED → COMPLETED",
            "",
            "## AND Condition Logic",
            "[CODE]if robot_at_kitchen AND cooking_complete:",
            "[CODE]    transition_to(LOADED)",
            "",
            "[SUCCESS]Robust synchronization via state machine!",
        ]
    )

    # Slide 12: AI - YOLO Vision
    pdf.add_slide(
        "AI Server: YOLOv8 Food Inspection",
        [
            "## Capabilities",
            "- Real-time object detection",
            "- Food quality verification",
            "- Assembly completeness check",
            "",
            "## Integration",
            "[CODE]POST /detect {'image': base64_data}",
            "[CODE]Response: {'objects': [...], 'confidence': 0.95}",
            "",
            "[BOX]Custom trained model for sandwich ingredients",
        ]
    )

    # Slide 13: AI - Voice Recognition
    pdf.add_slide(
        "AI Server: Voice Ordering System",
        [
            "## Pipeline",
            "- Whisper API: Speech-to-Text",
            "- GPT-4 Function Calling: Intent Extraction",
            "- TTS: Order Confirmation",
            "",
            "## Example Flow",
            "[CODE]'치즈버거 두 개 주세요' → {menu: 'cheeseburger', qty: 2}",
            "",
            "[SUCCESS]Natural language order processing",
        ]
    )

    # Slide 14: GUI Architecture
    pdf.add_slide(
        "GUI: Customer & Admin Interfaces",
        [
            "## Customer GUI (PyQt5)",
            "- Touch-friendly kiosk interface",
            "- Menu selection with images",
            "- Real-time order tracking",
            "- Delivery notification popup",
            "",
            "## Admin GUI",
            "- Fleet status monitoring",
            "- Order management",
            "- Robot manual control",
        ]
    )

    # Slide 15: Problem 4 - TCP Communication
    pdf.add_slide(
        "Problem #4: GUI-FMS Communication",
        [
            "## Challenge",
            "- GUI runs on separate device (tablet)",
            "- ROS2 not available on Android/tablets",
            "- Need bidirectional real-time updates",
            "",
            "## Requirements",
            "- Push notifications (delivery arrived)",
            "- Reliable message delivery",
            "- Low latency (<100ms)",
        ]
    )

    # Slide 16: Solution 4 - TCP Protocol
    pdf.add_slide(
        "Solution: Custom TCP/JSON Protocol",
        [
            "## Protocol Design",
            "[CODE]4-byte length header + JSON payload",
            "",
            "## Message Types",
            "- new_order: Customer places order",
            "- delivery_notification: Push to customer",
            "- delivery_complete: Customer confirms receipt",
            "",
            "[SUCCESS]Thread-per-client model for reliability",
        ]
    )

    # Slide 17: Error Handling
    pdf.add_slide(
        "Error Detection & Recovery",
        [
            "## ErrorDetector Features",
            "- Navigation timeout detection",
            "- Robot stuck detection",
            "- Communication failure handling",
            "",
            "## Recovery Options",
            "- RETRY: Attempt same action again",
            "- SKIP: Proceed to next step",
            "- MANUAL: Request operator intervention",
            "",
            "[BOX]Graceful degradation for production stability",
        ]
    )

    # Slide 18: Testing Strategy
    pdf.add_slide(
        "Testing: Skip Mode Architecture",
        [
            "## Problem",
            "- Physical robots not always available",
            "- Need to test FMS logic independently",
            "",
            "## Skip Mode Features",
            "- Simulated navigation completion",
            "- Mock sensor data",
            "- Accelerated time (configurable delay)",
            "",
            "[CODE]ros2 run fms fms_node --ros-args -p skip_mode:=true",
        ]
    )

    # Slide 19: Database Design
    pdf.add_slide(
        "Database: PostgreSQL Schema",
        [
            "## Core Tables",
            "- orders: Order tracking with status",
            "- menu_items: Menu catalog",
            "- robots: Fleet status",
            "- delivery_history: Analytics data",
            "",
            "## Features",
            "- Timestamp tracking for SLA",
            "- Foreign key relationships",
            "- Index optimization for queries",
        ]
    )

    # Slide 20: Performance Metrics
    pdf.add_slide(
        "Performance Characteristics",
        [
            "## Latency",
            "- Order acceptance: <100ms",
            "- Push notification: <50ms",
            "- Navigation goal: <200ms",
            "",
            "## Throughput",
            "- Order processing: ~60 seconds average",
            "- Concurrent robots: 3 (scalable)",
            "",
            "[BOX]Production-ready performance",
        ]
    )

    # Slide 21: Lessons Learned
    pdf.add_slide(
        "Key Lessons Learned",
        [
            "## Technical Insights",
            "- WiFi multicast is unreliable - use unicast",
            "- Domain separation simplifies multi-robot",
            "- State machines prevent race conditions",
            "",
            "## Process Insights",
            "- Skip mode enables parallel development",
            "- Good logging saves debugging time",
            "- Integration tests catch real issues",
        ]
    )

    # Slide 22: Future Roadmap
    pdf.add_slide(
        "Future Development",
        [
            "## Short-term",
            "- Additional robot support (5+ fleet)",
            "- Enhanced voice commands",
            "- Mobile app for customers",
            "",
            "## Long-term",
            "- Multi-floor navigation",
            "- Autonomous charging",
            "- ML-based demand prediction",
        ]
    )

    # Slide 23: Conclusion
    pdf.add_slide(
        "Conclusion",
        [
            "",
            "## Kitchmatics Achievement",
            "",
            "- Fully integrated autonomous restaurant system",
            "- Multi-robot coordination with FMS",
            "- AI-powered food inspection & voice ordering",
            "- Production-ready error handling",
            "",
            "",
            "[SUCCESS]From concept to working prototype in 8 weeks",
        ]
    )

    pdf.generate()
    print("PDF presentation created successfully!")


if __name__ == "__main__":
    main()

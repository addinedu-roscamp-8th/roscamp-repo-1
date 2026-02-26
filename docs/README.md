# Kitchmatics FMS Documentation

**Last Updated:** 2026-02-25
**Version:** 1.0
**Audience:** FMS Team, Precision Control Team, Robot Arm Team, QA/Testing Team

---

## Documentation Overview

This directory contains comprehensive interface and testing documentation for the Kitchmatics Fleet Management System (FMS) integration with external teams.

### Document Index

1. **[INTEGRATION_QUICKSTART.md](./INTEGRATION_QUICKSTART.md)** ← START HERE
   - 2-minute quick reference for each team
   - Essential commands and configurations
   - Common troubleshooting
   - **Best for:** Quick reference, getting started

2. **[external_interfaces.md](./external_interfaces.md)** ← DETAILED SPECS
   - Complete interface specification
   - Message format definitions
   - Network architecture and domain IDs
   - State machine and error handling
   - Testing procedures for external teams
   - **Best for:** Implementation details, integration planning

3. **[skip_mode_guide.md](./skip_mode_guide.md)** ← TESTING GUIDE
   - Skip mode functionality and parameters
   - Testing procedures and scenarios
   - Mock message behavior and timing
   - CI/CD integration examples
   - Troubleshooting guide
   - **Best for:** Development testing, test automation

4. **개발 영역별 문서**: Backend → `app/backend/docs/`, Mobile Robot → `mobile_robot/docs/`, DB 서버 → `database/db_server/docs/`. 이력은 [문서_이동_이력.md](./문서_이동_이력.md) 참고.

---

## Which Document Should I Read?

### I'm starting my integration work

→ **Read:** [INTEGRATION_QUICKSTART.md](./INTEGRATION_QUICKSTART.md)

This gives you everything you need in 5 minutes:
- Your team's responsibilities
- Key message formats
- Example test commands
- Network setup checklist

### I need to implement the interface

→ **Read:** [external_interfaces.md](./external_interfaces.md)

This has:
- Complete ROS topic specifications
- Message type definitions
- Communication protocol details
- State machine documentation
- Error handling procedures
- Integration testing strategies

### I need to test without external systems

→ **Read:** [skip_mode_guide.md](./skip_mode_guide.md)

This covers:
- Skip mode parameters and usage
- Mock message timing
- Testing procedures
- Debugging techniques
- CI/CD integration

### I need all of the above

→ **Read in order:**
1. INTEGRATION_QUICKSTART.md (10 min)
2. external_interfaces.md (30 min)
3. skip_mode_guide.md (30 min)

---

## Project Context

### Delivery Flow

```
Customer Orders Sandwich
    ↓
Main Server Receives Order
    ↓
FMS Navigates Robot to point13
    ↓
[Point13 Arrival]
    ↓
Precision Control Team: Point13 → Pickup_Spot
    ↓
[Precision Parking Complete]
    ↓
Robot Arm Team: Load Food
    ↓
[Food Loaded]
    ↓
FMS Navigates Robot to Table
    ↓
[Table Arrival]
    ↓
Customer Receives Food
    ↓
FMS Returns Robot to Parking
    ↓
[Complete]
```

### Team Responsibilities

| Team | Scope | Input | Output |
|------|-------|-------|--------|
| **FMS** | Navigation to point13, table, parking | Order request | Robot state updates |
| **Precision Control** | Point13 → Pickup_Spot positioning | goal_arrived message | precision_parked message |
| **Robot Arm** | Food loading at pickup_spot | precision_parked message | food_loaded message |
| **Main Server** | Order management, GUI coordination | Kiosk orders | Fleet monitoring |

### Network Architecture

```
Master PC (192.168.1.3, Domain 0)
├── FMS Node
├── Main Server
└── Database (PostgreSQL)

WiFi: kitchmatics (closed network)
    │
    ├─ Mobile Robots
    │  ├── pinky1 (192.168.1.7, Domain 11)
    │  ├── pinky2 (192.168.1.6, Domain 12)
    │  └── pinky3 (TBD, Domain 13)
    │
    └─ Cobot Arms
       ├── robot_arm_1 (192.168.1.4, Domain 14)
       └── robot_arm_2 (192.168.0.59, Domain 15)
```

---

## Quick Start by Role

### Precision Control Team Lead

**Read First:** [INTEGRATION_QUICKSTART.md](./INTEGRATION_QUICKSTART.md#for-precision-control-team)

**Key Points:**
- Subscribe to: `/fms/goal_arrived`
- Publish to: `/fms/precision_parked`
- Robot path: point13 (0.585, 0.63) → pickup_spot (0.47, 0.63)
- Rotation needed: 180° to face kitchen (θ ≈ π)
- Timing: Complete within 10 seconds

**Test Setup:**
```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=false \
    -p skip_robot_arm:=true
```

---

### Robot Arm Team Lead

**Read First:** [INTEGRATION_QUICKSTART.md](./INTEGRATION_QUICKSTART.md#for-robot-arm-team)

**Key Points:**
- Subscribe to: `/fms/precision_parked`
- Publish to: `/fms/food_loaded`
- Pickup location: X=0.47m, Y=0.63m, facing kitchen
- Timing: Complete within 60 seconds
- Load weight: Max 3 kg

**Test Setup:**
```bash
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=false
```

---

### FMS Developer

**Read First:** [INTEGRATION_QUICKSTART.md](./INTEGRATION_QUICKSTART.md)
**Then Read:** [skip_mode_guide.md](./skip_mode_guide.md)

**Key Features:**
- Skip mode for independent development
- 2194 lines of documentation covering all aspects
- Example test commands for each scenario
- Debugging and troubleshooting guides

**Development Setup:**
```bash
# Full skip mode for rapid iteration
ros2 run fms fms_node --ros-args \
    -p skip_precision:=true \
    -p skip_robot_arm:=true \
    -p skip_mode_timing:="fast"
```

---

### QA/Testing Team

**Read First:** [INTEGRATION_QUICKSTART.md](./INTEGRATION_QUICKSTART.md#for-qa-testing-team)
**Then Read:** [skip_mode_guide.md](./skip_mode_guide.md#testing-procedures)

**Key Procedures:**
- Standard test procedure (complete flow)
- Partial integration tests (one team at a time)
- Multi-robot concurrent tests
- Error scenario testing
- CI/CD automation

---

## Key Features of This Documentation

### 1. Role-Based Guidance

Each team gets specific guidance for their responsibilities:
- What messages to listen for
- What messages to publish
- Expected timing and constraints
- Example test commands

### 2. Multiple Difficulty Levels

- **Quick Start:** 2-5 minute overview
- **Standard:** Detailed but focused reference
- **Deep Dive:** Complete specification with examples

### 3. Practical Examples

All documents include:
- Bash command examples
- ROS topic examples
- Python code snippets
- YAML configuration examples
- Troubleshooting procedures

### 4. Testing Strategies

Multiple testing approaches:
- Skip mode development
- Partial integration (one team at a time)
- Full integration (all teams)
- Error scenario testing
- Automated CI/CD tests

### 5. Network Configuration

Clear guidance on:
- ROS_DOMAIN_ID setup
- WiFi connectivity
- Port usage
- Multi-domain communication

---

## Common Tasks and Where to Find Them

### Task: Set up my development environment

**Location:**
- INTEGRATION_QUICKSTART.md → Network Checklist
- external_interfaces.md → Network Configuration

### Task: Understand the complete delivery flow

**Location:**
- INTEGRATION_QUICKSTART.md → Quick Links (overview)
- external_interfaces.md → Delivery Flow and Message Exchange (detailed)
- skip_mode_guide.md → State Diagram with Skip Mode (visual)

### Task: Test my implementation without other teams

**Location:**
- skip_mode_guide.md → Skip Mode Workflow
- skip_mode_guide.md → Testing Procedures

### Task: Integrate with FMS without external teams

**Location:**
- external_interfaces.md → Per-Robot Topics (communication patterns)
- skip_mode_guide.md → Complete Skip Mode Workflow

### Task: Test with other teams

**Location:**
- external_interfaces.md → Testing Strategies for External Teams
- INTEGRATION_QUICKSTART.md → Partial Integration Tests

### Task: Debug a message format issue

**Location:**
- external_interfaces.md → ROS 2 Topic Specifications
- external_interfaces.md → Appendix B: Message Format Examples
- INTEGRATION_QUICKSTART.md → Message Format Examples

### Task: Troubleshoot network problems

**Location:**
- INTEGRATION_QUICKSTART.md → Network Checklist
- INTEGRATION_QUICKSTART.md → ROS Domain ID Setup
- external_interfaces.md → Network Configuration

---

## Documentation Statistics

| Aspect | Details |
|--------|---------|
| **Total Lines** | 2,194 lines of documentation |
| **Total Size** | 68 KB |
| **Documents** | 4 files |
| **Topics Covered** | 50+ major sections |
| **Code Examples** | 30+ practical examples |
| **Message Types** | 6 ROS 2 message types defined |
| **Test Procedures** | 8 detailed testing scenarios |

---

## Integration Checklist

Before starting integration work:

### Planning Phase
- [ ] Read INTEGRATION_QUICKSTART.md
- [ ] Identify your team's role
- [ ] Review your team's responsibilities
- [ ] Note key message formats

### Setup Phase
- [ ] Verify network connectivity
- [ ] Set ROS_DOMAIN_ID environment variables
- [ ] Configure FMS skip mode parameters
- [ ] Verify ROS 2 installation (Jazzy)

### Development Phase
- [ ] Test with skip mode enabled
- [ ] Implement message publishing/subscribing
- [ ] Validate message formats
- [ ] Test timing constraints

### Integration Phase
- [ ] Test with one external team
- [ ] Test with all external teams
- [ ] Document any issues
- [ ] Record actual timing data

### Validation Phase
- [ ] Run complete end-to-end test
- [ ] Verify all constraints met
- [ ] Test error scenarios
- [ ] Performance testing

---

## Message Format Reference

### At a Glance

| Message | Topic | Direction | Type | Critical Content |
|---------|-------|-----------|------|-----------------|
| goal_arrived | `/fms/goal_arrived` | FMS → Precision | String | "pinky{1,2,3}_arrived_at_point13" |
| precision_parked | `/fms/precision_parked` | Precision → FMS | String | "precision_parked:pinky{1,2,3}" |
| food_loaded | `/fms/food_loaded` | Arm → FMS | String | "food_loaded:pinky{1,2,3}" |
| delivery_complete | `/fms/delivery_complete` | GUI → FMS | DeliveryComplete | order_id, table_number |
| fleet_status | `/fms/fleet_status` | FMS → All | FleetStatus | robot_ids, robot_status, battery_levels |

**For Complete Specifications:** See [external_interfaces.md](./external_interfaces.md#ros-2-topic-specifications)

---

## Timing Constraints

| Operation | Timeout | Consequence |
|-----------|---------|------------|
| Precision Parking | 10 seconds | Alert, retry |
| Food Loading | 60 seconds | Alert, wait or cancel |
| Table Delivery | 300 seconds | Alert, timeout |
| Return to Parking | 60 seconds | Alert, timeout |

---

## Support and Questions

### For Questions About...

| Topic | Where to Look |
|-------|---------------|
| Message formats | external_interfaces.md → ROS 2 Topic Specifications |
| Skip mode | skip_mode_guide.md → Complete section |
| Testing procedures | skip_mode_guide.md → Testing Procedures |
| Network setup | external_interfaces.md → Network Configuration |
| Troubleshooting | INTEGRATION_QUICKSTART.md → Troubleshooting Quick Reference |
| Your team's role | INTEGRATION_QUICKSTART.md → Role-specific sections |

### Get Help

1. **Check the troubleshooting section** in relevant document
2. **Search for your keyword** in all documents
3. **Post in Slack** #fms-channel with:
   - Document you read
   - What you tried
   - Error message or unexpected behavior
4. **File Jira issue** with label "integration" or "interface"

---

## Document Versions

| Doc | Version | Updated | Status |
|-----|---------|---------|--------|
| INTEGRATION_QUICKSTART.md | 1.0 | 2026-02-25 | Ready |
| external_interfaces.md | 1.0 | 2026-02-25 | Ready |
| skip_mode_guide.md | 1.0 | 2026-02-25 | Ready |
| README.md | 1.0 | 2026-02-25 | Current |

### Update Policy

- Updates required for interface changes → Notify all teams
- Minor fixes/clarifications → Update immediately
- New test procedures → Update skip_mode_guide.md
- New integration findings → Update external_interfaces.md

---

## Related Project Files

For additional context, see:

- **FMS Configuration:** `/home/gw/kitchmatics/roscamp-repo-1/fms/config/`
  - `network_config.yaml` - Robot and network settings
  - `fms_config.yaml` - Map positions and zones

- **ROS Messages:** `/home/gw/kitchmatics/roscamp-repo-1/fleet_interfaces/msg/`
  - OrderRequest.msg
  - DeliveryComplete.msg
  - FleetStatus.msg

- **Main README:** `/home/gw/kitchmatics/roscamp-repo-1/README.md`
  - Project overview
  - Build and installation
  - Running instructions

- **CLAUDE.md:** Project guide and best practices

---

## Quick Links to Code

- **FMS Source:** `/home/gw/kitchmatics/roscamp-repo-1/fms/`
- **Scripts:** `/home/gw/kitchmatics/roscamp-repo-1/fms/scripts/`
  - `send_order.py` - Test order sender
  - `robot_client.py` - Robot TCP client
- **Launch Files:** `/home/gw/kitchmatics/roscamp-repo-1/fms/launch/`

---

## Next Steps

1. **Identify your role:** Precision Control, Robot Arm, FMS, or QA
2. **Read INTEGRATION_QUICKSTART.md** → 10 minutes
3. **Read role-specific section** in external_interfaces.md → 20 minutes
4. **Set up skip mode** if needed → skip_mode_guide.md
5. **Follow testing procedures** for your scenario
6. **Document findings** and share with team

---

## Acknowledgments

This documentation was created to enable seamless coordination between:
- **FMS Team** - Navigation and task orchestration
- **Precision Control Team** - Fine-grained positioning
- **Robot Arm Team** - Food loading operations
- **Main Server Team** - Order management
- **QA Team** - Quality assurance

All teams are expected to review relevant documentation and provide feedback.

---

**Created:** 2026-02-25
**Version:** 1.0
**Status:** Ready for use
**Contact:** #fms-channel Slack

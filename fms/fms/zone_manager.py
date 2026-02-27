"""
Fleet Management System용 Zone Manager
충돌 회피와 zone 기반 조정을 처리합니다
"""

import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
from geometry_msgs.msg import Pose
import math

logger = logging.getLogger(__name__)


class Zone:
    """
    맵의 zone을 나타냅니다

    Zone은 충돌 회피에 사용됩니다:
    - 한 번에 하나의 로봇만 zone을 점유할 수 있습니다
    - 로봇은 진입 전에 zone 접근을 요청해야 합니다
    - Zone은 접근을 보장하기 위해 미리 예약될 수 있습니다
    """

    def __init__(self, zone_id: str, center_x: float, center_y: float, radius: float,
                 reservation_timeout: float = 30.0):
        self.zone_id = zone_id
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        self.reservation_timeout = reservation_timeout  # Seconds before reservation expires
        self.occupied_by = None  # Robot ID currently in this zone
        self.reserved_by = None  # Robot ID that reserved this zone
        self.reserved_at = None  # Timestamp when zone was reserved

    def is_available(self) -> bool:
        """zone이 가용한지 확인합니다 (점유되거나 예약되지 않음)"""
        return self.occupied_by is None and self.reserved_by is None

    def is_occupied(self) -> bool:
        """zone이 점유되었는지 확인합니다"""
        return self.occupied_by is not None

    def is_reservation_expired(self) -> bool:
        """
        예약이 만료되었는지 확인합니다

        Returns:
            예약되었지만 타임아웃이 초과된 경우 True, 그렇지 않으면 False
        """
        if self.reserved_by is None or self.reserved_at is None:
            return False

        elapsed = (datetime.utcnow() - self.reserved_at).total_seconds()
        return elapsed > self.reservation_timeout

    def reserve(self, robot_id: str) -> bool:
        """
        로봇을 위해 zone을 예약합니다

        Args:
            robot_id: Robot ID

        Returns:
            예약 성공 시 True, 실패 시 False
        """
        if self.is_available():
            self.reserved_by = robot_id
            self.reserved_at = datetime.utcnow()
            logger.debug(f"Zone {self.zone_id} reserved by robot {robot_id}")
            return True
        else:
            logger.debug(f"Zone {self.zone_id} not available for reservation")
            return False

    def occupy(self, robot_id: str):
        """
        zone을 로봇에 의해 점유됨으로 표시합니다

        Args:
            robot_id: Robot ID
        """
        if self.reserved_by == robot_id or self.is_available():
            self.occupied_by = robot_id
            self.reserved_by = None
            self.reserved_at = None
            logger.debug(f"Zone {self.zone_id} occupied by robot {robot_id}")
        else:
            logger.warning(f"Robot {robot_id} tried to occupy zone {self.zone_id} without reservation")

    def release(self, robot_id: str):
        """
        로봇으로부터 zone을 해제합니다

        Args:
            robot_id: Robot ID
        """
        if self.occupied_by == robot_id:
            self.occupied_by = None
            logger.debug(f"Zone {self.zone_id} released by robot {robot_id}")
        elif self.reserved_by == robot_id:
            self.reserved_by = None
            self.reserved_at = None
            logger.debug(f"Zone {self.zone_id} reservation cancelled by robot {robot_id}")

    def contains_point(self, x: float, y: float) -> bool:
        """
        Check if point is inside zone

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            True if point is inside zone, False otherwise
        """
        distance = math.sqrt((x - self.center_x) ** 2 + (y - self.center_y) ** 2)
        return distance <= self.radius


class ZoneManager:
    """
    Manages zones for collision avoidance

    Responsibilities:
    - Define zones based on map layout
    - Track which robot is in which zone
    - Grant/deny zone access to prevent collisions
    - Handle zone transitions
    """

    def __init__(self, map_config: Optional[Dict] = None):
        """
        Initialize zone manager

        Args:
            map_config: Map configuration (optional, uses defaults if not provided)
        """
        self.zones = {}  # {zone_id: Zone}
        self.robot_zones = {}  # {robot_id: set of zone_ids}

        # Initialize zones based on map layout
        self._initialize_zones(map_config)

        logger.info(f"ZoneManager initialized with {len(self.zones)} zones")

    def _initialize_zones(self, map_config: Optional[Dict]):
        """
        Initialize zones based on map layout

        For a 2m x 1m map, we define zones around key locations:
        - Pickup area
        - Table areas (8 tables)
        - Parking areas (3 spots)
        - Waypoint areas

        Zones can be loaded from config or use defaults.
        """
        # Default reservation timeout (can be overridden per zone)
        default_timeout = 30.0

        if map_config:
            # Load from config
            zones_config = map_config.get('zones', [])
            for zone_cfg in zones_config:
                zone = Zone(
                    zone_id=zone_cfg['id'],
                    center_x=zone_cfg['center_x'],
                    center_y=zone_cfg['center_y'],
                    radius=zone_cfg['radius'],
                    reservation_timeout=zone_cfg.get('reservation_timeout', default_timeout)
                )
                self.zones[zone.zone_id] = zone
        else:
            # Use default zones (simplified for 2m x 1m map)
            default_zones = [
                # Pickup zone
                {'id': 'zone_pickup', 'center_x': 0.47, 'center_y': 0.63, 'radius': 0.10},

                # Table zones
                {'id': 'zone_table1', 'center_x': 1.785, 'center_y': 0.35, 'radius': 0.10},
                {'id': 'zone_table2', 'center_x': 1.415, 'center_y': 0.35, 'radius': 0.10},
                {'id': 'zone_table3', 'center_x': 1.785, 'center_y': 0.65, 'radius': 0.10},
                {'id': 'zone_table4', 'center_x': 1.415, 'center_y': 0.65, 'radius': 0.10},
                {'id': 'zone_table5', 'center_x': 1.235, 'center_y': 0.35, 'radius': 0.10},
                {'id': 'zone_table6', 'center_x': 0.865, 'center_y': 0.35, 'radius': 0.10},
                {'id': 'zone_table7', 'center_x': 1.235, 'center_y': 0.65, 'radius': 0.10},
                {'id': 'zone_table8', 'center_x': 0.865, 'center_y': 0.65, 'radius': 0.10},

                # Parking zones
                {'id': 'zone_parking1', 'center_x': 0.585, 'center_y': 0.085, 'radius': 0.08},
                {'id': 'zone_parking2', 'center_x': 0.585, 'center_y': 0.255, 'radius': 0.08},
                {'id': 'zone_parking3', 'center_x': 0.585, 'center_y': 0.915, 'radius': 0.08},

                # Waypoint zones
                {'id': 'zone_point1', 'center_x': 0.78, 'center_y': 0.15, 'radius': 0.08},
                {'id': 'zone_point2', 'center_x': 0.78, 'center_y': 0.35, 'radius': 0.08},
                {'id': 'zone_point3', 'center_x': 0.78, 'center_y': 0.65, 'radius': 0.08},
                {'id': 'zone_point4', 'center_x': 0.78, 'center_y': 0.85, 'radius': 0.08},
                {'id': 'zone_point13', 'center_x': 0.585, 'center_y': 0.63, 'radius': 0.08},
            ]

            for zone_cfg in default_zones:
                zone = Zone(
                    zone_id=zone_cfg['id'],
                    center_x=zone_cfg['center_x'],
                    center_y=zone_cfg['center_y'],
                    radius=zone_cfg['radius'],
                    reservation_timeout=default_timeout
                )
                self.zones[zone.zone_id] = zone

        logger.info(f"Initialized {len(self.zones)} zones")

    def update_robot_position(self, robot_id: str, pose: Pose):
        """
        Update robot position and manage zone occupancy

        Args:
            robot_id: Robot ID
            pose: Robot pose
        """
        x = pose.position.x
        y = pose.position.y

        # Find which zones robot is currently in
        current_zones = set()
        for zone_id, zone in self.zones.items():
            if zone.contains_point(x, y):
                current_zones.add(zone_id)

        # Get previous zones
        previous_zones = self.robot_zones.get(robot_id, set())

        # Handle zone entry
        entered_zones = current_zones - previous_zones
        for zone_id in entered_zones:
            zone = self.zones[zone_id]
            zone.occupy(robot_id)

        # Handle zone exit
        exited_zones = previous_zones - current_zones
        for zone_id in exited_zones:
            zone = self.zones[zone_id]
            zone.release(robot_id)

        # Update robot zones
        self.robot_zones[robot_id] = current_zones

    def reserve_zone(self, robot_id: str, zone_id: str) -> bool:
        """
        Pre-reserve a zone for a robot

        Reservation guarantees the robot can enter the zone later without
        conflicting with other robots. Only one robot can reserve a zone
        at a time.

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to reserve

        Returns:
            True if reservation successful, False otherwise
        """
        zone = self.zones.get(zone_id)
        if zone:
            if zone.reserve(robot_id):
                logger.info(f"Zone {zone_id} reserved for robot {robot_id}")
                return True
            else:
                logger.warning(
                    f"Failed to reserve zone {zone_id} for robot {robot_id} - "
                    f"occupied_by={zone.occupied_by}, reserved_by={zone.reserved_by}"
                )
                return False
        else:
            logger.warning(f"Zone {zone_id} not found")
            return False

    def release_reservation(self, robot_id: str, zone_id: str) -> bool:
        """
        Release a zone reservation

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to release

        Returns:
            True if reservation was released, False if no reservation found
        """
        zone = self.zones.get(zone_id)
        if zone and zone.reserved_by == robot_id:
            zone.release(robot_id)
            logger.info(f"Zone {zone_id} reservation released by robot {robot_id}")
            return True
        return False

    def occupy_zone(self, robot_id: str, zone_id: str) -> bool:
        """
        Transition zone from reserved to occupied

        Can only occupy a zone if:
        1. Zone was reserved by this robot
        2. Zone is available (not occupied)

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to occupy

        Returns:
            True if occupation successful, False otherwise
        """
        zone = self.zones.get(zone_id)
        if zone:
            # Only allow occupation if reserved by this robot or zone is available
            if zone.reserved_by == robot_id or zone.is_available():
                zone.occupy(robot_id)
                logger.info(f"Zone {zone_id} occupied by robot {robot_id}")
                return True
            else:
                logger.warning(
                    f"Robot {robot_id} cannot occupy zone {zone_id} - "
                    f"not reserved by this robot"
                )
                return False
        return False

    def leave_zone(self, robot_id: str, zone_id: str) -> bool:
        """
        Release zone from robot

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to leave

        Returns:
            True if zone was released, False if zone not found or not owned by robot
        """
        zone = self.zones.get(zone_id)
        if zone and zone.occupied_by == robot_id:
            zone.release(robot_id)
            logger.info(f"Zone {zone_id} released by robot {robot_id}")
            return True
        return False

    def request_zone(self, robot_id: str, zone_id: str) -> bool:
        """
        Request zone access for robot (alias for reserve_zone for backward compatibility)

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to request

        Returns:
            True if access granted, False otherwise
        """
        return self.reserve_zone(robot_id, zone_id)

    def release_zone(self, robot_id: str, zone_id: str):
        """
        Release zone from robot (backward compatibility wrapper)

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to release
        """
        zone = self.zones.get(zone_id)
        if zone:
            zone.release(robot_id)

    def get_zone_by_location(self, location_name: str) -> Optional[str]:
        """
        Get zone ID for location name

        Args:
            location_name: Location name (pickup_spot, table1-8, pinky1_spot, etc.)

        Returns:
            Zone ID if found, None otherwise
        """
        # Map location names to zone IDs
        location_to_zone = {
            'pickup_spot': 'zone_pickup',
            'table1': 'zone_table1',
            'table2': 'zone_table2',
            'table3': 'zone_table3',
            'table4': 'zone_table4',
            'table5': 'zone_table5',
            'table6': 'zone_table6',
            'table7': 'zone_table7',
            'table8': 'zone_table8',
            'pinky1_spot': 'zone_parking1',
            'pinky2_spot': 'zone_parking2',
            'pinky3_spot': 'zone_parking3',
        }

        return location_to_zone.get(location_name)

    def check_collision_risk(self, robot_id: str, target_zone_id: str) -> bool:
        """
        Check if moving to target zone would cause collision

        Args:
            robot_id: Robot ID
            target_zone_id: Target zone ID

        Returns:
            True if there's collision risk, False if safe
        """
        zone = self.zones.get(target_zone_id)
        if zone:
            # Collision risk if zone is occupied by another robot
            if zone.is_occupied() and zone.occupied_by != robot_id:
                return True
            # Also check if zone is reserved by another robot
            if zone.reserved_by and zone.reserved_by != robot_id:
                return True
        return False

    def is_zone_available(self, zone_id: str) -> bool:
        """
        Check if zone is available (not occupied or reserved)

        Args:
            zone_id: Zone ID

        Returns:
            True if zone is available, False otherwise
        """
        zone = self.zones.get(zone_id)
        if zone:
            return zone.is_available()
        return False

    def get_zone_status(self, zone_id: str) -> Optional[Dict]:
        """
        Get zone status

        Args:
            zone_id: Zone ID

        Returns:
            Dictionary with zone status information
        """
        zone = self.zones.get(zone_id)
        if zone:
            reservation_age = None
            if zone.reserved_at:
                reservation_age = (datetime.utcnow() - zone.reserved_at).total_seconds()

            return {
                'zone_id': zone.zone_id,
                'center_x': zone.center_x,
                'center_y': zone.center_y,
                'radius': zone.radius,
                'occupied_by': zone.occupied_by,
                'reserved_by': zone.reserved_by,
                'reserved_at': zone.reserved_at.isoformat() if zone.reserved_at else None,
                'reservation_age_sec': reservation_age,
                'reservation_timeout': zone.reservation_timeout,
                'is_reservation_expired': zone.is_reservation_expired(),
                'available': zone.is_available()
            }
        return None

    def get_all_zones_status(self) -> List[Dict]:
        """
        Get status of all zones

        Returns:
            List of zone status dictionaries
        """
        return [self.get_zone_status(zone_id) for zone_id in self.zones.keys()]

    def check_path_conflicts(self, robot_id: str, path_zones: List[str]) -> List[str]:
        """
        Check if path contains zones that would cause conflicts

        Args:
            robot_id: Robot ID
            path_zones: List of zone IDs in the planned path

        Returns:
            List of zone IDs that have conflicts (occupied by other robots or unavailable)
        """
        conflicts = []
        for zone_id in path_zones:
            zone = self.zones.get(zone_id)
            if zone:
                # Conflict if zone is occupied by another robot
                if zone.is_occupied() and zone.occupied_by != robot_id:
                    conflicts.append(zone_id)
                # Conflict if zone is reserved by another robot
                elif zone.reserved_by and zone.reserved_by != robot_id:
                    conflicts.append(zone_id)

        if conflicts:
            logger.warning(
                f"Path conflicts detected for robot {robot_id}: {conflicts}"
            )
        return conflicts

    def cleanup_expired_reservations(self) -> int:
        """
        Clean up all expired reservations

        Reservations expire after reservation_timeout seconds.
        This method should be called periodically to free up zones.

        Returns:
            Number of reservations cleaned up
        """
        cleaned_count = 0
        expired_zones = []

        for zone_id, zone in self.zones.items():
            if zone.is_reservation_expired():
                expired_zones.append((zone_id, zone.reserved_by))
                zone.release(zone.reserved_by)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info(
                f"Cleaned up {cleaned_count} expired reservations: {expired_zones}"
            )

        return cleaned_count

    def get_robot_reserved_zones(self, robot_id: str) -> List[str]:
        """
        Get all zones reserved by a robot

        Args:
            robot_id: Robot ID

        Returns:
            List of zone IDs reserved by the robot
        """
        reserved = []
        for zone_id, zone in self.zones.items():
            if zone.reserved_by == robot_id:
                reserved.append(zone_id)
        return reserved

    def get_robot_occupied_zones(self, robot_id: str) -> List[str]:
        """
        Get all zones occupied by a robot

        Args:
            robot_id: Robot ID

        Returns:
            List of zone IDs occupied by the robot
        """
        occupied = []
        for zone_id, zone in self.zones.items():
            if zone.occupied_by == robot_id:
                occupied.append(zone_id)
        return occupied

    def clear_robot(self, robot_id: str):
        """
        Clear all zones occupied/reserved by robot

        Args:
            robot_id: Robot ID
        """
        # Release all zones
        for zone_id, zone in self.zones.items():
            if zone.occupied_by == robot_id or zone.reserved_by == robot_id:
                zone.release(robot_id)

        # Clear from robot zones tracking
        if robot_id in self.robot_zones:
            del self.robot_zones[robot_id]

        logger.info(f"Cleared all zones for robot {robot_id}")

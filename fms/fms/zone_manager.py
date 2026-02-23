"""
Zone Manager for Fleet Management System
Handles collision avoidance and zone-based coordination
"""

import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
from geometry_msgs.msg import Pose
import math

logger = logging.getLogger(__name__)


class Zone:
    """
    Represents a zone in the map

    Zones are used for collision avoidance:
    - Only one robot can occupy a zone at a time
    - Robots must request zone access before entering
    """

    def __init__(self, zone_id: str, center_x: float, center_y: float, radius: float):
        self.zone_id = zone_id
        self.center_x = center_x
        self.center_y = center_y
        self.radius = radius
        self.occupied_by = None  # Robot ID currently in this zone
        self.reserved_by = None  # Robot ID that reserved this zone
        self.reserved_at = None

    def is_available(self) -> bool:
        """Check if zone is available (not occupied or reserved)"""
        return self.occupied_by is None and self.reserved_by is None

    def is_occupied(self) -> bool:
        """Check if zone is occupied"""
        return self.occupied_by is not None

    def reserve(self, robot_id: str) -> bool:
        """
        Reserve zone for robot

        Args:
            robot_id: Robot ID

        Returns:
            True if reservation successful, False otherwise
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
        Mark zone as occupied by robot

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
        Release zone from robot

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
        - Corridors/pathways

        TODO: Load zone definitions from config file
        """
        if map_config:
            # Load from config
            zones_config = map_config.get('zones', [])
            for zone_cfg in zones_config:
                zone = Zone(
                    zone_id=zone_cfg['id'],
                    center_x=zone_cfg['center_x'],
                    center_y=zone_cfg['center_y'],
                    radius=zone_cfg['radius']
                )
                self.zones[zone.zone_id] = zone
        else:
            # Use default zones (simplified for 2m x 1m map)
            # These are placeholder values - TODO: calibrate based on actual map coordinates
            default_zones = [
                # Pickup zone
                {'id': 'zone_pickup', 'center_x': 1.0, 'center_y': 0.3, 'radius': 0.15},

                # Table zones (left side)
                {'id': 'zone_table1', 'center_x': 0.3, 'center_y': 0.2, 'radius': 0.12},
                {'id': 'zone_table2', 'center_x': 0.3, 'center_y': 0.4, 'radius': 0.12},
                {'id': 'zone_table3', 'center_x': 0.3, 'center_y': 0.6, 'radius': 0.12},
                {'id': 'zone_table4', 'center_x': 0.3, 'center_y': 0.8, 'radius': 0.12},

                # Table zones (right side)
                {'id': 'zone_table5', 'center_x': 1.7, 'center_y': 0.2, 'radius': 0.12},
                {'id': 'zone_table6', 'center_x': 1.7, 'center_y': 0.4, 'radius': 0.12},
                {'id': 'zone_table7', 'center_x': 1.7, 'center_y': 0.6, 'radius': 0.12},
                {'id': 'zone_table8', 'center_x': 1.7, 'center_y': 0.8, 'radius': 0.12},

                # Parking zones
                {'id': 'zone_parking1', 'center_x': 1.0, 'center_y': 0.1, 'radius': 0.1},
                {'id': 'zone_parking2', 'center_x': 1.15, 'center_y': 0.1, 'radius': 0.1},
                {'id': 'zone_parking3', 'center_x': 1.3, 'center_y': 0.1, 'radius': 0.1},

                # Corridor zones (pathways between areas)
                {'id': 'zone_corridor1', 'center_x': 0.7, 'center_y': 0.5, 'radius': 0.15},
                {'id': 'zone_corridor2', 'center_x': 1.3, 'center_y': 0.5, 'radius': 0.15},
            ]

            for zone_cfg in default_zones:
                zone = Zone(
                    zone_id=zone_cfg['id'],
                    center_x=zone_cfg['center_x'],
                    center_y=zone_cfg['center_y'],
                    radius=zone_cfg['radius']
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

    def request_zone(self, robot_id: str, zone_id: str) -> bool:
        """
        Request zone access for robot

        Args:
            robot_id: Robot ID
            zone_id: Zone ID to request

        Returns:
            True if access granted, False otherwise
        """
        zone = self.zones.get(zone_id)
        if zone:
            return zone.reserve(robot_id)
        else:
            logger.warning(f"Zone {zone_id} not found")
            return False

    def release_zone(self, robot_id: str, zone_id: str):
        """
        Release zone from robot

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
            return {
                'zone_id': zone.zone_id,
                'center_x': zone.center_x,
                'center_y': zone.center_y,
                'radius': zone.radius,
                'occupied_by': zone.occupied_by,
                'reserved_by': zone.reserved_by,
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

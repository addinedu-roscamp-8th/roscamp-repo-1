#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kitchmatics FMS - Robot File Sync Script
Syncs parameter files from project to robot internal directories

Usage:
    python robot_file_sync.py --robot pinky_b4bc --sync
    python robot_file_sync.py --all --sync
    python robot_file_sync.py --robot pinky_b4bc --check
"""

import os
import sys
import yaml
import argparse
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("RobotFileSync")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
CONFIG_PATH = PROJECT_ROOT / "fms" / "config" / "network_config.yaml"


@dataclass
class SyncConfig:
    """File sync configuration"""
    local_path: Path
    remote_path: str
    files: List[str]
    rename_map: Dict[str, str] = None  # {local_name: remote_name}

    def __post_init__(self):
        if self.rename_map is None:
            self.rename_map = {}


@dataclass
class RobotInfo:
    """Robot connection info"""
    robot_id: str
    robot_name: str
    ip_address: str
    ssh_user: str
    ssh_port: int
    robot_type: str
    enabled: bool


def load_network_config() -> dict:
    """Load network configuration"""
    if not CONFIG_PATH.exists():
        logger.error(f"Config file not found: {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)


def get_robot_info(config: dict, robot_name: str) -> Optional[RobotInfo]:
    """Get robot info by name"""
    # Check mobile robots
    if robot_name in config.get('mobile_robots', {}):
        robot_cfg = config['mobile_robots'][robot_name]
        return RobotInfo(
            robot_id=robot_cfg['robot_id'],
            robot_name=robot_name,
            ip_address=robot_cfg['ip_address'],
            ssh_user=robot_cfg.get('ssh_user', 'pinky'),
            ssh_port=robot_cfg.get('ssh_port', 22),
            robot_type=robot_cfg.get('type', 'PINKYPRO'),
            enabled=robot_cfg.get('enabled', False)
        )

    # Check cobot arms
    if robot_name in config.get('cobot_arms', {}):
        robot_cfg = config['cobot_arms'][robot_name]
        return RobotInfo(
            robot_id=robot_cfg['robot_id'],
            robot_name=robot_name,
            ip_address=robot_cfg['ip_address'],
            ssh_user=robot_cfg.get('ssh_user', 'jetson'),
            ssh_port=robot_cfg.get('ssh_port', 22),
            robot_type=robot_cfg.get('type', 'JETCOBOT'),
            enabled=robot_cfg.get('enabled', False)
        )

    return None


def get_all_robots(config: dict) -> List[RobotInfo]:
    """Get all enabled robots"""
    robots = []

    for robot_name in config.get('mobile_robots', {}):
        robot_info = get_robot_info(config, robot_name)
        if robot_info and robot_info.enabled:
            robots.append(robot_info)

    for robot_name in config.get('cobot_arms', {}):
        robot_info = get_robot_info(config, robot_name)
        if robot_info and robot_info.enabled:
            robots.append(robot_info)

    return robots


def get_sync_configs(config: dict, robot_info: RobotInfo) -> List[SyncConfig]:
    """Get all sync configurations for a robot"""
    file_sync_cfg = config.get('file_sync', {})
    configs = []

    if not file_sync_cfg.get('enabled', False):
        return configs

    if robot_info.robot_type == "PINKYPRO":
        # 1. params 동기화 (공통)
        params_cfg = file_sync_cfg.get('params', {})
        if params_cfg:
            configs.append(SyncConfig(
                local_path=PROJECT_ROOT / "mobile_robot" / "params",
                remote_path=params_cfg.get('remote_path', '~/pinky_pro/src/pinky_pro/pinky_navigation/params'),
                files=params_cfg.get('files', ['nav2_params.yaml', 'mapper_params.yaml'])
            ))

        # 2. config 동기화 (로봇별)
        config_cfg = file_sync_cfg.get('config', {})
        if config_cfg:
            # 로봇 이름에 맞는 config 파일
            robot_config_file = f"{robot_info.robot_name}.yaml"
            local_config_path = PROJECT_ROOT / "mobile_robot" / "config"
            if (local_config_path / robot_config_file).exists():
                configs.append(SyncConfig(
                    local_path=local_config_path,
                    remote_path=config_cfg.get('remote_path', '~/pinky_pro/config'),
                    files=[robot_config_file],
                    rename_map={robot_config_file: config_cfg.get('rename_to', 'robot_config.yaml')}
                ))

        # 3. launch 동기화
        launch_cfg = file_sync_cfg.get('launch', {})
        if launch_cfg:
            configs.append(SyncConfig(
                local_path=PROJECT_ROOT / "mobile_robot" / "launch",
                remote_path=launch_cfg.get('remote_path', '~/pinky_pro/src/pinky_pro/pinky_navigation/launch'),
                files=launch_cfg.get('files', [])
            ))

        # 4. maps 동기화 (install 폴더로 직접)
        maps_cfg = file_sync_cfg.get('maps', {})
        if maps_cfg:
            configs.append(SyncConfig(
                local_path=PROJECT_ROOT / "mobile_robot" / "maps",
                remote_path=maps_cfg.get('remote_path', '~/pinky_pro/install/pinky_navigation/share/pinky_navigation/maps'),
                files=maps_cfg.get('files', ['real.yaml', 'real.png'])
            ))

    elif robot_info.robot_type == "JETCOBOT":
        # JetCobot config paths
        configs.append(SyncConfig(
            local_path=PROJECT_ROOT / "robot_arm" / "config",
            remote_path='~/jetcobot_ws/src/jetcobot/config',
            files=[]
        ))

    return configs


def get_sync_config(config: dict, robot_type: str) -> Optional[SyncConfig]:
    """Get sync configuration for robot type (legacy compatibility)"""
    file_sync_cfg = config.get('file_sync', {})

    if not file_sync_cfg.get('enabled', False):
        return None

    if robot_type == "PINKYPRO":
        params_cfg = file_sync_cfg.get('params', {})
        local_path = PROJECT_ROOT / "mobile_robot" / "params"
        remote_path = params_cfg.get('remote_path', '~/pinky_pro/src/pinky_pro/pinky_navigation/params')
        files = params_cfg.get('files', ['nav2_params.yaml', 'mapper_params.yaml'])
    elif robot_type == "JETCOBOT":
        local_path = PROJECT_ROOT / "robot_arm" / "config"
        remote_path = '~/jetcobot_ws/src/jetcobot/config'
        files = []
    else:
        return None

    return SyncConfig(
        local_path=local_path,
        remote_path=remote_path,
        files=files
    )


def check_ssh_connection(robot: RobotInfo) -> bool:
    """Check SSH connection to robot"""
    logger.info(f"Checking SSH connection to {robot.robot_name} ({robot.ip_address})...")

    cmd = [
        'ssh',
        '-o', 'ConnectTimeout=5',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'BatchMode=yes',
        '-p', str(robot.ssh_port),
        f'{robot.ssh_user}@{robot.ip_address}',
        'echo "OK"'
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and 'OK' in result.stdout:
            logger.info(f"  -> Connection successful")
            return True
        else:
            logger.error(f"  -> Connection failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"  -> Connection timeout")
        return False
    except Exception as e:
        logger.error(f"  -> Error: {e}")
        return False


def sync_files(robot: RobotInfo, sync_config: SyncConfig, dry_run: bool = False) -> bool:
    """Sync files to robot using rsync"""
    if not sync_config.files:
        logger.warning(f"No files configured for sync to {robot.robot_name}")
        return True

    logger.info(f"Syncing files to {robot.robot_name} ({robot.ip_address})...")

    success = True
    for filename in sync_config.files:
        local_file = sync_config.local_path / filename

        if not local_file.exists():
            logger.warning(f"  -> Local file not found: {local_file}")
            continue

        # 파일 이름 변경 처리 (rename_map)
        remote_filename = sync_config.rename_map.get(filename, filename)
        remote_dest = f"{robot.ssh_user}@{robot.ip_address}:{sync_config.remote_path}/{remote_filename}"

        logger.info(f"  Syncing: {filename}" + (f" -> {remote_filename}" if filename != remote_filename else ""))
        logger.info(f"    Local:  {local_file}")
        logger.info(f"    Remote: {remote_dest}")

        if dry_run:
            logger.info(f"    [DRY RUN] Would sync {filename}")
            continue

        # 원격 디렉토리 생성
        mkdir_cmd = [
            'ssh',
            '-p', str(robot.ssh_port),
            '-o', 'StrictHostKeyChecking=no',
            f'{robot.ssh_user}@{robot.ip_address}',
            f'mkdir -p {sync_config.remote_path}'
        ]
        subprocess.run(mkdir_cmd, capture_output=True, timeout=10)

        # Use rsync for efficient file transfer
        cmd = [
            'rsync',
            '-avz',
            '--progress',
            '-e', f'ssh -p {robot.ssh_port} -o StrictHostKeyChecking=no',
            str(local_file),
            remote_dest
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                logger.info(f"    -> Success")
            else:
                logger.error(f"    -> Failed: {result.stderr}")
                success = False
        except subprocess.TimeoutExpired:
            logger.error(f"    -> Timeout")
            success = False
        except Exception as e:
            logger.error(f"    -> Error: {e}")
            success = False

    return success


def sync_all_configs(robot: RobotInfo, config: dict, dry_run: bool = False) -> bool:
    """Sync all config types (params, config, launch) to robot"""
    sync_configs = get_sync_configs(config, robot)

    if not sync_configs:
        logger.warning(f"No sync configs for {robot.robot_name}")
        return True

    success = True
    for sync_cfg in sync_configs:
        if not sync_files(robot, sync_cfg, dry_run):
            success = False

    return success


def backup_remote_files(robot: RobotInfo, sync_config: SyncConfig) -> bool:
    """Backup remote files before sync"""
    logger.info(f"Backing up remote files on {robot.robot_name}...")

    backup_cmd = f"mkdir -p {sync_config.remote_path}/backup && "
    backup_cmd += f"cp {sync_config.remote_path}/*.yaml {sync_config.remote_path}/backup/ 2>/dev/null || true"

    cmd = [
        'ssh',
        '-p', str(robot.ssh_port),
        '-o', 'StrictHostKeyChecking=no',
        f'{robot.ssh_user}@{robot.ip_address}',
        backup_cmd
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info(f"  -> Backup created")
            return True
        else:
            logger.warning(f"  -> Backup may have issues: {result.stderr}")
            return True  # Continue even if backup has issues
    except Exception as e:
        logger.error(f"  -> Backup error: {e}")
        return False


def restore_remote_files(robot: RobotInfo, sync_config: SyncConfig) -> bool:
    """Restore remote files from backup"""
    logger.info(f"Restoring files on {robot.robot_name}...")

    restore_cmd = f"cp {sync_config.remote_path}/backup/*.yaml {sync_config.remote_path}/ 2>/dev/null || true"

    cmd = [
        'ssh',
        '-p', str(robot.ssh_port),
        '-o', 'StrictHostKeyChecking=no',
        f'{robot.ssh_user}@{robot.ip_address}',
        restore_cmd
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"  -> Restore error: {e}")
        return False


def compare_files(robot: RobotInfo, sync_config: SyncConfig) -> Dict[str, str]:
    """Compare local and remote files"""
    logger.info(f"Comparing files with {robot.robot_name}...")

    results = {}
    for filename in sync_config.files:
        local_file = sync_config.local_path / filename

        if not local_file.exists():
            results[filename] = "LOCAL_MISSING"
            continue

        # Get remote file checksum
        remote_path = f"{sync_config.remote_path}/{filename}"
        cmd = [
            'ssh',
            '-p', str(robot.ssh_port),
            '-o', 'StrictHostKeyChecking=no',
            f'{robot.ssh_user}@{robot.ip_address}',
            f'md5sum {remote_path} 2>/dev/null || echo "MISSING"'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if "MISSING" in result.stdout or result.returncode != 0:
                results[filename] = "REMOTE_MISSING"
                continue

            remote_md5 = result.stdout.split()[0]

            # Get local checksum
            local_result = subprocess.run(
                ['md5sum', str(local_file)],
                capture_output=True, text=True
            )
            local_md5 = local_result.stdout.split()[0]

            if local_md5 == remote_md5:
                results[filename] = "SYNCED"
            else:
                results[filename] = "DIFFERENT"

        except Exception as e:
            results[filename] = f"ERROR: {e}"

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Sync parameter files from project to robots"
    )
    parser.add_argument(
        '--robot', '-r',
        help='Robot name (e.g., pinky_b4bc, jetcobot_aa1f)'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Sync to all enabled robots'
    )
    parser.add_argument(
        '--sync', '-s',
        action='store_true',
        help='Perform file sync'
    )
    parser.add_argument(
        '--check', '-c',
        action='store_true',
        help='Check SSH connectivity'
    )
    parser.add_argument(
        '--compare',
        action='store_true',
        help='Compare local and remote files'
    )
    parser.add_argument(
        '--backup', '-b',
        action='store_true',
        help='Backup remote files before sync'
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='Restore remote files from backup'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all configured robots'
    )

    args = parser.parse_args()

    # Load config
    config = load_network_config()

    # List robots
    if args.list:
        print("\n=== Configured Robots ===\n")

        print("Mobile Robots (PinkyPro):")
        for name, cfg in config.get('mobile_robots', {}).items():
            status = "ENABLED" if cfg.get('enabled', False) else "DISABLED"
            ip = cfg.get('ip_address', 'N/A')
            print(f"  {name}: {ip} [{status}]")

        print("\nCobot Arms (JetCobot):")
        for name, cfg in config.get('cobot_arms', {}).items():
            status = "ENABLED" if cfg.get('enabled', False) else "DISABLED"
            ip = cfg.get('ip_address', 'N/A')
            print(f"  {name}: {ip} [{status}]")

        print("\nFile Sync Configuration:")
        sync_cfg = config.get('file_sync', {})
        print(f"  Enabled: {sync_cfg.get('enabled', False)}")

        # params
        params_cfg = sync_cfg.get('params', {})
        if params_cfg:
            print(f"\n  [params]")
            print(f"    Local:  {params_cfg.get('local_path', 'N/A')}")
            print(f"    Remote: {params_cfg.get('remote_path', 'N/A')}")
            print(f"    Files:  {', '.join(params_cfg.get('files', []))}")

        # config
        config_cfg = sync_cfg.get('config', {})
        if config_cfg:
            print(f"\n  [config] (robot-specific)")
            print(f"    Local:  {config_cfg.get('local_path', 'N/A')}")
            print(f"    Remote: {config_cfg.get('remote_path', 'N/A')}")
            print(f"    Rename: <robot_name>.yaml -> {config_cfg.get('rename_to', 'robot_config.yaml')}")

        # launch
        launch_cfg = sync_cfg.get('launch', {})
        if launch_cfg:
            print(f"\n  [launch]")
            print(f"    Local:  {launch_cfg.get('local_path', 'N/A')}")
            print(f"    Remote: {launch_cfg.get('remote_path', 'N/A')}")
            print(f"    Files:  {', '.join(launch_cfg.get('files', []))}")

        # maps
        maps_cfg = sync_cfg.get('maps', {})
        if maps_cfg:
            print(f"\n  [maps]")
            print(f"    Local:  {maps_cfg.get('local_path', 'N/A')}")
            print(f"    Remote: {maps_cfg.get('remote_path', 'N/A')}")
            print(f"    Files:  {', '.join(maps_cfg.get('files', []))}")

        return

    # Determine target robots
    if args.all:
        robots = get_all_robots(config)
    elif args.robot:
        robot_info = get_robot_info(config, args.robot)
        if not robot_info:
            logger.error(f"Robot not found: {args.robot}")
            sys.exit(1)
        robots = [robot_info]
    else:
        parser.print_help()
        return

    if not robots:
        logger.error("No robots to process")
        return

    # Process each robot
    for robot in robots:
        print(f"\n{'='*60}")
        print(f"Processing: {robot.robot_name} ({robot.ip_address})")
        print(f"  Robot ID: {robot.robot_id}, Type: {robot.robot_type}")
        print(f"{'='*60}")

        # Get all sync configs for this robot
        sync_configs = get_sync_configs(config, robot)
        legacy_sync_config = get_sync_config(config, robot.robot_type)

        # Check connectivity
        if args.check:
            check_ssh_connection(robot)

        # Compare files (using legacy single config for compare/backup/restore)
        if args.compare and legacy_sync_config:
            results = compare_files(robot, legacy_sync_config)
            print("\nFile Comparison:")
            for filename, status in results.items():
                print(f"  {filename}: {status}")

        # Backup
        if args.backup and legacy_sync_config:
            backup_remote_files(robot, legacy_sync_config)

        # Restore
        if args.restore and legacy_sync_config:
            restore_remote_files(robot, legacy_sync_config)

        # Sync - use sync_all_configs for comprehensive sync
        if args.sync:
            if not check_ssh_connection(robot):
                logger.error(f"Cannot sync to {robot.robot_name}: SSH connection failed")
                continue

            # Backup before sync if requested
            if args.backup and legacy_sync_config:
                backup_remote_files(robot, legacy_sync_config)

            # Sync all config types (params, config, launch)
            sync_all_configs(robot, config, dry_run=args.dry_run)

    print("\nDone!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
NVMe SSD Auto-Mount Script for Raspberry Pi 5 with NVMe HAT

This script automatically detects and mounts NVMe drives connected via
NVMe HATs (like Pimoroni NVMe Base). It supports ext4, NTFS, and exFAT
filesystems and is robust against device issues.

Features:
- Automatic detection of NVMe storage devices
- Support for ext4, NTFS (ntfs3), and exFAT filesystems
- Robust handling of device removal
- Automatic remounting when device is reconnected
- Health monitoring with device presence checks
"""

import os
import sys
import time
import subprocess
import re
from pathlib import Path

# Configuration
MOUNT_PATH = "/media/NVME_SSD"
POLL_INTERVAL = 0.5  # seconds
DEVICE_SETTLE_TIME = 1.0  # seconds to wait after device detection

# State variables
mounted_device = None
mounted_partition = None
last_device_check = 0


def is_nvme_device(device_name):
    """
    Check if a block device is an NVMe device.

    Args:
        device_name: Device name (e.g., 'nvme0n1', 'nvme1n1')

    Returns:
        bool: True if device is NVMe, False otherwise
    """
    try:
        # NVMe devices follow the pattern nvme[0-9]+n[0-9]+
        if re.match(r'^nvme\d+n\d+$', device_name):
            # Verify the device exists in /sys/class/nvme
            nvme_num = re.search(r'^nvme(\d+)', device_name).group(1)
            nvme_path = f"/sys/class/nvme/nvme{nvme_num}"
            if os.path.exists(nvme_path):
                return True
        return False
    except Exception as e:
        print(f"Error checking if {device_name} is NVMe device: {e}")
        return False


def get_nvme_devices():
    """
    Get list of all NVMe devices currently connected.

    Returns:
        list: List of device names (e.g., ['nvme0n1', 'nvme1n1'])
    """
    devices = []
    try:
        # Look for NVMe namespaces in /sys/class/nvme
        if os.path.exists("/sys/class/nvme"):
            for nvme_ctrl in os.listdir("/sys/class/nvme"):
                # Each controller can have multiple namespaces
                # Check for nvme devices in /dev
                for entry in os.listdir("/dev"):
                    if entry.startswith(nvme_ctrl + 'n'):
                        # Make sure it's a namespace (nvme0n1, nvme0n2, etc.)
                        if re.match(r'^nvme\d+n\d+$', entry):
                            if os.path.exists(f"/dev/{entry}"):
                                devices.append(entry)

        # Alternative method: check /dev directly for nvme devices
        if not devices:
            for entry in os.listdir("/dev"):
                if is_nvme_device(entry):
                    devices.append(entry)

        return sorted(set(devices))  # Remove duplicates and sort

    except Exception as e:
        print(f"Error getting NVMe devices: {e}")
        return []


def get_device_partitions(device_name):
    """
    Get all partitions for a given NVMe device.

    Args:
        device_name: Device name (e.g., 'nvme0n1')

    Returns:
        list: Sorted list of partition names (e.g., ['nvme0n1p1', 'nvme0n1p2'])
    """
    try:
        partitions = []
        # NVMe partitions follow pattern: nvme0n1p1, nvme0n1p2, etc.
        partition_pattern = f"{device_name}p"

        for entry in os.listdir("/dev/"):
            if entry.startswith(partition_pattern):
                # Verify it ends with a number (partition number)
                if re.search(r'p\d+$', entry):
                    partitions.append(entry)

        return sorted(partitions)
    except Exception as e:
        print(f"Error getting partitions for {device_name}: {e}")
        return []


def get_filesystem_type(device_path):
    """
    Determine the filesystem type of a device/partition.

    Args:
        device_path: Full path to device (e.g., '/dev/nvme0n1p1')

    Returns:
        str: Filesystem type or None if cannot be determined
    """
    try:
        result = subprocess.check_output(
            ["sudo", "blkid", "-s", "TYPE", "-o", "value", device_path],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        return result
    except subprocess.CalledProcessError:
        return None
    except Exception as e:
        print(f"Error determining filesystem type for {device_path}: {e}")
        return None


def is_device_mounted(device_path):
    """
    Check if a device is currently mounted.

    Args:
        device_path: Full path to device (e.g., '/dev/nvme0n1p1')

    Returns:
        tuple: (is_mounted, mount_point) where is_mounted is bool and
               mount_point is string or None
    """
    try:
        with open('/proc/mounts', 'r') as f:
            mounts = f.read()
            for line in mounts.split('\n'):
                if line.startswith(device_path):
                    parts = line.split()
                    if len(parts) >= 2:
                        return (True, parts[1])
        return (False, None)
    except Exception as e:
        print(f"Error checking if {device_path} is mounted: {e}")
        return (False, None)


def device_exists(device_path):
    """
    Check if a device path exists and is accessible.

    Args:
        device_path: Full path to device (e.g., '/dev/nvme0n1p1')

    Returns:
        bool: True if device exists, False otherwise
    """
    try:
        return os.path.exists(device_path)
    except Exception:
        return False


def mount_partition(device_path, fs_type):
    """
    Mount a partition with appropriate options based on filesystem type.

    Args:
        device_path: Full path to partition (e.g., '/dev/nvme0n1p1')
        fs_type: Filesystem type ('ext4', 'ntfs', 'exfat')

    Returns:
        bool: True if mount successful, False otherwise
    """
    try:
        # Create mount point if it doesn't exist
        os.makedirs(MOUNT_PATH, exist_ok=True)

        print(f"Mounting {device_path} ({fs_type}) at {MOUNT_PATH}...")

        # Mount with appropriate options based on filesystem
        if fs_type == "ntfs":
            # Use ntfs3 driver (kernel 5.15+) with proper permissions
            cmd = f"sudo mount -t ntfs3 -o uid=1000,gid=1000,dmask=022,fmask=133 {device_path} {MOUNT_PATH}"
        elif fs_type == "ext4":
            # Mount ext4 with defaults
            cmd = f"sudo mount -t ext4 {device_path} {MOUNT_PATH}"
        elif fs_type == "exfat":
            # Mount exFAT with proper permissions
            cmd = f"sudo mount -t exfat -o uid=1000,gid=1000,dmask=022,fmask=133 {device_path} {MOUNT_PATH}"
        elif fs_type == "ext3" or fs_type == "ext2":
            # Support older ext filesystems
            cmd = f"sudo mount -t {fs_type} {device_path} {MOUNT_PATH}"
        elif fs_type == "vfat" or fs_type == "msdos":
            # Support FAT filesystems
            cmd = f"sudo mount -t vfat -o uid=1000,gid=1000,dmask=022,fmask=133 {device_path} {MOUNT_PATH}"
        else:
            print(f"Unsupported filesystem type: {fs_type}")
            return False

        result = os.system(cmd)
        if result == 0:
            print(f"Successfully mounted {device_path} at {MOUNT_PATH}")
            return True
        else:
            print(f"Failed to mount {device_path} (exit code: {result})")
            return False

    except Exception as e:
        print(f"Error mounting {device_path}: {e}")
        return False


def unmount_partition(mount_path=MOUNT_PATH, force=False):
    """
    Unmount a partition.

    Args:
        mount_path: Path where partition is mounted
        force: If True, use lazy unmount (-l) for forceful unmount

    Returns:
        bool: True if unmount successful, False otherwise
    """
    try:
        print(f"Unmounting {mount_path}...")

        if force:
            # Lazy unmount - detaches the filesystem immediately
            cmd = f"sudo umount -l {mount_path}"
        else:
            # Normal unmount
            cmd = f"sudo umount {mount_path}"

        result = os.system(cmd)
        if result == 0:
            print(f"Successfully unmounted {mount_path}")
            return True
        else:
            print(f"Unmount returned exit code: {result}")
            if not force:
                # Try force unmount if normal unmount failed
                print("Attempting force unmount...")
                return unmount_partition(mount_path, force=True)
            return False

    except Exception as e:
        print(f"Error unmounting {mount_path}: {e}")
        return False


def mount_nvme_device():
    """
    Detect and mount an NVMe storage device.

    Returns:
        tuple: (device_name, partition_path) if successful, (None, None) otherwise
    """
    global mounted_device, mounted_partition

    # Get list of NVMe devices
    devices = get_nvme_devices()

    if not devices:
        return (None, None)

    # Use the first detected device
    device_name = devices[0]

    if len(devices) > 1:
        print(f"Multiple NVMe devices detected: {devices}. Using {device_name}")

    print(f"NVMe device detected: {device_name}")

    # Wait for device to settle
    time.sleep(DEVICE_SETTLE_TIME)

    # Get partitions
    partitions = get_device_partitions(device_name)

    if not partitions:
        print(f"No partitions found on {device_name}")
        return (None, None)

    # Use the last partition (similar to CFE script behavior)
    partition_name = partitions[-1]
    partition_path = f"/dev/{partition_name}"

    print(f"Found {len(partitions)} partition(s), using: {partition_name}")

    # Check if already mounted
    is_mounted, current_mount = is_device_mounted(partition_path)
    if is_mounted:
        if current_mount == MOUNT_PATH:
            print(f"{partition_path} already mounted at {MOUNT_PATH}")
            return (device_name, partition_path)
        else:
            print(f"{partition_path} already mounted at {current_mount}")
            return (None, None)

    # Detect filesystem type
    fs_type = get_filesystem_type(partition_path)

    if not fs_type:
        print(f"Could not determine filesystem type for {partition_path}")
        return (None, None)

    print(f"Detected filesystem: {fs_type}")

    # Mount the partition
    if mount_partition(partition_path, fs_type):
        mounted_device = device_name
        mounted_partition = partition_path
        return (device_name, partition_path)
    else:
        return (None, None)


def check_device_health():
    """
    Check if the currently mounted device is still present and accessible.

    Returns:
        bool: True if device is healthy, False if disconnected or inaccessible
    """
    global mounted_device, mounted_partition

    if not mounted_device or not mounted_partition:
        return True  # No device to check

    # Check if device path still exists
    if not device_exists(mounted_partition):
        print(f"Device {mounted_partition} has been disconnected!")
        return False

    # Check if device is still mounted
    is_mounted, mount_point = is_device_mounted(mounted_partition)
    if not is_mounted:
        print(f"Device {mounted_partition} is no longer mounted!")
        return False

    # Check if NVMe device is still present in system
    current_devices = get_nvme_devices()
    if mounted_device not in current_devices:
        print(f"NVMe device {mounted_device} is no longer present!")
        return False

    return True


def handle_device_removal():
    """
    Handle cleanup when a device is removed (accidentally or intentionally).
    """
    global mounted_device, mounted_partition

    print("Handling device removal...")

    # Attempt to unmount (force if necessary, since device might be gone)
    if os.path.ismount(MOUNT_PATH):
        unmount_partition(MOUNT_PATH, force=True)

    # Reset state
    mounted_device = None
    mounted_partition = None

    print("Device removal handled, ready for new device")


def main():
    """
    Main loop for NVMe SSD auto-mount daemon.
    """
    global mounted_device, mounted_partition

    print("NVMe SSD Auto-Mount Service Started")
    print(f"Mount path: {MOUNT_PATH}")
    print(f"Supported filesystems: ext4, ext3, ext2, NTFS, exFAT, FAT")

    try:
        while True:
            # Check if we have a mounted device
            if mounted_device:
                # Verify device health
                if not check_device_health():
                    handle_device_removal()
            else:
                # Try to mount an NVMe device
                device, partition = mount_nvme_device()
                if device:
                    print(f"Successfully mounted {partition} from device {device}")

            # Sleep before next check
            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("Received shutdown signal")
        if mounted_device:
            handle_device_removal()
    except Exception as e:
        print(f"Unexpected error in main loop: {e}")
        if mounted_device:
            handle_device_removal()
        raise


if __name__ == "__main__":
    # Check if running as root or with sudo
    if os.geteuid() != 0:
        print("Warning: This script should be run with sudo privileges for mounting operations")
        print("Starting anyway, but mount operations may fail...")

    main()

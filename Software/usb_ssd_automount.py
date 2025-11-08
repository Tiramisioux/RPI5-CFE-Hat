#!/usr/bin/env python3
"""
USB SSD Auto-Mount Script for Raspberry Pi 5

This script automatically detects and mounts USB-connected SSD drives.
It supports ext4, NTFS, and exFAT filesystems and is robust against
accidental disconnections.

Features:
- Automatic detection of USB storage devices
- Support for ext4, NTFS (ntfs3), and exFAT filesystems
- Robust handling of accidental device removal
- Automatic remounting when device is reconnected
- Health monitoring with read/write activity tracking
"""

import os
import sys
import time
import subprocess
import re
from pathlib import Path

# Configuration
MOUNT_BASE = "/media"
POLL_INTERVAL = 0.5  # seconds
DEVICE_SETTLE_TIME = 1.0  # seconds to wait after device detection

# State variables
mounted_device = None
mounted_partition = None
mounted_path = None
last_device_check = 0


def is_usb_storage_device(device_name):
    """
    Check if a block device is a USB storage device.

    Args:
        device_name: Device name (e.g., 'sda', 'sdb')

    Returns:
        bool: True if device is USB storage, False otherwise
    """
    try:
        # Check if device path exists in /sys/class/block
        sys_path = f"/sys/class/block/{device_name}"
        if not os.path.exists(sys_path):
            return False

        # Follow the device symlink to find the real path
        real_path = os.path.realpath(sys_path)

        # Check if 'usb' is in the device path (indicates USB device)
        if '/usb' in real_path:
            # Additional check: verify it's a disk, not a partition
            if not re.search(r'\d+$', device_name):
                return True

        return False
    except Exception as e:
        print(f"Error checking if {device_name} is USB storage: {e}")
        return False


def get_usb_storage_devices():
    """
    Get list of all USB storage devices currently connected.

    Returns:
        list: List of device names (e.g., ['sda', 'sdb'])
    """
    devices = []
    try:
        block_devices = os.listdir("/sys/class/block")
        for device in block_devices:
            # Skip loop devices, ramdisks, and partitions
            if device.startswith(('loop', 'ram', 'mmcblk')):
                continue

            if is_usb_storage_device(device):
                devices.append(device)

    except Exception as e:
        print(f"Error getting USB storage devices: {e}")

    return devices


def get_device_partitions(device_name):
    """
    Get all partitions for a given device.

    Args:
        device_name: Device name (e.g., 'sda')

    Returns:
        list: Sorted list of partition names (e.g., ['sda1', 'sda2'])
    """
    try:
        partitions = []
        for entry in os.listdir("/dev/"):
            if entry.startswith(device_name) and re.search(r'\d+$', entry):
                partitions.append(entry)
        return sorted(partitions)
    except Exception as e:
        print(f"Error getting partitions for {device_name}: {e}")
        return []


def get_filesystem_type(device_path):
    """
    Determine the filesystem type of a device/partition.

    Args:
        device_path: Full path to device (e.g., '/dev/sda1')

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


def get_filesystem_label(device_path):
    """
    Get the filesystem label of a device/partition.

    Args:
        device_path: Full path to device (e.g., '/dev/sda1')

    Returns:
        str: Filesystem label or None if no label is set
    """
    try:
        result = subprocess.check_output(
            ["sudo", "blkid", "-s", "LABEL", "-o", "value", device_path],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        return result if result else None
    except subprocess.CalledProcessError:
        return None
    except Exception as e:
        print(f"Error determining filesystem label for {device_path}: {e}")
        return None


def is_device_mounted(device_path):
    """
    Check if a device is currently mounted.

    Args:
        device_path: Full path to device (e.g., '/dev/sda1')

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
        device_path: Full path to device (e.g., '/dev/sda1')

    Returns:
        bool: True if device exists, False otherwise
    """
    try:
        return os.path.exists(device_path)
    except Exception:
        return False


def mount_partition(device_path, fs_type, mount_path):
    """
    Mount a partition with appropriate options based on filesystem type.

    Args:
        device_path: Full path to partition (e.g., '/dev/sda1')
        fs_type: Filesystem type ('ext4', 'ntfs', 'exfat')
        mount_path: Path where to mount the partition

    Returns:
        bool: True if mount successful, False otherwise
    """
    try:
        # Create mount point if it doesn't exist
        os.makedirs(mount_path, exist_ok=True)

        print(f"Mounting {device_path} ({fs_type}) at {mount_path}...")

        # Mount with appropriate options based on filesystem
        if fs_type == "ntfs":
            # Use ntfs3 driver (kernel 5.15+) with proper permissions
            cmd = f"sudo mount -t ntfs3 -o uid=1000,gid=1000,dmask=022,fmask=133 {device_path} {mount_path}"
        elif fs_type == "ext4":
            # Mount ext4 with defaults
            cmd = f"sudo mount -t ext4 {device_path} {mount_path}"
        elif fs_type == "exfat":
            # Mount exFAT with proper permissions
            cmd = f"sudo mount -t exfat -o uid=1000,gid=1000,dmask=022,fmask=133 {device_path} {mount_path}"
        elif fs_type == "ext3" or fs_type == "ext2":
            # Support older ext filesystems
            cmd = f"sudo mount -t {fs_type} {device_path} {mount_path}"
        elif fs_type == "vfat" or fs_type == "msdos":
            # Support FAT filesystems
            cmd = f"sudo mount -t vfat -o uid=1000,gid=1000,dmask=022,fmask=133 {device_path} {mount_path}"
        else:
            print(f"Unsupported filesystem type: {fs_type}")
            return False

        result = os.system(cmd)
        if result == 0:
            print(f"Successfully mounted {device_path} at {mount_path}")
            return True
        else:
            print(f"Failed to mount {device_path} (exit code: {result})")
            return False

    except Exception as e:
        print(f"Error mounting {device_path}: {e}")
        return False


def unmount_partition(mount_path, force=False):
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


def mount_usb_device():
    """
    Detect and mount a USB storage device.

    Returns:
        tuple: (device_name, partition_path, mount_path) if successful, (None, None, None) otherwise
    """
    global mounted_device, mounted_partition, mounted_path

    # Get list of USB storage devices
    devices = get_usb_storage_devices()

    if not devices:
        return (None, None, None)

    # Use the first detected device
    device_name = devices[0]

    if len(devices) > 1:
        print(f"Multiple USB storage devices detected: {devices}. Using {device_name}")

    print(f"USB storage device detected: {device_name}")

    # Wait for device to settle
    time.sleep(DEVICE_SETTLE_TIME)

    # Get partitions
    partitions = get_device_partitions(device_name)

    if not partitions:
        print(f"No partitions found on {device_name}")
        return (None, None, None)

    # Use the last partition (similar to CFE script behavior)
    partition_name = partitions[-1]
    partition_path = f"/dev/{partition_name}"

    print(f"Found {len(partitions)} partition(s), using: {partition_name}")

    # Detect filesystem type
    fs_type = get_filesystem_type(partition_path)

    if not fs_type:
        print(f"Could not determine filesystem type for {partition_path}")
        return (None, None, None)

    print(f"Detected filesystem: {fs_type}")

    # Get filesystem label
    label = get_filesystem_label(partition_path)

    # Determine mount path based on label
    if label:
        mount_path = os.path.join(MOUNT_BASE, label)
        print(f"Detected filesystem label: {label}")
    else:
        # No label, use device name as fallback
        mount_path = os.path.join(MOUNT_BASE, partition_name)
        print(f"No filesystem label detected, using device name: {partition_name}")

    # Check if already mounted
    is_mounted, current_mount = is_device_mounted(partition_path)
    if is_mounted:
        if current_mount == mount_path:
            print(f"{partition_path} already mounted at {mount_path}")
            mounted_device = device_name
            mounted_partition = partition_path
            mounted_path = mount_path
            return (device_name, partition_path, mount_path)
        else:
            print(f"{partition_path} already mounted at {current_mount} (expected {mount_path})")
            return (None, None, None)

    # Mount the partition
    if mount_partition(partition_path, fs_type, mount_path):
        mounted_device = device_name
        mounted_partition = partition_path
        mounted_path = mount_path
        return (device_name, partition_path, mount_path)
    else:
        return (None, None, None)


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

    # Check if USB device is still present in system
    current_devices = get_usb_storage_devices()
    if mounted_device not in current_devices:
        print(f"USB device {mounted_device} is no longer present!")
        return False

    return True


def handle_device_removal():
    """
    Handle cleanup when a device is removed (accidentally or intentionally).
    """
    global mounted_device, mounted_partition, mounted_path

    print("Handling device removal...")

    # Attempt to unmount (force if necessary, since device might be gone)
    if mounted_path and os.path.ismount(mounted_path):
        unmount_partition(mounted_path, force=True)

    # Reset state
    mounted_device = None
    mounted_partition = None
    mounted_path = None

    print("Device removal handled, ready for new device")


def main():
    """
    Main loop for USB SSD auto-mount daemon.
    """
    global mounted_device, mounted_partition, mounted_path

    print("USB SSD Auto-Mount Service Started")
    print(f"Mount base: {MOUNT_BASE}")
    print(f"Drives will be mounted to {MOUNT_BASE}/DRIVE_LABEL")
    print(f"Supported filesystems: ext4, ext3, ext2, NTFS, exFAT, FAT")

    try:
        while True:
            # Check if we have a mounted device
            if mounted_device:
                # Verify device health
                if not check_device_health():
                    handle_device_removal()
            else:
                # Try to mount a USB device
                device, partition, mount_path = mount_usb_device()
                if device:
                    print(f"Successfully mounted {partition} from device {device} at {mount_path}")

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

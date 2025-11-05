import smbus
import RPi.GPIO as GPIO
import time
import os
import psutil
import subprocess
import re
import logging
import shutil



# ========== LOGGING SETUP ==========
# Configure logging for console output only
logger = logging.getLogger("CFE_AutoMount")
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter with timestamp
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

logger.info("=" * 80)
logger.info("CFE Hat Auto Mount Service Starting")
logger.info("=" * 80)

# ========== GLOBAL VARIABLES ==========
i2c_ch = 1
i2c_address = 0x34
bus = smbus.SMBus(i2c_ch)

mounted = 0
lastReadCount = 0
lastWriteCount = 0

device_node = None
mount_path = "/media/RAW"
mounted_device_path = None  # Track the actual mounted device for yank detection

def readButtons():
    """Read button states from I2C microcontroller with debouncing"""
    try:
        while 1:
            data = bus.read_byte(i2c_address)
            if data != 0x69:  # Wait for valid data (not idle state)
                break
            time.sleep(0.1)
        eject_button = (data & 0x02 == 0x02)
        insert_button = (data & 0x01 == 0x01)
        logger.debug(f"Button read: insert={insert_button}, eject={eject_button}, raw=0x{data:02x}")
        return (insert_button, eject_button)
    except Exception as e:
        logger.error(f"Error reading buttons from I2C: {e}")
        return (0, 0)  # Return safe default


def writeLED(data):
    """Control LED indicator via I2C"""
    try:
        bus.write_byte(i2c_address, data)
        logger.debug(f"LED state set to: {data}")
    except Exception as e:
        logger.error(f"Error writing LED state to I2C: {e}")

def check_for_device(device_name):
    """Check for PCIe device using lspci and return device address"""
    try:
        logger.debug(f"Searching for PCIe device: {device_name}")
        output = subprocess.check_output("lspci -mm", shell=True, text=True)
        lines = output.split('\n')

        for line in lines:
            if device_name in line:
                # Extract the PCI address
                if len(line.split(" ")[0]) <= 7:
                    device_addr = "0000:" + line.split(" ")[0]
                else:
                    device_addr = line.split(" ")[0]
                logger.debug(f"Found device '{device_name}' at address: {device_addr}")
                return device_addr

        logger.debug(f"Device '{device_name}' not found in lspci output")
        return None
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running lspci command: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in check_for_device: {e}")
        return None

def get_filesystem_type(device_path):
    """Detect filesystem type using blkid"""
    try:
        result = subprocess.check_output(
            ["sudo", "blkid", "-s", "TYPE", "-o", "value", device_path],
            text=True,
            stderr=subprocess.PIPE
        ).strip()
        logger.debug(f"Detected filesystem type '{result}' for {device_path}")
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Error detecting filesystem type for {device_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_filesystem_type: {e}")
        return None


def get_disk_space_info(mount_path):
    """Get disk space information for mounted filesystem"""
    try:
        usage = shutil.disk_usage(mount_path)
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        percent_used = (usage.used / usage.total) * 100

        return {
            'total_gb': total_gb,
            'used_gb': used_gb,
            'free_gb': free_gb,
            'percent_used': percent_used
        }
    except Exception as e:
        logger.error(f"Error getting disk space for {mount_path}: {e}")
        return None


def get_device_label(device_path):
    """Get device label/name if available"""
    try:
        result = subprocess.check_output(
            ["sudo", "blkid", "-s", "LABEL", "-o", "value", device_path],
            text=True,
            stderr=subprocess.PIPE
        ).strip()
        return result if result else None
    except:
        return None

def mount_last_partition(device_node):
    """Mount the last partition of the detected NVMe device"""
    global mounted_device_path

    try:
        # List all partitions for the given device
        partitions = sorted([x for x in os.listdir(f"/dev/") if x.startswith(f"nvme{device_node[-1]}n1p")])
        last_partition = partitions[-1] if partitions else None

        if not last_partition:
            logger.warning(f"No partitions found for device {device_node}")
            return False

        device_path = f"/dev/{last_partition}"
        logger.info(f"Found partition: {device_path}")

        # Get device label if available
        device_label = get_device_label(device_path)
        if device_label:
            logger.info(f"Device label: '{device_label}'")

        # Detect filesystem type
        fs_type = get_filesystem_type(device_path)
        if not fs_type:
            logger.error(f"Could not determine filesystem type of {device_path}")
            return False

        logger.info(f"Filesystem type: {fs_type}")

        # Create mount point
        try:
            os.makedirs(mount_path, exist_ok=True)
            logger.debug(f"Mount point {mount_path} ready")
        except Exception as e:
            logger.error(f"Failed to create mount point {mount_path}: {e}")
            return False

        # Prepare mount command based on filesystem type
        mount_cmd = None
        if fs_type == "ntfs":
            mount_cmd = f"sudo mount -t ntfs3 -o uid=1000,gid=1000 {device_path} {mount_path}"
        elif fs_type == "ext4":
            mount_cmd = f"sudo mount -t ext4 {device_path} {mount_path}"
        elif fs_type == "exfat":
            mount_cmd = f"sudo mount -t exfat -o uid=1000,gid=1000 {device_path} {mount_path}"
        else:
            logger.error(f"Unsupported filesystem type: {fs_type}")
            return False

        logger.info(f"Attempting to mount {device_path} at {mount_path}...")

        # Execute mount command
        result = os.system(mount_cmd)

        if result == 0:
            mounted_device_path = device_path
            logger.info(f"Successfully mounted {device_path} at {mount_path}")

            # Get and log disk space information
            space_info = get_disk_space_info(mount_path)
            if space_info:
                logger.info(f"Disk space - Total: {space_info['total_gb']:.2f} GB, "
                           f"Used: {space_info['used_gb']:.2f} GB ({space_info['percent_used']:.1f}%), "
                           f"Free: {space_info['free_gb']:.2f} GB")

            return True
        else:
            logger.error(f"Mount command failed with return code {result}")
            mounted_device_path = None
            return False

    except Exception as e:
        logger.error(f"Error in mount_last_partition: {e}", exc_info=True)
        mounted_device_path = None
        return False


def unmountPCIe():
    """Unmount CFE card and remove PCIe device"""
    global mounted
    global device_node
    global mounted_device_path

    logger.info("=" * 60)
    logger.info("UNMOUNT REQUEST - Starting unmount procedure")
    logger.info("=" * 60)

    # Check if actually mounted
    if mounted == 0:
        logger.warning("Unmount requested but device was not marked as mounted")

    # Try to unmount the filesystem
    try:
        logger.info(f"Unmounting filesystem at {mount_path}...")
        result = os.system(f"sudo umount {mount_path}")

        if result == 0:
            logger.info(f"Successfully unmounted {mount_path}")
        else:
            logger.warning(f"Unmount command returned code {result} (may already be unmounted)")

    except Exception as e:
        logger.error(f"Error during unmount: {e}")

    # Find and remove the PCIe device
    NVMe_port = check_for_device("Non-Volatile memory controller")

    if NVMe_port:
        logger.info(f"Removing PCIe device at {NVMe_port}...")
        try:
            result = os.system(f"sudo bash -c 'echo 1 >/sys/bus/pci/devices/{NVMe_port}/remove'")
            if result == 0:
                logger.info(f"Successfully removed PCIe device {NVMe_port}")
            else:
                logger.warning(f"PCIe device removal returned code {result}")
        except Exception as e:
            logger.error(f"Error removing PCIe device: {e}")
    else:
        logger.warning("No NVMe device found to remove (may have already been removed)")

    # Turn off LED
    writeLED(False)
    logger.info("LED indicator disabled")

    # Clear state
    mounted = 0
    device_node = None
    mounted_device_path = None

    logger.info("Unmount procedure completed")
    logger.info("=" * 60)

def mountPCIe():
    """Mount CFE card by initializing PCIe and mounting filesystem"""
    global mounted
    global device_node

    logger.info("=" * 60)
    logger.info("MOUNT REQUEST - Starting mount procedure")
    logger.info("=" * 60)

    # Give hardware time to stabilize
    time.sleep(0.5)

    # Initialize PCIe driver
    driver_path = '/sys/devices/platform/axi/1000110000.pcie/driver'
    if os.path.exists(driver_path):
        logger.info("PCIe driver already loaded, performing bus rescan...")
        result = os.system("sudo bash -c 'echo 1 >/sys/bus/pci/rescan'")
        if result == 0:
            logger.info("PCIe bus rescan completed")
        else:
            logger.error(f"PCIe bus rescan failed with code {result}")
    else:
        logger.info("PCIe driver not loaded, binding driver...")
        result = os.system("sudo bash -c 'echo 1000110000.pcie > /sys/bus/platform/drivers/brcm-pcie/bind'")
        if result == 0:
            logger.info("PCIe driver bound successfully")
        else:
            logger.error(f"PCIe driver binding failed with code {result}")

    # Wait for device enumeration
    time.sleep(0.5)

    # Check for NVMe device
    logger.info("Scanning for NVMe device...")
    device_node = check_for_device("Non-Volatile memory controller")

    if device_node:
        logger.info(f"NVMe device detected: {device_node}")

        # Attempt to mount
        if mount_last_partition(device_node):
            writeLED(True)
            logger.info("LED indicator enabled")
            mounted = 1
            logger.info("Mount procedure completed successfully")
        else:
            logger.error("Mount procedure failed - could not mount partition")
            mounted = 0
    else:
        logger.warning("No NVMe device found after PCIe initialization")
        mounted = 0

    logger.info("=" * 60)


def check_for_yank():
    """
    Detect if the CFE card was yanked (removed without proper unmount)
    Returns True if card was yanked, False otherwise
    """
    global mounted
    global mounted_device_path
    global device_node

    if mounted == 0 or mounted_device_path is None:
        return False  # Not mounted, so can't be yanked

    # Check if the device still exists
    if not os.path.exists(mounted_device_path):
        logger.critical("!" * 60)
        logger.critical("CARD YANKED - Device removed without unmount!")
        logger.critical(f"Device {mounted_device_path} no longer exists")
        logger.critical("!" * 60)

        # Try to force unmount the stale mount point
        try:
            logger.warning(f"Attempting to clean up stale mount point {mount_path}...")
            result = os.system(f"sudo umount -f {mount_path} 2>/dev/null")
            if result == 0:
                logger.info("Force unmount successful")
            else:
                logger.warning("Force unmount may have failed, but continuing cleanup")
        except Exception as e:
            logger.error(f"Error during force unmount: {e}")

        # Clear the mounted state
        writeLED(False)
        logger.info("LED indicator disabled")
        mounted = 0
        device_node = None
        mounted_device_path = None

        logger.warning("System ready for new card insertion")
        logger.critical("!" * 60)

        return True

    # Additional check: verify mount point is still accessible
    try:
        os.stat(mount_path)
    except OSError as e:
        logger.critical("!" * 60)
        logger.critical("MOUNT POINT INACCESSIBLE - Possible card yank or I/O error")
        logger.critical(f"Cannot access {mount_path}: {e}")
        logger.critical("!" * 60)

        # Clean up
        try:
            os.system(f"sudo umount -f {mount_path} 2>/dev/null")
        except:
            pass

        writeLED(False)
        mounted = 0
        device_node = None
        mounted_device_path = None

        logger.warning("System reset after mount point became inaccessible")
        logger.critical("!" * 60)

        return True

    return False


# ========== MAIN EVENT LOOP ==========
last_insert_button = 0
last_eject_button = 0
yank_check_counter = 0
YANK_CHECK_INTERVAL = 10  # Check for yank every 1 second (10 * 0.1s)

logger.info("Performing initial button state check...")
(insert_button, eject_button) = readButtons()

# Auto-mount if card is already inserted at startup
if insert_button == 0 and mounted == 0:
    logger.info("Card detected at startup, performing initial mount...")
    mountPCIe()

last_insert_button = insert_button
last_eject_button = eject_button

logger.info("Entering main event loop...")
logger.info("Monitoring for card insertion, ejection, and yank events")

try:
    while True:
        # Read current button states
        (insert_button, eject_button) = readButtons()

        # Detect card insertion (falling edge on insert button)
        if last_insert_button == 1 and insert_button == 0 and mounted == 0:
            logger.info(">>> CARD INSERTION DETECTED (Insert button pressed) <<<")
            mountPCIe()

        # Detect eject button press (falling edge on eject button)
        if last_eject_button == 1 and eject_button == 0:
            logger.info(">>> EJECT BUTTON PRESSED <<<")
            unmountPCIe()

        # Update button state
        (last_insert_button, last_eject_button) = (insert_button, eject_button)

        # Periodically check for card yank
        yank_check_counter += 1
        if yank_check_counter >= YANK_CHECK_INTERVAL:
            yank_check_counter = 0
            if check_for_yank():
                logger.warning("Card yank detected and handled")

        time.sleep(0.1)

except KeyboardInterrupt:
    logger.info("Received shutdown signal (Ctrl+C)")
    logger.info("Cleaning up before exit...")
    if mounted:
        logger.info("Unmounting device before shutdown...")
        unmountPCIe()
    logger.info("CFE Hat Auto Mount Service stopped")

except Exception as e:
    logger.critical(f"Fatal error in main loop: {e}", exc_info=True)
    raise

finally:
    logger.info("Service terminated")

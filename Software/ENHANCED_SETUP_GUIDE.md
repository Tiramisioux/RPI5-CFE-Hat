# Enhanced Storage Auto-Mount Setup Guide

This guide covers setup and usage of the enhanced storage-automount service with improved CFE Hat mechanics.

## Features

### Enhanced CFE Hat Support
- ✅ **Instant yank detection** (0.1s response time using mechanical button state)
- ✅ **Fast recovery** after card removal (~1 second, no 30-second timeout)
- ✅ **Mechanical card presence tracking** via `card_physically_present` variable
- ✅ **Optimized unmount sequence** for yanked cards (skip umount → remove PCIe → cleanup)
- ✅ **Partition detection retry logic** (5 attempts with 0.5s delays)
- ✅ **Comprehensive logging** with timestamps for all operations

### USB Storage Support
- ✅ USB NVMe drives
- ✅ USB SSD drives
- ✅ Other USB storage devices
- ✅ RAW label arbitration (manages multiple devices labeled "RAW")
- ✅ Media-specific I/O tuning (cfe_nvme, usb_nvme, usb_ssd, other)

### Integration Features
- ✅ Redis integration for status monitoring
- ✅ Sysctl VM dirty page cache tuning for write performance
- ✅ Watchdog for sanity checks
- ✅ Udev-based device detection

## Installation

### Option 1: Automated Installation (Recommended)

```bash
cd /home/pi/RPI5-CFE-Hat/Software
sudo bash install-service.sh
```

This will:
1. Copy the script to `/opt/storage-automount/`
2. Install the systemd service
3. Enable auto-start on boot

### Option 2: Manual Installation

1. **Copy the script:**
   ```bash
   sudo mkdir -p /opt/storage-automount
   sudo cp storage-automount-enhanced.py /opt/storage-automount/
   sudo chmod +x /opt/storage-automount/storage-automount-enhanced.py
   ```

2. **Install systemd service:**
   ```bash
   sudo cp storage-automount.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable storage-automount
   ```

3. **Start the service:**
   ```bash
   sudo systemctl start storage-automount
   ```

## Usage

### Starting/Stopping the Service

```bash
# Start the service
sudo systemctl start storage-automount

# Stop the service
sudo systemctl stop storage-automount

# Restart the service
sudo systemctl restart storage-automount

# Check service status
sudo systemctl status storage-automount
```

### Viewing Logs

```bash
# Follow logs in real-time
sudo journalctl -u storage-automount -f

# View recent logs
sudo journalctl -u storage-automount -n 100

# View logs with timestamps
sudo journalctl -u storage-automount --since "10 minutes ago"
```

### Testing Without Service

For development or testing, you can run the script directly:

```bash
cd /home/pi/RPI5-CFE-Hat/Software
sudo python3 storage-automount-enhanced.py
```

**Note:** The script MUST be run with `sudo` (root privileges) because it needs to:
- Write to PCIe sysfs paths (`/sys/bus/platform/drivers/brcm-pcie/bind`)
- Mount/unmount filesystems
- Remove PCIe devices (`/sys/bus/pci/devices/{addr}/remove`)
- Modify sysctl settings

## Configuration

### Environment Variables

You can customize behavior via environment variables in the service file:

```bash
# Edit the service file
sudo nano /etc/systemd/system/storage-automount.service
```

Available variables:
- `STORAGE_AUTOMOUNT_LOG` - Log level (DEBUG, INFO, WARNING, ERROR)
- `REDIS_HOST` - Redis server hostname (default: localhost)
- `REDIS_PORT` - Redis server port (default: 6379)
- `REDIS_DB` - Redis database number (default: 0)

After editing, reload the service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart storage-automount
```

## Troubleshooting

### Permission Denied Errors

If you see errors like:
```
PCIe bind error: [Errno 13] Permission denied: '/sys/bus/platform/drivers/brcm-pcie/bind'
```

**Solution:** Make sure you're running with `sudo` or via the systemd service (which runs as root).

### Card Not Detected

1. **Check I2C connection:**
   ```bash
   sudo i2cdetect -y 1
   ```
   You should see device at address `0x34`.

2. **Check service logs:**
   ```bash
   sudo journalctl -u storage-automount -n 50
   ```

3. **Verify CFE Hat is properly seated** on the Raspberry Pi 5.

### Yank Detection Not Working

The enhanced version uses mechanical button state for instant detection. Check logs for:
```
>>> CARD INSERTION DETECTED <<<
CARD YANKED - CFE card physically removed!
```

If you don't see these messages, the I2C communication may have issues.

### Slow Remount After Yank

The enhanced version should remount within ~1 second. If it's slow:
1. Check that you're using `storage-automount-enhanced.py` (not the old version)
2. Review logs for any error messages
3. Ensure the script has the optimized unmount sequence

## How It Works

### CFE Hat Yank Detection

The script monitors the I2C button state (0x34) every 0.1 seconds:
- `raw=0x02` (insert_button=0) → Card is IN slot
- `raw=0x03` (insert_button=1) → Card is OUT of slot

When the card is mounted (`mounted_flag=True`) but mechanically removed (`card_physically_present=False`), a yank is detected instantly.

### Optimized Unmount Sequence

**Normal eject (button press):**
1. Unmount filesystem normally
2. Remove PCIe device
3. Clean up mount point

**Yank (card pulled without eject):**
1. Skip umount (would timeout for 30 seconds)
2. Remove PCIe device immediately
3. Clean up stale mount point (now instant since device is gone)

This eliminates the 30-second I/O timeout when the card is yanked.

### Partition Detection Retry

After PCIe rescan, the kernel needs time to read the partition table. The script:
1. Attempts to find partitions
2. Retries up to 5 times with 0.5s delays
3. Logs each attempt for debugging
4. Mounts the last partition when detected

## Uninstallation

```bash
sudo systemctl stop storage-automount
sudo systemctl disable storage-automount
sudo rm /etc/systemd/system/storage-automount.service
sudo rm -rf /opt/storage-automount
sudo systemctl daemon-reload
```

## Support

For issues or questions:
- Check the [GitHub repository](https://github.com/will127534/RPI5-CFE-Hat)
- Review the [Quick Start Guide](https://github.com/will127534/RPI5-CFE-Hat/wiki/RPI5-CFE-Hat-Quick-Start-Guide)
- Open an issue on GitHub

## Version History

### Enhanced Version (2025-11-06)
- Added instant yank detection using mechanical button state
- Optimized unmount sequence (eliminates 30-second timeout)
- Added partition detection retry logic
- Enhanced logging with comprehensive status messages
- Integrated CFE mechanics into unified storage-automount system
- Preserved USB storage handling and RAW arbitration

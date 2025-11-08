# USB SSD Auto-Mount for Raspberry Pi 5

A robust auto-mounting solution for USB-connected SSD drives on Raspberry Pi 5, designed to handle accidental disconnections gracefully.

## Features

- **Automatic Detection**: Automatically detects USB storage devices when connected
- **Multi-Filesystem Support**: Supports ext4, ext3, ext2, NTFS (ntfs3), exFAT, and FAT filesystems
- **Robust Disconnection Handling**: Gracefully handles accidental cable yanks and device removal
- **Auto-Recovery**: Automatically remounts devices when reconnected
- **Health Monitoring**: Continuously monitors device presence and mount status
- **Logging**: Comprehensive logging for troubleshooting

## Requirements

- Raspberry Pi 5 (or compatible Raspberry Pi)
- Python 3.7 or later
- Linux kernel 5.15+ (for NTFS3 driver support)
- Filesystem drivers:
  - ext4: Built into kernel (no additional packages needed)
  - NTFS: Uses kernel ntfs3 driver (kernel 5.15+)
  - exFAT: Install with `sudo apt install exfat-fuse exfat-utils`

## Installation

### 1. Install Required Packages

```bash
# Update package list
sudo apt update

# Install exFAT support (if needed)
sudo apt install exfat-fuse exfat-utils

# Verify NTFS3 support (kernel 5.15+)
uname -r  # Should show 5.15 or higher
```

### 2. Install the Script

The script is already located in the `Software` directory:
```bash
cd /home/user/RPI5-CFE-Hat/Software
```

Make sure it's executable:
```bash
chmod +x usb_ssd_automount.py
```

### 3. Install as Systemd Service (Recommended)

To run the auto-mount script automatically at boot:

```bash
# Copy the service file to systemd directory
sudo cp usb-ssd-automount.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start at boot
sudo systemctl enable usb-ssd-automount.service

# Start the service now
sudo systemctl start usb-ssd-automount.service
```

### 4. Verify Service Status

```bash
# Check service status
sudo systemctl status usb-ssd-automount.service

# View logs
sudo journalctl -u usb-ssd-automount.service -f
```

## Usage

### Automatic Mode (Systemd Service)

Once the systemd service is installed and running:

1. **Connect USB SSD**: Simply plug in your USB SSD
2. **Wait 1-2 seconds**: The device will be automatically detected and mounted
3. **Access Files**: Your drive will be mounted at `/media/USB_SSD`
4. **Disconnect**: You can safely remove the USB drive at any time

The script will automatically:
- Detect when the drive is connected
- Mount it to `/media/USB_SSD`
- Monitor for accidental disconnections
- Clean up gracefully if the drive is yanked
- Re-mount automatically if the same drive is reconnected

### Manual Mode

You can also run the script manually for testing:

```bash
sudo python3 /home/user/RPI5-CFE-Hat/Software/usb_ssd_automount.py
```

Press `Ctrl+C` to stop the script.

## Configuration

You can customize the script by editing `usb_ssd_automount.py`:

```python
# Change mount location (default: /media/USB_SSD)
MOUNT_PATH = "/media/USB_SSD"

# Change polling interval (default: 0.5 seconds)
POLL_INTERVAL = 0.5

# Change device settle time (default: 1.0 seconds)
DEVICE_SETTLE_TIME = 1.0

# Change log file location (default: /var/log/usb_ssd_automount.log)
LOG_FILE = "/var/log/usb_ssd_automount.log"
```

After making changes, restart the service:
```bash
sudo systemctl restart usb-ssd-automount.service
```

## How It Works

### Device Detection

The script monitors `/sys/class/block` for USB storage devices by:
1. Listing all block devices
2. Following symlinks to determine if they're USB devices
3. Filtering out non-storage devices (loop, ram, SD cards)

### Mounting Process

1. **Detect USB Device**: Script identifies new USB storage device
2. **Wait for Settle**: Waits for device to fully initialize
3. **Find Partitions**: Discovers all partitions on the device
4. **Select Partition**: Uses the last partition (configurable)
5. **Detect Filesystem**: Uses `blkid` to identify filesystem type
6. **Mount**: Mounts with appropriate options:
   - **NTFS**: `mount -t ntfs3 -o uid=1000,gid=1000,dmask=022,fmask=133`
   - **ext4**: `mount -t ext4`
   - **exFAT**: `mount -t exfat -o uid=1000,gid=1000,dmask=022,fmask=133`

### Robustness Features

**Accidental Disconnection Handling:**
- Continuous health monitoring checks device presence every 0.5 seconds
- If device disappears, performs lazy unmount (`umount -l`)
- Resets state and waits for device to be reconnected
- No crashes or hangs even with sudden disconnections

**Error Recovery:**
- Failed mounts don't crash the service
- Automatic retry on device reconnection
- Force unmount if normal unmount fails

## File Permissions

The script sets appropriate permissions for user access:
- **User ID**: 1000 (default Raspberry Pi user)
- **Group ID**: 1000 (default Raspberry Pi group)
- **Directory Mask**: 022 (755 permissions - rwxr-xr-x)
- **File Mask**: 133 (644 permissions - rw-r--r--)

This allows the default `pi` user to read/write files on NTFS and exFAT drives.

## Troubleshooting

### Device Not Mounting

**Check if service is running:**
```bash
sudo systemctl status usb-ssd-automount.service
```

**View logs for errors:**
```bash
sudo journalctl -u usb-ssd-automount.service -n 50
# or
sudo tail -f /var/log/usb_ssd_automount.log
```

**Verify USB device is detected:**
```bash
lsusb                    # List USB devices
lsblk                    # List block devices
sudo blkid               # List all block devices with filesystem info
```

### NTFS Not Working

**Check kernel version:**
```bash
uname -r  # Must be 5.15 or higher for ntfs3
```

If kernel is older than 5.15, you can use ntfs-3g:
```bash
sudo apt install ntfs-3g
```

Then modify the script to use `ntfs-3g` instead of `ntfs3`.

### exFAT Not Working

**Install exFAT support:**
```bash
sudo apt install exfat-fuse exfat-utils
```

### Permission Denied Errors

Make sure the script runs as root:
```bash
sudo systemctl status usb-ssd-automount.service
```

The systemd service should show `User=root`.

### Device Mounted Elsewhere

If your system has other auto-mount mechanisms (like `udisks2`):
```bash
# Check what's mounted
mount | grep /dev/sd

# Disable conflicting auto-mount (optional)
sudo systemctl stop udisks2
sudo systemctl disable udisks2
```

### Script Doesn't Start at Boot

**Check service is enabled:**
```bash
sudo systemctl is-enabled usb-ssd-automount.service
```

**Enable if not enabled:**
```bash
sudo systemctl enable usb-ssd-automount.service
```

## Advanced Usage

### Multiple USB Drives

Currently, the script mounts the first detected USB storage device. If you have multiple USB drives connected, only the first one will be mounted.

To support multiple drives, you can:
1. Run multiple instances with different mount paths
2. Modify the script to iterate through all devices

### Custom Partition Selection

By default, the script mounts the **last partition** on the device. To change this:

Edit the `mount_usb_device()` function:
```python
# Use first partition instead of last
partition_name = partitions[0]  # Change from partitions[-1]
```

### Integration with I2C/Buttons

If you want to integrate with the CFE hat's I2C buttons/LEDs:

1. Add I2C imports and initialization from `automount.py`
2. Add LED control in `mount_usb_device()` and `handle_device_removal()`
3. Optionally add button monitoring for manual eject

## Comparison with CFE Auto-Mount

| Feature | CFE Auto-Mount | USB SSD Auto-Mount |
|---------|----------------|-------------------|
| Interface | PCIe (CFexpress) | USB |
| Triggers | I2C buttons | Automatic detection |
| Device Path | `/dev/nvme*` | `/dev/sd*` |
| Mount Path | `/media/RAW` | `/media/USB_SSD` |
| LED Control | Yes (I2C) | No (can be added) |
| Filesystems | ext4, NTFS, exFAT | ext4, NTFS, exFAT, FAT |

## Logging

Logs are written to both:
- **File**: `/var/log/usb_ssd_automount.log`
- **Systemd Journal**: `sudo journalctl -u usb-ssd-automount.service`

Log levels:
- **INFO**: Normal operations (device detected, mounted, unmounted)
- **WARNING**: Non-critical issues (filesystem type unknown, multiple devices)
- **ERROR**: Critical errors (mount failed, device access failed)

## Security Considerations

The script runs as root (required for mounting). For enhanced security:

1. Review the script before running
2. Enable systemd security features (commented in service file)
3. Restrict mount path permissions
4. Consider using `polkit` for finer-grained permissions

## Uninstallation

To remove the auto-mount service:

```bash
# Stop the service
sudo systemctl stop usb-ssd-automount.service

# Disable from boot
sudo systemctl disable usb-ssd-automount.service

# Remove service file
sudo rm /etc/systemd/system/usb-ssd-automount.service

# Reload systemd
sudo systemctl daemon-reload

# Optionally remove mount point
sudo rmdir /media/USB_SSD
```

## License

This script is part of the RPI5-CFE-Hat project.

## Support

For issues or questions:
1. Check the logs: `sudo journalctl -u usb-ssd-automount.service -f`
2. Review this README for troubleshooting steps
3. Open an issue in the repository

## Future Enhancements

Possible improvements:
- [ ] Support for multiple USB drives simultaneously
- [ ] Integration with CFE hat I2C buttons/LEDs
- [ ] Configurable partition selection (first, last, all)
- [ ] Email/notification on mount errors
- [ ] Web interface for monitoring
- [ ] Support for encrypted volumes (LUKS)

# NVMe SSD Auto-Mount for Raspberry Pi 5 with NVMe HATs

A robust auto-mounting solution for NVMe drives connected via NVMe HATs (like Pimoroni NVMe Base, Geekworm X1001, etc.) on Raspberry Pi 5.

## Features

- **Automatic Detection**: Automatically detects NVMe devices when connected
- **Multi-Filesystem Support**: Supports ext4, ext3, ext2, NTFS (ntfs3), exFAT, and FAT filesystems
- **Robust Handling**: Gracefully handles device issues and removal
- **Auto-Recovery**: Automatically remounts devices when reconnected
- **Health Monitoring**: Continuously monitors device presence and mount status
- **Simple Logging**: Uses print statements for easy debugging

## What is an NVMe HAT?

NVMe HATs are expansion boards that connect to your Raspberry Pi's GPIO header and provide M.2 NVMe SSD connectivity via the PCIe interface. Popular NVMe HATs include:

- **Pimoroni NVMe Base** - Bottom-mounted NVMe adapter
- **Geekworm X1001** - Top-mounted NVMe HAT
- **52Pi N04** - Compact NVMe adapter
- **Waveshare PCIe to M.2 Adapter** - Various models

These HATs allow you to use fast NVMe SSDs with your Raspberry Pi 5, taking advantage of the PCIe Gen 2.0 or Gen 3.0 interface.

## Requirements

- Raspberry Pi 5 (or compatible Raspberry Pi with PCIe)
- NVMe HAT (Pimoroni NVMe Base, Geekworm, etc.)
- M.2 NVMe SSD installed in the HAT
- Python 3.7 or later
- Linux kernel 5.15+ (for NTFS3 driver support)
- Filesystem drivers:
  - ext4: Built into kernel (no additional packages needed)
  - NTFS: Uses kernel ntfs3 driver (kernel 5.15+)
  - exFAT: Install with `sudo apt install exfat-fuse exfat-utils`

## Installation

### 1. Enable PCIe on Raspberry Pi 5

First, ensure PCIe is enabled in your Raspberry Pi configuration:

```bash
# Check current PCIe status
sudo raspi-config

# Navigate to: Advanced Options > PCIe Speed
# Set to Gen 2 or Gen 3 (depending on your HAT)
```

Alternatively, edit `/boot/firmware/config.txt`:

```bash
# For PCIe Gen 2 (most HATs)
dtparam=pciex1_gen=2

# For PCIe Gen 3 (if supported by your HAT)
dtparam=pciex1_gen=3
```

Reboot after making changes:
```bash
sudo reboot
```

### 2. Verify NVMe Device Detection

After rebooting with your NVMe drive installed:

```bash
# Check if NVMe device is detected
lsblk

# Should show something like:
# nvme0n1         259:0    0  238.5G  0 disk
# └─nvme0n1p1     259:1    0  238.5G  0 part

# Check PCIe devices
lspci | grep -i nvme

# Check NVMe specifically
ls /dev/nvme*
```

### 3. Install Required Packages

```bash
# Update package list
sudo apt update

# Install exFAT support (if needed)
sudo apt install exfat-fuse exfat-utils

# Verify NTFS3 support (kernel 5.15+)
uname -r  # Should show 5.15 or higher
```

### 4. Install the Script

The script is already located in the `Software` directory:
```bash
cd /home/user/RPI5-CFE-Hat/Software
```

Make sure it's executable:
```bash
chmod +x nvme_ssd_automount.py
```

### 5. Install as Systemd Service (Recommended)

To run the auto-mount script automatically at boot:

```bash
# Copy the service file to systemd directory
sudo cp nvme-ssd-automount.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start at boot
sudo systemctl enable nvme-ssd-automount.service

# Start the service now
sudo systemctl start nvme-ssd-automount.service
```

### 6. Verify Service Status

```bash
# Check service status
sudo systemctl status nvme-ssd-automount.service

# View logs
sudo journalctl -u nvme-ssd-automount.service -f
```

## Usage

### Automatic Mode (Systemd Service)

Once the systemd service is installed and running:

1. **Power On**: Boot your Raspberry Pi with the NVMe drive installed
2. **Wait 1-2 seconds**: The device will be automatically detected and mounted
3. **Access Files**: Your drive will be mounted at `/media/NVME_SSD`

The script will automatically:
- Detect NVMe drives at boot
- Mount the last partition to `/media/NVME_SSD`
- Monitor for device issues
- Clean up gracefully if there are problems
- Re-mount automatically if the device becomes available again

### Manual Mode

You can also run the script manually for testing:

```bash
sudo python3 /home/user/RPI5-CFE-Hat/Software/nvme_ssd_automount.py
```

Press `Ctrl+C` to stop the script.

## Configuration

You can customize the script by editing `nvme_ssd_automount.py`:

```python
# Change mount location (default: /media/NVME_SSD)
MOUNT_PATH = "/media/NVME_SSD"

# Change polling interval (default: 0.5 seconds)
POLL_INTERVAL = 0.5

# Change device settle time (default: 1.0 seconds)
DEVICE_SETTLE_TIME = 1.0
```

After making changes, restart the service:
```bash
sudo systemctl restart nvme-ssd-automount.service
```

## How It Works

### Device Detection

The script monitors NVMe devices by:
1. Checking `/sys/class/nvme/` for NVMe controllers
2. Looking for NVMe namespaces in `/dev/` (nvme0n1, nvme1n1, etc.)
3. Filtering to ensure they're actual NVMe devices (not partitions)

### Mounting Process

1. **Detect NVMe Device**: Script identifies NVMe storage device
2. **Wait for Settle**: Waits for device to fully initialize
3. **Find Partitions**: Discovers all partitions on the device (nvme0n1p1, nvme0n1p2, etc.)
4. **Select Partition**: Uses the last partition (configurable)
5. **Detect Filesystem**: Uses `blkid` to identify filesystem type
6. **Mount**: Mounts with appropriate options:
   - **NTFS**: `mount -t ntfs3 -o uid=1000,gid=1000,dmask=022,fmask=133`
   - **ext4**: `mount -t ext4`
   - **exFAT**: `mount -t exfat -o uid=1000,gid=1000,dmask=022,fmask=133`

### Robustness Features

**Device Health Monitoring:**
- Continuous health monitoring checks device presence every 0.5 seconds
- If device disappears, performs lazy unmount (`umount -l`)
- Resets state and waits for device to be available again
- No crashes or hangs even with device issues

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

### NVMe Device Not Detected

**Check PCIe is enabled:**
```bash
# Check if PCIe is enabled
lspci | grep -i nvme

# If nothing shows, check config.txt
cat /boot/firmware/config.txt | grep pcie
```

**Enable PCIe if needed:**
```bash
sudo nano /boot/firmware/config.txt
# Add: dtparam=pciex1_gen=2
sudo reboot
```

**Verify NVMe device:**
```bash
# Check for NVMe devices
ls /dev/nvme*

# Check NVMe class
ls /sys/class/nvme/
```

### Device Not Mounting

**Check if service is running:**
```bash
sudo systemctl status nvme-ssd-automount.service
```

**View logs for errors:**
```bash
sudo journalctl -u nvme-ssd-automount.service -n 50
```

**Verify NVMe device is detected:**
```bash
lsblk                    # List block devices
sudo blkid               # List all block devices with filesystem info
ls /dev/nvme*           # List NVMe devices
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
sudo systemctl status nvme-ssd-automount.service
```

The systemd service should show `User=root`.

### PCIe Gen 3 Issues

Some NVMe drives may have compatibility issues with PCIe Gen 3. Try Gen 2:

```bash
sudo nano /boot/firmware/config.txt
# Change to: dtparam=pciex1_gen=2
sudo reboot
```

### Device Mounted Elsewhere

If your system has other auto-mount mechanisms (like `udisks2`):
```bash
# Check what's mounted
mount | grep /dev/nvme

# Disable conflicting auto-mount (optional)
sudo systemctl stop udisks2
sudo systemctl disable udisks2
```

## Comparison with Other Auto-Mount Scripts

| Feature | CFE Auto-Mount | USB SSD Auto-Mount | NVMe Auto-Mount |
|---------|----------------|-------------------|-----------------|
| Interface | PCIe (CFexpress) | USB | PCIe (NVMe HAT) |
| Triggers | I2C buttons | Automatic | Automatic |
| Device Path | `/dev/nvme*` | `/dev/sd*` | `/dev/nvme*` |
| Mount Path | `/media/RAW` | `/media/USB_SSD` | `/media/NVME_SSD` |
| LED Control | Yes (I2C) | No | No |
| Hot-Plug | Yes (with buttons) | Yes | Limited* |
| Filesystems | ext4, NTFS, exFAT | ext4, NTFS, exFAT, FAT | ext4, NTFS, exFAT, FAT |

*NVMe devices are typically not hot-pluggable and should be connected before boot.

## Using Multiple Auto-Mount Scripts

You can run multiple auto-mount scripts simultaneously:

- **CFE Auto-Mount** → `/media/RAW` (CFexpress cards)
- **USB SSD Auto-Mount** → `/media/USB_SSD` (USB drives)
- **NVMe Auto-Mount** → `/media/NVME_SSD` (NVMe HAT drives)

Each script uses different mount paths and device detection methods, so they won't conflict.

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
sudo systemctl stop nvme-ssd-automount.service

# Disable from boot
sudo systemctl disable nvme-ssd-automount.service

# Remove service file
sudo rm /etc/systemd/system/nvme-ssd-automount.service

# Reload systemd
sudo systemctl daemon-reload

# Optionally remove mount point
sudo rmdir /media/NVME_SSD
```

## Performance Notes

NVMe drives connected via NVMe HATs can achieve:
- **Sequential Read**: 400-500 MB/s (PCIe Gen 2) or 800-1000 MB/s (PCIe Gen 3)
- **Sequential Write**: 300-450 MB/s (PCIe Gen 2) or 600-900 MB/s (PCIe Gen 3)

Performance depends on:
- PCIe generation (Gen 2 vs Gen 3)
- NVMe drive specifications
- Thermal throttling (ensure adequate cooling)
- Filesystem type (ext4 is generally fastest for Linux)

## Compatible NVMe HATs

This script works with:

### Bottom-Mounted
- **Pimoroni NVMe Base** - Popular choice, good cooling
- **Geekworm X1000** - Compact design

### Top-Mounted
- **Geekworm X1001** - With active cooling
- **52Pi N04** - Aluminum heatsink design
- **Waveshare PCIe to M.2** - Various models

### Adapter Boards
- Any M.2 to PCIe adapter compatible with Raspberry Pi 5

## License

This script is part of the RPI5-CFE-Hat project.

## Support

For issues or questions:
1. Check the logs: `sudo journalctl -u nvme-ssd-automount.service -f`
2. Review this README for troubleshooting steps
3. Verify NVMe device is detected: `lsblk` and `ls /dev/nvme*`
4. Open an issue in the repository

## References

- [Raspberry Pi 5 PCIe Documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#pcie-gen-3-0)
- [Pimoroni NVMe Base Guide](https://learn.pimoroni.com/article/getting-started-with-nvme-base)
- [NVMe on Raspberry Pi](https://www.jeffgeerling.com/blog/2023/nvme-ssd-boot-raspberry-pi-5)

## Future Enhancements

Possible improvements:
- [ ] Support for multiple NVMe drives simultaneously
- [ ] SMART monitoring and health reporting
- [ ] Temperature monitoring with thermal throttling alerts
- [ ] Configurable partition selection (first, last, all)
- [ ] Support for encrypted volumes (LUKS)
- [ ] Integration with LED indicators

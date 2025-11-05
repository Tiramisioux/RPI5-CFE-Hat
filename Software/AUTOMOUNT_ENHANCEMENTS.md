# CFE Hat Auto Mount Script - Enhanced Version

## Overview

The enhanced `automount.py` script provides robust, production-ready CFE card auto-mounting with comprehensive logging and graceful error handling.

## New Features

### 1. Comprehensive Logging System

The script now uses Python's `logging` module with console output:

- **Output**: Console/CLI only (stdout)
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Timestamps**: All log entries include date and time stamps
- **Format**: `YYYY-MM-DD HH:MM:SS - LEVEL - Message`

#### Viewing Logs

Since output goes to console, you can redirect it to a file if needed:

```bash
# Run with output redirection
python3 automount.py > /tmp/automount.log 2>&1

# Run as a service and view with journalctl
sudo journalctl -u cfe-automount -f

# View live output
python3 automount.py
```

To save logs manually:
```bash
# Pipe output to tee for both display and file
python3 automount.py | tee /tmp/automount.log
```

### 2. Card Yank Detection

The script now detects when a CFE card is removed without proper unmounting:

- **Detection Method**: Periodic polling (every 1 second) checks if mounted device still exists
- **Recovery**: Automatically cleans up stale mount points and resets system state
- **Notifications**: Clear log messages indicate when a card yank occurs

#### Example Yank Detection Log

```
2025-11-05 14:32:15 - CRITICAL - !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
2025-11-05 14:32:15 - CRITICAL - CARD YANKED - Device removed without unmount!
2025-11-05 14:32:15 - CRITICAL - Device /dev/nvme0n1p1 no longer exists
2025-11-05 14:32:15 - CRITICAL - !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
2025-11-05 14:32:15 - WARNING - Attempting to clean up stale mount point /media/RAW...
2025-11-05 14:32:15 - INFO - Force unmount successful
2025-11-05 14:32:15 - INFO - LED indicator disabled
2025-11-05 14:32:15 - WARNING - System ready for new card insertion
```

### 3. Detailed Event Logging

All operations are now logged with comprehensive details:

#### Card Insertion Event
```
2025-11-05 14:30:10 - INFO - >>> CARD INSERTION DETECTED (Insert button pressed) <<<
2025-11-05 14:30:10 - INFO - ============================================================
2025-11-05 14:30:10 - INFO - MOUNT REQUEST - Starting mount procedure
2025-11-05 14:30:10 - INFO - ============================================================
2025-11-05 14:30:11 - INFO - PCIe driver already loaded, performing bus rescan...
2025-11-05 14:30:11 - INFO - PCIe bus rescan completed
2025-11-05 14:30:11 - INFO - Scanning for NVMe device...
2025-11-05 14:30:11 - INFO - NVMe device detected: 0000:01:00.0
2025-11-05 14:30:11 - INFO - Found partition: /dev/nvme0n1p1
2025-11-05 14:30:11 - INFO - Device label: 'CFE_CARD_001'
2025-11-05 14:30:11 - INFO - Filesystem type: exfat
2025-11-05 14:30:11 - INFO - Attempting to mount /dev/nvme0n1p1 at /media/RAW...
2025-11-05 14:30:11 - INFO - Successfully mounted /dev/nvme0n1p1 at /media/RAW
2025-11-05 14:30:11 - INFO - Disk space - Total: 476.94 GB, Used: 152.38 GB (32.0%), Free: 324.56 GB
2025-11-05 14:30:11 - INFO - LED indicator enabled
2025-11-05 14:30:11 - INFO - Mount procedure completed successfully
```

#### Eject Button Press Event
```
2025-11-05 14:35:22 - INFO - >>> EJECT BUTTON PRESSED <<<
2025-11-05 14:35:22 - INFO - ============================================================
2025-11-05 14:35:22 - INFO - UNMOUNT REQUEST - Starting unmount procedure
2025-11-05 14:35:22 - INFO - ============================================================
2025-11-05 14:35:22 - INFO - Unmounting filesystem at /media/RAW...
2025-11-05 14:35:22 - INFO - Successfully unmounted /media/RAW
2025-11-05 14:35:22 - INFO - Removing PCIe device at 0000:01:00.0...
2025-11-05 14:35:22 - INFO - Successfully removed PCIe device 0000:01:00.0
2025-11-05 14:35:22 - INFO - LED indicator disabled
2025-11-05 14:35:22 - INFO - Unmount procedure completed
```

### 4. Disk Space Information

When a card is mounted, the script now reports:
- Total capacity in GB
- Used space in GB
- Free space in GB
- Percentage used

This helps users monitor available recording space at a glance.

### 5. Device Identification

The script now attempts to read and log:
- Device label (if set on the filesystem)
- Filesystem type (NTFS, ExFAT, EXT4)
- Partition information
- PCIe device address

### 6. Improved Error Handling

- All exceptions are caught and logged with full stack traces
- System command return codes are checked and logged
- Graceful degradation when optional information is unavailable
- Clear error messages for troubleshooting

### 7. Startup Behavior

The script now logs its initialization:
```
2025-11-05 14:28:00 - INFO - ================================================================================
2025-11-05 14:28:00 - INFO - CFE Hat Auto Mount Service Starting
2025-11-05 14:28:00 - INFO - ================================================================================
2025-11-05 14:28:00 - INFO - Performing initial button state check...
2025-11-05 14:28:00 - INFO - Entering main event loop...
2025-11-05 14:28:00 - INFO - Monitoring for card insertion, ejection, and yank events
```

### 8. Graceful Shutdown

When stopped with Ctrl+C, the script cleanly unmounts any mounted devices:
```
2025-11-05 14:40:00 - INFO - Received shutdown signal (Ctrl+C)
2025-11-05 14:40:00 - INFO - Cleaning up before exit...
2025-11-05 14:40:00 - INFO - Unmounting device before shutdown...
2025-11-05 14:40:00 - INFO - CFE Hat Auto Mount Service stopped
```

## Technical Details

### Yank Check Interval

The card yank detection runs every 1 second (configurable via `YANK_CHECK_INTERVAL`):

```python
YANK_CHECK_INTERVAL = 10  # Check every 1 second (10 * 0.1s loop interval)
```

### Supported Filesystems

- **NTFS** (via ntfs3 driver)
- **ExFAT** (most common for CFE cards)
- **EXT4** (Linux native)

### Mount Options

- **NTFS/ExFAT**: Mounted with `uid=1000,gid=1000` for proper permissions
- **EXT4**: Mounted with default options

### Debug Mode

To enable more verbose logging, set the console handler to DEBUG level:

```python
console_handler.setLevel(logging.DEBUG)
```

This will show all button reads and internal state changes.

## Troubleshooting

### Missing Dependencies

Ensure all required Python packages are installed:
```bash
pip3 install RPi.GPIO smbus psutil
```

### I2C Communication Errors

If button reads fail, check I2C is enabled:
```bash
sudo raspi-config
# Interface Options -> I2C -> Enable
```

Verify the microcontroller is responding:
```bash
i2cdetect -y 1
```

Should show device at address `0x34`.

### Card Not Detected

Check the console output for PCIe initialization errors, or if running as a service:
```bash
sudo journalctl -u cfe-automount | grep "ERROR"
```

Verify the PCIe interface is working:
```bash
lspci -v
```

## Comparison: Old vs New

| Feature | Old Script | Enhanced Script |
|---------|-----------|-----------------|
| Logging | Basic print statements | Structured logging with timestamps |
| Log Output | Print to console | Python logging module (console) |
| Yank Detection | None | Automatic detection and recovery |
| Disk Space Info | Not reported | Full capacity reporting |
| Device Labels | Not shown | Labels displayed when available |
| Error Handling | Silent failures | Comprehensive error logging |
| Return Code Checks | Not performed | All commands validated |
| Shutdown Handling | No cleanup | Graceful unmount on exit |

## Recommendations for Production Use

1. **Start on Boot**: Add to systemd service for automatic startup
2. **Log Management**: When running as systemd service, logs go to journald automatically
3. **Redirect Logs**: If running standalone, redirect output to file or use `tee` for dual output
4. **Filesystem Choice**: Use ExFAT for maximum compatibility
5. **Label Your Cards**: Set filesystem labels for easy identification

## Future Enhancements

Potential additions for future versions:
- Email/SMS notifications on critical errors
- Web dashboard for real-time monitoring
- Statistics tracking (mounts/unmounts per day)
- Smart predictions for card failure based on I/O errors
- Integration with CinePi-Raw for recording start/stop coordination

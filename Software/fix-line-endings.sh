#!/bin/bash
# Fix line endings for all shell scripts
# This ensures CRLF (Windows) is converted to LF (Unix)

echo "Fixing line endings in shell scripts..."
sed -i 's/\r$//' install-service.sh
echo "✓ install-service.sh fixed"
echo "Line endings corrected. You can now run: sudo bash install-service.sh"

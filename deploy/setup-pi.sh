#!/usr/bin/env bash
#
# Pi deployment script — sets up systemd services for cc-sync and cc-web.
# Run on the Pi as root or with sudo.
#
# Usage: sudo ./setup-pi.sh <username>
#   e.g. sudo ./setup-pi.sh pi
#
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: sudo $0 <username>"
    echo "  e.g. sudo $0 pi"
    exit 1
fi

CC_USER="$1"
CC_HOME="$(eval echo "~$CC_USER")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Installing systemd services for user '$CC_USER' ==="

for svc in cc-sync.service cc-web.service; do
    sed "s|%USER%|$CC_USER|g; s|%HOME%|$CC_HOME|g" "$SCRIPT_DIR/$svc" \
        > "/etc/systemd/system/$svc"
done

systemctl daemon-reload
systemctl enable cc-sync cc-web
systemctl restart cc-sync cc-web

echo "=== Service status ==="
systemctl status cc-sync --no-pager || true
systemctl status cc-web --no-pager || true

echo ""
echo "Done. Both services are running."

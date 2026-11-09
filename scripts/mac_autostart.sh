#!/bin/bash
# macOS: start 不打字 automatically at login (LaunchAgent).
#   bash scripts/mac_autostart.sh            install / update
#   bash scripts/mac_autostart.sh remove     uninstall
# Note: when started this way, macOS asks for permissions on behalf of the venv's
# python (not Terminal), so add .venv/bin/python under Input Monitoring and Accessibility.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.budazi.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "$1" = "remove" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "removed $PLIST"
  exit 0
fi

PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "run 'uv sync' in $ROOT first"; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>-m</string><string>budazi.app</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
EOF
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $PLIST (starts at login; started now)"

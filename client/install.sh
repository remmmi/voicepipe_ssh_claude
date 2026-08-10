#!/usr/bin/env bash
# Installs the VoicePipe launcher for the current user (XDG desktops).
# With --autostart, also adds it to session startup.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

chmod +x "$DIR/voicetray.py" "$DIR/voicepipe.sh"

APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
sed "s|@DIR@|$DIR|g" "$DIR/voicepipe-tray.desktop.in" > "$APPS/voicepipe-tray.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "Launcher installed in $APPS"

if [ "${1:-}" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  cp "$APPS/voicepipe-tray.desktop" "$HOME/.config/autostart/"
  echo "Added to session autostart"
fi

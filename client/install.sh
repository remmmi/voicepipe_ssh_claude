#!/usr/bin/env bash
# Installs the VoicePipe launcher for the current user (XDG desktops).
# With --autostart, also adds it to session startup.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

chmod +x "$DIR/voicetray.py" "$DIR/voicepipe.sh"

APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
sed "s|@DIR@|$DIR|g" "$DIR/voicepipe-tray.desktop.in" > "$APPS/voicepipe-tray.desktop"

# named icon so the launcher shows up properly in the Multimedia menu
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICONS"
cp "$DIR/icons/voicepipe-on.svg" "$ICONS/voicepipe.svg"

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
command -v kbuildsycoca5 >/dev/null && kbuildsycoca5 --noincremental >/dev/null 2>&1 || true
echo "Launcher and icon installed for the current user"

if [ "${1:-}" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  cp "$APPS/voicepipe-tray.desktop" "$HOME/.config/autostart/"
  echo "Added to session autostart"
fi

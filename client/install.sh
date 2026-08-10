#!/usr/bin/env bash
# Installs the Voxtunnel launcher for the current user (XDG desktops).
# With --autostart, also adds it to session startup.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

chmod +x "$DIR/voxtunnel-tray.py" "$DIR/voxtunnel.sh"

APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"
sed "s|@DIR@|$DIR|g" "$DIR/voxtunnel.desktop.in" > "$APPS/voxtunnel.desktop"

# named icon so the launcher shows up properly in the Multimedia menu
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICONS"
cp "$DIR/icons/voxtunnel-on.svg" "$ICONS/voxtunnel.svg"

# clean leftovers from the old VoicePipe name
rm -f "$APPS/voicepipe-tray.desktop" "$ICONS/voicepipe.svg" \
      "$HOME/.config/autostart/voicepipe-tray.desktop"

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
command -v kbuildsycoca5 >/dev/null && kbuildsycoca5 --noincremental >/dev/null 2>&1 || true
echo "Launcher and icon installed for the current user"

if [ "${1:-}" = "--autostart" ]; then
  mkdir -p "$HOME/.config/autostart"
  cp "$APPS/voxtunnel.desktop" "$HOME/.config/autostart/"
  echo "Added to session autostart"
fi

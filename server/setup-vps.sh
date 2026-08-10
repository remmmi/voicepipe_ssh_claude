#!/usr/bin/env bash
# Prepares a VPS to receive Voxtunnel audio: ALSA loopback card (snd-aloop)
# plus alsa-utils. Idempotent and non-destructive: it only ADDS the loopback
# card, it never touches existing audio configuration.
#
#   ./setup-vps.sh            check + load snd-aloop for this boot
#   ./setup-vps.sh --persist  also load it automatically at every boot
#
# Run as root (or with sudo).
set -euo pipefail

say() { echo "setup-vps: $*"; }

[ "$(id -u)" -eq 0 ] || { say "run as root (sudo $0)"; exit 1; }

# --- alsa-utils (aplay/arecord) ---------------------------------------------
if command -v aplay >/dev/null 2>&1; then
  say "alsa-utils: already installed"
elif command -v apt-get >/dev/null 2>&1; then
  say "installing alsa-utils (apt)"
  DEBIAN_FRONTEND=noninteractive apt-get install -y alsa-utils
elif command -v dnf >/dev/null 2>&1; then
  say "installing alsa-utils (dnf)"
  dnf install -y alsa-utils
elif command -v pacman >/dev/null 2>&1; then
  say "installing alsa-utils (pacman)"
  pacman -S --noconfirm --needed alsa-utils
else
  say "no known package manager; install alsa-utils manually"; exit 1
fi

# --- snd-aloop module ---------------------------------------------------------
if lsmod | grep -q '^snd_aloop'; then
  say "snd-aloop: already loaded"
else
  say "loading snd-aloop"
  modprobe snd-aloop
fi

aplay -l | grep -q Loopback || { say "Loopback card not visible after modprobe"; exit 1; }
say "Loopback card: ok"

# --- persistence (optional) ---------------------------------------------------
if [ "${1:-}" = "--persist" ]; then
  CONF=/etc/modules-load.d/snd-aloop.conf
  if [ -f "$CONF" ] && grep -q '^snd-aloop$' "$CONF"; then
    say "persistence: already configured ($CONF)"
  else
    echo snd-aloop >> "$CONF"
    say "persistence: snd-aloop added to $CONF"
  fi
fi

say "done. Recording side on this VPS reads from: plughw:Loopback,1,0"

# VoicePipe — client (local machine)

This folder is the LOCAL side of VoicePipe: it captures the microphone and
streams it over SSH to the ALSA loopback card of a remote server. See the
repository README for the full picture.

## Files

- `voicepipe.sh` — the streaming engine (bash). One process per stream,
  configured entirely through environment variables (`VPS_HOST`, `MIC`,
  `RATE`, `BUFFER_US`, `PERIOD_US`). Run `./voicepipe.sh --help`.
- `voicetray.py` — PyQt5 tray/window app. Discovers hosts from
  `~/.ssh/config` (Host blocks that declare an IdentityFile), shows one
  toggle per host plus a master "Transmission" toggle, and runs one
  `voicepipe.sh` process per active host.
- `install.sh` — user-level install of the desktop launcher (no root).
- `voicepipe-tray.desktop.in` — launcher template; `@DIR@` is replaced by
  the absolute path of this folder at install time.
- `icons/` — SVG tray icons (green = transmitting, orange = cut).

## Installing without breaking the machine

Everything is user-level. Do NOT install anything system-wide beyond the
distribution packages listed below, and do not modify any audio
configuration: the client only READS the microphone through the existing
ALSA/PulseAudio/PipeWire stack.

1. Check dependencies (install with the distro package manager if missing):
   - `python3` and PyQt5 (`python3-pyqt5` on Debian/Ubuntu,
     `python3-qt5` on Fedora, `python-pyqt5` on Arch)
   - `alsa-utils` (for `arecord`) or `ffmpeg` as fallback recorder
   - `openssh-client`
   - optional: `sox` (only for `voicepipe.sh --tone`)
2. `./install.sh` installs the menu launcher for the current user only
   (`~/.local/share/applications`). `./install.sh --autostart` also copies
   it to `~/.config/autostart`. Nothing else is written outside
   `~/.cache/voicepipe/` (logs) and `~/.config/voicepipe/` (optional
   `ignore` file).
3. Run `python3 voicetray.py` (or the menu entry). A second launch exits
   immediately (single-instance lock in /tmp).

## Rules for agents

- Never commit or print the user's `~/.ssh/config` contents, host names or
  key paths: they are private. The app reads them at runtime only.
- Do not start a stream toward a host without the user asking: it sends
  live microphone audio.
- SSH access must use keys (`BatchMode=yes`); never store passwords.
- Keep `voicepipe.sh` free of automatic retry loops (see its header
  comment for why).

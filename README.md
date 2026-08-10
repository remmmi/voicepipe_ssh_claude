# VoicePipe SSH

Stream your local microphone to the virtual sound card of a remote server
(VPS) over SSH, with a small Linux tray app to switch streams on and off
per host.

Typical use case: you work on a VPS through SSH and want voice input
there (speech-to-text, Claude Code voice input, any program that records
from a microphone). VoicePipe makes your local mic appear on the VPS as a
regular ALSA capture device.

Version francaise : [README.fr.md](README.fr.md)

```
local machine                      VPS
-----------------                  -------------------------------
mic -> arecord ---- ssh (raw PCM) ---> aplay -> snd-aloop loopback
                                                  ^
                                       any recorder reads it as a mic
                                       (plughw:Loopback,1,0)
```

Latency is roughly 150-200 ms end to end with the default buffers. Raw
PCM, no compression: about 96 kB/s at 48 kHz mono.

## Repository layout

- `client/` — local machine: `voicepipe.sh` (streaming engine) and
  `voicetray.py` (PyQt5 tray app with per-host switches).
- `server/` — VPS side: `setup-vps.sh` (idempotent loopback setup).
- Each folder has a `CLAUDE.md` so Claude Code (or any agent) can install
  that side safely without breaking the machine.

## Requirements

Client (local Linux desktop):

| Package (Debian name)  | Purpose                              |
|------------------------|--------------------------------------|
| `openssh-client`       | transport                            |
| `alsa-utils`           | `arecord` capture (or `ffmpeg`)      |
| `python3`, `python3-pyqt5` | tray app                         |
| `sox` (optional)       | `--tone` test signal                 |

Server (VPS):

| Package                | Purpose                              |
|------------------------|--------------------------------------|
| `alsa-utils`           | `aplay` playback into the loopback   |
| `snd-aloop` (kernel module) | virtual sound card              |

SSH key authentication is required (the scripts use `BatchMode=yes`;
password prompts are never shown).

## Setup

Server, easiest way — the Debian package from the
[latest release](https://github.com/remmmi/voicepipe_ssh_claude/releases/latest)
(loads snd-aloop now and at every boot):

```
sudo apt install ./voicepipe-server_*.deb
```

Or with the script, as root on the VPS:

```
cd server
./setup-vps.sh --persist
```

Client, easiest way — grab the Debian package from the
[latest release](https://github.com/remmmi/voicepipe_ssh_claude/releases/latest):

```
sudo apt install ./voicepipe_*.deb
voicetray
```

Or from source, without root:

```
cd client
./voicepipe.sh --check    # VPS_HOST=user@my-vps ./voicepipe.sh --check
./install.sh              # desktop launcher; --autostart for session start
python3 voicetray.py
```

## Tray app

The app discovers hosts from `~/.ssh/config`: every `Host` block that
declares an `IdentityFile` gets a switch (wildcard patterns and
`github.com` are skipped; add more exclusions in
`~/.config/voicepipe/ignore`, one host per line).

- One switch per host; several streams can run at the same time.
- A master "Transmission" toggle with a green/gray light: switching it
  off cuts every stream but keeps the per-host switches as they are;
  switching it back on restores the streams whose switch is ON.
- Tray icon: green when transmission is enabled, orange when it is cut.
  Left click shows or hides the window, right click opens the same
  switches in a menu.
- A dead stream (network drop, failed preflight) turns its switch off and
  shows the error; there is no automatic reconnect by design.
- Logs per host in `~/.cache/voicepipe/<host>.log`.

## Engine without the GUI

`voicepipe.sh` works on its own, configured by environment variables
(`VPS_HOST`, `MIC`, `RATE`, `BUFFER_US`, `PERIOD_US`):

```
VPS_HOST=user@my-vps ./voicepipe.sh --check   # verify both ends
VPS_HOST=user@my-vps ./voicepipe.sh           # stream until Ctrl-C
VPS_HOST=user@my-vps ./voicepipe.sh --tone    # 1 kHz test tone
```

If you hear dropouts (xruns), raise the buffers:
`BUFFER_US=200000 PERIOD_US=50000`.

## Debian package

`./build-deb.sh` builds both packages (version from `voicetray.py`):

- `voicepipe_<version>_all.deb` — client: `voicetray` command, menu
  entry, icons.
- `voicepipe-server_<version>_all.deb` — server: loads `snd-aloop` at
  install and at every boot via `/etc/modules-load.d/`.

Prebuilt packages are attached to each GitHub release. The user-level
`client/install.sh` and `server/setup-vps.sh` remain the no-package
alternatives.

## Versioning

Single source of truth: `__version__` in `client/voicetray.py` (shown at
the bottom of the window). Each release gets a matching git tag
(`v1.0.0`, ...).

## Tested on

- Client: Debian with KDE Plasma.
- Server: Debian VPS.

Other Linux distributions and desktops should work: the client only needs
Python 3, PyQt5 and a system tray; the server only needs `snd-aloop` and
`alsa-utils`.

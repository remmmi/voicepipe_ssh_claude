# Voxtunnel client — Windows

## Recommended path: WSL2 (reliable today)

WSLg forwards the Windows microphone into the Linux subsystem through
PulseAudio, so the regular Linux client works unchanged, window
included (WSLg shows Linux GUI windows on the Windows desktop; only the
tray icon is not relayed):

```
wsl --install -d Debian
# inside WSL, with voxtunnel_*.deb downloaded from
# github.com/remmmi/voxtunnel/releases/latest:
sudo apt install ./voxtunnel_*.deb
voxtunnel
```

The .deb pulls its own dependencies. SSH keys live in the WSL home
(`~/.ssh`), not the Windows one. To run from source instead, clone the
repository and launch `client/voxtunnel-tray.py` with python3.

## Native path (experimental)

Status: CI-tested only (offscreen smoke tests on GitHub Windows
runners), never validated on real Windows hardware. Feedback welcome.

```
winget install ffmpeg python
pip install PyQt5
git clone https://github.com/remmmi/voxtunnel.git
python voxtunnel/client/voxtunnel-tray.py
```

The tray app is cross-platform: on Windows it captures with
`ffmpeg -f dshow` and pipes to the built-in OpenSSH client. It
auto-picks the first DirectShow microphone; to choose another, run
`voxtunnel.cmd --list` and write the exact device name into
`%USERPROFILE%\.config\voxtunnel\mic`. Keys go in `%USERPROFILE%\.ssh`
(BatchMode: no password prompts).

CLI only: see `voxtunnel.cmd` in this folder.

## Known limits

- Never tested on real hardware: dshow device names and the tray
  behavior in the Windows notification area come from documentation.
- No orphan-stream cleanup on Windows (POSIX-only mechanism); stray
  ffmpeg/ssh processes are visible in the Task Manager if the app is
  killed without Quit.
- The server side is unchanged: a Linux box with snd-aloop (see server/).

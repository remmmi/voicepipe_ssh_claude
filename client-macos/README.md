# Voxtunnel client — macOS (experimental)

Status: CI-tested only (offscreen smoke tests on GitHub macOS runners),
never validated on real Apple hardware. Feedback very welcome — open an
issue with what worked or broke.

## Install

```
brew install ffmpeg python
pip3 install PyQt5
git clone https://github.com/remmmi/voxtunnel.git
```

SSH keys are read from `~/.ssh/config` as on Linux.

## GUI (menu bar app, same as Linux)

```
python3 voxtunnel/client/voxtunnel-tray.py
```

The tray app is cross-platform: on macOS it captures with
`ffmpeg -f avfoundation` and pipes to ssh itself. Default microphone is
avfoundation `:0`; to pick another one, list devices with
`ffmpeg -f avfoundation -list_devices true -i ""` and write the input
(for example `:1`) into `~/.config/voxtunnel/mic`.

macOS will prompt for microphone permission on first capture.

## CLI only

```
VPS_HOST=user@vps ./voxtunnel.sh --check
VPS_HOST=user@vps ./voxtunnel.sh
```

## Known limits

- Never tested on real hardware: device names, mic permission flow and
  menu bar behavior come from documentation, not experience.
- The server side is unchanged: a Linux box with snd-aloop (see server/).

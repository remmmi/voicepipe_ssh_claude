#!/usr/bin/env bash
# Builds a Debian package of the VoicePipe client (tray app + engine).
# Output: voicepipe_<version>_all.deb in the repository root.
# The version comes from __version__ in client/voicetray.py.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$DIR/client/voicetray.py")"
[ -n "$VERSION" ] || { echo "version not found in voicetray.py" >&2; exit 1; }

BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
ROOT="$BUILD/voicepipe_${VERSION}_all"

mkdir -p "$ROOT/DEBIAN" \
         "$ROOT/usr/share/voicepipe/icons" \
         "$ROOT/usr/bin" \
         "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/icons/hicolor/scalable/apps" \
         "$ROOT/usr/share/doc/voicepipe"

install -m 755 "$DIR/client/voicepipe.sh" "$DIR/client/voicetray.py" \
        "$ROOT/usr/share/voicepipe/"
install -m 644 "$DIR/client/icons/"*.svg "$ROOT/usr/share/voicepipe/icons/"
install -m 644 "$DIR/client/icons/voicepipe-on.svg" \
        "$ROOT/usr/share/icons/hicolor/scalable/apps/voicepipe.svg"
install -m 644 "$DIR/README.md" "$DIR/README.fr.md" "$ROOT/usr/share/doc/voicepipe/"

cat > "$ROOT/usr/bin/voicetray" <<'EOF'
#!/bin/sh
exec /usr/share/voicepipe/voicetray.py "$@"
EOF
chmod 755 "$ROOT/usr/bin/voicetray"

sed 's|^Exec=.*|Exec=voicetray|' "$DIR/client/voicepipe-tray.desktop.in" \
    > "$ROOT/usr/share/applications/voicepipe-tray.desktop"
chmod 0644 "$ROOT/usr/share/applications/voicepipe-tray.desktop"

cat > "$ROOT/DEBIAN/control" <<EOF
Package: voicepipe
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Depends: python3, python3-pyqt5, alsa-utils, openssh-client
Recommends: sox
Maintainer: remmmi <remmmi@users.noreply.github.com>
Homepage: https://github.com/remmmi/voicepipe_ssh_claude
Description: Stream the local microphone to a VPS over SSH
 VoicePipe streams the local microphone to the ALSA loopback card of a
 remote server over SSH, so voice tools running there can record it as
 a regular capture device. Ships a tray app with one switch per SSH
 host (discovered from ~/.ssh/config) and a master transmission toggle.
 The server side only needs alsa-utils and the snd-aloop module (see
 the server/ folder of the homepage repository).
EOF

# umask restrictif possible : dpkg-deb exige des repertoires 0755
find "$ROOT" -type d -exec chmod 0755 {} +

dpkg-deb --build --root-owner-group "$ROOT" "$DIR/voicepipe_${VERSION}_all.deb"
echo "built: voicepipe_${VERSION}_all.deb"

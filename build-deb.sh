#!/usr/bin/env bash
# Builds the VoicePipe Debian packages:
#   voicepipe_<version>_all.deb         client (tray app + engine)
#   voicepipe-server_<version>_all.deb  server (snd-aloop loopback setup)
# Output in the repository root. Version: __version__ in client/voicetray.py.
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

# --- paquet serveur -----------------------------------------------------------
SROOT="$BUILD/voicepipe-server_${VERSION}_all"
mkdir -p "$SROOT/DEBIAN" \
         "$SROOT/etc/modules-load.d" \
         "$SROOT/usr/share/doc/voicepipe-server"

echo snd-aloop > "$SROOT/etc/modules-load.d/voicepipe-snd-aloop.conf"
chmod 0644 "$SROOT/etc/modules-load.d/voicepipe-snd-aloop.conf"
install -m 644 "$DIR/README.md" "$DIR/README.fr.md" \
        "$SROOT/usr/share/doc/voicepipe-server/"

cat > "$SROOT/DEBIAN/control" <<EOF
Package: voicepipe-server
Version: $VERSION
Section: sound
Priority: optional
Architecture: all
Depends: alsa-utils, kmod
Maintainer: remmmi <remmmi@users.noreply.github.com>
Homepage: https://github.com/remmmi/voicepipe_ssh_claude
Description: Receive VoicePipe audio on a server (ALSA loopback setup)
 Server side of VoicePipe: loads the snd-aloop kernel module now and at
 every boot, so audio streamed over SSH into plughw:Loopback,0,0 can be
 recorded locally from plughw:Loopback,1,0 like a regular microphone.
 Purely additive: no existing audio configuration is touched.
EOF

echo /etc/modules-load.d/voicepipe-snd-aloop.conf > "$SROOT/DEBIAN/conffiles"

cat > "$SROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    modprobe snd-aloop 2>/dev/null \
        || echo "voicepipe-server: snd-aloop not loadable now, will load at boot"
fi
exit 0
EOF
chmod 0755 "$SROOT/DEBIAN/postinst"

find "$SROOT" -type d -exec chmod 0755 {} +
find "$SROOT/DEBIAN" -type f -name conffiles -exec chmod 0644 {} +

dpkg-deb --build --root-owner-group "$SROOT" "$DIR/voicepipe-server_${VERSION}_all.deb"
echo "built: voicepipe-server_${VERSION}_all.deb"

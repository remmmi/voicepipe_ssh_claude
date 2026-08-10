#!/usr/bin/env python3
#
# voicetray.py — petite app tray/fenetre pour piloter voicepipe.sh
# vers les VPS decouverts dans ~/.ssh/config.
#
# - fenetre : un voyant + interrupteur maitre "Transmission", puis une ligne
#             par host avec un interrupteur on/off et un statut
# - tray    : icone dediee dans la barre KDE, clic droit = menu avec les memes
#             interrupteurs, clic gauche = afficher/masquer la fenetre
#
# Les interrupteurs par host expriment l'etat SOUHAITE ; l'interrupteur
# maitre "Transmission" coupe/retablit les liaisons sans changer cet etat :
# OFF -> voyant gris, tous les streams coupes, les interrupteurs restent tels
# quels ; ON -> voyant vert, les liaisons des hosts ON sont retablies.
#
# Decouverte : tous les blocs "Host" de ~/.ssh/config qui declarent un
# IdentityFile, hors patterns a jokers et hors liste d'exclusion
# (~/.config/voicepipe/ignore, un host par ligne, github.com exclu d'office).
#
# Chaque stream est un process voicepipe.sh lance dans son propre groupe ;
# l'arret envoie SIGTERM au groupe entier (arecord | ssh compris).
# Pas de relance automatique : un stream mort repasse son interrupteur a OFF
# et affiche l'erreur.

import os
import signal
import subprocess
import sys

from PyQt5.QtCore import QLockFile, QObject, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QMenu, QSlider,
    QSystemTrayIcon, QVBoxLayout, QWidget,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VOICEPIPE = os.path.join(SCRIPT_DIR, "voicepipe.sh")
ICON_DIR = os.path.join(SCRIPT_DIR, "icons")
LOG_DIR = os.path.join(os.path.expanduser("~"), ".cache", "voicepipe")
IGNORE_FILE = os.path.join(os.path.expanduser("~"), ".config", "voicepipe", "ignore")
DEFAULT_IGNORE = {"github.com"}

OFF, STARTING, ON, ERROR = "off", "starting", "on", "error"

GREEN, GRAY, ORANGE, RED = "#4caf50", "#9e9e9e", "#e6a23c", "#f44336"

# tampon ALSA reglable depuis la fenetre (voir l'en-tete de voicepipe.sh)
BUFFER_MIN_MS, BUFFER_DEFAULT_MS, BUFFER_MAX_MS = 40, 80, 300

# detecte si quelqu'un enregistre le loopback distant : un substream de
# capture pcm1c non "closed" = une ecoute est ouverte sur le VPS
LISTEN_CMD = ("grep -L closed /proc/asound/Loopback/pcm1c/sub*/status "
              "2>/dev/null | grep -q . && echo L || echo N")


def discover_hosts():
    """Hosts de ~/.ssh/config avec IdentityFile, hors jokers et exclusions."""
    ignore = set(DEFAULT_IGNORE)
    try:
        with open(IGNORE_FILE) as f:
            ignore |= {l.strip() for l in f if l.strip() and not l.startswith("#")}
    except OSError:
        pass

    hosts, current, has_key = [], [], False
    try:
        with open(os.path.expanduser("~/.ssh/config")) as f:
            lines = f.readlines()
    except OSError:
        return []

    def flush():
        if has_key:
            for h in current:
                if "*" not in h and "?" not in h and h not in ignore:
                    hosts.append(h)

    for line in lines:
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        key = parts[0].lower()
        if key == "host":
            flush()
            current, has_key = parts[1:], False
        elif key == "identityfile":
            has_key = True
    flush()
    return hosts


class StreamManager(QObject):
    """Un process voicepipe.sh par host actif, surveille par un timer."""

    state_changed = pyqtSignal(str, str, str)  # host, etat, message

    def __init__(self):
        super().__init__()
        self.procs = {}      # host -> Popen
        self.stopping = set()
        self.buffer_ms = BUFFER_DEFAULT_MS
        os.makedirs(LOG_DIR, exist_ok=True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(1000)

    def log_path(self, host):
        return os.path.join(LOG_DIR, host + ".log")

    def is_running(self, host):
        return host in self.procs

    def start(self, host):
        if host in self.procs:
            return
        # ratio tampon/periode 4:1, comme les defauts 80/20 ms du script
        env = dict(os.environ, VPS_HOST=host,
                   BUFFER_US=str(self.buffer_ms * 1000),
                   PERIOD_US=str(self.buffer_ms * 250))
        log = open(self.log_path(host), "wb", buffering=0)
        try:
            proc = subprocess.Popen(
                [VOICEPIPE], env=env, stdout=log, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError as e:
            log.close()
            self.state_changed.emit(host, ERROR, str(e))
            return
        log.close()
        self.procs[host] = proc
        self.state_changed.emit(host, STARTING, "")

    def stop(self, host):
        proc = self.procs.get(host)
        if not proc:
            return
        self.stopping.add(host)
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def stop_all(self):
        for host in list(self.procs):
            self.stop(host)

    def _last_log_line(self, host):
        try:
            with open(self.log_path(host), errors="replace") as f:
                lines = [l.strip() for l in f if l.strip()]
            return lines[-1] if lines else "arret sans message"
        except OSError:
            return "pas de log"

    def _poll(self):
        for host, proc in list(self.procs.items()):
            if proc.poll() is not None:
                del self.procs[host]
                if host in self.stopping:
                    self.stopping.discard(host)
                    self.state_changed.emit(host, OFF, "")
                else:
                    self.state_changed.emit(host, ERROR, self._last_log_line(host))
            else:
                # passe de "connexion" a "actif" quand le preflight est franchi
                try:
                    with open(self.log_path(host), errors="replace") as f:
                        if "Streaming" in f.read():
                            self.state_changed.emit(host, ON, "")
                except OSError:
                    pass


class ListenerChecker(QObject):
    """Verifie periodiquement en SSH si une ecoute est ouverte sur le
    loopback de chaque host (un process qui enregistre Loopback,1,0).
    Tout est non bloquant : un ssh par host, ramasse par un timer."""

    result = pyqtSignal(str, bool)  # host, ecoute active

    INTERVAL_MS = 30000

    def __init__(self, hosts):
        super().__init__()
        self.hosts = hosts
        self.pending = {}  # host -> Popen
        self.collect_timer = QTimer(self)
        self.collect_timer.timeout.connect(self._collect)
        self.collect_timer.start(500)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(self.INTERVAL_MS)
        self.refresh()

    def refresh(self):
        for host in self.hosts:
            if host in self.pending:
                continue
            try:
                self.pending[host] = subprocess.Popen(
                    ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                     host, LISTEN_CMD],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL)
            except OSError:
                self.result.emit(host, False)

    def _collect(self):
        for host, proc in list(self.pending.items()):
            if proc.poll() is None:
                continue
            del self.pending[host]
            out = proc.stdout.read() if proc.stdout else b""
            self.result.emit(host, proc.returncode == 0 and b"L" in out)


class ToggleSwitch(QCheckBox):
    """QCheckBox peinte en forme d'interrupteur."""

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(44, 24)

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        track = QColor(GREEN) if self.isChecked() else QColor(GRAY)
        if not self.isEnabled():
            track = QColor("#c0c0c0")
        w, h = 44, 24
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, w, h), h / 2, h / 2)
        p.setBrush(QColor("#ffffff"))
        x = w - h + 2 if self.isChecked() else 2
        p.drawEllipse(QRectF(x, 2, h - 4, h - 4))


class Voyant(QLabel):
    """Petit rond de couleur (vert = transmission, gris = coupee)."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(14, 14)
        self.set_on(True)

    def set_on(self, on):
        color = GREEN if on else GRAY
        self.setStyleSheet("border-radius: 7px; background: %s;" % color)


class StatusDot(QLabel):
    """Pastille devant le nom du VPS : vert = une ecoute tourne sur son
    loopback, rouge = pas d'ecoute (ou host injoignable), gris = inconnu."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(10, 10)
        self.set_state(None)

    def set_state(self, ok):
        color = GRAY if ok is None else (GREEN if ok else RED)
        self.setStyleSheet("border-radius: 5px; background: %s;" % color)
        label = "inconnue" if ok is None else ("active" if ok else "absente")
        self.setToolTip("écoute distante : " + label)


class HostRow(QWidget):
    def __init__(self, host, toggle_cb):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        self.dot = StatusDot()
        layout.addWidget(self.dot)
        name = QLabel(host)
        name.setMinimumWidth(160)
        self.switch = ToggleSwitch()
        self.status = QLabel("inactif")
        self.status.setStyleSheet("color: %s;" % GRAY)
        layout.addWidget(name)
        layout.addWidget(self.switch)
        layout.addWidget(self.status, 1)
        self.switch.toggled.connect(lambda on: toggle_cb(host, on))

    def set_checked(self, checked):
        self.switch.blockSignals(True)
        self.switch.setChecked(checked)
        self.switch.blockSignals(False)

    def set_status(self, text, color):
        self.status.setText(text)
        self.status.setStyleSheet("color: %s;" % color)


class MainWindow(QWidget):
    def __init__(self, hosts, toggle_cb, master_cb, buffer_cb):
        super().__init__()
        self.buffer_cb = buffer_cb
        self.setWindowTitle("VoicePipe")
        layout = QVBoxLayout(self)

        master = QHBoxLayout()
        master.setContentsMargins(8, 2, 8, 6)
        self.voyant = Voyant()
        label = QLabel("Transmission")
        label.setStyleSheet("font-weight: bold;")
        self.master_switch = ToggleSwitch()
        self.master_switch.setChecked(True)
        self.master_switch.toggled.connect(master_cb)
        master.addWidget(self.voyant)
        master.addWidget(label)
        master.addStretch(1)
        master.addWidget(self.master_switch)
        layout.addLayout(master)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self.rows = {}
        if not hosts:
            layout.addWidget(QLabel("Aucun host avec clé trouvé dans ~/.ssh/config"))
        for host in hosts:
            row = HostRow(host, toggle_cb)
            self.rows[host] = row
            layout.addWidget(row)
        layout.addStretch(1)

        # slider du tampon ALSA, en bas : plus haut = moins de coupures,
        # plus de latence ; applique aux streams en cours et suivants
        buf = QHBoxLayout()
        buf.setContentsMargins(8, 6, 8, 2)
        self.buffer_label = QLabel()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(BUFFER_MIN_MS, BUFFER_MAX_MS)
        self.slider.setValue(BUFFER_DEFAULT_MS)
        self.slider.setSingleStep(10)
        self.slider.setPageStep(20)
        self.slider.setToolTip(
            "Tampon audio : plus haut = moins de micro-coupures,\n"
            "plus de latence. Les streams en cours sont relancés.")
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.slider.sliderReleased.connect(
            lambda: self.buffer_cb(self.slider.value()))
        buf.addWidget(QLabel("Tampon"))
        buf.addWidget(self.slider, 1)
        buf.addWidget(self.buffer_label)
        layout.addLayout(buf)
        self._on_slider_changed(self.slider.value())

    def _on_slider_changed(self, value):
        self.buffer_label.setText("%d ms" % value)
        # au clavier il n'y a pas de sliderReleased : applique directement
        if not self.slider.isSliderDown():
            self.buffer_cb(value)

    def set_voyant(self, on):
        self.voyant.set_on(on)
        self.master_switch.blockSignals(True)
        self.master_switch.setChecked(on)
        self.master_switch.blockSignals(False)

    def closeEvent(self, event):
        # la fenetre se cache, l'app vit dans le tray
        event.ignore()
        self.hide()


class VoiceTrayApp:
    def __init__(self, app):
        self.app = app
        self.hosts = discover_hosts()
        self.manager = StreamManager()
        self.desired = set()       # hosts dont l'interrupteur est ON
        self.transmitting = True   # etat du voyant / interrupteur maitre
        self.restart_pending = set()  # a relancer des que leur arret est acte

        self.window = MainWindow(self.hosts, self.toggle_host,
                                 self.set_transmitting, self.set_buffer)

        self.checker = ListenerChecker(self.hosts)
        self.checker.result.connect(self._on_listener_result)

        self.icon_on = self._load_icon("voicepipe-on.svg")
        self.icon_idle = self._load_icon("voicepipe-idle.svg")
        self.icon_off = self._load_icon("voicepipe-off.svg")
        self.window.setWindowIcon(self.icon_on)

        self.tray = QSystemTrayIcon(self.icon_idle)
        self.menu = QMenu()
        self.master_action = self.menu.addAction("Transmission")
        self.master_action.setCheckable(True)
        self.master_action.setChecked(True)
        self.master_action.toggled.connect(self.set_transmitting)
        self.menu.addSeparator()
        self.actions = {}
        for host in self.hosts:
            act = self.menu.addAction(host)
            act.setCheckable(True)
            act.toggled.connect(lambda on, h=host: self.toggle_host(h, on))
            self.actions[host] = act
        self.menu.addSeparator()
        self.menu.addAction("Ouvrir la fenêtre", self._show_window)
        self.menu.addAction("Quitter", self._quit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

        self.manager.state_changed.connect(self._on_state_changed)
        self._update_tray()

    @staticmethod
    def _load_icon(filename):
        # pre-rend le SVG en pixmaps : une QIcon purement SVG arrive
        # transparente dans le tray Plasma (transfert DBus sans tailles)
        src = QIcon(os.path.join(ICON_DIR, filename))
        icon = QIcon()
        for size in (16, 22, 24, 32, 48, 64):
            icon.addPixmap(src.pixmap(size, size))
        return icon

    # --- logique d'etat -----------------------------------------------------

    def toggle_host(self, host, on):
        if on:
            self.desired.add(host)
            if self.transmitting:
                self.manager.start(host)
            else:
                self._set_host_ui(host, True, "suspendu", ORANGE)
        else:
            self.desired.discard(host)
            if self.manager.is_running(host):
                self.manager.stop(host)
            else:
                self._set_host_ui(host, False, "inactif", GRAY)
        self._update_tray()

    def set_buffer(self, ms):
        if ms == self.manager.buffer_ms:
            return
        self.manager.buffer_ms = ms
        # relance les streams en cours pour appliquer le nouveau tampon
        for host in list(self.manager.procs):
            self.restart_pending.add(host)
            self.manager.stop(host)

    def _on_listener_result(self, host, listening):
        row = self.window.rows.get(host)
        if row:
            row.dot.set_state(listening)

    def set_transmitting(self, on):
        self.transmitting = on
        self.window.set_voyant(on)
        self.master_action.blockSignals(True)
        self.master_action.setChecked(on)
        self.master_action.blockSignals(False)
        if on:
            for host in sorted(self.desired):
                self.manager.start(host)
        else:
            self.manager.stop_all()
            # les interrupteurs restent tels quels, seuls les streams tombent
            for host in sorted(self.desired):
                if not self.manager.is_running(host):
                    self._set_host_ui(host, True, "suspendu", ORANGE)
        self._update_tray()

    def _on_state_changed(self, host, state, message):
        if state == STARTING:
            self._set_host_ui(host, True, "connexion...", ORANGE)
        elif state == ON:
            self._set_host_ui(host, True, "actif", GREEN)
        elif state == ERROR:
            self.desired.discard(host)
            self.restart_pending.discard(host)
            self._set_host_ui(host, False, "erreur : " + message, RED)
            self.tray.showMessage("VoicePipe — " + host, message,
                                  QSystemTrayIcon.Warning, 8000)
        else:  # OFF
            if host in self.restart_pending:
                self.restart_pending.discard(host)
                if self.transmitting and host in self.desired:
                    # arret demande par set_buffer : repart aussitot
                    self.manager.start(host)
                    self._update_tray()
                    return
            if host in self.desired and not self.transmitting:
                self._set_host_ui(host, True, "suspendu", ORANGE)
            else:
                self._set_host_ui(host, host in self.desired, "inactif", GRAY)
        self._update_tray()

    # --- helpers UI ----------------------------------------------------------

    def _set_host_ui(self, host, checked, text, color):
        row = self.window.rows.get(host)
        if row:
            row.set_checked(checked)
            row.set_status(text, color)
        act = self.actions.get(host)
        if act:
            act.blockSignals(True)
            act.setChecked(checked)
            act.blockSignals(False)

    def _update_tray(self):
        # couleurs forcees : vert = transmission active, orange = coupee
        if not self.transmitting:
            self.tray.setIcon(self.icon_off)
            self.tray.setToolTip("VoicePipe — transmission coupée")
        else:
            self.tray.setIcon(self.icon_on)
            if self.manager.procs:
                self.tray.setToolTip(
                    "VoicePipe — actif : " + ", ".join(sorted(self.manager.procs)))
            else:
                self.tray.setToolTip("VoicePipe — transmission prête, aucun stream")

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.window.isVisible():
                self.window.hide()
            else:
                self._show_window()

    def _show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _quit(self):
        self.manager.stop_all()
        # laisse une seconde aux SIGTERM avant de sortir
        QTimer.singleShot(1000, self.app.quit)


def reap_orphans():
    """Tue les pipelines voicepipe.sh survivants d'une instance precedente
    (app tuee sans passer par Quitter : les streams vivent dans leurs
    propres sessions et continuent d'emettre)."""
    try:
        out = subprocess.run(["pgrep", "-f", "voicepipe.sh"],
                             capture_output=True, text=True).stdout
    except OSError:
        return
    for token in out.split():
        try:
            os.killpg(os.getpgid(int(token)), signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass


def main():
    lock = QLockFile(os.path.join("/tmp", "voicetray-%d.lock" % os.getuid()))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        print("voicetray: deja lance", file=sys.stderr)
        return 1

    # le verrou garantit qu'aucune autre instance ne tourne : tout
    # voicepipe.sh restant est un orphelin a purger
    reap_orphans()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("voicetray: pas de zone de notification disponible", file=sys.stderr)

    vt = VoiceTrayApp(app)
    vt._show_window()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

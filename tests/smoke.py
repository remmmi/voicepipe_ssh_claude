# Test de fumee multi-plateforme : decouverte des hosts, cycle
# start -> actif -> transmission coupee -> retablie -> stop, avec de
# faux moteurs (aucun ssh ni micro reel). Lance par la CI sur
# ubuntu / macos / windows en QT_QPA_PLATFORM=offscreen.
import importlib.util
import os
import stat
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

tmp = tempfile.mkdtemp()
sshdir = os.path.join(tmp, ".ssh")
os.makedirs(sshdir)
with open(os.path.join(sshdir, "config"), "w") as f:
    f.write("Host alpha\n  IdentityFile ~/.ssh/k\n"
            "Host beta\n  IdentityFile ~/.ssh/k\n"
            "Host github.com\n  IdentityFile ~/.ssh/k\n"
            "Host bad*\n  IdentityFile ~/.ssh/k\n")
os.environ["HOME"] = tmp
os.environ["USERPROFILE"] = tmp

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "vt", os.path.join(root, "client", "voxtunnel-tray.py"))
vt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vt)

hosts = vt.discover_hosts()
assert hosts == ["alpha", "beta"], "decouverte: %r" % hosts

SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]
if vt.IS_LINUX:
    engine = os.path.join(tmp, "fake-engine.sh")
    with open(engine, "w") as f:
        f.write("#!/bin/sh\necho preflight\necho Streaming\nsleep 60\n")
    os.chmod(engine, os.stat(engine).st_mode | stat.S_IEXEC)
    vt.VOICEPIPE = engine
else:
    vt.capture_cmd = lambda: SLEEPER
    vt.ssh_play_cmd = lambda host, ms: SLEEPER

from PyQt5.QtCore import QTimer            # noqa: E402
from PyQt5.QtWidgets import QApplication   # noqa: E402

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
ui = vt.VoiceTrayApp(app)

# pas de sondes ssh reelles pendant le test
ui.checker.refresh_timer.stop()
ui.checker.fast_timer.stop()
ui.checker.collect_timer.stop()
for p in ui.checker.pending.values():
    p.kill()
ui.checker.pending.clear()

results = []


def check(name, ok):
    results.append((name, bool(ok)))


QTimer.singleShot(300, lambda: ui.window.rows["alpha"].switch.setChecked(True))
QTimer.singleShot(4500, lambda: check("stream lance", "alpha" in ui.manager.procs))
QTimer.singleShot(4600, lambda: check(
    "statut actif", ui.window.rows["alpha"].status.text() == "actif"))
QTimer.singleShot(5000, lambda: ui.window.master_switch.setChecked(False))
QTimer.singleShot(8000, lambda: check("coupure: plus de stream", not ui.manager.procs))
QTimer.singleShot(8100, lambda: check(
    "coupure: interrupteur intact", ui.window.rows["alpha"].switch.isChecked()))
QTimer.singleShot(8500, lambda: ui.window.master_switch.setChecked(True))
QTimer.singleShot(10500, lambda: check("retablissement", "alpha" in ui.manager.procs))
QTimer.singleShot(11000, ui.manager.stop_all)
QTimer.singleShot(13500, lambda: check("arret final", not ui.manager.procs))
QTimer.singleShot(14000, app.quit)
QTimer.singleShot(30000, lambda: sys.exit(2))  # garde-fou

app.exec_()

for name, ok in results:
    print("%-30s %s" % (name, "ok" if ok else "ECHEC"))
failed = [n for n, ok in results if not ok]
if failed or len(results) != 6:
    print("SMOKE FAILED:", failed or "resultats incomplets")
    sys.exit(1)
print("SMOKE OK (%s)" % sys.platform)

#!/usr/bin/env bash
# Injects CHANGELOG.tsv into the changelog section of both website pages
# (docs/index.html in English, docs/fr/index.html in French), between the
# changelog:start / changelog:end markers. Called by build-deb.sh.
set -euo pipefail
cd "$(dirname "$0")"

python3 - <<'EOF'
import re

rows = []
for line in open("CHANGELOG.tsv"):
    line = line.rstrip("\n")
    if line.strip():
        rows.append(line.split("\t"))

for path, col in (("docs/index.html", 2), ("docs/fr/index.html", 3)):
    items = "\n".join(
        '    <li><b>v%s</b> <span class="d">%s</span> — %s</li>' % (r[0], r[1], r[col])
        for r in rows)
    s = open(path).read()
    s, n = re.subn(
        r"(<!-- changelog:start -->).*?(<!-- changelog:end -->)",
        lambda m: m.group(1) + "\n" + items + "\n    " + m.group(2),
        s, flags=re.S)
    if n != 1:
        raise SystemExit("markers not found in " + path)
    open(path, "w").write(s)
    print("changelog: %s (%d entrees)" % (path, len(rows)))
EOF

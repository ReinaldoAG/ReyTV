#!/usr/bin/env bash
# Comprobaciones de estructura antes de descargar los GB de una ISO.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

bash -n "$ROOT/iso/build.sh" \
  "$ROOT/iso/files/usr/local/bin/reytv-system-update" \
  "$ROOT/iso/files/usr/local/bin/reytv-install-chrome" \
  "$ROOT/linux/reytv-launch" \
  "$ROOT/linux/reytv-update" \
  "$ROOT/linux/reytv-rollback"

test -s "$ROOT/index.html"
test -s "$ROOT/iso/packages.list.chroot"
test -s "$ROOT/iso/files/etc/skel/.config/autostart/reytv.desktop"
test -s "$ROOT/iso/files/etc/apt/apt.conf.d/20auto-upgrades"
grep -Fq -- '--debian-installer live' "$ROOT/iso/build.sh"
grep -Fq -- '--binary-image iso-hybrid' "$ROOT/iso/build.sh"
grep -Fq -- 'unattended-upgrades' "$ROOT/iso/packages.list.chroot"
grep -Fq -- 'apt-get full-upgrade' "$ROOT/iso/files/usr/local/bin/reytv-system-update"
echo 'Estructura de ISO y scripts: OK.'

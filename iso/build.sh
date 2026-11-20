#!/usr/bin/env bash
# Genera una ISO live + instalador Debian que contiene ReyTV.
# Debe ejecutarse como root en un anfitrión Debian/Ubuntu con live-build.
# No escribe imágenes en dispositivos ni modifica el firmware del Chromebox.
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(<"$PROJECT_ROOT/iso/VERSION")"
BUILD_DIR="${1:-$PROJECT_ROOT/.build-iso}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo 'Ejecuta con sudo: sudo bash iso/build.sh [directorio-vacio]' >&2
  exit 1
fi
for requirement in lb xorriso mksquashfs debootstrap; do
  command -v "$requirement" >/dev/null 2>&1 || {
    echo "Falta $requirement. Instala live-build, xorriso, squashfs-tools y debootstrap." >&2
    exit 1
  }
done
[[ -f "$PROJECT_ROOT/index.html" ]] || { echo 'Falta index.html' >&2; exit 1; }
[[ -d "$PROJECT_ROOT/iso/files" ]] || { echo 'Falta iso/files' >&2; exit 1; }

mkdir -p -- "$BUILD_DIR"
BUILD_DIR="$(cd -- "$BUILD_DIR" && pwd)"
if [[ -e "$BUILD_DIR/config" || -e "$BUILD_DIR/chroot" ]]; then
  echo "El directorio $BUILD_DIR ya tiene una compilación. Utiliza uno vacío." >&2
  exit 1
fi

cd -- "$BUILD_DIR"
lb config \
  --mode debian \
  --distribution trixie \
  --architecture amd64 \
  --binary-image iso-hybrid \
  --debian-installer live \
  --chroot-squashfs-compression-type zstd \
  --chroot-squashfs-compression-level 3 \
  --archive-areas 'main contrib non-free-firmware' \
  --image-name 'reytv' \
  --iso-application "ReyTV $VERSION" \
  --iso-volume 'REYTV' \
  --bootappend-live 'boot=live components locales=es_ES.UTF-8 keyboard-layouts=latam'

# config/includes.chroot entra en el sistema en vivo y en el sistema INSTALADO
# porque debian-installer live copia el squashfs del medio de instalación.
install -d -m 0755 config/package-lists config/includes.chroot/usr/local/bin \
  config/includes.chroot/usr/local/share/reytv \
  config/includes.chroot/etc/skel/.config/systemd/user
install -m 0644 "$PROJECT_ROOT/iso/packages.list.chroot" config/package-lists/reytv.list.chroot
cp -a -- "$PROJECT_ROOT/iso/files/." config/includes.chroot/
install -m 0644 "$PROJECT_ROOT/index.html" config/includes.chroot/usr/local/share/reytv/index.html
install -m 0755 "$PROJECT_ROOT/linux/reytv-launch" config/includes.chroot/usr/local/bin/reytv
install -m 0644 "$PROJECT_ROOT/linux/reytv-server.py" config/includes.chroot/usr/local/bin/reytv-server.py
install -m 0755 "$PROJECT_ROOT/linux/reytv-update" config/includes.chroot/usr/local/bin/reytv-update
install -m 0755 "$PROJECT_ROOT/linux/reytv-rollback" config/includes.chroot/usr/local/bin/reytv-rollback
install -d -m 0755 config/includes.chroot/etc/skel/.local/bin
install -m 0755 "$PROJECT_ROOT/linux/reytv-update" config/includes.chroot/etc/skel/.local/bin/reytv-update
install -m 0755 "$PROJECT_ROOT/linux/reytv-rollback" config/includes.chroot/etc/skel/.local/bin/reytv-rollback
install -m 0755 "$PROJECT_ROOT/iso/files/usr/local/bin/reytv-system-update" config/includes.chroot/usr/local/bin/reytv-system-update
install -m 0755 "$PROJECT_ROOT/iso/files/usr/local/bin/reytv-install-chrome" config/includes.chroot/usr/local/bin/reytv-install-chrome
install -m 0644 "$PROJECT_ROOT/linux/systemd/reytv-update.service" config/includes.chroot/etc/skel/.config/systemd/user/reytv-update.service
install -m 0644 "$PROJECT_ROOT/linux/systemd/reytv-update.timer" config/includes.chroot/etc/skel/.config/systemd/user/reytv-update.timer
install -m 0644 "$PROJECT_ROOT/iso/VERSION" config/includes.chroot/usr/local/share/reytv/VERSION

lb build

ISO_FILE="$BUILD_DIR/reytv-amd64.hybrid.iso"
if [[ ! -s "$ISO_FILE" ]]; then
  echo "No se generó $ISO_FILE" >&2
  exit 1
fi
# El checksum debe contener el nombre RELATIVO del archivo, porque GitHub
# Actions ve /build dentro de Docker y otra ruta fuera del contenedor.
cd -- "$BUILD_DIR"
sha256sum reytv-amd64.hybrid.iso > reytv-amd64.hybrid.iso.sha256
echo "ISO creada: $ISO_FILE"
echo "SHA256: $(<reytv-amd64.hybrid.iso.sha256)"

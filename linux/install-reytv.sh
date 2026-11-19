#!/usr/bin/env bash
# Instalador NO destructivo: copia la interfaz e instala el arranque automático
# en la sesión del usuario actual. NO formatea discos ni modifica el firmware.
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
  echo 'Este instalador funciona únicamente en Linux.' >&2
  exit 1
fi
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$ROOT/index.html" ]] || { echo 'Falta index.html' >&2; exit 1; }

TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/reytv"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$TARGET" "$BIN_DIR" "$AUTOSTART_DIR" "$SYSTEMD_DIR"
install -m 0644 "$ROOT/index.html" "$TARGET/index.html"
install -m 0755 "$ROOT/linux/reytv-launch" "$BIN_DIR/reytv"
install -m 0755 "$ROOT/linux/reytv-update" "$BIN_DIR/reytv-update"
install -m 0755 "$ROOT/linux/reytv-rollback" "$BIN_DIR/reytv-rollback"
install -m 0644 "$ROOT/linux/systemd/reytv-update.service" "$SYSTEMD_DIR/reytv-update.service"
install -m 0644 "$ROOT/linux/systemd/reytv-update.timer" "$SYSTEMD_DIR/reytv-update.timer"

# Espacios en la ruta HOME son poco habituales; escaparlos conforme al formato
# Desktop Entry para que el comando Exec no cambie de argumentos.
EXEC_PATH="${BIN_DIR//\\/\\\\}/reytv"
EXEC_PATH="${EXEC_PATH// /\\s}"
{
  printf '%s\n' '[Desktop Entry]'
  printf '%s\n' 'Type=Application'
  printf '%s\n' 'Version=1.0'
  printf '%s\n' 'Name=ReyTV'
  printf 'Exec=%s\n' "$EXEC_PATH"
  printf '%s\n' 'Terminal=false'
  printf '%s\n' 'X-GNOME-Autostart-enabled=true'
  printf '%s\n' 'Comment=Interfaz de entretenimiento para Chromebox'
} > "$AUTOSTART_DIR/reytv.desktop"

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload 2>/dev/null || true
fi

printf '\nReyTV instalada para %s.\n' "$(id -un)"
printf 'Para abrirla ahora: %s\n' "$BIN_DIR/reytv"
printf 'Se abrirá también al iniciar sesión en Linux.\n'
printf 'Para desactivar el arranque automático, borra solo: %s\n' "$AUTOSTART_DIR/reytv.desktop"
printf 'Actualizaciones disponibles tras configurar el acceso SSH: %s\n' "$BIN_DIR/reytv-update"
printf 'Para habilitar la revisión diaria: systemctl --user enable --now reytv-update.timer\n'
printf 'Para volver a la versión anterior: %s\n' "$BIN_DIR/reytv-rollback"
printf 'Esto NO ha modificado particiones, Android, firmware ni datos ajenos a ReyTV.\n'

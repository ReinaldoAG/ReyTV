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

TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/franche-tv"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$TARGET" "$BIN_DIR" "$AUTOSTART_DIR"
install -m 0644 "$ROOT/index.html" "$TARGET/index.html"
install -m 0755 "$ROOT/linux/franche-tv-launch" "$BIN_DIR/franche-tv"

# Espacios en la ruta HOME son poco habituales; escaparlos conforme al formato
# Desktop Entry para que el comando Exec no cambie de argumentos.
EXEC_PATH="${BIN_DIR//\\/\\\\}/franche-tv"
EXEC_PATH="${EXEC_PATH// /\\s}"
{
  printf '%s\n' '[Desktop Entry]'
  printf '%s\n' 'Type=Application'
  printf '%s\n' 'Version=1.0'
  printf '%s\n' 'Name=Franche TV'
  printf 'Exec=%s\n' "$EXEC_PATH"
  printf '%s\n' 'Terminal=false'
  printf '%s\n' 'X-GNOME-Autostart-enabled=true'
  printf '%s\n' 'Comment=Interfaz de entretenimiento para Chromebox'
} > "$AUTOSTART_DIR/franche-tv.desktop"

printf '\nFranche TV instalada para %s.\n' "$(id -un)"
printf 'Para abrirla ahora: %s\n' "$BIN_DIR/franche-tv"
printf 'Se abrirá también al iniciar sesión en Linux.\n'
printf 'Para desactivar el arranque automático, borra solo: %s\n' "$AUTOSTART_DIR/franche-tv.desktop"
printf 'Esto NO ha modificado particiones, Android, firmware ni datos ajenos a Franche TV.\n'

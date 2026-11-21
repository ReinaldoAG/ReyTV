#!/usr/bin/env bash
# Habilita las actualizaciones gráficas en una instalación existente de ReyTV.
# Todo se instala en la cuenta actual: NO usa sudo ni toca particiones.
set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  echo 'Abre tu sesión normal de ReyTV; no ejecutes este instalador como root.' >&2
  exit 1
fi
for program in curl python3 git; do
  command -v "$program" >/dev/null || {
    echo "Falta $program en el dispositivo." >&2
    exit 1
  }
done

SOURCE="https://raw.githubusercontent.com/ReinaldoAG/ReyTV/main"
TEMP="$(mktemp -d)"
trap 'rm -rf -- "$TEMP"' EXIT

echo 'Descargando componentes oficiales de ReyTV por HTTPS...'
for file in linux/reytv-launch linux/reytv-update linux/reytv-rollback \
            linux/reytv-server.py linux/reytv-native.py linux/systemd/reytv-update.service \
            linux/systemd/reytv-update.timer index.html; do
  mkdir -p -- "$TEMP/$(dirname -- "$file")"
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    "$SOURCE/$file" --output "$TEMP/$file"
done

bash -n "$TEMP/linux/reytv-launch" "$TEMP/linux/reytv-update" "$TEMP/linux/reytv-rollback"
python3 -m py_compile "$TEMP/linux/reytv-server.py" "$TEMP/linux/reytv-native.py"
if ! grep -Fq '<title>ReyTV' "$TEMP/index.html" || ! grep -Fq '</html>' "$TEMP/index.html"; then
  echo 'El menú descargado no parece válido. No se ha instalado nada.' >&2
  exit 1
fi

BIN="$HOME/.local/bin"
APP="${XDG_DATA_HOME:-$HOME/.local/share}/reytv"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/reytv"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
SERVICES="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
install -d -m 0755 "$BIN" "$APP" "$STATE" "$AUTOSTART" "$SERVICES"

if [[ -f "$APP/index.html" ]] && ! cmp -s "$APP/index.html" "$TEMP/index.html"; then
  cp -p -- "$APP/index.html" "$STATE/previous-index.html"
  if [[ -f "$STATE/current.sha" ]]; then
    cp -p -- "$STATE/current.sha" "$STATE/previous.sha"
  else
    printf '%s\n' 'initial-install' > "$STATE/previous.sha"
  fi
fi

install -m 0755 "$TEMP/linux/reytv-launch" "$BIN/reytv"
install -m 0755 "$TEMP/linux/reytv-update" "$BIN/reytv-update"
install -m 0755 "$TEMP/linux/reytv-rollback" "$BIN/reytv-rollback"
install -m 0644 "$TEMP/linux/reytv-server.py" "$BIN/reytv-server.py"
install -m 0644 "$TEMP/linux/reytv-native.py" "$BIN/reytv-native.py"
install -m 0644 "$TEMP/index.html" "$APP/index.html"
install -m 0644 "$TEMP/linux/systemd/reytv-update.service" "$SERVICES/reytv-update.service"
install -m 0644 "$TEMP/linux/systemd/reytv-update.timer" "$SERVICES/reytv-update.timer"

# Esta entrada de usuario sustituye a la que venía preinstalada en la ISO.
printf '[Desktop Entry]\nType=Application\nName=ReyTV\nExec=%s/reytv\nTerminal=false\nX-GNOME-Autostart-enabled=true\n' \
  "$BIN" > "$AUTOSTART/reytv.desktop"

# Registrar el commit que acabamos de instalar evita detectar la misma versión
# como actualización pendiente en la primera comprobación.
if HEAD_SHA="$(git ls-remote 'https://github.com/ReinaldoAG/ReyTV.git' refs/heads/main 2>/dev/null)"; then
  HEAD_SHA="${HEAD_SHA%%[[:space:]]*}"
  if [[ "$HEAD_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    printf '%s\n' "$HEAD_SHA" > "$STATE/current.sha"
  fi
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload || true
  systemctl --user enable --now reytv-update.timer || true
fi

echo
echo 'Actualizador instalado. Reinicia el Chromebox una vez para activarlo.'
echo 'Después abre ReyTV > Ajustes > Actualizaciones.'

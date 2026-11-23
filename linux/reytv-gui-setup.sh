#!/usr/bin/env bash
# Instalador gráfico de arranque; ejecutado desde un acceso .desktop.
# NO necesita sudo. Instala el actualizador completo y conserva favoritos.
set -euo pipefail
[[ "$(id -u)" -ne 0 ]] || { echo 'Ejecuta desde tu usuario ReyTV, no como root.'; exit 1; }
for cmd in git bash curl python3; do
  command -v "$cmd" >/dev/null || { echo "Falta $cmd"; exit 1; }
done
echo 'ReyTV - Instalador de actualizaciones'
echo 'Descargando los componentes oficiales...'
temp="$(mktemp -d)"
trap 'rm -rf -- "$temp"' EXIT
git clone --quiet --depth 1 -b main https://github.com/ReinaldoAG/ReyTV.git "$temp/reytv"
bash -n "$temp/reytv/linux/reytv-update" "$temp/reytv/linux/reytv-rollback"
python3 -m py_compile "$temp/reytv/linux/reytv-server.py" "$temp/reytv/linux/reytv-native.py"
bash "$temp/reytv/linux/reytv-update" --force
# Este archivo es la única parte instalada con permisos de administrador.
# Las actualizaciones normales de la interfaz siguen sin sudo.
session_src="$temp/reytv/linux/reytv-tv-session"
session_dst="/usr/local/bin/reytv-tv-session"
if [[ -x "$session_dst" ]] && ! cmp -s "$session_src" "$session_dst"; then
  bash -n "$session_src"
  echo
  echo 'Ajustes del motor de Chrome: ocultar scrollbars y cerrar con seguridad.'
  echo 'Es necesario actualizar una vez el lanzador del modo TV.'
  echo 'Se solicitará la contraseña local de administrador (sudo).'
  if ! command -v sudo >/dev/null; then
    echo 'Falta sudo; solo se actualizó la parte del usuario.' >&2
    exit 3
  fi
  if ! sudo -v; then
    echo 'Sin permiso de administrador. El sistema TV quedó sin estos ajustes.' >&2
    exit 3
  fi
  state="${XDG_STATE_HOME:-$HOME/.local/state}/reytv"
  mkdir -p "$state"
  if [[ ! -f "$state/tv-session.before-051" ]]; then
    cp -p -- "$session_dst" "$state/tv-session.before-051"
  fi
  sudo install -m 0755 -- "$session_src" "$session_dst"
  cmp -s "$session_src" "$session_dst" || {
    echo 'No se pudo confirmar el lanzador TV instalado.' >&2
    exit 4
  }
  echo 'Lanzador del modo TV actualizado correctamente.'
fi
echo
echo 'Listo. Reinicia el Chromebox para activar todos los componentes.'
echo 'A partir de ahora: ReyTV > Ajustes > Actualizaciones > Actualizar ahora.'
echo 'No se han borrado cookies, contraseñas, favoritos ni otros perfiles del navegador.'

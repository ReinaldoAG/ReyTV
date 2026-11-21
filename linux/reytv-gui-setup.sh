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
echo
echo 'Listo. Reinicia el Chromebox para activar todos los componentes.'
echo 'A partir de ahora: ReyTV > Ajustes > Actualizaciones > Actualizar ahora.'
echo 'No se ha cambiado ninguna contraseña, ni Debian, ni el firmware.'

#!/usr/bin/env bash
# Transición desde ReyTV 0.2.2; no formatea, no borra LXQt, ni cambia firmware.
set -euo pipefail
[ "$(id -u)" != 0 ] || { echo 'Ejecuta como usuario normal, no con sudo.'; exit 1; }
user=$(id -un)
[[ "$user" =~ ^[a-z_][a-z0-9_-]*$ ]] || exit 1
for cmd in git curl python3 openbox startlxqt xset xsetroot setsid sudo; do
  command -v "$cmd" >/dev/null || { echo "Falta $cmd"; exit 1; }
done
[ -x /usr/bin/sddm ] && [ -f /usr/share/xsessions/lxqt.desktop ] || { echo 'No se encontró SDDM y la sesión LXQt de recuperación.'; exit 1; }
[ -s "$HOME/.local/bin/reytv-server.py" ] || { echo 'Primero instala el actualizador de ReyTV 0.2.2.'; exit 1; }
data=$(printenv XDG_DATA_HOME || true); [ -n "$data" ] || data="$HOME/.local/share"
state=$(printenv XDG_STATE_HOME || true); [ -n "$state" ] || state="$HOME/.local/state"
app="$data/reytv"; state="$state/reytv"
[ -s "$app/index.html" ] || exit 1
temp=$(mktemp -d)
trap 'rm -rf -- "$temp"' EXIT
echo 'Descargando una revisión de ReyTV...'
git clone --quiet --depth=1 --branch main https://github.com/ReinaldoAG/ReyTV.git "$temp/src"
src="$temp/src"
revision=$(git -C "$src" rev-parse HEAD)
for script in reytv-tv-session reytv-tv-disable; do bash -n "$src/linux/$script"; done
python3 -c 'import sys,xml.etree.ElementTree as E; E.parse(sys.argv[1])' "$src/linux/openbox-tv.xml"
grep -Eq 'ReyTV · 0\.3\.[0-9]+' "$src/index.html"
grep -Fq 'Actualizaciones de ReyTV' "$src/index.html"
sudo -v
if ! command -v unclutter >/dev/null; then
  sudo apt-get update --error-on=any
  sudo apt-get install --no-install-recommends unclutter
fi
command -v unclutter >/dev/null
# Preparar la configuración sin alterar las demás secciones que tenga SDDM.
if sudo test -f /etc/sddm.conf; then sudo cat /etc/sddm.conf > "$temp/old.conf"; else : > "$temp/old.conf"; fi
python3 - "$temp/old.conf" "$temp/new.conf" "$user" <<'PY'
import pathlib, re, sys
old, new, user = sys.argv[1:]
lines = pathlib.Path(old).read_text().splitlines()
out = []
in_auto = False
added = False
keys = [f"User={user}", "Session=reytv-tv.desktop", "Relogin=false"]
for line in lines:
    match = re.match(r"^\s*\[([^]]+)\]\s*$", line)
    if match:
        in_auto = match.group(1).lower() == "autologin"
        out.append(line)
        if in_auto and not added:
            out.extend(keys)
            added = True
        continue
    if in_auto and re.match(r"^\s*(User|Session|Relogin)\s*=", line, re.I):
        continue
    out.append(line)
if not added:
    out.extend(["", "[Autologin]", *keys])
pathlib.Path(new).write_text("\n".join(out) + "\n")
PY
# Instalar primero los archivos de sesión y recuperación, nunca activar a medias.
sudo install -d -m 0755 /usr/local/share/reytv-tv /usr/local/bin /usr/share/xsessions
sudo install -m 0755 "$src/linux/reytv-tv-session" /usr/local/bin/reytv-tv-session
sudo install -m 0755 "$src/linux/reytv-tv-disable" /usr/local/bin/reytv-tv-disable
sudo install -m 0644 "$src/linux/openbox-tv.xml" /usr/local/share/reytv-tv/openbox.xml
sudo install -m 0644 "$src/linux/reytv-tv.desktop" /usr/share/xsessions/reytv-tv.desktop
# Actualizar el menú del usuario conservando el perfil del navegador y los favoritos.
mkdir -p "$state"
if ! cmp -s "$src/index.html" "$app/index.html"; then
  cp -p "$app/index.html" "$state/previous-index.html"
  if [ -f "$state/current.sha" ]; then cp -p "$state/current.sha" "$state/previous.sha"; else echo initial-install > "$state/previous.sha"; fi
  localhtml=$(mktemp "$app/.tv-index.XXXXXXXX")
  install -m 0644 "$src/index.html" "$localhtml"
  mv -f "$localhtml" "$app/index.html"
fi
printf '%s\n' "$revision" > "$state/current.sha"
# El escritorio LXQt de mantenimiento no debe lanzar otra vez ReyTV.
autostart="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
mkdir -p "$autostart"
python3 - "$autostart/reytv.desktop" "$state" <<'PY'
import pathlib, sys
p, state = map(pathlib.Path, sys.argv[1:])
backup = state / "desktop-autostart.original"
if p.exists() and not backup.exists():
    backup.write_bytes(p.read_bytes())
p.write_text("[Desktop Entry]\nType=Application\nName=ReyTV\nHidden=true\n")
PY
# Respaldo de la configuración original, sin modificar el resto del sistema.
backup=/var/lib/reytv-tv
sudo install -d -m 0700 "$backup"
if ! sudo test -f "$backup/active"; then
  if sudo test -f /etc/sddm.conf; then
    sudo cp -a /etc/sddm.conf "$backup/sddm.conf.original"
    sudo touch "$backup/had-sddm-conf"
  else
    sudo rm -f "$backup/had-sddm-conf"
  fi
  sudo touch "$backup/active"
fi
# Activa la sesión solamente al final y no reinicia automáticamente.
sudo install -m 0644 "$temp/new.conf" /etc/sddm.conf
# Verificar la instalación antes de indicar que se puede apagar.
sudo test -s /etc/sddm.conf
sudo test -s /usr/share/xsessions/reytv-tv.desktop
sudo test -x /usr/local/bin/reytv-tv-session
cmp -s "$temp/new.conf" /etc/sddm.conf
sed -n '/^\[Autologin\]/,/^\[/p' /etc/sddm.conf
grep -F -- '--disable-features=Translate' /usr/local/bin/reytv-tv-session >/dev/null
sync
echo
echo 'MODO TV INSTALADO Y VERIFICADO. Apaga completamente el Chromebox y vuelve a encenderlo.'
echo 'F8: volver a Inicio. Ctrl+Alt+M: terminal (despues del arranque). Ctrl+Alt+Esc: escritorio LXQt de mantenimiento.'
echo 'Rescate: Ctrl+Alt+F3, iniciar sesión, sudo reytv-tv-disable, sudo reboot.'

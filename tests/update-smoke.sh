#!/usr/bin/env bash
# Prueba local, sin GitHub, de actualización, bloqueo tras rollback y restauración.
set -euo pipefail

PROJECT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d)"
trap 'rm -r -- "$TEST_ROOT"' EXIT

mkdir -p "$TEST_ROOT/source" "$TEST_ROOT/data/reytv" "$TEST_ROOT/cache" "$TEST_ROOT/state"
git init -q -b main "$TEST_ROOT/source"
cp "$PROJECT/index.html" "$TEST_ROOT/source/index.html"
cp "$PROJECT/index.html" "$TEST_ROOT/data/reytv/index.html"
git -C "$TEST_ROOT/source" add index.html
git -C "$TEST_ROOT/source" -c user.name='ReyTV Tests' -c user.email='tests@local.invalid' commit -qm 'Versión inicial'

export XDG_DATA_HOME="$TEST_ROOT/data"
export XDG_STATE_HOME="$TEST_ROOT/state"
export XDG_CACHE_HOME="$TEST_ROOT/cache"
export REYTV_REPO_URL="$TEST_ROOT/source"

# Primer chequeo: mismos archivos, no debe haber reemplazo.
bash "$PROJECT/linux/reytv-update"
[[ ! -f "$TEST_ROOT/state/reytv/previous-index.html" ]]

# Una actualización real crea respaldo y cambia la interfaz.
sed -i 's/ReyTV · 0\.2/ReyTV · 0.3/' "$TEST_ROOT/source/index.html"
git -C "$TEST_ROOT/source" add index.html
git -C "$TEST_ROOT/source" -c user.name='ReyTV Tests' -c user.email='tests@local.invalid' commit -qm 'Versión nueva'
bash "$PROJECT/linux/reytv-update"
rg -q 'ReyTV · 0.3' "$TEST_ROOT/data/reytv/index.html"
rg -q 'ReyTV · 0.2' "$TEST_ROOT/state/reytv/previous-index.html"

# Rollback y protección ante reinstalación de la versión revertida.
bash "$PROJECT/linux/reytv-rollback"
rg -q 'ReyTV · 0.2' "$TEST_ROOT/data/reytv/index.html"
bash "$PROJECT/linux/reytv-update"
rg -q 'ReyTV · 0.2' "$TEST_ROOT/data/reytv/index.html"

echo 'Actualización y rollback: pruebas OK.'

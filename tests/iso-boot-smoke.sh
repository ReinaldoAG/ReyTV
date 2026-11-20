#!/usr/bin/env bash
# Comprueba que una ISO de ReyTV contiene un initramfs utilizable y que
# el kernel logra pasar del entorno live al sistema instalado en el squashfs.
# No escribe en discos físicos; arranca una VM efímera con la ISO como CD.
set -euo pipefail

ISO_PATH="${1:?Uso: bash tests/iso-boot-smoke.sh imagen.iso directorio-de-logs}"
REPORT_DIR="${2:?Indica un directorio para guardar los registros}"
[[ -s "$ISO_PATH" ]] || { echo "No existe la ISO: $ISO_PATH" >&2; exit 1; }
mkdir -p -- "$REPORT_DIR"

for executable in xorriso lsinitramfs qemu-system-x86_64; do
  command -v "$executable" >/dev/null || {
    echo "Falta instalar $executable" >&2
    exit 1
  }
done

# No damos por buena una ISO por tener un sector de arranque: necesitamos
# que el kernel y su initrd existan dentro del fichero realmente publicado.
if ! xorriso -indev "$ISO_PATH" -find /live -name 'vmlinuz-*' \
  > "$REPORT_DIR/kernels.txt" 2> "$REPORT_DIR/xorriso-kernels.log"; then
  cat "$REPORT_DIR/xorriso-kernels.log" >&2
  exit 1
fi
mapfile -t kernels < "$REPORT_DIR/kernels.txt"
if [[ ${#kernels[@]} -ne 1 ]]; then
  echo "Se esperaba un único kernel Live; encontrados: ${#kernels[@]}" >&2
  exit 1
fi
# xorriso devuelve rutas con comillas simples para escaparlas como shell.
# Los nombres de kernel oficiales son seguros: quitamos esas comillas y
# validamos la ruta sin evaluarla ni ejecutar lo devuelto por xorriso.
kernel_path="${kernels[0]//\'/}"
if [[ "$kernel_path" != /live/vmlinuz-* ]]; then
  echo "Ruta de kernel Live inesperada: $kernel_path" >&2
  exit 1
fi
version="${kernel_path##*/vmlinuz-}"
initrd_path="/live/initrd.img-$version"

xorriso -osirrox on -indev "$ISO_PATH" \
  -extract "$kernel_path" "$REPORT_DIR/vmlinuz" \
  -extract "$initrd_path" "$REPORT_DIR/initrd.img" \
  > "$REPORT_DIR/xorriso-extract.log" 2>&1 || {
    cat "$REPORT_DIR/xorriso-extract.log" >&2
    exit 1
  }
test -s "$REPORT_DIR/vmlinuz"
test -s "$REPORT_DIR/initrd.img"
echo "Kernel: $kernel_path; initrd: $initrd_path"
ls -lh "$REPORT_DIR/vmlinuz" "$REPORT_DIR/initrd.img"

# Cuando falta /init, el kernel recae en la búsqueda de root= y puede dar
# exactamente el fallo 'unknown-block(0,0)' observado en el Chromebox.
lsinitramfs "$REPORT_DIR/initrd.img" > "$REPORT_DIR/initrd-contents.txt"
grep -Eq '^\.?/?init$' "$REPORT_DIR/initrd-contents.txt" || {
  echo 'FATAL: el initramfs no contiene /init' >&2
  exit 1
}
grep -Eq '^\.?/?scripts/live$' "$REPORT_DIR/initrd-contents.txt" || {
  echo 'FATAL: el initramfs no contiene scripts/live' >&2
  exit 1
}

echo 'Probando inicio de Debian Live con QEMU (sin KVM ni disco interno)...'
qemu-system-x86_64 \
  -accel tcg -m 2048 -smp 2 \
  -kernel "$REPORT_DIR/vmlinuz" \
  -initrd "$REPORT_DIR/initrd.img" \
  -append 'boot=live components console=ttyS0 loglevel=6' \
  -cdrom "$ISO_PATH" \
  -display none -monitor none \
  -serial "file:$REPORT_DIR/qemu-serial.log" \
  -no-reboot \
  > "$REPORT_DIR/qemu-errors.log" 2>&1 &
qemu_pid=$!
terminate_qemu() {
  if kill -0 "$qemu_pid" 2>/dev/null; then
    kill "$qemu_pid" 2>/dev/null || true
    wait "$qemu_pid" 2>/dev/null || true
  fi
}
trap terminate_qemu EXIT

# Esperar como máximo 3 minutos: se trata de QEMU por software en GitHub.
# No basta con el arranque del kernel; exigimos haber iniciado systemd desde
# el squashfs del sistema Live.
passed=false
for ((i=0; i<90; i++)); do
  sleep 2
  if [[ -f "$REPORT_DIR/qemu-serial.log" ]] && \
     grep -Eq 'systemd\[1\]:' "$REPORT_DIR/qemu-serial.log"; then
    passed=true
    break
  fi
  if [[ -f "$REPORT_DIR/qemu-serial.log" ]] && \
     grep -Eiq 'Kernel panic|Unable to mount root fs' "$REPORT_DIR/qemu-serial.log"; then
    echo 'FATAL: QEMU reprodujo un fallo de arranque del kernel' >&2
    break
  fi
  kill -0 "$qemu_pid" 2>/dev/null || break
done

if [[ "$passed" != true ]]; then
  echo 'FATAL: Debian Live no llegó a iniciar systemd en la VM' >&2
  tail -100 "$REPORT_DIR/qemu-serial.log" >&2 || true
  tail -40 "$REPORT_DIR/qemu-errors.log" >&2 || true
  exit 1
fi
echo 'OK: initrd completo y Debian Live inició systemd en QEMU.'

#!/usr/bin/env bash
# Diagnóstico de la ISO REAL por UEFI/OVMF -> GRUB -> kernel, sin bypass.
# QEMU usa una placa y firmware virtuales; no pretende reproducir exactamente
# el hardware GOOGLE Panther del Chromebox.
set -euo pipefail

ISO_PATH="${1:?Uso: bash tests/iso-uefi-smoke.sh ISO directorio-reportes}"
REPORT_DIR="${2:?Falta directorio de reportes}"
[[ -s "$ISO_PATH" ]] || { echo "Falta ISO: $ISO_PATH" >&2; exit 1; }
mkdir -p "$REPORT_DIR"

for executable in qemu-system-x86_64 tesseract; do
  command -v "$executable" >/dev/null || { echo "Falta $executable" >&2; exit 1; }
done
ovmf_code=/usr/share/OVMF/OVMF_CODE_4M.fd
ovmf_vars=/usr/share/OVMF/OVMF_VARS_4M.fd
test -s "$ovmf_code"
test -s "$ovmf_vars"
cp "$ovmf_vars" "$REPORT_DIR/OVMF_VARS.fd"

echo 'Iniciando ISO original con firmware OVMF/UEFI y GRUB...'
qemu-system-x86_64 \
  -accel tcg -machine pc -m 2048 -smp 2 -cpu Haswell \
  -drive "if=pflash,format=raw,readonly=on,file=$ovmf_code" \
  -drive "if=pflash,format=raw,file=$REPORT_DIR/OVMF_VARS.fd" \
  -drive "if=ide,media=cdrom,readonly=on,file=$ISO_PATH" \
  -boot d \
  -vga std -display none \
  -monitor tcp:127.0.0.1:45555,server,nowait \
  -serial "file:$REPORT_DIR/uefi-serial.log" \
  -no-reboot \
  > "$REPORT_DIR/uefi-errors.log" 2>&1 &
qemu_pid=$!
cleanup() {
  if kill -0 "$qemu_pid" 2>/dev/null; then
    kill "$qemu_pid" 2>/dev/null || true
    wait "$qemu_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Conexión al monitor de QEMU para capturar su pantalla sin interfaz gráfica.
# Abrimos una sola sesión TCP y la conservamos hasta finalizar.
monitor_connected=false
for ((attempt=0; attempt<20; attempt++)); do
  if exec 3<>/dev/tcp/127.0.0.1/45555 2>/dev/null; then
    monitor_connected=true
    break
  fi
  sleep 1
done
if [[ "$monitor_connected" != true ]]; then
  echo 'QEMU no abrió su monitor (posible error de inicio)' >&2
  tail -50 "$REPORT_DIR/uefi-errors.log" >&2 || true
  exit 1
fi

last_second=0
detected_boot=false
for second in 15 40 70 100; do
  sleep "$((second - last_second))"
  last_second="$second"
  frame="$REPORT_DIR/uefi-${second}s.ppm"
  printf 'screendump %s\n' "$frame" >&3
  for ((retry=0; retry<5; retry++)); do
    [[ -s "$frame" ]] && break
    sleep 1
  done
  if [[ ! -s "$frame" ]]; then
    echo "No se pudo capturar pantalla UEFI a los ${second}s" >&2
    tail -50 "$REPORT_DIR/uefi-errors.log" >&2 || true
    exit 1
  fi

  output="$REPORT_DIR/uefi-${second}s.txt"
  tesseract "$frame" stdout --psm 6 > "$output" 2>/dev/null || true
  echo "=== Pantalla virtual UEFI: ${second}s ==="
  sed -n '1,24p' "$output"

  if grep -Eiq 'Kernel panic|unknown.block\(0,0\)|Unable to mount root|Cannot open root device' "$output"; then
    echo 'FALLO: el arranque UEFI por GRUB reprodujo el kernel panic' >&2
    exit 1
  fi
  if grep -Eiq 'Debian GNU/Linux|ReyTV|GNU GRUB|Live system|login:' "$output"; then
    detected_boot=true
  fi
  kill -0 "$qemu_pid" 2>/dev/null || break
done

if [[ "$detected_boot" != true ]]; then
  echo 'No se pudo identificar el estado de arranque mediante OCR; revisar capturas.' >&2
  exit 1
fi
echo 'UEFI/GRUB: no se reconoció un kernel panic en las capturas OCR.'
echo 'Esta prueba NO demuestra todavía que el escritorio haya arrancado.'

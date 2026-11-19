# ReyTV — versión 0.3 (ISO instalable)

**ReyTV** transforma una computadora x86-64, como el ASUS Chromebox CN60, en un centro de entretenimiento tipo Roku controlado inicialmente con teclado. Ofrece un menú a pantalla completa para servicios **web oficiales** de YouTube, Netflix, Prime Video, Disney+, Max, Spotify, Twitch y Plex; no contiene APKs ni suplanta aplicaciones de Android.

## ISO de ReyTV — reemplaza Bliss OS sin depender de un Linux previo

La ISO personalizada se construye con **Debian 13 (trixie) + LXQt + ReyTV** mediante [Debian live-build](https://live-team.pages.debian.net/live-manual/html/live-manual/index.en.html). Incluye un escritorio live para probarla desde USB y un **instalador de Debian Live** que puede instalar la misma imagen en el disco interno. No instala Android ni ChromeOS, y **no flashea el firmware**.

### Descargar una ISO compilada

1. Entra en el repositorio privado [ReinaldoAG/ReyTV](https://github.com/ReinaldoAG/ReyTV) con tu sesión de GitHub.
2. Abre [Actions → Compilar ISO de ReyTV](https://github.com/ReinaldoAG/ReyTV/actions/workflows/build-iso.yml).
3. Escoge una ejecución **correcta** (marca verde) → **Artifacts** → descarga `ReyTV-...-amd64-ISO.zip`.
4. Descomprime el ZIP: encontrarás `reytv-amd64.hybrid.iso` y `reytv-amd64.hybrid.iso.sha256`. Comprueba su SHA256 antes de usarla.

**La ISO únicamente existe después de una compilación correcta en Actions**. No confundas el código fuente o el ZIP del repositorio con un medio de instalación. El artefacto de Actions caduca a los **30 días**, así que conserva una copia local si la necesitas más adelante. Se puede repetir la compilación con `Run workflow`.

### Cómo instalar en tu Chromebox (cuidado: este paso puede borrar Bliss OS)

1. Desde otra computadora, copia el archivo `.iso` **como imagen de disco** a un USB de 8 GB o más con una herramienta como Balena Etcher o Rufus. No copies simplemente el fichero a la memoria.
2. Conecta el pendrive al CN60 y utiliza el menú de arranque que ofrezca su firmware. **Antes hay que confirmar si el firmware actual admite arrancar desde USB con BIOS Legacy o UEFI**; no podemos confirmarlo a distancia. No modifiques el firmware por seguir esta guía.
3. Primero elige **Live** para comprobar video, Wi-Fi/Ethernet, sonido HDMI, teclado y que ReyTV se abre. La reproducción con DRM (Netflix, etc.) se debe validar en el dispositivo real.
4. Solo si todo funciona, inicia **Install** / **Graphical Install** en el menú de arranque o el instalador desde el escritorio. Selecciona el **disco interno correcto**, crea tu usuario y decide explícitamente si eliminar Bliss OS. La opción «usar todo el disco» **borra Android y sus datos**: haz copia de seguridad antes.
5. Reinicia sin USB, inicia sesión en el usuario creado y ReyTV debería abrir automáticamente. Configura la conexión a internet y prueba el navegador.

El USB no sustituye a comprobar el firmware del CN60 y **la imagen no ha sido validada aún físicamente en el dispositivo**. Para diagnóstico, conecta un teclado y un ratón convencional.

### Navegador y Netflix

La ISO incluye **Chromium y Firefox ESR** desde Debian, pero **no distribuye Google Chrome ni Widevine de terceros**. Para Netflix, si el navegador incorporado no reproduce contenido protegido, puedes instalar **Google Chrome oficial** desde el propio Chromebox, con internet y tu autorización:

```bash
sudo reytv-install-chrome
```

El script descarga el paquete `.deb` directamente desde `dl.google.com` y deja que el sistema te pida confirmación antes de instalarlo. Luego cierra y vuelve a abrir ReyTV, que priorizará Chrome. La reproducción y resolución de cada servicio dependen de sus requisitos, DRM y suscripción; no garantizamos Netflix en el CN60 hasta probarlo.

### Actualizar el sistema operativo entero **sin volver al pendrive**

**Hay dos vías de actualización**:

| Componente | Mecanismo | Qué cambia |
| --- | --- | --- |
| Kernel, Debian, dependencias y parches de seguridad | `unattended-upgrades` de Debian | Descarga e instala automáticamente los parches cubiertos por su configuración oficial. |
| Resto de paquetes, escritorio y navegadores instalados con APT | `sudo reytv-system-update` | Revisa y propone una actualización **completa de paquetes** (`apt full-upgrade`), con confirmación. |
| Interfaz ReyTV (`index.html`) | `reytv-update` | Descarga desde GitHub, hace copia de la interfaz y permite `reytv-rollback`. Requiere configurar acceso SSH de solo lectura al repositorio privado. |
| Salto de Debian 13 a Debian 14 o firmware | **No automático todavía** | Se hará con una versión probada y un plan de respaldo; no es seguro prometer un A/B rollback en un SSD de 16 GB. |

Es una distribución Linux personalizable que se actualiza **por paquetes**, no un sistema Android ni un firmware con actualizaciones atómicas A/B. Actualizaciones de kernel pueden exigir reinicio. El repositorio privado no debe incluir claves de GitHub, cuentas de Netflix ni contraseñas.

#### Configurar actualizaciones de la interfaz desde GitHub

1. En el Chromebox instalado, crea una deploy key SSH **de solo lectura**:

   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   ssh-keygen -t ed25519 -f ~/.ssh/reytv_deploy -N '' -C 'ReyTV CN60'
   cat ~/.ssh/reytv_deploy.pub
   ```

2. Copia solamente la **clave pública** a `ReinaldoAG/ReyTV → Settings → Deploy keys → Add deploy key` sin marcar «Allow write access». Comprueba la huella del servidor SSH de GitHub con su documentación oficial antes de aceptar la conexión.
3. Prueba la descarga y luego habilita la verificación diaria:

   ```bash
   reytv-update
   systemctl --user daemon-reload
   systemctl --user enable --now reytv-update.timer
   ```

4. Si una interfaz nueva falla, ejecuta `reytv-rollback`. Se bloqueará temporalmente esa revisión y se esperará una nueva versión. El actualizador **solo cambia la interfaz web**: los scripts del sistema se entregan mediante futuras revisiones empaquetadas o nuevos instaladores.

## Construir la ISO en tu propia computadora Linux

En una máquina de compilación Ubuntu/Debian x86-64 con suficiente espacio disponible (recomendamos 20 GB libres y conexión rápida):

```bash
sudo apt-get update
sudo apt-get install live-build debootstrap xorriso squashfs-tools isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin dosfstools mtools
bash tests/iso-smoke.sh
sudo bash iso/build.sh
```

La imagen se genera en `.build-iso/reytv-amd64.hybrid.iso` junto con su checksum. No ejecuta `dd`, no particiona discos y no modifica el firmware. El workflow de GitHub Actions realiza estos mismos pasos y conserva la ISO como un artefacto descargable.

## Controles y futura compatibilidad

| Tecla | Función |
| --- | --- |
| `← ↑ ↓ →` | Mover el foco entre botones y tarjetas |
| `Enter` | Abrir / confirmar |
| `Esc` | Regresar al inicio (dentro del menú ReyTV) |
| `/` | Buscar servicios |
| `Ctrl+W` | Cerrar la pestaña de un servicio |
| `F11` | Alternar pantalla completa (según navegador) |

La compatibilidad Bluetooth con tu mando Sony PS3 Blu-ray queda para la siguiente etapa. El mando del televisor por HDMI-CEC podría requerir hardware adicional, por lo que no lo prometemos ahora.

## Archivos importantes

- `index.html`: menú con favoritos, búsqueda y URLs personalizadas.
- `iso/build.sh`: genera el USB live + instalador de Debian con ReyTV.
- `iso/files/` y `iso/packages.list.chroot`: sistema incorporado y dependencias.
- `.github/workflows/build-iso.yml`: compilación y descarga de la ISO.
- `linux/reytv-launch`: servidor de interfaz local y navegador a pantalla completa.
- `linux/install-reytv.sh`: instalador no destructivo para un Linux existente (opcional).
- `linux/reytv-update` y `linux/reytv-rollback`: actualizar y recuperar la interfaz.
- `tests/iso-smoke.sh` y `tests/update-smoke.sh`: pruebas de consistencia.

Proyecto personal sin afiliación con los servicios de streaming mencionados.

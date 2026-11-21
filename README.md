# ReyTV — versión 0.3 (ISO instalable)

**ReyTV** transforma una computadora x86-64, como el ASUS Chromebox CN60, en un centro de entretenimiento tipo Roku controlado inicialmente con teclado. Ofrece un menú a pantalla completa para servicios **web oficiales** de YouTube, Netflix, Prime Video, Disney+, Max, Spotify, Twitch y Plex; no contiene APKs ni suplanta aplicaciones de Android.

## ISO de ReyTV — reemplaza Bliss OS sin depender de un Linux previo

La ISO personalizada se construye con **Debian 13 (trixie) + LXQt + ReyTV** mediante [Debian live-build](https://live-team.pages.debian.net/live-manual/html/live-manual/index.en.html). Incluye un escritorio live para probarla desde USB y un **instalador de Debian Live** que puede instalar la misma imagen en el disco interno. No instala Android ni ChromeOS, y **no flashea el firmware**.

### Descargar una ISO compilada

1. Entra en [ReinaldoAG/ReyTV](https://github.com/ReinaldoAG/ReyTV).
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
| Interfaz ReyTV (`index.html`) | Botones en **Ajustes → Actualizaciones** | Comprueba GitHub público por HTTPS, instala el menú y permite volver a la versión anterior. No necesita claves SSH ni privilegios de root. |
| Salto de Debian 13 a Debian 14 o firmware | **No automático todavía** | Se hará con una versión probada y un plan de respaldo; no es seguro prometer un A/B rollback en un SSD de 16 GB. |

Es una distribución Linux personalizable que se actualiza **por paquetes**, no un sistema Android ni un firmware con actualizaciones atómicas A/B. Las actualizaciones del kernel pueden exigir reinicio. Nunca almacenes contraseñas, claves personales ni cuentas de Netflix en el repositorio público.

#### Actualizar el menú sin terminal (nuevas instalaciones)

1. Abre **Ajustes** en ReyTV.
2. Pulsa **Buscar actualizaciones** y después **Actualizar ahora** si aparece una versión nueva.
3. El menú se recarga con el cambio. **Volver a la versión anterior** restaura la última copia si es necesario.
4. El comprobador diario usa `systemctl --user` y descarga cambios del repositorio público por HTTPS. No ejecuta comandos recibidos del navegador ni eleva permisos.

La interfaz de Ajustes solo controla el menú web. **No es un actualizador completo del kernel, del firmware ni de la versión mayor de Debian**; esa parte sigue usando APT y requiere intervención por separado.

#### Habilitar el botón en una ISO ya instalada (una sola vez)

Las ISO previas a la incorporación de `reytv-server.py` utilizaban el servidor web estático y no tienen el API para actualizar con un botón. Su instalación se puede conservar. Tras hacer público este repositorio, descarga el instalador de transición desde GitHub y ejecútalo con tu usuario normal (no con `sudo`):

```bash
curl -fsSL --proto '=https' --proto-redir '=https' \
  https://raw.githubusercontent.com/ReinaldoAG/ReyTV/main/linux/reytv-enable-updates.sh \
  -o /tmp/reytv-enable-updates.sh
bash /tmp/reytv-enable-updates.sh
```

El instalador comprueba los archivos antes de copiarlos, guarda respaldo del menú, instala el servicio local en `~/.local/bin`, configura el inicio y activa el temporizador diario. **Reinicia una vez** y ya podrás usar los botones de Ajustes. No reconfigura particiones ni elimina otros sistemas. Como cualquier instalador descargado de Internet, ejecútalo únicamente si confías en el repositorio y en su contenido.

Si falla una actualización, usa el botón de restauración o ejecuta `reytv-rollback`. Se bloqueará temporalmente esa revisión y se esperará una versión nueva. El actualizador **solo cambia el menú HTML**: nuevos scripts o servicios se entregarán en futuras versiones empaquetadas y revisadas. No es una actualización atómica del sistema operativo.

## Construir la ISO en tu propia computadora Linux

En una máquina de compilación **Debian 13 (trixie)** x86-64 con suficiente espacio disponible (recomendamos 20 GB libres y conexión rápida):

```bash
sudo apt-get update
sudo apt-get install live-build debootstrap xorriso squashfs-tools isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin dosfstools mtools
bash tests/iso-smoke.sh
sudo bash iso/build.sh
```

La imagen se genera en `.build-iso/reytv-amd64.hybrid.iso` junto con su checksum. No ejecuta `dd`, no particiona discos y no modifica el firmware. El workflow de GitHub Actions usa un contenedor **Debian 13** para evitar el `live-build` anticuado incluido en Ubuntu 24.04 y conserva la ISO como un artefacto descargable.

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

## Modo TV dedicado (0.3, transición experimental)

Desde una instalación 0.2.2 con reloj y APT funcionando, sigue [copy](copy). La transición crea una sesión X11 independiente de LXQt con inicio automático SDDM, Openbox mínimo, Chromium/Chrome en modo kiosco, cursor oculto al quedar quieto y reinicio supervisado. F8 (o tecla multimedia Home) vuelve a Inicio cerrando y reabriendo el navegador con el mismo perfil; F2 marca favoritos. Las aplicaciones web externas conservan sus propios controles y DRM: su navegación exclusivamente por mando todavía no está garantizada.

La sesión es reversible: Ctrl+Alt+Esc muestra SDDM; puedes elegir LXQt. Si falla el arranque: Ctrl+Alt+F3, entrar con tu usuario, ejecutar sudo reytv-tv-disable y sudo reboot. Se restaura la configuración previa de SDDM. No se elimina LXQt ni el perfil. Los cambios en HTML siguen llegando por el actualizador existente; los cambios de sesión nativa todavía requieren un instalador separado. No se ha validado este modo en el CN60 físico.

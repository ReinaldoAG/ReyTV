# ReyTV — versión 0.2

Interfaz de televisión ligera y actualizable para el ASUS Chromebox CN60. Funciona con teclado y abre **servicios web legítimos** en el navegador; no suplanta ninguna aplicación oficial ni promete compatibilidad con todas las plataformas.

## Qué incluye esta versión

- Inicio a pantalla completa, tarjetas de servicios, reloj, favoritos y búsqueda.
- Flechas para mover el foco, Enter para abrir y Escape para volver a Inicio.
- Pestañas independientes para cada servicio: `Ctrl+W` cierra la pestaña y regresa al menú.
- Lista de favoritos y accesos HTTPS personalizados (hasta 24), guardados en el navegador.
- Instalador de arranque automático **no destructivo** para Linux.
- Actualizador de la interfaz desde la rama `main` de `ReinaldoAG/ReyTV`, con copia de seguridad y vuelta a la versión anterior.
- Temporizador opcional para comprobar novedades una vez al día.

Servicios predefinidos: YouTube, Netflix, Prime Video, Disney+, Max, Spotify, Twitch y Plex. Todas son **páginas web**, no APKs instalados. Se requiere internet y, en su caso, una suscripción activa.

## Para probar hoy mismo, sin instalar nada

Abre `index.html` con un navegador actual en cualquier computadora. Comprueba flechas, Enter, favoritos, búsqueda y la opción «Añadir servicio». Esta prueba no modifica ningún sistema operativo.

## Arquitectura recomendada para el CN60

**Debian 13 de 64 bits + escritorio ligero LXQt + Google Chrome oficial + ReyTV**. El launcher tiene pocas dependencias y evita instalar Electron o Android emulado en el Chromebox. Con 16 GB de almacenamiento hay que seleccionar un escritorio ligero y evitar aplicaciones innecesarias.

Netflix admite algunos navegadores actuales en GNU/Linux, pero no garantiza que funcione en todas las configuraciones. La reproducción, calidad, audio y navegación dentro de cada plataforma deben probarse físicamente en el CN60. Al no ser un Android certificado, **esta solución no instala aplicaciones Android nativas ni una Play Store certificada**.

## Instalación segura en el Chromebox (una vez instalado Linux)

1. **Antes de borrar Android:** confirmar cómo arranca el CN60 (firmware UEFI o modo heredado), hacer copia de lo importante y tener un pendrive instalador funcional. NO flashear firmware solamente por seguir esta guía.
2. Descargar la imagen de Debian 13 amd64 **desde** <https://www.debian.org/download> y seguir su guía oficial <https://www.debian.org/releases/stable/amd64/>. Crear el USB desde otra computadora. Solo al verificar en pantalla el **disco interno exacto**, decidir si se elimina Android; el instalador de Debian puede borrar por completo el disco si se elige usarlo entero.
3. Durante la instalación, seleccionar **LXQt** como entorno de escritorio ligero (si el instalador lo ofrece) y crear un usuario normal. Habilitar inicio de sesión automático más adelante si se desea un arranque sin teclado.
4. Ya en Debian, instalar Chrome **desde** <https://www.google.com/chrome/> eligiendo `.deb` de 64 bits. Google Chrome es preferible a Chromium para probar Netflix y Widevine.
5. Asegurarse de tener `python3` y `git`: `sudo apt install python3 git`.
6. Descargar el ZIP de `ReinaldoAG/ReyTV` desde GitHub, descomprimirlo y abrir una terminal dentro de esa carpeta. Ejecutar:

   ```bash
   bash linux/install-reytv.sh
   ```

7. El instalador deja un comando `~/.local/bin/reytv` y una entrada de inicio automático para la sesión gráfica. Ejecutar el comando para probar; al reiniciar sesión debería abrirse el menú a pantalla completa.

**Importante:** este proyecto **no es todavía una ISO ni reemplaza Android por sí solo**. Incluye la aplicación ReyTV y su instalador para Linux. La instalación del sistema base se hará por separado y únicamente tras revisar el arranque del CN60.

## Actualizaciones sin volver a instalar Linux

Una vez instalado Debian, solo hace falta copiar ReyTV una vez. Los cambios futuros del menú se descargan desde GitHub **sin formatear el disco y sin reinstalar Debian**. Las actualizaciones de Chrome, firmware y Debian son independientes; para parches de seguridad del sistema se puede usar el paquete oficial `unattended-upgrades`.

El repositorio `ReinaldoAG/ReyTV` actualmente es **privado**. Para que el Chromebox acceda sin almacenar tu contraseña de GitHub en el código, se recomienda una **deploy key SSH de solo lectura** vinculada exclusivamente a este repositorio.

En el Chromebox, después de instalar Debian:

1. Crear una clave dedicada (el archivo privado permanece en el Chromebox):

   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   ssh-keygen -t ed25519 -f ~/.ssh/reytv_deploy -N '' -C 'ReyTV Chromebox CN60'
   cat ~/.ssh/reytv_deploy.pub
   ```

2. Copiar **solo la clave pública** que aparece en pantalla a **GitHub → ReinaldoAG/ReyTV → Settings → Deploy keys → Add deploy key**. No marcar `Allow write access`. Nunca compartir el contenido del archivo sin `.pub`.
3. Realizar una conexión SSH inicial a GitHub y **verificar la huella del servidor con la documentación oficial de GitHub** antes de aceptarla. Si no queda registrada la clave del host en `~/.ssh/known_hosts`, la actualización automática se detendrá por seguridad.
4. Probar manualmente:

   ```bash
   ~/.local/bin/reytv-update
   ```

5. Si se actualizó correctamente, habilitar la comprobación diaria (requiere `systemd --user`, habitual en Debian):

   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now reytv-update.timer
   ```

6. Cuando ReyTV detecta una versión nueva de `main`, guarda la interfaz anterior y sustituye únicamente `index.html`. Basta recargar ReyTV para ver el cambio. Si algo sale mal:

   ```bash
   ~/.local/bin/reytv-rollback
   ```

   El rollback bloquea temporalmente el commit revertido para que el temporizador no lo reinstale al día siguiente. Una versión posterior en `main` se podrá aplicar con normalidad. Para forzar la versión previamente bloqueada: `~/.local/bin/reytv-update --force`.

**Limitaciones actuales:** el actualizador únicamente gestiona `index.html`; si actualizamos los scripts del sistema, debemos ejecutar de nuevo el instalador. Todavía no se ha probado en el CN60 real. Evitar publicar en `main` cambios experimentales sin comprobar primero su comportamiento; los dispositivos con auto-actualización recibirán la nueva interfaz.

## Controles

| Tecla | Acción |
|---|---|
| `← ↑ ↓ →` | Cambiar selección en la interfaz |
| `Enter` | Abrir / confirmar |
| `Esc` o `Retroceso` | Volver al inicio cuando estás dentro del menú |
| `/` | Ir a búsqueda de aplicaciones |
| `Ctrl+W` | Cerrar pestaña de servicio y volver al menú |
| `F11` | Alternar pantalla completa (según navegador) |

La navegación dentro de Netflix, Disney+, etc., la controla cada página. Algunos servicios podrían necesitar mouse; la compatibilidad con el control de PS3 será una fase posterior.

## Estructura

- `index.html`: interfaz web autocontenida, sin CDN ni dependencias externas.
- `linux/reytv-launch`: servidor local solo en `127.0.0.1` + navegador a pantalla completa.
- `linux/install-reytv.sh`: copia los archivos al usuario y crea su autostart. No realiza cambios de firmware ni formateos.
- `linux/reytv-update`: comprueba novedades en GitHub y actualiza únicamente la interfaz, con validación básica y copia previa.
- `linux/reytv-rollback`: restaura la interfaz inmediatamente anterior.
- `linux/systemd/`: servicio y temporizador opcionales para revisión diaria.

## Próximos pasos

1. Probar la interfaz con teclado en la PC.
2. Identificar el firmware y la edición de Android actual del Chromebox.
3. Probar una sesión de Debian **desde USB**, sin instalar, si el firmware/medio lo permite.
4. Instalar Debian solo después de comprobar conexión, video, sonido, Wi-Fi y capacidad de regresar al instalador.
5. Verificar Netflix/YouTube y afinar rendimiento real.
6. Emparejar y mapear el mando Blu-ray de PS3 por Bluetooth.

Desarrollado como proyecto personal. ReyTV no está afiliado con los servicios de streaming incluidos.

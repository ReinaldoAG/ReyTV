# Franche TV — versión 0.1

Interfaz de televisión ligera para el ASUS Chromebox CN60. Funciona con teclado y abre **servicios web legítimos** en el navegador; no suplanta ninguna aplicación oficial ni promete compatibilidad con todas las plataformas.

## Qué incluye esta versión

- Inicio a pantalla completa, tarjetas de servicios, reloj, favoritos y búsqueda.
- Flechas para mover el foco, Enter para abrir y Escape para volver a Inicio.
- Pestañas independientes para cada servicio: `Ctrl+W` cierra la pestaña y regresa al menú.
- Lista de favoritos y accesos HTTPS personalizados (hasta 24), guardados en el navegador.
- Instalador de arranque automático **no destructivo** para Linux.

Servicios predefinidos: YouTube, Netflix, Prime Video, Disney+, Max, Spotify, Twitch y Plex. Todas son **páginas web**, no APKs instalados. Se requiere internet y, en su caso, una suscripción activa.

## Para probar hoy mismo, sin instalar nada

Abre `index.html` con un navegador actual en cualquier computadora. Comprueba flechas, Enter, favoritos, búsqueda y la opción «Añadir servicio». Esta prueba no modifica ningún sistema operativo.

## Arquitectura recomendada para el CN60

**Debian 13 de 64 bits + escritorio ligero LXQt + Google Chrome oficial + Franche TV**. El launcher tiene pocas dependencias y evita instalar Electron o Android emulado en el Chromebox. Con 16 GB de almacenamiento hay que seleccionar un escritorio ligero y evitar aplicaciones innecesarias.

Netflix admite algunos navegadores actuales en GNU/Linux, pero no garantiza que funcione en todas las configuraciones. La reproducción, calidad, audio y navegación dentro de cada plataforma deben probarse físicamente en el CN60. Al no ser un Android certificado, **esta solución no instala aplicaciones Android nativas ni una Play Store certificada**.

## Instalación segura en el Chromebox (una vez instalado Linux)

1. **Antes de borrar Android:** confirmar cómo arranca el CN60 (firmware UEFI o modo heredado), hacer copia de lo importante y tener un pendrive instalador funcional. NO flashear firmware solamente por seguir esta guía.
2. Descargar la imagen de Debian 13 amd64 **desde** <https://www.debian.org/download> y seguir su guía oficial <https://www.debian.org/releases/stable/amd64/>. Crear el USB desde otra computadora. Solo al verificar en pantalla el **disco interno exacto**, decidir si se elimina Android; el instalador de Debian puede borrar por completo el disco si se elige usarlo entero.
3. Durante la instalación, seleccionar **LXQt** como entorno de escritorio ligero (si el instalador lo ofrece) y crear un usuario normal. Habilitar inicio de sesión automático más adelante si se desea un arranque sin teclado.
4. Ya en Debian, instalar Chrome **desde** <https://www.google.com/chrome/> eligiendo `.deb` de 64 bits. Google Chrome es preferible a Chromium para probar Netflix y Widevine.
5. Asegurarse de tener `python3` (normalmente incluido): `sudo apt install python3`.
6. Copiar la carpeta `franche-tv` al Linux, abrir una terminal dentro de esa carpeta y ejecutar:

   ```bash
   bash linux/install-franche-tv.sh
   ```

7. El instalador deja un comando `~/.local/bin/franche-tv` y una entrada de inicio automático para la sesión gráfica. Ejecutar el comando para probar; al reiniciar sesión debería abrirse el menú a pantalla completa.

**Importante:** este ZIP **no es una ISO ni reemplaza Android por sí solo**. Incluye el software de Franche TV y su instalador para Linux. La instalación del sistema base se hará por separado y únicamente tras revisar el arranque del CN60.

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
- `linux/franche-tv-launch`: servidor local solo en `127.0.0.1` + navegador a pantalla completa.
- `linux/install-franche-tv.sh`: copia los archivos al usuario y crea su autostart. No realiza cambios de firmware ni formateos.

## Próximos pasos

1. Probar la interfaz con teclado en la PC.
2. Identificar el firmware y la edición de Android actual del Chromebox.
3. Probar una sesión de Debian **desde USB**, sin instalar, si el firmware/medio lo permite.
4. Instalar Debian solo después de comprobar conexión, video, sonido, Wi-Fi y capacidad de regresar al instalador.
5. Verificar Netflix/YouTube y afinar rendimiento real.
6. Emparejar y mapear el mando Blu-ray de PS3 por Bluetooth.

Desarrollado como proyecto personal. Franche TV no está afiliado con los servicios de streaming incluidos.

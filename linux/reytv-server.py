#!/usr/bin/env python3
"""Servidor local de ReyTV y actualización de la interfaz sin permisos de root.

Solo escucha 127.0.0.1 y acepta acciones del propio menú ReyTV.
No ejecuta comandos arbitrarios enviados por HTTP.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


PORT = 18763
REPOSITORY = "https://github.com/ReinaldoAG/ReyTV.git"
BRANCH = "main"



def cpu_ticks(path=Path("/proc/stat")):
    values = [int(v) for v in path.read_text().splitlines()[0].split()[1:9]]
    if len(values) < 5:
        raise ValueError("Invalid CPU counters")
    return sum(values), values[3] + values[4]


def cpu_percent(first, second):
    total = second[0] - first[0]
    idle = second[1] - first[1]
    return round(max(0, min(100, 100 * (total-idle)/total))) if total > 0 else None


def memory_snapshot(path=Path("/proc/meminfo")):
    values = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
            values[key] = int(value.split()[0])
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable")
    used = max(0, total-available) if available is not None and total else None
    return {"percent": min(100, round(100*used/total)) if used is not None else None,
            "total_mib": round(total/1024), "used_mib": round(used/1024) if used is not None else None,
            "swap_mib": round(values.get("SwapTotal",0)/1024),
            "swap_used_mib": round(max(0, values.get("SwapTotal",0)-values.get("SwapFree",0))/1024)}


def tv_browser():
    # Never return command lines or browsing history over HTTP.
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home()/".config")
    profile = os.fsencode("--user-data-dir="+str(config/"reytv/chrome-profile"))
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = (proc/"cmdline").read_bytes().split(b"\0")
            if profile not in args or any(arg.startswith(b"--type=") for arg in args):
                continue
            exe = os.readlink(proc/"exe")
            if exe.startswith("/opt/google/chrome/"):
                return "Google Chrome"
            if "chromium" in exe.lower():
                return "Chromium"
        except OSError:
            continue
    return "No verificado"


def vaapi_snapshot():
    import shutil
    nodes = sorted(Path("/dev/dri").glob("renderD*"))
    drivers = []
    for node in nodes:
        try:
            drivers.append((Path("/sys/class/drm")/node.name/"device/driver").resolve(strict=True).name)
        except OSError:
            continue
    installed = [name for name in ("i965", "iHD") if any(
        Path("/usr/lib").glob("*/dri/"+name+"_drv_video.so"))]
    result = {"driver": ", ".join(sorted(set(drivers))) or "No detectado",
              "va_drivers": installed, "status": "No comprobado", "h264": None}
    if not nodes:
        result["status"] = "Sin dispositivo de renderizado"
    elif not shutil.which("vainfo"):
        result["status"] = "Falta vainfo"
    else:
        # Explicit local device, bounded execution, no privileged action.
        try:
            env = dict(os.environ, LC_ALL="C")
            run = subprocess.run(["vainfo","--display","drm","--device",str(nodes[0])],
                                 capture_output=True,text=True,timeout=4,env=env)
            if run.returncode == 0:
                result["status"] = "VA-API disponible"
                result["h264"] = bool(re.search(r"VAProfileH264\w*\s*:\s*VAEntrypointVLD",run.stdout))
            else:
                result["status"] = "VA-API no se pudo iniciar"
        except (OSError, subprocess.TimeoutExpired):
            result["status"] = "Diagnóstico no disponible"
    return result


def browser_profile_health():
    """Indicadores del perfil, sin leer ni devolver cookies o contraseñas."""
    config = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home()/".config"))
    profile = config/"reytv/chrome-profile"
    basic = (config/"reytv/tv-password-store-basic").is_file()
    cookie_files = (profile/"Default/Network/Cookies", profile/"Default/Cookies")
    return {"profile_writable": profile.is_dir() and os.access(profile, os.W_OK),
            "cookies_database_present": any(p.is_file() for p in cookie_files),
            "password_storage": "Básico (sin llavero)" if basic else "Llavero del sistema"}


def performance_snapshot():
    import shutil
    import time
    first = cpu_ticks()
    memory = memory_snapshot()
    disk = shutil.disk_usage("/")
    time.sleep(.20)
    cpu = cpu_percent(first,cpu_ticks())
    try:
        zram = any(line.split()[0].startswith("/dev/zram") for line in Path("/proc/swaps").read_text().splitlines()[1:] if line.split())
    except OSError:
        zram = None
    return {"cpu_percent":cpu,"memory":memory,
            "disk":{"percent":round(100*disk.used/disk.total),"free_gib":round(disk.free/1024**3,1)},
            "browser":tv_browser(),"video":vaapi_snapshot(),"zram":zram,
            "session":browser_profile_health()}


class ReyTVServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, app_dir, bin_dir, state_dir):
        super().__init__(address, ReyTVHandler)
        self.app_dir = Path(app_dir)
        self.bin_dir = Path(bin_dir)
        self.state_dir = Path(state_dir)
        self.csrf = secrets.token_urlsafe(32)
        self.action_lock = threading.Lock()
        self.restart_requested = False


class ReyTVHandler(BaseHTTPRequestHandler):
    def _local_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def _send(self, status, data, kind="application/json; charset=utf-8"):
        payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self._local_host():
            self._send(403, {"error": "Acceso permitido solo desde este dispositivo"})
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            self._send(200, {"ready": True, "token": self.server.csrf,
                             "revision": self._current_sha(), "version": self._version(), "full_update": True})
        elif path == "/api/performance":
            try:
                self._send(200, performance_snapshot())
            except (OSError, ValueError):
                self._send(503, {"error": "Diagnóstico temporalmente no disponible"})
        elif path == "/api/native/status":
            try:
                self._send(200, self._native().status())
            except (OSError, ImportError) as exc:
                self._send(503, {"error": "Controles del sistema no instalados."})
        elif path in ("/", "/index.html"):
            try:
                html = (self.server.app_dir / "index.html").read_bytes()
            except OSError:
                self._send(404, {"error": "No se encuentra el menú de ReyTV"})
                return
            self._send(200, html, "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "No encontrado"})

    def do_POST(self):
        path = urlsplit(self.path).path
        if path not in ("/api/check", "/api/update", "/api/rollback", "/api/native/action", "/api/native/scan"):
            self._send(404, {"error": "Acción desconocida"})
            return
        # Los sitios externos no pueden solicitar una actualización mediante
        # formularios ni JavaScript: exigimos origen correcto y un token efímero.
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if (not self._local_host() or self.headers.get("Origin") != origin
                or not secrets.compare_digest(self.headers.get("X-ReyTV-Token", ""), self.server.csrf)
                or not self._body_length_allowed(path)):

            self._send(403, {"error": "Solicitud no autorizada"})
            return
        if not self.server.action_lock.acquire(blocking=False):
            self._send(409, {"error": "Ya se está realizando otra operación"})
            return
        try:
            if path.startswith("/api/native/"):
                try:
                    body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                    native = self._native()
                    if path == "/api/native/scan":
                        target = body.get("target")
                        if type(body) is not dict or set(body) != {"target"} or target not in ("wifi", "bluetooth"):
                            raise ValueError("Tipo de escaneo incorrecto.")
                        response = native.wifi_status(True) if target == "wifi" else native.bluetooth_status(True)
                        self._send(200, response)
                    else:
                        if type(body) is not dict or set(body) != {"operation", "params"}:
                            raise ValueError("Solicitud incorrecta.")
                        response = native.act(body["operation"], body["params"])
                        self._send(200, response)
                except (ValueError, TypeError) as error:
                    self._send(400, {"error": str(error)[:160]})
                except Exception as error:
                    # Un error de autorización / dispositivo no debe romper ReyTV.
                    if error.__class__.__name__ == "NativeError":
                        self._send(400, {"error": str(error)[:160]})
                    else:
                        self._send(503, {"error": "Controles nativos temporalmente no disponibles."})
                return
            if path == "/api/check":
                cmd = ["git", "ls-remote", REPOSITORY, "refs/heads/" + BRANCH]
                result = self._run(cmd, timeout=30)
                if result.returncode:
                    self._send(502, {"error": "No se pudo comprobar GitHub", "detail": result.stderr[-400:]})
                    return
                remote = result.stdout.split()[0] if result.stdout.strip() else ""
                if not re.fullmatch(r"[0-9a-f]{40}", remote):
                    self._send(502, {"error": "Respuesta inesperada de GitHub"})
                    return
                self._send(200, {"available": remote != self._current_sha(), "revision": remote,
                                 "installed": self._current_sha(), "full_update": True})
                return
            name = "reytv-update" if path == "/api/update" else "reytv-rollback"
            executable = self.server.bin_dir / name
            if not executable.is_file():
                self._send(503, {"error": f"No se encuentra {name}"})
                return
            result = self._run([str(executable)], timeout=90)
            if result.returncode:
                self._send(502, {"error": f"Falló {name}", "detail": result.stderr[-600:] or result.stdout[-600:]})
                return
            self._send(200, {"ok": True, "message": result.stdout.strip()[-500:],
                             "revision": self._current_sha()})
            # Recargar el backend desde el archivo recién instalado.
            # Primero respondemos a Chromium; luego liberamos el puerto HTTP.
            self.server.restart_requested = True
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        except subprocess.TimeoutExpired:
            self._send(504, {"error": "La operación tardó demasiado; prueba de nuevo más tarde"})
        except OSError:
            self._send(503, {"error": "Herramientas de actualización no disponibles"})
        finally:
            self.server.action_lock.release()

    def _body_length_allowed(self, path):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return False
        return (0 <= length <= 2) if not path.startswith("/api/native/") else (2 <= length <= 2048)

    def _native(self):
        module_path = self.server.bin_dir / "reytv-native.py"
        spec = importlib.util.spec_from_file_location("reytv_native", module_path)
        if spec is None or spec.loader is None:
            raise ImportError("Native module missing.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _run(self, cmd, timeout):
        env = os.environ.copy()
        env["REYTV_REPO_URL"] = REPOSITORY
        env["REYTV_CHANNEL"] = BRANCH
        return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=env, check=False)

    def _current_sha(self):
        try:
            return (self.server.state_dir / "current.sha").read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def _version(self):
        try:
            html = (self.server.app_dir / "index.html").read_text(encoding="utf-8")
            match = re.search(r"ReyTV · (\d+(?:\.\d+)+)", html)
            return match.group(1) if match else "desconocida"
        except OSError:
            return "desconocida"

    def log_message(self, fmt, *args):
        # Solo se registra la ruta, nunca cabeceras ni tokens.
        super().log_message(fmt, *args)



def mouse_overlay():
    """Control X11 local de navegación. Proceso aislado; no HTTP ni permisos root."""
    import ctypes as C
    import time
    import queue
    if not os.environ.get("DISPLAY") or os.getuid() == 0:
        return
    try:
        x = C.CDLL("libX11.so.6")
        xt = C.CDLL("libXtst.so.6")
    except OSError as exc:
        print("ReyTV: navegación X11 no disponible:", exc, file=sys.stderr)
        return
    P, U, I, L = C.c_void_p, C.c_ulong, C.c_int, C.c_long

    class Attributes(C.Structure):
        _fields_ = [(n,U) for n in ("background_pixmap","background_pixel","border_pixmap","border_pixel")] + [
            ("bit_gravity",I),("win_gravity",I),("backing_store",I),
            ("backing_planes",U),("backing_pixel",U),("save_under",I),
            ("event_mask",L),("do_not_propagate_mask",L),("override_redirect",I),
            ("colormap",U),("cursor",U)]

    class Button(C.Structure):
        _fields_ = [("type",I),("serial",U),("send_event",I),("display",P),
            ("window",U),("root",U),("subwindow",U),("time",U),
            ("x",I),("y",I),("x_root",I),("y_root",I),("state",C.c_uint),
            ("button",C.c_uint),("same_screen",I)]

    class Event(C.Union):
        _fields_ = [("type",I),("button",Button),("pad",L*24)]

    class ClassHint(C.Structure):
        _fields_ = [("res_name",P),("res_class",P)]

    def fn(lib,name,ret,*args):
        f=getattr(lib,name);f.restype=ret;f.argtypes=list(args);return f

    for name,ret,args in [
        ("XOpenDisplay",P,[C.c_char_p]),("XCloseDisplay",I,[P]),
        ("XDefaultScreen",I,[P]),("XRootWindow",U,[P,I]),
        ("XDisplayWidth",I,[P,I]),("XDisplayHeight",I,[P,I]),
        ("XCreateSimpleWindow",U,[P,U,I,I,C.c_uint,C.c_uint,C.c_uint,U,U]),
        ("XChangeWindowAttributes",I,[P,U,U,C.POINTER(Attributes)]),
        ("XStoreName",I,[P,U,C.c_char_p]),("XSelectInput",I,[P,U,L]),
        ("XCreateGC",P,[P,U,U,P]),("XFreeGC",I,[P,P]),
        ("XInternAtom",U,[P,C.c_char_p,I]),
        ("XGetWindowProperty",I,[P,U,U,L,L,I,U,C.POINTER(U),C.POINTER(I),C.POINTER(U),C.POINTER(U),C.POINTER(P)]),
        ("XGetClassHint",I,[P,U,C.POINTER(ClassHint)]),("XFree",I,[P]),
        ("XMapRaised",I,[P,U]),("XUnmapWindow",I,[P,U]),("XRaiseWindow",I,[P,U]),
        ("XMoveWindow",I,[P,U,I,I]),("XMoveResizeWindow",I,[P,U,I,I,C.c_uint,C.c_uint]),("XDestroyWindow",I,[P,U]),
        ("XQueryPointer",I,[P,U,C.POINTER(U),C.POINTER(U),C.POINTER(I),C.POINTER(I),C.POINTER(I),C.POINTER(I),C.POINTER(C.c_uint)]),("XPending",I,[P]),("XNextEvent",I,[P,C.POINTER(Event)]),
        ("XSetForeground",I,[P,P,U]),("XFillRectangle",I,[P,U,P,I,I,C.c_uint,C.c_uint]),
        ("XDrawLine",I,[P,U,P,I,I,I,I]),("XDrawString",I,[P,U,P,I,I,C.c_char_p,I]),
        ("XFlush",I,[P]),("XStringToKeysym",U,[C.c_char_p]),("XKeysymToKeycode",C.c_ubyte,[P,U]),
        ("XkbKeycodeToKeysym",U,[P,C.c_ubyte,I,I]),("XLoadFont",U,[P,C.c_char_p]),("XSetFont",I,[P,P,U]),("XUnloadFont",I,[P,U]),
    ]: fn(x,name,ret,*args)
    fake=fn(xt,"XTestFakeKeyEvent",I,P,C.c_uint,I,U)
    # Una ventana puede desaparecer mientras consultamos su título.
    # Los errores X11 de esas ventanas no deben interrumpir esta ayuda.
    error_type=C.CFUNCTYPE(I,P,P)
    error_callback=error_type(lambda display,error: 0)
    fn(x,"XSetErrorHandler",P,error_type)(error_callback)
    d=x.XOpenDisplay(None)
    if not d:return
    screen=x.XDefaultScreen(d);root=x.XRootWindow(d,screen)
    active_atom=x.XInternAtom(d,b"_NET_ACTIVE_WINDOW",False)
    title_atom=x.XInternAtom(d,b"_NET_WM_NAME",False)
    legacy_atom=x.XInternAtom(d,b"WM_NAME",False)
    # Tres iconos compactos, ocultos hasta acercar el mouse a la esquina superior derecha.
    width,height=132,44
    win=x.XCreateSimpleWindow(d,root,0,0,width,height,1,0x839DD0,0x162745)
    attrs=Attributes();attrs.override_redirect=1
    x.XChangeWindowAttributes(d,win,1<<9,C.byref(attrs))
    x.XStoreName(d,win,b"ReyTV mouse navigation")
    x.XSelectInput(d,win,(1<<15)|(1<<2)|(1<<3))
    gc=x.XCreateGC(d,win,0,None)
    event=Event()
    # Una segunda ventana sin foco conserva la entrada en el campo original.
    kw=x.XCreateSimpleWindow(d,root,0,0,820,260,1,0x839DD0,0x101e39)
    x.XChangeWindowAttributes(d,kw,1<<9,C.byref(attrs))
    x.XStoreName(d,kw,b"ReyTV external keyboard")
    x.XSelectInput(d,kw,(1<<15)|(1<<2)|(1<<3))
    kgc=x.XCreateGC(d,kw,0,None)
    font=x.XLoadFont(d,b"-*-*-bold-r-normal--20-*-*-*-*-*-iso8859-1")
    if font:x.XSetFont(d,kgc,font)
    key_open=False;key_mode='lower';key_pressed=None;key_rect=(0,0,820,260);field_y=None
    focus_events=queue.SimpleQueue();mouse_down=False;opened_at=0.0;field_bounds=None
    mapped=False;pressed=None;last_window=0;last_size=None;last_raise=0.0;hover_since=None
    parent=os.getppid()

    def prop(window,atom):
        typ=U();fmt=I();count=U();after=U();data=P()
        result=x.XGetWindowProperty(d,window,atom,0,1024,False,0,C.byref(typ),C.byref(fmt),C.byref(count),C.byref(after),C.byref(data))
        try:
            if result or not data.value or not count.value:return None
            if fmt.value==32:return C.cast(data,C.POINTER(U))[0]
            if fmt.value==8:return C.string_at(data,count.value).decode("utf-8","replace")
            return None
        finally:
            if data.value:x.XFree(data)

    def browser_window():
        active=prop(root,active_atom)
        if not isinstance(active,int) or not active or active==win:return 0
        hint=ClassHint()
        if not x.XGetClassHint(d,active,C.byref(hint)):return 0
        try:
            names=" ".join(C.string_at(p).decode("ascii","ignore").lower() for p in (hint.res_name,hint.res_class) if p)
        finally:
            for p in (hint.res_name,hint.res_class):
                if p:x.XFree(p)
        if "chrome" not in names and "chromium" not in names:return 0
        title=prop(active,title_atom) or prop(active,legacy_atom) or ""
        # El menú local ya tiene su propio botón; no duplicarlo.
        if isinstance(title,str) and title.startswith("ReyTV — Tu pantalla, tus reglas"):return 0
        return active

    def paint():
        # Iconos sin texto: Atrás, Inicio y Teclado. Contraste alto en 44 px.
        x.XSetForeground(d,gc,0x162745)
        x.XFillRectangle(d,win,gc,0,0,width,height)
        x.XSetForeground(d,gc,0x39547B)
        for xpos in (44,88):x.XDrawLine(d,win,gc,xpos,5,xpos,38)
        x.XSetForeground(d,gc,0xEDF5FF)
        for dy in (0,1):
            x.XDrawLine(d,win,gc,14,21+dy,33,21+dy)
            x.XDrawLine(d,win,gc,14,21+dy,21,14+dy)
            x.XDrawLine(d,win,gc,14,21+dy,21,28+dy)
            x.XDrawLine(d,win,gc,56,21+dy,66,13+dy)
            x.XDrawLine(d,win,gc,66,13+dy,76,21+dy)
        x.XDrawLine(d,win,gc,59,21,59,31)
        x.XDrawLine(d,win,gc,73,21,73,31)
        x.XDrawLine(d,win,gc,59,31,73,31)
        x.XDrawLine(d,win,gc,101,15,121,15)
        x.XDrawLine(d,win,gc,101,15,101,30)
        x.XDrawLine(d,win,gc,121,15,121,30)
        x.XDrawLine(d,win,gc,101,30,121,30)
        for xx in (106,111,116):
            x.XDrawLine(d,win,gc,xx,20,xx,22)
            x.XDrawLine(d,win,gc,xx,25,xx,27)
        x.XFlush(d)

    def send_keys(home):
        keys=[b"F8"] if home else [b"Alt_L",b"Left"]
        codes=[x.XKeysymToKeycode(d,x.XStringToKeysym(k)) for k in keys]
        if not all(codes):return
        for code in codes:fake(d,code,True,0)
        for code in reversed(codes):fake(d,code,False,0)
        x.XFlush(d)


    # El monitor solo escucha cambios de foco y estados editables; jamás lee el texto.
    # AT-SPI es opcional. Si no está disponible, el botón Teclado funciona igual.
    def monitor_focus():
        try:
            import gi
            gi.require_version("Atspi","2.0")
            from gi.repository import Atspi, GLib, Gio
            bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
            try:
                bus.call_sync("org.a11y.Bus","/org/a11y/bus","org.freedesktop.DBus.Properties","Set",
                    GLib.Variant("(ssv)",("org.a11y.Status","IsEnabled",GLib.Variant("b",True))),
                    None,Gio.DBusCallFlags.NONE,2000,None)
            except Exception:
                pass
            Atspi.init()
            def focused(event,*_):
                try:
                    obj=event.source
                    app=obj.get_application()
                    if not app or not any(name in (app.get_name() or "").lower() for name in ("chrome","chromium")):
                        return
                    if not event.detail1:
                        focus_events.put((False,None));return
                    states=obj.get_state_set()
                    editable=bool(states and states.contains(Atspi.StateType.EDITABLE))
                    bounds=None
                    if editable:
                        try:
                            rect=obj.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
                            if rect.width>0 and rect.height>0:bounds=(rect.x,rect.y,rect.width,rect.height)
                        except Exception:pass
                    focus_events.put((editable,bounds))
                except Exception:
                    pass
            listener=Atspi.EventListener.new(focused,None)
            if listener.register("object:state-changed:focused"):
                GLib.MainLoop().run()
        except Exception:
            return

    def geometry():
        sw,sh=last_size or (x.XDisplayWidth(d,screen),x.XDisplayHeight(d,screen))
        w=min(1000,max(310,int(sw*.76)));h=min(300,max(170,int(sh*.40)))
        top=field_y is not None and field_y>sh*.61
        return ((sw-w)//2,18 if top else max(0,sh-h-70),w,h)

    def rows():
        if key_mode=="symbol":
            return ["1234567890","@._-/:+!?#","%&*=$()[];","SHIFT|ABC|SPACE|DEL|ENTER|DONE"]
        if key_mode=="extra":
            return ["<>,;:'\"\\|","^~{}!?_+-=","0123456789","SHIFT|ABC|SPACE|DEL|ENTER|DONE"]
        chars=["qwertyuiop","asdfghjklñ","zxcvbnm"]
        if key_mode=="upper":chars=[row.upper() for row in chars]
        return chars+["SHIFT|123|SPACE|DEL|ENTER|DONE"]

    def cells():
        _,_,w,h=key_rect
        result=[];gap=6;top=36;rh=max(24,(h-top-12)//4)
        for index,row in enumerate(rows()):
            keys=row.split("|") if index==3 else list(row)
            cw=(w-24-gap*(len(keys)-1))//len(keys)
            offset=(w-(cw*len(keys)+gap*(len(keys)-1)))//2
            for i,key in enumerate(keys):
                result.append((key,offset+i*(cw+gap),top+index*rh,cw,rh-gap))
        return result

    def key_at(px,py):
        return next((key for key,l,t,w,h in cells() if l<=px<l+w and t<=py<t+h),None)

    def paint_keyboard():
        _,_,w,h=key_rect
        x.XSetForeground(d,kgc,0x101e39);x.XFillRectangle(d,kw,kgc,0,0,w,h)
        x.XSetForeground(d,kgc,0xB9CEF5)
        label=b"TECLADO REYTV  -  Escribe en la aplicacion"
        x.XDrawString(d,kw,kgc,14,24,label,len(label))
        labels={"SHIFT":"Mayus","123":"123 / #","ABC":"ABC","SPACE":"Espacio","DEL":"Borrar","ENTER":"Intro / Ir","DONE":"Cerrar","MORE":"Simbolos"}
        for key,l,t,cw,ch in cells():
            x.XSetForeground(d,kgc,0x466EAD if key==key_pressed or key in ("ENTER","DONE") else 0x253D66)
            x.XFillRectangle(d,kw,kgc,l,t,cw,ch)
            x.XSetForeground(d,kgc,0xF0F6FF)
            txt=labels.get(key,key).encode("latin-1")
            x.XDrawString(d,kw,kgc,max(l+4,l+(cw-len(txt)*9)//2),t+ch//2+6,txt,len(txt))
        x.XFlush(d)

    def hide_keyboard():
        nonlocal key_open,key_pressed
        if key_open:x.XUnmapWindow(d,kw)
        key_open=False;key_pressed=None

    def show_keyboard():
        nonlocal key_open,key_rect,key_mode,opened_at
        if not browser_window():return
        if not key_open:key_mode="lower";opened_at=time.monotonic()
        key_rect=geometry()
        x.XMoveResizeWindow(d,kw,*key_rect)
        x.XMapRaised(d,kw);key_open=True;paint_keyboard()

    def key_event(key):
        nonlocal key_mode
        if key=="DONE":hide_keyboard();return
        if key=="SHIFT":
            key_mode={"lower":"upper","upper":"lower","symbol":"extra","extra":"symbol"}[key_mode];paint_keyboard();return
        if key=="123":key_mode="symbol";paint_keyboard();return
        if key=="ABC":key_mode="lower";paint_keyboard();return
        if not browser_window():hide_keyboard();return
        special={"SPACE":b"space","DEL":b"BackSpace","ENTER":b"Return"}
        if key in special:
            code=x.XKeysymToKeycode(d,x.XStringToKeysym(special[key]))
            if code:fake(d,code,True,0);fake(d,code,False,0)
        else:
            # Usar el mapa XKB existente (base, Shift, AltGr), sin tocar el portapapeles.
            sym=ord(key)
            shift=x.XKeysymToKeycode(d,x.XStringToKeysym(b"Shift_L"))
            altgr=x.XKeysymToKeycode(d,x.XStringToKeysym(b"ISO_Level3_Shift"))
            match=None
            for level in range(4):
                if level&1 and not shift or level&2 and not altgr:continue
                for code in range(8,256):
                    if x.XkbKeycodeToKeysym(d,code,0,level)==sym:
                        match=(code,level);break
                if match:break
            if match:
                code,level=match
                modifiers=([altgr] if level&2 else [])+([shift] if level&1 else [])
                for mod in modifiers:fake(d,mod,True,0)
                fake(d,code,True,0);fake(d,code,False,0)
                for mod in reversed(modifiers):fake(d,mod,False,0)
        x.XFlush(d)
        if key=="ENTER":hide_keyboard()

    threading.Thread(target=monitor_focus,daemon=True).start()

    try:
        while os.getppid()==parent:
            active=browser_window()
            size=(x.XDisplayWidth(d,screen),x.XDisplayHeight(d,screen))
            if size!=last_size:
                x.XMoveWindow(d,win,max(0,size[0]-width-14),14)
                last_size=size
                if key_open:show_keyboard()
            # La esquina funciona como zona de activación; no hay ventana
            # invisible que intercepte clics sobre las aplicaciones.
            rr=U();ch=U();rx=I();ry=I();wx=I();wy=I();mask=C.c_uint()
            pointer_ok=bool(x.XQueryPointer(d,root,C.byref(rr),C.byref(ch),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask)))
            near=pointer_ok and rx.value>=size[0]-175 and ry.value<=75 and rx.value<size[0] and ry.value>=0
            if active and near:
                if hover_since is None:hover_since=time.monotonic()
                if time.monotonic()-hover_since>=.17:
                    if not mapped:
                        x.XMapRaised(d,win);mapped=True;paint();last_raise=time.monotonic()
                    elif time.monotonic()-last_raise>=.5:
                        x.XRaiseWindow(d,win);last_raise=time.monotonic()
            else:
                hover_since=None
                if mapped:
                    x.XUnmapWindow(d,win);mapped=False;pressed=None
            if active!=last_window:pressed=None;hide_keyboard();last_window=active;field_bounds=None;field_y=None
            latest=None
            while not focus_events.empty():latest=focus_events.get_nowait()
            if latest is not None and active:
                editable,field_bounds=latest
                field_y=field_bounds[1]+field_bounds[3]/2 if field_bounds else None
                if editable:show_keyboard()
                else:hide_keyboard()
            # Reabrir al volver a pulsar un campo editable que conserva el foco.
            # No observar el teclado físico, solo el estado del botón del ratón.
            if active:
                rr=U();ch=U();rx=I();ry=I();wx=I();wy=I();mask=C.c_uint()
                if x.XQueryPointer(d,root,C.byref(rr),C.byref(ch),C.byref(rx),C.byref(ry),C.byref(wx),C.byref(wy),C.byref(mask)):
                    down=bool(mask.value&(1<<8));kx,ky,ww,hh=key_rect
                    over_key=key_open and kx<=rx.value<kx+ww+2 and ky<=ry.value<ky+hh+2
                    over_bar=mapped and size[0]-width-14<=rx.value<size[0]-14 and 14<=ry.value<14+height
                    on_field=False
                    if field_bounds:
                        fx,fy,fw,fh=field_bounds;on_field=fx<=rx.value<fx+fw and fy<=ry.value<fy+fh
                    if down and not mouse_down and not over_key and not over_bar:
                        if not key_open and on_field:show_keyboard()
                        elif key_open and not on_field and time.monotonic()-opened_at>.4:hide_keyboard()
                    mouse_down=down
            else:mouse_down=False
            if key_open:x.XRaiseWindow(d,kw)
            while x.XPending(d):
                x.XNextEvent(d,C.byref(event))
                if event.type==12:
                    # XExpose.window ocupa el mismo offset que XButtonEvent.window.
                    if event.button.window==kw and key_open:paint_keyboard()
                    elif event.button.window==win and mapped:paint()
                elif event.type==4 and event.button.button==1:
                    if event.button.window==kw and key_open:
                        key_pressed=key_at(event.button.x,event.button.y);paint_keyboard()
                    else:pressed=min(2,event.button.x//44) if mapped and active and event.button.window==win else None
                elif event.type==5 and event.button.button==1:
                    b=event.button
                    if b.window==kw and key_open:
                        key=key_at(b.x,b.y)
                        if key and key==key_pressed and browser_window()==active:key_event(key)
                        key_pressed=None
                        if key_open:paint_keyboard()
                    elif pressed is not None and mapped and 0<=b.x<width and 0<=b.y<height and pressed==min(2,b.x//44) and browser_window()==active:
                        if pressed==2:
                            if key_open:hide_keyboard()
                            else:show_keyboard()
                        else:
                            hide_keyboard();send_keys(pressed==1)
                    pressed=None
            x.XFlush(d)
            time.sleep(.05)
    finally:
        if font:x.XUnloadFont(d,font)
        x.XFreeGC(d,kgc);x.XDestroyWindow(d,kw)
        x.XFreeGC(d,gc);x.XDestroyWindow(d,win);x.XCloseDisplay(d)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mouse-overlay", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--app-dir", type=Path,
                        default=Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "reytv")
    parser.add_argument("--state-dir", type=Path,
                        default=Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "reytv")
    parser.add_argument("--bin-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if args.mouse_overlay:
        mouse_overlay()
        return
    server = ReyTVServer(("127.0.0.1", args.port), args.app_dir, args.bin_dir, args.state_dir)
    overlay = None
    if os.environ.get("REYTV_TV_PID", "").isdigit() and os.environ.get("DISPLAY"):
        try:
            overlay = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--mouse-overlay"])
        except OSError as exc:
            print("ReyTV: no se pudo iniciar la ayuda del puntero:", exc, file=sys.stderr)
    print(f"ReyTV escuchando en http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if overlay is not None:
            overlay.terminate()
            try:
                overlay.wait(timeout=2)
            except subprocess.TimeoutExpired:
                overlay.kill()
                overlay.wait()
    if server.restart_requested:
        os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()),
                 "--port", str(args.port), "--app-dir", str(args.app_dir),
                 "--state-dir", str(args.state_dir), "--bin-dir", str(args.bin_dir)])


if __name__ == "__main__":
    main()

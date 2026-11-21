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
        ("XMoveWindow",I,[P,U,I,I]),("XDestroyWindow",I,[P,U]),
        ("XPending",I,[P]),("XNextEvent",I,[P,C.POINTER(Event)]),
        ("XSetForeground",I,[P,P,U]),("XFillRectangle",I,[P,U,P,I,I,C.c_uint,C.c_uint]),
        ("XDrawLine",I,[P,U,P,I,I,I,I]),("XDrawString",I,[P,U,P,I,I,C.c_char_p,I]),
        ("XFlush",I,[P]),("XStringToKeysym",U,[C.c_char_p]),("XKeysymToKeycode",C.c_ubyte,[P,U]),
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
    width,height=148,44
    win=x.XCreateSimpleWindow(d,root,0,0,width,height,1,0x839DD0,0x162745)
    attrs=Attributes();attrs.override_redirect=1
    x.XChangeWindowAttributes(d,win,1<<9,C.byref(attrs))
    x.XStoreName(d,win,b"ReyTV mouse navigation")
    x.XSelectInput(d,win,(1<<15)|(1<<2)|(1<<3))
    gc=x.XCreateGC(d,win,0,None)
    event=Event()
    mapped=False;pressed=None;last_window=0;last_size=None
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
        x.XSetForeground(d,gc,0x162745);x.XFillRectangle(d,win,gc,0,0,width,height)
        x.XSetForeground(d,gc,0x324D80);x.XDrawLine(d,win,gc,75,6,75,37)
        x.XSetForeground(d,gc,0xE9F1FF)
        for dy in (0,1):
            x.XDrawLine(d,win,gc,12,22+dy,26,22+dy)
            x.XDrawLine(d,win,gc,12,22+dy,18,16+dy)
            x.XDrawLine(d,win,gc,12,22+dy,18,28+dy)
            x.XDrawLine(d,win,gc,85,21+dy,92,14+dy)
            x.XDrawLine(d,win,gc,92,14+dy,99,21+dy)
        x.XDrawLine(d,win,gc,87,21,87,30);x.XDrawLine(d,win,gc,97,21,97,30)
        x.XDrawLine(d,win,gc,87,30,97,30)
        for text,xx in [(b"Atras",31),(b"Inicio",105)]:
            x.XDrawString(d,win,gc,xx,26,text,len(text))
        x.XFlush(d)

    def send_keys(home):
        keys=[b"F8"] if home else [b"Alt_L",b"Left"]
        codes=[x.XKeysymToKeycode(d,x.XStringToKeysym(k)) for k in keys]
        if not all(codes):return
        for code in codes:fake(d,code,True,0)
        for code in reversed(codes):fake(d,code,False,0)
        x.XFlush(d)

    try:
        while os.getppid()==parent:
            active=browser_window()
            size=(x.XDisplayWidth(d,screen),x.XDisplayHeight(d,screen))
            if size!=last_size:
                x.XMoveWindow(d,win,max(0,size[0]-width-18),max(0,size[1]-height-18))
                last_size=size
            if active:
                if not mapped:
                    x.XMapRaised(d,win);mapped=True;paint()
                else:x.XRaiseWindow(d,win)
            elif mapped:
                x.XUnmapWindow(d,win);mapped=False;pressed=None
            if active!=last_window:pressed=None;last_window=active
            while x.XPending(d):
                x.XNextEvent(d,C.byref(event))
                if event.type==12 and mapped:paint()
                elif event.type==4 and event.button.button==1:
                    pressed=(event.button.x>=76) if mapped and active else None
                elif event.type==5 and event.button.button==1:
                    b=event.button
                    if pressed is not None and mapped and 0<=b.x<width and 0<=b.y<height and pressed==(b.x>=76) and browser_window()==active:
                        send_keys(pressed)
                    pressed=None
            x.XFlush(d)
            time.sleep(.05)
    finally:
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

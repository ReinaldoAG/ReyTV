#!/usr/bin/env python3
"""Servidor local de ReyTV y actualización de la interfaz sin permisos de root.

Solo escucha 127.0.0.1 y acepta acciones del propio menú ReyTV.
No ejecuta comandos arbitrarios enviados por HTTP.
"""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
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
                             "revision": self._current_sha(), "version": self._version()})
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
        if path not in ("/api/check", "/api/update", "/api/rollback"):
            self._send(404, {"error": "Acción desconocida"})
            return
        # Los sitios externos no pueden solicitar una actualización mediante
        # formularios ni JavaScript: exigimos origen correcto y un token efímero.
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if (not self._local_host() or self.headers.get("Origin") != origin
                or not secrets.compare_digest(self.headers.get("X-ReyTV-Token", ""), self.server.csrf)
                or self.headers.get("Content-Length", "0") not in ("0", "2")):
            self._send(403, {"error": "Solicitud no autorizada"})
            return
        if not self.server.action_lock.acquire(blocking=False):
            self._send(409, {"error": "Ya se está realizando otra operación"})
            return
        try:
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
                                 "installed": self._current_sha()})
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
        except subprocess.TimeoutExpired:
            self._send(504, {"error": "La operación tardó demasiado; prueba de nuevo más tarde"})
        except OSError:
            self._send(503, {"error": "Herramientas de actualización no disponibles"})
        finally:
            self.server.action_lock.release()

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--app-dir", type=Path,
                        default=Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "reytv")
    parser.add_argument("--state-dir", type=Path,
                        default=Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "reytv")
    parser.add_argument("--bin-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    server = ReyTVServer(("127.0.0.1", args.port), args.app_dir, args.bin_dir, args.state_dir)
    print(f"ReyTV escuchando en http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

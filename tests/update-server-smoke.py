#!/usr/bin/env python3
"""Prueba HTTP de actualización y rollback sin red ni permisos de root."""

from contextlib import contextmanager
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reytv_server", ROOT / "linux/reytv-server.py")
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


def git(*args):
    return subprocess.run(["git", *map(str, args)], check=True, capture_output=True, text=True)


@contextmanager
def test_environment(root):
    env = {"HOME": str(root / "home"), "XDG_DATA_HOME": str(root / "data"),
           "XDG_STATE_HOME": str(root / "state"), "XDG_CACHE_HOME": str(root / "cache")}
    old = {key: os.environ.get(key) for key in env}
    try:
        os.environ.update(env)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main():
    with tempfile.TemporaryDirectory(prefix="reytv-http-test-") as tmp:
        root = Path(tmp)
        source, app, state, bin_dir = (root / "source", root / "data/reytv",
                                       root / "state/reytv", root / "bin")
        for directory in (source, app, state, bin_dir, root / "home"):
            directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "linux/reytv-update", bin_dir / "reytv-update")
        shutil.copy2(ROOT / "linux/reytv-rollback", bin_dir / "reytv-rollback")
        for name in ("reytv-update", "reytv-rollback"):
            (bin_dir / name).chmod(0o755)
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        (source / "index.html").write_text(html, encoding="utf-8")
        (app / "index.html").write_text(html, encoding="utf-8")
        git("init", "-q", "-b", "main", source)
        git("-C", source, "add", "index.html")
        git("-C", source, "-c", "user.name=Test", "-c", "user.email=test@local.invalid",
            "commit", "-qm", "Initial")

        with test_environment(root):
            previous_repo = server_module.REPOSITORY
            server_module.REPOSITORY = str(source)
            server = server_module.ReyTVServer(("127.0.0.1", 0), app, bin_dir, state)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = f"http://127.0.0.1:{server.server_port}"

            def get(path):
                with request.urlopen(url + path, timeout=5) as response:
                    return response.status, response.read()

            def post(path, token=None):
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["X-ReyTV-Token"] = token
                    headers["Origin"] = url
                req = request.Request(url + path, data=b"{}", method="POST", headers=headers)
                try:
                    with request.urlopen(req, timeout=30) as response:
                        return response.status, json.load(response)
                except error.HTTPError as exc:
                    return exc.code, json.load(exc)

            try:
                status, payload = get("/api/status")
                assert status == 200
                token = json.loads(payload)["token"]
                assert get("/")[1].startswith(b"<!doctype html>")
                hostile = request.Request(url + "/api/status", headers={"Host": "evil.example"})
                try:
                    request.urlopen(hostile, timeout=5)
                    raise AssertionError("Un host no local no puede consultar el API")
                except error.HTTPError as exc:
                    assert exc.code == 403
                assert post("/api/update")[0] == 403
                assert post("/api/update", "invalid")[0] == 403

                modified = html.replace("ReyTV · 0.2.1", "ReyTV · 0.2.2")
                assert modified != html
                (source / "index.html").write_text(modified, encoding="utf-8")
                git("-C", source, "add", "index.html")
                git("-C", source, "-c", "user.name=Test", "-c", "user.email=test@local.invalid",
                    "commit", "-qm", "Update")
                assert post("/api/check", token)[1]["available"]
                assert post("/api/update", token)[1]["ok"]
                assert b"ReyTV \xc2\xb7 0.2.2" in get("/index.html")[1]
                assert not post("/api/check", token)[1]["available"]
                assert post("/api/rollback", token)[1]["ok"]
                assert b"ReyTV \xc2\xb7 0.2.1" in get("/index.html")[1]
                assert post("/api/check", token)[1]["available"]
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
                server_module.REPOSITORY = previous_repo

    print("HTTP ReyTV: autorización, actualización y rollback OK.")


if __name__ == "__main__":
    main()

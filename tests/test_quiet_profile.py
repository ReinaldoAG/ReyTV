"""Prueba de preferencias aisladas y permiso real de Chromium."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("server",ROOT/"linux/reytv-server.py")
server=importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)/"tv"
    default=root/"Default"
    default.mkdir(parents=True)
    path=default/"Preferences"
    original={"profile":{"default_content_setting_values":{"notifications":1,"geolocation":3},
        "content_settings":{"exceptions":{"notifications":{"https://example.test:443,*":{"setting":1}},"cookies":{"test":{"setting":1}}}}},
        "bookmark_bar":{"show_on_all_tabs":True}}
    path.write_text(json.dumps(original))
    lock=root/"SingletonLock"
    lock.symlink_to(socket.gethostname()+"-"+str(os.getpid()))
    assert not server.quiet_tv_profile(root)
    assert json.loads(path.read_text())==original
    lock.unlink()
    assert server.quiet_tv_profile(root)
    prefs=json.loads(path.read_text())
    assert prefs["profile"]["default_content_setting_values"]=={"notifications":2,"geolocation":3}
    assert "notifications" not in prefs["profile"]["content_settings"]["exceptions"]
    assert prefs["profile"]["content_settings"]["exceptions"]["cookies"]==original["profile"]["content_settings"]["exceptions"]["cookies"]
    assert prefs["bookmark_bar"]==original["bookmark_bar"]
    with sync_playwright() as p:
        ctx=p.chromium.launch_persistent_context(str(root),headless=True)
        page=ctx.pages[0]
        page.route("https://example.test/**",lambda route:route.fulfill(body="<html>Prueba</html>",content_type="text/html"))
        page.goto("https://example.test/")
        assert page.evaluate("Notification.permission")=="denied"
        assert page.evaluate("Notification.requestPermission()")=="denied"
        assert not server.quiet_tv_profile(root)
        ctx.close()
print("Notificaciones bloqueadas en Chromium, perfil activo protegido, otros ajustes preservados.")

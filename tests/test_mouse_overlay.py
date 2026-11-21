"""Verifica una superposición X11 real en Chromium, sin acceso a Internet."""
from pathlib import Path
import os
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TITLE = "ReyTV mouse navigation"

def cmd(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()

def overlay_id():
    try:
        return cmd("xdotool", "search", "--onlyvisible", "--name", "^"+TITLE+"$").splitlines()[0]
    except (subprocess.CalledProcessError, IndexError):
        return None

def wait_until(page, condition, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = condition()
        if value:
            return value
        page.wait_for_timeout(100)
    raise AssertionError("No se cumplió condición X11")

def main():
    wm = subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    overlay = None
    try:
        time.sleep(.5)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--kiosk", "--ozone-platform=x11"])
            page = browser.new_page(no_viewport=True)
            def route(r):
                title = "ReyTV — Tu pantalla, tus reglas" if "/index.html" in r.request.url else "Servicio externo"
                r.fulfill(body="<title>"+title+"</title><h1>"+title+"</h1><script>window.homePressed=false;addEventListener('keydown',e=>{if(e.key==='F8')window.homePressed=true;});</script>", content_type="text/html; charset=utf-8")
            page.route("**/*", route)
            page.goto("http://127.0.0.1:18763/index.html")
            page.bring_to_front()
            wait_until(page, lambda: "ReyTV" in cmd("xdotool","getactivewindow","getwindowname"))
            overlay = subprocess.Popen([sys.executable, str(ROOT/"linux/reytv-server.py"), "--mouse-overlay"])
            page.wait_for_timeout(500)
            assert not overlay_id(), "No debe duplicar el botón en ReyTV"
            page.goto("https://example.test/first")
            page.goto("https://example.test/second")
            window = wait_until(page, overlay_id)
            active_before = cmd("xdotool","getactivewindow")
            cmd("xdotool","mousemove","--window",window,"30","20","click","1")
            page.wait_for_url("**/first")
            assert cmd("xdotool","getactivewindow")==active_before, "No tomar foco"
            window=wait_until(page,overlay_id)
            cmd("xdotool","mousemove","--window",window,"110","20","click","1")
            page.wait_for_function("window.homePressed===true")
            window=wait_until(page,overlay_id)
            cmd("xdotool","mousemove","--window",window,"30","20","click","1")
            page.wait_for_url("**/index.html")
            wait_until(page,lambda:not overlay_id())
            browser.close()
        print("Superposición X11: atrás, inicio, foco y ocultamiento local correctos.")
    finally:
        if overlay:
            overlay.terminate()
            overlay.wait(timeout=5)
        wm.terminate()
        wm.wait(timeout=5)

if __name__=="__main__":
    main()

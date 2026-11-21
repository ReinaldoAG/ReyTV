"""Verifica una superposición X11 real en Chromium, sin acceso a Internet."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import time
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
TITLE = "ReyTV mouse navigation"

def cmd(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()

def overlay_id(title=TITLE):
    try:
        return cmd("xdotool", "search", "--onlyvisible", "--name", "^"+title+"$").splitlines()[0]
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
    fixture = tempfile.TemporaryDirectory()
    marker = Path(fixture.name) / "home-called"
    config = Path(fixture.name) / "openbox.xml"
    # La sesión real captura F8 en Openbox, no en el DOM de Chromium.
    xml = (ROOT/"linux/openbox-tv.xml").read_text()
    config.write_text(xml.replace("/usr/local/bin/reytv-tv-session --home", "touch "+str(marker)))
    wm = subprocess.Popen(["openbox","--config-file",str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    overlay = None
    try:
        time.sleep(.5)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, args=["--kiosk", "--ozone-platform=x11"])
            page = browser.new_page(no_viewport=True)
            def route(r):
                title = "ReyTV — Tu pantalla, tus reglas" if "/index.html" in r.request.url else "Servicio externo"
                r.fulfill(body="<title>"+title+"</title><h1>"+title+"</h1><input id=entry aria-label=Email><script>window.homePressed=false;addEventListener('keydown',e=>{if(e.key==='F8')window.homePressed=true;});</script>", content_type="text/html; charset=utf-8")
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
            # Teclado externo sin alterar el foco, con escritura real en un formulario.
            page.locator("#entry").click()
            window=wait_until(page,overlay_id)
            cmd("xdotool","mousemove","--window",window,"190","20","click","1")
            keyboard=wait_until(page,lambda:overlay_id("ReyTV external keyboard"))
            def key(row,col,count):
                info=cmd("xdotool","getwindowgeometry","--shell",keyboard)
                vals=dict(line.split("=",1) for line in info.splitlines() if "=" in line)
                w,h=int(vals["WIDTH"]),int(vals["HEIGHT"])
                gap=6;cw=(w-24-gap*(count-1))//count
                start=(w-(cw*count+gap*(count-1)))//2
                rh=max(24,(h-36-12)//4)
                cmd("xdotool","mousemove","--window",keyboard,str(start+col*(cw+gap)+cw//2),str(36+row*rh+(rh-gap)//2),"click","1")
                page.wait_for_timeout(130)
            key(1,0,10)
            key(3,0,6)
            key(0,1,10)
            key(3,1,6)
            key(0,1,10)
            key(1,0,10)
            page.wait_for_function("document.querySelector('#entry').value === 'aW2@'")
            assert cmd("xdotool","getactivewindow")==active_before
            key(3,5,6)
            wait_until(page,lambda:not overlay_id("ReyTV external keyboard"))
            cmd("xdotool","mousemove","--window",window,"190","20","click","1")
            keyboard=wait_until(page,lambda:overlay_id("ReyTV external keyboard"))
            key(3,4,6)
            wait_until(page,lambda:not overlay_id("ReyTV external keyboard"))
            window=wait_until(page,overlay_id)
            cmd("xdotool","mousemove","--window",window,"110","20","click","1")
            wait_until(page, marker.exists)
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
        fixture.cleanup()

if __name__=="__main__":
    main()

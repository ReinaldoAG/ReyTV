"""Valida que Chrome preserve cookies de un perfil dedicado entre reinicios limpios."""
from pathlib import Path
import tempfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
session=(ROOT/"linux/reytv-tv-session").read_text()
installer=(ROOT/"linux/reytv-gui-setup.sh").read_text()
assert "--hide-scrollbars" in session
assert '--user-data-dir="$PROFILE"' in session
assert "wait_child_shutdown" in session
assert "sudo install -m 0755" in installer
assert "/usr/local/bin/reytv-tv-session" in installer

with tempfile.TemporaryDirectory() as tmp, sync_playwright() as p:
    def launch():
        return p.chromium.launch_persistent_context(
            tmp, headless=False, args=["--ozone-platform=x11","--hide-scrollbars"],
            viewport={"width":950,"height":550})
    ctx=launch()
    page=ctx.pages[0]
    page.route("https://example.test/**",lambda route:route.fulfill(
        body="<html><body style='margin:0;height:200vh'>Sitio de prueba</body></html>",
        content_type="text/html"))
    page.goto("https://example.test/")
    assert page.evaluate("document.documentElement.scrollHeight>innerHeight")
    assert page.evaluate("document.documentElement.clientWidth==innerWidth"),"Scrollbar visible"
    page.evaluate("scrollTo(0,500)")
    assert page.evaluate("scrollY")>0, "La página debe poder desplazarse"
    ctx.add_cookies([{"name":"reytv_demo","value":"retained","domain":"example.test","path":"/",
                      "secure":True,"httpOnly":True,"expires":2000000000,"sameSite":"Lax"}])
    ctx.close()
    ctx=launch()
    cookies=ctx.cookies("https://example.test")
    assert any(c["name"]=="reytv_demo" and c["value"]=="retained" for c in cookies),cookies
    ctx.close()
print("Chrome: barras ocultas, scroll funcional y cookies persistentes entre cierres limpios.")

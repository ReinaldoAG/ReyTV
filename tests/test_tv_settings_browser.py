"""Prueba de interfaz en navegador real, con API y dispositivos simulados."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text()
STATUS = {"ready": True, "token": "test", "version": "0.4.5", "full_update": True}
NATIVE = {
    "wifi": {"available": True, "enabled": True, "connected": "Red de prueba",
             "ipv4": "192.168.1.20", "interface": "wlan0",
             "networks": [{"name": "Red de prueba", "active": True, "signal": 80, "security": "WPA2"},
                          {"name": "Otra red", "active": False, "signal": 60, "security": "WPA2"}] +
                         [{"name": f"Red {i}", "active": False, "signal": 40, "security": "WPA2"} for i in range(28)]},
    "bluetooth": {"available": True, "enabled": True, "devices": []},
    "sound": {"available": True, "percent": 50, "muted": False},
}

def test(browser, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    def route(r):
        url = r.request.url
        if "/api/native/status" in url:
            r.fulfill(json=NATIVE)
        elif "/api/status" in url:
            r.fulfill(json=STATUS)
        elif "/api/check" in url:
            r.fulfill(json={"available": True, "revision": "a"*40})
        elif "/api/native/action" in url:
            r.fulfill(json={"ok": True})
        elif "/index.html" in url:
            r.fulfill(body=HTML, content_type="text/html; charset=utf-8")
        else:
            r.fulfill(status=404, body="")
    page.route("**/*", route)
    page.goto("http://127.0.0.1:18763/index.html?tv=1")
    page.locator('[data-page="ajustes"]').click()
    page.locator("#native-wifi-toggle").wait_for()
    page.wait_for_function("!document.getElementById('native-wifi-toggle').disabled")
    assert page.locator(".settings-category").count() == 5
    assert page.locator(".native-panel:visible").count() == 1
    assert page.locator("#native-wifi-details").inner_text().find("192.168.1.20") >= 0
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert page.locator('[data-native-panel="bluetooth"]').is_visible()
    assert not page.locator('[data-native-panel="wifi"]').is_visible()
    page.keyboard.press("Escape")
    assert page.locator('[data-settings-category="bluetooth"]').evaluate("(el)=>document.activeElement===el")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert page.locator("#native-sound-info").inner_text() == "Volumen: 50%"
    page.keyboard.press("Escape")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert page.locator("#settings-version").inner_text() == "0.4.5"
    page.locator("#check-update").click()
    page.wait_for_function("!document.getElementById('apply-update').disabled")
    assert not page.locator("#native-settings").is_visible()
    page.locator('[data-settings-category="wifi"]').click()
    page.get_by_role("button", name="Otra red", exact=False).click()
    assert page.locator("#native-pass").is_visible()
    assert page.locator("#native-keys button").first.evaluate("(el)=>document.activeElement===el")
    page.keyboard.press("Enter")
    assert len(page.locator("#keyboard-value").input_value()) == 1
    page.locator("#keyboard-done").click()
    assert not page.locator("#screen-keyboard").is_visible()
    assert len(page.locator("#native-pass").input_value()) == 1
    page.locator("#back-button").click()
    assert not page.locator("#modal").is_visible()

    # El documento no se desplaza; solo el panel desbordado.
    stage = page.locator(".settings-stage")
    assert stage.evaluate("(el)=>el.scrollHeight > el.clientHeight")
    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1")
    box = stage.bounding_box()
    x, y, h = box["x"] + box["width"] * .82, box["y"], box["height"]
    page.mouse.move(x, y + h*.5)
    stage.evaluate("(el)=>el.scrollTop=0")
    page.wait_for_timeout(650)
    assert stage.evaluate("(el)=>el.scrollTop") == 0
    page.mouse.move(x, y + h*.82)
    page.wait_for_timeout(850)
    slow = stage.evaluate("(el)=>el.scrollTop")
    assert slow > 0, slow
    page.mouse.move(x, y + h*.5)
    stage.evaluate("(el)=>el.scrollTop=0")
    page.mouse.move(x, y + h*.96)
    page.wait_for_timeout(850)
    fast = stage.evaluate("(el)=>el.scrollTop")
    assert fast > slow * 2, (fast, slow)
    page.mouse.move(x, y + h*.5)
    stopped = stage.evaluate("(el)=>el.scrollTop")
    page.wait_for_timeout(400)
    assert stage.evaluate("(el)=>el.scrollTop") == stopped

    # El teclado universal sirve también para buscar y añadir servicios.
    page.locator('[data-page="aplicaciones"]').click()
    assert page.locator("#apps .app-wrap").count() == 8
    assert page.locator("#app-next").is_visible()
    page.locator("#app-next").click()
    assert page.locator(".utility-card").is_visible()
    page.locator(".utility-card").click()
    assert page.locator("#screen-keyboard").is_visible()
    page.keyboard.type("Prueba")
    page.locator("#keyboard-done").click()
    assert page.locator("#custom-name").input_value() == "Prueba"
    assert page.locator("#screen-keyboard").is_visible()
    page.keyboard.type("https://example.org")
    page.locator("#keyboard-done").click()
    assert page.locator("#custom-url").input_value() == "https://example.org"
    assert not page.locator("#screen-keyboard").is_visible()
    page.locator("#add-form button[type=submit]").click()
    page.locator("#search").click()
    assert page.locator("#screen-keyboard").is_visible()
    page.keyboard.type("netflix")
    assert page.locator("#keyboard-done").inner_text() == "Buscar"
    page.locator("#keyboard-done").click()
    assert not page.locator("#screen-keyboard").is_visible()
    assert page.locator("#apps .app-card").count() == 1
    assert page.locator("#apps .app-card").inner_text().find("Netflix") >= 0
    assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 1")
    page.locator("#back-button").click()
    assert page.locator("#search").input_value() == ""
    page.locator("#search").click()
    assert page.locator("#screen-keyboard").is_visible()
    page.locator("#back-button").click()
    assert not page.locator("#screen-keyboard").is_visible()
    page.locator('[data-page="favoritos"]').click()
    page.locator("#back-button").click()
    assert page.locator('[data-page="aplicaciones"]').get_attribute("aria-current") == "page"
    assert not errors, errors
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for size in ((1280, 720), (1920, 1080), (1366, 768)):
        test(browser, *size)
    browser.close()
print("Ajustes TV: navegación, Wi-Fi, sonido, actualizaciones y teclado virtual correctos.")

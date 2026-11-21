"""API HTTP real: aislamiento por Host, Origin y token."""
import http.client
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
from subprocess import CompletedProcess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reytv_server", ROOT / "linux" / "reytv-server.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        app, bin_dir, state = [base / name for name in ("app", "bin", "state")]
        for folder in (app, bin_dir, state):
            folder.mkdir()
        (app / "index.html").write_text("<title>ReyTV</title> ReyTV · 0.4.0</html>")
        shutil.copyfile(ROOT / "linux" / "reytv-native.py", bin_dir / "reytv-native.py")
        self.server = mod.ReyTVServer(("127.0.0.1", 0), app, bin_dir, state)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=8)
        conn.request(method, path, body=json.dumps(data) if data is not None else None,
                     headers=headers or {})
        result = conn.getresponse()
        payload = json.loads(result.read())
        status = result.status
        conn.close()
        return status, payload

    def test_status_and_untrusted_requests(self):
        status, obj = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        token = obj["token"]
        self.assertTrue(token)
        body = {"operation": "sound_mute", "params": {"muted": True}}
        # Sin cabeceras de origen no se permite cambiar configuraciones.
        status, _ = self.request("POST", "/api/native/action", body)
        self.assertEqual(status, 403)
        headers = {"Origin": f"http://127.0.0.1:{self.port}", "X-ReyTV-Token": token}
        status, _ = self.request("POST", "/api/native/action", body, headers={**headers,"X-ReyTV-Token":"wrong"})
        self.assertEqual(status, 403)
        # Un comando desconocido se rechaza antes de ejecutar ningún subprocess.
        status, obj = self.request("POST", "/api/native/action",
                                   {"operation": "shell", "params": {}}, headers=headers)
        self.assertEqual(status, 400)
        self.assertIn("no permitida", obj["error"])

    def test_update_check_reports_full_update(self):
        _, status = self.request("GET", "/api/status")
        headers = {"Origin": f"http://127.0.0.1:{self.port}", "X-ReyTV-Token": status["token"]}
        with patch.object(mod.ReyTVHandler, "_run", return_value=CompletedProcess([], 0, "a"*40+"\trefs/heads/main\n", "")):
            code, info = self.request("POST", "/api/check", {}, headers=headers)
        self.assertEqual(code, 200)
        self.assertTrue(info["available"])
        self.assertTrue(info["full_update"])

    def test_native_status_read_only(self):
        status, obj = self.request("GET", "/api/native/status")
        self.assertEqual(status, 200)
        self.assertIn("wifi", obj)
        self.assertIn("bluetooth", obj)
        self.assertIn("sound", obj)


if __name__ == "__main__":
    unittest.main()

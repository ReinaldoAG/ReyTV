import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location("server",Path(__file__).resolve().parents[1]/"linux/reytv-server.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class PerformanceTests(unittest.TestCase):
    def test_cpu_delta(self):
        self.assertEqual(mod.cpu_percent((100,60),(200,140)),20)
        self.assertIsNone(mod.cpu_percent((100,60),(100,60)))
        self.assertEqual(mod.cpu_percent((100,60),(200,200)),0)
    def test_memory(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"meminfo"
            p.write_text("MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\nSwapTotal: 102400 kB\nSwapFree: 51200 kB\n")
            result=mod.memory_snapshot(p)
            self.assertEqual(result["percent"],50)
            self.assertEqual(result["total_mib"],2000)
            self.assertEqual(result["swap_used_mib"],50)
    def test_profile_health_without_reading_cookies(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {"XDG_CONFIG_HOME":d}):
            config=Path(d)/"reytv"
            profile=config/"chrome-profile"/"Default"/"Network"
            profile.mkdir(parents=True)
            (profile/"Cookies").write_bytes(b"fake-no-real-secrets")
            (config/"tv-password-store-basic").touch()
            status=mod.browser_profile_health()
            self.assertTrue(status["profile_writable"])
            self.assertTrue(status["cookies_database_present"])
            self.assertIn("Básico",status["password_storage"])
            self.assertNotIn("fake",repr(status))
    def test_snapshot(self):
        with patch.object(mod,"vaapi_snapshot",return_value={"h264":None}),patch.object(mod,"tv_browser",return_value="No verificado"):
            result=mod.performance_snapshot()
        self.assertIn("memory",result)
        self.assertIn("disk",result)
        self.assertIsNone(result["video"]["h264"])

if __name__=="__main__":
    unittest.main()

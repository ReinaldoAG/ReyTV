"""Pruebas que no requieren Bluetooth, Wi-Fi ni root."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch, Mock

FILE = Path(__file__).resolve().parents[1] / "linux" / "reytv-native.py"
spec = importlib.util.spec_from_file_location("reytv_native", FILE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class NativeTests(unittest.TestCase):
    def test_nm_escaped(self):
        self.assertEqual(mod._split_nm(r"*:Red\:2:80:WPA2"), ["*", "Red:2", "80", "WPA2"])

    def test_wifi_status(self):
        def fake(cmd, timeout=12):
            if "radio" in cmd:
                return "enabled\n"
            if "status" in cmd:
                return "wlp2s0:wifi:connected:MiCasa\n"
            return "*:MiCasa:87:WPA2\n :Invitados:50:--\n"
        with patch.object(mod, "_run", side_effect=fake):
            s = mod.wifi_status()
            self.assertEqual(s["connected"], "MiCasa")
            self.assertEqual(s["networks"][0]["name"], "MiCasa")

    def test_no_arbitrary_command_or_field(self):
        with self.assertRaises(mod.NativeError):
            mod.act("shell", {"command": "echo hi"})
        with self.assertRaises(mod.NativeError):
            mod.act("wifi_toggle", {"enabled": True, "extra": "oops"})
        with self.assertRaises(mod.NativeError):
            mod.act("bt_connect", {"address": "; touch /tmp/pwn"})

    def test_wifi_password_not_returned(self):
        with patch.object(mod, "_wifi_iface", return_value=("wlan0", "connected", "Home")), \
             patch.object(mod, "_run", return_value="ok") as run:
            self.assertEqual(mod.act("wifi_connect", {"ssid": "Home", "password": "MySecretPwd"})["ok"], True)
            self.assertIn("MySecretPwd", run.call_args.args[0])
        with patch.object(mod, "_wifi_iface", return_value=("wlan0", "connected", "Home")), \
             patch.object(mod, "_run", side_effect=mod.NativeError("No autorizado")):
            with self.assertRaises(mod.NativeError):
                mod.act("wifi_connect", {"ssid": "Home", "password": "MySecretPwd"})

    def test_sound_bounds(self):
        with self.assertRaises(mod.NativeError):
            mod.act("sound_volume", {"percent": 200})


if __name__ == "__main__":
    unittest.main()

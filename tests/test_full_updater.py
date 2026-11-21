"""Prueba integral sin red: instalar paquete, revertir HTML y servicios."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class FullUpdateTest(unittest.TestCase):
    def test_launcher_and_bootstrap_present(self):
        desktop = (ROOT / "Instalar-ReyTV.desktop").read_text()
        launcher = (ROOT / "linux/reytv-gui-setup.sh").read_text()
        self.assertIn("Type=Application", desktop)
        self.assertIn("Terminal=true", desktop)
        self.assertIn("reytv-gui-setup.sh", desktop)
        self.assertIn('linux/reytv-update', launcher)
        self.assertNotIn("sudo ", launcher)
        self.assertNotIn("sudo ", (ROOT / "linux/reytv-update").read_text())

    def test_install_rollback_user_space_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            home = root / "home"
            home.mkdir()
            app = home / ".local/share/reytv"
            bindir = home / ".local/bin"
            state = home / ".local/state/reytv"
            for path in (app, bindir, state):
                path.mkdir(parents=True)
            oldhtml = "<title>ReyTV antiguo</title>\n" + "a" * 4000 + "</html>"
            (app / "index.html").write_text(oldhtml)
            (bindir / "reytv-server.py").write_text("print('anterior')\n")
            (state / "current.sha").write_text("b" * 40 + "\n")
            source = root / "source"
            (source / "linux").mkdir(parents=True)
            for name in ("reytv-server.py", "reytv-native.py", "reytv-update", "reytv-rollback"):
                shutil.copyfile(ROOT / "linux" / name, source / "linux" / name)
            shutil.copyfile(ROOT / "index.html", source / "index.html")
            fakebin = root / "fakebin"
            fakebin.mkdir()
            git = fakebin / "git"
            git.write_text(
                "#!/bin/bash\n"
                "if [[ \"$1\" == clone ]]; then\n"
                "  for arg in \"$@\"; do last=\"$arg\"; done\n"
                "  mkdir -p \"$last/.git\"\n"
                "elif [[ \"$1\" == -C ]]; then\n"
                "  shift 2\n"
                "  if [[ \"$1\" == rev-parse ]]; then printf '%040d\\n' 1\n"
                "  elif [[ \"$1\" == show ]]; then rel=\"${2#*:}\"; cat \"$MOCK_SOURCE/$rel\"\n"
                "  elif [[ \"$1\" == fetch ]]; then :\n"
                "  elif [[ \"$1\" == remote ]]; then :\n"
                "  fi\n"
                "else exit 19\n"
                "fi\n")
            git.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "HOME": str(home),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "MOCK_SOURCE": str(source),
                "PATH": str(fakebin) + os.pathsep + os.environ["PATH"],
            })
            update = subprocess.run(["bash", str(ROOT / "linux/reytv-update"), "--force"],
                                    env=env, text=True, capture_output=True, timeout=25)
            self.assertEqual(update.returncode, 0, update.stderr + update.stdout)
            self.assertIn("0.4.6", (app / "index.html").read_text())
            self.assertIn("restart_requested", (bindir / "reytv-server.py").read_text())
            self.assertEqual((state / "previous-bundle/index.html").read_text(), oldhtml)
            self.assertFalse((home / ".config/reytv/chrome-profile").exists())
            undo = subprocess.run(["bash", str(bindir / "reytv-rollback")], env=env,
                                  text=True, capture_output=True, timeout=15)
            self.assertEqual(undo.returncode, 0, undo.stderr + undo.stdout)
            self.assertEqual((app / "index.html").read_text(), oldhtml)
            self.assertEqual((bindir / "reytv-server.py").read_text(), "print('anterior')\n")
            self.assertTrue((state / "blocked.sha").is_file())

if __name__ == "__main__":
    unittest.main()

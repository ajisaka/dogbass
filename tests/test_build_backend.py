from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import build_backend


class BuildBackendTests(unittest.TestCase):
    def test_build_editable_creates_pth_based_wheel(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wheel_name = build_backend.build_editable(tmpdir)
            wheel_path = Path(tmpdir) / wheel_name

            with zipfile.ZipFile(wheel_path) as wheel:
                names = set(wheel.namelist())
                pth_name = "dogbass-editable.pth"

                self.assertIn(pth_name, names)
                self.assertNotIn("dogbass/cli.py", names)
                self.assertNotIn("dogbass/markdown.py", names)

                editable_path = wheel.read(pth_name).decode("utf-8")
                self.assertEqual(editable_path, f"{build_backend.ROOT}\n")


if __name__ == "__main__":
    unittest.main()

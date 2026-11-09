import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import install_launcher


class LauncherTest(unittest.TestCase):
    def test_install_without_overwriting_existing_file(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'XDG_DATA_HOME': temp}):
            self.assertEqual(install_launcher.main(), 0)
            path = Path(temp) / 'applications/the-vigilant.desktop'
            self.assertIn('main.py', path.read_text())
            self.assertEqual(install_launcher.main(), 0)
            path.write_text('outro atalho')
            self.assertEqual(install_launcher.main(), 1)
            self.assertEqual(path.read_text(), 'outro atalho')


if __name__ == '__main__':
    unittest.main()

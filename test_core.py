import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import core


class CoreTests(unittest.TestCase):
    def test_domains(self):
        self.assertEqual(core.domain_from_input('https://WWW.YouTube.com/watch?v=1'), 'youtube.com')
        self.assertEqual(core.domain_from_input('youtube.com/path'), 'youtube.com')
        for bad in ('', 'localhost', 'https://user:pass@example.com', 'file:///etc/passwd', '127.0.0.1', '-bad.com', 'example.com:99999'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                core.domain_from_input(bad)

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'):
            self.assertEqual(core.load_data(), {'tasks': [], 'sites': [], 'apps': []})
            data = {'tasks': [{'text': 'Estudar', 'done': False}], 'sites': ['x.com'], 'apps': []}
            core.save_data(data)
            self.assertEqual(core.load_data(), data)
            core.DATA_FILE.write_text(json.dumps({'tasks': []}))
            with self.assertRaises(ValueError):
                core.load_data()


if __name__ == '__main__':
    unittest.main()

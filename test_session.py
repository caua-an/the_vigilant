import json
import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import core
from main import Vigilant


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requer uma sessão gráfica X11')
class SessionTest(unittest.TestCase):
    def test_session_and_last_task(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'):
            root = tk.Tk()
            root.withdraw()
            app = Vigilant(root)
            try:
                app.commit({'tasks': [{'text': 'Estudar', 'done': False}], 'sites': ['youtube.com'], 'apps': []})
                with patch.dict('os.environ', {'XDG_SESSION_TYPE': 'x11'}):
                    app.toggle_session()
                request = Request('http://127.0.0.1:47653/state', headers={'Origin': 'chrome-extension://test'})
                with urlopen(request) as response:
                    self.assertEqual(json.load(response)['domains'], ['youtube.com'])
                    self.assertEqual(response.headers['Access-Control-Allow-Origin'], 'chrome-extension://test')
                app.task_list.selection_set(0)
                with patch('main.messagebox.showinfo'):
                    app.toggle_task()
                self.assertFalse(app.active)
                with urlopen(request) as response:
                    self.assertEqual(json.load(response)['domains'], [])
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()

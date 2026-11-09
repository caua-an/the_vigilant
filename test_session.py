import json
import io
import os
import tempfile
import tkinter as tk
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

import core
from main import Vigilant, alert_sound


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requer uma sessão gráfica X11')
class SessionTest(unittest.TestCase):
    def test_session_and_last_task(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'), patch('main.PORT', 0):
            root = tk.Tk()
            root.withdraw()
            app = Vigilant(root)
            try:
                app.commit({'tasks': [{'text': 'Estudar', 'done': False}], 'sites': ['youtube.com'], 'apps': []})
                with patch.dict('os.environ', {'XDG_SESSION_TYPE': 'x11'}):
                    app.toggle_session()
                request = Request(f'http://127.0.0.1:{app.server.server_port}/state', headers={'Origin': 'chrome-extension://test'})
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


class AlertTest(unittest.TestCase):
    def test_alert_is_two_seconds(self):
        with wave.open(io.BytesIO(alert_sound()), 'rb') as sound:
            self.assertEqual(sound.getnframes(), sound.getframerate() * 2)


if __name__ == '__main__':
    unittest.main()

import json
import io
import os
import ctypes
import ctypes.util
import tempfile
import tkinter as tk
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen

import core
from main import EYES, VISORS, Vigilant, alert_sound, bubble_position


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requer uma sessão gráfica X11')
class SessionTest(unittest.TestCase):
    def test_customization_and_reaction(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'), patch('main.PORT', 0):
            root = tk.Tk()
            root.withdraw()
            app = Vigilant(root)
            try:
                app.set_customization(metal='Cobre', eyes='Azul-escuro', sound=False, adult=True)
                app.message_entry.insert(0, 'Volte ao foco!')
                app.message_adult_var.set(True)
                app.add_message()
                self.assertEqual(core.load_data()['customization']['messages'], [{'text': 'Volte ao foco!', 'adult': True}])
                with patch.dict('os.environ', {'XDG_SESSION_TYPE': 'x11'}):
                    app.toggle_session()
                app.server.events.put('attempt')
                root.after_cancel(app.tick_job)
                with patch('main.play_alert') as play:
                    app.tick()
                    play.assert_not_called()
                self.assertIsNotNone(app.bubble)
                self.assertEqual(app.bubble.winfo_height(), 96)
                self.assertTrue(any(app.canvas.itemcget(i, 'fill') == '#ff7771' for i in app.canvas.find_all()))
                app.end_session()
                self.assertIsNone(app.bubble)
            finally:
                app.close()

    def test_drag_and_app_search(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'), patch('main.PORT', 0):
            root = tk.Tk()
            root.withdraw()
            app = Vigilant(root)
            try:
                app.show_robot()
                app.robot.update()
                x, y = app.robot.winfo_x(), app.robot.winfo_y()
                app.robot_press(SimpleNamespace(x_root=x + 10, y_root=y + 10))
                app.robot_move(SimpleNamespace(x_root=x - 10, y_root=y - 10))
                app.robot_release(SimpleNamespace())
                self.assertEqual(core.load_data()['robot_position'], [max(0, x - 20), max(0, y - 20)])
                with patch('main.installed_apps', return_value=[('Alpha', 'alpha'), ('Brave', 'brave')]):
                    app.choose_app()
                dialog = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w is not app.robot][0]
                entry = next(w for w in dialog.winfo_children() if isinstance(w, tk.Entry))
                listing = next(w for w in dialog.winfo_children() if isinstance(w, tk.Listbox))
                entry.insert(0, 'BRA')
                self.assertEqual(listing.size(), 1)
                self.assertIn('Brave', listing.get(0))
                listing.selection_set(0)
                button = next(w for w in dialog.winfo_children() if isinstance(w, tk.Button))
                button.invoke()
                self.assertEqual(app.data['apps'][0]['id'], 'brave')
            finally:
                app.close()

    def test_robot_outer_window_is_shaped(self):
        from main import shape_head
        root = tk.Tk()
        root.withdraw()
        robot = tk.Toplevel(root)
        robot.overrideredirect(True)
        robot.geometry('144x144')
        robot.update()
        x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
        xext = ctypes.CDLL(ctypes.util.find_library('Xext'))
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
        x11.XFree.argtypes = [ctypes.c_void_p]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xext.XShapeGetRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        xext.XShapeGetRectangles.restype = ctypes.c_void_p
        display = x11.XOpenDisplay(None)
        try:
            root_id, parent, children, nchildren = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p(), ctypes.c_uint()
            self.assertTrue(x11.XQueryTree(display, robot.winfo_id(), ctypes.byref(root_id), ctypes.byref(parent), ctypes.byref(children), ctypes.byref(nchildren)))
            if children.value:
                x11.XFree(children)
            shape_head(robot)
            count, ordering = ctypes.c_int(), ctypes.c_int()
            rectangles = xext.XShapeGetRectangles(display, parent.value, 0, ctypes.byref(count), ctypes.byref(ordering))
            try:
                self.assertGreater(count.value, 1, 'A janela externa ainda é retangular')
            finally:
                if rectangles:
                    x11.XFree(rectangles)
        finally:
            x11.XCloseDisplay(display)
            root.destroy()

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

    def test_multiple_browser_connections_and_firefox_attempt(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'), patch('main.PORT', 0):
            root = tk.Tk()
            root.withdraw()
            app = Vigilant(root)
            try:
                base = f'http://127.0.0.1:{app.server.server_port}'
                for name, origin in [('brave', 'chrome-extension://brave'), ('chrome', 'chrome-extension://chrome'), ('firefox', 'moz-extension://firefox')]:
                    with urlopen(Request(f'{base}/state?browser={name}', headers={'Origin': origin})) as response:
                        self.assertEqual(response.headers['Access-Control-Allow-Origin'], origin)
                self.assertEqual(set(app.server.last_seen), {'brave', 'chrome', 'firefox'})
                with urlopen(Request(f'{base}/attempt', data=b'', headers={'Origin': 'moz-extension://firefox'})) as response:
                    self.assertEqual(json.load(response), {'ok': True})
                self.assertEqual(app.server.events.get_nowait(), 'attempt')
            finally:
                app.close()

    def test_browser_heartbeat_without_origin(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(core, 'DATA_FILE', Path(temp) / 'data.json'), patch('main.PORT', 0):
            root = tk.Tk()
            root.withdraw()
            app = Vigilant(root)
            try:
                base = f'http://127.0.0.1:{app.server.server_port}'
                for browser in ('brave', 'chrome'):
                    with urlopen(f'{base}/state?browser={browser}') as response:
                        self.assertEqual(response.status, 200)
                self.assertEqual(set(app.server.last_seen), {'brave', 'chrome'})
            finally:
                app.close()


class AlertTest(unittest.TestCase):
    def test_dark_blue_eye_contrast(self):
        def luminance(color):
            values = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            return sum(weight * (v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
                       for v, weight in zip(values, (0.2126, 0.7152, 0.0722)))
        for visor in VISORS.values():
            self.assertGreaterEqual((luminance(EYES['Azul-escuro']) + 0.05) / (luminance(visor) + 0.05), 3)

    def test_bubble_stays_on_screen(self):
        self.assertEqual(bubble_position(0, 0, 270, 78, 1000, 800), (152, 108))
        self.assertEqual(bubble_position(300, 400, 270, 78, 1000, 800), (452, 358))
        self.assertEqual(bubble_position(900, 700, 270, 78, 1000, 800), (622, 658))

    def test_alert_is_two_seconds(self):
        with wave.open(io.BytesIO(alert_sound()), 'rb') as sound:
            self.assertEqual(sound.getnframes(), sound.getframerate() * 2)


if __name__ == '__main__':
    unittest.main()

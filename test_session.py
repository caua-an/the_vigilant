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
from main import Vigilant, alert_sound


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Requer uma sessão gráfica X11')
class SessionTest(unittest.TestCase):
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


class AlertTest(unittest.TestCase):
    def test_alert_is_two_seconds(self):
        with wave.open(io.BytesIO(alert_sound()), 'rb') as sound:
            self.assertEqual(sound.getnframes(), sound.getframerate() * 2)


if __name__ == '__main__':
    unittest.main()

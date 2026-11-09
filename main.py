#!/usr/bin/env python3
import configparser
import copy
import ctypes
import ctypes.util
import glob
import io
import json
import math
import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
import tkinter as tk
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox, ttk

from core import PRESETS, domain_from_input, load_data, save_data

BG, PANEL, INK, BLUE = '#101923', '#182533', '#edf3f6', '#a9bdc9'
RED = '#ff7771'
PORT = 47653
HEAD_ROWS = (6, 10, 14, 16, 18, 20, 20, 22, 22, 24, 24, 24, 24, 24, 24, 22, 22, 20, 20, 18, 16, 14, 10, 6)


def alert_sound():
    rate = 16000
    samples = bytearray()
    for i in range(rate * 2):
        t = i / rate
        envelope = min(1, t * 20, (2 - t) * 8)
        tone = math.sin(2 * math.pi * (440 if t < 0.9 else 330) * t)
        samples.extend(int(128 + 32 * envelope * tone).to_bytes(1, 'little'))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setparams((1, 1, rate, 0, 'NONE', 'not compressed'))
        output.writeframes(samples)
    return buffer.getvalue()


def play_alert():
    player = shutil.which('paplay')
    if not player:
        return
    def play():
        try:
            subprocess.run([player], input=alert_sound(), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
    threading.Thread(target=play, daemon=True).start()


def shape_head(window):
    """Recorta a janela no contorno pixelado usando a extensão XShape do X11."""
    class Rectangle(ctypes.Structure):
        _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short),
                    ('width', ctypes.c_ushort), ('height', ctypes.c_ushort)]

    try:
        x11 = ctypes.CDLL(ctypes.util.find_library('X11'))
        xext = ctypes.CDLL(ctypes.util.find_library('Xext'))
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x11.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint)]
        x11.XFree.argtypes = [ctypes.c_void_p]
        xext.XShapeCombineRectangles.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int,
                                                  ctypes.c_int, ctypes.c_int, ctypes.POINTER(Rectangle),
                                                  ctypes.c_int, ctypes.c_int, ctypes.c_int]
        display = x11.XOpenDisplay(None)
        if not display:
            return
        try:
            root, parent = ctypes.c_ulong(), ctypes.c_ulong()
            children, count = ctypes.c_void_p(), ctypes.c_uint()
            if not x11.XQueryTree(display, window.winfo_id(), ctypes.byref(root), ctypes.byref(parent), ctypes.byref(children), ctypes.byref(count)):
                return
            if children.value:
                x11.XFree(children)
            rows = (Rectangle * len(HEAD_ROWS))(*(Rectangle((24 - width) // 2 * 6, y * 6, width * 6, 6)
                                                   for y, width in enumerate(HEAD_ROWS)))
            xext.XShapeCombineRectangles(display, parent.value, 0, 0, 0, rows, len(rows), 0, 0)
        finally:
            x11.XCloseDisplay(display)
    except (OSError, AttributeError, TypeError):
        pass  # Se XShape não estiver disponível, a cabeça permanece em uma janela quadrada.


def installed_apps():
    entries = {}
    dirs = [Path.home() / '.local/share/applications', Path('/usr/local/share/applications'), Path('/usr/share/applications')]
    for directory in dirs:
        for path in glob.glob(str(directory / '*.desktop')):
            try:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.read(path, encoding='utf-8')
                entry = parser['Desktop Entry']
                if entry.get('Type') != 'Application' or entry.getboolean('NoDisplay', fallback=False) or entry.getboolean('Hidden', fallback=False):
                    continue
                name = entry.get('Name[pt_BR]', entry.get('Name', '')).strip()
                command = shlex.split(entry.get('Exec', ''))
                if not name or not command:
                    continue
                # Flatpak launchers need StartupWMClass or a manually specified process name.
                identifier = entry.get('StartupWMClass', '').strip() or os.path.basename(command[0])
                entries.setdefault(name, identifier)
            except (OSError, ValueError, KeyError, configparser.Error):
                continue
    return sorted(entries.items(), key=lambda item: item[0].lower())


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    def respond(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        origin = self.headers.get('Origin', '')
        if origin.startswith('chrome-extension://'):
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != '/state':
            self.send_error(404)
            return
        with self.server.state_lock:
            domains = list(self.server.domains)
            self.server.last_seen = time.monotonic()
        self.respond({'domains': domains})

    def do_POST(self):
        if self.path != '/attempt' or not self.headers.get('Origin', '').startswith('chrome-extension://'):
            self.send_error(403)
            return
        self.server.events.put('attempt')
        self.respond({'ok': True})

    def log_message(self, format, *args):
        pass


class Vigilant:
    def __init__(self, root):
        self.root = root
        self.root.title('The Vigilant')
        self.root.geometry('820x720')
        self.root.minsize(680, 540)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.active = False
        self.robot = None
        self.last_blocked = None
        self.angry_until = 0
        self.data = load_data()
        self.server = Server(('127.0.0.1', PORT), Handler)
        self.server.domains = []
        self.server.last_seen = 0
        self.server.state_lock = threading.Lock()
        self.server.events = queue.SimpleQueue()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.build()
        self.refresh()
        self.root.after(500, self.tick)

    def build(self):
        self.root.option_add('*Font', ('DejaVu Sans', 10))
        for widget in ('Button', 'Entry', 'Listbox', 'Checkbutton'):
            self.root.option_add(f'*{widget}.background', '#223342')
            self.root.option_add(f'*{widget}.foreground', INK)
        self.root.option_add('*Button.activeBackground', '#36566b')
        self.root.option_add('*Button.activeForeground', INK)
        self.root.option_add('*Button.relief', 'flat')
        self.root.option_add('*Button.padX', 12)
        self.root.option_add('*Button.padY', 7)
        self.root.option_add('*Button.highlightThickness', 0)
        self.root.option_add('*Entry.insertBackground', INK)
        self.root.option_add('*Entry.relief', 'flat')
        self.root.option_add('*Entry.highlightThickness', 1)
        self.root.option_add('*Entry.highlightBackground', '#223342')
        self.root.option_add('*Entry.highlightColor', '#8bc7d3')
        self.root.option_add('*Listbox.highlightThickness', 1)
        self.root.option_add('*Listbox.highlightBackground', '#223342')
        self.root.option_add('*Listbox.highlightColor', '#8bc7d3')
        self.root.option_add('*Listbox.selectBackground', '#365c73')
        self.root.option_add('*Listbox.selectForeground', INK)
        self.root.option_add('*Checkbutton.selectColor', '#111a25')
        self.root.option_add('*Checkbutton.activeBackground', PANEL)
        self.root.option_add('*Checkbutton.activeForeground', INK)
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=BG, foreground=BLUE, padding=(20, 10), borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', INK)])
        content = tk.Frame(self.root, bg=BG, padx=44, pady=26)
        content.pack(fill='both', expand=True)
        tk.Label(content, text='THE VIGILANT  /  SEU ESPAÇO DE FOCO', bg=BG, fg='#8bc7d3', font=('DejaVu Sans Mono', 9, 'bold')).pack(anchor='w')
        tk.Label(content, text='Um passo de cada vez.', bg=BG, fg=INK, font=('DejaVu Sans', 22, 'bold')).pack(anchor='w', pady=(12, 3))
        tk.Label(content, text='Organize suas tarefas e deixe as distrações em pausa.', bg=BG, fg=BLUE, font=('DejaVu Sans', 10)).pack(anchor='w')
        bar = tk.Frame(content, bg=PANEL, padx=18, pady=12)
        bar.pack(fill='x', pady=(24, 18))
        status_area = tk.Frame(bar, bg=PANEL)
        status_area.pack(side='left', fill='x', expand=True)
        self.status = tk.Label(status_area, bg=PANEL, fg=INK, font=('DejaVu Sans', 11, 'bold'))
        self.status.pack(anchor='w')
        self.connection = tk.Label(status_area, bg=PANEL, fg=BLUE, font=('DejaVu Sans', 9), anchor='w')
        self.connection.pack(anchor='w')
        self.session_button = tk.Button(bar, command=self.toggle_session, bg='#83bdc9', fg='#10222a', activebackground='#a6d6de', activeforeground='#10222a', relief='flat', padx=15, pady=8)
        self.session_button.pack(side='right')
        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill='both', expand=True)
        self.tasks_tab = tk.Frame(self.notebook, bg=PANEL, padx=22, pady=20)
        self.sites_tab = tk.Frame(self.notebook, bg=PANEL, padx=22, pady=20)
        self.apps_tab = tk.Frame(self.notebook, bg=PANEL, padx=22, pady=20)
        self.notebook.add(self.tasks_tab, text='  Tarefas  ')
        self.notebook.add(self.sites_tab, text='  Sites  ')
        self.notebook.add(self.apps_tab, text='  Aplicativos  ')
        self.make_tasks()
        self.make_sites()
        self.make_apps()

    def commit(self, updated):
        try:
            save_data(updated)
        except OSError as exc:
            messagebox.showerror('Não foi possível salvar', str(exc), parent=self.root)
            return False
        self.data = updated
        self.publish()
        self.refresh()
        return True

    def publish(self):
        with self.server.state_lock:
            self.server.domains = list(self.data['sites']) if self.active else []

    def make_tasks(self):
        tk.Label(self.tasks_tab, text='O que você vai estudar?', bg=PANEL, fg=INK, font=('DejaVu Sans', 15, 'bold')).pack(anchor='w')
        tk.Label(self.tasks_tab, text='Adicione suas tarefas para esta sessão.', bg=PANEL, fg=BLUE).pack(anchor='w', pady=(4, 0))
        row = tk.Frame(self.tasks_tab, bg=PANEL, pady=12)
        row.pack(fill='x')
        self.task_entry = tk.Entry(row, font=('DejaVu Sans', 11))
        self.task_entry.pack(side='left', fill='x', expand=True, ipady=5)
        self.task_entry.bind('<Return>', lambda _: self.add_task())
        tk.Button(row, text='Adicionar tarefa', command=self.add_task).pack(side='left', padx=(8, 0))
        self.task_list = tk.Listbox(self.tasks_tab, font=('DejaVu Sans', 11), selectmode='single', activestyle='none', relief='flat', borderwidth=0)
        self.task_list.pack(fill='both', expand=True)
        actions = tk.Frame(self.tasks_tab, bg=PANEL, pady=10)
        actions.pack(fill='x')
        tk.Button(actions, text='Concluir / reabrir', command=self.toggle_task).pack(side='left')
        tk.Button(actions, text='Excluir selecionada', command=self.delete_task).pack(side='left', padx=8)
        tk.Label(self.tasks_tab, text='Concluir a última tarefa pendente encerra a sessão.', bg=PANEL, fg=BLUE).pack(anchor='w')

    def add_task(self):
        text = self.task_entry.get().strip()
        if text:
            data = copy.deepcopy(self.data)
            data['tasks'].append({'text': text, 'done': False})
            if self.commit(data):
                self.task_entry.delete(0, 'end')

    def selected(self, widget):
        selection = widget.curselection()
        return selection[0] if selection else None

    def toggle_task(self):
        index = self.selected(self.task_list)
        if index is None:
            return
        data = copy.deepcopy(self.data)
        task = data['tasks'][index]
        task['done'] = not task['done']
        complete = task['done'] and not any(not item['done'] for item in data['tasks'])
        if self.commit(data) and self.active and complete:
            self.end_session()
            messagebox.showinfo('Sessão concluída', 'Todas as tarefas foram concluídas. Os bloqueios foram liberados.', parent=self.root)

    def delete_task(self):
        index = self.selected(self.task_list)
        if index is not None:
            data = copy.deepcopy(self.data)
            data['tasks'].pop(index)
            self.commit(data)

    def make_sites(self):
        tk.Label(self.sites_tab, text='Sites para deixar em pausa', bg=PANEL, fg=INK, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w')
        tk.Label(self.sites_tab, text='Selecione sugestões ou adicione um link. O domínio inteiro será bloqueado.', bg=PANEL, fg=BLUE, wraplength=650, justify='left').pack(anchor='w', pady=(4, 10))
        self.preset_vars = {}
        presets = tk.Frame(self.sites_tab, bg=PANEL)
        presets.pack(fill='x')
        for site in PRESETS:
            var = tk.BooleanVar()
            self.preset_vars[site] = var
            tk.Checkbutton(presets, text=site, variable=var, bg=PANEL, command=lambda s=site, v=var: self.preset_changed(s, v)).pack(side='left', padx=(0, 10))
        row = tk.Frame(self.sites_tab, bg=PANEL, pady=12)
        row.pack(fill='x')
        self.site_entry = tk.Entry(row, font=('DejaVu Sans', 11))
        self.site_entry.pack(side='left', fill='x', expand=True, ipady=5)
        self.site_entry.bind('<Return>', lambda _: self.add_site())
        tk.Button(row, text='Adicionar site', command=self.add_site).pack(side='left', padx=(8, 0))
        self.site_list = tk.Listbox(self.sites_tab, font=('DejaVu Sans', 11), relief='flat', borderwidth=0)
        self.site_list.pack(fill='both', expand=True)
        tk.Button(self.sites_tab, text='Remover selecionado', command=self.delete_site).pack(anchor='w', pady=10)
        tk.Label(self.sites_tab, text='Instale a extensão do Brave conforme as instruções no README.', bg=PANEL, fg=BLUE).pack(anchor='w')

    def preset_changed(self, site, var):
        data = copy.deepcopy(self.data)
        if var.get() and site not in data['sites']:
            data['sites'].append(site)
        elif not var.get() and site in data['sites']:
            data['sites'].remove(site)
        if not self.commit(data):
            self.refresh()

    def add_site(self):
        try:
            site = domain_from_input(self.site_entry.get())
        except ValueError as exc:
            messagebox.showerror('Site inválido', str(exc), parent=self.root)
            return
        data = copy.deepcopy(self.data)
        if site not in data['sites']:
            data['sites'].append(site)
        if self.commit(data):
            self.site_entry.delete(0, 'end')

    def delete_site(self):
        index = self.selected(self.site_list)
        if index is not None:
            data = copy.deepcopy(self.data)
            data['sites'].pop(index)
            self.commit(data)

    def make_apps(self):
        tk.Label(self.apps_tab, text='Aplicativos para deixar em pausa', bg=PANEL, fg=INK, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w')
        tk.Label(self.apps_tab, text='Ao ganhar foco, o aplicativo será minimizado, sem ser fechado.', bg=PANEL, fg=BLUE).pack(anchor='w', pady=(4, 12))
        row = tk.Frame(self.apps_tab, bg=PANEL)
        row.pack(fill='x', pady=(0, 12))
        tk.Button(row, text='Escolher instalado', command=self.choose_app).pack(side='left')
        self.app_list = tk.Listbox(self.apps_tab, font=('DejaVu Sans', 11), relief='flat', borderwidth=0)
        self.app_list.pack(fill='both', expand=True)
        tk.Button(self.apps_tab, text='Remover selecionado', command=self.delete_app).pack(anchor='w', pady=10)
        tk.Label(self.apps_tab, text='Alguns aplicativos podem não ser identificados corretamente ao ganhar foco.', bg=PANEL, fg=BLUE, wraplength=640, justify='left').pack(anchor='w')

    def choose_app(self):
        window = tk.Toplevel(self.root)
        window.configure(bg=PANEL)
        window.title('Escolher aplicativo')
        window.geometry('440x500')
        tk.Label(window, text='Buscar aplicativo instalado:', bg=PANEL, fg=INK).pack(anchor='w', padx=12, pady=(12, 4))
        search = tk.StringVar(master=window)
        search_entry = tk.Entry(window, textvariable=search)
        search_entry.pack(fill='x', padx=12, pady=(0, 10), ipady=4)
        listing = tk.Listbox(window)
        listing.pack(fill='both', expand=True, padx=12)
        entries = installed_apps()
        filtered = []
        def update_list(*_):
            query = search.get().strip().casefold()
            filtered[:] = [(name, identifier) for name, identifier in entries if query in name.casefold()]
            listing.delete(0, 'end')
            for name, identifier in filtered:
                listing.insert('end', f'{name}  ·  {identifier}')
        search.trace_add('write', update_list)
        update_list()
        search_entry.focus_set()
        def choose():
            index = self.selected(listing)
            if index is not None:
                name, identifier = filtered[index]
                self.add_app(name, identifier)
                window.destroy()
        tk.Button(window, text='Adicionar', command=choose).pack(pady=12)
        listing.bind('<Double-Button-1>', lambda _: choose())

    def add_app(self, name, identifier):
        data = copy.deepcopy(self.data)
        if not any(app['id'].casefold() == identifier.casefold() for app in data['apps']):
            data['apps'].append({'name': name, 'id': identifier})
            self.commit(data)

    def delete_app(self):
        index = self.selected(self.app_list)
        if index is not None:
            data = copy.deepcopy(self.data)
            data['apps'].pop(index)
            self.commit(data)

    def refresh(self):
        self.status.config(text='●  Sessão em andamento' if self.active else '○  Pronto para estudar', fg=BLUE if self.active else INK)
        self.session_button.config(text='Encerrar sessão' if self.active else 'Iniciar sessão')
        self.task_list.delete(0, 'end')
        for task in self.data['tasks']:
            self.task_list.insert('end', ('☑  ' if task['done'] else '☐  ') + task['text'])
        self.site_list.delete(0, 'end')
        for site in self.data['sites']:
            self.site_list.insert('end', site)
        for site, var in self.preset_vars.items():
            var.set(site in self.data['sites'])
        self.app_list.delete(0, 'end')
        for app in self.data['apps']:
            self.app_list.insert('end', f"{app['name']}  ·  {app['id']}")

    def toggle_session(self):
        if self.active:
            self.end_session()
        else:
            if os.environ.get('XDG_SESSION_TYPE') != 'x11' or not shutil.which('xdotool') or not shutil.which('xprop'):
                messagebox.showwarning('Monitoramento de aplicativos indisponível', 'O bloqueio de aplicativos requer uma sessão X11, xdotool e xprop. O bloqueio de sites pode continuar funcionando.', parent=self.root)
            self.active = True
            self.publish()
            self.show_robot()
            self.refresh()

    def end_session(self):
        self.active = False
        self.publish()
        if self.robot:
            self.robot.destroy()
            self.robot = None
        self.refresh()

    def show_robot(self):
        self.robot = tk.Toplevel(self.root)
        self.robot.overrideredirect(True)
        self.robot.attributes('-topmost', True)
        position = self.data.get('robot_position')
        if not (isinstance(position, list) and len(position) == 2 and all(type(v) is int for v in position)):
            position = [self.root.winfo_screenwidth() - 160, self.root.winfo_screenheight() - 195]
        x = max(0, min(position[0], self.root.winfo_screenwidth() - 144))
        y = max(0, min(position[1], self.root.winfo_screenheight() - 144))
        self.robot.geometry(f'144x144+{x}+{y}')
        self.canvas = tk.Canvas(self.robot, width=144, height=144, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<ButtonPress-1>', self.robot_press)
        self.canvas.bind('<B1-Motion>', self.robot_move)
        self.canvas.bind('<ButtonRelease-1>', self.robot_release)
        self.draw_robot(False)
        self.robot.update_idletasks()
        shape_head(self.robot)

    def robot_press(self, event):
        self.drag_start = (event.x_root, event.y_root, self.robot.winfo_x(), self.robot.winfo_y())
        self.dragged = False

    def robot_move(self, event):
        start_x, start_y, window_x, window_y = self.drag_start
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if abs(dx) + abs(dy) < 5 and not self.dragged:
            return
        self.dragged = True
        x = max(0, min(window_x + dx, self.root.winfo_screenwidth() - 144))
        y = max(0, min(window_y + dy, self.root.winfo_screenheight() - 144))
        self.robot.geometry(f'+{x}+{y}')

    def robot_release(self, event):
        if self.dragged:
            self.robot.update_idletasks()
            data = copy.deepcopy(self.data)
            data['robot_position'] = [self.robot.winfo_x(), self.robot.winfo_y()]
            self.commit(data)
        else:
            self.root.deiconify()
            self.root.lift()

    def draw_robot(self, angry):
        c = self.canvas
        c.delete('all')
        def pixel(x, y, color):
            c.create_rectangle(x * 6, y * 6, x * 6 + 6, y * 6 + 6, fill=color, outline='')

        # Cabeça redonda em pixels, com contorno e poucos detalhes metálicos.
        for y, width in enumerate(HEAD_ROWS):
            start = (24 - width) // 2
            for x in range(start, start + width):
                edge = y in (0, 23) or x in (start, start + width - 1)
                color = '#243b4b' if edge else '#7094a1' if y > 18 or x > 19 else '#c1d5d7' if y < 5 or x < 4 else '#a1bdc3'
                pixel(x, y, color)
        for x, y in ((7, 3), (8, 3), (9, 3), (6, 4), (18, 19), (17, 20)):
            pixel(x, y, '#deebea' if y < 10 else '#5b7f8c')
        # Um visor amplo, integrado à carcaça, forma o rosto do robô.
        for y in range(6, 18):
            for x in range(4, 20):
                if (x in (4, 19) and y in (6, 17)):
                    continue
                pixel(x, y, '#304c5b' if y in (6, 17) or x in (4, 19) else '#1c3443')
        color = RED if angry else '#a8e5e5'
        for x in (8, 14):
            for y in (10, 11, 12):
                pixel(x, y, color)
                pixel(x + 1, y, color)
            pixel(x, 10, '#ffe0dc' if angry else '#e1ffff')
        if angry:
            for x, y in ((7, 8), (8, 9), (9, 9), (14, 9), (15, 9), (16, 8)):
                pixel(x, y, color)
            for x in range(10, 14):
                pixel(x, 14, color)
        else:
            for x, y in ((10, 14), (11, 15), (12, 15), (13, 14)):
                pixel(x, y, color)
        for x in (10, 11, 12, 13):
            pixel(x, 20, '#648896')

    def tick(self):
        if self.active:
            with self.server.state_lock:
                connected = time.monotonic() - self.server.last_seen < 35
            self.connection.config(text='Brave: extensão conectada' if connected else 'Brave: extensão não detectada — confira a instalação no README.')
            event = False
            while not self.server.events.empty():
                self.server.events.get()
                event = True
            if self.data['apps'] and shutil.which('xdotool') and shutil.which('xprop'):
                try:
                    window = subprocess.check_output(['xdotool', 'getactivewindow'], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
                    pid = subprocess.check_output(['xdotool', 'getwindowpid', window], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
                    classes = subprocess.check_output(['xprop', '-id', window, 'WM_CLASS'], text=True, stderr=subprocess.DEVNULL, timeout=1).split('=', 1)[-1].replace('"', '').split(',')
                    names = {s.strip().casefold() for s in classes}
                    try:
                        names.add(Path(f'/proc/{pid}/comm').read_text().strip().casefold())
                    except OSError:
                        pass
                    if any(app['id'].casefold() in names for app in self.data['apps']):
                        subprocess.run(['xdotool', 'windowminimize', window], stderr=subprocess.DEVNULL, timeout=1, check=True)
                        event = True
                except (OSError, subprocess.SubprocessError):
                    pass
            if event:
                if time.monotonic() >= self.angry_until:
                    play_alert()
                self.angry_until = time.monotonic() + 2
            if self.robot:
                angry = time.monotonic() < self.angry_until
                self.draw_robot(angry)
                if angry and int(time.monotonic() * 6) % 2:
                    self.canvas.move('all', 3, 0)
        else:
            self.connection.config(text='')
            while not self.server.events.empty():
                self.server.events.get()
        self.root.after(500, self.tick)

    def close(self):
        if self.active and not messagebox.askyesno('Encerrar sessão?', 'Fechar o The Vigilant encerrará a sessão e liberará os bloqueios. Continuar?', parent=self.root):
            return
        self.active = False
        self.publish()
        self.server.shutdown()
        self.server.server_close()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    try:
        Vigilant(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        messagebox.showerror('The Vigilant não iniciou', f'Verifique os dados salvos e se outra instância já está aberta.\n\n{exc}', parent=root)
        root.destroy()
    else:
        root.mainloop()

#!/usr/bin/env python3
import configparser
import copy
import glob
import json
import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from core import PRESETS, domain_from_input, load_data, save_data

BG, INK, BLUE, RED = '#e9eff7', '#19334b', '#426d89', '#b6434e'
PORT = 47653


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
        self.root.geometry('820x690')
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
        header = tk.Frame(self.root, bg=INK, padx=22, pady=16)
        header.pack(fill='x')
        tk.Label(header, text='THE VIGILANT', bg=INK, fg='#f1f6fa', font=('DejaVu Sans Mono', 18, 'bold')).pack(anchor='w')
        tk.Label(header, text='Um pequeno guardião para suas grandes tarefas.', bg=INK, fg='#bad1df', font=('DejaVu Sans', 10)).pack(anchor='w')
        bar = tk.Frame(self.root, bg=BG, padx=20, pady=14)
        bar.pack(fill='x')
        self.status = tk.Label(bar, bg=BG, fg=INK, font=('DejaVu Sans', 11, 'bold'))
        self.status.pack(side='left')
        self.session_button = tk.Button(bar, command=self.toggle_session, bg=BLUE, fg='white', activebackground=INK, activeforeground='white', relief='flat', padx=15, pady=8)
        self.session_button.pack(side='right')
        self.connection = tk.Label(self.root, bg=BG, fg=BLUE, font=('DejaVu Sans', 9), anchor='w', padx=20)
        self.connection.pack(fill='x', pady=(0, 6))
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=20, pady=(0, 20))
        self.tasks_tab = tk.Frame(self.notebook, bg='white', padx=16, pady=15)
        self.sites_tab = tk.Frame(self.notebook, bg='white', padx=16, pady=15)
        self.apps_tab = tk.Frame(self.notebook, bg='white', padx=16, pady=15)
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
        tk.Label(self.tasks_tab, text='O que você vai estudar?', bg='white', fg=INK, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w')
        row = tk.Frame(self.tasks_tab, bg='white', pady=12)
        row.pack(fill='x')
        self.task_entry = tk.Entry(row, font=('DejaVu Sans', 11))
        self.task_entry.pack(side='left', fill='x', expand=True, ipady=5)
        self.task_entry.bind('<Return>', lambda _: self.add_task())
        tk.Button(row, text='Adicionar tarefa', command=self.add_task).pack(side='left', padx=(8, 0))
        self.task_list = tk.Listbox(self.tasks_tab, font=('DejaVu Sans', 11), selectmode='single', activestyle='none', relief='solid', borderwidth=1)
        self.task_list.pack(fill='both', expand=True)
        actions = tk.Frame(self.tasks_tab, bg='white', pady=10)
        actions.pack(fill='x')
        tk.Button(actions, text='Concluir / reabrir', command=self.toggle_task).pack(side='left')
        tk.Button(actions, text='Excluir selecionada', command=self.delete_task).pack(side='left', padx=8)
        tk.Label(self.tasks_tab, text='Concluir a última tarefa pendente encerra a sessão.', bg='white', fg=BLUE).pack(anchor='w')

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
        tk.Label(self.sites_tab, text='Sites para deixar em pausa', bg='white', fg=INK, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w')
        tk.Label(self.sites_tab, text='Selecione sugestões ou adicione um link. O domínio inteiro será bloqueado.', bg='white', fg=BLUE, wraplength=650, justify='left').pack(anchor='w', pady=(4, 10))
        self.preset_vars = {}
        presets = tk.Frame(self.sites_tab, bg='white')
        presets.pack(fill='x')
        for site in PRESETS:
            var = tk.BooleanVar()
            self.preset_vars[site] = var
            tk.Checkbutton(presets, text=site, variable=var, bg='white', command=lambda s=site, v=var: self.preset_changed(s, v)).pack(side='left', padx=(0, 10))
        row = tk.Frame(self.sites_tab, bg='white', pady=12)
        row.pack(fill='x')
        self.site_entry = tk.Entry(row, font=('DejaVu Sans', 11))
        self.site_entry.pack(side='left', fill='x', expand=True, ipady=5)
        self.site_entry.bind('<Return>', lambda _: self.add_site())
        tk.Button(row, text='Adicionar site', command=self.add_site).pack(side='left', padx=(8, 0))
        self.site_list = tk.Listbox(self.sites_tab, font=('DejaVu Sans', 11), relief='solid', borderwidth=1)
        self.site_list.pack(fill='both', expand=True)
        tk.Button(self.sites_tab, text='Remover selecionado', command=self.delete_site).pack(anchor='w', pady=10)
        tk.Label(self.sites_tab, text='Instale a extensão do Brave conforme as instruções no README.', bg='white', fg=BLUE).pack(anchor='w')

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
        tk.Label(self.apps_tab, text='Aplicativos para deixar em pausa', bg='white', fg=INK, font=('DejaVu Sans', 13, 'bold')).pack(anchor='w')
        tk.Label(self.apps_tab, text='Ao ganhar foco, o aplicativo será minimizado, sem ser fechado.', bg='white', fg=BLUE).pack(anchor='w', pady=(4, 12))
        row = tk.Frame(self.apps_tab, bg='white')
        row.pack(fill='x', pady=(0, 12))
        tk.Button(row, text='Escolher instalado', command=self.choose_app).pack(side='left')
        tk.Button(row, text='Adicionar nome manualmente', command=self.add_manual_app).pack(side='left', padx=8)
        self.app_list = tk.Listbox(self.apps_tab, font=('DejaVu Sans', 11), relief='solid', borderwidth=1)
        self.app_list.pack(fill='both', expand=True)
        tk.Button(self.apps_tab, text='Remover selecionado', command=self.delete_app).pack(anchor='w', pady=10)
        tk.Label(self.apps_tab, text='Alguns aplicativos exigem informar manualmente o nome do processo ou da classe da janela.', bg='white', fg=BLUE, wraplength=640, justify='left').pack(anchor='w')

    def choose_app(self):
        window = tk.Toplevel(self.root)
        window.title('Escolher aplicativo')
        window.geometry('440x500')
        tk.Label(window, text='Selecione um aplicativo instalado:').pack(anchor='w', padx=12, pady=10)
        listing = tk.Listbox(window)
        listing.pack(fill='both', expand=True, padx=12)
        entries = installed_apps()
        for name, identifier in entries:
            listing.insert('end', f'{name}  ·  {identifier}')
        def choose():
            index = self.selected(listing)
            if index is not None:
                name, identifier = entries[index]
                self.add_app(name, identifier)
                window.destroy()
        tk.Button(window, text='Adicionar', command=choose).pack(pady=12)
        listing.bind('<Double-Button-1>', lambda _: choose())

    def add_manual_app(self):
        value = simpledialog.askstring('Adicionar aplicativo', 'Nome exato do processo ou classe da janela:', parent=self.root)
        if value and value.strip():
            self.add_app(value.strip(), value.strip())

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
        self.robot.geometry(f'140x154+{self.root.winfo_screenwidth()-155}+{self.root.winfo_screenheight()-210}')
        self.canvas = tk.Canvas(self.robot, width=140, height=154, bg=BG, highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind('<Button-1>', lambda _: (self.root.deiconify(), self.root.lift()))
        self.draw_robot(False)

    def draw_robot(self, angry):
        c = self.canvas
        c.delete('all')
        c.create_rectangle(18, 10, 122, 129, fill=INK, outline=INK)
        c.create_rectangle(26, 18, 114, 121, fill='#d5e4eb', outline='')
        c.create_rectangle(35, 32, 105, 80, fill='#355c74', outline='')
        color = '#ff7771' if angry else '#a9e1dd'
        for x in (44, 82):
            c.create_rectangle(x, 47, x+13, 58, fill=color, outline='')
        if angry:
            c.create_line(42, 39, 59, 46, fill=color, width=5)
            c.create_line(81, 46, 98, 39, fill=color, width=5)
            c.create_rectangle(52, 68, 88, 72, fill=color, outline='')
        else:
            c.create_rectangle(54, 68, 86, 71, fill=color, outline='')
        c.create_rectangle(40, 94, 100, 99, fill=BLUE, outline='')
        c.create_text(70, 143, text='NÃO!' if angry else 'THE VIGILANT', fill=RED if angry else INK, font=('DejaVu Sans Mono', 10, 'bold'))

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

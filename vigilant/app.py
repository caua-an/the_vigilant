"""Janela principal e ciclo de vida da sessão de estudos."""
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from core import load_data, save_data
from .applications import ApplicationsUI
from .browser_server import Handler, PORT, Server
from .customization import CustomizationUI
from .linux import minimize_blocked_app, monitoring_available
from .robot import RobotUI
from .sites import SitesUI
from .sound import play_alert
from .tasks import TasksUI
from .theme import ACCENT, BG, BLUE, FIELD, INK, PANEL


class Vigilant(TasksUI, SitesUI, ApplicationsUI, CustomizationUI, RobotUI):
    """Coordena a janela, os componentes de interface e a sessão."""
    def __init__(self, root):
        self.root = root
        self.root.title('The Vigilant')
        self.root.geometry('820x720')
        self.root.minsize(680, 540)
        self.root.configure(bg=BG)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.active = False
        self.session_started = None
        self.robot = None
        self.bubble = None
        self.last_blocked = None
        self.angry_until = 0
        self.data = load_data()
        self.server = Server(('127.0.0.1', PORT), Handler)
        self.server.domains = []
        self.server.exceptions = []
        self.server.last_seen = {}
        self.server.state_lock = threading.Lock()
        self.server.events = queue.SimpleQueue()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.build()
        self.refresh()
        self.tick_job = self.root.after(500, self.tick)

    def build(self):
        self.root.option_add('*Font', ('DejaVu Sans', 10))
        for widget in ('Button', 'Entry', 'Listbox', 'Checkbutton'):
            self.root.option_add(f'*{widget}.background', FIELD)
            self.root.option_add(f'*{widget}.foreground', INK)
        self.root.option_add('*Button.activeBackground', '#383257')
        self.root.option_add('*Button.activeForeground', INK)
        self.root.option_add('*Button.relief', 'flat')
        self.root.option_add('*Button.padX', 12)
        self.root.option_add('*Button.padY', 7)
        self.root.option_add('*Button.highlightThickness', 1)
        self.root.option_add('*Button.highlightBackground', PANEL)
        self.root.option_add('*Button.highlightColor', '#c7bbff')
        self.root.option_add('*Entry.insertBackground', INK)
        self.root.option_add('*Entry.relief', 'flat')
        self.root.option_add('*Entry.highlightThickness', 1)
        self.root.option_add('*Entry.highlightBackground', FIELD)
        self.root.option_add('*Entry.highlightColor', '#c7bbff')
        self.root.option_add('*Listbox.highlightThickness', 1)
        self.root.option_add('*Listbox.highlightBackground', FIELD)
        self.root.option_add('*Listbox.highlightColor', '#c7bbff')
        self.root.option_add('*Listbox.selectBackground', '#40327f')
        self.root.option_add('*Listbox.selectForeground', INK)
        self.root.option_add('*Checkbutton.selectColor', '#211195')
        self.root.option_add('*Checkbutton.activeBackground', PANEL)
        self.root.option_add('*Checkbutton.activeForeground', INK)
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('Hidden.TNotebook', background=BG, borderwidth=0, tabmargins=0)
        style.layout('Hidden.TNotebook.Tab', [])
        sidebar = tk.Frame(self.root, bg='#0e102a', width=164, padx=12, pady=22)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text='THE\nVIGILANT', justify='left', bg='#0e102a', fg=INK, font=('DejaVu Sans Mono', 13, 'bold')).pack(anchor='w', padx=8)
        tk.Label(sidebar, text='ESPAÇO DE FOCO', bg='#0e102a', fg='#a99de0', font=('DejaVu Sans Mono', 8)).pack(anchor='w', padx=8, pady=(5, 28))
        self.nav_buttons = []
        for index, (icon, label) in enumerate((('▣', 'Tarefas'), ('◉', 'Sites'), ('▦', 'Aplicativos'), ('◇', 'Customização'))):
            button = tk.Button(sidebar, text=f'{icon}   {label}', anchor='w', bg='#0e102a', fg=BLUE,
                               activebackground='#211b4d', activeforeground=INK, highlightbackground='#0e102a',
                               highlightcolor='#c7bbff', command=lambda i=index: self.notebook.select(i))
            button.pack(fill='x', pady=3)
            self.nav_buttons.append(button)
        tk.Label(sidebar, text='SEU TEMPO\nIMPORTA.', justify='left', bg='#0e102a', fg='#8f88b6', font=('DejaVu Sans Mono', 9)).pack(side='bottom', anchor='w', padx=8, pady=10)
        content = tk.Frame(self.root, bg=BG, padx=22, pady=18)
        content.pack(fill='both', expand=True)
        bar = tk.Frame(content, bg=PANEL, padx=14, pady=10)
        bar.pack(fill='x', pady=(0, 14))
        status_area = tk.Frame(bar, bg=PANEL)
        status_area.pack(side='left', fill='x', expand=True)
        self.status = tk.Label(status_area, bg=PANEL, fg=INK, font=('DejaVu Sans', 11, 'bold'))
        self.status.pack(anchor='w')
        self.session_elapsed = tk.Label(status_area, text='Tempo de sessão  00:00:00', bg=PANEL, fg=BLUE, font=('DejaVu Sans Mono', 10), anchor='w')
        self.session_elapsed.pack(anchor='w')
        self.connection = tk.Label(status_area, bg=PANEL, fg=BLUE, font=('DejaVu Sans', 8), anchor='w', wraplength=340, justify='left')
        self.connection.pack(anchor='w')
        self.session_button = tk.Button(bar, command=self.toggle_session, bg=ACCENT, fg=INK, activebackground='#826cf1', activeforeground=INK, relief='flat', padx=12, pady=7)
        self.session_button.pack(side='right')
        bar.bind('<Configure>', lambda event: self.connection.configure(wraplength=max(100, event.width - self.session_button.winfo_reqwidth() - 48)))
        self.notebook = ttk.Notebook(content, style='Hidden.TNotebook')
        self.notebook.pack(fill='both', expand=True)
        self.tasks_tab = tk.Frame(self.notebook, bg=PANEL, padx=22, pady=20)
        self.sites_tab = tk.Frame(self.notebook, bg=PANEL)
        sites_scroll = tk.Canvas(self.sites_tab, bg=PANEL, highlightthickness=0)
        self.sites_scroll = sites_scroll
        sites_bar = ttk.Scrollbar(self.sites_tab, orient='vertical', command=sites_scroll.yview)
        sites_bar.pack(side='right', fill='y')
        sites_scroll.pack(side='left', fill='both', expand=True)
        sites_scroll.configure(yscrollcommand=sites_bar.set)
        self.sites_content = tk.Frame(sites_scroll, bg=PANEL, padx=22, pady=16)
        sites_window = sites_scroll.create_window(0, 0, anchor='nw', window=self.sites_content)
        self.sites_content.bind('<Configure>', lambda _: sites_scroll.configure(scrollregion=sites_scroll.bbox('all')))
        sites_scroll.bind('<Configure>', lambda e: sites_scroll.itemconfigure(sites_window, width=e.width))
        sites_scroll.bind('<Button-4>', lambda _: sites_scroll.yview_scroll(-1, 'units'))
        sites_scroll.bind('<Button-5>', lambda _: sites_scroll.yview_scroll(1, 'units'))
        self.apps_tab = tk.Frame(self.notebook, bg=PANEL, padx=22, pady=20)
        custom_page = tk.Frame(self.notebook, bg=PANEL)
        custom_scroll = tk.Canvas(custom_page, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(custom_page, orient='vertical', command=custom_scroll.yview)
        scrollbar.pack(side='right', fill='y')
        custom_scroll.pack(side='left', fill='both', expand=True)
        custom_scroll.configure(yscrollcommand=scrollbar.set)
        self.custom_tab = tk.Frame(custom_scroll, bg=PANEL, padx=22, pady=12)
        custom_window = custom_scroll.create_window(0, 0, anchor='nw', window=self.custom_tab)
        self.custom_tab.bind('<Configure>', lambda _: custom_scroll.configure(scrollregion=custom_scroll.bbox('all')))
        custom_scroll.bind('<Configure>', lambda e: custom_scroll.itemconfigure(custom_window, width=e.width))
        custom_scroll.bind('<Button-4>', lambda _: custom_scroll.yview_scroll(-1, 'units'))
        custom_scroll.bind('<Button-5>', lambda _: custom_scroll.yview_scroll(1, 'units'))
        self.notebook.add(self.tasks_tab, text='  Tarefas  ')
        self.notebook.add(self.sites_tab, text='  Sites  ')
        self.notebook.add(self.apps_tab, text='  Aplicativos  ')
        self.notebook.add(custom_page, text='  Customização  ')
        self.notebook.bind('<<NotebookTabChanged>>', self.update_navigation)
        self.make_tasks()
        self.make_sites()
        self.make_apps()
        self.make_customization()
        self.update_navigation()

    def update_navigation(self, event=None):
        selected = self.notebook.index(self.notebook.select())
        for index, button in enumerate(self.nav_buttons):
            button.configure(bg='#302260' if index == selected else '#0e102a',
                             fg=INK if index == selected else BLUE)

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
            self.server.exceptions = list(self.data.get('site_exceptions', [])) if self.active else []

    def selected(self, widget):
        selection = widget.curselection()
        return selection[0] if selection else None

    def refresh(self):
        self.status.config(text='●  Sessão em andamento' if self.active else '○  Pronto para estudar', fg=BLUE if self.active else INK)
        self.session_button.config(text='Encerrar sessão' if self.active else 'Iniciar sessão')
        self.task_list.delete(0, 'end')
        for task in self.data['tasks']:
            self.task_list.insert('end', ('☑  ' if task['done'] else '☐  ') + task['text'])
        self.site_list.delete(0, 'end')
        for site in self.data['sites']:
            self.site_list.insert('end', site)
        self.exception_list.delete(0, 'end')
        for site in self.data.get('site_exceptions', []):
            self.exception_list.insert('end', site)
        for label, empty in ((self.empty_sites, not self.data['sites']),
                             (self.empty_exceptions, not self.data.get('site_exceptions', []))):
            if empty:
                label.place(relx=0.5, rely=0.5, anchor='center')
            else:
                label.place_forget()
        for site, var in self.preset_vars.items():
            var.set(site in self.data['sites'])
        self.app_list.delete(0, 'end')
        for app in self.data['apps']:
            self.app_list.insert('end', f"{app['name']}  ·  {app['id']}")
        self.refresh_customization()

    def toggle_session(self):
        if self.active:
            self.end_session()
        else:
            if not monitoring_available():
                messagebox.showwarning('Monitoramento de aplicativos indisponível', 'O bloqueio de aplicativos requer uma sessão X11, xdotool e xprop. O bloqueio de sites pode continuar funcionando.', parent=self.root)
            self.active = True
            self.session_started = time.monotonic()
            self.update_session_elapsed()
            self.publish()
            self.show_robot()
            self.refresh()

    def end_session(self):
        self.update_session_elapsed()
        self.active = False
        self.session_started = None
        self.publish()
        self.hide_bubble()
        if self.robot:
            self.robot.destroy()
            self.robot = None
        self.refresh()

    def update_session_elapsed(self):
        if self.session_started is not None:
            seconds = int(time.monotonic() - self.session_started)
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            self.session_elapsed.config(text=f'Tempo de sessão  {hours:02d}:{minutes:02d}:{seconds:02d}')

    def tick(self):
        if self.active:
            self.update_session_elapsed()
            with self.server.state_lock:
                seen = dict(self.server.last_seen)
            now = time.monotonic()
            statuses = [f"{label}: {'detectada' if now - seen.get(key, 0) < 65 else 'não detectada'}"
                        for key, label in (('brave', 'Brave'), ('chrome', 'Chrome/Chromium'), ('firefox', 'Firefox'))]
            self.connection.config(text='Extensão — ' + '  ·  '.join(statuses))
            event = False
            while not self.server.events.empty():
                self.server.events.get()
                event = True
            if minimize_blocked_app(self.data['apps']):
                event = True
            if event:
                if time.monotonic() >= self.angry_until and self.customization().get('sound', True):
                    play_alert()
                self.angry_until = time.monotonic() + 2
                if self.robot:
                    self.show_bubble()
            if self.robot:
                angry = time.monotonic() < self.angry_until
                self.draw_robot(angry)
                if not angry:
                    self.hide_bubble()
        else:
            self.connection.config(text='')
            while not self.server.events.empty():
                self.server.events.get()
        self.tick_job = self.root.after(500, self.tick)

    def close(self):
        if self.active and not messagebox.askyesno('Encerrar sessão?', 'Fechar o The Vigilant encerrará a sessão e liberará os bloqueios. Continuar?', parent=self.root):
            return
        self.active = False
        self.publish()
        self.hide_bubble()
        self.root.after_cancel(self.tick_job)
        self.server.shutdown()
        self.server.server_close()
        self.root.destroy()

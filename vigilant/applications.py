"""Interface: ApplicationsUI."""
import copy
import tkinter as tk
from .linux import installed_apps
from .theme import BLUE, INK, PANEL


class ApplicationsUI:
    """Controles para escolher os aplicativos bloqueados."""
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

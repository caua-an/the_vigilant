"""Interface: SitesUI."""
import copy
import tkinter as tk
from tkinter import messagebox
from core import PRESETS, domain_from_input
from .theme import ACCENT, BLUE, CARD, FIELD, INK, PANEL


class SitesUI:
    """Controles e ações dos bloqueios e exceções de sites."""
    def make_sites(self):
        tab = self.sites_content
        tk.Label(tab, text='SEU ESPAÇO DE FOCO  /  SITES', bg=PANEL, fg='#b4a4ff', font=('DejaVu Sans Mono', 9, 'bold')).pack(anchor='w')
        tk.Label(tab, text='Sites em pausa', bg=PANEL, fg=INK, font=('DejaVu Sans', 20, 'bold')).pack(anchor='w', pady=(8, 2))
        tk.Label(tab, text='Escolha o que fica fora da sua sessão.', bg=PANEL, fg=BLUE, justify='left').pack(anchor='w', pady=(0, 14))
        tk.Label(tab, text='SUGESTÕES RÁPIDAS', bg=PANEL, fg=BLUE, font=('DejaVu Sans', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        self.preset_vars = {}
        presets = tk.Frame(tab, bg=PANEL)
        presets.pack(fill='x', pady=(0, 16))
        for index, site in enumerate(PRESETS):
            var = tk.BooleanVar()
            self.preset_vars[site] = var
            tk.Checkbutton(presets, text=site, variable=var, bg=CARD, fg=INK, indicatoron=False,
                           selectcolor='#403181', activebackground='#3b3268', activeforeground=INK,
                           highlightthickness=1, highlightbackground=PANEL, highlightcolor='#c7bbff',
                           command=lambda s=site, v=var: self.preset_changed(s, v)).grid(row=index // 2, column=index % 2, sticky='ew', padx=(0, 8), pady=3)
        presets.columnconfigure((0, 1), weight=1, uniform='presets')
        lists = tk.Frame(tab, bg=PANEL)
        lists.pack(fill='both', expand=True)
        self.blocked_card = tk.Frame(lists, bg=CARD, padx=14, pady=12)
        self.allowed_card = tk.Frame(lists, bg=CARD, padx=14, pady=12)
        def make_card(card, title, empty, add_label, add, remove_label, remove):
            tk.Label(card, text=title, bg=CARD, fg=INK, font=('DejaVu Sans', 11, 'bold')).pack(anchor='w', pady=(0, 8))
            row = tk.Frame(card, bg=CARD)
            row.pack(fill='x', pady=(0, 8))
            entry = tk.Entry(row, font=('DejaVu Sans', 10))
            entry.pack(side='left', fill='x', expand=True, ipady=5)
            entry.bind('<Return>', lambda _: add())
            tk.Button(row, text=add_label, command=add, bg=ACCENT, fg=INK,
                      activebackground='#826cf1', highlightbackground=CARD).pack(side='left', padx=(6, 0))
            list_area = tk.Frame(card, bg=FIELD)
            list_area.pack(fill='both', expand=True)
            listing = tk.Listbox(list_area, font=('DejaVu Sans', 10), height=5, relief='flat', borderwidth=0, exportselection=False)
            listing.pack(fill='both', expand=True)
            placeholder = tk.Label(list_area, text=empty, bg=FIELD, fg=BLUE, font=('DejaVu Sans', 9))
            tk.Button(card, text=remove_label, command=remove, bg=CARD, fg=BLUE,
                      activebackground='#302b58', highlightbackground=CARD).pack(anchor='w', pady=(6, 0))
            return entry, listing, placeholder
        self.site_entry, self.site_list, self.empty_sites = make_card(
            self.blocked_card, 'Sites bloqueados', 'Nenhum site bloqueado', 'Adicionar site', self.add_site, 'Remover selecionado', self.delete_site)
        self.exception_entry, self.exception_list, self.empty_exceptions = make_card(
            self.allowed_card, 'Exceções permitidas', 'Nenhuma exceção adicionada', 'Adicionar exceção', self.add_exception, 'Remover selecionado', self.delete_exception)
        def arrange(event):
            stacked = event.width < 620
            if getattr(self, 'sites_stacked', None) == stacked:
                return
            self.sites_stacked = stacked
            self.blocked_card.grid_forget()
            self.allowed_card.grid_forget()
            lists.columnconfigure(0, weight=1, uniform='cards')
            lists.columnconfigure(1, weight=0 if stacked else 1, uniform='' if stacked else 'cards')
            self.blocked_card.grid(row=0, column=0, sticky='nsew', padx=(0, 0 if stacked else 6), pady=(0, 8 if stacked else 0))
            self.allowed_card.grid(row=1 if stacked else 0, column=0 if stacked else 1, sticky='nsew', padx=(0 if stacked else 6, 0))
        lists.bind('<Configure>', arrange)
        def reveal(event):
            widget = event.widget
            def scroll_into_view():
                if not widget.winfo_exists():
                    return
                canvas = self.sites_scroll
                top = widget.winfo_rooty() - canvas.winfo_rooty()
                bottom = top + widget.winfo_height()
                delta = top if top < 0 else max(0, bottom - canvas.winfo_height())
                bounds = canvas.bbox('all')
                if delta and bounds and bounds[3] > 0:
                    canvas.yview_moveto((canvas.canvasy(0) + delta) / bounds[3])
            self.root.after_idle(scroll_into_view)
        def bind_scroll(widget):
            widget.bind('<Button-4>', lambda _: (self.sites_scroll.yview_scroll(-1, 'units'), 'break')[1])
            widget.bind('<Button-5>', lambda _: (self.sites_scroll.yview_scroll(1, 'units'), 'break')[1])
            widget.bind('<MouseWheel>', lambda event: (self.sites_scroll.yview_scroll(-1 if event.delta > 0 else 1, 'units'), 'break')[1])
            if isinstance(widget, (tk.Button, tk.Checkbutton, tk.Entry, tk.Listbox)):
                widget.bind('<FocusIn>', reveal, add='+')
            for child in widget.winfo_children():
                bind_scroll(child)
        bind_scroll(tab)

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

    def add_exception(self):
        try:
            site = domain_from_input(self.exception_entry.get())
        except ValueError as exc:
            messagebox.showerror('Exceção inválida', str(exc), parent=self.root)
            return
        data = copy.deepcopy(self.data)
        exceptions = data.setdefault('site_exceptions', [])
        if site not in exceptions:
            exceptions.append(site)
        if self.commit(data):
            self.exception_entry.delete(0, 'end')

    def delete_exception(self):
        index = self.selected(self.exception_list)
        if index is not None:
            data = copy.deepcopy(self.data)
            data['site_exceptions'].pop(index)
            self.commit(data)

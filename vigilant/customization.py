"""Interface: CustomizationUI."""
import copy
import time
import tkinter as tk
from tkinter import messagebox, ttk
from .robot import DEFAULT_COLORS, EYES, METALS, VISORS
from .theme import BLUE, INK, PANEL


class CustomizationUI:
    """Controles de aparência, som e frases do robô."""
    def customization(self):
        return self.data.get('customization', {})

    def set_customization(self, **changes):
        data = copy.deepcopy(self.data)
        data.setdefault('customization', {}).update(changes)
        if self.commit(data):
            self.draw_robot(False, self.preview)
            if self.robot:
                self.draw_robot(time.monotonic() < self.angry_until)
        else:
            self.refresh_customization()

    def make_customization(self):
        header = tk.Frame(self.custom_tab, bg=PANEL)
        header.pack(fill='x')
        self.preview = tk.Canvas(header, width=72, height=72, bg=PANEL, highlightthickness=0)
        self.preview.pack(side='right', padx=(8, 4))
        tk.Label(header, text='Seu Vigilant', bg=PANEL, fg=INK, font=('DejaVu Sans', 15, 'bold')).pack(anchor='w')
        tk.Label(header, text='Escolha as cores e como ele conversa com você.', bg=PANEL, fg=BLUE).pack(anchor='w', pady=(2, 8))
        self.draw_robot(False, self.preview)
        colors = tk.Frame(self.custom_tab, bg=PANEL)
        colors.pack(fill='x')
        self.color_vars = {}
        for col, (key, label, choices) in enumerate((('metal', 'Metal', METALS), ('visor', 'Visor', VISORS), ('eyes', 'Olhos', EYES))):
            section = tk.Frame(colors, bg=PANEL)
            section.grid(row=0, column=col, sticky='ew', padx=(0, 8))
            colors.columnconfigure(col, weight=1)
            tk.Label(section, text=label, bg=PANEL, fg=INK).pack(anchor='w')
            var = tk.StringVar()
            self.color_vars[key] = var
            combo = ttk.Combobox(section, textvariable=var, values=list(choices), state='readonly', width=15)
            combo.pack(fill='x', pady=(4, 4))
            combo.bind('<<ComboboxSelected>>', lambda _, k=key, v=var: self.set_customization(**{k: v.get()}))
        options = tk.Frame(self.custom_tab, bg=PANEL)
        options.pack(fill='x', pady=(2, 4))
        tk.Button(options, text='Restaurar cores', command=lambda: self.set_customization(**DEFAULT_COLORS)).pack(side='left')
        self.sound_var = tk.BooleanVar()
        self.adult_var = tk.BooleanVar()
        tk.Checkbutton(options, text='Som', bg=PANEL, variable=self.sound_var, command=lambda: self.set_customization(sound=self.sound_var.get())).pack(side='left', padx=(12, 0))
        tk.Checkbutton(options, text='Modo adulto', bg=PANEL, variable=self.adult_var, command=lambda: self.set_customization(adult=self.adult_var.get())).pack(side='left')
        tk.Label(self.custom_tab, text='Suas frases', bg=PANEL, fg=INK, font=('DejaVu Sans', 10, 'bold')).pack(anchor='w', pady=(4, 0))
        row = tk.Frame(self.custom_tab, bg=PANEL)
        row.pack(fill='x', pady=4)
        self.message_entry = tk.Entry(row)
        self.message_entry.pack(side='left', fill='x', expand=True, ipady=3)
        self.message_entry.bind('<Return>', lambda _: self.add_message())
        self.message_adult_var = tk.BooleanVar()
        tk.Checkbutton(row, text='Adulta', bg=PANEL, variable=self.message_adult_var).pack(side='left')
        tk.Button(row, text='Adicionar', command=self.add_message).pack(side='left')
        self.message_list = tk.Listbox(self.custom_tab, height=3, relief='flat', borderwidth=0)
        self.message_list.pack(fill='both', expand=True)
        tk.Button(self.custom_tab, text='Excluir frase selecionada', command=self.delete_message).pack(anchor='w', pady=(5, 0))
        self.refresh_customization()

    def refresh_customization(self):
        settings = self.customization()
        for key, var in self.color_vars.items():
            var.set(settings.get(key, DEFAULT_COLORS[key]))
        self.sound_var.set(settings.get('sound', True))
        self.adult_var.set(settings.get('adult', False))
        self.message_list.delete(0, 'end')
        for item in settings.get('messages', []):
            self.message_list.insert('end', ('[Adulta] ' if item['adult'] else '[Normal] ') + item['text'])

    def add_message(self):
        text = self.message_entry.get().strip()
        if not text:
            return
        if len(text) > 90:
            messagebox.showerror('Frase muito longa', 'Use até 90 caracteres para caber no balão.', parent=self.root)
            return
        messages = copy.deepcopy(self.customization().get('messages', []))
        messages.append({'text': text, 'adult': self.message_adult_var.get()})
        self.set_customization(messages=messages)
        self.message_entry.delete(0, 'end')

    def delete_message(self):
        index = self.selected(self.message_list)
        if index is not None:
            messages = copy.deepcopy(self.customization().get('messages', []))
            messages.pop(index)
            self.set_customization(messages=messages)

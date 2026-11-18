"""Interface: TasksUI."""
import copy
import tkinter as tk
from tkinter import messagebox
from .theme import BLUE, INK, PANEL


class TasksUI:
    """Controles e ações das tarefas; usados pela janela Vigilant."""
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

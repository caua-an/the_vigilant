#!/usr/bin/env python3
"""Ponto de entrada do The Vigilant."""
import json
import tkinter as tk
from tkinter import messagebox

from vigilant.app import Vigilant


if __name__ == '__main__':
    root = tk.Tk()
    try:
        Vigilant(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        messagebox.showerror('The Vigilant não iniciou', f'Verifique os dados salvos e se outra instância já está aberta.\n\n{exc}', parent=root)
        root.destroy()
    else:
        root.mainloop()

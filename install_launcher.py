#!/usr/bin/env python3
"""Instala um atalho do The Vigilant no menu do usuário Linux."""
import os
import sys
from pathlib import Path


def desktop_quote(value):
    value = str(value).replace('%', '%%')
    return '"' + ''.join('\\' + c if c in '\\"`$' else c for c in value) + '"'


def main():
    if not sys.platform.startswith('linux'):
        print('O instalador de atalho está disponível somente no Linux.', file=sys.stderr)
        return 1
    project = Path(__file__).resolve().parent
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    destination = data / 'applications' / 'the-vigilant.desktop'
    contents = ('[Desktop Entry]\nType=Application\nName=The Vigilant\n'
                'Comment=Organize seus estudos e mantenha o foco\n'
                f'Exec={desktop_quote(sys.executable)} {desktop_quote(project / "main.py")}\n'
                f'Icon={project / "icon.svg"}\n'
                f'Path={project}\nTerminal=false\nCategories=Education;Utility;\n')
    if destination.exists():
        if destination.read_text(encoding='utf-8') == contents:
            print(f'O atalho já está instalado: {destination}')
            return 0
        print(f'O arquivo {destination} já existe e não será substituído. Remova-o ou renomeie-o antes de reinstalar.', file=sys.stderr)
        return 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as file:
        file.write(contents)
    print(f'Atalho instalado: {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

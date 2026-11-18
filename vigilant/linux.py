"""Integração com aplicativos instalados no Linux."""
import configparser
import glob
import os
import shlex
import shutil
import subprocess
from pathlib import Path


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


def monitoring_available():
    return os.environ.get('XDG_SESSION_TYPE') == 'x11' and bool(shutil.which('xdotool')) and bool(shutil.which('xprop'))


def minimize_blocked_app(apps):
    if not apps or not shutil.which('xdotool') or not shutil.which('xprop'):
        return False
    try:
        window = subprocess.check_output(['xdotool', 'getactivewindow'], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
        pid = subprocess.check_output(['xdotool', 'getwindowpid', window], text=True, stderr=subprocess.DEVNULL, timeout=1).strip()
        classes = subprocess.check_output(['xprop', '-id', window, 'WM_CLASS'], text=True, stderr=subprocess.DEVNULL, timeout=1).split('=', 1)[-1].replace('"', '').split(',')
        names = {name.strip().casefold() for name in classes}
        try:
            names.add(Path(f'/proc/{pid}/comm').read_text().strip().casefold())
        except OSError:
            pass
        if any(app['id'].casefold() in names for app in apps):
            subprocess.run(['xdotool', 'windowminimize', window], stderr=subprocess.DEVNULL, timeout=1, check=True)
            return True
    except (OSError, subprocess.SubprocessError):
        pass
    return False

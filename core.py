import ipaddress
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

DATA_FILE = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'the-vigilant' / 'data.json'
PRESETS = ['youtube.com', 'x.com', 'instagram.com', 'tiktok.com']


def domain_from_input(value):
    value = value.strip()
    if not value:
        raise ValueError('Informe um endereço de site.')
    try:
        parts = urlsplit(value if '://' in value else 'https://' + value)
        host = (parts.hostname or '').rstrip('.').lower().encode('idna').decode('ascii')
        if parts.scheme not in ('http', 'https') or parts.username or parts.password or not host:
            raise ValueError
        if parts.port is not None and not 0 < parts.port < 65536:
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        labels = host.split('.')
        if len(labels) < 2 or any(not label or len(label) > 63 or label[0] == '-' or label[-1] == '-' or any(not (c.isascii() and (c.isalnum() or c == '-')) for c in label) for label in labels):
            raise ValueError
        if host.startswith('www.') and len(labels) > 2:
            host = host[4:]
        return host
    except (ValueError, UnicodeError):
        raise ValueError('Informe um domínio válido, como youtube.com.') from None


def load_data():
    if not DATA_FILE.exists():
        return {'tasks': [], 'sites': [], 'apps': []}
    with DATA_FILE.open(encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ('tasks', 'sites', 'apps')):
        raise ValueError('Formato de dados inválido.')
    return data


def save_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=DATA_FILE.parent, prefix='.data-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(name, DATA_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)

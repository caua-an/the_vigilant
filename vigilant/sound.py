"""Som de alerta sem dependências Python adicionais."""
import io
import math
import shutil
import subprocess
import threading
import wave


def alert_sound():
    rate = 16000
    samples = bytearray()
    for i in range(rate * 2):
        t = i / rate
        envelope = min(1, t * 20, (2 - t) * 8)
        tone = math.sin(2 * math.pi * (440 if t < 0.9 else 330) * t)
        samples.extend(int(128 + 32 * envelope * tone).to_bytes(1, 'little'))
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as output:
        output.setparams((1, 1, rate, 0, 'NONE', 'not compressed'))
        output.writeframes(samples)
    return buffer.getvalue()


def play_alert():
    player = shutil.which('paplay')
    if not player:
        return
    def play():
        try:
            subprocess.run([player], input=alert_sound(), stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
    threading.Thread(target=play, daemon=True).start()

"""One bounded 0.8 s / 0.03 m/s trial through the real keyboard HTTP bridge."""
import json
from pathlib import Path
import re
import time
import urllib.request

client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
base = 'http://127.0.0.1:8765'
with client.open(base, timeout=1) as response:
    token = re.search("const token='([^']+)'", response.read().decode()).group(1)
sequence = int(time.time()*1000)*1000
samples = []

def send(kind, v=0.0):
    global sequence
    sequence += 1
    data = json.dumps(dict(type=kind, seq=sequence, v=v, w=0.0)).encode()
    request = urllib.request.Request(base+'/input', data=data,
        headers={'Content-Type':'application/json', 'X-Control-Token':token})
    with client.open(request, timeout=0.3) as response:
        response.read()

def status():
    with client.open(base+'/status', timeout=0.3) as response:
        value = json.load(response)
    samples.append(dict(t=time.time(), **value))
    return value

error = None
started = False
try:
    # This newer sequence temporarily takes ownership from an already-open page.
    send('stop')
    deadline = time.monotonic()+0.5
    while time.monotonic() < deadline:
        send('command')
        status()
        time.sleep(0.05)
    send('arm')
    deadline = time.monotonic()+0.4
    while time.monotonic() < deadline:
        send('command')
        if status()['armed']:
            break
        time.sleep(0.03)
    else:
        raise RuntimeError('Control did not arm')
    started = True
    end = time.monotonic()+0.8
    while time.monotonic() < end:
        value = status()
        if not value['armed']:
            raise RuntimeError('Control enable lost; trial stopped')
        send('command', 0.03)
        time.sleep(0.04)
finally:
    # Always disarm, including on a network or application error.
    for _ in range(5):
        try:
            send('stop')
        except Exception:
            pass
        time.sleep(0.05)
    result = dict(started=started, samples=samples, final=status())
    Path(__file__).with_name('trial-command.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(dict(started=started,
        nonzero_samples=sum(s['v']>0 for s in samples), final=result['final'])))

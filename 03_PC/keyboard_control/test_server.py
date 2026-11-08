"""End-to-end localhost preview test. Never runs WSL or ROS."""
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request


class PreviewHTTPTest(unittest.TestCase):
    def test_preview_commands_and_timeout(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, '-B', str(Path(__file__).with_name('keyboard_server.py')),
             '--preview', '--no-browser', '--port', str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{port}'

        def get(path):
            with opener.open(base+path, timeout=1) as response:
                return response.read().decode('utf-8')

        def send(packet, token):
            request = urllib.request.Request(base+'/input',
                data=json.dumps(packet).encode(),
                headers={'Content-Type': 'application/json', 'X-Control-Token': token})
            with opener.open(request, timeout=1) as response:
                return response.status

        try:
            deadline = time.monotonic()+5
            while True:
                try:
                    html = get('/')
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() > deadline:
                        self.fail('Preview server failed to start')
                    time.sleep(0.05)
            token = re.search("const token='([^']+)'", html).group(1)
            self.assertNotEqual(token, '__TOKEN__')
            self.assertTrue(json.loads(get('/status'))['preview'])
            with self.assertRaises(urllib.error.HTTPError) as failure:
                send({'type': 'arm', 'seq': 0}, 'wrong-token')
            self.assertEqual(failure.exception.code, 403)
            send({'type': 'arm', 'seq': 1}, token)
            send({'type': 'command', 'seq': 2, 'v': 0.03, 'w': 0}, token)
            value = json.loads(get('/status'))
            self.assertTrue(value['armed'])
            self.assertGreaterEqual(value['v'], 0.0)
            self.assertLessEqual(value['v'], 0.03)
            send({'type': 'stop', 'seq': 4}, token)
            with self.assertRaises(urllib.error.HTTPError) as stale:
                send({'type': 'arm', 'seq': 3}, token)
            self.assertEqual(stale.exception.code, 409)
            self.assertFalse(json.loads(get('/status'))['armed'])
            send({'type': 'arm', 'seq': 5}, token)
            send({'type': 'command', 'seq': 6, 'v': -0.03, 'w': 0}, token)
            time.sleep(0.36)
            value = json.loads(get('/status'))
            self.assertFalse(value['armed'])
            self.assertEqual(value['v'], 0)
        finally:
            process.terminate()
            process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()

"""Local Windows panel. --preview never starts WSL or ROS."""
import argparse
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from control_state import ControlState

ROOT = Path(__file__).resolve().parent


def wsl_path(path):
    text = str(path).replace('\\', '/')
    if len(text) < 3 or text[1:3] != ':/':
        raise ValueError('程序必须存放于 Windows 本地盘符路径')
    return '/mnt/' + text[0].lower() + text[2:]


class Backend:
    def __init__(self, preview, distro):
        self.preview = preview
        self.lock = threading.Lock()
        self.sequence = -1
        self.accepted_inputs = 0
        self.stale_inputs = 0
        self.last_input = None
        self.status = dict(armed=False, connected=False, reason='正在启动 ROS 2',
                           v=0.0, w=0.0, preview=preview)
        self.updated = time.monotonic()
        self.state = ControlState()
        self.proc = None
        if not preview:
            command = ('source /opt/ros/humble/setup.bash && '
                       'export ROS_DOMAIN_ID=0 && exec python3 -u ' +
                       shlex.quote(wsl_path(ROOT / 'ros_bridge.py')))
            self.log = (ROOT / 'keyboard_bridge.log').open('w', encoding='utf-8')
            self.proc = subprocess.Popen(
                ['wsl.exe', '-d', distro, '--', 'bash', '-lc', command],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                text=True, encoding='utf-8', bufsize=1)
            threading.Thread(target=self.read_status, daemon=True).start()

    def read_status(self):
        try:
            for line in self.proc.stdout:
                try:
                    status = json.loads(line)
                    if isinstance(status, dict) and 'armed' in status:
                        with self.lock:
                            self.status = status
                            self.updated = time.monotonic()
                except ValueError:
                    continue
        finally:
            with self.lock:
                self.status.update(armed=False, connected=False, v=0.0, w=0.0,
                                   reason='ROS 进程已退出；请查看 keyboard_bridge.log')

    def send(self, packet):
        with self.lock:
            sequence = packet.get('seq')
            if type(sequence) is not int:
                raise ValueError('Missing sequence number')
            if sequence <= self.sequence:
                self.stale_inputs += 1
                return False
            self.sequence = sequence
            if self.preview:
                self.state.receive(packet, time.monotonic(), True)
            else:
                if self.proc.poll() is not None:
                    raise RuntimeError('ROS 进程未运行')
                self.proc.stdin.write(json.dumps(packet, allow_nan=False) + '\n')
                self.proc.stdin.flush()
            self.accepted_inputs += 1
            self.last_input = dict(type=packet.get('type'), seq=sequence, v=packet.get('v', 0), w=packet.get('w', 0), received=time.monotonic())
            return True

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            if self.preview:
                v, w = self.state.output(now, True)
                return dict(armed=self.state.armed, connected=True, v=v, w=w,
                            reason=self.state.reason, preview=True)
            value = self.status.copy()
            value['input_diagnostics'] = dict(accepted=self.accepted_inputs, rejected_stale=self.stale_inputs, last=self.last_input)
            if now - self.updated > 0.60:
                value.update(armed=False, connected=False, v=0.0, w=0.0,
                             reason='ROS 状态超时；控制已停止')
            return value

    def close(self):
        if self.proc:
            try:
                self.send({'type': 'stop', 'seq': self.sequence + 1})
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                if self.proc.poll() is None:
                    self.proc.terminate()
            self.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--distro', default='Ubuntu')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    token = secrets.token_urlsafe(24)
    backend = Backend(args.preview, args.distro)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, code, body, content_type='application/json; charset=utf-8'):
            data = body.encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/':
                self.respond(200, (ROOT / 'panel.html').read_text(encoding='utf-8')
                             .replace('__TOKEN__', token), 'text/html; charset=utf-8')
            elif self.path == '/status':
                self.respond(200, json.dumps(backend.snapshot()))
            else:
                self.respond(404, '{}')

        def do_POST(self):
            if self.path != '/input' or self.headers.get('X-Control-Token') != token:
                self.respond(403, '{}')
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 1024:
                    raise ValueError('Invalid body length')
                packet = json.loads(self.rfile.read(length))
                if not isinstance(packet, dict):
                    raise ValueError('Expected an object')
                if not backend.send(packet):
                    self.respond(409, json.dumps({'error': '控制指令已过期或被其他页面/工具接管；请刷新，并只保留一个遥控页面。', 'code': 'stale_sequence'}))
                    return
                self.respond(200, json.dumps({'accepted': True}))
            except (ValueError, OSError, RuntimeError) as error:
                self.respond(400, json.dumps({'error': str(error)}))

    server = None
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
        print(('离线预览，不发送 ROS 指令。' if args.preview else 'ROS 2 键盘控制。') +
              f' 打开 http://127.0.0.1:{args.port} ，Ctrl+C 关闭。', flush=True)
        if not args.no_browser:
            webbrowser.open(f'http://127.0.0.1:{args.port}')
        server.serve_forever(poll_interval=0.10)
    except KeyboardInterrupt:
        pass
    finally:
        backend.close()
        if server:
            server.server_close()


if __name__ == '__main__':
    main()

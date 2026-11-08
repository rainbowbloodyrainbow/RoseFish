"""Offline binary preservation and fragmented packet checks on Linux."""
import os
from pathlib import Path
import select
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import time
import tty
import unittest
from lidar_tcp_bridge import PacketCheck


def packet(samples=(400, 800, 1200)):
    fields = [0x55AA, len(samples) << 8, 1, 257]
    checksum = 0
    for value in fields + list(samples):
        checksum ^= value
    return struct.pack('<5H', *fields, checksum) + struct.pack('<'+'H'*len(samples), *samples)


class Checks(unittest.TestCase):
    def test_fragmentation_and_checksum(self):
        check = PacketCheck()
        raw = b'noise' + packet() + packet()
        for byte in raw:
            check.feed(bytes([byte]))
        self.assertEqual(check.valid, 2)
        self.assertEqual(check.bad, 0)
        broken = bytearray(packet())
        broken[-1] ^= 1
        check.feed(broken + packet())
        self.assertEqual(check.valid, 3)
        self.assertGreaterEqual(check.bad, 1)

    def test_reset_does_not_join_sessions(self):
        check = PacketCheck()
        data = packet()
        check.feed(data[:7])
        check.reset()
        check.feed(data[7:] + data)
        self.assertEqual(check.valid, 1)

    def test_tcp_to_pty_preserves_binary(self):
        with tempfile.TemporaryDirectory(prefix='lidar_bridge_') as temp:
            path = Path(temp)/'serial'
            with socket.socket() as server, open(Path(temp)/'log','w+') as log:
                server.bind(('127.0.0.1', 0))
                server.listen(1)
                server.settimeout(5)
                port = server.getsockname()[1]
                process = subprocess.Popen([sys.executable,
                    str(Path(__file__).with_name('lidar_tcp_bridge.py')),
                    '--host','127.0.0.1','--port',str(port),'--serial',str(path)],
                    stdout=log,stderr=subprocess.STDOUT)
                fd = None
                try:
                    with server.accept()[0] as peer:
                        fd = os.open(path, os.O_RDWR|os.O_NOCTTY)
                        tty.setraw(fd)
                        payload = bytes(range(256))*16 + b'\x00\r\n\xff\xaa\x55'
                        # Split a binary payload across arbitrary TCP sends.
                        for i in range(0,len(payload),37):
                            peer.sendall(payload[i:i+37])
                        actual = bytearray()
                        deadline = time.monotonic()+5
                        while len(actual)<len(payload) and time.monotonic()<deadline:
                            if select.select([fd],[],[],.2)[0]:
                                actual.extend(os.read(fd,8192))
                        self.assertEqual(actual,payload)
                finally:
                    if fd is not None: os.close(fd)
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=5)

    def test_silent_connection_is_reconnected(self):
        with tempfile.TemporaryDirectory(prefix='lidar_reconnect_') as temp:
            path = Path(temp)/'serial'
            with socket.socket() as server, open(Path(temp)/'log', 'w+') as log:
                server.bind(('127.0.0.1', 0))
                server.listen(2)
                server.settimeout(5)
                process = subprocess.Popen([sys.executable,
                    str(Path(__file__).with_name('lidar_tcp_bridge.py')),
                    '--host','127.0.0.1','--port',str(server.getsockname()[1]),
                    '--serial',str(path),'--idle-timeout','0.3'],
                    stdout=log,stderr=subprocess.STDOUT)
                fd = None
                try:
                    with server.accept()[0] as silent:
                        with server.accept()[0] as recovered:
                            fd = os.open(path, os.O_RDWR|os.O_NOCTTY)
                            tty.setraw(fd)
                            recovered.sendall(packet())
                            self.assertTrue(select.select([fd],[],[],2)[0])
                            self.assertEqual(os.read(fd,1024),packet())
                finally:
                    if fd is not None: os.close(fd)
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()

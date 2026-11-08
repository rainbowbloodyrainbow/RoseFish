#!/usr/bin/env python3
"""Linux TCP client to raw PTY. No third-party packages or ROS required."""
import argparse
import errno
import json
import os
from pathlib import Path
import select
import signal
import socket
import struct
import termios
import time
import tty


class PacketCheck:
    """Diagnostic checker for the observed no-intensity AA55 wire format.

    It never changes the raw bytes passed to the serial driver. A matching
    checksum confirms a packet, not calibrated range/angle values.
    """
    def __init__(self):
        self.buffer = bytearray()
        self.valid = self.bad = self.discarded = 0

    def reset(self):
        self.buffer.clear()

    def feed(self, data):
        self.buffer.extend(data)
        while len(self.buffer) >= 2:
            start = self.buffer.find(b'\xaa\x55')
            if start < 0:
                keep = 1 if self.buffer[-1] == 0xAA else 0
                self.discarded += len(self.buffer) - keep
                self.buffer[:] = self.buffer[-1:] if keep else b''
                return
            if start:
                self.discarded += start
                del self.buffer[:start]
            if len(self.buffer) < 10:
                return
            samples = self.buffer[3]
            if not samples:
                self.bad += 1
                del self.buffer[0]
                continue
            length = 10 + samples * 2
            if len(self.buffer) < length:
                return
            header, ct_lsn, first, last, expected = struct.unpack_from('<5H', self.buffer)
            actual = header ^ ct_lsn ^ first ^ last
            for offset in range(10, length, 2):
                actual ^= struct.unpack_from('<H', self.buffer, offset)[0]
            if actual != expected:
                self.bad += 1
                del self.buffer[0]
            else:
                self.valid += 1
                del self.buffer[:length]


def stream_status(args, receiving, **extra):
    if args.status_file:
        Path(args.status_file).write_text(json.dumps(dict(updated=time.time(), receiving=receiving, **extra)))


def run(args):
    stream_status(args, False, state="starting")
    path = Path(args.serial)
    master, slave = os.openpty()
    tty.setraw(master)
    tty.setraw(slave)
    os.set_blocking(master, False)
    slave_name = os.ttyname(slave)
    # Never replace an unrelated file, physical device, or another bridge's PTY.
    try:
        path.symlink_to(slave_name)
    except FileExistsError:
        os.close(master)
        os.close(slave)
        raise RuntimeError(f'{path} already exists; stop its owner or choose --serial')
    print(f'PTY_READY {path} -> {slave_name}', flush=True)
    check = PacketCheck()
    totals = dict(bytes=0, pty_bytes=0, control_bytes=0, reconnects=0)
    record = open(args.record, 'ab') if args.record else None
    try:
        while True:
            # Old bytes must not be replayed into a new network session.
            termios.tcflush(slave, termios.TCIOFLUSH)
            check.reset()
            pending = bytearray()
            try:
                connection = socket.create_connection((args.host, args.port), timeout=5)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 3)
                connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
                connection.setblocking(False)
                totals['reconnects'] += 1
                print(f'TCP_CONNECTED {args.host}:{args.port}', flush=True)
                report = time.monotonic()
                last_data = report
                last_bytes = totals['bytes']
                with connection:
                    while True:
                        readers, writers, _ = select.select(
                            [connection, master], [master] if pending else [], [], 0.2)
                        if connection in readers:
                            data = connection.recv(16384)
                            if not data:
                                raise ConnectionError('S3 closed the stream')
                            totals['bytes'] += len(data)
                            last_data = time.monotonic()
                            check.feed(data)
                            if record:
                                record.write(data)
                            pending.extend(data)
                            if len(pending) > 131072:
                                raise BufferError('PTY consumer stalled; stream closed instead of silently losing bytes')
                        if master in writers and pending:
                            try:
                                count = os.write(master, pending)
                                del pending[:count]
                                totals['pty_bytes'] += count
                            except BlockingIOError:
                                pass
                        if master in readers:
                            try:
                                controls = os.read(master, 4096)
                            except OSError as error:
                                if error.errno != errno.EIO:
                                    raise
                                controls = b''
                            # Current hardware has only lidar TX -> S3 RX.
                            # Consume SDK control writes; no physical reverse
                            # channel exists. Never echo them into scan data.
                            totals['control_bytes'] += len(controls)
                        now = time.monotonic()
                        if now - last_data > args.idle_timeout:
                            raise TimeoutError(f'No lidar bytes for {args.idle_timeout:g} seconds; reconnecting')
                        if now - report >= 1:
                            stream_status(args, True, state="streaming", bytes=totals["bytes"], valid_packets=check.valid)
                            print(json.dumps({**totals,
                                'bytes_per_s': round((totals['bytes'] - last_bytes)/(now-report)),
                                'valid_packets': check.valid,
                                'bad_checksums': check.bad,
                                'pending': len(pending)}), flush=True)
                            last_bytes = totals['bytes']
                            report = now
            except (OSError, ConnectionError, BufferError) as error:
                stream_status(args, False, state="retry", error=str(error))
                print(f'TCP_RETRY {type(error).__name__}: {error}', flush=True)
                # No blind mixing of the partial old stream with a reconnect.
                termios.tcflush(slave, termios.TCIOFLUSH)
                check.reset()
                time.sleep(1)
    except KeyboardInterrupt:
        print('Bridge stopped', flush=True)
    finally:
        stream_status(args, False, state="stopped")
        if record:
            record.close()
        if path.is_symlink() and os.readlink(path) == slave_name:
            path.unlink()
        os.close(master)
        os.close(slave)


if __name__ == '__main__':
    def stop(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status-file')
    parser.add_argument('--host', required=True, help='S3 IP printed as TCP_READY on USB console')
    parser.add_argument('--port', type=int, default=8889)
    parser.add_argument('--serial', default='/tmp/lidar_wifi')
    parser.add_argument('--record', help='Optional raw capture; appends across sessions')
    parser.add_argument('--idle-timeout', type=float, default=8,
                        help='Reconnect a silent/stale TCP peer after this many seconds')
    run(parser.parse_args())

#!/usr/bin/env python3
"""Lightweight HTTP server that briefly breaks a circuit using a relay.

POST /pulse  -> break the circuit for break_seconds (replies immediately)
                contact=nc: relay idle OFF, turned ON during the break
                contact=no: relay idle ON,  turned OFF during the break
POST /rearm  -> end a running break now (reconnect the circuit)
GET  /health -> "ok"

Only the Python standard library and gpiozero are used, so it runs on the
original Raspberry Pi (ARMv6, 256/512 MB RAM).
"""

import argparse
import json
import logging
import signal
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import load_config

log = logging.getLogger("raspi-relay")


class FakeRelay:
    """Stand-in for gpiozero.OutputDevice, used with --fake-gpio for testing."""

    def on(self):
        log.info("[fake] relay ON")

    def off(self):
        log.info("[fake] relay OFF")

    def close(self):
        pass


def make_relay(pin, active_high, idle_on, fake):
    if fake:
        return FakeRelay()
    from gpiozero import OutputDevice  # imported here so --fake-gpio works without it

    # Start in the idle state, so the circuit is connected right away
    return OutputDevice(pin, active_high=active_high, initial_value=idle_on)


class RelayController:
    """Keeps the relay in its idle state and breaks the circuit on request.

    idle_on=False (NC wiring): idle OFF, break = ON
    idle_on=True  (NO wiring): idle ON,  break = OFF
    """

    def __init__(self, relay, break_seconds, idle_on):
        self.relay = relay
        self.break_seconds = break_seconds
        self.idle_on = idle_on
        self.lock = threading.Lock()
        # Event of the break in progress (None when idle). Setting it ends the
        # break early; each break gets its own Event so old timers can't
        # interfere with a newer break.
        self.current = None

    def _set(self, on):
        self.relay.on() if on else self.relay.off()

    def idle(self):
        self._set(self.idle_on)

    def pulse(self):
        """Start breaking the circuit. Returns False if a break is already running."""
        with self.lock:
            if self.current is not None:
                return False
            ev = threading.Event()
            self.current = ev
            self._set(not self.idle_on)
        log.info("break start (%.2fs)", self.break_seconds)
        threading.Thread(target=self._run, args=(ev,), daemon=True).start()
        return True

    def _run(self, ev):
        rearmed = ev.wait(self.break_seconds)
        with self.lock:
            if self.current is ev:
                self.idle()
                self.current = None
        if not rearmed:
            log.info("break end")

    def rearm(self):
        """End a running break now. Returns True if a break was running."""
        with self.lock:
            ev = self.current
            self.current = None
            self.idle()  # always re-assert the idle state
        if ev is None:
            return False
        ev.set()
        log.info("break end (rearmed)")
        return True


class Handler(BaseHTTPRequestHandler):
    controller = None  # set in main()
    server_version = "raspi-relay/1.0"

    def _send(self, code, body):
        data = json.dumps(body).encode() + b"\n"
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # Read and discard any request body so the connection stays clean
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(min(length, 65536))

        path = self.path.rstrip("/")
        c = self.controller
        if path == "/pulse":
            if c.pulse():
                self._send(200, {"result": "ok", "break_seconds": c.break_seconds})
            else:
                self._send(409, {"result": "busy"})
        elif path == "/rearm":
            self._send(200, {"result": "rearmed" if c.rearm() else "idle"})
        else:
            self._send(404, {"result": "not found"})

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            return self._send(200, {"result": "ok"})
        self._send(404, {"result": "not found"})

    def log_message(self, fmt, *args):
        log.info("%s %s", self.client_address[0], fmt % args)


class DualStackServer(ThreadingHTTPServer):
    """Listens on IPv6 and IPv4 at the same time when bound to '::'."""

    address_family = socket.AF_INET6
    daemon_threads = True

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        except (AttributeError, OSError):
            pass
        super().server_bind()


def make_server(bind, port):
    if ":" in bind:
        try:
            return DualStackServer((bind, port), Handler)
        except OSError as e:
            log.warning("IPv6 bind failed (%s); falling back to IPv4 0.0.0.0", e)
            bind = "0.0.0.0"
    srv = ThreadingHTTPServer((bind, port), Handler)
    srv.daemon_threads = True
    return srv


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", help="config file path")
    ap.add_argument("--fake-gpio", action="store_true",
                    help="do not touch GPIO (for testing on a PC)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)s %(message)s")

    cfg, path = load_config(args.config)
    log.info("config: %s", path or "(defaults)")

    pin = cfg.getint("relay", "gpio_pin")
    active_high = cfg.getboolean("relay", "active_high")
    break_seconds = min(max(cfg.getfloat("relay", "break_seconds"), 0.05), 3600.0)
    contact = cfg.get("relay", "contact").strip().lower()
    if contact not in ("nc", "no"):
        log.error("contact must be nc or no, not '%s'; using nc", contact)
        contact = "nc"
    idle_on = contact == "no"
    port = cfg.getint("server", "port")
    bind = cfg.get("server", "bind").strip() or "::"

    relay = make_relay(pin, active_high, idle_on, args.fake_gpio)
    controller = RelayController(relay, break_seconds, idle_on)
    controller.idle()
    Handler.controller = controller

    srv = make_server(bind, port)

    def shutdown(signum, frame):
        log.info("signal %d, shutting down", signum)
        threading.Thread(target=srv.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("GPIO%d active_high=%s contact=%s break=%.2fs, listening on [%s]:%d",
             pin, active_high, contact, break_seconds, bind, port)
    try:
        srv.serve_forever()
    finally:
        # Leave the circuit connected. With NO wiring the circuit still breaks
        # once this process exits and the GPIO is released.
        controller.idle()
        relay.close()
        srv.server_close()
        log.info("stopped")


if __name__ == "__main__":
    main()

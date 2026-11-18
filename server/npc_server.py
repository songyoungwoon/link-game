#!/usr/bin/env python3
# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""LINK NPC travel demo: autonomous simulation, read-only observers and trusted handoff."""
from __future__ import annotations
import argparse
import ipaddress
from pathlib import Path
import socket
import sys
import threading
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import npc
from server.vendor import link_server as asset

ROOT = Path(__file__).resolve().parents[1]
JOIN, JOINED, STEP, STATE, LEAVE, FAIL = 16, 17, 18, 19, 20, 21
TRANSFER, TRANSFERRED = 32, 33
PROFILE = "npc-travel-v1"
TRANSFER_TIMEOUT = 2.0


def send(connection, kind, request_id, value):
    asset.send_frame(connection, kind, request_id, npc.encode(value))


def exchange(peer, payload, key):
    host, port, _ = npc.address(peer)
    deadline = time.monotonic() + TRANSFER_TIMEOUT
    with socket.create_connection((host, port), timeout=TRANSFER_TIMEOUT) as connection:
        body = npc.encode(npc.signed(payload, key))
        connection.settimeout(max(.001, deadline - time.monotonic()))
        connection.sendall(asset.HEADER.pack(b"LINK", 0, 1, TRANSFER, 0, 0, len(body)) + body)
        raw = asset.receive_exact(connection, asset.HEADER.size, deadline)
        magic, major, minor, kind, flags, request_id, length = asset.HEADER.unpack(raw)
        npc.require((magic, major, minor, kind, flags, request_id) == (b"LINK", 0, 1, TRANSFERRED, 0, 0) and 1 <= length <= npc.MAX_JSON, "NPC handoff response was rejected.")
        return npc.decode(asset.receive_exact(connection, length, deadline))


class NpcHandler(asset.LinkTCPHandler):
    def _header(self, deadline):
        if hasattr(self, "first_header"):
            result = self.first_header
            del self.first_header
            return result
        return super()._header(deadline)

    def handle(self):
        request_id = 0
        try:
            deadline = time.monotonic() + asset.REQUEST_TIMEOUT
            kind, request_id, size = self._header(deadline)
            if kind == asset.MESSAGE_HELLO:
                self.first_header = (kind, request_id, size)
                return super().handle()
            npc.require(request_id == 0 and 1 <= size <= npc.MAX_JSON)
            value = npc.decode(asset.receive_exact(self.request, size, deadline))
            if kind == TRANSFER:
                response = self.server.world.accept(value)
                send(self.request, TRANSFERRED, 0, response)
                return
            npc.require(kind == JOIN, "Expected an NPC observer JOIN or a trusted transfer.")
            npc.exact(value, {"version", "world", "profile"})
            npc.integer(value["version"], 1, 1)
            npc.require(value["world"] == self.server.slug and value["profile"] == PROFILE, "This server requires npc-travel-v1 for its configured world.")
            npc.require(not self.server.tick_failure, "NPC simulation is unavailable; reconnect after server recovery.")
            send(self.request, JOINED, 0, {"snapshot": self.server.world.snapshot()})
            expected_id, last_step, credit = 1, time.monotonic(), 2.0
            while not self.server.stopping.is_set():
                deadline = time.monotonic() + asset.REQUEST_TIMEOUT
                kind, request_id, size = self._header(deadline)
                npc.require(request_id == expected_id, "NPC observer request ids must increase sequentially.")
                if kind == LEAVE:
                    npc.require(size == 0)
                    return
                npc.require(kind == STEP and 1 <= size <= 32, "NPC observers can only request a snapshot.")
                now = time.monotonic()
                credit = min(2.0, credit + max(0, now - last_step) * 20)
                last_step = now
                npc.require(credit >= 1 - 1e-6, "NPC observer polling exceeds 20 Hz.")
                credit -= 1
                value = npc.decode(asset.receive_exact(self.request, size, deadline))
                npc.exact(value, set())
                npc.require(not self.server.tick_failure, "NPC simulation is unavailable; reconnect after server recovery.")
                send(self.request, STATE, request_id, self.server.world.snapshot())
                expected_id += 1
        except npc.NpcError as error:
            try:
                send(self.request, FAIL, request_id, {"message": str(error)})
            except OSError:
                pass
        except asset.ProtocolError as error:
            try:
                send(self.request, FAIL, error.request_id, {"message": error.message})
            except OSError:
                pass
        except (EOFError, OSError):
            pass
        except Exception:
            # Never log peer keys, request bodies, database rows or private paths.
            print("NPC request failed safely.", file=sys.stderr, flush=True)
            try:
                send(self.request, FAIL, request_id, {"message": "The NPC request could not be processed."})
            except OSError:
                pass


class NpcServer(asset.LinkTCPServer):
    def __init__(self, bind, worlds_root, config, database, key, *, clock=time.monotonic, transport=exchange):
        self.world = npc.NpcWorld(config, database, key, clock)
        self.slug = npc.address(config["authority"])[2]
        self.stopping = threading.Event()
        self.transport = transport
        self.tick_failure = False
        self.transfer_failures = 0
        self._close_lock = threading.Lock()
        self._npc_closed = False
        self.tick_thread = self.transfer_thread = None
        try:
            super().__init__(bind, worlds_root)
            self.RequestHandlerClass = NpcHandler
            self.tick_thread = threading.Thread(target=self._tick_loop, name="link-npc-world", daemon=True)
            self.transfer_thread = threading.Thread(target=self._transfer_loop, name="link-npc-handoff", daemon=True)
            self.tick_thread.start()
            self.transfer_thread.start()
        except BaseException:
            self.stopping.set()
            self.world.close()
            raise

    def _tick_loop(self):
        while not self.stopping.wait(.05):
            try:
                self.world.tick()
            except Exception:
                # Halt motion if durable simulation cannot be committed.
                self.tick_failure = True
                print("NPC simulation stopped after a durable-state error.", file=sys.stderr, flush=True)
                return

    def _transfer_loop(self):
        attempts = {}
        while not self.stopping.wait(.05):
            pending = self.world.pending()
            current = {item[0] for item in pending}
            attempts = {key: value for key, value in attempts.items() if key in current}
            for identifier, peer, payload in pending:
                if self.stopping.is_set():
                    return
                next_attempt, count = attempts.get(identifier, (0, 0))
                if time.monotonic() < next_attempt:
                    continue
                try:
                    response = self.transport(peer, payload, self.world.key)
                    self.world.acknowledge(identifier, response)
                    attempts.pop(identifier, None)
                except (OSError, EOFError, npc.NpcError):
                    self.transfer_failures += 1
                    count = min(count + 1, 8)
                    attempts[identifier] = (time.monotonic() + min(5.0, .25 * (2 ** (count - 1))), count)
                    # An uncertain transfer remains frozen. Retrying the same
                    # durable id is safe even if the destination already owns it.
                except Exception:
                    self.transfer_failures += 1
                    attempts[identifier] = (time.monotonic() + 5, 8)
                    print("NPC handoff remains pending after a safe failure.", file=sys.stderr, flush=True)

    def server_close(self):
        with self._close_lock:
            if self._npc_closed:
                return
            self._npc_closed = True
            self.stopping.set()
            try:
                super().server_close()
            finally:
                for thread in (self.tick_thread, self.transfer_thread):
                    if thread and thread is not threading.current_thread():
                        thread.join(timeout=TRANSFER_TIMEOUT + 1)
                self.world.close()


def create_server(config, database, key, *, host="127.0.0.1", port=None, worlds_root=None, clock=time.monotonic, transport=exchange):
    npc.validate_config(config)
    ipaddress.IPv4Address(host)
    if port is None:
        port = npc.address(config["authority"])[1]
    npc.require(isinstance(port, int) and not isinstance(port, bool) and 0 <= port <= 65535)
    worlds = Path(worlds_root if worlds_root is not None else ROOT / "worlds").resolve(strict=True)
    npc.require(worlds.is_dir())
    slug = npc.address(config["authority"])[2]
    npc.require((worlds / slug / "world.link").is_file(), "Configured NPC world is not published.")
    database = Path(database).resolve()
    npc.require(not database.is_relative_to(worlds), "NPC database must be outside published worlds.")
    return NpcServer((host, port), worlds, config, database, key, clock=clock, transport=transport)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--peer-key-file", required=True, type=Path)
    parser.add_argument("--host", default="127.0.0.1", help="Numeric IPv4 bind address; loopback is the demo default")
    parser.add_argument("--port", type=int, help="Override bind port; otherwise use the configured authority port")
    parser.add_argument("--worlds", type=Path, default=ROOT / "worlds")
    args = parser.parse_args(argv)
    try:
        config = npc.load_config(args.config)
        key_path = args.peer_key_file.resolve(strict=True)
        npc.require(not key_path.is_relative_to(args.worlds.resolve(strict=True)), "Peer key must be outside published worlds.")
        key = npc.load_key(key_path)
        server = create_server(config, args.database, key, host=args.host, port=args.port, worlds_root=args.worlds)
    except (OSError, ValueError, npc.NpcError):
        parser.error("Cannot start NPC server. Check configuration, peer key, world directory and database location.")
    print("LINK NPC travel | " + config["authority"], flush=True)
    print("Autonomous simulation, durable handoff, read-only observers. Trusted peers only; plain TCP, no TLS. Ctrl+C stops safely.", flush=True)
    try:
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

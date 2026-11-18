#!/usr/bin/env python3
# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""ASTERFALL: LINK assets and authoritative shared-state-v1 on one TCP port."""
from __future__ import annotations
import argparse
import ipaddress
import json
import math
from pathlib import Path
import socket
import sys
import time

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.game import Game, GameError
from server.vendor import link_server as asset

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORLDS = ROOT / "worlds"
DEFAULT_DATABASE = ROOT / "data" / "characters.sqlite3"
JOIN, JOINED, STEP, STATE, LEAVE, FAIL = 16, 17, 18, 19, 20, 21
MAX_JSON = 65536


def encode_json(value):
    body = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_JSON:
        raise GameError("State exceeds the protocol byte limit.")
    return body


def decode_json(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise GameError("Duplicate JSON keys are not allowed.")
            result[key] = value
        return result
    def constant(_):
        raise GameError("JSON numbers must be finite.")
    try:
        value = json.loads(body.decode("utf-8", "strict"), object_pairs_hook=unique, parse_constant=constant)
        remaining = [4096]
        def validate(item, depth=0):
            remaining[0] -= 1
            if remaining[0] < 0 or depth > 24:
                raise GameError("JSON structure is too complex.")
            if isinstance(item, float) and not math.isfinite(item):
                raise GameError("JSON numbers must be finite.")
            if isinstance(item, str):
                item.encode("utf-8", "strict")
            elif isinstance(item, dict):
                for key, child in item.items():
                    key.encode("utf-8", "strict")
                    validate(child, depth + 1)
            elif isinstance(item, list):
                for child in item:
                    validate(child, depth + 1)
        validate(value)
        return value
    except (UnicodeError, ValueError, RecursionError):
        raise GameError("Expected bounded, valid UTF-8 JSON.") from None


class GameHandler(asset.LinkTCPHandler):
    def _header(self, deadline):
        if hasattr(self, "first_header"):
            result = self.first_header
            del self.first_header
            return result
        return super()._header(deadline)

    def _json_message(self, kind, request_id, value):
        asset.send_frame(self.request, kind, request_id, encode_json(value))

    def handle(self):
        player = None
        request_id = 0
        try:
            deadline = time.monotonic() + asset.REQUEST_TIMEOUT
            kind, request_id, size = self._header(deadline)
            if kind == asset.MESSAGE_HELLO:
                self.first_header = (kind, request_id, size)
                return super().handle()
            if kind != JOIN or request_id != 0 or not 1 <= size <= MAX_JSON:
                raise GameError("First game message must be JOIN with id 0.")
            value = decode_json(asset.receive_exact(self.request, size, deadline))
            if not isinstance(value, dict) or set(value) != {"version", "world", "token", "name"} or not isinstance(value["version"], int) or isinstance(value["version"], bool) or value["version"] != 1 or value["world"] != "link-game":
                raise GameError("JOIN requires shared-state-v1 for world link-game.")
            player, token = self.server.game.join(value["token"], value["name"])
            self._json_message(JOINED, 0, {"token": token, "playerId": player.id, "snapshot": self.server.game.snapshot(player)})
            print(f"ASTERFALL player connected in slot {player.slot}.", flush=True)
            expected_id = 1
            last_step = self.server.game.clock()
            rate_credit = 2.0
            while True:
                deadline = time.monotonic() + asset.REQUEST_TIMEOUT
                kind, request_id, size = self._header(deadline)
                if request_id != expected_id:
                    raise GameError("Game request ids must increase sequentially from 1.")
                if kind == LEAVE:
                    if size:
                        raise GameError("LEAVE must have an empty payload.")
                    return
                if kind != STEP or not 1 <= size <= MAX_JSON:
                    raise GameError("Expected bounded STEP JSON.")
                now = self.server.game.clock()
                rate_credit = min(2.0, rate_credit + max(0, now - last_step) * 20)
                last_step = now
                if rate_credit < 1 - 1e-6:
                    raise GameError("STEP rate exceeds 20 Hz.")
                rate_credit -= 1
                value = decode_json(asset.receive_exact(self.request, size, deadline))
                snapshot = self.server.game.step(player, value)
                self._json_message(STATE, request_id, snapshot)
                expected_id += 1
        except GameError as error:
            try:
                self._json_message(FAIL, request_id, {"message": str(error)})
            except (OSError, GameError):
                pass
        except asset.ProtocolError as error:
            try:
                self._json_message(FAIL, error.request_id, {"message": error.message})
            except OSError:
                pass
        except (EOFError, OSError):
            pass
        except Exception:
            # Never log request bodies, bearer tokens, SQL rows or private paths.
            print("ASTERFALL request failed safely.", file=sys.stderr, flush=True)
            try:
                self._json_message(FAIL, request_id, {"message": "The server could not process this request."})
            except OSError:
                pass
        finally:
            if player is not None:
                self.server.game.leave(player)
                print(f"ASTERFALL player disconnected from slot {player.slot}.", flush=True)


class GameServer(asset.LinkTCPServer):
    def __init__(self, address, worlds_root, database, clock=time.monotonic):
        self.game = Game(database, clock=clock)
        try:
            super().__init__(address, worlds_root)
            self.RequestHandlerClass = GameHandler
            self.game.start()
        except BaseException:
            self.game.close()
            raise

    def server_close(self):
        try:
            super().server_close()
        finally:
            self.game.close()


def create_server(host="0.0.0.0", port=8002, worlds_root=None, database=None, *, clock=time.monotonic):
    ipaddress.IPv4Address(host)
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    worlds = Path(worlds_root if worlds_root is not None else DEFAULT_WORLDS).expanduser().resolve(strict=True)
    if not worlds.is_dir():
        raise ValueError("Worlds root must be an existing directory.")
    database_path = Path(database if database is not None else DEFAULT_DATABASE).expanduser().resolve()
    if database_path.is_relative_to(worlds):
        raise ValueError("Character database must be outside the published worlds directory.")
    return GameServer((host, port), worlds, database_path, clock=clock)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0", help="IPv4 bind address (default: 0.0.0.0)")
    parser.add_argument("--port", default=8002, type=int, help="LINK and game TCP port (default: 8002)")
    parser.add_argument("--worlds", default=DEFAULT_WORLDS, type=Path, help="Published worlds directory")
    parser.add_argument("--database", default=DEFAULT_DATABASE, type=Path, help="SQLite character database, outside published worlds")
    args = parser.parse_args(argv)
    try:
        server = create_server(args.host, args.port, args.worlds, args.database)
    except (OSError, ValueError) as error:
        parser.error("Cannot start ASTERFALL: " + str(error))
    try:
        host, port = server.server_address
        print(f"ASTERFALL cooperative PvE alpha | LINK + shared-state-v1 | {host}:{port}", flush=True)
        addresses = asset.lan_ipv4_addresses() if host == "0.0.0.0" else [host]
        for address in addresses:
            print(f"  LAN: link://{address}:{port}/link-game", flush=True)
        if host == "0.0.0.0":
            print(f"  Local: link://127.0.0.1:{port}/link-game", flush=True)
        print("Eight players, twelve roaming enemies, sixteen gathering plants. Inventory and character progress saved to SQLite. Trusted LAN, plain TCP. Ctrl+C saves and stops.", flush=True)
        server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        print("\nSaving characters and stopping ASTERFALL...", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        raise SystemExit("ASTERFALL server requires Python 3.10 or newer.")
    raise SystemExit(main())
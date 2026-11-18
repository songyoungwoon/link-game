# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Disposable SQLite and real LINK sockets; never opens a user's game database."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import npc, npc_server
from server.vendor import link_server as asset

KEY = bytes.fromhex("49" * 32)


class Clock:
    def __init__(self):
        self.value = 1000.0
        self.lock = threading.Lock()
    def __call__(self):
        with self.lock:
            return self.value
    def advance(self, delta=.2):
        with self.lock:
            self.value += delta


def config(authority, peer, seed=False):
    return {"version": 1, "authority": authority, "peers": [peer],
            "bounds": {"min": [-5, 0, -5], "max": [5, 4, 5]}, "arrival": [0, 0, 2],
            "route": [{"position": [0, 0, 1], "wait": .2}, {"position": [0, 0, -1], "portal": {"address": peer, "arrival": [0, 0, 2], "position": [0, 1.5, -1], "size": [2, 3, .4]}}],
            "seeds": [{"id": "wayfarer-01", "kind": "liora", "name": "Liora", "position": [0, 0, 2], "yaw": 180}] if seed else [], "speed": 5}


def receive(connection):
    deadline = time.monotonic() + 2
    raw = asset.receive_exact(connection, 16, deadline)
    magic, major, minor, kind, flags, request_id, size = asset.HEADER.unpack(raw)
    assert (magic, major, minor, flags) == (b"LINK", 0, 1, 0)
    assert 0 <= size <= npc.MAX_JSON
    body = asset.receive_exact(connection, size, deadline)
    return kind, request_id, npc.decode(body) if body else None


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="link-npc-store-")
        self.base = Path(self.temp.name)
        self.clock = Clock()
        self.a_address, self.b_address = "link://127.0.0.1:18010/traveler-a", "link://127.0.0.1:18011/traveler-b"
        self.a_config, self.b_config = config(self.a_address, self.b_address, True), config(self.b_address, self.a_address)
        self.a = npc.NpcWorld(self.a_config, self.base / "a.sqlite3", KEY, self.clock)
        self.b = npc.NpcWorld(self.b_config, self.base / "b.sqlite3", KEY, self.clock)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.close)

    def close(self):
        self.a.close()
        self.b.close()

    def reach_portal(self, world):
        for _ in range(40):
            self.clock.advance()
            world.tick()
            if world.pending():
                return world.pending()[0]
        self.fail("Autonomous NPC did not enter its configured portal")

    def test_roundtrip_identity_state_and_geometric_entry(self):
        initial = self.a.snapshot()["npcs"][0]
        self.clock.advance(.1)
        self.a.tick()
        self.assertNotEqual(self.a.snapshot()["npcs"][0]["position"], initial["position"])
        transfer, peer, payload = self.reach_portal(self.a)
        self.assertEqual(peer, self.b_address)
        self.assertEqual(self.a.snapshot()["npcs"], [])
        response = self.b.accept(npc.signed(payload, KEY))
        self.a.acknowledge(transfer, response)
        arrived = self.b.snapshot()["npcs"][0]
        self.assertEqual((arrived["id"], arrived["kind"], arrived["name"], arrived["epoch"], arrived["journey"]), ("wayfarer-01", "liora", "Liora", 2, 1))
        second_id, _, second = self.reach_portal(self.b)
        self.b.acknowledge(second_id, self.a.accept(npc.signed(second, KEY)))
        returned = self.a.snapshot()["npcs"][0]
        self.assertEqual((returned["id"], returned["epoch"], returned["journey"]), (initial["id"], 3, 2))
        self.assertEqual(self.b.snapshot()["npcs"], [])

    def test_lost_ack_restart_and_duplicate_receipt(self):
        identifier, _, payload = self.reach_portal(self.a)
        response = self.b.accept(npc.signed(payload, KEY))
        self.assertEqual(self.b.accept(npc.signed(payload, KEY)), response)
        tick = self.a.snapshot()["tick"]
        self.a.close()
        self.b.close()
        self.a = npc.NpcWorld(self.a_config, self.base / "a.sqlite3", KEY, self.clock)
        self.b = npc.NpcWorld(self.b_config, self.base / "b.sqlite3", KEY, self.clock)
        self.assertEqual(self.a.snapshot()["npcs"], [])
        self.assertEqual(self.a.snapshot()["tick"], tick)
        self.assertEqual(self.a.pending()[0][0], identifier)
        retry_response = self.b.accept(npc.signed(self.a.pending()[0][2], KEY))
        self.assertEqual(retry_response, response)
        self.a.acknowledge(identifier, retry_response)
        self.assertEqual(self.a.pending(), [])
        self.assertEqual(len(self.b.snapshot()["npcs"]), 1)

    def test_delayed_ack_cannot_delete_returned_npc(self):
        identifier, _, payload = self.reach_portal(self.a)
        late_ack = self.b.accept(npc.signed(payload, KEY))
        return_id, _, returned = self.reach_portal(self.b)
        return_ack = self.a.accept(npc.signed(returned, KEY))
        self.a.acknowledge(identifier, late_ack)
        self.b.acknowledge(return_id, return_ack)
        self.assertEqual(self.a.snapshot()["npcs"][0]["epoch"], 3)
        self.assertEqual(self.a.pending(), [])
        # Replaying an old receipt after the return only repeats its old ACK.
        self.assertEqual(self.b.accept(npc.signed(payload, KEY)), late_ack)
        self.assertEqual(self.b.snapshot()["npcs"], [])

    def test_source_restart_before_receiver_accepts(self):
        identifier, _, payload = self.reach_portal(self.a)
        self.a.close()
        self.a = npc.NpcWorld(self.a_config, self.base / "a.sqlite3", KEY, self.clock)
        self.assertEqual(self.a.pending()[0][2], payload)
        self.a.acknowledge(identifier, self.b.accept(npc.signed(payload, KEY)))
        self.assertEqual(len(self.b.snapshot()["npcs"]), 1)
        self.assertEqual(self.a.snapshot()["npcs"], [])

    def test_authentication_allowlist_arrival_and_identity_rejection(self):
        _, _, original = self.reach_portal(self.a)
        with self.assertRaises(npc.NpcError):
            self.b.accept(npc.signed(original, bytes(32)))
        for change in (lambda p: p.update(source="link://127.0.0.1:19999/stranger"),
                       lambda p: p["npc"].update(position=[0, 0, 4]),
                       lambda p: p["npc"].update(position=[0, 0, 100]),
                       lambda p: p["npc"].update(kind="executable"),
                       lambda p: p["npc"].update(epoch=2.0),
                       lambda p: p["npc"].update(journey=99)):
            payload = copy.deepcopy(original)
            change(payload)
            with self.assertRaises(npc.NpcError):
                self.b.accept(npc.signed(payload, KEY))
        self.assertEqual(self.b.snapshot()["npcs"], [])
        response = self.b.accept(npc.signed(original, KEY))
        conflict = copy.deepcopy(original)
        conflict["npc"]["name"] = "Other"
        with self.assertRaises(npc.NpcError):
            self.b.accept(npc.signed(conflict, KEY))
        stale = copy.deepcopy(original)
        stale["transferId"] = "a" * 64
        with self.assertRaises(npc.NpcError):
            self.b.accept(npc.signed(stale, KEY))
        self.assertEqual(len(self.b.snapshot()["npcs"]), 1)
        self.assertTrue(npc.authenticated(response, KEY)["accepted"])

    def test_unacknowledged_source_never_unfreezes_on_time(self):
        self.reach_portal(self.a)
        for _ in range(30):
            self.clock.advance(3600)
            self.a.tick()
        self.assertEqual(self.a.snapshot()["npcs"], [])
        self.assertEqual(len(self.a.pending()), 1)
        self.assertEqual(self.b.snapshot()["npcs"], [])

    def test_bounded_outbox_freezes_safely_and_wrong_destination_rejected(self):
        _, _, original = self.reach_portal(self.a)
        wrong = copy.deepcopy(original)
        wrong["destination"] = self.a_address
        with self.assertRaises(npc.NpcError):
            self.b.accept(npc.signed(wrong, KEY))
        # Capacity includes every unresolved record, not only the worker's batch.
        self.a.acknowledge(original["transferId"], self.b.accept(npc.signed(original, KEY)))
        return_id, _, returned = self.reach_portal(self.b)
        self.b.acknowledge(return_id, self.a.accept(npc.signed(returned, KEY)))
        with self.a.db:
            for index in range(npc.MAX_OUTBOX):
                self.a.db.execute("INSERT INTO npc_outbox VALUES(?,?,?)", (str(index), self.b_address, npc.encode(original).decode()))
        with self.assertRaises(npc.NpcError):
            for _ in range(40):
                self.clock.advance()
                self.a.tick()
        self.assertEqual(self.a.db.execute("SELECT count(*) FROM npc_outbox").fetchone()[0], npc.MAX_OUTBOX)
        self.assertEqual(len(self.a.snapshot()["npcs"]), 1)

    def test_parser_and_key_budgets(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[' * 30 + b'0' + b']' * 30, b'"' + b'a' * 5000 + b'"'):
            with self.assertRaises(npc.NpcError):
                npc.decode(body)
        with self.assertRaises(npc.NpcError):
            npc.encode({"huge": "x" * npc.MAX_JSON})
        bad = copy.deepcopy(self.a_config)
        bad["arrival"] = [0, 0, -1]
        with self.assertRaises(npc.NpcError):
            npc.validate_config(bad)
        key = self.base / "peer.key"
        key.write_text("49" * 32 + "\n", encoding="ascii")
        self.assertEqual(npc.load_key(key), KEY)
        key.write_text("short", encoding="ascii")
        with self.assertRaises(npc.NpcError):
            npc.load_key(key)

    def test_segment_crossing_not_nearby_waypoint(self):
        portal = self.a_config["route"][-1]["portal"]
        self.assertTrue(npc.enters_portal([0, 0, 0], [0, 0, -2], portal))
        self.assertFalse(npc.enters_portal([3, 0, 0], [3, 0, -2], portal))
        self.assertFalse(npc.enters_portal([0, 0, -1], [0, 0, -2], portal))
        self.assertFalse(npc.enters_portal([0, 4, 0], [0, 4, -2], portal))


class SocketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="link-npc-tcp-")
        self.base = Path(self.temp.name)
        self.worlds = self.base / "worlds"
        for slug in ("traveler-a", "traveler-b"):
            directory = self.worlds / slug
            directory.mkdir(parents=True)
            (directory / "world.link").write_text('world {version:"0.1";id:"' + slug + '";}\n', encoding="ascii")
        reserves = [socket.socket(), socket.socket()]
        for connection in reserves:
            connection.bind(("127.0.0.1", 0))
        self.ports = [connection.getsockname()[1] for connection in reserves]
        for connection in reserves:
            connection.close()
        self.a_address = f"link://127.0.0.1:{self.ports[0]}/traveler-a"
        self.b_address = f"link://127.0.0.1:{self.ports[1]}/traveler-b"
        self.clock = Clock()
        self.a_config, self.b_config = config(self.a_address, self.b_address, True), config(self.b_address, self.a_address)
        self.servers, self.threads, self.clients = [], [], []
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.close)
        self.a = self.start(self.a_config, "a")
        self.b = self.start(self.b_config, "b")

    def start(self, settings, name, transport=npc_server.exchange):
        server = npc_server.create_server(settings, self.base / (name + ".sqlite3"), KEY, worlds_root=self.worlds, clock=self.clock, transport=transport)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        thread.start()
        self.servers.append(server)
        self.threads.append(thread)
        return server

    def close(self):
        for connection in self.clients:
            connection.close()
        for server in self.servers:
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=3)

    def advance_until(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            self.clock.advance(.1)
            time.sleep(.025)
        self.fail("Real LINK handoff did not reach its expected state")

    def observer(self, server, settings):
        connection = socket.create_connection(server.server_address, timeout=2)
        self.clients.append(connection)
        asset.send_frame(connection, npc_server.JOIN, 0, npc.encode({"version": 1, "world": npc.address(settings["authority"])[2], "profile": "npc-travel-v1"}))
        kind, identifier, value = receive(connection)
        self.assertEqual((kind, identifier), (npc_server.JOINED, 0))
        self.assertEqual(set(value), {"snapshot"})
        return connection, value["snapshot"]

    def test_real_tcp_roundtrip_without_observers_then_two_readers(self):
        self.advance_until(lambda: any(item["epoch"] >= 3 for item in self.a.world.snapshot()["npcs"]))
        first, snapshot = self.observer(self.a, self.a_config)
        second, same = self.observer(self.a, self.a_config)
        self.assertEqual(snapshot["npcs"][0]["id"], same["npcs"][0]["id"])
        self.assertEqual(snapshot["npcs"][0]["journey"], 2)
        self.assertEqual(set(snapshot), {"tick", "time", "world", "npcs"})
        asset.send_frame(first, npc_server.STEP, 1, npc.encode({}))
        kind, identifier, value = receive(first)
        self.assertEqual((kind, identifier), (npc_server.STATE, 1))
        self.assertGreaterEqual(value["tick"], snapshot["tick"])
        self.assertFalse(self.a.tick_failure)
        self.assertFalse(self.b.tick_failure)
        # Observers cannot move NPCs or submit game actions.
        asset.send_frame(second, npc_server.STEP, 1, npc.encode({"position": [0, 0, 0]}))
        kind, _, _ = receive(second)
        self.assertEqual(kind, npc_server.FAIL)

    def test_actual_lost_ack_retries_without_duplicate_ownership(self):
        dropped = threading.Event()
        def lose_first(peer, payload, key):
            response = npc_server.exchange(peer, payload, key)
            if not dropped.is_set():
                dropped.set()
                raise OSError("simulated ACK loss")
            return response
        self.a.transport = lose_first
        self.advance_until(lambda: dropped.is_set())
        self.advance_until(lambda: self.a.transfer_failures >= 1 and not self.a.world.pending())
        # The destination may already have returned it; only one world simulates.
        owners = len(self.a.world.snapshot()["npcs"]) + len(self.b.world.snapshot()["npcs"])
        self.assertLessEqual(owners, 1)
        self.advance_until(lambda: any(item["journey"] >= 2 for item in self.a.world.snapshot()["npcs"]))

    def test_real_tcp_destination_restart_recovers_frozen_outbox(self):
        self.b.shutdown()
        self.b.server_close()
        self.a.transport = lambda *args: (_ for _ in ()).throw(OSError("destination offline"))
        self.advance_until(lambda: bool(self.a.world.pending()))
        identifier = self.a.world.pending()[0][0]
        self.assertEqual(self.a.world.snapshot()["npcs"], [])
        self.b = self.start(self.b_config, "b")
        self.a.transport = npc_server.exchange
        self.advance_until(lambda: not any(item[0] == identifier for item in self.a.world.pending()))
        self.assertLessEqual(len(self.a.world.snapshot()["npcs"]) + len(self.b.world.snapshot()["npcs"]), 1)
        self.advance_until(lambda: any(item["journey"] >= 2 for item in self.a.world.snapshot()["npcs"]))

    def test_failed_tick_is_not_published_as_a_healthy_observer(self):
        def fail_tick():
            raise OSError("simulated durable-state error")
        self.a.world.tick = fail_tick
        self.advance_until(lambda: self.a.tick_failure)
        connection = socket.create_connection(self.a.server_address, timeout=2)
        self.clients.append(connection)
        asset.send_frame(connection, npc_server.JOIN, 0, npc.encode({"version": 1, "world": "traveler-a", "profile": "npc-travel-v1"}))
        kind, identifier, value = receive(connection)
        self.assertEqual((kind, identifier), (npc_server.FAIL, 0))
        self.assertIn("unavailable", value["message"])

    def test_wrong_peer_key_and_asset_transport_still_work(self):
        # A fake signed handoff must not create a character.
        _, _, payload = self._make_outgoing_fixture()
        with self.assertRaises(npc.NpcError):
            npc_server.exchange(self.b_address, payload, bytes(32))
        self.assertEqual(self.b.world.snapshot()["npcs"], [])
        connection = socket.create_connection(self.a.server_address, timeout=2)
        self.clients.append(connection)
        asset.send_frame(connection, asset.MESSAGE_HELLO, 0, b'\x00\x01traveler-a')
        deadline = time.monotonic() + 2
        header = asset.receive_exact(connection, 16, deadline)
        _, _, _, kind, _, identifier, length = asset.HEADER.unpack(header)
        self.assertEqual((kind, identifier), (asset.MESSAGE_WELCOME, 0))
        self.assertEqual(asset.receive_exact(connection, length, deadline), b'\x00\x01traveler-a')

    def _make_outgoing_fixture(self):
        # Keep production A from dispatching while tests obtain a real frozen row.
        self.a.transport = lambda *args: (_ for _ in ()).throw(OSError("offline"))
        self.advance_until(lambda: bool(self.a.world.pending()))
        return self.a.world.pending()[0]


if __name__ == "__main__":
    unittest.main()

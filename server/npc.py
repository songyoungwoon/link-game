# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Persistent NPC simulation and idempotent handoff between explicitly trusted worlds.

Only data moves. A destination chooses its own local archetype/rendering/scripts.
An uncertain handoff stays frozen: availability never overrides single ownership.
"""
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import json
import math
from pathlib import Path
import re
import sqlite3
import threading
import time

MAX_JSON = 65536
MAX_NPCS = 16
MAX_RECEIPTS = 65536
MAX_OUTBOX = 128
MAX_INTEGER = 9007199254740991
NPC_FIELDS = {"id", "kind", "name", "position", "yaw", "animation", "epoch", "journey"}
ADDRESS = re.compile(r"link://([0-9.]+):([0-9]{1,5})/([a-z0-9]+(?:-[a-z0-9]+)*)\Z", re.ASCII)
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
TRANSFER_ID = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)


class NpcError(Exception):
    """Bounded public error without paths, secrets or SQL details."""


def require(condition, message="Invalid NPC travel data."):
    if not condition:
        raise NpcError(message)


def exact(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields))


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def integer(value, low=0, high=MAX_INTEGER):
    require(isinstance(value, int) and not isinstance(value, bool) and low <= value <= high)
    return value


def position(value):
    require(isinstance(value, list) and len(value) == 3 and all(numeric(v) and abs(v) <= 1000000 for v in value))
    return [float(v) for v in value]


def text(value, maximum):
    require(isinstance(value, str) and 1 <= len(value.encode("utf-8")) <= maximum and all(c.isprintable() for c in value))
    return value


def address(value):
    require(isinstance(value, str))
    match = ADDRESS.fullmatch(value)
    require(match is not None, "Expected a numeric IPv4 LINK world address with an explicit port.")
    try:
        host = str(ipaddress.IPv4Address(match[1]))
    except ValueError:
        raise NpcError("Expected a numeric IPv4 LINK world address.") from None
    port = int(match[2])
    require(1 <= port <= 65535 and str(port) == match[2] and host == match[1])
    return host, port, match[3]


def encode(value):
    try:
        result = json.dumps(value, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError):
        raise NpcError("Expected bounded UTF-8 JSON.") from None
    require(1 <= len(result) <= MAX_JSON, "NPC message exceeds the byte limit.")
    return result


def decode(body):
    require(isinstance(body, bytes) and 1 <= len(body) <= MAX_JSON)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON keys are not allowed.")
            result[key] = value
        return result
    def constant(_):
        raise NpcError("JSON numbers must be finite.")
    try:
        value = json.loads(body.decode("utf-8", "strict"), object_pairs_hook=unique, parse_constant=constant)
        remaining = [4096]
        def bounded(item, depth=0):
            remaining[0] -= 1
            require(remaining[0] >= 0 and depth <= 24)
            if isinstance(item, float):
                require(math.isfinite(item))
            elif isinstance(item, str):
                require(len(item.encode("utf-8", "strict")) <= 4096)
            elif isinstance(item, list):
                for child in item:
                    bounded(child, depth + 1)
            elif isinstance(item, dict):
                for key, child in item.items():
                    bounded(key, depth + 1)
                    bounded(child, depth + 1)
        bounded(value)
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise NpcError("Expected bounded UTF-8 JSON.") from None


def validate_npc(value):
    exact(value, NPC_FIELDS)
    require(isinstance(value["id"], str) and IDENTIFIER.fullmatch(value["id"]))
    require(value["kind"] == "liora", "Destination does not support this NPC archetype.")
    text(value["name"], 48)
    position(value["position"])
    require(numeric(value["yaw"]) and abs(value["yaw"]) <= 1000000)
    require(value["animation"] in ("Idle", "Walk"))
    integer(value["epoch"], 1)
    integer(value["journey"])
    require(value["journey"] == value["epoch"] - 1)
    return value


def inside(point, bounds):
    return all(bounds["min"][axis] <= point[axis] <= bounds["max"][axis] for axis in range(3))


def portal_contains(feet, portal):
    center = [feet[0], feet[1] + 1.0, feet[2]]
    return all(abs(center[axis] - portal["position"][axis]) <= portal["size"][axis] / 2 for axis in range(3))


def enters_portal(start, end, portal):
    """Segment/AABB intersection, using the NPC's center one metre above its feet."""
    if portal_contains(start, portal):
        return False
    low, high = 0.0, 1.0
    for axis in range(3):
        a = start[axis] + (1.0 if axis == 1 else 0.0)
        b = end[axis] + (1.0 if axis == 1 else 0.0)
        minimum = portal["position"][axis] - portal["size"][axis] / 2
        maximum = portal["position"][axis] + portal["size"][axis] / 2
        delta = b - a
        if abs(delta) < 1e-12:
            if not minimum <= a <= maximum:
                return False
        else:
            left, right = (minimum - a) / delta, (maximum - a) / delta
            low, high = max(low, min(left, right)), min(high, max(left, right))
            if low > high:
                return False
    return 0 <= low <= 1 and high >= 0


def validate_config(value):
    exact(value, {"version", "authority", "peers", "bounds", "arrival", "route", "seeds", "speed"})
    integer(value["version"], 1, 1)
    address(value["authority"])
    peers = value["peers"]
    require(isinstance(peers, list) and 1 <= len(peers) <= 8 and len(set(peers)) == len(peers))
    for peer in peers:
        address(peer)
        require(peer != value["authority"])
    exact(value["bounds"], {"min", "max"})
    minimum, maximum = position(value["bounds"]["min"]), position(value["bounds"]["max"])
    require(all(a < b for a, b in zip(minimum, maximum)))
    position(value["arrival"])
    require(inside(value["arrival"], value["bounds"]))
    require(numeric(value["speed"]) and .1 <= value["speed"] <= 5)
    route = value["route"]
    require(isinstance(route, list) and 1 <= len(route) <= 32)
    for index, step in enumerate(route):
        require(isinstance(step, dict) and "position" in step and not set(step) - {"position", "wait", "portal"})
        position(step["position"])
        require(inside(step["position"], value["bounds"]))
        if "wait" in step:
            require(numeric(step["wait"]) and 0 <= step["wait"] <= 300)
        if "portal" in step:
            portal = step["portal"]
            exact(portal, {"address", "arrival", "position", "size"})
            require(index == len(route) - 1 and portal["address"] in peers)
            for key in ("arrival", "position", "size"):
                position(portal[key])
            require(all(0 < v <= 100 for v in portal["size"]))
            require(portal_contains(step["position"], portal))
            require(not portal_contains(value["arrival"], portal), "Arrival must be outside the outgoing portal.")
    require("portal" in route[-1], "The final waypoint must lead into a portal.")
    seeds = value["seeds"]
    require(isinstance(seeds, list) and len(seeds) <= MAX_NPCS)
    identifiers = set()
    for seed in seeds:
        exact(seed, {"id", "kind", "name", "position", "yaw"})
        validate_npc(dict(seed, animation="Idle", epoch=1, journey=0))
        require(inside(seed["position"], value["bounds"]) and seed["id"] not in identifiers)
        require(not portal_contains(seed["position"], route[-1]["portal"]))
        identifiers.add(seed["id"])
    return value


def load_config(path):
    return validate_config(decode(Path(path).read_bytes()))


def load_key(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 128, "Peer key must contain exactly 64 hexadecimal characters.")
    try:
        value = raw.decode("ascii").strip()
        require(re.fullmatch(r"[a-fA-F0-9]{64}", value), "Peer key must contain exactly 64 hexadecimal characters.")
        return bytes.fromhex(value)
    except UnicodeError:
        raise NpcError("Peer key must contain exactly 64 hexadecimal characters.") from None


def signed(payload, key):
    return {"payload": payload, "mac": hmac.new(key, encode(payload), hashlib.sha256).hexdigest()}


def authenticated(envelope, key):
    exact(envelope, {"payload", "mac"})
    require(isinstance(envelope["mac"], str) and TRANSFER_ID.fullmatch(envelope["mac"]), "Invalid peer authentication.")
    require(hmac.compare_digest(envelope["mac"], signed(envelope["payload"], key)["mac"]), "Invalid peer authentication.")
    return envelope["payload"]


class NpcWorld:
    """One SQLite authority. All mutations are serialized; network I/O is external."""
    def __init__(self, config, database, key, clock=time.monotonic):
        self.config = validate_config(config)
        require(isinstance(key, bytes) and len(key) == 32)
        self.key, self.clock = key, clock
        self.lock = threading.RLock()
        self.closed = False
        self.last_clock = clock()
        database = Path(database)
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, timeout=5, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS npc_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS npc_entities(id TEXT PRIMARY KEY,state TEXT NOT NULL,status TEXT NOT NULL,waypoint INTEGER NOT NULL,waiting REAL NOT NULL,transfer_id TEXT);
        CREATE TABLE IF NOT EXISTS npc_outbox(transfer_id TEXT PRIMARY KEY,peer TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS npc_receipts(transfer_id TEXT PRIMARY KEY,digest TEXT NOT NULL,peer TEXT NOT NULL,response TEXT NOT NULL);
        """)
        with self.db:
            prior = self.db.execute("SELECT value FROM npc_meta WHERE key='authority'").fetchone()
            require(prior is None or prior[0] == config["authority"], "NPC database belongs to a different authority.")
            self.db.execute("INSERT OR IGNORE INTO npc_meta VALUES('authority',?)", (config["authority"],))
            self.db.execute("INSERT OR IGNORE INTO npc_meta VALUES('tick','0')")
            self.db.execute("INSERT OR IGNORE INTO npc_meta VALUES('time','0')")
            for seed in config["seeds"]:
                state = dict(seed, animation="Idle", epoch=1, journey=0)
                self.db.execute("INSERT OR IGNORE INTO npc_entities VALUES(?,?,'active',0,0,NULL)", (state["id"], encode(state).decode()))
        self.tick_count = int(self.db.execute("SELECT value FROM npc_meta WHERE key='tick'").fetchone()[0])
        self.elapsed = float(self.db.execute("SELECT value FROM npc_meta WHERE key='time'").fetchone()[0])
        require(self.db.execute("SELECT count(*) FROM npc_entities").fetchone()[0] <= MAX_NPCS)

    def snapshot(self):
        with self.lock:
            require(not self.closed, "NPC world is stopping.")
            states = [json.loads(row[0]) for row in self.db.execute("SELECT state FROM npc_entities WHERE status='active' ORDER BY id")]
            return {"tick": self.tick_count, "time": round(self.elapsed, 4), "world": address(self.config["authority"])[2], "npcs": states}

    def tick(self):
        with self.lock:
            if self.closed:
                return
            now = self.clock()
            delta = min(.2, max(0, now - self.last_clock))
            self.last_clock = now
            require(self.tick_count < MAX_INTEGER)
            self.tick_count += 1
            self.elapsed += delta
            with self.db:
                rows = list(self.db.execute("SELECT * FROM npc_entities WHERE status='active'"))
                for row in rows:
                    state = json.loads(row["state"])
                    step = self.config["route"][row["waypoint"]]
                    waiting = max(0.0, row["waiting"] - delta)
                    waypoint = row["waypoint"]
                    state["animation"] = "Idle"
                    if row["waiting"] <= 0:
                        old = state["position"]
                        target = step["position"]
                        dx, dy, dz = [target[i] - old[i] for i in range(3)]
                        length = math.sqrt(dx * dx + dy * dy + dz * dz)
                        travel = min(length, self.config["speed"] * delta)
                        if length > 1e-8:
                            state["position"] = [old[i] + (target[i] - old[i]) / length * travel for i in range(3)]
                            state["yaw"] = math.degrees(math.atan2(dx, dz))
                            state["animation"] = "Walk" if travel > 0 else "Idle"
                        portal = step.get("portal")
                        if portal and enters_portal(old, state["position"], portal):
                            self._freeze(row["id"], state, portal)
                            continue
                        if length <= travel + 1e-8:
                            require(portal is None, "NPC reached a portal without entering its volume.")
                            waiting = float(step.get("wait", 0))
                            waypoint = (waypoint + 1) % len(self.config["route"])
                            state["animation"] = "Idle"
                    self.db.execute("UPDATE npc_entities SET state=?,waypoint=?,waiting=? WHERE id=?", (encode(state).decode(), waypoint, waiting, row["id"]))
                self.db.execute("UPDATE npc_meta SET value=? WHERE key='tick'", (str(self.tick_count),))
                self.db.execute("UPDATE npc_meta SET value=? WHERE key='time'", (str(self.elapsed),))

    def _freeze(self, identifier, state, portal):
        require(state["epoch"] < MAX_INTEGER and state["journey"] < MAX_INTEGER)
        require(self.db.execute("SELECT count(*) FROM npc_outbox").fetchone()[0] < MAX_OUTBOX, "NPC pending-transfer capacity reached; keep this authority stopped until acknowledgements recover.")
        transfer_state = dict(state, position=portal["arrival"], animation="Idle", epoch=state["epoch"] + 1, journey=state["journey"] + 1)
        identifier_bytes = encode({"source": self.config["authority"], "destination": portal["address"], "id": identifier, "epoch": transfer_state["epoch"]})
        transfer_id = hashlib.sha256(identifier_bytes).hexdigest()
        payload = {"version": 1, "transferId": transfer_id, "source": self.config["authority"], "destination": portal["address"], "npc": transfer_state}
        self.db.execute("INSERT INTO npc_outbox VALUES(?,?,?)", (transfer_id, portal["address"], encode(payload).decode()))
        self.db.execute("UPDATE npc_entities SET state=?,status='outgoing',transfer_id=? WHERE id=?", (encode(dict(state, animation="Idle")).decode(), transfer_id, identifier))

    def pending(self):
        with self.lock:
            if self.closed:
                return []
            return [(row[0], row[1], json.loads(row[2])) for row in self.db.execute("SELECT transfer_id,peer,payload FROM npc_outbox ORDER BY rowid LIMIT 16")]

    def accept(self, envelope):
        payload = authenticated(envelope, self.key)
        exact(payload, {"version", "transferId", "source", "destination", "npc"})
        integer(payload["version"], 1, 1)
        require(isinstance(payload["transferId"], str) and TRANSFER_ID.fullmatch(payload["transferId"]))
        require(payload["source"] in self.config["peers"] and payload["destination"] == self.config["authority"], "Peer or destination is not permitted.")
        state = validate_npc(payload["npc"])
        require(state["epoch"] >= 2)
        digest = hashlib.sha256(encode(payload)).hexdigest()
        with self.lock:
            require(not self.closed, "NPC world is stopping.")
            with self.db:
                receipt = self.db.execute("SELECT digest,peer,response FROM npc_receipts WHERE transfer_id=?", (payload["transferId"],)).fetchone()
                if receipt:
                    require(receipt[0] == digest and receipt[1] == payload["source"], "Conflicting transfer replay.")
                    return signed(json.loads(receipt[2]), self.key)
                require(state["position"] == self.config["arrival"] and inside(state["position"], self.config["bounds"]), "NPC arrival is not permitted.")
                require(self.db.execute("SELECT count(*) FROM npc_receipts").fetchone()[0] < MAX_RECEIPTS, "NPC receipt capacity reached; administrative maintenance is required.")
                current = self.db.execute("SELECT state,status FROM npc_entities WHERE id=?", (state["id"],)).fetchone()
                if current:
                    known = json.loads(current[0])
                    require(current[1] != "active", "This world already owns that NPC.")
                    require(state["epoch"] > known["epoch"] and state["kind"] == known["kind"] and state["name"] == known["name"], "Stale or conflicting NPC identity.")
                else:
                    require(self.db.execute("SELECT count(*) FROM npc_entities").fetchone()[0] < MAX_NPCS, "NPC capacity reached.")
                state = dict(state, animation="Idle")
                self.db.execute("INSERT OR REPLACE INTO npc_entities VALUES(?,?,'active',0,0,NULL)", (state["id"], encode(state).decode()))
                response = {"version": 1, "transferId": payload["transferId"], "source": self.config["authority"], "destination": payload["source"], "digest": digest, "epoch": state["epoch"], "accepted": True}
                self.db.execute("INSERT INTO npc_receipts VALUES(?,?,?,?)", (payload["transferId"], digest, payload["source"], encode(response).decode()))
                return signed(response, self.key)

    def acknowledge(self, transfer_id, envelope):
        response = authenticated(envelope, self.key)
        exact(response, {"version", "transferId", "source", "destination", "digest", "epoch", "accepted"})
        require(response["accepted"] is True and response["version"] == 1 and response["transferId"] == transfer_id)
        with self.lock:
            if self.closed:
                return
            with self.db:
                row = self.db.execute("SELECT peer,payload FROM npc_outbox WHERE transfer_id=?", (transfer_id,)).fetchone()
                if row is None:
                    return
                payload = json.loads(row[1])
                require(response["source"] == row[0] and response["destination"] == self.config["authority"] and response["digest"] == hashlib.sha256(encode(payload)).hexdigest() and response["epoch"] == payload["npc"]["epoch"])
                # A newer return handoff may already own this identity here.
                self.db.execute("UPDATE npc_entities SET status='departed',transfer_id=NULL WHERE id=? AND status='outgoing' AND transfer_id=?", (payload["npc"]["id"], transfer_id))
                self.db.execute("DELETE FROM npc_outbox WHERE transfer_id=?", (transfer_id,))

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.db.commit()
            self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.db.close()

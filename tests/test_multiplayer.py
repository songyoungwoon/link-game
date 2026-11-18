# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Real TCP clients; a deterministic world clock avoids slow combat/respawn tests."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import asterfall
from server.game import ENTRY, spawn_position, Game, GameError, CharacterStore, Player, MONSTER_STATS, in_camp
from server.world_data import SPAWNS, RESOURCE_SPAWNS, BOUNDS, STACK_LIMIT, RESOURCE_RESPAWN_SECONDS
from server.vendor import link_server as asset

PLAYER_FIELDS = {"id", "slot", "active", "name", "position", "yaw", "hp", "maxHp", "level", "xp", "gold", "weapon", "kills", "quest", "attack", "respawn"}
MONSTER_FIELDS = {"id", "active", "position", "yaw", "hp", "maxHp", "kind", "attack", "respawnIn"}


class Clock:
    def __init__(self):
        self.value = 1000.0
        self.lock = threading.Lock()
    def __call__(self):
        with self.lock:
            return self.value
    def advance(self, seconds):
        with self.lock:
            self.value += seconds


def exact(connection, count):
    result = bytearray()
    while len(result) < count:
        chunk = connection.recv(count - len(result))
        if not chunk:
            raise EOFError("closed")
        result.extend(chunk)
    return bytes(result)


def receive(connection):
    magic, major, minor, kind, flags, request_id, size = asset.HEADER.unpack(exact(connection, 16))
    assert (magic, major, minor, flags) == (b"LINK", 0, 1, 0)
    return kind, request_id, exact(connection, size)


class Client:
    def __init__(self, test, name="Explorer", token=""):
        self.test = test
        self.connection = socket.create_connection(("127.0.0.1", test.server.server_address[1]), timeout=2)
        self.connection.settimeout(2)
        self.request_id = 0
        self.action_seq = 0
        self.position = ENTRY.copy()
        asset.send_frame(self.connection, asterfall.JOIN, 0, asterfall.encode_json({"version": 1, "world": "link-game", "token": token, "name": name}))
        kind, request_id, body = receive(self.connection)
        self.joined = json.loads(body)
        self.kind = kind
        if kind == asterfall.JOINED:
            self.token = self.joined["token"]
            self.id = self.joined["playerId"]
            self.snapshot = self.joined["snapshot"]
            self.position = self.snapshot["self"]["position"].copy()
        test.clients.append(self)

    def step(self, action=None, *, position=None, advance=.06):
        self.test.clock.advance(advance)
        self.request_id += 1
        value = {"position": self.position if position is None else position, "yaw": 0, "action": action}
        asset.send_frame(self.connection, asterfall.STEP, self.request_id, asterfall.encode_json(value))
        kind, request_id, body = receive(self.connection)
        self.test.assertEqual(request_id, self.request_id)
        result = json.loads(body)
        if kind == asterfall.STATE:
            self.snapshot = result
        return kind, result

    def action(self, kind, target, **options):
        self.action_seq += 1
        return self.step({"kind": kind, "target": target, "seq": self.action_seq}, **options)

    def close(self):
        if self.connection is None:
            return
        try:
            asset.send_frame(self.connection, asterfall.LEAVE, self.request_id + 1, b"")
        except OSError:
            pass
        self.connection.close()
        self.connection = None


class MultiplayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="asterfall-test-")
        self.base = Path(self.temp.name)
        self.worlds = self.base / "worlds"
        self.world = self.worlds / "link-game"
        self.world.mkdir(parents=True)
        self.manifest = b'world {version:"0.1";id:"link-game";}\n'
        (self.world / "world.link").write_bytes(self.manifest)
        (self.world / "scene.element").write_bytes(b"scene {}\n")
        self.database = self.base / "data" / "characters.sqlite3"
        self.clock = Clock()
        self.clients = []
        self.start_server()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.cleanup_server)

    def start_server(self):
        self.server = asterfall.create_server("127.0.0.1", 0, self.worlds, self.database, clock=self.clock)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.server_running = True

    def stop_server(self):
        if self.server_running:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server_running = False

    def cleanup_server(self):
        for client in self.clients:
            client.close()
        self.stop_server()

    def wait_until(self, predicate):
        deadline = time.monotonic() + 2
        while not predicate():
            if time.monotonic() > deadline:
                self.fail("Condition timed out")
            time.sleep(.01)

    def place(self, client, x, z):
        # Test fixture positioning, not a network/admin backdoor. Clients still send
        # real STEP frames and every combat decision passes the production server.
        with self.server.game.lock:
            player = next(player for player in self.server.game.players if player and player.id == client.id)
            player.position = [float(x), 1.65, float(z)]
            player.last_step = self.clock()
            client.position = player.position.copy()
            return player

    def near_monster(self, client, identifier="slime_0", dx=0, dz=2):
        with self.server.game.lock:
            monster = next(monster for monster in self.server.game.monsters if monster.id == identifier)
            return self.place(client,monster.position[0]+dx,monster.position[2]+dz)

    def near_resource(self,client,index=0):
        resource = self.server.game.resources[index]
        return self.place(client,resource.position[0],resource.position[1]+1)

    def equip_iron(self, client):
        self.place(client, 3, 24)
        kind, snapshot = client.action("equip", "iron_altar")
        self.assertEqual(kind, asterfall.STATE)
        self.assertEqual(snapshot["self"]["weapon"], "iron")

    def monster(self, snapshot, identifier="slime_0"):
        return next(monster for monster in snapshot["monsters"] if monster["id"] == identifier)

    def raw_connection(self):
        connection = socket.create_connection(("127.0.0.1", self.server.server_address[1]), timeout=2)
        connection.settimeout(2)
        self.addCleanup(connection.close)
        return connection

    def test_same_port_preserves_native_asset_transport(self):
        connection = self.raw_connection()
        asset.send_frame(connection, 1, 0, b"\x00\x01link-game")
        self.assertEqual(receive(connection), (2, 0, b"\x00\x01link-game"))
        asset.send_frame(connection, 3, 1, struct.pack("!I", 65536) + b"world.link")
        self.assertEqual(receive(connection), (4, 1, self.manifest))
        asset.send_frame(connection, 6, 2, b"")
        self.assertEqual(connection.recv(1), b"")

    def test_two_live_clients_have_exact_shared_snapshot_and_private_tokens(self):
        alice, bob = Client(self, "Alice"), Client(self, "Bob")
        self.assertEqual(alice.kind, asterfall.JOINED)
        _, snapshot = alice.step()
        self.assertEqual(set(snapshot), {"tick", "time", "self", "players", "monsters", "notice", "inventory", "resources"})
        self.assertEqual(len(snapshot["players"]), 8)
        self.assertEqual(len(snapshot["monsters"]), 12)
        self.assertEqual(len(snapshot["resources"]),16)
        self.assertEqual(snapshot["inventory"],[])
        self.assertEqual(sum(player["active"] for player in snapshot["players"]), 2)
        self.assertEqual(snapshot["self"]["id"], alice.id)
        self.assertNotEqual(alice.id, bob.id)
        for player in snapshot["players"]:
            self.assertEqual(set(player), PLAYER_FIELDS)
            self.assertGreater(player["maxHp"], 0)
            self.assertGreaterEqual(player["level"], 1)
        for monster in snapshot["monsters"]:
            self.assertEqual(set(monster), MONSTER_FIELDS)
        wire = asterfall.encode_json(snapshot)
        self.assertNotIn(alice.token.encode(), wire)
        self.assertNotIn(bob.token.encode(), wire)

    def test_two_players_share_damage_and_receive_each_kill_reward_once(self):
        alice, bob = Client(self, "Alice"), Client(self, "Bob")
        self.equip_iron(alice)
        self.equip_iron(bob)
        self.near_monster(alice)
        self.near_monster(bob,dx=2)
        _, first = alice.action("attack", "slime_0")
        self.assertEqual(self.monster(first)["hp"], 20)
        _, observed = bob.step()
        self.assertEqual(self.monster(observed)["hp"], 20)
        _, victory = bob.action("attack", "slime_0")
        self.assertFalse(self.monster(victory)["active"])
        self.assertEqual(victory["self"]["kills"], 1)
        self.assertEqual(victory["self"]["gold"], 12)
        _, alice_state = alice.step()
        self.assertEqual(alice_state["self"]["kills"], 1)
        self.assertEqual(alice_state["self"]["gold"], 12)
        self.assertEqual(alice_state["inventory"],[{"item":"slime_gel","count":1}])
        self.assertEqual(victory["inventory"],[{"item":"slime_gel","count":1}])
        # Replayed seq and fresh attacks against a dead target both grant nothing.
        _, repeated = bob.step({"kind": "attack", "target": "slime_0", "seq": bob.action_seq}, advance=.7)
        self.assertEqual(repeated["self"]["gold"], 12)
        _, repeated = bob.action("attack", "slime_0", advance=.7)
        self.assertEqual(repeated["self"]["kills"], 1)
        self.assertEqual(repeated["self"]["gold"], 12)
        self.assertEqual(repeated["inventory"],[{"item":"slime_gel","count":1}])

    def test_server_enforces_cooldown_and_remote_melee_distance(self):
        client = Client(self)
        _, far = client.action("attack", "slime_0")
        self.assertEqual(self.monster(far)["hp"], 45)
        self.assertEqual(far["self"]["attack"], 0)
        self.near_monster(client)
        _, hit = client.action("attack", "slime_0")
        self.assertEqual(self.monster(hit)["hp"], 33)
        _, fast = client.action("attack", "slime_0")
        self.assertEqual(self.monster(fast)["hp"], 33)
        self.assertEqual(fast["self"]["attack"], 1)
        _, recovered = client.action("attack", "slime_0", advance=.7)
        self.assertEqual(self.monster(recovered)["hp"], 21)
        self.assertEqual(recovered["self"]["attack"], 2)

    def test_forged_teleport_cannot_authorize_an_attack(self):
        client = Client(self)
        _, result = client.step({"kind": "attack", "target": "slime_0", "seq": 1}, position=[-24, 1.65, 10])
        self.assertEqual(result["self"]["position"], spawn_position(result["self"]["slot"]))
        self.assertEqual(result["self"]["attack"], 0)
        self.assertEqual(self.monster(result)["hp"], 45)
        self.assertEqual(result["self"]["gold"], 0)

    def test_finite_bounds_and_forged_stats_validation_close_the_session(self):
        payloads = [
            b'{"position":[NaN,1.65,28],"yaw":0,"action":null}',
            b'{"position":[0,1e999,28],"yaw":0,"action":null}',
            b'{"position":[121,1.65,28],"yaw":0,"action":null}',
            b'{"position":[0,1.65,28],"yaw":0,"action":null,"hp":9999}',
            b'{"position":[0,1.65,28],"yaw":0,"yaw":1,"action":null}',
            b'{"position":[0,1.65,28],"yaw":0,"action":{"kind":"attack","target":"slime_0","seq":true}}',
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                client = Client(self)
                self.clock.advance(.06)
                asset.send_frame(client.connection, asterfall.STEP, 1, payload)
                kind, _, body = receive(client.connection)
                self.assertEqual(kind, asterfall.FAIL, body)
                self.assertEqual(client.connection.recv(1), b"")
                client.connection.close()
                client.connection = None

    def test_wrong_order_oversize_and_rate_flood_fail_promptly(self):
        client = Client(self)
        asset.send_frame(client.connection, asterfall.STEP, 2, b"{}")
        self.assertEqual(receive(client.connection)[0], asterfall.FAIL)
        oversized = self.raw_connection()
        oversized.sendall(asset.HEADER.pack(b"LINK", 0, 1, asterfall.JOIN, 0, 0, 65537))
        self.assertEqual(receive(oversized)[0], asterfall.FAIL)
        flood = Client(self)
        self.assertEqual(flood.step(advance=0)[0], asterfall.STATE)
        self.assertEqual(flood.step(advance=0)[0], asterfall.STATE)
        self.assertEqual(flood.step(advance=0)[0], asterfall.FAIL)

    def test_duplicate_live_token_and_ninth_player_are_rejected(self):
        first = Client(self)
        duplicate = Client(self, token=first.token)
        self.assertEqual(duplicate.kind, asterfall.FAIL)
        for index in range(7):
            self.assertEqual(Client(self, "Player" + str(index)).kind, asterfall.JOINED)
        self.assertEqual(Client(self, "Ninth").kind, asterfall.FAIL)

    def test_reconnect_and_server_restart_keep_character_progress(self):
        client = Client(self, "Saved")
        self.equip_iron(client)
        player = self.near_monster(client)
        with self.server.game.lock:
            player.kills = 4
            self.server.game.monsters[0].hp = 1
        client.action("attack", "slime_0")
        self.place(client, 0, 20)
        _, quest = client.action("claim", "quest_stone")
        self.assertEqual((quest["self"]["kills"], quest["self"]["quest"], quest["self"]["gold"]), (5, 1, 112))
        self.place(client, -3, 24)
        _, star = client.action("equip", "star_altar")
        self.assertEqual((star["self"]["weapon"], star["self"]["gold"]), ("star", 12))
        token, identity = client.token, client.id
        client.close()
        self.wait_until(lambda: not any(self.server.game.players))
        resumed = Client(self, "Saved", token)
        self.assertEqual(resumed.id, identity)
        self.assertEqual(resumed.snapshot["self"]["weapon"], "star")
        resumed.close()
        self.wait_until(lambda: not any(self.server.game.players))
        self.stop_server()
        self.start_server()
        restored = Client(self, "Saved", token)
        self.assertEqual(restored.id, identity)
        own = restored.snapshot["self"]
        self.assertEqual((own["kills"], own["quest"], own["gold"], own["weapon"]), (5, 1, 12, "star"))
        self.place(restored, 0, 24)
        restored.action("equip", "starter_altar")
        self.place(restored, -3, 24)
        _, reequipped = restored.action("equip", "star_altar")
        self.assertEqual((reequipped["self"]["weapon"], reequipped["self"]["gold"]), ("star", 12))
        # A new connection starts action seq at 1; saved stats never reset it globally.
        self.assertEqual(restored.action_seq, 2)
        with self.server.game.lock:
            rows = self.server.game.store.connection.execute("SELECT token_hash FROM characters").fetchall()
        self.assertIn((hashlib.sha256(token.encode()).hexdigest(),), rows)
        self.assertNotIn(token.encode(), self.database.read_bytes())

    def test_monsters_attack_and_respawn_player_and_enemy(self):
        client = Client(self)
        player = self.near_monster(client,dz=1.7)
        with self.server.game.lock:
            player.hp = 1
            monster = self.server.game.monsters[0]
            monster.next_attack = 0
        self.server.game.tick()
        _, dead = client.step()
        self.assertEqual(dead["self"]["hp"], 0)
        counter = dead["self"]["respawn"]
        self.clock.advance(3.1)
        self.server.game.tick()
        client.position = spawn_position(player.slot)
        _, alive = client.step()
        self.assertEqual(alive["self"]["position"], spawn_position(player.slot))
        self.assertEqual(alive["self"]["respawn"], counter + 1)
        self.assertEqual(alive["self"]["hp"], alive["self"]["maxHp"])
        self.near_monster(client)
        with self.server.game.lock:
            monster.hp = 1
        client.action("attack", "slime_0", advance=.7)
        self.clock.advance(12.1)
        self.server.game.tick()
        _, respawned = client.step()
        self.assertTrue(self.monster(respawned)["active"])
        self.assertEqual(self.monster(respawned)["hp"], 45)

    def test_spawn_slots_are_separate_and_initial_probe_pose_is_accepted(self):
        alice, bob = Client(self, "Alice"), Client(self, "Bob")
        self.assertNotEqual(alice.position, bob.position)
        self.assertEqual(alice.position, spawn_position(0))
        self.assertEqual(bob.position, spawn_position(1))
        _, initial = alice.step(position=ENTRY)
        self.assertEqual(initial["self"]["position"], ENTRY)
        # The initial alignment exemption is consumed; another 3m teleport fails.
        _, later = alice.step(position=[3, 1.65, 28])
        self.assertEqual(later["self"]["position"], ENTRY)

    def test_quest_and_star_purchase_rewards_are_idempotent(self):
        client = Client(self)
        player = self.place(client, 0, 20)
        with self.server.game.lock:
            player.kills = 5
        _, first = client.action("claim", "quest_stone")
        self.assertEqual((first["self"]["quest"], first["self"]["gold"]), (1, 100))
        _, again = client.action("claim", "quest_stone")
        self.assertEqual(again["self"]["gold"], 100)
        self.place(client, -3, 24)
        _, purchased = client.action("equip", "star_altar")
        self.assertEqual((purchased["self"]["weapon"], purchased["self"]["gold"]), ("star", 0))
        self.place(client, 0, 24)
        client.action("equip", "starter_altar")
        self.place(client, -3, 24)
        _, free = client.action("equip", "star_altar")
        self.assertEqual((free["self"]["weapon"], free["self"]["gold"]), ("star", 0))
        self.near_monster(client,"warden_0")
        with self.server.game.lock:
            next(monster for monster in self.server.game.monsters if monster.id == "warden_0").hp = 1
        client.action("attack", "warden_0")
        self.place(client, 0, 20)
        _, final = client.action("claim", "quest_stone")
        self.assertEqual((final["self"]["quest"], final["self"]["gold"], final["self"]["xp"]), (2, 390, 350))
        _, replay = client.action("claim", "quest_stone")
        self.assertEqual((replay["self"]["gold"], replay["self"]["xp"]), (390, 350))

    def test_leaving_vacates_only_the_connection_slot(self):
        alice, bob = Client(self, "탐험가"), Client(self, "Bob")
        slot = alice.snapshot["self"]["slot"]
        alice.close()
        self.wait_until(lambda: self.server.game.players[slot] is None)
        _, snapshot = bob.step()
        self.assertFalse(snapshot["players"][slot]["active"])
        self.assertEqual(snapshot["self"]["id"], bob.id)
        replacement = Client(self, "New")
        self.assertEqual(replacement.snapshot["self"]["slot"], slot)
        self.assertNotEqual(replacement.id, alice.id)
    def test_database_is_never_inside_the_published_world_root(self):
        with self.assertRaises(ValueError):
            asterfall.create_server("127.0.0.1", 0, self.worlds, self.world / "characters.sqlite3")
        connection = self.raw_connection()
        asset.send_frame(connection, 1, 0, b"\x00\x01link-game")
        receive(connection)
        asset.send_frame(connection, 3, 1, struct.pack("!I", 65536) + b"../../data/characters.sqlite3")
        self.assertEqual(receive(connection)[0], asset.MESSAGE_ERROR)


    def test_roaming_monsters_are_bounded_and_safe_camp_is_respected(self):
        initial = [monster.position.copy() for monster in self.server.game.monsters]
        for _ in range(80):
            self.clock.advance(.2)
            self.server.game.tick()
        self.assertTrue(all(monster.position != before for monster,before in zip(self.server.game.monsters,initial)))
        for monster in self.server.game.monsters:
            self.assertTrue(BOUNDS["min"][0] <= monster.position[0] <= BOUNDS["max"][0])
            self.assertTrue(BOUNDS["min"][2] <= monster.position[2] <= BOUNDS["max"][2])
            radius = {"slime":4,"wolf":8,"golem":5,"warden":3}[monster.kind]
            self.assertLessEqual(abs(monster.position[0]-monster.home[0]),radius+.01)
            self.assertLessEqual(abs(monster.position[2]-monster.home[1]),radius+.01)
            self.assertFalse(in_camp(monster.position[0],monster.position[2]))
        client = Client(self)
        player = self.place(client,0,28)
        with self.server.game.lock:
            monster = self.server.game.monsters[0]
            monster.position = [0,0,26]
            monster.next_attack = 0
        self.clock.advance(.2);self.server.game.tick()
        self.assertEqual(player.hp,100)
        self.assertGreater(monster.position[2],25)
        # South of the camp is no longer an artificial globally safe half-world.
        self.near_monster(client,"slime_4",dz=1.7)
        with self.server.game.lock:
            south = next(monster for monster in self.server.game.monsters if monster.id=="slime_4")
            south.next_attack = 0
        self.clock.advance(.2);self.server.game.tick()
        self.assertLess(player.hp,100)

    def test_two_clients_gather_exactly_once_and_inventory_is_private(self):
        alice,bob = Client(self,"Alice"),Client(self,"Bob")
        self.near_resource(alice);self.near_resource(bob)
        barrier = threading.Barrier(2);answers=[];errors=[]
        def gather(client):
            try:
                barrier.wait(timeout=2)
                answers.append(client.action("gather","herb_0"))
            except BaseException as error:
                errors.append(error)
        workers=[threading.Thread(target=gather,args=(client,)) for client in (alice,bob)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(timeout=3)
        self.assertFalse(errors)
        self.assertEqual(len(answers),2)
        self.assertEqual(sorted(sum(item["count"] for item in state["inventory"]) for _,state in answers),[0,1])
        self.assertTrue(all(not state["resources"][0]["active"] for _,state in answers))
        for _,state in answers:
            self.assertTrue(all("inventory" not in player for player in state["players"]))
            self.assertEqual(set(state["resources"][0]),{"id","kind","position","active","respawnIn"})
            self.assertLess(len(asterfall.encode_json(state)),65536)
        alice.action_seq += 1
        _, again = alice.step({"kind":"gather","target":"herb_0","seq":alice.action_seq})
        with self.server.game.lock:
            self.assertEqual(sum(sum(player.inventory.values()) for player in self.server.game.players if player),1)
        self.clock.advance(RESOURCE_RESPAWN_SECONDS+.1);self.server.game.tick()
        _, respawned = alice.action("gather","herb_0")
        with self.server.game.lock:
            self.assertEqual(sum(sum(player.inventory.values()) for player in self.server.game.players if player),2)

    def test_gather_range_death_replay_and_full_stack_never_consume_extra_plants(self):
        client = Client(self)
        _, far = client.action("gather","herb_3")
        self.assertEqual(far["inventory"],[])
        self.assertTrue(far["resources"][3]["active"])
        player = self.near_resource(client)
        with self.server.game.lock:player.inventory={"moonleaf":STACK_LIMIT}
        _, full = client.action("gather","herb_0")
        self.assertEqual(full["inventory"],[{"item":"moonleaf","count":STACK_LIMIT}])
        self.assertTrue(full["resources"][0]["active"])
        with self.server.game.lock:player.inventory={};player.hp=0
        _, dead = client.action("gather","herb_0")
        self.assertEqual(dead["inventory"],[])
        self.assertTrue(dead["resources"][0]["active"])
        with self.server.game.lock:player.hp=100
        _, gathered = client.action("gather","herb_0")
        self.assertEqual(gathered["inventory"],[{"item":"moonleaf","count":1}])
        _, replay = client.step({"kind":"gather","target":"herb_0","seq":client.action_seq})
        self.assertEqual(replay["inventory"],[{"item":"moonleaf","count":1}])
        self.assertFalse(replay["resources"][0]["active"])
        # A fabricated close pose still cannot authorize an otherwise remote pickup.
        _, remote = client.step({"kind":"gather","target":"herb_3","seq":client.action_seq+1},position=[-42,1.65,-9])
        self.assertTrue(remote["resources"][3]["active"])
        self.assertEqual(remote["inventory"],[{"item":"moonleaf","count":1}])

    def test_gather_and_loot_persist_across_reconnect_and_server_restart(self):
        client=Client(self,"Collector")
        self.near_resource(client)
        client.action("gather","herb_0")
        self.near_resource(client,1)
        client.action("gather","herb_1")
        player=self.near_monster(client)
        with self.server.game.lock:self.server.game.monsters[0].hp=1
        _, killed=client.action("attack","slime_0")
        inventory={item["item"]:item["count"] for item in killed["inventory"]}
        self.assertEqual(inventory,{"moonleaf":1,"sunbloom":1,"slime_gel":1})
        token=client.token;client.close();self.wait_until(lambda:not any(self.server.game.players))
        resumed=Client(self,"Collector",token)
        self.assertEqual({item["item"]:item["count"] for item in resumed.snapshot["inventory"]},inventory)
        resumed.close();self.wait_until(lambda:not any(self.server.game.players));self.stop_server();self.start_server()
        restored=Client(self,"Collector",token)
        self.assertEqual({item["item"]:item["count"] for item in restored.snapshot["inventory"]},inventory)
        with self.server.game.lock:
            self.assertRaises(GameError,self.server.game.store.save,Player("x"*64,"bad","Bad",inventory={"unknown":5}))

    def test_legacy_character_schema_migrates_with_wal_backup_without_progress_loss(self):
        database=self.base/"legacy.sqlite3"
        old=sqlite3.connect(database)
        self.addCleanup(old.close)
        old.execute("PRAGMA journal_mode=WAL")
        old.execute("CREATE TABLE characters (token_hash TEXT PRIMARY KEY,id TEXT NOT NULL UNIQUE,name TEXT NOT NULL,hp INTEGER NOT NULL,level INTEGER NOT NULL,xp INTEGER NOT NULL,gold INTEGER NOT NULL,weapon TEXT NOT NULL,kills INTEGER NOT NULL,quest INTEGER NOT NULL,attack INTEGER NOT NULL,respawn INTEGER NOT NULL,warden_kills INTEGER NOT NULL,owned_star INTEGER NOT NULL)")
        token="L"*43;token_hash=hashlib.sha256(token.encode()).hexdigest()
        original=(token_hash,"legacy-hero","Legacy",123,3,250,77,"star",9,1,4,2,0,1)
        old.execute("INSERT INTO characters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",original);old.commit()
        self.assertTrue(Path(str(database)+"-wal").exists())
        game=Game(database,clock=self.clock)
        try:
            player,_=game.join(token,"Legacy")
            self.assertEqual((player.id,player.hp,player.level,player.xp,player.gold,player.weapon,player.kills,player.quest,player.owned_star),("legacy-hero",123,3,250,77,"star",9,1,1))
            self.assertEqual(player.inventory,{})
            backup=database.with_name(database.name+".pre-inventory.bak")
            before=backup.read_bytes()
            saved=sqlite3.connect(backup)
            try:
                self.assertEqual(saved.execute("SELECT * FROM characters").fetchone(),original)
                self.assertNotIn("inventory",{row[1] for row in saved.execute("PRAGMA table_info(characters)")})
            finally:saved.close()
            player.inventory={"wildberry":2};game.store.save(player)
        finally:game.close()
        again=Game(database,clock=self.clock)
        try:
            player,_=again.join(token,"Legacy")
            self.assertEqual(player.inventory,{"wildberry":2})
            self.assertEqual(backup.read_bytes(),before)
        finally:again.close()

    def test_forged_inventory_fields_are_rejected(self):
        client=Client(self)
        value={"position":client.position,"yaw":0,"action":None,"inventory":[{"item":"moonleaf","count":99}]}
        self.clock.advance(.06)
        asset.send_frame(client.connection,asterfall.STEP,1,asterfall.encode_json(value))
        self.assertEqual(receive(client.connection)[0],asterfall.FAIL)
        client.connection.close();client.connection=None


    def test_full_monster_loot_stack_preserves_combat_rewards(self):
        client=Client(self)
        player=self.near_monster(client)
        with self.server.game.lock:
            player.inventory={"slime_gel":STACK_LIMIT}
            self.server.game.monsters[0].hp=1
        _,victory=client.action("attack","slime_0")
        self.assertEqual(victory["inventory"],[{"item":"slime_gel","count":STACK_LIMIT}])
        self.assertEqual((victory["self"]["gold"],victory["self"]["xp"],victory["self"]["kills"]),(12,18,1))

    def test_inventory_storage_rejects_unknown_overflow_and_duplicate_items(self):
        database=self.base/"inventory-validation.sqlite3"
        store=CharacterStore(database)
        try:
            player=Player("f"*64,"storage-probe","Probe")
            store.save(player)
            for inventory in ({"unknown":1},{"moonleaf":0},{"moonleaf":100},{"moonleaf":True}):
                player.inventory=inventory
                with self.assertRaises(GameError):store.save(player)
            self.assertEqual(store.load(player.token_hash).inventory,{})
            for source in ('{"moonleaf":1,"moonleaf":2}','{"moonleaf":100}','{"unknown":2}','[]','not-json'):
                store.connection.execute("UPDATE characters SET inventory=? WHERE token_hash=?",(source,player.token_hash));store.connection.commit()
                with self.assertRaises(GameError):store.load(player.token_hash)
        finally:store.close()


if __name__ == "__main__":
    unittest.main()
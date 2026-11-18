# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""One authoritative, bounded cooperative world. No client owns combat or rewards."""
from __future__ import annotations
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from server.world_data import BOUNDS, CAMP_CENTER, CAMP_RADIUS, SPAWNS, RESOURCE_SPAWNS, ITEM_LABELS, INVENTORY_SLOTS, STACK_LIMIT, RESOURCE_RESPAWN_SECONDS

ENTRY = [0.0, 1.65, 28.0]
MAX_PLAYERS = 8
SPEED = 3.6
WEAPONS = {"starter": (12, .65), "iron": (25, .55), "star": (40, .50)}
ALTARS = {"starter_altar": (0, 24), "iron_altar": (3, 24), "star_altar": (-3, 24), "rest_shrine": (0, 30), "quest_stone": (0, 20)}

# HP, damage, speed, aggro, attack cooldown, XP, gold, respawn seconds.
MONSTER_STATS = {"slime": (45, 8, 1.8, 11, 1.4, 18, 12, 12), "wolf": (90, 12, 2.4, 14, 1.1, 35, 20, 18), "golem": (240, 18, 1.2, 18, 1.6, 80, 50, 35), "warden": (700, 28, 1.45, 20, 1.6, 200, 140, 60)}
MONSTER_LOOT = {"slime":"slime_gel", "wolf":"wolf_fang", "golem":"ancient_shard", "warden":"ancient_shard"}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z", re.ASCII)


class GameError(Exception):
    """A short, public protocol error; never contains a token or SQL exception."""


def inventory_value(value):
    if not isinstance(value, dict) or len(value) > INVENTORY_SLOTS:
        raise GameError("Saved inventory is invalid.")
    if any(item not in ITEM_LABELS or not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= STACK_LIMIT for item, count in value.items()):
        raise GameError("Saved inventory is invalid.")
    return dict(value)


def in_camp(x, z):
    return math.hypot(x - CAMP_CENTER[0], z - CAMP_CENTER[1]) < CAMP_RADIUS


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def distance(position, target):
    return math.hypot(position[0] - target[0], position[2] - target[1])


def spawn_position(slot):
    return [round((slot % 4 - 1.5) * 1.4, 3), 1.65, 28.0 + (slot // 4) * 1.6]


def max_hp(level):
    return 100 + 20 * (level - 1)


@dataclass
class Player:
    token_hash: str
    id: str
    name: str
    slot: int = 0
    position: list = field(default_factory=lambda: ENTRY.copy())
    yaw: float = 0
    hp: int = 100
    level: int = 1
    xp: int = 0
    gold: int = 0
    weapon: str = "starter"
    kills: int = 0
    quest: int = 0
    attack: int = 0
    respawn: int = 0
    warden_kills: int = 0
    owned_star: bool = False
    inventory: dict = field(default_factory=dict)
    first_pose: bool = True
    last_step: float = 0
    move_credit: float = .6
    next_attack: float = 0
    death_at: float | None = None
    last_action: int = 0
    notice: str = "Welcome to ASTERFALL. Equip a weapon at the camp altars."

    def public(self):
        return {"id": self.id, "slot": self.slot, "active": True, "name": self.name, "position": [round(v, 4) for v in self.position], "yaw": round(self.yaw, 3), "hp": self.hp, "maxHp": max_hp(self.level), "level": self.level, "xp": self.xp, "gold": self.gold, "weapon": self.weapon, "kills": self.kills, "quest": self.quest, "attack": self.attack, "respawn": self.respawn}


def vacant(slot):
    return {"id": "", "slot": slot, "active": False, "name": "", "position": ENTRY.copy(), "yaw": 0, "hp": 0, "maxHp": 100, "level": 1, "xp": 0, "gold": 0, "weapon": "starter", "kills": 0, "quest": 0, "attack": 0, "respawn": 0}


@dataclass
class Monster:
    id: str
    kind: str
    home: tuple
    position: list
    hp: int
    yaw: float = 0
    attack: int = 0
    active: bool = True
    respawn_at: float = 0
    next_attack: float = 0
    last_combat: float = 0
    participants: dict = field(default_factory=dict)
    patrol_index: int = 0
    returning: bool = False

    def public(self, now):
        return {"id": self.id, "active": self.active, "position": [round(v, 4) for v in self.position], "yaw": round(self.yaw, 3), "hp": self.hp, "maxHp": MONSTER_STATS[self.kind][0], "kind": self.kind, "attack": self.attack, "respawnIn": round(max(0, self.respawn_at - now), 2) if not self.active else 0}


@dataclass
class Resource:
    id: str
    kind: str
    position: tuple
    ready_at: float = 0

    def public(self, now):
        return {"id":self.id,"kind":self.kind,"position":[self.position[0],0,self.position[1]],
                "active":now >= self.ready_at,"respawnIn":round(max(0,self.ready_at-now),2)}


class CharacterStore:
    FIELDS = ("token_hash", "id", "name", "hp", "level", "xp", "gold", "weapon", "kills", "quest", "attack", "respawn", "warden_kills", "owned_star", "inventory")

    def __init__(self, database):
        database = Path(database)
        database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database, timeout=5, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute("CREATE TABLE IF NOT EXISTS characters (token_hash TEXT PRIMARY KEY, id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, hp INTEGER NOT NULL, level INTEGER NOT NULL, xp INTEGER NOT NULL, gold INTEGER NOT NULL, weapon TEXT NOT NULL, kills INTEGER NOT NULL, quest INTEGER NOT NULL, attack INTEGER NOT NULL, respawn INTEGER NOT NULL, warden_kills INTEGER NOT NULL, owned_star INTEGER NOT NULL, inventory TEXT NOT NULL DEFAULT '{}')")
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(characters)")}
        if "inventory" not in columns:
            # SQLite backup includes committed WAL pages. Reserve a new path so a
            # previous pre-migration backup can never be replaced.
            backup_path = database.with_name(database.name+".pre-inventory.bak")
            try:
                with backup_path.open("xb"):
                    pass
            except FileExistsError:
                pass
            else:
                try:
                    backup = sqlite3.connect(backup_path)
                    try:
                        self.connection.backup(backup)
                    finally:
                        backup.close()
                except BaseException:
                    backup_path.unlink(missing_ok=True)
                    self.connection.close()
                    raise
            self.connection.execute("ALTER TABLE characters ADD COLUMN inventory TEXT NOT NULL DEFAULT '{}'")
        self.connection.commit()

    def load(self, token_hash):
        columns = ",".join(self.FIELDS)
        row = self.connection.execute("SELECT " + columns + " FROM characters WHERE token_hash=?", (token_hash,)).fetchone()
        if not row:
            return None
        values = dict(zip(self.FIELDS, row))
        source = values["inventory"]
        if not isinstance(source,str) or len(source) > 4096:
            raise GameError("Saved inventory is invalid.")
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise GameError("Saved inventory is invalid.")
                result[key] = value
            return result
        try:
            values["inventory"] = inventory_value(json.loads(source,object_pairs_hook=unique))
        except (ValueError,TypeError):
            raise GameError("Saved inventory is invalid.") from None
        return Player(**values)

    def save(self, player, commit=True):
        columns = ",".join(self.FIELDS)
        placeholders = ",".join("?" for _ in self.FIELDS)
        inventory = json.dumps(inventory_value(player.inventory), sort_keys=True, separators=(",",":"))
        values = [inventory if key == "inventory" else getattr(player, key) for key in self.FIELDS]
        self.connection.execute("INSERT OR REPLACE INTO characters (" + columns + ") VALUES (" + placeholders + ")", values)
        if commit:
            self.connection.commit()

    def close(self):
        self.connection.commit()
        self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self.connection.close()


class Game:
    def __init__(self, database, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.store = CharacterStore(database)
        self.players = [None] * MAX_PLAYERS
        self.monsters = [Monster(identifier, kind, (x, z), [float(x), 0.0, float(z)], MONSTER_STATS[kind][0]) for identifier, kind, x, z in SPAWNS]
        self.resources = [Resource(identifier,kind,(float(x),float(z))) for identifier,kind,x,z in RESOURCE_SPAWNS]
        self.started = self.last_tick = self.last_flush = self.clock()
        self.tick_count = 0
        self.closed = False
        self.stopping = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._loop, name="asterfall-world", daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.stopping.wait(.05):
            self.tick()

    def join(self, token, name):
        with self.lock:
            if self.closed:
                raise GameError("Server is stopping.")
            if not isinstance(token, str) or (token and not TOKEN_PATTERN.fullmatch(token)):
                raise GameError("Invalid character token.")
            if not isinstance(name, str) or not name.strip() or len(name) > 48 or len(name.encode("utf-8")) > 48 or any(not char.isprintable() for char in name):
                raise GameError("Name must use 1 to 48 printable UTF-8 bytes.")
            name = name.strip()
            token_hash = hashlib.sha256(token.encode("ascii")).hexdigest() if token else ""
            if token_hash and any(player and player.token_hash == token_hash for player in self.players):
                raise GameError("This character is already connected.")
            try:
                slot = self.players.index(None)
            except ValueError:
                raise GameError("The world already has eight players.") from None
            if token:
                player = self.store.load(token_hash)
                if not player:
                    raise GameError("Unknown character token; create a new character.")
                player.name = name
            else:
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
                player = Player(token_hash, "p" + secrets.token_hex(8), name)
            player.slot = slot
            player.position = spawn_position(slot)
            player.last_step = self.clock()
            if player.hp <= 0:
                player.hp = max_hp(player.level)
                player.respawn += 1
            player.hp = min(player.hp, max_hp(player.level))
            self.store.save(player)
            self.players[slot] = player
            return player, token

    def leave(self, player):
        with self.lock:
            if self.players[player.slot] is not player:
                return
            if not self.closed:
                self.store.save(player)
            self.players[player.slot] = None

    def snapshot(self, player):
        with self.lock:
            now = self.clock()
            return {"tick": self.tick_count, "time": round(max(0, now - self.started), 4), "self": player.public(), "players": [other.public() if other else vacant(slot) for slot, other in enumerate(self.players)], "monsters": [monster.public(now) for monster in self.monsters], "notice": player.notice, "inventory":[{"item":item,"count":player.inventory[item]} for item in ITEM_LABELS if item in player.inventory], "resources":[resource.public(now) for resource in self.resources]}

    def step(self, player, value):
        if not isinstance(value, dict) or set(value) != {"position", "yaw", "action"}:
            raise GameError("STEP requires position, yaw and action only.")
        position, yaw, action = value["position"], value["yaw"], value["action"]
        if not isinstance(position, list) or len(position) != 3 or any(not numeric(v) for v in position) or not numeric(yaw) or abs(yaw) > 1000000:
            raise GameError("Pose must contain finite coordinates and yaw.")
        if not all(BOUNDS["min"][axis] <= position[axis] <= BOUNDS["max"][axis] for axis in range(3)):
            raise GameError("Pose is outside the world bounds.")
        if action is not None:
            if not isinstance(action, dict) or set(action) != {"kind", "target", "seq"} or action["kind"] not in ("attack", "equip", "rest", "claim", "gather"):
                raise GameError("Invalid action shape or kind.")
            if not isinstance(action["target"], str) or not 1 <= len(action["target"]) <= 64 or not re.fullmatch(r"[A-Za-z0-9_-]+", action["target"]):
                raise GameError("Invalid action target.")
            if not isinstance(action["seq"], int) or isinstance(action["seq"], bool) or not 1 <= action["seq"] <= 2147483647:
                raise GameError("Action sequence must be a positive integer.")
        with self.lock:
            if self.closed or self.players[player.slot] is not player:
                raise GameError("Character session is no longer active.")
            now = self.clock()
            elapsed = max(0, now - player.last_step)
            player.last_step = now
            player.move_credit = min(1.2, player.move_credit + SPEED * elapsed)
            travel = math.hypot(position[0] - player.position[0], position[2] - player.position[2])
            if player.hp > 0:
                if travel <= player.move_credit + 1e-6 or (player.first_pose and travel <= 3.0):
                    player.position = [float(v) for v in position]
                    player.yaw = (float(yaw) + 180) % 360 - 180
                    player.move_credit = max(0, player.move_credit - travel)
                else:
                    player.notice = "Movement rejected: keep within the walking speed."
            player.first_pose = False
            if action is not None and action["seq"] > player.last_action:
                player.last_action = action["seq"]
                if player.hp > 0:
                    self._action(player, action, now)
                else:
                    player.notice = "You are down. Respawning at camp in three seconds."
            return self.snapshot(player)

    def _action(self, player, action, now):
        kind, target = action["kind"], action["target"]
        if kind == "gather":
            resource = next((resource for resource in self.resources if resource.id == target),None)
            if resource is None or now < resource.ready_at:
                player.notice = "This plant is recovering. Explore another grove."
                return
            if distance(player.position,resource.position) > 2.8 or abs(player.position[1]-1.65) > 1.5:
                player.notice = "Move within 2.8 metres to gather this plant."
                return
            previous = player.inventory.copy()
            if not self._add_item(player,resource.kind):
                player.notice = "Inventory stack is full. This plant is still available."
                return
            try:
                self.store.save(player)
            except BaseException:
                player.inventory = previous
                raise
            resource.ready_at = now + RESOURCE_RESPAWN_SECONDS
            player.notice = "Gathered " + ITEM_LABELS[resource.kind] + " +1. Open Status to view your inventory."
            return
        if kind == "attack":
            monster = next((monster for monster in self.monsters if monster.id == target), None)
            if not monster or not monster.active:
                player.notice = "That enemy is not available."
                return
            melee_distance = math.sqrt((player.position[0] - monster.position[0]) ** 2 + (player.position[1] - 1.65) ** 2 + (player.position[2] - monster.position[2]) ** 2)
            if melee_distance > 3.5:
                player.notice = "Move within 3.5 metres to attack."
                return
            if now < player.next_attack:
                player.notice = "Your weapon is still recovering."
                return
            damage, cooldown = WEAPONS[player.weapon]
            player.next_attack = now + cooldown
            player.attack += 1
            monster.hp = max(0, monster.hp - damage)
            monster.last_combat = now
            monster.participants[player.id] = now
            player.notice = "Hit " + monster.kind + " for " + str(damage) + "."
            if not monster.hp:
                self._kill(monster, player, now)
            self.store.save(player)
            return
        altar = ALTARS.get(target)
        expected = {"equip": {"starter_altar", "iron_altar", "star_altar"}, "rest": {"rest_shrine"}, "claim": {"quest_stone"}}
        if target not in expected.get(kind, set()) or not altar:
            player.notice = "That action does not match the target."
            return
        if distance(player.position, altar) > 4.5:
            player.notice = "Move within 4.5 metres of the camp station."
            return
        if kind == "equip":
            if target == "star_altar":
                if not player.owned_star:
                    if player.quest < 1 or player.gold < 100:
                        player.notice = "Starblade requires the first quest and 100 gold."
                        return
                    player.gold -= 100
                    player.owned_star = True
                player.weapon = "star"
            else:
                player.weapon = "iron" if target == "iron_altar" else "starter"
            player.notice = "Equipped " + player.weapon + "."
        elif kind == "rest":
            player.hp = max_hp(player.level)
            player.notice = "The camp shrine restored your health."
        elif player.quest == 0 and player.kills >= 5:
            player.quest = 1
            player.gold += 100
            player.notice = "Quest complete: five enemies. Reward: 100 gold; Starblade unlocked."
        elif player.quest == 1 and player.warden_kills > 0:
            player.quest = 2
            player.gold += 250
            self._xp(player, 150)
            player.notice = "The Warden has fallen. Final quest reward: 250 gold and 150 XP."
        else:
            player.notice = "Quest: defeat five enemies, then defeat the Warden."
        self.store.save(player)

    def _add_item(self, player, item, count=1):
        if item not in ITEM_LABELS or not isinstance(count,int) or isinstance(count,bool) or count < 1:
            return False
        current = player.inventory.get(item,0)
        if current + count > STACK_LIMIT or (not current and len(player.inventory) >= INVENTORY_SLOTS):
            return False
        player.inventory[item] = current + count
        return True

    def _xp(self, player, amount):
        player.xp += amount
        previous = player.level
        player.level = min(100, 1 + player.xp // 100)
        if player.level > previous:
            player.hp = min(max_hp(player.level), player.hp + 20 * (player.level - previous))

    def _kill(self, monster, killer, now):
        # This transition happens under one world lock before any rewards are issued.
        monster.active = False
        stats = MONSTER_STATS[monster.kind]
        monster.respawn_at = now + stats[7]
        for player in self.players:
            if not player or player.hp <= 0:
                continue
            contributed = now - monster.participants.get(player.id, -1000000) <= 20
            nearby = distance(player.position, (monster.position[0], monster.position[2])) <= 12
            if player is killer or (contributed and nearby):
                player.kills += 1
                player.gold += stats[6]
                self._xp(player, stats[5])
                if monster.kind == "warden":
                    player.warden_kills += 1
                loot = MONSTER_LOOT[monster.kind]
                gained = self._add_item(player,loot)
                player.notice = "Co-op victory: " + monster.kind + ". +" + str(stats[6]) + " gold. " + (ITEM_LABELS[loot]+" +1." if gained else "Material stack full; XP and gold received.")
                self.store.save(player, commit=False)
        monster.participants.clear()
        self.store.connection.commit()

    def tick(self):
        with self.lock:
            if self.closed:
                return
            now = self.clock()
            delta = min(.2, max(0, now - self.last_tick))
            self.last_tick = now
            self.tick_count += 1
            for player in self.players:
                if player and player.hp <= 0 and player.death_at is not None and now - player.death_at >= 3:
                    player.hp = max_hp(player.level)
                    player.position = spawn_position(player.slot)
                    player.yaw = 0
                    player.respawn += 1
                    player.death_at = None
                    player.last_step = now
                    player.move_credit = .6
                    player.notice = "Respawned at camp. Your progress and equipment are safe."
                    self.store.save(player)
            for monster in self.monsters:
                self._monster_tick(monster, now, delta)
            if now - self.last_flush >= 10:
                for player in self.players:
                    if player:
                        self.store.save(player, commit=False)
                self.store.connection.commit()
                self.last_flush = now

    def _monster_tick(self, monster, now, delta):
        stats = MONSTER_STATS[monster.kind]
        if not monster.active:
            if now >= monster.respawn_at:
                monster.active = True
                monster.hp = stats[0]
                monster.position = [float(monster.home[0]), 0.0, float(monster.home[1])]
                monster.respawn_at = 0
                monster.next_attack = now + 1
                monster.participants.clear()
                monster.returning = False
                monster.patrol_index = 0
            return
        home_distance = distance(monster.position,monster.home)
        if home_distance > stats[3] + 8 or in_camp(monster.position[0],monster.position[2]):
            monster.returning = True
        candidates = [] if monster.returning else [player for player in self.players if player and player.hp > 0 and not in_camp(player.position[0],player.position[2]) and distance(player.position,monster.home) <= stats[3] + 7 and distance(player.position,(monster.position[0],monster.position[2])) <= stats[3]]
        target = min(candidates,key=lambda player:distance(player.position,(monster.position[0],monster.position[2])),default=None)
        if not target and monster.hp < stats[0] and now-monster.last_combat > 8:
            monster.returning = True
        if monster.returning and home_distance <= .2:
            monster.hp = stats[0]
            monster.participants.clear()
            monster.returning = False
        radius = {"slime":4,"wolf":8,"golem":5,"warden":3}[monster.kind]
        corners = ((1,-1),(-1,-1),(-1,1),(1,1))
        offset = corners[monster.patrol_index % 4]
        patrol = (monster.home[0]+offset[0]*radius,monster.home[1]+offset[1]*radius)
        destination = (target.position[0],target.position[2]) if target else monster.home if monster.returning else patrol
        dx,dz = destination[0]-monster.position[0],destination[1]-monster.position[2]
        length = math.hypot(dx,dz)
        if length > .001:
            monster.yaw = math.degrees(math.atan2(-dx,-dz))
            speed = stats[2] * (1 if target or monster.returning else .45)
            travel = min(length if not target else max(0,length-1.7),speed*delta)
            nx,nz = monster.position[0]+dx/length*travel,monster.position[2]+dz/length*travel
            approaching_camp = in_camp(nx,nz) and math.hypot(nx-CAMP_CENTER[0],nz-CAMP_CENTER[1]) < math.hypot(monster.position[0]-CAMP_CENTER[0],monster.position[2]-CAMP_CENTER[1])
            if not approaching_camp:
                monster.position[0] = min(BOUNDS["max"][0],max(BOUNDS["min"][0],nx))
                monster.position[2] = min(BOUNDS["max"][2],max(BOUNDS["min"][2],nz))
            else:
                monster.returning = True
        if not target and not monster.returning and length <= .2:
            monster.patrol_index = (monster.patrol_index+1)%4
        if target and length <= 2.3 and now >= monster.next_attack:
            monster.next_attack = now+stats[4]
            monster.attack += 1
            monster.last_combat = now
            armor = {"starter":1,"iron":.8,"star":.65}[target.weapon]
            target.hp = max(0,target.hp-max(1,round(stats[1]*armor)))
            target.notice = monster.kind.title()+" hit you. Retreat to camp to rest."
            if target.hp == 0:
                target.death_at = now
                target.notice = "You are down. Respawning at camp in three seconds."
                self.store.save(target)

    def close(self):
        self.stopping.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        with self.lock:
            if self.closed:
                return
            for player in self.players:
                if player:
                    self.store.save(player, commit=False)
            self.store.connection.commit()
            self.closed = True
            self.store.close()
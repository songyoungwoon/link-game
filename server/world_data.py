# Copyright 2026 Song Youngwoon
# SPDX-License-Identifier: Apache-2.0
"""Static, dependency-free terrain contract shared by server and world generator."""
BOUNDS = {"min": [-120, 0, -140], "max": [120, 4, 110]}
CAMP_CENTER = (0, 28)
CAMP_RADIUS = 13
SPAWNS = [
    ("slime_0", "slime", -24, 8), ("slime_1", "slime", -58, -12),
    ("slime_2", "slime", 28, 0), ("slime_3", "slime", 58, -38),
    ("wolf_0", "wolf", -72, -50), ("wolf_1", "wolf", 72, -68),
    ("golem_0", "golem", 32, -90), ("warden_0", "warden", 0, -112),
    ("slime_4", "slime", 45, 65), ("slime_5", "slime", -80, 62),
    ("wolf_2", "wolf", -35, -100), ("wolf_3", "wolf", 85, 10),
]
RESOURCE_SPAWNS = [
    ("herb_0", "moonleaf", 8, 29), ("herb_1", "sunbloom", -9, 31),
    ("herb_2", "wildberry", -18, 7), ("herb_3", "moonleaf", -42, -10),
    ("herb_4", "wildberry", -63, -28), ("herb_5", "sunbloom", -90, -45),
    ("herb_6", "moonleaf", -25, -72), ("herb_7", "sunbloom", 18, -88),
    ("herb_8", "wildberry", 52, -48), ("herb_9", "moonleaf", 78, -82),
    ("herb_10", "sunbloom", 89, 3), ("herb_11", "wildberry", 50, 40),
    ("herb_12", "sunbloom", 20, 72), ("herb_13", "wildberry", -28, 85),
    ("herb_14", "moonleaf", -72, 65), ("herb_15", "sunbloom", -88, 18),
]
ITEM_LABELS = {"moonleaf": "Moonleaf", "sunbloom": "Sunbloom", "wildberry": "Wild Berry",
               "slime_gel": "Slime Gel", "wolf_fang": "Wolf Fang", "ancient_shard": "Ancient Shard"}
INVENTORY_SLOTS = 16
STACK_LIMIT = 99
RESOURCE_RESPAWN_SECONDS = 60

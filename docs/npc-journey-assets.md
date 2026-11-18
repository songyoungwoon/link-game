# The Wayfarer’s Passage — original demo assets

Two independent addresses share one traveling NPC: Dawn Court (`traveler-a`) and Azure Court (`traveler-b`). The warm stone and cool blue courts use original Element geometry. Liora is the original Apache-2.0 character from Moon Garden, copied unchanged into each world as a destination-owned model.

The server owns movement, identity, authority, epoch and journey count. These worlds never decide that an NPC has crossed a portal. Their Script only renders validated observations and interpolates between positions. The NPC continues on the servers while the browser is closed. Her current route is a bounded waypoint demonstration, not an AI model or general obstacle navigation.

| Item | Contract |
| --- | --- |
| Default Dawn address | `link://127.0.0.1:8010/traveler-a` |
| Default Azure address | `link://127.0.0.1:8011/traveler-b` |
| Server configuration | `configs/npc-traveler-a.json`, `configs/npc-traveler-b.json` |
| Arrival, both courts | `[0, 0, 3]`, outside the outgoing portal |
| Route | Arrival → `[-2, 0, 1]`, wait 2 seconds → outgoing portal |
| Portal | Center `[0, 1.5, -4]`, size `[2, 3, 1]` |
| NPC speed | 0.8 meters per second |
| Browser extensions | `models-v1`, `npc-travel-v1` |
| Presentation binding | Component `npc_slot`, model `traveler_model` |
| Durable demo identity | `wayfarer-01`, kind `liora`, display name Liora |

Walking into the visible gateway changes the browser’s address to the peer server. This navigation observes the NPC’s already server-owned journey; it does not carry or duplicate the NPC. Start both NPC servers before opening either remote address. Local file previews show the court and hide the NPC until an observer session supplies state.

The protocol can observe up to 16 NPCs. This deliberately small demonstration has one authored model slot and displays the first supported `liora` entry. Unknown kinds are hidden. Adding another kind requires a destination-owned asset mapping and additional authored slots. Models, Script and executable code are never received as part of a character handoff.

The observation plaque displays the stable NPC ID, journey count and authority epoch. Empty observations hide `npc_slot` immediately. A new identity or epoch snaps the visual model to its arrival pose; ordinary updates interpolate pose for presentation. The same model supplies `Idle` and `Walk` clips. These interpolation frames do not advance the authoritative character on the server.

## Reproduction

Run from `link-game` with Python 3:

```powershell
python tools/generate_npc_journey.py
```

No packages, internet downloads, Blender installation or image generation are required. The source `worlds/moon-garden/models/hero.glb` must exist. The script creates only the two journey world directories and their two public server configuration files. It does not open character databases, generate credentials or reset NPC progress.

For two computers, use the IPv4 addresses that each browser and server can reach:

```powershell
python tools/generate_npc_journey.py --host-a 192.168.0.10 --host-b 192.168.0.11 --port-a 8010 --port-b 8011
```

This regenerates portal destinations and peer allowlists together. Restart the NPC servers with the updated configurations. The defaults use loopback and are intended for two processes on the same computer. `0.0.0.0` is a bind address, so the generator rejects it as a destination.

Each world contains 158 nodes, one self-contained 779,304-byte GLB, no external textures and six output files. Each server configuration remains outside the published `worlds` directory. The generated `asset-report.json` files record addresses, node counts, model provenance and SHA-256.

## Model provenance and limits

Liora’s original geometry, 21-joint skeleton, `Idle`/`Walk`/`Attack` clips and embedded face/clothing images were authored in `tools/generate_moon_garden.py`. The copied GLB SHA-256 is:

```text
51e0a6ba54e2fdcaa1726bbe003f23f4805c639540b441d8230285997b80ea3b
```

The character, new court geometry, palette, Script and generator are Apache-2.0, Copyright 2026 Song Youngwoon. There are no third-party visual assets in these two worlds. See `docs/moon-garden-assets.md` for the original model’s construction and renderer limitations.

The floor is level and movement uses the current rectangular walk bounds. Decorative planters, columns and walls have no physical collision. The scene makes no claim of terrain physics, arbitrary cross-server AI, public-internet encryption or headset comfort certification.

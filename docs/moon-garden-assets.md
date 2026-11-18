# MOON GARDEN assets and authoring notes

MOON GARDEN is an original, small visual demonstration for LINK's `models-v1`
profile. Liora, the Garden Wayfarer, wears a blue and ivory traveling coat and
carries an original sword. She breathes, walks across a short stage and performs a
sword technique in a garden of pale stone, reflecting water and planted ruins.
The scene is a first textured-model and skeletal-animation milestone. It is a
stylized demonstration, with no claim of photorealism or parity with a commercial
engine's complete rendering pipeline.

## Files and provenance

| File | Purpose | Origin |
| --- | --- | --- |
| `worlds/moon-garden/models/hero.glb` | Skinned character, face and cloth textures, contact shade | Generated from scratch by the source below |
| `worlds/moon-garden/models/garden.glb` | Courtyard, arch, water, vegetation, mountain layers and sky accents | Generated from scratch by the source below |
| `tools/generate_moon_garden.py` | Editable source for every shape, pixel, bone, keyframe and world document | Original Python 3 code; standard library only |
| `worlds/moon-garden/asset-report.json` | Byte sizes, geometry counts and SHA-256 digests | Written by the generator |
| `worlds/moon-garden/scene.element` | Two imported models and three world-space text surfaces | Generated Element document |
| `worlds/moon-garden/appearance.style` | PBR courtyard and thin-outline toon character | Generated Style document |
| `worlds/moon-garden/scripts/wayfarer.script` | Named-clip playback and short local walking route | Generated Script document |

No downloaded meshes, photographs, font files, motion-capture clips, textures,
character designs or existing game maps are included. The name Liora and the
wayfarer's appearance were created for this scene; they do not reproduce an
existing anime character. All pixels are procedural: woven cloth, facial details,
stone joints and weathering, grass, bark, leaf veins and water caustics.

The source and generated original assets are distributed under this repository's
[Apache License 2.0](../LICENSE). Copyright 2026 Song Youngwoon. There are no
third-party art attributions or art-license dependencies for this world. LINK's
browser dependencies retain their separate upstream licenses.

## Generate and inspect

From the `link-game` directory:

```powershell
python tools/generate_moon_garden.py
```

The generator needs Python 3 and uses no additional packages. It writes only the
new `worlds/moon-garden` directory and prints an asset report. Repeated generation
on the tested Python installation produces identical bytes for all seven world
files. It contains fixed seeds and no timestamps or absolute machine paths.
Changes to the generator intentionally replace the generated world documents and
models, so edit the source when a change must survive regeneration.

Use an updated LINK Browser with `models-v1` support. Run the existing game server
and navigate to `link://127.0.0.1:8002/moon-garden` on the same PC; replace the host
and port with the server's configured address for another PC. For direct local
inspection, launch the browser with its `--worlds` option pointing at this
repository's `worlds` directory, then open `link://local/moon-garden`.

The world deliberately requests only `models-v1`. It is a local animation
presentation, and does not connect to the multiplayer RPG's shared-state session
or change saved inventory, quests or combat progress.

## Interaction and animation

On entry, Liora idles for 3.5 seconds, walks a short route across the stage, returns
to the center and performs an attack. Selecting her model with the desktop pointer
or a supported VR controller ray immediately requests the `Attack` clip. Existing
LINK walking, head tracking, controller movement and VR comfort settings remain
the browser's responsibility.

| glTF clip | Duration | Motion |
| --- | --- | --- |
| `Idle` | 3 seconds, looping | Breathing, a subtle head turn and scarf movement |
| `Walk` | 1 second, looping | Articulated legs, knees, ankles, arms, coat tails and scarf |
| `Attack` | 1.35 seconds, one shot | Wind-up, overhead sword swing, torso turn and recovery |

The Script calls `ctx.playAnimation("hero_model", "Idle", true, 1)` and changes
the selected clip at transitions. Character placement along the short route uses
`ctx.setTransform`. The GLB clips deform actual bones and mesh vertices; moving the
Element is independent of skeletal animation. This is not authoritative combat,
root-motion extraction or a multiplayer character controller.

## Coordinate and model contract

- Units: meters. Y is up; the character faces +Z and stands about 1.84 meters tall.
- The character's feet are at ground level; its Element begins at `[0,0,-5]`.
- The level walking rectangle is X `[-12,12]`, Z `[-18,10]`, eye height 1.65 meters.
- Mountains, the sun and other backdrop geometry extend outside that rectangle.
- The scene contains 21 skeleton joints. Every skinned vertex has normalized
  `JOINTS_0` / `WEIGHTS_0` values and embedded inverse-bind matrices.
- Character parts have rigid single-joint weights, with overlapping closed joint
  shapes. This first rig does not include facial blendshapes, soft cloth simulation
  or a production-quality anatomical deformation rig.
- A separate unskinned, unlit `BLEND` mesh with radial vertex alpha gives Liora a
  small, soft ground-contact shade that follows her Element. Tree shade is baked
  into vertex colors over the matching grass texture.

| Asset | Bytes | Vertices | Triangles | Draw primitives | Joints | Embedded images |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `hero.glb` | 779,304 | 8,815 | 11,632 | 13 | 21 | 2 |
| `garden.glb` | 2,706,032 | 43,774 | 44,026 | 19 | 0 | 6 |

Both are glTF 2.0 binary files with embedded BIN buffers, indexed `TRIANGLES`,
finite normals, UV0, vertex colors and embedded PNG bufferViews. No external URI,
data URI, mesh compression, morph targets, cubic animation interpolation or extra
PBR texture maps are required. `KHR_materials_unlit` is used only for the authored
sun/cloud accents and the character's contact shade. Animation uses glTF TRS
channels with `LINEAR` interpolation.

The courtyard uses metallic-roughness material factors, six embedded textures,
vertex shading, detailed mesh silhouettes and four layers of continuous mountain
ridges. The character uses a facial texture, woven cloth texture, toon lighting and
a 0.0048-meter outline. Style keeps its base color white and leaves roughness and
metalness unset, preserving each imported material's authored values.

## Verification and current limits

The assets were regenerated twice and compared by SHA-256. Structural checks
verify GLB chunk lengths, embedded-only resources, accessor alignment, index
bounds, finite unit normals, valid joint indices, normalized weights, PNG headers
and increasing animation key times. LINK's real model loader was also used to
sample the original rig across all three clips and confirm finite deformed
positions and normalized normals; the browser's end-to-end model smoke test
covers rendering, selection and animation playback.

The water uses an authored caustic texture, without planar reflection or fluid
simulation. Vegetation and ruins are static geometry. There are no dynamic shadow
maps, terrain collision meshes, material normal maps, animation blending, inverse
kinematics, LOD streaming or real headset performance results implied by this art
package. Existing LINK walking keeps the viewer on a flat plane, so the decorative
pool borders, columns and benches are not a physical obstacle course. The scene
provides a practical base for those later improvements.

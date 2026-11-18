from pathlib import Path
import tempfile
import unittest
from server.vendor import link_server as asset

class ModelAssets(unittest.TestCase):
    def test_glb_type_budget_and_confinement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            world = root / "sample"
            world.mkdir()
            (world / "hero.glb").write_bytes(b"glTF")
            resolved, directory, limit, mime = asset.resolve_resource(root, "/sample/hero.glb")
            self.assertEqual(resolved, (world / "hero.glb").resolve())
            self.assertEqual(limit, 16 * 1024 * 1024)
            self.assertEqual(mime, "model/gltf-binary")
            with self.assertRaises(asset.RequestError):
                asset.resolve_resource(root, "/sample/../hero.glb")
            with self.assertRaises(asset.RequestError):
                asset.resource_type(Path("external.gltf"))
            (world / "sky.hdr").write_bytes(b"#?RADIANCE")
            resolved, directory, limit, mime = asset.resolve_resource(root, "/sample/sky.hdr")
            self.assertEqual(limit, 8 * 1024 * 1024)
            self.assertEqual(mime, "image/vnd.radiance")
            self.assertEqual(asset.read_resource(resolved, directory, limit), b"#?RADIANCE")


if __name__ == "__main__":
    unittest.main()

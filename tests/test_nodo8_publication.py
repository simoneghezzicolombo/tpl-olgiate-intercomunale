"""The retired map must stay in Git and must not enter the public artifact."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publication", ROOT / "scripts/build_nodo8_publication.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicationTests(unittest.TestCase):
    def test_exactly_two_html_pages_and_all_dependencies(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "site"
            manifest = module.build(output, revision="test")
            self.assertEqual(set(manifest["published_html_pages"]), module.HTML_PAGES)
            self.assertFalse((output / "outputs/maps/mappa_interattiva_rete_tpl_olgiate.html").exists())
            self.assertFalse((output / ".github").exists())
            self.assertFalse((output / "scripts").exists())
            self.assertTrue((ROOT / "outputs/maps/mappa_interattiva_rete_tpl_olgiate.html").exists())
            module.validate_links(output)

    def test_no_deletion_of_unpublished_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "source"
            root.mkdir()
            for name in module.selected_files():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            (root / "config").mkdir(exist_ok=True)
            shutil.copyfile(ROOT / module.POLICY, root / module.POLICY)
            old = root / "retired-site.html"
            old.write_text("keep me", encoding="utf-8")
            module.build(Path(folder) / "public", root=root)
            self.assertEqual(old.read_text(encoding="utf-8"), "keep me")
            self.assertFalse((Path(folder) / "public/retired-site.html").exists())

    def test_rejects_an_extra_html_site(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config").mkdir()
            policy = json.loads((ROOT / module.POLICY).read_text(encoding="utf-8"))
            policy["include_files"].append("old-site.html")
            (root / module.POLICY).write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaises(ValueError):
                module.selected_files(root)

    def test_refuses_overwriting_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            marker = output / "valuable.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                module.build(output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()

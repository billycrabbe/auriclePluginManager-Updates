"""Tests for the brand readers (against real page excerpts) and the updater's safety rules."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import readers  # noqa: E402
import update  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def page(name):
    with open(os.path.join(FIX, name)) as f:
        return f.read()


def fake_fetch(url):
    if "fabfilter" in url:
        return page("fabfilter.html")
    if "u-he" in url:
        return page("uhe.html")
    if "kilohearts" in url:
        return page("kilohearts.html")
    if "soundtoys" in url:
        return page("soundtoys.html")
    if "valhalla-shimmer" in url:
        return page("valhalla_shimmer.html")
    if "valhalla-vintage-verb" in url:
        return page("valhalla_vintageverb.html")
    return ""


class Readers(unittest.TestCase):
    def test_fabfilter(self):
        self.assertEqual(readers.fabfilter(fake_fetch),
                         {"FabFilter Pro-Q 4": "4.13", "FabFilter Pro-C 3": "3.02", "FabFilter Timeless 3": "3.10"})

    def test_uhe_quoted_and_unquoted_names(self):
        self.assertEqual(readers.uhe(fake_fetch), {"Zebra 3": "3.0.2", "Diva": "1.4.8"})

    def test_valhalla_current_and_per_os(self):
        found = readers.valhalla(fake_fetch)
        self.assertEqual(found["ValhallaVintageVerb"], "4.0.5")
        self.assertEqual(found["ValhallaShimmer"], "1.2.2")  # lower of Mac 1.3.0 / Windows 1.2.2

    def test_kilohearts_uses_changelog_not_installer(self):
        self.assertEqual(readers.kilohearts(fake_fetch), {"*": "2.4.6"})

    def test_soundtoys_newest_entry(self):
        self.assertEqual(readers.soundtoys(fake_fetch), {"*": "5.5.5"})


class Updater(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.list_file = os.path.join(self.dir, "plugin-versions.json")
        self.catalog = os.path.join(self.dir, "catalog.json")
        with open(self.catalog, "w") as f:
            json.dump({"products": [
                {"brand": "fabfilter", "product": "Pro-Q 4", "keys": ["com.fabfilter.pro-q.4", "fabfilter:pro-q 4"]},
                {"brand": "valhalla", "product": "ValhallaVintageVerb", "keys": ["com.valhalladsp.vintageverb"]},
                {"brand": "soundtoys", "product": "EchoBoy", "keys": ["com.soundtoys.echoboy"]},
                {"brand": "u-he", "product": "Diva", "keys": ["com.u-he.diva"]},
            ]}, f)

    def write_list(self, plugins):
        with open(self.list_file, "w") as f:
            json.dump({"schema": 1, "updated": "", "plugins": plugins}, f)

    def run_update(self, fetcher=fake_fetch):
        return update.run(fetcher=fetcher, list_file=self.list_file, catalog_file=self.catalog)

    def read_list(self):
        with open(self.list_file) as f:
            return json.load(f)["plugins"]

    def test_creates_entries_matched_by_normalised_name(self):
        changed, failures, notes, _ = self.run_update()
        p = self.read_list()
        self.assertTrue(changed)
        self.assertEqual(failures, [])
        self.assertEqual(p["com.fabfilter.pro-q.4"]["latest"], "4.13")
        self.assertEqual(p["com.fabfilter.pro-q.4"]["aliases"], ["fabfilter:pro-q 4"])
        self.assertEqual(p["com.valhalladsp.vintageverb"]["latest"], "4.0.5")
        self.assertEqual(p["com.soundtoys.echoboy"]["latest"], "5.5.5")
        self.assertEqual(p["com.u-he.diva"]["latest"], "1.4.8")

    def test_hand_made_entries_never_touched(self):
        auricle = {"latest": "2.1.0", "url": "https://www.auricleaudio.co.uk/l/x", "versionStyle": "semver"}
        self.write_list({"com.auricleaudio.auricleapeiron": auricle,
                         "com.fabfilter.pro-q.4": {"latest": "9.9", "url": "https://example.com"}})
        self.run_update()
        p = self.read_list()
        self.assertEqual(p["com.auricleaudio.auricleapeiron"], auricle)
        self.assertEqual(p["com.fabfilter.pro-q.4"]["latest"], "9.9")  # no "source": hand-made, kept

    def test_never_lowers_a_version(self):
        self.write_list({"com.fabfilter.pro-q.4": {"latest": "4.20", "url": "https://x", "source": "auto:fabfilter"}})
        _, _, notes, _ = self.run_update()
        self.assertEqual(self.read_list()["com.fabfilter.pro-q.4"]["latest"], "4.20")
        self.assertTrue(any("older than" in n for n in notes))

    def test_failed_reader_keeps_old_versions_and_reports(self):
        self.write_list({"com.u-he.diva": {"latest": "1.4.7", "url": "https://x", "source": "auto:u-he"}})

        def broken(url):
            if "u-he" in url:
                raise RuntimeError("HTTP 503")
            return fake_fetch(url)

        _, failures, _, _ = self.run_update(broken)
        self.assertEqual(self.read_list()["com.u-he.diva"]["latest"], "1.4.7")
        self.assertTrue(any(f.startswith("u-he:") for f in failures))

    def test_layout_change_reported_not_published(self):
        _, failures, _, _ = self.run_update(lambda url: "" if "fabfilter" in url else fake_fetch(url))
        self.assertNotIn("com.fabfilter.pro-q.4", self.read_list())
        self.assertTrue(any("no versions found" in f for f in failures))

    def test_output_matches_plugin_manager_format(self):
        self.run_update()
        with open(self.list_file) as f:
            doc = json.load(f)
        self.assertEqual(doc["schema"], 1)
        for key, e in doc["plugins"].items():
            self.assertEqual(key, key.lower())
            self.assertRegex(e["latest"], r"^[0-9]+(\.[0-9]+){1,3}$")
            self.assertTrue(e["url"].startswith("https://"))  # the app ignores non-https links


if __name__ == "__main__":
    unittest.main()

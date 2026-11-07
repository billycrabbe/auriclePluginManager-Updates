"""Refreshes plugin-versions.json from the brand readers. Run weekly by GitHub Actions.

Safety rules:
  * Only entries this script created ("source": "auto:<brand>") are ever changed. Hand-made
    entries, such as the auricle plugins, are never touched.
  * A value is only accepted if it looks like a version number.
  * A version is never lowered.
  * A brand whose reader fails, or returns nothing, keeps its previous versions and is
    listed in failures.txt (the workflow turns that into a GitHub issue).

Usage: python tools/versions/update.py [--dry-run]
"""
import datetime
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from readers import READERS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
LIST_FILE = os.path.join(ROOT, "plugin-versions.json")
CATALOG_FILE = os.path.join(HERE, "catalog.json")
FAILURES_FILE = os.path.join(ROOT, "failures.txt")
VALID_VERSION = re.compile(r"^[0-9]+(\.[0-9]+){1,3}$")
USER_AGENT = "auricle-plugin-manager-version-check/1.0 (+https://www.auricleaudio.co.uk)"


def fetch(url):
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # network blips: retry, then give up on this brand
            last = e
    raise RuntimeError(f"{url}: {last}")


BRAND_WORDS = ("fabfilter", "valhalla", "u-he", "uhe", "kilohearts", "soundtoys")


def norm(name):
    """'FabFilter Pro-Q 4' / 'Pro-Q 4' / 'ValhallaVintageVerb' -> 'proq4' / 'vintageverb'."""
    s = name.lower()
    for w in BRAND_WORDS:
        s = s.replace(w, "")
    return re.sub(r"[^a-z0-9]", "", s)


def lookup(found, product):
    if "*" in found:
        return found["*"]
    want = norm(product)
    for name, version in found.items():
        if norm(name) == want:
            return version
    return None


def as_tuple(v):
    return tuple(int(x) for x in v.split("."))


def is_newer_or_same(new, old):
    a, b = as_tuple(new), as_tuple(old)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) >= b + (0,) * (n - len(b))


def run(fetcher=fetch, dry_run=False, list_file=LIST_FILE, catalog_file=CATALOG_FILE):
    with open(catalog_file) as f:
        catalog = json.load(f)["products"]
    if os.path.exists(list_file):
        with open(list_file) as f:
            doc = json.load(f)
    else:
        doc = {"schema": 1, "updated": "", "plugins": {}}
    plugins = doc.setdefault("plugins", {})
    before = json.dumps(plugins, sort_keys=True)

    failures, notes = [], []
    for brand, (reader, url, style) in READERS.items():
        entries = [p for p in catalog if p["brand"] == brand]
        if not entries:
            continue
        try:
            found = reader(fetcher)
        except Exception as e:
            failures.append(f"{brand}: reader failed ({e})")
            continue
        if not found:
            failures.append(f"{brand}: page read but no versions found (layout may have changed)")
            continue

        for p in entries:
            version = lookup(found, p["product"])
            if version is None:
                notes.append(f"{brand}: '{p['product']}' not on the page (renamed or discontinued?)")
                continue
            if not VALID_VERSION.match(version):
                failures.append(f"{brand}: '{p['product']}' gave an invalid version {version!r}")
                continue
            key = p["keys"][0]
            old = plugins.get(key)
            if old is not None and not str(old.get("source", "")).startswith("auto:"):
                continue  # hand-made entry (e.g. auricle plugins): never touched
            if old is not None and VALID_VERSION.match(str(old.get("latest", ""))) \
                    and not is_newer_or_same(version, old["latest"]):
                notes.append(f"{brand}: '{p['product']}' page shows {version}, older than {old['latest']}; kept")
                continue
            plugins[key] = {
                "latest": version,
                "url": url,
                "versionStyle": p.get("versionStyle", style),
                "aliases": p["keys"][1:],
                "source": f"auto:{brand}",
            }

    changed = json.dumps(plugins, sort_keys=True) != before
    if changed:
        doc["schema"] = 1
        doc["updated"] = datetime.date.today().isoformat()
    if changed and not dry_run:
        with open(list_file, "w") as f:
            f.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    return changed, failures, notes, doc


def check_readers():
    """Runs every reader against the live sites and prints what it finds (commits nothing).
    Used on pull requests to prove each brand's page can still be read."""
    bad = 0
    for brand, (reader, _, _) in READERS.items():
        try:
            found = reader(fetch)
        except Exception as e:
            print(f"FAILED {brand}: {e}")
            bad += 1
            continue
        valid = {k: v for k, v in found.items() if VALID_VERSION.match(v)}
        print(f"{'ok' if valid else 'FAILED'} {brand}: {len(valid)} version(s)")
        for k in sorted(valid):
            print(f"    {k}: {valid[k]}")
        bad += 0 if valid else 1
    sys.exit(1 if bad else 0)


def main():
    if "--check-readers" in sys.argv:
        check_readers()
    dry = "--dry-run" in sys.argv
    changed, failures, notes, doc = run(dry_run=dry)
    auto = {k: v["latest"] for k, v in doc["plugins"].items() if str(v.get("source", "")).startswith("auto:")}
    print(f"{len(auto)} auto-managed entries; changed={changed}; dry_run={dry}")
    for k in sorted(auto):
        print(f"  {k}: {auto[k]}")
    for n in notes:
        print("note:", n)
    for x in failures:
        print("FAILED:", x)
    if failures:
        with open(FAILURES_FILE, "w") as f:
            f.write("\n".join(failures) + "\n")
    elif os.path.exists(FAILURES_FILE):
        os.remove(FAILURES_FILE)


if __name__ == "__main__":
    main()

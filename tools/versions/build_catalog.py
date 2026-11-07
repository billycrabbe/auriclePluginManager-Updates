"""Builds catalog.json (which installed plugins each brand reader covers, and the keys the
Plugin Manager matches them by) from the Plugin Manager's own scan.

  python tools/versions/build_catalog.py path/to/auricle_plugin_cache_v3.xml

The scan lives at ~/Library/Application Support/Auricle/auricle_plugin_cache_v3.xml.
Re-run it after installing more plugins from a covered brand; existing entries are kept.
Keys match PluginUpdateChecker::keysFor: the bundle id, and "manufacturer:name", lower-cased.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_FILE = os.path.join(HERE, "catalog.json")

BRANDS = {  # brand id -> (manufacturer contains, bundle id prefixes)
    "fabfilter": ("fabfilter", ("com.fabfilter.",)),
    "u-he": ("u-he", ("com.u-he.",)),
    "valhalla": ("valhalla", ("com.valhalladsp.",)),
    "kilohearts": ("kilohearts", ("com.kilohearts.",)),
    "soundtoys": ("soundtoys", ("com.soundtoys.",)),
}


def brand_of(manufacturer, bundle_id):
    m, b = manufacturer.lower(), bundle_id.lower()
    for brand, (word, prefixes) in BRANDS.items():
        if word in m or b.startswith(prefixes):
            return brand
    return None


def main(cache_path):
    sys.path.insert(0, HERE)
    from update import norm

    root = ET.parse(cache_path).getroot()
    groups = {}
    for e in root:
        a = e.attrib
        if a.get("shellChild", "false").lower() in ("1", "true"):
            continue
        name, mfr, bid = a.get("name", "").strip(), a.get("manufacturer", "").strip(), a.get("bundleId", "").strip()
        brand = brand_of(mfr, bid)
        if not brand or not name:
            continue
        g = groups.setdefault((brand, norm(name)), {"brand": brand, "product": name, "bundleIds": [], "aliases": [], "installed": set()})
        if bid and bid.lower() not in g["bundleIds"]:
            g["bundleIds"].append(bid.lower())
        alias = f"{mfr.lower()}:{name.lower()}"
        if mfr and alias not in g["aliases"]:
            g["aliases"].append(alias)
        if a.get("version"):
            g["installed"].add(a["version"])

    existing = []
    if os.path.exists(CATALOG_FILE):
        existing = json.load(open(CATALOG_FILE))["products"]
    seen = {(p["brand"], norm(p["product"])) for p in existing}
    added = 0
    for (brand, n), g in sorted(groups.items()):
        if (brand, n) in seen:
            continue
        keys = g["bundleIds"] + [a for a in g["aliases"] if a not in g["bundleIds"]]
        existing.append({"brand": brand, "product": g["product"], "keys": keys,
                         "installedWhenAdded": sorted(g["installed"])})
        added += 1
    existing.sort(key=lambda p: (p["brand"], p["product"].lower()))
    with open(CATALOG_FILE, "w") as f:
        f.write(json.dumps({"products": existing}, indent=2, ensure_ascii=False) + "\n")
    print(f"catalog: {len(existing)} products ({added} new)")
    for p in existing:
        print(f"  {p['brand']:<11} {p['product']:<32} installed {', '.join(p.get('installedWhenAdded', [])) or '?'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])

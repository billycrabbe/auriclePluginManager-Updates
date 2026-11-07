"""Brand readers: each turns a brand's public web page into {product name: latest version}.

A reader only reads; it never decides what gets published. update.py validates every value
and keeps the last good version when a reader fails or returns something odd.

To add a brand: write a function that takes `fetch` (url -> html text) and returns
{product: version}, add it to READERS, then run build_catalog.py so the brand's plugins
get keys in catalog.json.
"""
import html
import re

VERSION = r"([0-9]+(?:\.[0-9]+){1,3})"


def _clean(text):
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def fabfilter(fetch):
    """fabfilter.com/download lists every current plug-in with its version and date."""
    page = fetch("https://www.fabfilter.com/download")
    found = {}
    for m in re.finditer(
        r"<h2[^>]*>\s*Download FabFilter ([^<]+?)\s*</h2>\s*<p>.{0,300}?<br>\s*" + VERSION + r"\s*&mdash;",
        page, re.S):
        found["FabFilter " + _clean(m.group(1))] = m.group(2)
    return found


def uhe(fetch):
    """u-he.com/products shows "Downloads (vX.Y.Z)" inside each product card."""
    page = fetch("https://u-he.com/products/")
    found = {}
    for card in re.split(r"<article ", page)[1:]:
        name = re.search(r'<img [^>]*alt=(?:"([^"]+)"|([^\s>]+))', card)
        ver = re.search(r"Downloads \(v" + VERSION + r"\)", card)
        if name and ver:
            found[_clean(name.group(1) or name.group(2))] = ver.group(1)
    return found


VALHALLA_PAGES = {
    "ValhallaVintageVerb": "https://valhalladsp.com/shop/reverb/valhalla-vintage-verb/",
    "ValhallaFutureVerb": "https://valhalladsp.com/shop/reverb/valhallafutureverb/",
    "ValhallaDelay": "https://valhalladsp.com/shop/delay/valhalladelay/",
    "ValhallaRoom": "https://valhalladsp.com/shop/reverb/valhalla-room/",
    "ValhallaPlate": "https://valhalladsp.com/shop/reverb/valhalla-plate/",
    "ValhallaShimmer": "https://valhalladsp.com/shop/reverb/valhalla-shimmer/",
    "ValhallaUberMod": "https://valhalladsp.com/shop/delay/valhalla-uber-mod/",
    "ValhallaFreqEcho": "https://valhalladsp.com/shop/delay/valhalla-freq-echo/",
    "ValhallaSpaceModulator": "https://valhalladsp.com/shop/modulation/valhalla-space-modulator/",
    "ValhallaSupermassive": "https://valhalladsp.com/shop/reverb/valhalla-supermassive/",
}


def valhalla(fetch):
    """Each Valhalla product page says "Current Version: X.Y.Z" (or per-OS versions)."""
    found = {}
    for name, url in VALHALLA_PAGES.items():
        page = fetch(url)
        m = re.search(r"Current Version:\s*" + VERSION, page)
        if m:
            found[name] = m.group(1)
            continue
        # Some pages list Mac and Windows separately ("Version 1.3.0 (Mac)"). The list holds one
        # version for both, so take the lower: it can never announce an update that isn't there.
        per_os = re.findall(r"Version\s+" + VERSION + r"\s*\((?:Mac|Windows)\)", page)
        if per_os:
            found[name] = min(per_os, key=lambda v: tuple(int(x) for x in v.split(".")))
    return found


def kilohearts(fetch):
    """All Kilohearts plugins share one version: the newest entry in the changelog."""
    page = fetch("https://kilohearts.com/download")
    # Each changelog entry is <section id="2.4.6">; the newest comes first.
    m = re.search(r'<section id="' + VERSION + r'"', page)
    return {"*": m.group(1)} if m else {}


def soundtoys(fetch):
    """All Soundtoys 5 plug-ins share one version: the newest entry in the release log."""
    page = fetch("https://www.soundtoys.com/release-log/")
    m = re.search(r"Soundtoys " + VERSION + r" Update", page)
    return {"*": m.group(1)} if m else {}


# brand id -> (reader, page users are sent to for the update, how versions compare)
READERS = {
    "fabfilter": (fabfilter, "https://www.fabfilter.com/download", "semver"),
    "u-he": (uhe, "https://u-he.com/products/", "semver"),
    "valhalla": (valhalla, "https://valhalladsp.com/shop/", "semver"),
    "kilohearts": (kilohearts, "https://kilohearts.com/download", "semver"),
    "soundtoys": (soundtoys, "https://www.soundtoys.com/release-log/", "semver"),
}

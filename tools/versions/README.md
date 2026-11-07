# Weekly plugin version check

Keeps `plugin-versions.json` current for the brands below, so the auricle Plugin Manager can
show "update available" for third-party plugins too. Runs every Monday via GitHub Actions
(`.github/workflows/update-plugin-versions.yml`); you can also run it from the Actions tab
(dry run by default).

| Brand | Source | Notes |
|---|---|---|
| FabFilter | fabfilter.com/download | per plugin |
| u-he | u-he.com/products | per plugin |
| Valhalla | each product page | per plugin; where Mac/Windows differ, the lower is used |
| Kilohearts | kilohearts.com/download changelog | one version for all plugins |
| Soundtoys | soundtoys.com/release-log | one version for all plugins |

Not covered: Waves (Waves Central handles it; versions are per bundle), Xfer (no public
version), and brands whose versions sit behind a login (NI, Arturia, iZotope).

**Safety:** only entries the job created (`"source": "auto:…"`) are ever changed, so the auricle
entries are never touched; versions are validated and never lowered; a brand that fails keeps
its last good versions and opens a GitHub issue.

**Covering more of your plugins:** run
`python3 tools/versions/build_catalog.py ~/Library/Application\ Support/Auricle/auricle_plugin_cache_v3.xml`
after installing plugins from a covered brand, then commit `catalog.json`.

**Adding a brand:** add a reader to `readers.py` (+ a fixture and test), add it to `READERS`
and `BRANDS` in `build_catalog.py`, then rebuild the catalog.

Tests: `python3 -m unittest discover -s tools/versions/tests -v`

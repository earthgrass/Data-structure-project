# BJUT offline map data

© OpenStreetMap contributors. This folder's `source.osm`, derived `network.json`
and `campus-network.json`
are OpenStreetMap data under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/),
**not** the project's code MIT license. Attribution and license information:
<https://www.openstreetmap.org/copyright>.

- Source: <https://api.openstreetmap.org/api/0.6/map?bbox=116.465,39.865,116.495,39.885>
- Retrieved: 2026-11-08; WGS84 bbox 116.465–116.495 E, 39.865–39.885 N.
- Exact extract preserved as `source.osm`; SHA-256 in `network.json.provenance`.
- `build-config.json` contains filtering, default speeds, simulated base locations and pool size.
- Rebuild with `PYTHONPATH=src python -B scripts/build_bjut_map.py`.
- Campus profile: `PYTHONPATH=src python -B scripts/build_bjut_map.py campus-config.json`.
  The campus data preserves the original roads, adding source-referenced service
  anchors for dormitories, teaching buildings, libraries, the swimming-pool-side
  parcel station and four gate lockers. Cabinet/station locations are approximate
  references based on the user's campus knowledge, not surveyed cabinet coordinates.
- No API token, external tile service, routing service or startup download is used.
- Binary text attributes preserve exact extract bytes across Windows checkouts.

Buildings, roads and land polygons are geographic reference data. Simulated business
facilities and pickup points do not imply real warehouses, customers, access permission
or commercial affiliations. No live traffic data is included.

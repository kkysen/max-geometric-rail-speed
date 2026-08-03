#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "geopandas",
#     "pyogrio",
#     "shapely",
#     "pyproj",
# ]
# ///
"""Build the track geometry + stations input for railway_speed.py from the raw
MTA DOS Track LRS geodatabase and MTA Subway Stations dataset (see fetch_data.py).

Route: Coney Island-Stillwell Av -> Times Sq-42 St, the Q train's physical path
(Brighton Line, Manhattan Bridge south tracks, Broadway Express tracks).

DOS_Track_Network's `BMT-A-3` record (Division BMT, Section A = the historical
"Broadway Brighton" trunk, Track 3) is a MultiLineString with exactly two parts:

  part0 (~18,497 ft): Canal St -> 34 St -> Times Sq -> ~57 St-7 Av (Manhattan)
  part1 (~56,060 ft): Coney Island-Stillwell Av -> ... -> DeKalb Av (Brooklyn)

Every station projects onto its expected part with an offset of a few feet to
a few hundred feet -- except the ~1 mile DeKalb Ave interlocking / Manhattan
Bridge crossing itself, which sits in the gap between the two parts (BMT-A's
own Track 3 designation doesn't cover the interlocking throat; it becomes a
different RouteId there -- see the LRS overview PDF). No single connecting
RouteId in this dataset fully bridges that gap (checked BMT-F/BMT-B/BMT-H/
IRT-MM candidates: closest partial match left a ~5,000 ft remainder in the
wrong direction). That short stretch is filled with a straight-line bridge
here -- see README "Known limitations".
"""

import json
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Point
from shapely.ops import substring

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"

GDB = RAW / "Subways_Track_LRS.gdb"
STATIONS_JSON = RAW / "mta_subway_stations.json"
TRACK_ID = "BMT-A-3"

STATION_ORDER = [
    "Coney Island-Stillwell Av", "W 8 St-NY Aquarium", "Ocean Pkwy", "Brighton Beach",
    "Sheepshead Bay", "Neck Rd", "Avenue U", "Kings Hwy", "Avenue M", "Avenue J",
    "Avenue H", "Newkirk Plaza", "Cortelyou Rd", "Beverley Rd", "Church Av",
    "Parkside Av", "Prospect Park", "7 Av", "Atlantic Av-Barclays Ctr", "DeKalb Av",
    "Canal St", "14 St-Union Sq", "34 St-Herald Sq", "Times Sq-42 St",
]
Q_LINES = {"Broadway - Brighton", "Manhattan Bridge", "Sea Beach / West End / Culver / Brighton"}

# Brighton EXPRESS (not local): the real B train's stopping pattern per
# Wikipedia's BMT Brighton Line article -- Parkside Av, Beverley Rd,
# Cortelyou Rd, Avenue H, Avenue J, Avenue M, Avenue U, and Neck Rd are
# local-only; DeKalb Av, Atlantic Av-Barclays Ctr, 7 Av, Prospect Park,
# Church Av, Newkirk Plaza, Kings Hwy, Sheepshead Bay, and Brighton Beach
# are express stops. The real B terminates at Brighton Beach and never runs
# to Ocean Pkwy/W 8 St/Coney Island at all, but those three have
# express-capable platforms, so this route (which needs a Coney Island
# origin) treats them as express stops -- extending the real B pattern
# south, not itself sourced from it.
EXPRESS_SKIP = {
    "Parkside Av", "Beverley Rd", "Cortelyou Rd", "Avenue H", "Avenue J",
    "Avenue M", "Avenue U", "Neck Rd",
}


def load_stations() -> list[dict]:
    raw = json.loads(STATIONS_JSON.read_text())
    q = [s for s in raw if "Q" in s.get("daytime_routes", "").split() and s["line"] in Q_LINES]
    by_name = {s["stop_name"]: s for s in q}
    missing = [n for n in STATION_ORDER if n not in by_name]
    if missing:
        raise SystemExit(f"Station(s) not found in MTA dataset: {missing}")
    return [by_name[n] for n in STATION_ORDER]


def main() -> None:
    stations = load_stations()
    stations_gdf = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(
            [float(s["gtfs_longitude"]) for s in stations],
            [float(s["gtfs_latitude"]) for s in stations],
        ),
        crs=4326,
    ).to_crs(2263)
    print(f"[1/4] {len(stations)} Q stations, Coney Island-Stillwell Av -> Times Sq-42 St")

    net = gpd.read_file(GDB, layer="DOS_Track_Network").to_crs(2263)
    geom = net.loc[net["RouteId"] == TRACK_ID, "geometry"].iloc[0]
    part_manhattan, part_brooklyn = list(geom.geoms)
    print(f"[2/4] {TRACK_ID}: Manhattan part {part_manhattan.length:.0f} ft, "
          f"Brooklyn part {part_brooklyn.length:.0f} ft")

    times_sq = stations_gdf.geometry.iloc[-1]
    chain_times_sq = part_manhattan.project(times_sq)
    offset_times_sq = part_manhattan.distance(times_sq)
    manhattan_piece = substring(part_manhattan, chain_times_sq, part_manhattan.length)
    manhattan_coords = list(reversed(manhattan_piece.coords))  # Canal -> Times Sq

    brooklyn_coords = list(reversed(part_brooklyn.coords))  # Coney Island -> DeKalb

    bridge_gap_ft = Point(brooklyn_coords[-1][:2]).distance(Point(manhattan_coords[0][:2]))
    print(f"[3/4] Times Sq clip offset {offset_times_sq:.0f} ft; "
          f"straight-line bridge across DeKalb Ave/Manhattan Bridge gap: {bridge_gap_ft:.0f} ft "
          f"({bridge_gap_ft / 5280:.2f} mi)")

    coords_2263 = [(x, y) for x, y, *_ in brooklyn_coords] + \
                  [(x, y) for x, y, *_ in manhattan_coords]
    route_2263 = LineString(coords_2263)
    route_4326 = gpd.GeoSeries([route_2263], crs=2263).to_crs(4326).iloc[0]
    print(f"[4/4] Assembled route: {len(coords_2263)} vertices, "
          f"{route_2263.length / 5280:.2f} mi ({route_2263.length * 0.3048 / 1000:.2f} km)")

    offsets_m = []
    for s, pt in zip(stations, stations_gdf.geometry):
        offsets_m.append(route_2263.distance(pt) * 0.3048)
    for s, off in zip(stations, offsets_m):
        if off > 100:
            print(f"  {s['stop_name']:<28} offset {off:>6.0f} m")
    print(f"  Max station-to-track offset: {max(offsets_m):.0f} m "
          f"(worst case is expected at the bridged gap)")

    OUT.mkdir(parents=True, exist_ok=True)
    track_path = OUT / "track_coney_island_times_sq.geojson"
    track_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "source": "MTA DOS Track Linear Referencing System (LRS), data.ny.gov dyuj-5if7, "
                           f"RouteId {TRACK_ID}",
                "route": "Coney Island-Stillwell Av to Times Sq-42 St via Brighton Line, "
                         "Manhattan Bridge, Broadway Express",
                "note": f"~{bridge_gap_ft * 0.3048:.0f} m straight-line bridge across the "
                        "DeKalb Ave interlocking / Manhattan Bridge crossing -- see README",
            },
            "geometry": {"type": "LineString", "coordinates": list(route_4326.coords)},
        }],
    }, indent=2))
    print(f"\n  Track:    {track_path}")

    stations_path = OUT / "stations_coney_island_times_sq.csv"
    with open(stations_path, "w") as f:
        f.write("name,lat,lon,stop\n")
        for s in stations:
            stop = 0 if s["stop_name"] in EXPRESS_SKIP else 1
            f.write(f"{s['stop_name']},{s['gtfs_latitude']},{s['gtfs_longitude']},{stop}\n")
    print(f"  Stations: {stations_path} (Brighton EXPRESS: skips {sorted(EXPRESS_SKIP)})")


if __name__ == "__main__":
    main()

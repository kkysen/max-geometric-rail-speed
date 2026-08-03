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
"""Build the track geometry + stations input for rail_curvature_timetable.py,
from the raw MTA DOS Track LRS geodatabase and MTA Subway Stations dataset
(see fetch_data.py). Builds three routes, all through the Q/B/D-family
DeKalb Ave interlocking:

  coney_island_times_sq  Coney Island-Stillwell Av -> Times Sq-42 St
                          (Brighton Express, Manhattan Bridge, Broadway Express)
  dekalb_times_sq         DeKalb Av -> Times Sq-42 St
                          (Manhattan Bridge, Broadway Express)
  dekalb_bryant_park      DeKalb Av -> 42 St-Bryant Pk
                          (Chrystie St Connection, 6th Ave Express)

DOS_Track_Network's `BMT-A-3` record (Division BMT, Section A = the historical
"Broadway Brighton" trunk, Track 3) is a MultiLineString with exactly two parts:

  part0 (~18,497 ft): Canal St -> 34 St -> Times Sq -> ~57 St-7 Av (Manhattan)
  part1 (~56,060 ft): Coney Island-Stillwell Av -> ... -> DeKalb Av (Brooklyn)

`IND-B-3` (Division IND, Section B = "6th Av - Culver") is also two parts, one
of them (also ~26,163 ft) covering Grand St -> ... -> 42 St-Bryant Pk -> ~57
St (Manhattan); the other part is the unrelated Culver Line in Brooklyn.

Every station projects onto its expected part with an offset of a few feet to
a few hundred feet -- except DeKalb Av itself, which is ~6,500 ft (its own
closest point on either part1) from where BMT-A-3's Brooklyn part and
IND-B-3's Manhattan part both *start*: both parts' coords[0] are the exact
same point (verified: 0.0 ft apart), the DeKalb Ave interlocking throat where
the Broadway route (Manhattan Bridge south tracks) and the 6th Ave route
(Chrystie St Connection, Manhattan Bridge north tracks) diverge. That ~6,500
ft of BMT-A-3 part1 between the DeKalb Av platform and that shared node is
real interlocking-throat trackage common to both routes, so both reuse it.

From that shared node, BMT-A-3's Manhattan part is a further ~1.05 mile real
gap from IND-B-3's part1 endpoint continuing north into Manhattan -- the
Manhattan Bridge crossing (south tracks) plus DeKalb throat isn't covered by
any single connecting RouteId in this dataset (checked BMT-F/BMT-B/BMT-H/
IRT-MM candidates: closest partial match left a ~5,000 ft remainder in the
wrong direction), so it's filled with a straight-line bridge. IND-B-3's own
part1, by contrast, has real (if coarse, ~11 vertices over that span)
geometry the entire way from the shared node through Grand St and beyond --
no bridge needed for the 6th Ave route. See README "Known limitations".
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

BROADWAY_BRIGHTON = "BMT-A-3"
SIXTH_AVE = "IND-B-3"

Q_LINES = {"Broadway - Brighton", "Manhattan Bridge", "Sea Beach / West End / Culver / Brighton"}
BD_LINES = {"Broadway - Brighton", "6th Av - Culver"}

# Brighton EXPRESS (not local): the real B train's stopping pattern per
# Wikipedia's BMT Brighton Line article -- Parkside Av, Beverley Rd,
# Cortelyou Rd, Avenue H, Avenue J, Avenue M, Avenue U, and Neck Rd are
# local-only; DeKalb Av, Atlantic Av-Barclays Ctr, 7 Av, Prospect Park,
# Church Av, Newkirk Plaza, Kings Hwy, Sheepshead Bay, and Brighton Beach
# are express stops. The real B terminates at Brighton Beach and never runs
# to Ocean Pkwy/W 8 St/Coney Island at all, but those three have
# express-capable platforms, so this route (which needs a Coney Island
# origin) treats them as express stops too -- extending the real B pattern
# south, not itself sourced from it.
BRIGHTON_EXPRESS_SKIP = {
    "Parkside Av", "Beverley Rd", "Cortelyou Rd", "Avenue H", "Avenue J",
    "Avenue M", "Avenue U", "Neck Rd",
}


def load_stations() -> list[dict]:
    return json.loads(STATIONS_JSON.read_text())


def station_lookup(raw: list[dict], names_lines: list[tuple[str, str]]) -> list[dict]:
    by_key = {(s["stop_name"], s["line"]): s for s in raw}
    missing = [nl for nl in names_lines if nl not in by_key]
    if missing:
        raise SystemExit(f"Station(s) not found in MTA dataset: {missing}")
    return [by_key[nl] for nl in names_lines]


def stations_gdf(stations: list[dict]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(
            [float(s["gtfs_longitude"]) for s in stations],
            [float(s["gtfs_latitude"]) for s in stations],
        ),
        crs=4326,
    ).to_crs(2263)


def clip_dir(line, chain_a: float, chain_b: float) -> list[tuple[float, float]]:
    """Coords of `line` between the two chainages, ordered chain_a -> chain_b."""
    lo, hi = sorted((chain_a, chain_b))
    piece = substring(line, lo, hi)
    coords = [(x, y) for x, y, *_ in piece.coords]
    return list(reversed(coords)) if chain_a > chain_b else coords


def stitch(*pieces: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Concatenate coordinate lists, dropping a duplicate point at each seam."""
    out = list(pieces[0])
    for piece in pieces[1:]:
        if out and piece and Point(out[-1]).distance(Point(piece[0])) < 0.1:
            piece = piece[1:]
        out.extend(piece)
    return out


def write_route(name: str, label: str, coords_2263: list[tuple[float, float]],
                 stations: list[dict], express_skip: set[str], source_note: str) -> LineString:
    route_2263 = LineString(coords_2263)
    route_4326 = gpd.GeoSeries([route_2263], crs=2263).to_crs(4326).iloc[0]
    print(f"  Assembled: {len(coords_2263)} vertices, {route_2263.length / 5280:.2f} mi "
          f"({route_2263.length * 0.3048 / 1000:.2f} km)")

    stgdf = stations_gdf(stations)
    offsets_m = [route_2263.distance(pt) * 0.3048 for pt in stgdf.geometry]
    for s, off in zip(stations, offsets_m):
        if off > 100:
            print(f"    {s['stop_name']:<28} offset {off:>6.0f} m")
    print(f"  Max station-to-track offset: {max(offsets_m):.0f} m")

    OUT.mkdir(parents=True, exist_ok=True)
    track_path = OUT / f"track_{name}.geojson"
    track_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"source": source_note, "route": label},
            "geometry": {"type": "LineString", "coordinates": list(route_4326.coords)},
        }],
    }, indent=2))

    stations_path = OUT / f"stations_{name}.csv"
    with open(stations_path, "w") as f:
        f.write("name,lat,lon,stop\n")
        for s in stations:
            stop = 0 if s["stop_name"] in express_skip else 1
            f.write(f"{s['stop_name']},{s['gtfs_latitude']},{s['gtfs_longitude']},{stop}\n")
    print(f"  Track:    {track_path}")
    print(f"  Stations: {stations_path}"
          + (f" (skips {sorted(express_skip)})" if express_skip else ""))
    return route_2263


def write_grade_csv(name: str, breakpoints: list[tuple[float, float]], comment: str) -> None:
    path = OUT / f"grade_markers_{name}.csv"
    with open(path, "w") as f:
        f.write(comment)
        f.write("chainage_km,grade_pct\n")
        for km, pct in breakpoints:
            f.write(f"{km:.3f},{pct}\n")
    print(f"  Grade:    {path}")


def main() -> None:
    raw_stations = load_stations()
    net = gpd.read_file(GDB, layer="DOS_Track_Network").to_crs(2263)
    bb_geom = net.loc[net["RouteId"] == BROADWAY_BRIGHTON, "geometry"].iloc[0]
    bb_manhattan, bb_brooklyn = list(bb_geom.geoms)
    sa_geom = net.loc[net["RouteId"] == SIXTH_AVE, "geometry"].iloc[0]
    sa_manhattan = max(list(sa_geom.geoms), key=lambda p: p.length)  # the 6th Ave part, not Culver

    bb_source = (f"MTA DOS Track Linear Referencing System (LRS), data.ny.gov dyuj-5if7, "
                 f"RouteId {BROADWAY_BRIGHTON}")
    sa_source = (f"MTA DOS Track Linear Referencing System (LRS), data.ny.gov dyuj-5if7, "
                 f"RouteId {SIXTH_AVE}")

    # ------------------------------------------------------------------
    # Route: Coney Island-Stillwell Av -> Times Sq-42 St
    # ------------------------------------------------------------------
    print("\n=== coney_island_times_sq ===")
    ci_order = [
        ("Coney Island-Stillwell Av", "Sea Beach / West End / Culver / Brighton"),
        ("W 8 St-NY Aquarium", "Broadway - Brighton"), ("Ocean Pkwy", "Broadway - Brighton"),
        ("Brighton Beach", "Broadway - Brighton"), ("Sheepshead Bay", "Broadway - Brighton"),
        ("Neck Rd", "Broadway - Brighton"), ("Avenue U", "Broadway - Brighton"),
        ("Kings Hwy", "Broadway - Brighton"), ("Avenue M", "Broadway - Brighton"),
        ("Avenue J", "Broadway - Brighton"), ("Avenue H", "Broadway - Brighton"),
        ("Newkirk Plaza", "Broadway - Brighton"), ("Cortelyou Rd", "Broadway - Brighton"),
        ("Beverley Rd", "Broadway - Brighton"), ("Church Av", "Broadway - Brighton"),
        ("Parkside Av", "Broadway - Brighton"), ("Prospect Park", "Broadway - Brighton"),
        ("7 Av", "Broadway - Brighton"), ("Atlantic Av-Barclays Ctr", "Broadway - Brighton"),
        ("DeKalb Av", "Broadway - Brighton"), ("Canal St", "Manhattan Bridge"),
        ("14 St-Union Sq", "Broadway - Brighton"), ("34 St-Herald Sq", "Broadway - Brighton"),
        ("Times Sq-42 St", "Broadway - Brighton"),
    ]
    ci_stations = station_lookup(raw_stations, ci_order)
    times_sq_pt = stations_gdf([ci_stations[-1]]).geometry.iloc[0]
    chain_times_sq = bb_manhattan.project(times_sq_pt)

    dekalb_throat = clip_dir(bb_brooklyn, bb_brooklyn.length, 0.0)  # full Brooklyn part, Coney->DeKalb node
    manhattan_to_times_sq = clip_dir(bb_manhattan, bb_manhattan.length, chain_times_sq)  # Canal->Times Sq
    bridge = [dekalb_throat[-1], manhattan_to_times_sq[0]]
    bridge_ft = Point(bridge[0]).distance(Point(bridge[1]))

    coords = stitch(dekalb_throat, bridge, manhattan_to_times_sq)
    chain_bridge_start = sum(
        Point(dekalb_throat[i]).distance(Point(dekalb_throat[i + 1]))
        for i in range(len(dekalb_throat) - 1)
    )
    chain_bridge_end = chain_bridge_start + bridge_ft
    print(f"  {bridge_ft:.0f} ft ({bridge_ft / 5280:.2f} mi) straight-line bridge across the "
          f"DeKalb Ave interlocking / Manhattan Bridge crossing")
    write_route(
        "coney_island_times_sq",
        "Coney Island-Stillwell Av to Times Sq-42 St via Brighton Express, "
        "Manhattan Bridge, Broadway Express",
        coords, ci_stations, BRIGHTON_EXPRESS_SKIP,
        f"{bb_source}; {bridge_ft * 0.3048:.0f} m straight-line bridge across the DeKalb Ave "
        "interlocking / Manhattan Bridge crossing -- see README",
    )
    _write_manhattan_bridge_grade("coney_island_times_sq", chain_bridge_start, chain_bridge_end)

    # ------------------------------------------------------------------
    # Route: DeKalb Av -> Times Sq-42 St
    # ------------------------------------------------------------------
    print("\n=== dekalb_times_sq ===")
    dt_order = ["DeKalb Av", "Canal St", "14 St-Union Sq", "34 St-Herald Sq", "Times Sq-42 St"]
    dt_stations = station_lookup(raw_stations, [
        (n, "Manhattan Bridge" if n == "Canal St" else "Broadway - Brighton") for n in dt_order
    ])
    dekalb_pt = stations_gdf([dt_stations[0]]).geometry.iloc[0]
    chain_dekalb = bb_brooklyn.project(dekalb_pt)

    dekalb_throat_short = clip_dir(bb_brooklyn, chain_dekalb, 0.0)  # DeKalb platform -> node
    coords = stitch(dekalb_throat_short, bridge, manhattan_to_times_sq)
    chain_bridge_start2 = sum(
        Point(dekalb_throat_short[i]).distance(Point(dekalb_throat_short[i + 1]))
        for i in range(len(dekalb_throat_short) - 1)
    )
    chain_bridge_end2 = chain_bridge_start2 + bridge_ft
    write_route(
        "dekalb_times_sq",
        "DeKalb Av to Times Sq-42 St via Manhattan Bridge, Broadway Express",
        coords, dt_stations, set(),
        f"{bb_source}; {bridge_ft * 0.3048:.0f} m straight-line bridge across the DeKalb Ave "
        "interlocking / Manhattan Bridge crossing -- see README",
    )
    _write_manhattan_bridge_grade("dekalb_times_sq", chain_bridge_start2, chain_bridge_end2)

    # ------------------------------------------------------------------
    # Route: DeKalb Av -> 42 St-Bryant Pk
    # ------------------------------------------------------------------
    print("\n=== dekalb_bryant_park ===")
    bp_order = ["DeKalb Av", "Grand St", "Broadway-Lafayette St", "W 4 St-Wash Sq",
                "34 St-Herald Sq", "42 St-Bryant Pk"]
    bp_stations = station_lookup(raw_stations, [
        (n, "Broadway - Brighton" if n == "DeKalb Av" else "6th Av - Culver") for n in bp_order
    ])
    bryant_pk_pt = stations_gdf([bp_stations[-1]]).geometry.iloc[0]
    chain_bryant_pk = sa_manhattan.project(bryant_pk_pt)

    sixth_ave_to_bryant_pk = clip_dir(sa_manhattan, 0.0, chain_bryant_pk)  # node -> Bryant Pk
    coords = stitch(dekalb_throat_short, sixth_ave_to_bryant_pk)
    chain_node2 = sum(
        Point(dekalb_throat_short[i]).distance(Point(dekalb_throat_short[i + 1]))
        for i in range(len(dekalb_throat_short) - 1)
    )
    print("  No bridge needed -- IND-B-3 has real geometry from the shared DeKalb node onward")
    write_route(
        "dekalb_bryant_park",
        "DeKalb Av to 42 St-Bryant Pk via Chrystie St Connection, 6th Ave Express",
        coords, bp_stations, set(), sa_source,
    )
    # Chrystie St Connection / Manhattan Bridge (north tracks) grade: subs.nyc const GRADES,
    # division B2 chain B ("IND Manhattan Bridge Connection" / "Track B3/B4 IND Manhattan
    # Bridge Connection"), grades 3.5-5.1%. Same simplified rise-then-fall hump treatment as
    # the Broadway route's bridge, over the shared node -> Grand St span (real curvature,
    # but no elevation data), zero point uncertain so placed by geography, not stationing.
    grand_st_chain = sa_manhattan.project(stations_gdf([bp_stations[1]]).geometry.iloc[0])
    _write_grade_hump(
        "dekalb_bryant_park", chain_node2, chain_node2 + grand_st_chain * 0.4,
        chain_node2 + grand_st_chain * 0.6, grade_pct=5.1,
        comment=(
            "# Grade breakpoints for the DeKalb Av -> 42 St-Bryant Pk route.\n"
            "# chainage_km,grade_pct: grade holds constant from this chainage until the next row.\n"
            "#\n"
            "# Source: subs.nyc (\"SUBWAYS_IO\", by Calcagno Maps / NYRTIG), "
            "https://map.subs.nyc/data.js,\n"
            "# const GRADES, division B2, chain B, route \"Route 112\" (\"IND Manhattan Bridge\n"
            "# Connection\" / \"Track B3/B4 IND Manhattan Bridge Connection\"): grade 3.5-5.1 at\n"
            "# markers 878+77/881+70/886+00/907+90. Simplified to a single representative +-5.1%\n"
            "# \"hump\" over the DeKalb Ave interlocking / Chrystie St Connection / Manhattan Bridge\n"
            "# (north tracks) span -- real curvature is available there (unlike the Broadway route's\n"
            "# bridge), but not elevation. Sign (climb then descend) inferred from the physical\n"
            "# profile, not encoded in the source. Everywhere else defaults to flat.\n"
        ),
    )


def _write_manhattan_bridge_grade(name: str, chain_start_ft: float, chain_end_ft: float) -> None:
    comment = (
        "# Grade breakpoints for this route.\n"
        "# chainage_km,grade_pct: grade holds constant from this chainage until the next row.\n"
        "#\n"
        "# Source: subs.nyc (\"SUBWAYS_IO\", by Calcagno Maps / NYRTIG), https://map.subs.nyc/data.js,\n"
        "# const GRADES, division B1, chains A and H, route \"MBX\" (\"Manhattan Bridge [c]rossing\"):\n"
        "# Manhattan Bridge North Approach (chain A, zero 57th & 7th): grade 4.82-5.40 at markers\n"
        "# 207+10/211+20/269+30/271+20/275+80. Manhattan Bridge South Approach (chain H, zero\n"
        "# Chambers): grade 4.97-5.30 at markers 35+40/39+12/41+50. Simplified here to a single\n"
        "# representative +-5.1% \"hump\" over this route's straight-line bridge span (no real\n"
        "# curvature/elevation there -- see README \"Known limitations\"). Sign (climb then descend)\n"
        "# is inferred from the known physical profile -- tunnel level in Brooklyn, up onto the\n"
        "# elevated bridge deck, back down into the Canal St tunnel in Manhattan -- not encoded in\n"
        "# the source, which gives magnitude only. Everywhere else on the route defaults to flat.\n"
    )
    mid = (chain_start_ft + chain_end_ft) / 2
    _write_grade_hump(name, chain_start_ft, mid, chain_end_ft, grade_pct=5.1, comment=comment)


def _write_grade_hump(name: str, chain_up_ft: float, chain_peak_ft: float, chain_down_ft: float,
                       grade_pct: float, comment: str) -> None:
    ft_to_km = 0.3048 / 1000
    write_grade_csv(name, [
        (0.0, 0.0),
        (chain_up_ft * ft_to_km, grade_pct),
        (chain_peak_ft * ft_to_km, -grade_pct),
        (chain_down_ft * ft_to_km, 0.0),
    ], comment)


if __name__ == "__main__":
    main()

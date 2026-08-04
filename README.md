# max-geometric-rail-speed

Exploring [Brendan Dawe's Railway Curvature & Timetable Generator](https://gist.github.com/BSDawe/52c5fd15202fee9912c7391dbf8352cd)
(described in [this article](https://cartoview.blogspot.com/2026/08/the-railway-curvature-timetabling-tool.html)),
applied to real NYC subway routes through the DeKalb Ave interlocking:

- **Coney Island-Stillwell Av to Times Sq-42 St**, via the Brighton Line (Express), Manhattan
  Bridge, and Broadway Express tracks -- the Q's physical path.
- **DeKalb Av to Times Sq-42 St**, via the Manhattan Bridge and Broadway Express tracks -- the
  Manhattan-only tail of the same route.
- **DeKalb Av to 42 St-Bryant Pk**, via the Chrystie St Connection and 6th Ave Express tracks --
  the B/D's physical path where it diverges from the Broadway route at DeKalb.

`rail_curvature_timetable.py` started as the **original, unmodified** gist script: a QGIS 3.28+
Python console script that computes track curvature from a centerline geometry, derives a
permissible-speed profile (cant + cant deficiency, EN 13803 reverse-curve transition limits), runs a
kinematic train-performance simulation over that profile, and produces a timetable, single-track
meet/loop analysis, and curve-by-curve time-loss ranking. It is licensed CC BY-NC 4.0 by Brendan Dawe;
see the script's own header for the full license text and terms. Used here for personal,
non-commercial, research purposes.

It has since been adapted in place to run standalone, outside QGIS: same curvature/speed/kinematics/
meet-loop/curve-ranking algorithm, but reading a GeoJSON track + CSV stations/grade instead of a QGIS
layer + DEM, and writing CSV only (no QGIS memory layers). The original, unmodified script is
preserved in this repo's first commit -- `git show 537968c:rail_curvature_timetable.py`, or `git log
-p -- rail_curvature_timetable.py` for the full diff.

## Usage

```sh
uv run scripts/fetch_data.py         # download raw MTA LRS geodatabase, MTA stations, R211 spec
unzip -o data/raw/Subways_Track_LRS.gdb.zip -d data/raw/
uv run scripts/prepare_route.py      # build all three routes' track/stations/grade files

uv run rail_curvature_timetable.py coney_island_times_sq   # or:
uv run rail_curvature_timetable.py dekalb_times_sq
uv run rail_curvature_timetable.py dekalb_bryant_park
```

The route argument is required -- it selects which of `prepare_route.py`'s prepared routes to run,
overriding `CONFIG["track_geojson"]`/`stations_csv`/`grade_csv`/`run_label`. Each writes
`output/<run_label>_*.csv`.

The Brooklyn leg of `coney_island_times_sq` models Brighton **Express** (the real B train's
stopping pattern, extended south to Coney Island since the B itself terminates at Brighton Beach):
skips Parkside Av, Beverley Rd, Cortelyou Rd, Avenue H, Avenue J, Avenue M, Avenue U, and Neck Rd.
`dekalb_times_sq` and `dekalb_bryant_park` are both already express-only end to end -- their station
lists are filtered to stations the real Broadway/6th Ave express services actually call at, so there
are no local-only stations to skip.

## Data sources

- **Track geometry**: [MTA DOS Track Linear Referencing System (LRS)](https://data.ny.gov/Transportation/MTA-DOS-Track-Linear-Referencing-System-LRS-/dyuj-5if7),
  published on `data.ny.gov`. `DOS_Track_Network`, `RouteId` `BMT-A-3` (Division BMT, Section A =
  the historical "Broadway Brighton" trunk, Track 3) for the Coney Island/DeKalb/Times Sq routes,
  and `IND-B-3` (Division IND, Section B = "6th Av - Culver" trunk, Track 3) for the Bryant Park route.
- **Station coordinates**: [MTA Subway Stations](https://data.ny.gov/Transportation/MTA-Subway-Stations/39hk-dx4f),
  published on `data.ny.gov`.
- **Grade data**: [subs.nyc](https://subs.nyc) ("SUBWAYS_IO", by Calcagno Maps / NYRTIG), a
  third-party hobbyist infrastructure database with point-based ruling-grade values
  (`https://map.subs.nyc/data.js`, `const GRADES`).
- **Rolling stock figures**: [NYCT R211 Technical Specification](https://web.archive.org/web/20230604084254/https://transitinnovation.org/wp-content/uploads/2019/12/R211%20Tech%20Spec.pdf)
  (Contract R34211) -- max speed, acceleration/deceleration rates, and car weight are read from the
  spec; power and tractive effort are back-calculated from those (the spec text extracted here
  didn't turn up an explicit total HP/kN figure), so treat those two as order-of-magnitude, not
  cited. See the comment above `CONFIG` in `rail_curvature_timetable.py` for the derivation.

## Known limitations

- Track curvature is derived from ~62 m-spaced engineering panel data, not a true as-built survey —
  tight curves are smoothed/approximate.
- `BMT-A-3`'s own geometry has a real ~1.05 mile gap spanning the DeKalb Ave interlocking and the
  Manhattan Bridge (south tracks) crossing itself (no single connecting `RouteId` in the LRS dataset
  bridges it cleanly -- checked `BMT-F`/`BMT-B`/`BMT-H`/`IRT-MM` candidates). `prepare_route.py` fills
  it with a straight line, so there's no real curvature over that stretch on the
  `coney_island_times_sq` and `dekalb_times_sq` routes. The grade CSV applies a simplified +/-5.1%
  "hump" there instead (see its header comment). `IND-B-3` (the `dekalb_bryant_park` route) doesn't
  have this problem -- it has real, if coarse, geometry the entire way across the Manhattan Bridge
  north tracks/Chrystie St Connection, no bridge needed -- but still has no elevation data there
  either, so the same kind of simplified grade "hump" is used for that span too.
- Grade elsewhere on all three routes defaults to flat; real grade data only exists at a few named
  points in the third-party source, not a continuous profile.
- Rolling-stock power/tractive-effort figures are back-calculated, not cited (see above).
- Output is explicitly "geometric potential," not a real achievable schedule (per the original
  script's own documented caveats: no signalling headway, civil speed restrictions, freight
  conflicts, etc.) -- these runs' end-to-end times are well under the real services' scheduled times
  for exactly that reason.

## Possible follow-ups

- `subs.nyc`'s database also has switch/interlocking data (`RELAY_INTERLOCKINGS`, `MASTER_TOWERS`)
  that could refine curvature right at interlockings, and might help close the Broadway route's
  DeKalb/Manhattan Bridge gap above with real geometry instead of a straight line.

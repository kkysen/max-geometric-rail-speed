# max-geometric-rail-speed

Exploring [Brendan Dawe's Railway Curvature & Timetable Generator](https://gist.github.com/BSDawe/52c5fd15202fee9912c7391dbf8352cd)
(described in [this article](https://cartoview.blogspot.com/2026/08/the-railway-curvature-timetabling-tool.html)),
applied to a real subway route: the Q train's physical path from Coney Island-Stillwell Av to
Times Sq-42 St via the Brighton Line, the Manhattan Bridge south tracks, and the Broadway Express
tracks.

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
uv run scripts/prepare_route.py      # build data/track_*.geojson + data/stations_*.csv + grade CSV
uv run rail_curvature_timetable.py   # run the model, write output/*.csv
```

The route modeled is Brighton **Express**, not local: it skips Beverley Rd, Cortelyou Rd, Avenue H,
and Avenue J (the 4 local-only stations on the 4-track section between Prospect Park and Newkirk
Plaza).

## Data sources

- **Track geometry**: [MTA DOS Track Linear Referencing System (LRS)](https://data.ny.gov/Transportation/MTA-DOS-Track-Linear-Referencing-System-LRS-/dyuj-5if7),
  published on `data.ny.gov`. `DOS_Track_Network`, `RouteId` `BMT-A-3` (Division BMT, Section A =
  the historical "Broadway Brighton" trunk, Track 3).
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
  Manhattan Bridge crossing itself (no single connecting `RouteId` in the LRS dataset bridges it
  cleanly -- checked `BMT-F`/`BMT-B`/`BMT-H`/`IRT-MM` candidates). `prepare_route.py` fills it with a
  straight line, so there's no real curvature or fine-grained grade over the Manhattan Bridge crossing
  itself. The grade CSV applies a simplified +/-5.1% "hump" there instead (see its header comment).
- Grade elsewhere on the route defaults to flat; real grade data only exists at a few named points in
  the third-party source, not a continuous profile.
- Rolling-stock power/tractive-effort figures are back-calculated, not cited (see above).
- Output is explicitly "geometric potential," not a real achievable schedule (per the original
  script's own documented caveats: no signalling headway, civil speed restrictions, freight
  conflicts, etc.) -- this run's ~34 min end-to-end is well under the real Q's scheduled time for
  exactly that reason.

## Possible follow-ups

- `subs.nyc`'s database also has switch/interlocking data (`RELAY_INTERLOCKINGS`, `MASTER_TOWERS`)
  that could refine curvature right at interlockings, and might help close the DeKalb/Manhattan
  Bridge gap above with real geometry instead of a straight line.

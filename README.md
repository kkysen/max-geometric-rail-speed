# max-geometric-rail-speed

Exploring [Brendan Dawe's Railway Curvature & Timetable Generator](https://gist.github.com/BSDawe/52c5fd15202fee9912c7391dbf8352cd)
(described in [this article](https://cartoview.blogspot.com/2026/08/the-railway-curvature-timetabling-tool.html)),
applied to a real subway route: the Q train's physical path from Coney Island-Stillwell Av to
Times Sq-42 St via the Brighton Line, the Manhattan Bridge south tracks, and the Broadway Express
tracks.

`rail_curvature_timetable.py` is the **original, unmodified** gist script: a QGIS 3.28+ Python
console script that computes track curvature from a centerline geometry, derives a permissible-speed
profile (cant + cant deficiency, EN 13803 reverse-curve transition limits), runs a kinematic
train-performance simulation over that profile, and produces a timetable, single-track meet/loop
analysis, and curve-by-curve time-loss ranking. It is licensed CC BY-NC 4.0 by Brendan Dawe; see the
script's own header for the full license text and terms. Used here for personal, non-commercial,
research purposes.

The rest of this repo adapts that script to run standalone (via `uv`, outside QGIS) against real
track geometry, station, and grade data for the route above. See the plan/commit history for the
data sources used and their limitations.

## Data sources

- **Track geometry**: [MTA DOS Track Linear Referencing System (LRS)](https://data.ny.gov/Transportation/MTA-DOS-Track-Linear-Referencing-System-LRS-/dyuj-5if7),
  published on `data.ny.gov`.
- **Station coordinates**: [MTA Subway Stations](https://data.ny.gov/Transportation/MTA-Subway-Stations/39hk-dx4f),
  published on `data.ny.gov`.
- **Grade data**: [subs.nyc](https://subs.nyc) ("SUBWAYS_IO", by Calcagno Maps / NYRTIG), a
  third-party hobbyist infrastructure database with point-based ruling-grade values.

## Known limitations

- Track curvature is derived from ~62 m-spaced engineering panel data, not a true as-built survey —
  tight curves are smoothed/approximate.
- Grade is a hand-mapped set of point ruling-grades from a third-party database, not a continuous
  profile.
- Output is explicitly "geometric potential," not a real achievable schedule (per the original
  script's own documented caveats: no signalling headway, civil speed restrictions, freight
  conflicts, etc.).

"""
Brendan Dawe's Railway Curvature & Timetable Generator  v5
===========================================
QGIS 3.28+ Python Console script.

(c) Brendan Dawe. Licensed CC BY-NC 4.0 (Attribution-NonCommercial):
free to use, share, and modify for personal, educational, or research
purposes with attribution. Full text:
https://creativecommons.org/licenses/by-nc/4.0/

If you'd like to use this as part of paid consulting, a commissioned
report, or your work at a transit agency, engineering firm, or similar
organization, please get in touch first -- I'm generally happy to say
yes, I just want to know it's happening. Hobbyists, students, and
enthusiasts: use it freely, no need to ask.


WHAT THIS DOES
--------------
You give it a railway centreline (any line layer in your QGIS project) and a
CSV of station locations. It works out how fast a train could physically run
over that alignment, and turns that into a timetable.

Concretely, it:

  1. Stitches the line features into one continuous route and measures it.
  2. Fits a smoothing spline and computes curvature along it.
  3. Converts curvature into a permissible speed at every point, using cant
     and cant deficiency, plus EN 13803 transition limits at reverse curves.
  4. Runs a train over that speed profile with real traction physics, in both
     directions, and produces arrival and departure times.
  5. Works out where opposing trains would meet, and therefore where passing
     loops must go.
  6. Ranks every curve by how many seconds it costs, so you can see which
     realignments would actually be worth building.

It is a tool for answering "what could this corridor do if rebuilt?", not for
reproducing an existing operator's timetable.


WHAT IT DOES NOT MODEL
----------------------
The run times it produces are the GEOMETRIC POTENTIAL of the right-of-way.
A real timetable on the same alignment will be slower, typically by 8-12%,
because none of the following are included:

  * Signalling headway and block occupancy
  * Civil speed restrictions through stations, junctions and turnouts
  * Level crossing approach speed limits
  * Temporary speed restrictions and track condition
  * Freight paths, and conflicts with them
  * Platform reoccupation and terminal constraints beyond a fixed turnaround

Treat the output as an upper bound, and as a way of comparing scenarios
against each other rather than as a schedule you could publish.


QUICK START
-----------
  1. Load your track centreline as a line layer in QGIS. Note its layer name.
  2. Make a stations CSV with columns: name, lat, lon
     Optionally add a "stop" column (1 = call, 0 = pass through).
     List the stations in route order.
  3. In the CONFIG block below, set at minimum:
        track_layer_name   your layer's name
        stations_csv       full path to the CSV
        chain_start        which end of the route to measure from
  4. Paste the whole script into the QGIS Python Console and run.

Nothing is written to disk unless you set output_dir. By default the script
runs in scratch mode: it adds three memory layers to your project and prints
everything to the console. Set output_dir to a real folder to also get CSVs.

The script validates your CONFIG before doing any work, so mistakes surface
in about a second rather than after a full run.


THE OUTPUT LAYERS
-----------------
  <label>_speed    the route, split into short segments, carrying permissible
                   speed, envelope speed in each direction, radius and grade.
                   Style this graduated on env_t1_kmh to see where the train
                   is actually slow.
  <label>_curves   one point per curve, carrying radius, permissible speed and
                   time_loss_s. Style graduated on loss_s: the big dots are
                   the curves worth spending money on.
  <label>_loops    where opposing trains meet, and therefore where passing
                   loops are needed. Includes a minimum usable loop length.


READING THE CONSOLE OUTPUT
--------------------------
Most of it is self-explanatory. Three things repay attention:

  Reverse-curve table. Where two curves bend opposite ways with a short
  straight between them, cant has to be ramped from one side to the other,
  and that takes distance. The "bind" column tells you which limit is doing
  the damage:
      dD/dt  rate of change of applied cant
      dI/dt  rate of change of cant deficiency
      dD/ds  cant gradient - not enough length to build the cant at all
  If dI/dt dominates, your alignment cannot usefully take cant and speed
  depends almost entirely on how much deficiency the stock will tolerate.
  Raising ed_mm will then do more for you than easing radii will.

  Curve time-loss ranking. Each curve is relaxed to line speed in turn and
  the leg is re-run, so loss_s is the time that curve actually costs, not a
  proxy. A long tail of 10-30 second curves means there is no single
  realignment worth doing; a short head of large values means there is.

  Loop table and fleet count. Loop count and fleet size are step functions of
  run time, so the script reports how many seconds you would need to save to
  drop to the next step down. That is usually the number that decides whether
  a given investment is worth anything.


KEY SETTINGS, AND THE ONES PEOPLE GET WRONG
-------------------------------------------
  cant_mm / ed_mm
      Applied cant and cant deficiency, in millimetres. Their sum sets
      permissible speed: R = 11.8 * V^2 / (cant + deficiency). Typical
      conventional practice is 150-180 cant and 100-150 deficiency. Tilting
      stock runs 250-300 deficiency.

  cant_base_m  --  LEAVE THIS AT 1.500
      This is EN 13803's 'e', the spacing between the two wheel-rail contact
      patches. It is NOT the track gauge, even though 1435 mm is sitting right
      there looking like the obvious value. Cant is an angle expressed against
      a 1500 mm reference base, so the cant figure you enter above is already
      defined on that base. Setting this to 1.435 mixes two reference bases in
      one equation and overstates every speed by 2.2%. The script refuses to
      run if you change it.

  xy_noise_m
      How much positional error you expect in your centreline, in metres. This
      drives the smoothing spline. Too low and the script differentiates your
      digitising wobble into imaginary sharp curves; too high and it smooths
      away real ones. If the console warns that smoothed minimum radius is far
      above raw minimum radius, raise this rather than touching curv_smooth_m.

  chain_start
      Which end of the route to start measuring from. Use "south" or "north"
      for north-south corridors and "west" or "east" for east-west ones.
      Getting it wrong is harmless - the script detects it from the station
      order and reverses - but setting it correctly avoids the extra pass.

  train_length_m
      A speed restriction applies until the whole train has cleared it, so
      restrictions extend one train length beyond the curve itself. Set to 0
      for a point-mass approximation.

  dem_layer_name
      Optional. Without a DEM every gradient is zero, which on any route with
      real topography is the largest single error in the result, and it makes
      the two directions come out artificially identical. Surface DEMs read
      hillsides rather than formation in cuttings and tunnels, so grades are
      clipped at dem_max_grade_pct and flagged.

  takt_min
      The service interval you want to run. This drives the whole meet and
      fleet analysis. On a symmetric clockface timetable, opposing trains
      cross at fixed points spaced half a takt apart in RUNNING TIME, which
      is why loops bunch together where the line is slow.


GRADE CONVENTION
----------------
  grade_pct > 0 = uphill in the Train 1 direction (increasing chainage).
  The sign is flipped automatically for Train 2.


CSV FORMAT
----------
  name,lat,lon,stop
  Victoria,48.4284,-123.3656,1
  Langford,48.4500,-123.5000,1
  Goldstream,48.4700,-123.5500,0

  The "stop" column is optional and defaults to 1. Terminals always count as
  stops regardless. Stations are projected onto the nearest point of the
  route; if the console reports an offset of more than 500 m, your coordinate
  is probably a town centre rather than a station site, and the resulting
  chainage will be wrong enough to move loop locations.


REQUIREMENTS
------------
  QGIS 3.28 or later, with numpy and scipy (both ship with QGIS).
  GDAL is used for local DEM files if present, with a slower QGIS
  identify-based fallback for web raster layers.
"""

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    # --- Input ---
    "track_layer_name": "MyTrack", #This is just the name in your layer list
    "stations_csv":     r"C:\path\to\stations.csv",
    "dem_layer_name":   None,

    # --- Output ---
    "output_dir":       None,   # None = scratch layers only, no files
    "run_label":        "MyRoute",

    # --- Track geometry ---
    "cant_mm":       180,
    "ed_mm":         120,             # Cant Deficiency 
    # EN 13803 'e': contact patch spacing, NOT track gauge. Do not set 1.435.
    "cant_base_m":   1.500,

    # --- Rolling stock ---
    "v_max_kmh":      160.0,
    "power_kw":      5200.0,
    "mass_tonnes":    200.0,
    "max_te_kn":      360.0,          # Maximum Tractive Effort (kN)
    "max_brake_kn":   280.0,
    "traction_type":  "emu",          # emu / dmu / loco
    "train_length_m": 200.0,

    # --- Comfort caps (passenger) ---
    "max_accel_ms2":  1.10,
    "max_decel_ms2":  1.10,

    # --- Grade ---
    "grade_pct":         0.0,
    "dem_smooth_m":    400.0,
    "dem_max_grade_pct": 3.0,

    # --- Schedule ---
    "dwell_s":       60.0,
    "recovery":      0.07,
    "dep_hhmm_t1":  "07:00",
    "dep_hhmm_t2":  "07:00",

    # --- Service pattern (for meets / fleet) ---
    "takt_min":         60,
    "turnaround_min":   15,
    "meet_phase_sweep": True,
    "loop_cluster_km":  1.5,
    "punctuality_s":    60.0,

    # --- Chain start ---
    "chain_start": "south",           # south / north / east / west

    # --- Geometry processing ---
    "resample_m":       20.0,
    "xy_noise_m":        3.0,         # expected digitising error -> spline s
    "curv_smooth_m":   100.0,         # curvature-space smoothing window
    "curve_thresh_m":  2000,
    "curve_min_len_m":  100,
    "spur_max_len_m": 2000.0,

    # --- Reverse curve / EN 13803 ---
    "rev_curve_qualify_r":  1000,
    "cant_rate_mms":        35.0,     # dD/dt
    "cant_def_rate_mms":    55.0,     # dI/dt
    "cant_gradient_mm_m":    2.5,     # dD/ds, 2.5 mm/m = 1:400

    # --- Analysis toggles ---
    "rank_curve_time_loss": True,
    "max_curves_ranked":    60,
}

# ============================================================
# SCRIPT
# ============================================================

import math, os, csv
import numpy as np
from scipy.interpolate import splprep, splev
from scipy.ndimage import uniform_filter1d, minimum_filter1d
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
    QgsPointXY, QgsField, QgsFields, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsCoordinateTransformContext, QgsRasterLayer,
)
from PyQt5.QtCore import QVariant

print("=" * 64)
print("Railway Timetable Generator  v5")
print("Written by Brendan Dawe -- CC BY-NC 4.0 (Attribution-NonCommercial)")
print("Free for personal, educational and research use. Professional or")
print("organizational use: please contact me first. See header for details.")
print("=" * 64)

G = 9.81
WARNINGS = []


# ------------------------------------------------------------
# 0. Config validation - fail fast, before any computation
# ------------------------------------------------------------
# Everything here used to be checked late: stations_csv at step 5, output_dir
# not until step 13. A typo cost the whole run, and makedirs(exist_ok=True)
# silently created placeholder trees like C:\path\to\output instead of
# complaining. Validate up front and refuse to start.

_PLACEHOLDERS = {
    "track_layer_name": {"MyTrack"},
    "stations_csv": {r"C:\path\to\stations.csv", "/path/to/stations.csv"},
    "output_dir": {r"C:\path\to\output", "/path/to/output"},
    "run_label": {"MyRoute"},
}

_errors = []

# Only inputs are fatal when left as placeholders. output_dir and run_label
# are handled below: an unset output_dir means scratch layers, not an error.
for _key in ("track_layer_name", "stations_csv"):
    if str(CONFIG.get(_key, "")).strip() in _PLACEHOLDERS[_key]:
        _errors.append(f"CONFIG['{_key}'] is still the placeholder "
                       f"{CONFIG[_key]!r} - set it to a real value")

_csv = CONFIG["stations_csv"]
if not os.path.isfile(_csv):
    _errors.append(f"stations_csv not found: {_csv}")
else:
    try:
        with open(_csv, newline="", encoding="utf-8-sig") as _fh:
            _hdr = next(csv.reader(_fh), [])
        _hdr = [h.strip().lower() for h in _hdr]
        _missing = [c for c in ("name", "lat", "lon") if c not in _hdr]
        if _missing:
            _errors.append(f"stations_csv missing column(s): {', '.join(_missing)}")
    except Exception as _exc:
        _errors.append(f"stations_csv unreadable: {_exc}")

_outdir = CONFIG.get("output_dir")
_outdir_str = str(_outdir).strip() if _outdir is not None else ""
WRITE_FILES = True

if (_outdir is None or _outdir_str == ""
        or _outdir_str in _PLACEHOLDERS["output_dir"]):
    # Scratch mode: memory layers only, nothing written to disk.
    WRITE_FILES = False
elif os.path.isdir(_outdir_str):
    if not os.access(_outdir_str, os.W_OK):
        _errors.append(f"output_dir is not writable: {_outdir_str}")
else:
    # A path was given but doesn't exist. Create one level only, and only if
    # the parent is real - a missing parent means the path is wrong, not that
    # a tree needs building.
    _parent = os.path.dirname(os.path.normpath(_outdir_str))
    if _parent and not os.path.isdir(_parent):
        _errors.append(f"output_dir parent does not exist: {_parent}\n"
                       f"      (refusing to create the full tree - check the path.\n"
                       f"       Set output_dir to None for scratch layers only.)")
    else:
        try:
            os.makedirs(_outdir_str)
            print(f"  Created output directory: {_outdir_str}")
        except Exception as _exc:
            _errors.append(f"could not create output_dir {_outdir_str}: {_exc}")

if not str(CONFIG.get("run_label", "")).strip():
    CONFIG["run_label"] = "Route"
_bad_chars = set('\\/:*?"<>|')
if _bad_chars & set(str(CONFIG["run_label"])):
    _errors.append(f"run_label contains illegal filename characters: "
                   f"{CONFIG['run_label']!r}")

if not QgsProject.instance().mapLayersByName(CONFIG["track_layer_name"]):
    _names = [l.name() for l in QgsProject.instance().mapLayers().values()]
    _errors.append(f"track layer '{CONFIG['track_layer_name']}' not in project.\n"
                   f"      Loaded layers: {', '.join(_names) if _names else '(none)'}")

if CONFIG.get("dem_layer_name"):
    if not QgsProject.instance().mapLayersByName(CONFIG["dem_layer_name"]):
        _errors.append(f"dem_layer_name '{CONFIG['dem_layer_name']}' not in project "
                       f"(set to None for a flat model)")

if abs(CONFIG["cant_base_m"] - 1.5) > 0.05:
    _errors.append(f"cant_base_m is {CONFIG['cant_base_m']} - expected ~1.500. "
                   f"This is EN 13803 'e' (contact patch spacing), NOT track gauge. "
                   f"Do not set it to 1.435.")

for _k in ("v_max_kmh", "power_kw", "mass_tonnes", "max_te_kn",
           "max_brake_kn", "takt_min"):
    if CONFIG.get(_k, 0) <= 0:
        _errors.append(f"CONFIG['{_k}'] must be positive")

class ConfigError(Exception):
    """Raised for invalid CONFIG. Deliberately NOT SystemExit: QGIS embeds
    Python in the application process, so a propagating SystemExit is read as
    a request to shut the interpreter down and takes QGIS with it."""


if _errors:
    _msg = ["", "CONFIGURATION ERRORS - nothing was run:", ""]
    for _e in _errors:
        _msg.append(f"  * {_e}")
    _msg += ["", "Fix the CONFIG block above and re-run.", ""]
    _text = "\n".join(_msg)
    print(_text)
    raise ConfigError(_text)

if WRITE_FILES:
    print(f"  Config OK -> {os.path.join(_outdir_str, CONFIG['run_label'])}_*.csv")
else:
    print("  Config OK -> SCRATCH MODE: memory layers only, no files written")
    print("               (set output_dir to a real folder to save CSVs)")


def warn(kind, msg):
    WARNINGS.append((kind, msg))
    print(f"  [!] {kind}: {msg}")


def hav(p1, p2):
    lo1, la1 = math.radians(p1[0]), math.radians(p1[1])
    lo2, la2 = math.radians(p2[0]), math.radians(p2[1])
    dlo = lo2 - lo1
    dla = la2 - la1
    a = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(max(0.0, a)))


# ------------------------------------------------------------
# 1. Load track
# ------------------------------------------------------------
print(f"\n[1/11] Loading track layer: {CONFIG['track_layer_name']}")
_layers = QgsProject.instance().mapLayersByName(CONFIG["track_layer_name"])
if not _layers:
    raise ValueError(f"Layer '{CONFIG['track_layer_name']}' not found.")
layer = _layers[0]

segments = []
for feat in layer.getFeatures():
    geom = feat.geometry()
    if geom is None:
        continue
    parts = (geom.asMultiPolyline()
             if QgsWkbTypes.isMultiType(geom.wkbType())
             else [geom.asPolyline()])
    for part in parts:
        pts = [(p.x(), p.y()) for p in part if p.x() != 0 or p.y() != 0]
        if len(pts) >= 2:
            L = sum(hav(pts[j], pts[j + 1]) for j in range(len(pts) - 1))
            segments.append({"points": pts, "len_m": L,
                             "start": pts[0], "end": pts[-1]})

print(f"  {len(segments)} segments, "
      f"{sum(len(s['points']) for s in segments)} vertices")


# ------------------------------------------------------------
# 2. Spur detection
# ------------------------------------------------------------
print("\n[2/11] Geometry QA")
CONN_TOL = 5.0


def endpoint_degree(idx, role, segs, tol):
    pt = segs[idx]["start"] if role == "start" else segs[idx]["end"]
    return sum(1 for j, s in enumerate(segs)
               if j != idx and (hav(pt, s["start"]) < tol or hav(pt, s["end"]) < tol))


spurs = []
for i, seg in enumerate(segments):
    cs = endpoint_degree(i, "start", segments, CONN_TOL)
    ce = endpoint_degree(i, "end", segments, CONN_TOL)
    if (cs == 0) != (ce == 0) and seg["len_m"] < CONFIG["spur_max_len_m"]:
        free = seg["start"] if cs == 0 else seg["end"]
        spurs.append({"idx": i, "len_m": round(seg["len_m"]), "free_end": free})

if spurs:
    print(f"  {len(spurs)} possible spur/yard segment(s):")
    for sp in spurs:
        lon, lat = sp["free_end"]
        print(f"    seg {sp['idx']:>4}  {sp['len_m']:>6} m  {lat:.5f}, {lon:.5f}")
    print("  -> filter in QGIS if they disturb chaining")
else:
    print("  No spurs detected.")


# ------------------------------------------------------------
# 3. Chain
# ------------------------------------------------------------
print(f"\n[3/11] Chaining (chain_start='{CONFIG['chain_start']}')")
_cs = CONFIG.get("chain_start", "south").lower()
if _cs == "south":
    _key = lambda f, r: (f["start"][1] if r == "start" else f["end"][1]); _rev = False
elif _cs == "north":
    _key = lambda f, r: (f["start"][1] if r == "start" else f["end"][1]); _rev = True
elif _cs == "east":
    _key = lambda f, r: (f["start"][0] if r == "start" else f["end"][0]); _rev = True
else:
    _key = lambda f, r: (f["start"][0] if r == "start" else f["end"][0]); _rev = False

endpoints = ([(_key(f, "start"), i, "start") for i, f in enumerate(segments)] +
             [(_key(f, "end"), i, "end") for i, f in enumerate(segments)])
endpoints.sort(reverse=_rev)
_, start_i, start_role = endpoints[0]

used = set()
order = []
reverse_first = (start_role == "end")
cursor = segments[start_i]["start"] if reverse_first else segments[start_i]["end"]
order.append((start_i, reverse_first))
used.add(start_i)

gaps = []
while len(used) < len(segments):
    best_d, best_i, best_rev = 1e18, None, False
    for i, f in enumerate(segments):
        if i in used:
            continue
        ds = hav(cursor, f["start"])
        de = hav(cursor, f["end"])
        if ds < best_d:
            best_d, best_i, best_rev = ds, i, False
        if de < best_d:
            best_d, best_i, best_rev = de, i, True
    if best_i is None:
        break
    if best_d > 200:
        gaps.append((best_d, best_i))
    if best_d > 5000:
        # Record the gap and stop consuming here, but keep the route built so
        # far rather than discarding it. A gap this large usually means a
        # disconnected branch or an unrelated line in the same layer.
        warn("LARGE_GAP", f"nearest unused segment is {best_d:.0f} m away; "
                          f"{len(segments) - len(used)} segment(s) left unchained")
        break
    f = segments[best_i]
    cursor = f["start"] if best_rev else f["end"]
    order.append((best_i, best_rev))
    used.add(best_i)

coords = []
for k, (si, rv) in enumerate(order):
    pts = segments[si]["points"]
    if rv:
        pts = list(reversed(pts))
    coords.extend(pts[1:] if k > 0 else pts)

clean = [coords[0]]
for i in range(1, len(coords)):
    if hav(coords[i - 1], coords[i]) > 0.1:
        clean.append(coords[i])
if len(clean) != len(coords):
    print(f"  Removed {len(coords) - len(clean)} duplicate point(s)")
coords = clean

cum = [0.0]
for i in range(1, len(coords)):
    cum.append(cum[-1] + hav(coords[i - 1], coords[i]))
polyline_m = cum[-1]

print(f"  Chained {len(order)}/{len(segments)} segments, {len(coords)} vertices")
print(f"  Polyline length: {polyline_m/1000:.2f} km")
if gaps:
    print(f"  {len(gaps)} join(s) > 200 m, largest {max(g[0] for g in gaps):.0f} m")

spacing = [hav(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
print(f"  Source spacing: mean {np.mean(spacing):.0f} m, max {np.max(spacing):.0f} m")
if np.mean(spacing) > 50:
    warn("LOW_POINT_DENSITY", f"mean source spacing {np.mean(spacing):.0f} m")


# ------------------------------------------------------------
# 4. Project + arc-length-correct spline resample
# ------------------------------------------------------------
print(f"\n[4/11] Resampling at {CONFIG['resample_m']} m (true arc length)")

lat0 = math.radians(float(np.mean([c[1] for c in coords])))
lon0_deg = float(np.mean([c[0] for c in coords]))
R_E = 6371000.0


def to_xy(lon, lat):
    x = R_E * math.radians(lon - lon0_deg) * math.cos(lat0)
    y = R_E * math.radians(lat - math.degrees(lat0))
    return x, y


def to_lonlat(x, y):
    lon = lon0_deg + math.degrees(x / (R_E * math.cos(lat0)))
    lat = math.degrees(lat0) + math.degrees(y / R_E)
    return lon, lat


xs0 = np.array([to_xy(c[0], c[1])[0] for c in coords])
ys0 = np.array([to_xy(c[0], c[1])[1] for c in coords])

# Smoothing spline: s is the allowed sum of squared residuals.
sigma = CONFIG["xy_noise_m"]
s_smooth = len(xs0) * (sigma ** 2)
u0 = np.array(cum) / polyline_m
tck, _ = splprep([xs0, ys0], u=u0, s=s_smooth, k=3)
print(f"  Smoothing spline: sigma {sigma:.1f} m -> s = {s_smooth:.0f}")

# Dense pass to build the true arc-length table
u_dense = np.linspace(0.0, 1.0, max(20000, 20 * int(polyline_m / CONFIG["resample_m"])))
xd, yd = splev(u_dense, tck)
s_dense = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(xd), np.diff(yd)))])
spline_m = float(s_dense[-1])

STEP = CONFIG["resample_m"]
chain_m = np.arange(0.0, spline_m, STEP)
u_r = np.interp(chain_m, s_dense, u_dense)
xs_r, ys_r = splev(u_r, tck)
xs_r = np.asarray(xs_r)
ys_r = np.asarray(ys_r)
N = len(chain_m)
seg_len = np.diff(chain_m)
total_m = float(chain_m[-1])

print(f"  {N} points, spline length {spline_m/1000:.2f} km "
      f"({100*(spline_m-polyline_m)/polyline_m:+.2f}% vs polyline)")


# ------------------------------------------------------------
# 5. Stations + settle direction BEFORE curvature
# ------------------------------------------------------------
print(f"\n[5/11] Stations: {CONFIG['stations_csv']}")


def project_point(lon, lat):
    x, y = to_xy(lon, lat)
    d = np.hypot(xs_r - x, ys_r - y)
    i = int(np.argmin(d))
    return i, float(chain_m[i]), float(d[i])


def read_stations():
    out = []
    with open(CONFIG["stations_csv"], newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = row["name"].strip()
            lat = float(row["lat"])
            lon = float(row["lon"])
            stop = str(row.get("stop", "1")).strip().lower() not in ("0", "false", "no", "pass")
            idx, ch, off = project_point(lon, lat)
            out.append({"name": name, "idx": idx, "km": ch / 1000.0,
                        "offset_m": round(off), "stop": stop})
    return out


stations = read_stations()
kms = [s["km"] for s in stations]
n_asc = sum(1 for i in range(len(kms) - 1) if kms[i] < kms[i + 1])
n_desc = sum(1 for i in range(len(kms) - 1) if kms[i] > kms[i + 1])

flipped = False
if n_desc > n_asc:
    print(f"  Reversing chain ({n_desc} descending vs {n_asc} ascending pairs)")
    xs_r = xs_r[::-1].copy()
    ys_r = ys_r[::-1].copy()
    # chain_m stays 0..total ascending; geometry is now mirrored
    flipped = True
    stations = read_stations()
    kms = [s["km"] for s in stations]

for st in stations:
    flag = "  <-- offset > 500 m" if st["offset_m"] > 500 else ""
    kind = "" if st["stop"] else "  (pass)"
    print(f"  {st['name']:<24} {st['km']:>8.2f} km  off {st['offset_m']:>4} m{kind}{flag}")
    if st["offset_m"] > 500:
        warn("STATION_OFFSET", f"{st['name']} projected {st['offset_m']} m from track")

if not all(kms[i] <= kms[i + 1] for i in range(len(kms) - 1)):
    warn("MODEL_LIMITATION", "stations not monotonic along chain - check geometry")
else:
    print(f"  Ordering OK ({'reversed' if flipped else 'original'} chain)")

stop_indices = [s["idx"] for s in stations if s["stop"]]
if stations[0]["idx"] not in stop_indices:
    stop_indices.insert(0, stations[0]["idx"])
if stations[-1]["idx"] not in stop_indices:
    stop_indices.append(stations[-1]["idx"])
stop_indices = sorted(set(stop_indices))
stn_indices = [s["idx"] for s in stations]


# ------------------------------------------------------------
# 6. Curvature - analytic, smoothed in curvature space
# ------------------------------------------------------------
print("\n[6/11] Curvature (analytic from spline derivatives)")

u_eval = u_r[::-1].copy() if flipped else u_r
dx, dy = splev(u_eval, tck, der=1)
ddx, ddy = splev(u_eval, tck, der=2)
dx = np.asarray(dx); dy = np.asarray(dy)
ddx = np.asarray(ddx); ddy = np.asarray(ddy)

denom = (dx * dx + dy * dy) ** 1.5
kappa = np.where(denom > 1e-12, (dx * ddy - dy * ddx) / denom, 0.0)
if flipped:
    kappa = -kappa  # mirrored geometry flips handedness

W_CURV = max(1, int(round(CONFIG["curv_smooth_m"] / STEP)))
kappa_s = uniform_filter1d(kappa, size=W_CURV)

R_CAP = 5000.0
radii = np.where(np.abs(kappa_s) > 1.0 / R_CAP, 1.0 / np.maximum(np.abs(kappa_s), 1e-12), R_CAP)
radii = np.clip(radii, 20.0, R_CAP)

raw_radii = np.where(np.abs(kappa) > 1.0 / R_CAP, 1.0 / np.maximum(np.abs(kappa), 1e-12), R_CAP)
raw_radii = np.clip(raw_radii, 20.0, R_CAP)

i_min = int(np.argmin(radii))
lon_m, lat_m = to_lonlat(xs_r[i_min], ys_r[i_min])
print(f"  Smoothing window: {W_CURV} pts ({W_CURV*STEP:.0f} m) in curvature space")
print(f"  Tightest curve: R = {radii[i_min]:.0f} m at km {chain_m[i_min]/1000:.2f}"
      f"  ({lat_m:.5f}, {lon_m:.5f})")
print(f"  Raw minimum:    R = {raw_radii.min():.0f} m")
if radii.min() > 1.5 * raw_radii.min():
    warn("SMOOTHING_CORRECTION",
         f"smoothed min R ({radii.min():.0f} m) > 1.5x raw ({raw_radii.min():.0f} m)")
if radii.min() < 50:
    warn("FALSE_CURVE_SUSPECTED", f"minimum radius {radii.min():.0f} m - verify geometry")


# ------------------------------------------------------------
# 7. DEM / grade
# ------------------------------------------------------------
dem_name = CONFIG.get("dem_layer_name")
use_dem = dem_name is not None


def sample_dem():
    lyrs = QgsProject.instance().mapLayersByName(dem_name)
    if not lyrs or not isinstance(lyrs[0], QgsRasterLayer):
        warn("MODEL_LIMITATION", f"DEM '{dem_name}' unavailable - treating as flat")
        return None
    dem = lyrs[0]
    src = dem.source().split("|")[0].strip()
    is_web = any(k in src for k in ("url=", "http://", "https://", "wms", "wmts", "dpiMode"))
    elev = None

    if not is_web:
        try:
            from osgeo import gdal, osr
            gdal.UseExceptions()
            ds = gdal.Open(src)
            if ds is not None:
                print("  Strategy: GDAL array")
                band = ds.GetRasterBand(1)
                gt = ds.GetGeoTransform()
                nodata = band.GetNoDataValue()
                dsrs = osr.SpatialReference(); dsrs.ImportFromWkt(ds.GetProjection())
                tsrs = osr.SpatialReference(); tsrs.ImportFromEPSG(4326)
                tsrs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                dsrs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                need = not dsrs.IsSameGeogCS(tsrs) or not dsrs.IsGeographic()
                lons = np.array([to_lonlat(xs_r[i], ys_r[i])[0] for i in range(N)])
                lats = np.array([to_lonlat(xs_r[i], ys_r[i])[1] for i in range(N)])
                if need:
                    ct = osr.CoordinateTransformation(tsrs, dsrs)
                    cd = np.array([ct.TransformPoint(lons[i], lats[i])[:2] for i in range(N)])
                    gx, gy = cd[:, 0], cd[:, 1]
                else:
                    gx, gy = lons, lats
                px = (gx - gt[0]) / gt[1]
                py = (gy - gt[3]) / gt[5]
                c0 = max(0, int(np.floor(px.min())) - 2)
                r0 = max(0, int(np.floor(py.min())) - 2)
                c1 = min(ds.RasterXSize - 1, int(np.ceil(px.max())) + 2)
                r1 = min(ds.RasterYSize - 1, int(np.ceil(py.max())) + 2)
                w, h = c1 - c0 + 1, r1 - r0 + 1
                arr = band.ReadAsArray(c0, r0, w, h).astype(np.float64)
                if nodata is not None:
                    arr[arr == nodata] = np.nan
                ds = None
                lx, ly = px - c0, py - r0
                x0 = np.clip(np.floor(lx).astype(int), 0, w - 2)
                y0 = np.clip(np.floor(ly).astype(int), 0, h - 2)
                fx, fy = lx - x0, ly - y0
                elev = (arr[y0, x0] * (1 - fx) * (1 - fy) + arr[y0, x0 + 1] * fx * (1 - fy) +
                        arr[y0 + 1, x0] * (1 - fx) * fy + arr[y0 + 1, x0 + 1] * fx * fy)
        except Exception as exc:
            print(f"  GDAL failed ({exc}) - falling back")
            elev = None

    if elev is None:
        from qgis.core import QgsRaster
        from scipy.interpolate import interp1d
        stride = max(1, int(CONFIG["dem_smooth_m"] / STEP))
        idxs = list(range(0, N, stride))
        if idxs[-1] != N - 1:
            idxs.append(N - 1)
        print(f"  Strategy: QGIS identify, {len(idxs)} samples")
        xf = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"),
                                    dem.crs(), QgsCoordinateTransformContext())
        prov = dem.dataProvider()
        sparse = np.full(len(idxs), np.nan)
        for q, i in enumerate(idxs):
            lon, lat = to_lonlat(xs_r[i], ys_r[i])
            res = prov.identify(xf.transform(QgsPointXY(lon, lat)),
                                QgsRaster.IdentifyFormatValue).results().get(1)
            if res is not None and res == res:
                sparse[q] = float(res)
        if np.isnan(sparse).all():
            warn("MODEL_LIMITATION", "DEM all nodata - treating as flat")
            return None
        ok = ~np.isnan(sparse)
        sparse = np.interp(np.arange(len(idxs)), np.where(ok)[0], sparse[ok])
        elev = interp1d(chain_m[idxs], sparse, kind="cubic",
                        fill_value="extrapolate")(chain_m)

    nan = np.isnan(elev)
    if nan.any():
        if (~nan).sum() < 4:
            warn("MODEL_LIMITATION", "DEM mostly nodata - treating as flat")
            return None
        elev[nan] = np.interp(np.flatnonzero(nan), np.flatnonzero(~nan), elev[~nan])

    wpts = max(3, int(CONFIG["dem_smooth_m"] / STEP))
    elev_s = uniform_filter1d(elev, size=wpts)
    g_raw = np.gradient(elev_s, chain_m)
    gmax = CONFIG["dem_max_grade_pct"] / 100.0
    n_clip = int(np.sum(np.abs(g_raw) > gmax))
    g = np.clip(g_raw, -gmax, gmax)
    print(f"  Elevation {elev_s.min():.0f}-{elev_s.max():.0f} m, "
          f"grade {g.min()*100:+.2f}% to {g.max()*100:+.2f}%")
    if n_clip:
        warn("MODEL_LIMITATION",
             f"{n_clip} DEM grade points clipped at +/-{CONFIG['dem_max_grade_pct']}%; "
             f"surface DEMs misread cuttings, embankments, bridges and tunnels")
    return g


print(f"\n[7/11] Grade")
grade = None
if use_dem:
    grade = sample_dem()
if grade is None:
    use_dem = False
    grade = np.full(N, CONFIG["grade_pct"] / 100.0)
    print(f"  Constant grade {CONFIG['grade_pct']:+.2f}%")


# ------------------------------------------------------------
# 8. Permissible speed + reverse-curve transitions
# ------------------------------------------------------------
print("\n[8/11] Permissible speed")

CANT = float(CONFIG["cant_mm"])
ED = float(CONFIG["ed_mm"])
EB = float(CONFIG["cant_base_m"])
VMAX = CONFIG["v_max_kmh"] / 3.6


def v_from_radius(R, cant_mm=CANT, def_mm=ED):
    if R >= 4000:
        return VMAX
    return min(math.sqrt(max(0.0, R * G * (cant_mm + def_mm) / 1000.0 / EB)), VMAX)


vp = np.array([v_from_radius(radii[i]) for i in range(N)])
vp = np.maximum(vp, 20 / 3.6)

r_needed = (VMAX ** 2 * EB) / (G * (CANT + ED) / 1000.0)
print(f"  Cant base e = {EB*1000:.0f} mm (EN 13803), cant {CANT:.0f} + deficiency {ED:.0f}")
print(f"  R required for {CONFIG['v_max_kmh']:.0f} km/h: {r_needed:.0f} m")

# --- reverse curves: measure the TANGENT GAP ---
QUAL = CONFIG["rev_curve_qualify_r"]
D_RATE = CONFIG["cant_rate_mms"]
I_RATE = CONFIG["cant_def_rate_mms"]
D_GRAD = CONFIG["cant_gradient_mm_m"]

sign = np.sign(kappa_s)
rev_zones = []
for i in range(1, N):
    if sign[i] != 0 and sign[i - 1] != 0 and sign[i] != sign[i - 1]:
        if radii[max(0, i - 5)] < QUAL and radii[min(N - 1, i + 5)] < QUAL:
            rev_zones.append(i)

# cluster
clustered = []
for z in rev_zones:
    if clustered and z - clustered[-1][-1] <= int(300 / STEP):
        clustered[-1].append(z)
    else:
        clustered.append([z])


def opt_cant(R, v_ms):
    if R >= 4000:
        return 0.0
    return min((v_ms ** 2 * EB / (R * G)) * 1000.0, CANT)


def min_cant(R, v_ms):
    """Least applied cant that keeps deficiency within ED at speed v on radius R.

    A designer facing a constrained reversal reduces cant rather than running
    equilibrium cant, because less cant means less to ramp. Using equilibrium
    cant here overstates the excursion and understates the permissible speed.
    """
    if R >= 4000:
        return 0.0
    need = (v_ms ** 2 * EB / (R * G)) * 1000.0 - ED
    return min(max(need, 0.0), CANT)


rev_info = []
for zone in clustered:
    i_rev = int(np.mean(zone))
    i_rev = max(1, min(i_rev, N - 2))

    # The sign change happens IN the tangent between the two curves, so
    # radii[i_rev] is large here. Walk outward WHILE STRAIGHT to measure that
    # tangent: it is the distance available to ramp cant from one side to the
    # other, and it is what limits speed at a reversal.
    j = i_rev
    while j > 0 and radii[j] >= QUAL:
        j -= 1
    lo = j + 1
    j = i_rev
    while j < N - 1 and radii[j] >= QUAL:
        j += 1
    hi = j - 1
    L_avail = max((hi - lo + 1) * STEP, STEP)

    # Radii of the two circular curves flanking the tangent
    R_l = float(radii[max(0, lo - 1)])
    R_r = float(radii[min(N - 1, hi + 1)])
    R_min = min(R_l, R_r)

    # Solve jointly: highest v whose required cant ramps within L_avail.
    def transition_ok(v):
        d_l = min_cant(R_l, v)
        d_r = min_cant(R_r, v)
        dE = d_l + d_r
        if dE < 0.1:
            return True, "none"
        if v * dE > D_RATE * L_avail:
            return False, "dD/dt"
        if v * (2.0 * ED) > I_RATE * L_avail:
            return False, "dI/dt"
        if dE > L_avail * D_GRAD:
            return False, "dD/ds"
        return True, "none"

    ok_full, bind_full = transition_ok(VMAX)
    if ok_full:
        v_lim, binding = VMAX, "none"
    else:
        lo_v, hi_v = 5.0 / 3.6, VMAX
        binding = bind_full
        for _ in range(40):
            mid = 0.5 * (lo_v + hi_v)
            ok, b = transition_ok(mid)
            if ok:
                lo_v = mid
            else:
                hi_v = mid
                binding = b
        v_lim = lo_v

    rev_info.append({
        "idx": i_rev, "km": chain_m[i_rev] / 1000.0,
        "L_avail_m": round(L_avail), "span_m": round(L_avail),
        "v_lim_kmh": round(v_lim * 3.6, 1),
        "binding": binding,
        "r_bef": round(R_l), "r_aft": round(R_r),
    })

n_capped = 0
for info in rev_info:
    v_lim = info["v_lim_kmh"] / 3.6
    if v_lim >= VMAX - 0.05:
        continue
    half = max(1, int((info["L_avail_m"] / 2) / STEP))
    a = max(0, info["idx"] - half)
    b = min(N - 1, info["idx"] + half)
    before = vp[a:b + 1].copy()
    vp[a:b + 1] = np.minimum(vp[a:b + 1], v_lim)
    n_capped += int(np.sum(vp[a:b + 1] < before))

binding = [r for r in rev_info if r["v_lim_kmh"] < CONFIG["v_max_kmh"] - 0.1]
print(f"  Reverse-curve zones: {len(rev_info)}, speed-constraining: {len(binding)}")
if binding:
    print(f"  {'km':>8} {'L_avail':>9} {'V_lim':>8} {'bind':>7} {'R_bef':>7} {'R_aft':>7}")
    for r in binding[:25]:
        print(f"  {r['km']:>8.2f} {r['L_avail_m']:>8} m {r['v_lim_kmh']:>7.1f} "
              f"{r['binding']:>7} {r['r_bef']:>6} m {r['r_aft']:>6} m")
print(f"  {n_capped} points capped by transition limits")


# ------------------------------------------------------------
# 9. Curve inventory
# ------------------------------------------------------------
THRESH = CONFIG["curve_thresh_m"]
MINL = CONFIG["curve_min_len_m"]
curves = []
in_curve = radii < THRESH
i = 0
while i < N:
    if in_curve[i]:
        j = i
        while j < N and in_curve[j]:
            j += 1
        arc = chain_m[j - 1] - chain_m[i]
        if arc >= MINL:
            mi = i + int(np.argmin(radii[i:j]))
            tlon, tlat = to_lonlat(xs_r[mi], ys_r[mi])
            curves.append({
                "i0": i, "i1": j - 1, "imin": mi,
                "track_lon": tlon, "track_lat": tlat,
                "start_km": round(chain_m[i] / 1000.0, 3),
                "end_km": round(chain_m[j - 1] / 1000.0, 3),
                "length_m": round(arc),
                "min_r": round(float(radii[i:j].min())),
                "perm_kmh": round(v_from_radius(float(radii[i:j].min())) * 3.6, 1),
            })
        i = j
    else:
        i += 1
print(f"  {len(curves)} curves (R < {THRESH} m, length >= {MINL} m); "
      f"{sum(1 for c in curves if c['min_r'] < r_needed)} below line speed")


# ------------------------------------------------------------
# 10. Kinematics
# ------------------------------------------------------------
print("\n[9/11] Kinematic model")

TT = CONFIG["traction_type"].lower()
MASS = CONFIG["mass_tonnes"] * 1000.0
POWER = CONFIG["power_kw"] * 1000.0
TE_MAX = CONFIG["max_te_kn"] * 1000.0
BRK_MAX = CONFIG["max_brake_kn"] * 1000.0
LAMBDA = {"emu": 1.06, "dmu": 1.08, "loco": 1.12}.get(TT, 1.06)
EFF_MASS = MASS * LAMBDA
A_CAP = CONFIG["max_accel_ms2"]
B_CAP = CONFIG["max_decel_ms2"]
TRAIN_L = CONFIG["train_length_m"]

if TT in ("emu", "dmu"):
    DA, DB, DC = 1.5, 0.006, 5.5
else:
    DA, DB, DC = 2.5, 0.010, 8.0
V_TRANS = POWER / TE_MAX
CURVE_RES_K = 700.0     # N per kN of weight, times 1/R (Roeckl-style)


def resistance_n(v_ms, grade_frac=0.0, radius_m=R_CAP):
    v_kmh = v_ms * 3.6
    # A and B scale with mass; C is a vehicle geometry term and does not.
    r_roll = (MASS / 1000.0) * (DA + DB * v_kmh)
    r_aero = DC * (v_kmh / 100.0) ** 2 * 1000.0
    r_curve = (MASS / 1000.0) * (CURVE_RES_K / max(radius_m, 100.0))
    return r_roll + r_aero + r_curve + MASS * G * grade_frac


def net_accel(v_ms, grade_frac=0.0, radius_m=R_CAP):
    te = TE_MAX if v_ms <= V_TRANS else POWER / max(v_ms, 0.1)
    a = (te - resistance_n(v_ms, grade_frac, radius_m)) / EFF_MASS
    return min(a, A_CAP)


def max_decel(v_ms, grade_frac=0.0, radius_m=R_CAP):
    b = (BRK_MAX + resistance_n(v_ms, grade_frac, radius_m)) / EFF_MASS
    return max(min(b, B_CAP), 0.01)


print(f"  {TT.upper()}  lambda {LAMBDA}  effective mass {EFF_MASS/1000:.0f} t")
print(f"  Transition speed {V_TRANS*3.6:.0f} km/h")
print(f"  Accel: {net_accel(1.0):.2f} / {net_accel(V_TRANS):.2f} / "
      f"{net_accel(VMAX*0.9):.2f} m/s2 (cap {A_CAP})")
print(f"  Decel cap {B_CAP} m/s2, curve resistance on")

if TRAIN_L > 0:
    Lp = max(1, int(round(TRAIN_L / STEP)))
    # rolling minimum over the whole train length, trailing
    vp_eff = minimum_filter1d(vp, size=Lp + 1, origin=(Lp // 2), mode="nearest")
    print(f"  Train length {TRAIN_L:.0f} m -> {int(np.sum(vp_eff < vp))} pts tightened")
else:
    Lp = 0
    vp_eff = vp.copy()
    print("  Point-mass train")


def build_envelope(vperm, slen, stops, grd, rad):
    pts = sorted(set(stops))
    env = np.zeros(len(vperm))
    for k in range(len(pts) - 1):
        i0, i1 = pts[k], pts[k + 1]
        L = i1 - i0 + 1
        vf = np.zeros(L)
        for j in range(1, L):
            d = slen[i0 + j - 1]
            a = net_accel(max(vf[j - 1], 0.1), float(grd[i0 + j - 1]), float(rad[i0 + j - 1]))
            vf[j] = min(math.sqrt(max(0.0, vf[j - 1] ** 2 + 2 * a * d)), vperm[i0 + j], VMAX)
        vb = np.zeros(L)
        for j in range(L - 2, -1, -1):
            d = slen[i0 + j]
            b = max_decel(max(vb[j + 1], 0.1), float(grd[i0 + j]), float(rad[i0 + j]))
            vb[j] = min(math.sqrt(max(0.0, vb[j + 1] ** 2 + 2 * b * d)), vperm[i0 + j], VMAX)
        env[i0:i1 + 1] = np.minimum(vf, vb)
    # Points outside the stop span would otherwise stay at zero and be charged
    # at the 0.1 m/s floor by cumulative_time. They are not on any train's
    # journey, so hold the terminal values rather than leaving a speed of zero.
    if pts:
        env[:pts[0]] = vperm[:pts[0]]
        env[pts[-1] + 1:] = vperm[pts[-1] + 1:]
    return env


def cumulative_time(env, slen):
    t = np.zeros(len(env))
    for i in range(1, len(env)):
        t[i] = t[i - 1] + slen[i - 1] / max((env[i - 1] + env[i]) / 2.0, 0.1)
    return t


DWELL = CONFIG["dwell_s"]
PAD = CONFIG["recovery"]

# --- Train 1: increasing chainage ---
env1 = build_envelope(vp_eff, seg_len, stop_indices, grade, radii)
traw1 = cumulative_time(env1, seg_len)

# --- Train 2: decreasing chainage. Grade sign MUST flip. ---
vp_r = vp[::-1]
vp_r_eff = (minimum_filter1d(vp_r, size=Lp + 1, origin=(Lp // 2), mode="nearest")
            if Lp > 0 else vp_r.copy())
slen_r = seg_len[::-1]
grade_r = -grade[::-1]
radii_r = radii[::-1]
stops_r = sorted({N - 1 - i for i in stop_indices})
env2 = build_envelope(vp_r_eff, slen_r, stops_r, grade_r, radii_r)
traw2 = cumulative_time(env2, slen_r)


def schedule(traw, stn_idx_seq, stop_flags):
    """Return padded offsets (s) at each listed station, plus total.

    prev_t is baselined to the ORIGIN station rather than to zero. The speed
    envelope is only built between the first and last stop, so if a terminal
    does not project exactly to index 0 or N-1, the points beyond it would
    otherwise be charged as running time before the train has departed. That
    error is direction-dependent and would make one direction look several
    minutes slower than the other on identical geometry.
    """
    out = []
    prev_t = float(traw[stn_idx_seq[0]])
    acc = 0.0
    for k, (idx, is_stop) in enumerate(zip(stn_idx_seq, stop_flags)):
        run = float(traw[idx]) - prev_t
        acc += run * (1.0 + PAD)
        out.append(acc)
        prev_t = float(traw[idx])
        if is_stop and 0 < k < len(stn_idx_seq) - 1:
            acc += DWELL
    return out, acc


seq1 = [s["idx"] for s in stations]
flag1 = [s["stop"] for s in stations]
arr1, tot1 = schedule(traw1, seq1, flag1)

seq2 = [N - 1 - s["idx"] for s in reversed(stations)]
flag2 = [s["stop"] for s in reversed(stations)]
arr2, tot2 = schedule(traw2, seq2, flag2)


def fmt(sec):
    m = int(round(sec / 60))
    return f"{m//60}h{m%60:02d}m" if m >= 60 else f"{m}m"


t1h, t1m = map(int, CONFIG["dep_hhmm_t1"].split(":"))
BASE1 = t1h * 3600 + t1m * 60
t2h, t2m = map(int, CONFIG["dep_hhmm_t2"].split(":"))
BASE2 = t2h * 3600 + t2m * 60


def clock(base, off):
    t = base + off
    return f"{int(t//3600)%24:02d}:{int((t%3600)//60):02d}"


print(f"\n  Train 1 {stations[0]['name']} -> {stations[-1]['name']}: {fmt(tot1)}")
print(f"  Train 2 {stations[-1]['name']} -> {stations[0]['name']}: {fmt(tot2)}")
print(f"  Mean speed T1: {total_m/1000/(tot1/3600):.1f} km/h")

hdr = f"  {'Station':<24} {'km':>8} {'arr':>7} {'dep':>7}"
print(f"\n  TRAIN 1  departs {CONFIG['dep_hhmm_t1']}")
print("  " + "-" * (len(hdr) - 2))
print(hdr)
for k, st in enumerate(stations):
    first, last = k == 0, k == len(stations) - 1
    a = "--" if first else clock(BASE1, arr1[k])
    if first:
        d = CONFIG["dep_hhmm_t1"]
    elif last:
        d = "--"
    else:
        d = clock(BASE1, arr1[k] + (DWELL if st["stop"] else 0))
    print(f"  {st['name']:<24} {st['km']:>8.2f} {a:>7} {d:>7}")

print(f"\n  TRAIN 2  departs {CONFIG['dep_hhmm_t2']}")
print("  " + "-" * (len(hdr) - 2))
print(hdr)
rev_stations = list(reversed(stations))
for k, st in enumerate(rev_stations):
    first, last = k == 0, k == len(rev_stations) - 1
    a = "--" if first else clock(BASE2, arr2[k])
    if first:
        d = CONFIG["dep_hhmm_t2"]
    elif last:
        d = "--"
    else:
        d = clock(BASE2, arr2[k] + (DWELL if st["stop"] else 0))
    print(f"  {st['name']:<24} {st['km']:>8.2f} {a:>7} {d:>7}")


# ------------------------------------------------------------
# 11. Single-track meets -> required passing loops
# ------------------------------------------------------------
print("\n[10/11] Single-track meets")

TAKT = CONFIG["takt_min"] * 60.0
TURN = CONFIG["turnaround_min"] * 60.0

# Physical-chainage time profiles, dwell included, padding applied.
def physical_time_profile(traw, stops, forward):
    """Seconds from origin to reach each physical index."""
    stop_set = sorted(set(stops))
    dwell_before = np.zeros(N)
    run = 0.0
    interior = set(stop_set[1:-1])
    for i in range(N):
        dwell_before[i] = run
        if i in interior:
            run += DWELL
    # Baseline to the origin stop, for the same reason as in schedule().
    t = (traw - float(traw[stop_set[0]])) * (1.0 + PAD) + dwell_before
    t = np.maximum(t, 0.0)
    if forward:
        return t
    out = np.zeros(N)
    out[::-1] = t
    return out


t1_phys = physical_time_profile(traw1, stop_indices, True)
t2_phys = physical_time_profile(traw2, stops_r, False)

# g(i) is monotonic increasing; meets occur where g = offset + j*TAKT
g_fun = t1_phys - t2_phys
offset0 = BASE2 - BASE1


def meets_for_offset(offset):
    lo, hi = float(g_fun[0]), float(g_fun[-1])
    out = []
    jmin = int(math.floor((lo - offset) / TAKT)) - 1
    jmax = int(math.ceil((hi - offset) / TAKT)) + 1
    for j in range(jmin, jmax + 1):
        target = offset + j * TAKT
        if target < lo or target > hi:
            continue
        i = int(np.searchsorted(g_fun, target))
        i = max(1, min(i, N - 1))
        out.append({"idx": i, "km": float(chain_m[i]) / 1000.0,
                    "radius_m": float(radii[i]),
                    "grade_pct": float(grade[i]) * 100.0,
                    "speed_kmh": float(min(env1[i], env2[N - 1 - i])) * 3.6})
    # cluster
    out.sort(key=lambda m: m["km"])
    clus = []
    for m in out:
        if clus and m["km"] - clus[-1]["km"] < CONFIG["loop_cluster_km"]:
            continue
        clus.append(m)
    return clus


def site_score(meets):
    """Lower is better: penalise tight radius and steep grade at the loop."""
    s = 0.0
    for m in meets:
        if m["radius_m"] < 600:
            s += 2.0
        elif m["radius_m"] < 1200:
            s += 1.0
        if abs(m["grade_pct"]) > 1.0:
            s += 2.0
        elif abs(m["grade_pct"]) > 0.5:
            s += 1.0
    return s


base_meets = meets_for_offset(offset0)
print(f"  Takt {CONFIG['takt_min']} min -> meets every {CONFIG['takt_min']/2:.0f} min "
      f"of running time")
print(f"  Loops required at current phasing: {len(base_meets)}")

best = {"offset": offset0, "meets": base_meets,
        "score": site_score(base_meets), "n": len(base_meets)}
if CONFIG["meet_phase_sweep"]:
    for dt in range(0, int(TAKT), 60):
        cand = meets_for_offset(offset0 + dt)
        sc = site_score(cand)
        if (len(cand), sc) < (best["n"], best["score"]):
            best = {"offset": offset0 + dt, "meets": cand, "score": sc, "n": len(cand)}
    shift = (best["offset"] - offset0) / 60.0
    if abs(shift) > 0.5:
        print(f"  Best phasing: shift Train 2 by {shift:+.0f} min "
              f"-> {best['n']} loops (score {best['score']:.0f})")
    else:
        print("  Current phasing is already the best in the sweep")

print(f"\n  {'km':>9} {'R at site':>11} {'grade':>8} {'v':>8} {'loop len':>10}")
for m in best["meets"]:
    v = max(m["speed_kmh"], 40.0)
    loop_m = 2.0 * (v / 3.6) * CONFIG["punctuality_s"] + 2 * TRAIN_L
    flag = ""
    if m["radius_m"] < 600 or abs(m["grade_pct"]) > 1.0:
        flag = "  <-- poor site"
    print(f"  {m['km']:>9.2f} {m['radius_m']:>10.0f} m {m['grade_pct']:>+7.2f}% "
          f"{v:>7.0f} {loop_m/1000:>9.2f} km{flag}")

round_trip = tot1 + tot2 + 2 * TURN
n_sets = max(1, int(math.ceil(round_trip / TAKT)))
slack = n_sets * TAKT - round_trip
to_drop = round_trip - (n_sets - 1) * TAKT if n_sets > 1 else None
print(f"\n  Round trip {fmt(round_trip)} (incl. {CONFIG['turnaround_min']} min turnarounds)")
print(f"  Fleet at {CONFIG['takt_min']} min takt: {n_sets} sets, slack {fmt(slack)}")
if to_drop:
    print(f"  Save {fmt(to_drop)} to drop to {n_sets-1} sets")


# ------------------------------------------------------------
# 12. Per-curve time loss
# ------------------------------------------------------------
ranked = []
if CONFIG["rank_curve_time_loss"] and curves:
    print("\n[11/11] Curve time-loss ranking")
    stops_sorted = sorted(set(stop_indices))

    def leg_time(vperm, i0, i1):
        env = build_envelope(vperm[i0:i1 + 1], seg_len[i0:i1],
                             [0, i1 - i0], grade[i0:i1 + 1], radii[i0:i1 + 1])
        return float(cumulative_time(env, seg_len[i0:i1])[-1])

    for c in curves:
        a = max([s for s in stops_sorted if s <= c["i0"]], default=stops_sorted[0])
        b = min([s for s in stops_sorted if s >= c["i1"]], default=stops_sorted[-1])
        if b <= a:
            continue
        base_t = leg_time(vp_eff, a, b)
        # Relax from the UNFILTERED permissible speed, then apply the
        # train-length filter once. Relaxing the already-filtered array and
        # filtering again would spread restrictions wider than the baseline
        # and make relaxed curves look slower than unrelaxed ones.
        relaxed = vp.copy()
        relaxed[c["i0"]:c["i1"] + 1] = VMAX
        if Lp > 0:
            relaxed = minimum_filter1d(relaxed, size=Lp + 1,
                                       origin=(Lp // 2), mode="nearest")
        new_t = leg_time(relaxed, a, b)
        c["loss_s"] = round(base_t - new_t, 1)
        ranked.append(c)

    ranked.sort(key=lambda c: -c["loss_s"])
    shown = ranked[:CONFIG["max_curves_ranked"]]
    total_loss = sum(c["loss_s"] for c in ranked)
    print(f"  Total recoverable by relaxing every curve: {fmt(total_loss)}")
    print(f"  {'rank':>5} {'km':>9} {'R':>7} {'len':>7} {'v':>7} {'loss':>8}")
    for k, c in enumerate(shown[:20], 1):
        print(f"  {k:>5} {c['start_km']:>9.2f} {c['min_r']:>6} m {c['length_m']:>6} m "
              f"{c['perm_kmh']:>6.0f} {c['loss_s']:>7.1f}s")
else:
    for c in curves:
        c["loss_s"] = 0.0
    ranked = curves


# ------------------------------------------------------------
# 13. Outputs
# ------------------------------------------------------------
label = CONFIG["run_label"]
outdir = _outdir_str

def write_csv_outputs():
    """CSV export. Skipped entirely in scratch mode."""
    tt_path = os.path.join(outdir, f"{label}_timetable.csv")
    with open(tt_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["station", "km", "offset_m", "stop",
                    "t1_arr", "t1_dep", "t2_arr", "t2_dep", "mean_grade_pct"])
        n = len(stations)
        for k, st in enumerate(stations):
            last = k == n - 1
            a1 = "--" if k == 0 else clock(BASE1, arr1[k])
            d1 = (CONFIG["dep_hhmm_t1"] if k == 0 else
                  "--" if last else clock(BASE1, arr1[k] + (DWELL if st["stop"] else 0)))
            j = n - 1 - k
            a2 = "--" if j == 0 else clock(BASE2, arr2[j])
            d2 = (CONFIG["dep_hhmm_t2"] if j == 0 else
                  "--" if j == n - 1 else clock(BASE2, arr2[j] + (DWELL if st["stop"] else 0)))
            gp = (round(float(np.mean(grade[stn_indices[k]:stn_indices[k + 1] + 1])) * 100, 3)
                  if not last else 0.0)
            w.writerow([st["name"], round(st["km"], 2), st["offset_m"], int(st["stop"]),
                        a1, d1, a2, d2, gp])
    print(f"\n  Timetable CSV: {tt_path}")

    cv_path = os.path.join(outdir, f"{label}_curves.csv")
    with open(cv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "start_km", "end_km", "length_m", "min_r_m",
                    "perm_kmh", "time_loss_s", "track_lat", "track_lon"])
        for k, c in enumerate(ranked, 1):
            w.writerow([k, c["start_km"], c["end_km"], c["length_m"], c["min_r"],
                        c["perm_kmh"], c.get("loss_s", 0.0),
                        round(c["track_lat"], 6), round(c["track_lon"], 6)])
    print(f"  Curves CSV:    {cv_path}")

    lp_path = os.path.join(outdir, f"{label}_loops.csv")
    with open(lp_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["loop", "km", "radius_m", "grade_pct", "meet_speed_kmh",
                    "min_loop_len_km", "site_ok", "lat", "lon"])
        for k, m in enumerate(best["meets"], 1):
            v = max(m["speed_kmh"], 40.0)
            loop_m = 2.0 * (v / 3.6) * CONFIG["punctuality_s"] + 2 * TRAIN_L
            ok = int(m["radius_m"] >= 600 and abs(m["grade_pct"]) <= 1.0)
            lon, lat = to_lonlat(xs_r[m["idx"]], ys_r[m["idx"]])
            w.writerow([k, round(m["km"], 3), round(m["radius_m"]), round(m["grade_pct"], 2),
                        round(v, 1), round(loop_m / 1000, 2), ok,
                        round(lat, 6), round(lon, 6)])
    print(f"  Loops CSV:     {lp_path}")

    sl_path = os.path.join(outdir, f"{label}_stringline.csv")
    with open(sl_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["km", "t1_min_from_dep", "t2_min_from_dep"])
        stride = max(1, int(500 / STEP))
        for i in range(0, N, stride):
            w.writerow([round(float(chain_m[i]) / 1000, 3),
                        round(float(t1_phys[i]) / 60, 3),
                        round(float(t2_phys[i]) / 60, 3)])
    print(f"  Stringline CSV:{sl_path}")


if WRITE_FILES:
    write_csv_outputs()
else:
    print("\n  Scratch mode - no CSVs written (output_dir is None).")
    print("  Results are in the memory layers below; nothing saved to disk.")

# --- QGIS layers ---
pf = QgsFields()
for nm, tp in [("rank", QVariant.Int), ("min_r_m", QVariant.Int),
               ("perm_kmh", QVariant.Double), ("length_m", QVariant.Int),
               ("start_km", QVariant.Double), ("loss_s", QVariant.Double)]:
    pf.append(QgsField(nm, tp))
vl = QgsVectorLayer("Point?crs=EPSG:4326", f"{label}_curves", "memory")
pr = vl.dataProvider(); pr.addAttributes(pf); vl.updateFields()
feats = []
for k, c in enumerate(ranked, 1):
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(c["track_lon"], c["track_lat"])))
    ft.setAttributes([k, c["min_r"], c["perm_kmh"], c["length_m"],
                      c["start_km"], c.get("loss_s", 0.0)])
    feats.append(ft)
pr.addFeatures(feats); vl.updateExtents()
QgsProject.instance().addMapLayer(vl)
print(f"  Layer '{label}_curves' added (graduate on loss_s)")

lf = QgsFields()
for nm, tp in [("loop", QVariant.Int), ("km", QVariant.Double),
               ("radius_m", QVariant.Int), ("grade_pct", QVariant.Double),
               ("min_len_km", QVariant.Double), ("site_ok", QVariant.Int)]:
    lf.append(QgsField(nm, tp))
vll = QgsVectorLayer("Point?crs=EPSG:4326", f"{label}_loops", "memory")
prl = vll.dataProvider(); prl.addAttributes(lf); vll.updateFields()
lfeats = []
for k, m in enumerate(best["meets"], 1):
    v = max(m["speed_kmh"], 40.0)
    loop_m = 2.0 * (v / 3.6) * CONFIG["punctuality_s"] + 2 * TRAIN_L
    lon, lat = to_lonlat(xs_r[m["idx"]], ys_r[m["idx"]])
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
    ft.setAttributes([k, round(m["km"], 3), int(m["radius_m"]),
                      round(m["grade_pct"], 2), round(loop_m / 1000, 2),
                      int(m["radius_m"] >= 600 and abs(m["grade_pct"]) <= 1.0)])
    lfeats.append(ft)
prl.addFeatures(lfeats); vll.updateExtents()
QgsProject.instance().addMapLayer(vll)
print(f"  Layer '{label}_loops' added")

SUB = 5
sf = QgsFields()
for nm, tp in [("perm_kmh", QVariant.Double), ("perm_eff_kmh", QVariant.Double),
               ("env_t1_kmh", QVariant.Double), ("env_t2_kmh", QVariant.Double),
               ("radius_m", QVariant.Double), ("km_start", QVariant.Double),
               ("grade_pct", QVariant.Double)]:
    sf.append(QgsField(nm, tp))
vls = QgsVectorLayer("LineString?crs=EPSG:4326", f"{label}_speed", "memory")
prs = vls.dataProvider(); prs.addAttributes(sf); vls.updateFields()
sfeats = []
env2_phys = env2[::-1]
for i in range(0, N - SUB, SUB):
    i1 = i + SUB
    pts = [QgsPointXY(*to_lonlat(xs_r[k], ys_r[k])) for k in range(i, min(i1 + 1, N))]
    if len(pts) < 2:
        continue
    ft = QgsFeature()
    ft.setGeometry(QgsGeometry.fromPolylineXY(pts))
    ft.setAttributes([
        round(float(np.mean(vp[i:i1 + 1])) * 3.6, 1),
        round(float(np.mean(vp_eff[i:i1 + 1])) * 3.6, 1),
        round(float(np.mean(env1[i:i1 + 1])) * 3.6, 1),
        round(float(np.mean(env2_phys[i:i1 + 1])) * 3.6, 1),
        round(float(np.mean(radii[i:i1 + 1])), 1),
        round(float(chain_m[i]) / 1000, 3),
        round(float(np.mean(grade[i:i1 + 1])) * 100, 3),
    ])
    sfeats.append(ft)
prs.addFeatures(sfeats); vls.updateExtents()
QgsProject.instance().addMapLayer(vls)
print(f"  Layer '{label}_speed' added")

if WARNINGS and WRITE_FILES:
    wp = os.path.join(outdir, f"{label}_warnings.csv")
    with open(wp, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "message"])
        for k, m in WARNINGS:
            w.writerow([k, m])
    print(f"  Warnings CSV:  {wp}")

print("\n" + "=" * 64)
print(f"Done.  {len(curves)} curves | {len(best['meets'])} loops | {n_sets} sets")
print(f"  T1 {fmt(tot1)}  T2 {fmt(tot2)}  round trip {fmt(round_trip)}")
print(f"  cant {CANT:.0f} + def {ED:.0f} on {EB*1000:.0f} mm base | {TT.upper()}")
print("  Model intent: geometric potential of the right-of-way.")
print("  Excludes civil limits, yard limits, signalling headway, freight paths.")
print()
print("  Written by Brendan Dawe. CC BY-NC 4.0 -- free for personal, educational")
print("  and research use with attribution. Professional/organizational use:")
print("  please reach out first. https://creativecommons.org/licenses/by-nc/4.0/")
print("=" * 64)
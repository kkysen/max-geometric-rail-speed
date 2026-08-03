#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "pypdf",
# ]
# ///
"""Download the raw data feeding scripts/prepare_route.py, into data/raw/.

Sources:
  MTA DOS Track Linear Referencing System (LRS) -- data.ny.gov dataset dyuj-5if7.
  MTA Subway Stations                           -- data.ny.gov dataset 39hk-dx4f.
  NYCT R211 Technical Specification (Contract R34211), via the Wayback Machine --
    background reading for the rolling-stock figures in railway_speed.py's CONFIG
    (not read programmatically; extracted to text here just so the source is
    grep-able/citable locally instead of a 9 MB PDF).

The first two are official MTA Open Data publications on data.ny.gov (Socrata).
Re-run any time to refresh; data/raw/ is gitignored so nothing here is committed.
"""

import json
import subprocess
from pathlib import Path

from pypdf import PdfReader

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

TRACK_LRS_URL = (
    "https://data.ny.gov/api/views/dyuj-5if7/files/"
    "9a3e5aed-c507-4b67-8b07-b24d5406b675"
    "?download=true&filename=Subways_Track_LRS.gdb.zip"
)
STATIONS_URL = "https://data.ny.gov/resource/39hk-dx4f.json?$limit=1000"
R211_SPEC_URL = (
    "https://web.archive.org/web/20230604084254/"
    "https://transitinnovation.org/wp-content/uploads/2019/12/R211%20Tech%20Spec.pdf"
)


def download(url: str, dest: Path) -> None:
    # Shells out to curl rather than urllib: archive.org serves an HTML
    # interstitial instead of the PDF to plain urllib requests (even with a
    # matching User-Agent) but serves the real file to curl directly --
    # likely an HTTP/2 or TLS-fingerprint difference, not a header one.
    print(f"  {dest.name} <- {url}")
    subprocess.run(
        ["curl", "-sL", "--fail", "--max-time", "180", "-o", str(dest), url],
        check=True,
    )
    print(f"    {dest.stat().st_size:,} bytes")


def extract_pdf_text(pdf_path: Path, dest: Path) -> None:
    reader = PdfReader(str(pdf_path))
    print(f"  Extracting text from {pdf_path.name} ({len(reader.pages)} pages)")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    dest.write_text(text)
    print(f"    {dest.name}: {len(text):,} chars")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    track_zip = RAW_DIR / "Subways_Track_LRS.gdb.zip"
    download(TRACK_LRS_URL, track_zip)

    stations_json = RAW_DIR / "mta_subway_stations.json"
    download(STATIONS_URL, stations_json)
    n = len(json.loads(stations_json.read_text()))
    print(f"    {n} stations")

    r211_pdf = RAW_DIR / "r211_tech_spec.pdf"
    download(R211_SPEC_URL, r211_pdf)
    extract_pdf_text(r211_pdf, RAW_DIR / "r211_tech_spec.txt")

    print("\nDone. See data/raw/.")


if __name__ == "__main__":
    main()

# TSM Analytics

TSM Analytics is a standalone Linux desktop application for visualizing **TSM Accounting Sales exports**.

It provides:
- CSV file picker (no terminal usage needed)
- Automatic TSM column detection (timestamp, price, item, quantity)
- Manual mapping fallback UI when autodetect fails
- Local-time conversion of TSM unix timestamps
- Copper-to-gold conversion for price values
- Background loading to keep the UI responsive for large files
- Charts for:
  - Gold earned per day
  - Sales count per day
  - Price per sale over time (toggleable)
- Sortable table of parsed rows
- Filters (date range + item)
- Export chart to PNG
- Export normalized data to CSV

## Where the source CSV comes from

From the TSM Desktop App:

**TSM Desktop App → Accounting → Sales export**

## Tech stack

- Python 3.11+
- PySide6 (GUI)
- pandas (CSV parsing/transforms)
- matplotlib (chart rendering)
- PyInstaller + AppImageKit `appimagetool` for AppImage packaging

## Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m tsm_analytics.main
```

## Build a single AppImage (Fedora / Nobara compatible)

```bash
chmod +x scripts/build_appimage.sh
./scripts/build_appimage.sh
```

Output:

- `TSM-Analytics-x86_64.AppImage`

### Reproducible build steps (exact)

1. `python3 -m venv build/.venv-appimage`
2. `source build/.venv-appimage/bin/activate`
3. `pip install --upgrade pip`
4. `pip install -r requirements-build.txt`
5. `pyinstaller --noconfirm --windowed --name TSMAnalytics --paths src --collect-all matplotlib --collect-all pandas --hidden-import PySide6.QtSvg src/tsm_analytics/main.py`
6. Create AppDir structure and copy assets (automated by `scripts/build_appimage.sh`)
7. Download `appimagetool-x86_64.AppImage` and run:
   `ARCH=x86_64 build/appimagetool build/TSMAnalytics.AppDir TSM-Analytics-x86_64.AppImage`

## How to use

1. Launch `TSM Analytics`.
2. Click **Select TSM Sales CSV** and choose your export file.
3. If auto-detection succeeds, data loads immediately in the background.
4. If auto-detection fails, assign required columns:
   - Timestamp
   - Price
   - (Optional) Item
   - (Optional) Quantity
5. Use filters:
   - Start / End date
   - Item selector/search
6. Explore charts and sortable table.
7. Use export buttons to save chart PNGs or normalized CSV output.

## Project layout

- `src/tsm_analytics/app.py` — Main GUI app
- `src/tsm_analytics/csv_processing.py` — Detection, parsing, normalization, aggregation
- `src/tsm_analytics/table_model.py` — DataFrame table model for Qt
- `scripts/build_appimage.sh` — AppImage build script
- `assets/tsm-analytics.svg` — App icon

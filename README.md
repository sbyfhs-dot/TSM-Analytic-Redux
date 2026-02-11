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

- Classic tailoring item ID→name mapping via `data/item_names.json`
- Copper prices normalized to integer copper plus formatted `Xg Ys Zc` displays

## Where the source CSV comes from

From the TSM Desktop App:

**TSM Desktop App → Accounting → Sales export**

## Tech stack

- Python 3.11+ (including Python 3.14)
- PySide6 `>=6.10.1,<6.11` (GUI; supports modern Python including 3.14)
- pandas (CSV parsing/transforms)
- matplotlib (chart rendering)
- PyInstaller + AppImageKit `appimagetool` for AppImage packaging


> Python 3.14 note: the build/runtime dependency range uses `PySide6>=6.10.1,<6.11` so pip can resolve compatible wheels on Python 3.14+.

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

- `dist/TSM-Analytics-x86_64.AppImage`

### Reproducible build steps (exact)

1. `python3 -m venv .venv-appimage`
2. `source .venv-appimage/bin/activate`
3. `pip install --upgrade pip`
4. `pip install -r requirements-build.txt`
5. `pyinstaller --noconfirm --windowed --name TSMAnalytics --paths src --collect-all matplotlib --collect-all pandas --hidden-import PySide6.QtSvg src/tsm_analytics/main.py`
6. Create AppDir structure and copy assets (automated by `scripts/build_appimage.sh`)
7. Download `appimagetool-x86_64.AppImage` and run:
   `ARCH=x86_64 build/appimagetool build/TSMAnalytics.AppDir dist/TSM-Analytics-x86_64.AppImage`

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


## How to cut a release

1. Commit and push your release-ready changes.
2. Create and push a semantic tag like `v1.0.0`:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. GitHub Actions runs `.github/workflows/release-appimage.yml` on that tag.
4. CI builds `dist/TSM-Analytics-x86_64.AppImage`, verifies it is executable, generates `dist/SHA256SUMS.txt`, then creates/updates the GitHub Release for the tag and uploads both files as release assets.


## Classic tailoring mapping file

- Mapping file path: `data/item_names.json`
- Format: JSON object where key is item ID as string and value is display name.
- Example:
  ```json
  {
    "4306": "Silk Cloth",
    "4338": "Mageweave Cloth"
  }
  ```
- To add support for more items, append new `"<item_id>": "<Item Name>"` entries and restart the app.

## Gold / silver / copper formatting

- Raw sale prices are treated as **integer copper** (`price_copper`).
- The app derives:
  - `price_display` as `Xg Ys Zc` (for example `1s 50c`, `1g 5s 0c`)
  - `total_copper` as `price_copper * quantity`
  - `total_display` in `Xg Ys Zc` format
- Charts aggregate numeric totals in gold internally, while hover text and table/export include human-readable g/s/c fields.

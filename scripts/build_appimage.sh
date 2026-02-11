#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
APPDIR="$BUILD_DIR/TSMAnalytics.AppDir"
VENV_DIR="$BUILD_DIR/.venv-appimage"

mkdir -p "$BUILD_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements-build.txt"

cd "$ROOT_DIR"
rm -rf build dist *.spec "$APPDIR" "$ROOT_DIR/TSM-Analytics-x86_64.AppImage"

pyinstaller \
  --noconfirm \
  --windowed \
  --name TSMAnalytics \
  --paths src \
  --collect-all matplotlib \
  --collect-all pandas \
  --hidden-import PySide6.QtSvg \
  src/tsm_analytics/main.py

mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/scalable/apps"
cp -r "$ROOT_DIR/dist/TSMAnalytics" "$APPDIR/usr/bin/"
cp "$ROOT_DIR/assets/tsm-analytics.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/tsm-analytics.svg"

cat > "$APPDIR/TSMAnalytics.desktop" <<'DESKTOP'
[Desktop Entry]
Name=TSM Analytics
Exec=TSMAnalytics
Icon=tsm-analytics
Type=Application
Categories=Utility;Finance;
Terminal=false
DESKTOP

cp "$APPDIR/TSMAnalytics.desktop" "$APPDIR/usr/share/applications/TSMAnalytics.desktop"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/TSMAnalytics/TSMAnalytics" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

if [[ ! -x "$BUILD_DIR/appimagetool" ]]; then
  curl -L "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -o "$BUILD_DIR/appimagetool"
  chmod +x "$BUILD_DIR/appimagetool"
fi

ARCH=x86_64 "$BUILD_DIR/appimagetool" "$APPDIR" "$ROOT_DIR/TSM-Analytics-x86_64.AppImage"

echo "Built AppImage: $ROOT_DIR/TSM-Analytics-x86_64.AppImage"

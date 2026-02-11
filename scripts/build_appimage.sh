#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
DIST_DIR="$ROOT_DIR/dist"
APPDIR="$BUILD_DIR/TSMAnalytics.AppDir"
VENV_DIR="$ROOT_DIR/.venv-appimage"
APPIMAGE_TOOL="$BUILD_DIR/appimagetool"
APPIMAGE_NAME="TSM-Analytics-x86_64.AppImage"
APPIMAGE_PATH="$DIST_DIR/$APPIMAGE_NAME"

mkdir -p "$BUILD_DIR" "$DIST_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$ROOT_DIR/requirements-build.txt"

cd "$ROOT_DIR"
rm -rf "$APPDIR" "$DIST_DIR/TSMAnalytics" "$ROOT_DIR/TSMAnalytics.spec" "$APPIMAGE_PATH"

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

if [[ ! -x "$APPIMAGE_TOOL" ]]; then
  curl -L "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" -o "$APPIMAGE_TOOL"
  chmod +x "$APPIMAGE_TOOL"
fi

ARCH=x86_64 "$APPIMAGE_TOOL" "$APPDIR" "$APPIMAGE_PATH"
chmod +x "$APPIMAGE_PATH"

echo "Built AppImage: $APPIMAGE_PATH"

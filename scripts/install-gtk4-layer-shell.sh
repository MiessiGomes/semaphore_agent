#!/usr/bin/env bash
# Build and install gtk4-layer-shell from source (Ubuntu 24.04 / Zorin 18 / Debian 12).
# Note: even after install, layer-shell does NOT work on GNOME Wayland — use KDE/Hyprland
# for true always-on-top overlay, or use semaphore's GNOME fallback automatically.
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage: ./scripts/install-gtk4-layer-shell.sh

Builds gtk4-layer-shell from GitHub and installs to /usr/local.
Requires: sudo for apt and ninja install.

On GNOME/Zorin this library installs but is ignored by Mutter — semaphore
uses GTK fallback automatically on GNOME sessions.
EOF
  exit 0
fi

echo "==> Installing build dependencies..."
sudo apt update
sudo apt install -y \
  git meson ninja-build pkg-config \
  libwayland-dev wayland-protocols \
  libgtk-4-dev gobject-introspection libgirepository-2.0-dev \
  gtk-doc-tools python3 valac

BUILD_DIR="${TMPDIR:-/tmp}/gtk4-layer-shell-build"
rm -rf "$BUILD_DIR"
git clone --depth 1 https://github.com/wmww/gtk4-layer-shell.git "$BUILD_DIR"
cd "$BUILD_DIR"

echo "==> Building gtk4-layer-shell..."
meson setup -Dexamples=false -Ddocs=false -Dtests=false build
ninja -C build

echo "==> Installing (sudo)..."
sudo ninja -C build install
sudo ldconfig

echo ""
echo "Done. Verify with:"
echo "  ldconfig -p | grep gtk4-layer-shell"
echo ""
echo "Runtime packages for semaphore (PyGObject):"
echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0"

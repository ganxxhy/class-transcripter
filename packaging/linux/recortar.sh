#!/usr/bin/env bash
# Trims the PyInstaller output (dist/Estudio) before it goes into the AppImage.
#
# The asistente window uses the system's WebKitGTK (pywebview + PyGObject), so the whole GTK stack
# that PyInstaller copied from the build machine (GTK, GLib, Pango, Cairo, fontconfig...) must NOT
# travel in the AppImage: it would clash with the newer WebKitGTK of the user's distribution.
# We keep only what Python, Tk (libXss is not installed by default on every distribution), the pip libraries
# PortAudio's own dependencies (ALSA and JACK, as before: not every system has them) and libgirepository-1.0 (Arch and other new distributions only ship the 2.0 one, which PyGObject 3.50 cannot use) need.
# Usage: bash packaging/linux/recortar.sh dist/Estudio
set -euo pipefail

DIR="${1:?usage: recortar.sh dist/Estudio}/_internal"
antes=$(du -sm "$DIR/.." | cut -f1)

# Typelibs, GIO modules and icon themes of the build machine: the system ones are used instead
rm -rf "$DIR/gi_typelibs" "$DIR/gio_modules" "$DIR/share/icons" "$DIR/share/glib-2.0" "$DIR/share/mime"

# System libraries that PyInstaller bundled, except the ones Python, Tk and PortAudio need.
# Libraries from pip wheels have a hash in their name (libfoo-1a2b3c4d.so) and live next to them: keep them.
for f in "$DIR"/lib*.so*; do
  n=$(basename "$f")
  case "$n" in
    libpython*|libportaudio*|libffi*|libssl*|libcrypto*|libz.so*|libbz2*|liblzma.so*|libsqlite3*|\
    libtcl*|libtk*|libXss*|libgirepository-1.0*|libasound*|libjack*|libdb-*|libreadline*|libtinfo*|libuuid*|libexpat*|libmvec*) continue ;;
  esac
  [[ "$n" =~ -[0-9a-f]{8}\.so ]] && continue
  rm -f "$f"
done

# Debug symbols are useless in a release
find "$DIR" -type f \( -name '*.so' -o -name '*.so.*' \) -exec strip --strip-unneeded {} + 2>/dev/null || true

# What is left may only depend on libraries that are present (here, on the build machine)
fallos=0
while IFS= read -r lib; do
  falta=$(LD_LIBRARY_PATH="$DIR" ldd "$lib" 2>/dev/null | grep 'not found' || true)
  if [ -n "$falta" ]; then echo "$(basename "$lib"): $falta"; fallos=1; fi
done < <(find "$DIR" -maxdepth 1 -type f \( -name '*.so' -o -name '*.so.*' \); find "$DIR" -path '*/lib-dynload/*.so' -type f)
despues=$(du -sm "$DIR/.." | cut -f1)
echo "recortar: ${antes} MB -> ${despues} MB"
exit $fallos

#!/bin/bash
# Runs inside the 32-bit Debian (armhf) environment. Called by install.sh.
# Installs the native libraries the linux-arm build needs, then installs or updates
# Jellyfin in /opt/jellyfin. Data lives in /var/lib/jellyfin and survives updates.
set -e
SRC="${1:-/tmp/jellyfin-redmi9}"
export DEBIAN_FRONTEND=noninteractive

[ "$(dpkg --print-architecture)" = "armhf" ] || { echo "Not an armhf Debian." >&2; exit 1; }

echo "-- apt packages"
apt-get update
# names that differ between Debian releases (bookworm: libicu72/libssl3, trixie: libicu76/libssl3t64)
ICU="$(apt-cache pkgnames libicu | grep -E '^libicu[0-9]+$' | sort -V | tail -1)"
SSL="$(apt-cache pkgnames libssl | grep -E '^libssl3(t64)?$' | sort | tail -1)"
apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates tzdata procps \
    libfontconfig1 fonts-dejavu-core \
    zlib1g libstdc++6 libgcc-s1 ${ICU:-libicu-dev} ${SSL:-libssl3}

FFV="$(ffmpeg -version | head -1 | awk '{print $3}')"
echo "ffmpeg $FFV (Jellyfin needs 4.4 or newer)"

echo "-- Jellyfin files"
mkdir -p /var/lib/jellyfin/data /var/lib/jellyfin/config /var/lib/jellyfin/cache /var/lib/jellyfin/log
rm -rf /opt/jellyfin.new
cp -a "$SRC/server" /opt/jellyfin.new
chmod 755 /opt/jellyfin.new/jellyfin
rm -rf /opt/jellyfin.old
[ -d /opt/jellyfin ] && mv /opt/jellyfin /opt/jellyfin.old
mv /opt/jellyfin.new /opt/jellyfin
rm -rf /opt/jellyfin.old

# phone-friendly transcoding defaults, only on first install (the dashboard can change them)
if [ ! -f /var/lib/jellyfin/config/encoding.xml ]; then
    cp "$SRC/encoding.xml" /var/lib/jellyfin/config/encoding.xml
fi

install -m 755 "$SRC/jellyfin-run" /usr/local/bin/jellyfin-run
rm -rf "$SRC"
echo "-- installed: $(cat /opt/jellyfin/VERSION 2>/dev/null)"

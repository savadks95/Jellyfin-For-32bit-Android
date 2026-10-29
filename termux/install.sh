#!/data/data/com.termux/files/usr/bin/sh
# Jellyfin 12.4 for 32-bit Termux (e.g. Redmi 9: 64-bit CPU, 32-bit Android).
#
# Termux's own "jellyfin-server" package does not exist for 32-bit ARM, because
# Microsoft's .NET does not run on Android's libc for 32-bit ARM. .NET *does* support
# 32-bit ARM Linux with glibc, so this installs a small 32-bit Debian with proot-distro
# and runs a Jellyfin build made for linux-arm inside it.
#
# Usage (inside Termux, in the unpacked jellyfin-32bit-android folder):
#   sh install.sh            install or update
#   sh install.sh --boot     also start Jellyfin automatically (needs the Termux:Boot app)
set -e

DISTRO="${JF_DISTRO:-debian}"
HERE="$(cd "$(dirname "$0")" && pwd -P)"
BOOT=0
[ "$1" = "--boot" ] && BOOT=1

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[ -n "$PREFIX" ] && [ -d "$PREFIX" ] || die "Run this inside the Termux app."
[ -d "$HERE/server" ] || die "The 'server' folder is missing next to install.sh. Unpack the whole archive."

ARCH="$(dpkg --print-architecture 2>/dev/null || echo unknown)"
case "$ARCH" in
    arm) ;;
    aarch64)
        die "This Termux is 64-bit. Use the official package instead: pkg install jellyfin-server
       (this build is only for 32-bit Termux, e.g. Redmi 9 with 32-bit Android)." ;;
    *) die "Unsupported Termux architecture: $ARCH (this build is for 32-bit ARM)." ;;
esac
echo "Kernel: $(uname -m), Termux userspace: $ARCH"

say "Updating Termux and installing proot-distro, curl, iproute2"
# never stop to ask about changed config files (works over SSH too); keep the user's versions
export DEBIAN_FRONTEND=noninteractive
APT_OPTS="-o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"
apt-get update
apt-get -y $APT_OPTS full-upgrade
apt-get -y $APT_OPTS install proot-distro curl iproute2 tar

say "Preparing the 32-bit Debian environment ('$DISTRO')"
if proot-distro login "$DISTRO" -- true >/dev/null 2>&1; then
    echo "'$DISTRO' is already installed; reusing it."
else
    proot-distro install "$DISTRO"
fi
GUEST_ARCH="$(proot-distro login "$DISTRO" -- dpkg --print-architecture)"
[ "$GUEST_ARCH" = "armhf" ] || die "The '$DISTRO' environment is '$GUEST_ARCH', expected 'armhf'. Set JF_DISTRO to another name and retry."

if command -v jellyfin >/dev/null 2>&1; then
    say "Stopping the running Jellyfin before updating it"
    jellyfin stop || true
fi

say "Copying Jellyfin into Debian (about 200 MB, takes a minute)"
# A tar stream through proot-distro avoids depending on where proot-distro keeps its files.
tar -C "$HERE" -cf - server debian-setup.sh jellyfin-run encoding.xml \
    | proot-distro login "$DISTRO" -- sh -c 'rm -rf /tmp/jellyfin-redmi9 && mkdir -p /tmp/jellyfin-redmi9 && tar -C /tmp/jellyfin-redmi9 -xf -'

say "Installing Debian packages and Jellyfin (inside Debian)"
proot-distro login "$DISTRO" -- bash /tmp/jellyfin-redmi9/debian-setup.sh /tmp/jellyfin-redmi9

say "Installing the 'jellyfin' command in Termux"
sed "s/^DISTRO=.*/DISTRO=\"\${JF_DISTRO:-$DISTRO}\"/" "$HERE/jellyfin" > "$PREFIX/bin/jellyfin"
chmod 755 "$PREFIX/bin/jellyfin"

if [ "$BOOT" = "1" ]; then
    mkdir -p "$HOME/.termux/boot"
    cat > "$HOME/.termux/boot/start-jellyfin" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
$PREFIX/bin/jellyfin start
EOF
    chmod 755 "$HOME/.termux/boot/start-jellyfin"
    echo "Jellyfin will start when the phone boots (requires the Termux:Boot app, opened once)."
fi

say "Starting Jellyfin"
"$PREFIX/bin/jellyfin" start

cat <<'EOF'

Done. Next steps:
  * Wait 1-2 minutes on first start, then open the address printed above
    (or http://127.0.0.1:8096 on the phone itself) and finish the setup wizard.
  * Media on the phone's storage is under /sdcard (run termux-setup-storage once).
  * Commands: jellyfin start | stop | restart | status | logs | run
  * Keep Termux out of battery optimisation (Settings > Apps > Termux > Battery saver
    > No restrictions; MIUI: also enable "Autostart") or Android will kill the server.
EOF

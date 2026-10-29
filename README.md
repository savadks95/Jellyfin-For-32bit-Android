# Jellyfin For 32bit Android

Run the **real Jellyfin media server (12.4)** on Android phones, tablets and TV boxes that run
**32-bit Android**, from **Termux**, with no root.

Many budget devices have a 64-bit CPU but ship 32-bit Android. The Redmi 9 is one example:
Helio G80 CPU, `armeabi-v7a` software. On those devices Termux is 32-bit, and Termux's own
`jellyfin-server` package is not available. This project fills that gap.

> **Unofficial build.** This is an independent community build of the open-source
> [Jellyfin](https://github.com/jellyfin/jellyfin) server. It is **not affiliated with or
> supported by the Jellyfin project**, which dropped 32-bit ARM in 10.11. Please report
> problems here, not to Jellyfin.

## Do I need this?

| Your Termux (`dpkg --print-architecture`) | Use |
|---|---|
| `arm` (32-bit) | **this project** |
| `aarch64` (64-bit) | the official package: `pkg install jellyfin-server` |

## Install

Requirements:
* 32-bit Android 7 or newer.
* [Termux](https://f-droid.org/packages/com.termux/) from F-Droid or GitHub, not the old
  Play Store version.
* About 1 GB of free storage and Wi-Fi.

In Termux:

```sh
termux-setup-storage                 # tap "Allow" so Jellyfin can read your media
pkg install -y curl
cd ~
curl -LO https://github.com/savadks95/Jellyfin-For-32bit-Android/releases/download/v12.4-1/jellyfin-32bit-android-12.4.tar.gz
tar xzf jellyfin-32bit-android-12.4.tar.gz
cd jellyfin-32bit-android
sh install.sh                        # or: sh install.sh --boot  (auto-start, needs Termux:Boot)
```

The first install downloads about 150 MB (a small Debian system and FFmpeg) and takes
5–15 minutes. Then open the address it prints, for example `http://192.168.x.x:8096`, on any
device in your Wi-Fi (or `http://127.0.0.1:8096` on the phone) and finish Jellyfin's setup
wizard.

* **Media folders:** your phone storage is `/sdcard` (for example `/sdcard/Movies`). SD
  cards and USB drives are under `/storage/XXXX-XXXX`.
* **Watching:** use the Jellyfin apps (Android, Android TV, iOS, smart TVs), Findroid,
  Kodi, or any web browser.

### Everyday commands (in Termux)

| Command | What it does |
|---|---|
| `jellyfin start` | start in the background and print the addresses |
| `jellyfin stop` | stop cleanly |
| `jellyfin restart` | stop, then start |
| `jellyfin status` | is it running? |
| `jellyfin logs` | live log (Ctrl+C to leave; the server keeps running) |
| `jellyfin run` | run in the foreground (Ctrl+C stops it) |

To update, download a newer release and run `sh install.sh` again. Your users, libraries
and watch history (in `/var/lib/jellyfin` inside Debian) are kept.

### Keep Android from killing it

* Settings → Apps → Termux → Battery: **No restrictions**. On MIUI, also turn on **Autostart**.
* Lock Termux in the recent-apps screen.
* `jellyfin start` takes a Termux wake lock so the CPU keeps running with the screen off.

## How it works

1. Microsoft's .NET does not run on Android's own C library (Bionic) on 32-bit ARM. That is
   why Termux's .NET and Jellyfin packages exclude `arm`. .NET does support 32-bit ARM
   **Linux** with glibc.
2. `install.sh` uses **proot-distro** to install a small **32-bit Debian (armhf)** inside
   Termux, with no root needed.
3. It installs FFmpeg from Debian and copies in a self-contained **linux-arm** build of
   Jellyfin 12.4. That build is compiled from the official
   [v12.4 source](https://github.com/jellyfin/jellyfin/tree/v12.4), plus the official
   jellyfin-web 12.4.
4. **One fix was needed on real hardware.** .NET's prebuilt launcher (the `jellyfin`
   executable, Microsoft's "apphost") crashes inside the dynamic linker under proot.
   * It is replaced by [`termux/jellyfin-host.c`](termux/jellyfin-host.c), about 40 lines of
     C that do the same job: load `libhostfxr.so` and call .NET's documented
     `hostfxr_main_startupinfo`.
   * Like Microsoft's launcher, it links `libm`/`libstdc++`/`libgcc_s`, because SQLite's
     native library relies on that.
   * `termux/jellyfin-host.armhf` is that file compiled with Debian 13's gcc on armhf. It
     needs glibc 2.34 or newer.

### Settings chosen for phones

| Setting | Value | Why |
|---|---|---|
| .NET GC heap limit | 768 MB (`JELLYFIN_HEAP_HEX=30000000`) | 32-bit .NET under proot otherwise fails with "GC heap initialization failed". For 2–3 GB phones: `export JELLYFIN_HEAP_HEX=20000000` before `jellyfin start`. |
| `--nonetchange` | on | Android doesn't let apps watch network interfaces. |
| .NET W^X | off | Its memory double-mapping is unreliable under proot. |
| Transcoding | preset superfast, CRF 25, throttling and segment deletion on | Keeps CPU and storage use low. Change in Dashboard → Playback → Transcoding. |

## Compared with regular Jellyfin

Everything Jellyfin does works: the web UI, apps, users, metadata, subtitles, SyncPlay,
plugins, music and photos. The exceptions:

| | Regular Jellyfin | This build |
|---|---|---|
| Hardware transcoding (NVENC, QSV, VAAPI, …) | ✅ | ❌ the phone's video hardware isn't reachable from Linux in Termux |
| Software transcoding | ✅ | ⚠️ about one 720p stream (57 fps measured on a Helio G80); prefer clients that direct play |
| FFmpeg | jellyfin-ffmpeg | Debian's FFmpeg 7.1 (lacks some of Jellyfin's extra filters) |
| Runs as a service with auto-restart | ✅ | ❌ `jellyfin start` / Termux:Boot; Android may kill it |
| Network change detection | ✅ | ❌ restart Jellyfin if the phone's IP changes |
| Official support and updates | ✅ | ❌ community build; update by installing a newer release |

## Tested on

Redmi 9 (M2006C3MII), Android 10, 32-bit Termux, proot-distro 5.10, Debian 13 armhf:
* install, start and update all work;
* the first start takes about 1.5 minutes (database creation);
* it uses about 230 MB of RAM;
* the web UI is reachable from the LAN;
* 720p software encoding runs at 1.9× real time.

Other devices should work if they run 32-bit Android 7+ with an ARMv7 or newer CPU.
ARMv6 CPUs are not supported, because Debian armhf and .NET both need ARMv7.

## Build it yourself (Windows)

Requirements: Python 3, Git, and a clone of `https://github.com/jellyfin/jellyfin`.

```sh
python tools/build.py --clone path/to/jellyfin    # exports tag v12.4 with git archive; the clone is not changed
```

* Put these in `.build/downloads` first (see the header of `tools/build.py`):
  * the .NET 10 SDK zip (SHA-512 checked);
  * the official `jellyfin_12.4.tar.xz`, used only for its prebuilt web UI (MD5 checked).
* The script checks that every native file in the result is 32-bit ARM.
* Other options:
  * `--test-win` also builds a Windows copy for a local test.
  * `--package-only` repackages script changes without recompiling.

## Files

```
termux/install.sh          run in Termux: sets up Debian, installs, starts
termux/debian-setup.sh     runs inside Debian: packages, /opt/jellyfin, first-run config
termux/jellyfin-run        inside Debian: starts the server with the phone settings
termux/jellyfin            the Termux "jellyfin" command
termux/encoding.xml        first-run transcoding defaults
termux/jellyfin-host.c     replacement for .NET's launcher
termux/jellyfin-host.armhf that program, compiled for armhf
tools/build.py             builds dist/jellyfin-32bit-android-12.4.tar.gz
```

## License and source code

This project's scripts and launcher are GPL-2.0, the same license as Jellyfin.

The release archive contains:
* **Jellyfin server 12.4**, GPL-2.0, built unmodified from commit
  [`83d0d0e`](https://github.com/jellyfin/jellyfin/commit/83d0d0e7f76e23e2e085c8ff67d28b772d35967d);
* **jellyfin-web 12.4** (GPL-2.0);
* the **.NET 10 runtime** (MIT), SkiaSharp (MIT), SQLite (public domain) and PDFium (BSD).

The exact Jellyfin source code is attached to each release.

FFmpeg is not bundled; it is installed from Debian on the device.

Jellyfin is the work of [its contributors](https://github.com/jellyfin/jellyfin/blob/master/CONTRIBUTORS.md).

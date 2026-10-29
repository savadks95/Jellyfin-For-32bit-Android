"""Builds Jellyfin 12.4 for 32-bit ARM Linux (linux-arm) and packages it for Termux.

Input:
  a clone of github.com/jellyfin/jellyfin  tag v12.4 is exported with git archive; the clone is not changed.
                                          Path: --clone DIR, or $JELLYFIN_SRC, or ../Jellyfin_Orginal/jellyfin
  .build/downloads/dotnet-sdk-*.zip       .NET 10 SDK for Windows (portable, not installed system-wide)
  .build/downloads/jellyfin_12.4.tar.xz   official platform-neutral 12.4 package: only its jellyfin-web is used
Output:
  dist/jellyfin-32bit-android-12.4.tar.gz unpack in Termux and run: sh install.sh

Usage: python tools/build.py [--clone DIR] [--tag v12.4] [--test-win] [--package-only]   (--package-only: repackage scripts, no recompile)
"""
import glob
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLONE = os.environ.get("JELLYFIN_SRC") or os.path.join(os.path.dirname(ROOT), "Jellyfin_Orginal", "jellyfin")
B = os.path.join(ROOT, ".build")
DL = os.path.join(B, "downloads")
SDK_ZIP = "dotnet-sdk-10.0.403-win-x64.zip"
SDK_SHA512 = "7a114c318fa7f1d9822991b534b2814d0e78386ceda816b371f5141acefe741d87ccb606ede06cadac8f9ac5070e32b708a67bbd1619ff5e5a7858a27874ef48"
WEB_TAR = "jellyfin_12.4.tar.xz"
WEB_MD5 = "08d9518c5d0e9193f2d158ad500732f4"  # as listed on repo.jellyfin.org
SCRIPTS = ["install.sh", "debian-setup.sh", "jellyfin-run", "jellyfin", "encoding.xml"]
EXECUTABLE_SCRIPTS = {"install.sh", "debian-setup.sh", "jellyfin-run", "jellyfin"}


def log(m):
    print("==> " + m, flush=True)


def run(cmd, **kw):
    print("    " + " ".join(cmd)[:300], flush=True)
    r = subprocess.run(cmd, **kw)
    if r.returncode:
        sys.exit("failed: %s" % cmd[0])


def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sdk():
    root = os.path.join(B, "dotnet")
    exe = os.path.join(root, "dotnet.exe")
    if os.path.isfile(exe):
        return exe
    z = os.path.join(DL, SDK_ZIP)
    if not os.path.isfile(z):
        sys.exit("missing %s (download from builds.dotnet.microsoft.com)" % z)
    log("Verifying and unpacking the .NET SDK")
    if digest(z, "sha512") != SDK_SHA512:
        sys.exit("SHA-512 mismatch for " + SDK_ZIP)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(root)
    return exe


def export_source(tag):
    src = os.path.join(B, "src")
    stamp = os.path.join(src, ".tag")
    if os.path.isfile(stamp) and open(stamp).read().strip() == tag:
        return src
    log("Exporting %s from %s (read-only)" % (tag, CLONE))
    shutil.rmtree(src, ignore_errors=True)
    os.makedirs(src)
    data = subprocess.run(["git", "-C", CLONE, "archive", "--format=tar", tag], capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(src)
    open(stamp, "w").write(tag)
    return src


def env():
    e = dict(os.environ)
    e.update({
        "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        "DOTNET_NOLOGO": "1",
        "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
        "DOTNET_CLI_HOME": os.path.join(B, "cli-home"),
        "NUGET_PACKAGES": os.path.join(B, "nuget"),   # keep packages out of the user profile
        "DOTNET_ROOT": os.path.join(B, "dotnet"),
    })
    return e


def publish(dotnet, src, rid):
    out = os.path.join(B, "publish-" + rid)
    shutil.rmtree(out, ignore_errors=True)
    log("Compiling Jellyfin.Server for %s (self-contained)" % rid)
    run([dotnet, "publish", os.path.join(src, "Jellyfin.Server", "Jellyfin.Server.csproj"),
         "--configuration", "Release", "--runtime", rid, "--self-contained", "true",
         "-p:DebugType=None", "-p:DebugSymbols=false", "-p:GenerateDocumentationFile=false",
         "--output", out], env=env(), cwd=src)
    return out


def add_web(server_dir):
    tar = os.path.join(DL, WEB_TAR)
    if not os.path.isfile(tar):
        sys.exit("missing " + tar)
    if digest(tar, "md5") != WEB_MD5:
        sys.exit("MD5 mismatch for " + WEB_TAR)
    log("Adding jellyfin-web 12.4 from the official package")
    web = os.path.join(server_dir, "jellyfin-web")
    shutil.rmtree(web, ignore_errors=True)
    with tarfile.open(tar) as t:
        for m in t.getmembers():
            parts = m.name.split("/")
            if "jellyfin-web" not in parts:
                continue
            rel = "/".join(parts[parts.index("jellyfin-web") + 1:])
            if not rel or not m.isfile():
                continue
            dst = os.path.join(web, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with t.extractfile(m) as fsrc, open(dst, "wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
    if not os.path.isfile(os.path.join(web, "index.html")):
        sys.exit("jellyfin-web not found in " + WEB_TAR)


ELF_MACHINES = {40: "ARM 32-bit", 183: "AArch64", 62: "x86-64", 3: "x86"}


def check_arm(server_dir):
    log("Checking that native files are 32-bit ARM")
    bad = []
    found = []
    for root, _, files in os.walk(server_dir):
        for f in files:
            p = os.path.join(root, f)
            with open(p, "rb") as fh:
                head = fh.read(20)
            if head[:4] != b"\x7fELF":
                continue
            machine = int.from_bytes(head[18:20], "little")
            rel = os.path.relpath(p, server_dir)
            found.append(rel)
            if head[4] != 1 or machine != 40:
                bad.append("%s (%s)" % (rel, ELF_MACHINES.get(machine, machine)))
    for need in ["jellyfin", "libSkiaSharp.so", "libe_sqlite3.so", "libcoreclr.so"]:
        if not any(os.path.basename(f) == need for f in found):
            sys.exit("missing native file for linux-arm: " + need)
    if bad:
        sys.exit("non-ARM32 native files: " + ", ".join(bad))
    print("    %d native ELF files, all 32-bit ARM" % len(found))


def package(server_dir, version):
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", "jellyfin-32bit-android-%s.tar.gz" % version)
    log("Packaging " + out)
    with open(os.path.join(server_dir, "VERSION"), "w", newline="\n") as f:
        f.write("Jellyfin %s, linux-arm self-contained, built from github.com/jellyfin/jellyfin tag v%s\n" % (version, version))

    def add(t, path, arc, mode):
        info = t.gettarinfo(path, arc)
        info.mode = mode
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        if info.isfile():
            data = open(path, "rb").read()
            if os.path.basename(path) in SCRIPTS:
                data = data.replace(b"\r\n", b"\n")  # scripts must have Unix line endings
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
        else:
            t.addfile(info)

    with tarfile.open(out, "w:gz", compresslevel=6) as t:
        top = "jellyfin-32bit-android"
        add(t, os.path.join(ROOT, "termux"), top, 0o755)
        for s in SCRIPTS:
            add(t, os.path.join(ROOT, "termux", s), top + "/" + s, 0o755 if s in EXECUTABLE_SCRIPTS else 0o644)
        add(t, os.path.join(ROOT, "README.md"), top + "/README.md", 0o644)
        for root, dirs, files in os.walk(server_dir):
            dirs.sort()
            rel_root = os.path.relpath(root, server_dir).replace("\\", "/")
            arc_root = top + "/server" + ("" if rel_root == "." else "/" + rel_root)
            add(t, root, arc_root, 0o755)
            for f in sorted(files):
                p = os.path.join(root, f)
                with open(p, "rb") as fh:
                    elf = fh.read(4) == b"\x7fELF"
                executable = elf and not f.endswith(".so") and ".so." not in f
                add(t, p, arc_root + "/" + f, 0o755 if executable else 0o644)
    print("    %.1f MB" % (os.path.getsize(out) / 1048576))
    return out


def use_custom_host(server_dir):
    """Replaces Microsoft's apphost, which crashes in ld.so under Termux's proot.

    termux/jellyfin-host.armhf is termux/jellyfin-host.c compiled with Debian trixie's gcc
    inside the phone's armhf proot (see the command in the .c file).
    """
    src = os.path.join(ROOT, "termux", "jellyfin-host.armhf")
    if not os.path.isfile(src):
        sys.exit("missing " + src + " (compile termux/jellyfin-host.c in the armhf Debian)")
    log("Using termux/jellyfin-host.armhf as the 'jellyfin' launcher")
    shutil.copyfile(src, os.path.join(server_dir, "jellyfin"))


def main():
    global CLONE
    args = sys.argv[1:]
    tag = args[args.index("--tag") + 1] if "--tag" in args else "v12.4"
    if "--clone" in args:
        CLONE = os.path.abspath(args[args.index("--clone") + 1])
    if "--package-only" in args:
        # scripts changed only: reuse the last linux-arm build
        server = os.path.join(B, "publish-linux-arm")
        use_custom_host(server)
        check_arm(server)
        package(server, tag.lstrip("v"))
        log("Done")
        return
    dotnet = sdk()
    src = export_source(tag)
    server = publish(dotnet, src, "linux-arm")
    add_web(server)
    use_custom_host(server)
    check_arm(server)
    package(server, tag.lstrip("v"))
    if "--test-win" in args:
        win = publish(dotnet, src, "win-x64")
        add_web(win)
        log("Windows test build in " + win)
    log("Done")


if __name__ == "__main__":
    main()

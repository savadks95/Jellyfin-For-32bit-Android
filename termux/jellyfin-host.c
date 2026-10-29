/*
 * Minimal replacement for .NET's prebuilt "apphost" launcher (/opt/jellyfin/jellyfin).
 *
 * Microsoft's linux-arm apphost crashes with SIGSEGV inside the dynamic linker under
 * Termux's proot (even `ld.so --list` on it crashes), while every .NET library loads
 * fine. The apphost only locates libhostfxr.so next to itself and calls the documented
 * hosting entry point hostfxr_main_startupinfo(), so this program does exactly that.
 *
 * It must be named like the app's dll ("jellyfin" next to "jellyfin.dll"): hostfxr then
 * treats it as a self-contained apphost.
 *
 * It must also link the same libraries as Microsoft's apphost (libstdc++, libm, libgcc_s)
 * even though it does not use them: they land in the process's global symbol scope, and
 * SQLitePCLRaw's libe_sqlite3.so relies on that (it calls trunc() without linking libm).
 * Build inside the armhf Debian (debian-setup.sh does this):
 *   gcc -O2 -o jellyfin jellyfin-host.c -Wl,--no-as-needed -lm -ldl \
 *       /usr/lib/arm-linux-gnueabihf/libstdc++.so.6 /usr/lib/arm-linux-gnueabihf/libgcc_s.so.1
 */
#include <dlfcn.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

typedef int (*hostfxr_main_startupinfo_fn)(const int argc, const char **argv, const char *host_path,
                                           const char *dotnet_root, const char *app_path);

int main(int argc, const char **argv)
{
    char self[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", self, sizeof(self) - 1);
    if (n <= 0) {
        perror("readlink /proc/self/exe");
        return 1;
    }
    self[n] = '\0';

    char dir[PATH_MAX];
    strcpy(dir, self);
    char *slash = strrchr(dir, '/');
    if (slash == NULL) {
        fprintf(stderr, "unexpected executable path: %s\n", self);
        return 1;
    }
    *slash = '\0';
    const char *name = slash + 1;

    char fxr[PATH_MAX];
    char app[PATH_MAX];
    snprintf(fxr, sizeof(fxr), "%s/libhostfxr.so", dir);
    snprintf(app, sizeof(app), "%s/%s.dll", dir, name);

    void *lib = dlopen(fxr, RTLD_NOW | RTLD_LOCAL);
    if (lib == NULL) {
        fprintf(stderr, "cannot load %s: %s\n", fxr, dlerror());
        return 1;
    }
    hostfxr_main_startupinfo_fn start = (hostfxr_main_startupinfo_fn)dlsym(lib, "hostfxr_main_startupinfo");
    if (start == NULL) {
        fprintf(stderr, "hostfxr_main_startupinfo not found in %s\n", fxr);
        return 1;
    }
    /* self-contained app: the runtime root is the app folder */
    return start(argc, argv, self, dir, app);
}

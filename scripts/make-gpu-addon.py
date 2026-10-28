#!/usr/bin/env python3
"""Pack the owner-built Adreno Metal plugin into a GPU addon file for the boot payload.

  make-gpu-addon.py [--publish] [--clients NAME,...] [--wallpaper DIR] [--prime-list FILE] OUTPUT

The files are the ones add-gpu-plugin-data.py stages into a Data seed, with the same paths below /private/var/ngpu and the same modes:
addons/NativeAdrenoMetal.bundle/*, addons/NativeAdrenoMetal.publish (--publish), addons/NativeAdrenoMetal.clients (--clients),
bin/adrenoprobed and daemons/*.plist. --wallpaper adds the files of DIR (scripts/make-wallpaper-overlay.py) as wallpaper/*, which the
kernel mounts over the default wallpaper's layered animation. --prime-list adds FILE (the absolute paths of the OS image's .metallib
files, one per line) as addons/NativeAdrenoMetal.primelist, the libraries the render server compiles ahead (PrimeShaders.h). The payload carries the file next to the kernel (unixnu build payload --gpu-addon), the loader
hands it to the kernel as /chosen/memory-map/GpuAddon, and the kernel writes every file whose content or mode differs into the mounted
Data volume before its addon mounts (sheng-gpu-addon=1). The Data seed then no longer changes with the plugin, so its persistent store
(whose identity is the seed's content) survives a plugin rebuild. The kernel creates missing directories.

The data of every file is zlib-compressed: the payload FAT (the boot image's ramdisk) has to stay at 192 MiB, which the tablet's boot
loader accepts (a 256 MiB ramdisk does not start the firmware), and the kernel and the Data seed already take most of it.

Layout, little endian: "NGPUADD2", u32 count, u32 0, u64 total bytes; per file u32 path bytes (with its NUL, at most 160), u32 mode,
u64 size, u64 compressed size, the path padded to 8 bytes, the zlib stream padded to 8 bytes."""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'build/adreno-metal-plugin'
BUNDLE = PLUGIN / 'NativeAdrenoMetal.bundle'


def pad(data):
    return data + bytes(-len(data) % 8)


def main():
    args = [a for a in sys.argv[1:] if a != '--publish']
    publish = len(args) != len(sys.argv) - 1
    force_generic = '--force-generic' in args
    args = [a for a in args if a != '--force-generic']
    clients = None
    wallpaper = None
    plugin = PLUGIN
    if '--plugin-dir' in args:
        at = args.index('--plugin-dir')
        plugin = Path(args[at + 1]).resolve()
        del args[at:at + 2]
        if not (plugin / 'NativeAdrenoMetal.bundle' / 'NativeAdrenoMetal').is_file():
            sys.exit('--plugin-dir takes a build/adreno-metal-plugin output directory')
    bundle = plugin / 'NativeAdrenoMetal.bundle'
    if '--wallpaper' in args:
        at = args.index('--wallpaper')
        wallpaper = Path(args[at + 1])
        del args[at:at + 2]
        if not wallpaper.is_dir():
            sys.exit('--wallpaper takes a directory')
    prime_list = None
    if '--prime-list' in args:
        at = args.index('--prime-list')
        prime_list = Path(args[at + 1])
        del args[at:at + 2]
        lines = prime_list.read_text().split()
        if not lines or any(not line.startswith('/') or not line.endswith('.metallib') for line in lines):
            sys.exit('--prime-list takes a file of absolute .metallib paths')
    daemon_plist = None
    if '--daemon-plist' in args:
        at = args.index('--daemon-plist')
        daemon_plist = args[at + 1]
        del args[at:at + 2]
        if not daemon_plist.endswith('.plist'):
            sys.exit('--daemon-plist takes the job plist file name')
    if '--clients' in args:
        at = args.index('--clients')
        clients = [name for name in args[at + 1].split(',') if name]
        del args[at:at + 2]
        if not clients or any(not all(c.isalnum() or c in '._-*' for c in name) for name in clients):
            sys.exit('--clients takes process names separated by commas')
    if len(args) != 1:
        sys.exit(__doc__)
    output = Path(args[0]).resolve()
    if output.exists():
        sys.exit('Refuse to overwrite ' + str(output))
    if not (bundle / 'NativeAdrenoMetal').is_file():
        sys.exit('Build the plugin first: python3 scripts/build-adreno-metal-plugin.py')
    files = []
    for path in sorted(p for p in bundle.rglob('*') if p.is_file()):
        mode = 0o755 if path.name in ('NativeAdrenoMetal', 'libvulkan_freedreno.dylib') else 0o644
        files.append(('addons/NativeAdrenoMetal.bundle/' + path.relative_to(bundle).as_posix(), mode, path.read_bytes()))
    if publish:
        files.append(('addons/NativeAdrenoMetal.publish', 0o644, b'1\n'))
    if force_generic:
        files.append(('addons/NativeAdrenoMetal.generic', 0o644, b'1\n'))
    if clients:
        files.append(('addons/NativeAdrenoMetal.clients', 0o644, ('\n'.join(clients) + '\n').encode()))
    if prime_list:
        files.append(('addons/NativeAdrenoMetal.primelist', 0o644, prime_list.read_bytes()))
    files.append(('bin/adrenoprobed', 0o755, (plugin / 'adrenoprobed').read_bytes()))
    for plist in sorted(plugin.glob('*.plist')):
        if plist.name.endswith('-entitlements.plist'):   # build input, not a launchd job
            continue
        if daemon_plist is not None and plist.name != daemon_plist:
            continue
        files.append(('daemons/' + plist.name, 0o644, plist.read_bytes()))
    if wallpaper:
        for path in sorted(p for p in wallpaper.rglob('*') if p.is_file()):
            files.append(('wallpaper/' + path.relative_to(wallpaper).as_posix(), 0o644, path.read_bytes()))
    body = b''
    for name, mode, data in files:
        encoded = name.encode() + b'\0'
        if len(encoded) > 160 or '..' in name.split('/') or name.startswith('/'):
            sys.exit('Bad addon path ' + name)
        packed = zlib.compress(data, 9)
        body += struct.pack('<IIQQ', len(encoded), mode, len(data), len(packed)) + pad(encoded) + pad(packed)
    blob = b'NGPUADD2' + struct.pack('<IIQ', len(files), 0, 24 + len(body)) + body
    output.write_bytes(blob)
    for name, mode, data in files:
        print(f'{mode:o} {len(data):>10} {name}')
    print(f'{output}: {len(files)} files, {len(blob)} bytes')


if __name__ == '__main__':
    main()

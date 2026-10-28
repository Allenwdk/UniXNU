#!/usr/bin/env python3
"""Build the owner-signed Adreno userspace pieces for ARM64/iOS 17: the Metal plugin bundle (drivers/NativeMetal/NativeAdrenoMetalPlugin.mm)
and the launchd probe daemon with its job plist (NativeAdrenoProbeDaemon.cpp).

Output (ignored, never committed): build/adreno-metal-plugin/NativeAdrenoMetal.bundle with a 4 KiB-page ad-hoc signature, and
trust.json with its CDHash. The bundle is staged into the Data seed by add-gpu-plugin-data.py and trusted through an extra
owner trust module (make-owner-trust-bundle.py); neither changes the original trust modules, AMFI or any Apple signature."""
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Host build environment (the Linux XNU toolchain): the CLT tools (clang/strip through xcrun),
# rustup's pinned cargo for the bridge, and an iPhoneOS SDK. macOS needs none of this.
for tool_dir in (Path.home() / '.cargo/bin', Path('/opt/unixnu-linux/CommandLineTools/usr/bin')):
    if tool_dir.is_dir():
        os.environ['PATH'] = str(tool_dir) + os.pathsep + os.environ.get('PATH', '')
OUT = ROOT / 'build/adreno-metal-plugin'
bundle = OUT / 'NativeAdrenoMetal.bundle'
if OUT.exists():
    shutil.rmtree(OUT)
bundle.mkdir(parents=True)
def is_sdk(path):
    return bool(path) and ((Path(path) / 'SDKSettings.plist').is_file() or (Path(path) / 'SDKSettings.json').is_file())
sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
if not is_sdk(sdk):
    candidates = [c for c in sorted(Path.home().glob('.cache/ios-sdks/iPhoneOS*.sdk')) if is_sdk(str(c))]
    if not candidates:
        raise SystemExit('no iPhoneOS SDK: install one under ~/.cache/ios-sdks (the kernel fakeroot is not one)')
    sdk = str(candidates[-1])
    os.environ['UNIXNU_SDKROOT'] = sdk  # the xcrun shim answers -show-sdk-path from it
base = ['xcrun', 'clang', '-target', 'arm64-apple-ios17.0', '-isysroot', sdk, '-O2', '-g', '-Wall', '-Wextra', '-Werror',
        '-fstack-protector-strong']
if sys.platform != 'darwin':
    base += ['-fuse-ld=lld', '-Wno-unused-command-line-argument']
VULKAN_INCLUDE = ROOT / '.cache/mesa-work/include'
TURNIP = ROOT / 'build/mesa-tu-ios/src/freedreno/vulkan/libvulkan_freedreno.dylib'
if not TURNIP.is_file():
    raise SystemExit('Build Turnip first: python3 scripts/build-turnip-darwin.py --target ios')
LDID = os.environ.get('LDID') or next((str(c) for c in (Path.home() / '.cache/ldid/ldid', Path(shutil.which('ldid') or '')) if c.is_file()), None)

def signed_target(path):
    # ldid takes Mach-O files; a .bundle directory means its main executable (the
    # kernel's trust sees that file's CodeDirectory either way).
    path = Path(path)
    return path / path.name[:-len('.bundle')] if path.is_dir() and path.name.endswith('.bundle') else path

def sign(path, identifier, entitlements=None):
    path = signed_target(path)
    if sys.platform == 'darwin':
        command = ['codesign', '--force', '--sign', '-', '--pagesize', '4096', '--identifier', identifier]
        if entitlements: command += ['--entitlements', str(entitlements)]
        subprocess.run(command + [str(path)], check=True)
    else:
        if not LDID: raise SystemExit('ldid is required to sign on this host (~/.cache/ldid/ldid)')
        subprocess.run([LDID, *(['-S' + str(entitlements)] if entitlements else ['-S']), '-I' + identifier, str(path)], check=True)

def signed_cdhash(path):
    path = signed_target(path)
    if sys.platform == 'darwin':
        detail = subprocess.run(['codesign', '--display', '--verbose=4', str(path)], capture_output=True, text=True, check=True).stderr
        assert re.search(r'^Page size=4096$', detail, re.M), 'the signature must use 4 KiB pages'
    else:
        if not LDID: raise SystemExit('ldid is required to read signatures on this host')
        detail = subprocess.run([LDID, '-h', str(path)], capture_output=True, text=True, check=True).stdout
    return re.search(r'^CDHash=([a-f0-9]{40})$', detail, re.M)[1]

def signed_entitlements(path):
    if sys.platform == 'darwin':
        return subprocess.check_output(['codesign', '-d', '--entitlements', ':-', str(path)], stderr=subprocess.DEVNULL)
    return subprocess.check_output([LDID, '-e', str(path)])

def verify(path):
    path = signed_target(path)
    if sys.platform == 'darwin':
        subprocess.run(['codesign', '--verify', '--strict', str(path)], check=True)
    else:
        subprocess.run([LDID, '-h', str(path)], check=True, stdout=subprocess.DEVNULL)

subprocess.run(['python3', ROOT / 'scripts/gen-turnip-smoke-shaders.py'], check=True)
# Turnip's first submission, recorded on the host, for the plugin's prefix replay (build/turnip-smoke/TurnipReplay.h).
# The recording runs the macOS host simulation; a Linux host builds the plugin without it (the header is optional).
if sys.platform == 'darwin':
    subprocess.run(['python3', ROOT / 'scripts/gen-turnip-replay.py'], check=True)
else:
    (ROOT / 'build/turnip-smoke/TurnipReplay.h').unlink(missing_ok=True)
subprocess.run(['python3', ROOT / 'scripts/build-native-metal-bridge.py', '--target', 'ios'], check=True)
BRIDGE = ROOT / 'build/native-metal-bridge/ios/libnative_metal_bridge.a'
pm4 = OUT / 'AdrenoPM4.o'
subprocess.run([*base, '-std=c11', '-c', ROOT / 'kits/AdrenoPM4/AdrenoPM4.c', '-o', pm4], check=True)
exe = bundle / 'NativeAdrenoMetal'
subprocess.run([*(['xcrun', 'clang++'] + base[2:]), '-std=c++17', '-fobjc-arc', '-Wno-deprecated-declarations', '-bundle',
                '-I', ROOT / 'drivers/NativeAdreno', '-I', ROOT / 'kits/AdrenoPM4', '-I', VULKAN_INCLUDE, '-I', ROOT / 'build/turnip-smoke',
                '-x', 'objective-c++', ROOT / 'drivers/NativeMetal/NativeAdrenoMetalPlugin.mm',
                ROOT / 'drivers/NativeMetal/NativeBridgeMetalFrontend.mm', '-x', 'none', pm4, BRIDGE,
                '-Wl,-dead_strip', '-lobjc', '-framework', 'Foundation', '-framework', 'Metal', '-framework', 'IOSurface', '-o', exe], check=True)
subprocess.run(['xcrun', 'strip', '-x', exe], check=True)
# The linker writes the debug symbols of the Rust bridge next to the executable; keep them beside the bundle, not in the image.
symbols = OUT / 'NativeAdrenoMetal.dSYM'
shutil.rmtree(symbols, ignore_errors=True)
if (bundle / 'NativeAdrenoMetal.dSYM').exists():
    shutil.move(bundle / 'NativeAdrenoMetal.dSYM', symbols)
# Turnip (the real Mesa Vulkan driver with the native Darwin kernel backend) travels inside the plugin bundle, signed on its own with 4 KiB pages so its
# CDHash can be trusted like the plugin's. It is signed before the bundle so the bundle's resource seal covers the final bytes.
turnip_lib = bundle / 'libvulkan_freedreno.dylib'
shutil.copyfile(TURNIP, turnip_lib)
subprocess.run(['xcrun', 'strip', '-x', turnip_lib], check=True)
sign(turnip_lib, 'org.blu-sharky.turnip')
turnip_cdhash = signed_cdhash(turnip_lib)
(bundle / 'Info.plist').write_bytes(plistlib.dumps(dict(
    CFBundleIdentifier='org.blu-sharky.NativeAdrenoMetal', CFBundleExecutable='NativeAdrenoMetal', CFBundlePackageType='BNDL',
    CFBundleVersion='1', CFBundleShortVersionString='1', NSPrincipalClass='NativeAdrenoMetalDevice',
    MinimumOSVersion='17.0'), fmt=plistlib.FMT_XML))
sign(bundle, 'org.blu-sharky.NativeAdrenoMetal')
verify(bundle)
cdhash = signed_cdhash(bundle)
header = exe.read_bytes()[:16]
magic, cputype, subtype = int.from_bytes(header[0:4], 'little'), int.from_bytes(header[4:8], 'little'), int.from_bytes(header[8:12], 'little')
assert (magic, cputype, subtype & 0xffffff) == (0xfeedfacf, 0x100000c, 0), 'expected an ordinary ARM64 (subtype 0) Mach-O'
# The probe daemon (launchd starts it as an owner job). The original platform sandbox policy refuses IOServiceOpen for any user-client class
# a process has not been granted (the same refusal an unentitled consumer got in the offline owner tests), so it carries exactly the grant that
# worked there: com.apple.security.iokit-user-client-class naming the one class it opens, plus no-container.
entitlements = OUT / 'adrenoprobed-entitlements.plist'
entitlements.write_bytes(plistlib.dumps({'com.apple.private.security.no-container': True,
                                         'com.apple.security.iokit-user-client-class': ['AGXDeviceUserClient']}))
daemon = OUT / 'adrenoprobed'
subprocess.run(['xcrun', 'clang++', *base[2:], '-std=c++17', '-I', ROOT / 'drivers/NativeAdreno', '-I', ROOT / 'kits/AdrenoPM4', '-I', VULKAN_INCLUDE,
                '-I', ROOT / 'build/turnip-smoke',
                ROOT / 'drivers/NativeMetal/NativeAdrenoProbeDaemon.cpp', '-x', 'objective-c++', '-fobjc-arc',
                ROOT / 'drivers/NativeMetal/NativeOsLogExport.mm', '-x', 'none', pm4, '-framework', 'Foundation', '-lz', '-o', daemon], check=True)
sign(daemon, 'org.blu-sharky.adrenoprobed', entitlements)
actual = plistlib.loads(signed_entitlements(daemon))
assert actual == plistlib.loads(entitlements.read_bytes()), 'the signed entitlement set differs'
verify(daemon)
daemon_cdhash = signed_cdhash(daemon)
(OUT / 'org.blu-sharky.adrenoprobed.plist').write_bytes(plistlib.dumps(dict(
    Label='org.blu-sharky.adrenoprobed', ProgramArguments=['/private/var/ngpu/bin/adrenoprobed'], RunAtLoad=True,
    KeepAlive=False, ThrottleInterval=30, UserName='root', StandardErrorPath='/dev/null'), fmt=plistlib.FMT_XML))
# launchd may enumerate the directory without our overlay's new names, so the same job is also offered under the name of an existing,
# non-essential RunAtLoad job (the display FDR loader: root, no MachServices): the overlay answers a lookup of that name first.
(OUT / 'com.apple.iomfb_fdr_loader.plist').write_bytes(plistlib.dumps(dict(
    Label='com.apple.iomfb_fdr_loader', ProgramArguments=['/private/var/ngpu/bin/adrenoprobed'], RunAtLoad=True,
    KeepAlive=False, LimitLoadToSessionType='System', ProcessType='Interactive', StandardErrorPath='/dev/null'), fmt=plistlib.FMT_XML))
# Bluetooth is unused on this board; its job is RunAtLoad and was seen to be exec'd on every boot (the exec observer lists bluetoothd).
(OUT / 'com.apple.bluetoothd.plist').write_bytes(plistlib.dumps(dict(
    Label='com.apple.bluetoothd', ProgramArguments=['/private/var/ngpu/bin/adrenoprobed'], RunAtLoad=True, KeepAlive=False,
    ProcessType='Interactive', StandardErrorPath='/dev/null'), fmt=plistlib.FMT_XML))
(OUT / 'trust.json').write_text(json.dumps(dict(cdhash=cdhash, daemon_cdhash=daemon_cdhash, turnip_cdhash=turnip_cdhash, bundle='NativeAdrenoMetal.bundle',
    executable_bytes=exe.stat().st_size, purpose='owner-built plugin and probe daemon; trusted only through an extra owner trust module'),
    indent=2) + '\n')
print('PASS: Adreno plugin bundle and probe daemon built and 4K-signed, CDHashes', cdhash, daemon_cdhash, turnip_cdhash)

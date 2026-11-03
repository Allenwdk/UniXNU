#!/usr/bin/env python3
"""Build a symbol-bearing RELEASE comparison kernel in an isolated output tree."""
import json
import os
import re
import shutil
import hashlib
import argparse
import fnmatch
from pathlib import Path
import subprocess


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree_hash(path):
    """Hash inputs by content; follow SDK header-directory links as the compiler does."""
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    for directory, dirs, files in os.walk(path, followlinks=True):
        dirs[:] = sorted(d for d in dirs if d != '.git')
        for name in sorted(files):
            item = Path(directory) / name
            digest.update(str(item.relative_to(path)).encode() + b'\0')
            digest.update(file_hash(item).encode() + b'\0')
    return digest.hexdigest()


def reusable(final, record, inputs):
    try:
        saved = json.loads(record.read_text())
        return saved['inputs'] == inputs and saved['sha256'] == file_hash(final)
    except (OSError, ValueError, KeyError):
        return False


def linked_objects(directory, lto):
    if lto:
        # XNU splits the final link into non-LTO objects and the code generated
        # by its intermediate LTO link. There is no link.filelist in this mode.
        objects = (directory / 'nonltolink.filelist').read_text().splitlines()
        generated = directory / 'justlto.o'
        objects += [str(p) for p in sorted(generated.glob('*.o'))] if generated.is_dir() else [str(generated)]
    else:
        objects = (directory / 'link.filelist').read_text().splitlines()
        objects += [str(directory / name) for name in
                    ('version.o', 'lastkerneldataconst.o', 'lastkernelconstructor.o')
                    if (directory / name).is_file()]
    return [str(Path(name) if Path(name).is_absolute() else directory / name)
            for name in objects if name.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', required=True, type=Path, help='prepared XNU build tree of the OS profile')
    parser.add_argument('--lto', action='store_true', help='enable the RELEASE default link-time optimization')
    options = parser.parse_args()
    mode = 'lto' if options.lto else 'snapshot'
    root = options.tree.resolve()
    # Prepare XNU's existing Linux adaptations before copying the reference.
    prepare = root / 'scripts/linux/prepare-xnu.py'
    if os.uname().sysname == 'Linux' and prepare.is_file():
        subprocess.run(['python3', str(prepare), 'source'], cwd=root, check=True)
    build_root = root / 'build/xnu/fileset-reference'
    final = build_root / 'mach.release.bcm2837.unstripped.noctf'
    cache_record = final.with_suffix('.json')
    sdk = root / '.cache/fakeroot'
    archives = [root/'build/corecrypto-2023/libcorecrypto_kernel_noasm-namespaced.a']
    forced = [root/f'build/{folder}/{name}' for folder,name in (
        ('libpthread-kernel','libpthread_kernel.a'),('armdt-platform','libArmDTPlatform.a'),('armcpu','libArmCpu.a'))]
    inputs = {
        'mode': mode,
        'script': file_hash(Path(__file__)),
        'source': tree_hash(root / '.cache/xnu-work'),
        'sdk': tree_hash(sdk),
        'archives': {str(p.relative_to(root)): file_hash(p) for p in archives + forced},
        'versions': {name: os.environ.get(name, default) for name, default in (
            ('UNIXNU_IOS_VERSION', '26.0'), ('UNIXNU_XNU_DARWIN', '25.5.0'),
            ('UNIXNU_XNU_VERSION', '12377.121.6'))},
        'compiler': subprocess.check_output(['xcrun', 'clang', '--version'], text=True),
        'environment': {name: value for name, value in os.environ.items()
                        if name.startswith(('XNU_', 'RC_', 'CCC_')) or name in
                        ('CC', 'CXX', 'LD', 'CROSS_CLANG', 'CROSS_EXTRA_FLAGS', 'DARWIN_TRIPLE',
                         'XNU_CLANG_DROP_FLAGS')},
    }
    # ld64 must be built with LTO support on Linux; keep it separate from the
    # installed non-LTO toolchain and include its identity in cache validation.
    lto_linker = os.environ.get('UNIXNU_LTO_LD') if os.uname().sysname == 'Linux' and options.lto else None
    if lto_linker:
        linker_path = Path(lto_linker).resolve(strict=True)
        inputs['linux_lto_linker'] = {'path': str(linker_path), 'sha256': file_hash(linker_path)}
    if lto_linker and os.environ.get('LIBLTO'):
        library_path = Path(os.environ['LIBLTO']).resolve(strict=True)
        inputs['linux_lto_library'] = {'path': str(library_path), 'sha256': file_hash(library_path)}
    if reusable(final, cache_record, inputs):
        print(f'reference inputs and digest match ({mode}): {final}')
        return
    # Separate workspaces prevent non-LTO objects and stale patched sources from
    # being reused after a mode, source, SDK, archive or compiler change.
    key = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    output = build_root / f'{mode}-{key[:16]}'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    source = output / 'source'
    if not source.exists():
        shutil.copytree(root/'.cache/xnu-work', source, symlinks=True,
                        ignore=shutil.ignore_patterns('.git'))
        # The shared tree currently has this observation hook at file scope. The
        # reference build disables observation hooks; repair only its private copy.
        sleh = source / 'osfmk/arm64/sleh.c'
        text = sleh.read_text()
        misplaced = '\n\tboot_progress_user_breakpoint(state, esr);\n#if __has_feature(ptrauth_calls)'
        if misplaced in text:
            sleh.write_text(text.replace(misplaced, '\n#if __has_feature(ptrauth_calls)', 1))
        manifest = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in source.rglob('*') if p.is_file()}
        (output/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    env = dict(os.environ, KERNEL_SDKROOT=str(sdk),
               XNU_AVAILABILITY_PL=str(sdk/'usr/local/libexec/availability.pl'))
    flags = '-Wno-reserved-identifier -Wno-pre-c11-compat -Wno-missing-designated-field-initializers -Wno-suggest-override -Wno-unnecessary-virtual-specifier -Wno-suggest-destructor-override -Wno-ms-bitfield-padding -DXNU_NATIVE_PAN=1 -DXNU_SOURCE_CORECRYPTO14=1 -DXNU_BOOT_PROGRESS=0'
    if os.uname().sysname == 'Linux':
        # Current upstream clang inserts explicit authentication-failure traps
        # that the Apple comparison image does not contain. This image only
        # supplies identities and never executes; retain PAC and match Apple's
        # instruction selection here. The running native kernel keeps its checks.
        flags += ' -fno-ptrauth-auth-traps'
    args = ['make','-C',str(source),'build','SDKROOT=iphoneos',
        'ARCH_CONFIGS=ARM64','MACHINE_CONFIGS=BCM2837','KERNEL_CONFIGS=RELEASE',
        'ARCH_STRING_FOR_CURRENT_MACHINE_CONFIG=arm64e','LARGE_MEMORY_DEFINE=-UARM_LARGE_MEMORY',
        'ARM64_LINK_ADDR=0xfffffff007004000','ARM64_PLKSEG_ADDR=0xfffffff004004000',
        f'DEPLOYMENT_TARGET_FLAGS=-miphoneos-version-min={os.environ.get("UNIXNU_IOS_VERSION", "26.0")} -DXNU_TARGET_OS_IOS',
        f'DEPLOYMENT_LINKER_FLAGS=-Wl,-ios_version_min,{os.environ.get("UNIXNU_IOS_VERSION", "26.0")}',
        f'RC_DARWIN_KERNEL_VERSION={os.environ.get("UNIXNU_XNU_DARWIN", "25.5.0")}',
        f'RC_ProjectSourceVersion={os.environ.get("UNIXNU_XNU_VERSION", "12377.121.6")}',
        f'BUILD_LTO={int(options.lto)}','BOUND_CHECKS=0','BUILD_WERROR=0','MAKEJOBS=-j8',
        f'LDFLAGS_KERNEL_LTO=-miphoneos-version-min={inputs["versions"]["UNIXNU_IOS_VERSION"]} -Wl,-mllvm,-inline-threshold=100',
        f'CFLAGS_EXTRA={flags}',
        'copyio.o_CFLAGS_ADD=-march=armv8.1-a','pcb.o_CFLAGS_ADD=-march=armv8.1-a',
        'LD_KERNEL_ARCHIVES='+' '.join([f'-L{sdk}/usr/local/lib/kernel','-lfirehose_kernel',
                                        *map(str,archives),*(f'-Wl,-force_load,{p}' for p in forced)]),
        'XNU_EXTERNAL_KERNEL_ARCHIVES='+' '.join(map(str,archives+forced)),
        f'OBJROOT={output}/{mode}-obj',f'SYMROOT={output}/{mode}-sym',f'DSTROOT={output}/{mode}-dst']
    if os.uname().sysname == 'Linux':
        clt = os.environ.get('CLT_PREFIX', '/opt/unixnu-linux/CommandLineTools/usr')
        env.update(PLATFORM='iPhoneOS', HOST_CC=f'{clt}/bin/xnu-host-cc',
                   MIGCOM=f'{clt}/libexec/migcom')
        args += ['TIGHTBEAMC=tightbeamc-not-supported', 'BUILD_DSYM=0',
                 f'MEMORY_SIZE={os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")}',
                 f'SYSCTL_HW_PHYSICALCPU={os.cpu_count()}', f'SYSCTL_HW_LOGICALCPU={os.cpu_count()}',
                 f'LD_KERNEL_LIBS={sdk}/usr/local/lib/kernel/libcc_kext.a']
    if lto_linker:
        # XNU's LD variable is a clang driver (its flags include -Wl,...).
        # Override the driver only for the link, so compile recipes stay intact.
        driver = output / 'linux-lto-link.py'
        driver.write_text('import os,sys\nos.execvp("xcrun", ["xcrun", "clang++", "-nostdlib", '
                          + repr('-fuse-ld=' + str(linker_path)) + ', *sys.argv[1:]])\n')
        args.append(f'LD={os.sys.executable} {driver}')
    (output/f'{mode}-command.json').write_text(json.dumps(args,indent=2)+'\n')
    with (output/f'{mode}-build.log').open('w') as log:
        result = subprocess.run(args,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
    print('RELEASE reference exit',result.returncode,'log',output/f'{mode}-build.log',flush=True)
    # The bring-up patch calls native hooks from the kernel core behind weak_import declarations; on arm64e
    # the authenticated pointer of an undefined weak symbol fails the link. The private copy stubs them: this
    # comparison kernel never runs, the prelink step reads its layout.
    build_log = (output / f'{mode}-build.log').read_text()
    stub_names = sorted(set(re.findall(r'^\s+"(_(?:native_[a-z0-9_]+|boot_log_rounds|uke_boot_stage(?:_bind|_unbind)?))"', build_log, re.M)))
    if stub_names:
        (output / 'native-stubs.c').write_text(''.join(f'long {name[1:]};\n' for name in stub_names))   # the linker names carry the leading underscore
        iphoneos = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
        subprocess.run(['xcrun', 'clang', '-arch', 'arm64e', '-mkernel', '-isysroot', iphoneos, '-c',
                        '-o', str(output / 'native-stubs.o'), str(output / 'native-stubs.c')], check=True)
        at = next(i for i, a in enumerate(args) if a.startswith('LD_KERNEL_ARCHIVES='))
        args[at] += f' -Wl,-force_load,{output}/native-stubs.o'
    # Forced exports the built objects cannot provide: remove them from this private copy and link again
    # (the symbols are absent from the comparison kernel either way; the first link can stop exactly there,
    # and its file list is what names the objects that were built).
    objects = linked_objects(output / f'{mode}-obj/RELEASE_ARM64_BCM2837', options.lto)
    objects += list(map(str, archives + forced))
    names = set()
    for i in range(0, len(objects), 100):
        listed = subprocess.run(['xcrun', 'nm', '-gUj', *objects[i:i + 100]], capture_output=True, text=True, check=True)
        names.update(symbol for symbol in listed.stdout.splitlines() if symbol.startswith('_') and ' ' not in symbol)
    removed = []
    for filename in ('Private.exports', 'Private.arm64.exports'):
        path = output / 'source/config' / filename
        lines = path.read_text().splitlines(keepends=True)
        rejected = {line.strip() for line in lines
                    if line.strip().startswith('_') and ':' not in line and not any(fnmatch.fnmatchcase(n, line.strip()) for n in names)}
        removed.extend(sorted(rejected))
        path.write_text(''.join(line for line in lines if line.strip() not in rejected))
    import json as _json
    record = output / 'omitted-unavailable-forced-exports.json'
    previous = _json.loads(record.read_text()) if record.exists() else []
    record.write_text(_json.dumps(sorted(set(previous + removed)), indent=2) + chr(10))
    print('removed', len(removed), 'unavailable forced exports; linking again')
    with (output / f'{mode}-build.log').open('a') as log:
        result = subprocess.run(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
    print('RELEASE reference exit', result.returncode, 'log', output / f'{mode}-build.log', flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    built = output / f'{mode}-obj/RELEASE_ARM64_BCM2837/mach.release.bcm2837.unstripped'
    temporary = final.with_suffix('.tmp')
    shutil.copyfile(built, temporary)
    os.replace(temporary, final)
    cache_record.write_text(json.dumps({'inputs': inputs, 'sha256': file_hash(final),
                                  'build': str(output)}, indent=2) + '\n')
    print('reference', final)


if __name__ == '__main__':
    main()

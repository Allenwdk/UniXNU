"""Boot payload: the FAT volume that becomes the ramdisk of the boot image.

The volume is what UniXNU reads at boot: its config, the kernel Mach-O (optionally with the panic
screen patched into a copy), the device tree sidecar the board script generates, and optionally the
trust cache and the Data ramdisk seed. The loader (DarwinBoot) is part of the firmware volume.

Inputs that are not in a repository are options: the prelinked kernel (default: the output of
"build kernel"), --trust-cache, --data-ramdisk and the platform seed --unique-chip-id.
The volume is written with mtools, without mounting, so it is the same on every run.
"""
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from . import kernel as kernel_step
from .util import Error, expand, log, run, sha256_file, tool

EPOCH = 315532800   # 1980-01-01, the first FAT timestamp; keeps the volume reproducible


def paths(ctx):
    out = ctx.work / 'payload'
    return out, out / 'payload.img', out / 'payload.json'


def check_args(arguments):
    for value in arguments:
        # A value may hold ':' and '=' (exec-env=NAME:VAR=VALUE); no space, quote or shell character.
        if not re.fullmatch(r'[A-Za-z0-9_.\-]+(=[A-Za-z0-9_.,/\-:=]+)?', value):
            raise Error(f'unsupported kernel argument: {value}')
    line = ' '.join(arguments)
    # DarwinBoot copies the command line into a 1024-byte buffer and refuses a longer one.
    if len(line) > 1000:
        raise Error(f'the kernel command line is {len(line)} bytes; the limit is 1000')
    return line


def check_data_input(ctx, data):
    """An owner-Data kernel needs a seed even when it resumes a persistent overlay."""
    if data:
        return
    from .config import parse_config
    config = ctx.config
    if not ctx.config_path.is_file() and ctx.config_name:
        selected = ctx.device / 'configs' / ctx.config_name
        if selected.is_file():
            config = parse_config(selected.read_text())
    if config.get('XNU_OWNER_DATA_MOUNT'):
        raise Error('CONFIG_XNU_OWNER_DATA_MOUNT requires --data-ramdisk FILE (or [build] data_ramdisk); '
                    'persistent Data still needs its original seed to publish the volume')


def check_native_root(kernel, arguments, vmm_present=False):
    """Refuse the known bare-metal AMFI panic before the volume is written.

    A board whose device tree declares vmm-present has no PMGR for AMFI to wait for; it needs no PMGR stand-in."""
    if vmm_present:
        return
    values = {}
    for argument in arguments:
        key, separator, value = argument.partition('=')
        if separator:
            values.setdefault(key, []).append(value)
    if '1' not in values.get('native-ufs-root', []):
        return
    if values.get('pmgr', values.get('sheng-pmgr')) != ['2']:
        raise Error('native UFS root boot needs exactly one pmgr=2 (or sheng-pmgr=2); the unchanged target AMFI otherwise panics with No PMGR')
    symbols = run([tool('llvm-nm', 'brew install llvm'), '--defined-only', kernel], capture=True)
    if not any(line.split()[-1:] == ['_sheng_pmgr_run'] for line in symbols.splitlines()):
        raise Error('the native UFS root kernel lacks the linked sheng PMGR integration')


def write_volume(stage, image, label, size_mib, cluster_sectors=None):
    """Publish only a FAT volume whose complete file set was accepted by mtools."""

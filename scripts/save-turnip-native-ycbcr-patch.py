#!/usr/bin/env python3
"""Regenerate patches/mesa/turnip-native-ycbcr-dynamic.patch from the working Mesa tree.

The patch is the difference between "pinned Mesa + the other recorded patches" and the working tree for the files the
native YCbCr path touches, so it can be applied last: the sampled image's descriptor element carries its Y'CbCr
conversion's state (tu_device.h, tu_image.cc) and a shader that samples a dynamically indexed image applies the model
and range conversion from it (tu_shader.cc), which the immutable-sampler lowering cannot do. Edit the Mesa tree, run
this, then run build-turnip-darwin.py to prove the tree equals the recorded patches."""
import json
import tempfile
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MESA = ROOT / '.cache/mesa-work'
MINE = ['src/freedreno/vulkan/tu_device.h', 'src/freedreno/vulkan/tu_device.cc',
        'src/freedreno/vulkan/tu_image.cc', 'src/freedreno/vulkan/tu_shader.cc']
OUT = ROOT / 'patches/mesa/turnip-native-ycbcr-dynamic.patch'
others = [p for p in json.loads((ROOT / 'scripts/data/adreno-compiler-inputs.json').read_text())['patches']
          if Path(p) != OUT.relative_to(ROOT)]


def git(tmp, *args, check=True):
    return subprocess.run(['git', '-c', 'user.email=a@b', '-c', 'user.name=n', *args], cwd=tmp, check=check,
                          capture_output=True, text=True).stdout


tmp = Path(tempfile.mkdtemp(dir=ROOT / '.cache'))
try:
    git(tmp, 'init', '-q')
    for f in MINE:
        (tmp / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp / f).write_bytes(subprocess.run(['git', 'show', 'HEAD:' + f], cwd=MESA, check=True,
                                             capture_output=True).stdout)
    git(tmp, 'add', '-A')
    git(tmp, 'commit', '-q', '-m', 'base')
    for patch in others:
        for f in MINE:
            git(tmp, 'apply', '--include=' + f, str(ROOT / patch), check=False)
    git(tmp, 'add', '-A')
    git(tmp, 'commit', '-q', '-m', 'others', '--allow-empty')
    for f in MINE:
        shutil.copy(MESA / f, tmp / f)
    OUT.write_text(git(tmp, 'diff'))
finally:
    shutil.rmtree(tmp)
print('wrote', OUT.relative_to(ROOT), len(OUT.read_text().splitlines()), 'lines')

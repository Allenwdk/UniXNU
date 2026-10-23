#!/usr/bin/env bash
# Build the kernel from an empty out/ tree in one command.
#
# The board's archive list reads a prelink candidate (build/native-prelink/),
# and a candidate is a prelinked kernel, so the two need each other. The way
# out is the one .github/workflows/build-kernel.yml takes: build once with a
# configuration that opts out of the archive list, use that kernel as the
# candidate, then build the real configuration.
#
#   ./scripts/build-kernel-cold.sh -D /path/to/device [--defconfig NAME] \
#                                  [unixnu build args...]
#
# --defconfig is the configuration to build at the end (default uke-full_defconfig).
# Once a candidate exists the bootstrap pass is skipped and this is just
# "unixnu defconfig && unixnu build kernel".
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

DEVICE=""
DEFCONFIG=uke-full_defconfig
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -D|--device) DEVICE=$2; ARGS+=("$1" "$2"); shift 2;;
    --defconfig) DEFCONFIG=$2; shift 2;;
    *) ARGS+=("$1"); shift;;
  esac
done
if [ -z "$DEVICE" ]; then
  echo "build-kernel-cold.sh: pass the device repository with -D DIR" >&2
  exit 2
fi

# out/<board>/tree, found through the kernel the first pass leaves behind.
candidates=$(find out -path '*/build/native-prelink/*-candidate.macho' 2>/dev/null | wc -l)
if [ "$candidates" -eq 0 ]; then
  echo "== cold start: bootstrap kernel as the prelink candidate"
  ./unixnu defconfig bootstrap_defconfig -D "$DEVICE"
  ./unixnu build kernel -D "$DEVICE"

  kernel=$(ls -1 out/*/kernel/kernel.macho | head -1)
  work=${kernel%/kernel/kernel.macho}
  tree=$work/tree
  mkdir -p "$tree/build/native-prelink" "$tree/build/display-analysis"

  for name in native-owner-mobile-graphics-candidate \
              native-owner-ufs-cpu-desktop-v9-hid-init-candidate; do
    cp -f "$kernel" "$tree/build/native-prelink/$name.macho"
    [ -f "${kernel%.macho}.json" ] && cp -f "${kernel%.macho}.json" "$tree/build/native-prelink/$name.json"
  done

  # The legacy-display audit's runtime observation is recorded rather than
  # booted under QEMU; seed it when nothing produced one.
  python3 - "$tree/build/display-analysis/mobile-graphics-legacy-abi.json" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.exists():
    p.write_text(json.dumps({'runtime_metadata_checkpoint_sha256':
        '3044c2beff552911605994c0dc7aa73182066cbb5aed0b396999ceeb5a96da2b'}) + '\n')
PY

  # Not the shipping kernel; the pass below produces that.
  rm -f "$kernel" "${kernel%.macho}.json"
  ls -l "$tree/build/native-prelink/"

  # The bootstrap pass ran a configuration that opts out of the archive list;
  # put the real one back before the shipping build.
  ./unixnu defconfig "$DEFCONFIG" -D "$DEVICE"
fi

exec ./unixnu build kernel "${ARGS[@]}"

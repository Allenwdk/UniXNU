#!/usr/bin/env bash
# Linux toolchain environment for the UniXNU XNU build.
#   source scripts/linux-build-env.sh
# Once xnu-linux-toolchain/bootstrap.sh has run, one `source` is enough.

# xnu-linux-toolchain owns the tools; its bootstrap.sh installs env.sh into the
# prefix, so one `source scripts/linux-build-env.sh` is enough.
for _candidate in \
    "${XNU_LINUX_REPO:-}/env.sh" \
    "${XNU_LINUX_PREFIX:-}/env.sh" \
    "${XNU_LINUX_PREFIX:-$HOME/.local/xnu-linux}/env.sh"; do
  if [ -n "$_candidate" ] && [ -f "$_candidate" ]; then
    . "$_candidate"
    break
  fi
done
unset _candidate

# Tools come from the xnu-linux-toolchain prefix. Nothing outside it is assumed
# to exist; a machine that has not run bootstrap.sh is told so rather than left
# pointing at a path from someone else's home directory.
if [ -z "${UNIXNU_TOOLCHAIN:-}" ]; then
  for _bin in "${XNU_LINUX_PREFIX:-}/bin" "$HOME/.local/xnu-linux/bin"; do
    if [ -n "${_bin%/bin}" ] && [ -x "$_bin/migcom" ]; then
      UNIXNU_TOOLCHAIN=$_bin
      break
    fi
  done
  unset _bin
fi
if [ -z "${UNIXNU_TOOLCHAIN:-}" ]; then
  echo "linux-build-env.sh: no xnu-linux-toolchain prefix found" >&2
  echo "linux-build-env.sh: clone https://github.com/Allenwdk/xnu-linux-toolchain and run ./bootstrap.sh" >&2
  return 1 2>/dev/null || exit 1
fi
export UNIXNU_SHIM="$UNIXNU_TOOLCHAIN"
# The kernel build's SDK is the fakeroot build-xnu-4k-baseline.sh assembles in
# the device tree, not an Apple SDK. Point xcrun's -show-sdk-path at it.
UNIXNU_DEVICE=${UNIXNU_DEVICE:-uke}

# The fakeroot lives in the project's own out/ tree; derive it from this
# script's location rather than the caller's cwd.
UNIXNU_PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)
export UNIXNU_SDKROOT="${UNIXNU_SDKROOT:-$UNIXNU_PROJECT_ROOT/out/$UNIXNU_DEVICE/tree/.cache/fakeroot}"
export UNIXNU_SDK_VERSION=17.0
export UNIXNU_SDK_BUILD=21A326
# XNU's SETUP host tools (kextsymboltool, setsegname) include <mach-o/*.h>;
# those headers ship with cctools-port, not with the Linux SDK.
export UNIXNU_HOST_CCTOOLS_INCLUDE="${UNIXNU_HOST_CCTOOLS_INCLUDE:-$UNIXNU_TOOLCHAIN/../cctools/include}"
export PATH="$UNIXNU_TOOLCHAIN:$PATH"
export JOBS=${JOBS:-$(nproc)}


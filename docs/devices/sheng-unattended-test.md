# sheng log capture example

The common [log capture procedure](/porting/log-capture) defines the porting
workflow. This page records the sheng values used by that procedure: its storage
region, Linux reader image, reset arguments and runner.

## Board inputs

Use the [sheng device repository](https://github.com/UniXNU/UniXNU-sheng), a
built kernel and package, configured [local inputs](/reference/configuration#local-build-inputs),
fastboot and Python 3.

```sh
DEVICE_REPO=$(cd ../UniXNU-sheng && pwd)
TARGET="$PWD/out/sheng/ipados-17.7.11-21H461/sheng"
mkdir -p "$TARGET/boot"
fastboot devices
```

The sheng writer reserves the last 32 MiB of `userdata`. Its board arguments are:

| Argument | Function |
| --- | --- |
| `sheng-log=1` | Starts the persistent log writer |
| `sheng-autoreset=120` | Returns to fastboot after log synchronization and the 120 second deadline |

The implementation uses `package/BootLog.c`, `BootReset.c`, `BootResetCore.h`,
`package/linux-log/` and `scripts/read-sheng-log.py` in the device repository.
The [sheng Linux release](https://github.com/ianchb/sm8550-mainline/releases)
provides `boot_sheng_singleboot.img` and `nvmem-reboot-mode.ko`.

## Reader image

Build the sheng Linux reader with the device repository script. The reader copies
the reserved region into RAM, exposes a USB CDC ACM shell and keeps source storage
read-only.

```sh
clang++ --target=aarch64-linux-gnu -fuse-ld=lld -nostdlib -static \\
  -fno-stack-protector -fno-exceptions -fno-rtti -Wl,-e,start \\
  "$DEVICE_REPO/package/linux-log/rebootbl.cpp" -o "$TARGET/boot/rebootbl"
python3 "$DEVICE_REPO/package/linux-log/build-linux-log-boot.py" \\
  --boot /path/to/boot_sheng_singleboot.img --busybox /path/to/busybox \\
  --rebootbl "$TARGET/boot/rebootbl" --module /path/to/nvmem-reboot-mode.ko \\
  --out "$TARGET/boot/sheng-linux-log.img"
```

## Manual cycle {#manual-cycle}

Build and boot the logging image, then boot the reader and collect the region:

```sh
./unixnu payload --kernel-arg=sheng-log=1
./unixnu bootimg
SERIAL=<serial>
fastboot -s "$SERIAL" boot "$TARGET/boot/boot.img"
fastboot -s "$SERIAL" boot "$TARGET/boot/sheng-linux-log.img"
python3 "$DEVICE_REPO/scripts/read-sheng-log.py" \\
  --wait 240 --out "$TARGET/logs/captures"
```

The output directory contains `log.bin`, `header.txt`, `msgbuf.txt`, `slots.txt`
and `latest.txt` under a boot ID. Confirm the reader returns the device to
fastboot before the next run. Use the [recovery reader procedure](/porting/log-capture#persistent-logs) when the board provides a compatible recovery image.

## Automated cycle {#automated-cycle}

Enable the timed reset and run the board script with absolute image paths:

```sh
./unixnu payload --kernel-arg=sheng-log=1 \\
  --kernel-arg=sheng-autoreset=120
./unixnu bootimg
SERIAL="$SERIAL" READER="$TARGET/boot/sheng-linux-log.img" \\
  bash "$DEVICE_REPO/scripts/run-sheng-unattended.sh" \\
  "$TARGET/boot/boot.img" 420
```

The runner stores captures under
`UniXNU-sheng/build/sheng-logs/<tag>-<boot id>/`. Record the image revision,
arguments, checkpoint, reset result and output directory in the [porting record](/porting/records).

## Reader verification

The device repository includes a QEMU check for partition lookup, RAM copying,
transfer and decoding:

```sh
python3 "$DEVICE_REPO/package/linux-log/check-linux-log-qemu.py" \\
  --image "$TARGET/boot/sheng-linux-log.img" \\
  --kernel /path/to/qemu-virt-linux-Image \\
  --work "$TARGET/logs/reader-qemu"
```

Record this host check separately from board storage writes, USB transfer and
reset observations.

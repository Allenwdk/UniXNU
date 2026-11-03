# AdrenoMetal

Start with the [adaptation procedure](/porting/gpu) for board inputs, source changes, build integration and verification order.

AdrenoMetal provides the Metal frontend through metal2vulkan and Turnip. It
publishes a device through `MTLAddDevice`, translates AIR, and submits work to
the kernel GPU interface.

| Field | Value |
| --- | --- |
| Repository | [UniXNU/AdrenoMetal](https://github.com/UniXNU/AdrenoMetal) |
| Implementation | A740/SM8550 graphics stack and the selected OS ABI |
| Dependencies | Adreno740, Turnip, metal2vulkan, IOGPUFamily and IOSurface interfaces |
| Board inputs | Firmware, power policy, memory layout, display integration |
| Verified device | sheng |
| Runtime plugin | `NativeAdrenoMetal` |

sheng runs the GPU-composited desktop. Exported pipeline caches are reused across
boots. The render server primes every Metal library of the OS image while the
desktop is idle: the payload carries the list (`NativeAdrenoMetal.primelist`) and
a copy of the cryptex QuartzCore library, which the render server's sandbox
cannot reach. The idle desktop submits about 6 command buffers per 250 ms at
120 Hz, so priming waits only above 8. The PR log row shows its progress; all
162 libraries are primed on sheng. With the list present the render server does
not scan directories, and each library is read only while the display is quiet.
The lists, the pipeline pack and the resume rules are in [Warm the shader caches](/porting/gpu#shader-warmup).

A render pass that cannot be encoded still returns an encoder, and its command
buffer is refused: RenderBox caches encoder methods and cannot take nil. The first problem of each process is written to the driver's
per-process text line from the thread that hit it.

```sh
python3 scripts/build-turnip-darwin.py --target ios
python3 scripts/build-adreno-metal-plugin.py
```

See [Adreno740](/drivers/adreno740) for the runtime path, staging commands, and checks.


## iOS 27 Turnip load format

Build Turnip with `python3 scripts/build-turnip-darwin.py --target ios27` as well as the plugin's `--target ios27`. The Turnip link explicitly enables `-Wl,-fixup_chains`, including when Meson reconfigures a cached build. Confirm the final signed dylib contains `LC_DYLD_CHAINED_FIXUPS`. The owner trust module must use its new CDHash.

An uke 24A446 iconservicesagent report showed a stack guard fault in dyld `MachOAnalyzer::withChainStarts` while Metal opened Turnip. Legacy arm64e `LC_DYLD_INFO_ONLY` made dyld synthesize chain starts on the workqueue stack: the old library required 439,304 bytes, matching crash register x8 exactly. Chained metadata avoids that legacy synthesis. This is a load-format fix, with rendering behavior and compiler pins preserved; actual icon/widget recovery and freeze acceptance still require hardware testing. See [Apple's implementation](https://github.com/apple-oss-distributions/dyld/blob/main/common/MachOAnalyzer.cpp).


## Resources in owner cryptex views

A boot-time bind view of the union-mounted SystemOS tree must preserve the source union's lower OS directories. Otherwise the framework view exposes upper files but cannot find or enumerate lower resources such as Core Image's `ci_stdlib.metallib` and stitchable libraries. The arm64e series includes `native-bindfs-source-union.patch`: owner boot bind mounts inherit the source union flag, and the existing VFS union lookup and directory enumeration follow the source's lower directory. Ordinary bind mounts keep their covered-directory behavior. Read-only mounts, access checks and vnode reference ownership stay on the existing VFS paths.

This closes a resource-view gap found while investigating uke 24A446 slow icons and repeated Core Image program failures. It is not hardware proof that every library load or GPU context loss is repaired. Keep GPU fault recovery and its normal error propagation enabled; qualify the actual framework/resource path, icons, widgets and application transitions on the device.

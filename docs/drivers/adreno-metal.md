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


## iOS 27 Core Image library lookup

The uke iOS 27 frontend retains the original `CIKernelLibrary` `internalLibraryWithName:device:` result. A nil result for this frontend's own device retries only the known Core Image standard-library and stitchable-library names at their standard `/System/Library/Frameworks/CoreImage.framework` paths, using the unchanged `newLibraryWithURL:error:` implementation and runtime parser. The original helper's retained return convention is preserved. Successes and other clients are unchanged; a refused retry remains nil and retains its actual failure text. No files are copied and the global VFS view is not changed.

This targets observed library-load failures in uke 24A446 iconservicesagent; its device effect remains unqualified. The earlier source-union VFS experiment caused an Apple-logo boot regression and was reverted. Kernel recovery now records the existing fence/restart/fault result once per recovery, and the existing plugin marker text can terminate with NUL to persist bounded failure summaries. This does not change scheduling, preemption, error propagation or recovery policy.

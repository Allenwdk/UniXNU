# AdrenoMetal

Turnip vertex binding checks command-substream allocation before writing packets. Allocation failures invalidate recording with the original error. `scripts/check-turnip-vertex-allocation.py` exercises the actual function with failing and successful allocation peers. Reused builds must have the selected source directory in Meson's source identity.

With `diag=1`, recovery diagnostics match the runtime's public `Degradation::DeviceRecovered.code()`, including the `metal2vulkan-degrade-` prefix. Recovered-object refusals also preserve the first loss's source location. Recovery and resource lifetime are unchanged.

AdrenoMetal publishes a Metal device through `MTLAddDevice`. It translates AIR through metal2vulkan, compiles SPIR-V with Turnip, and submits work to [Adreno740](/drivers/adreno740). Firmware, power votes and display integration come from the board.

## Rendering and interfaces

| Area | Behavior |
| --- | --- |
| MSAA policy | All clients use one sample for textures, pipelines and render passes by default. Resolve targets receive the rendered output; load and store-and-resolve preserve the source. `NATIVE_METAL_SINGLE_SAMPLE=0` preserves a process's requested sample counts; `1` forces single-sample rendering. |
| Heap resources | Buffer and texture `makeAliasable` release their heap ranges. |
| Texture channels | Texture descriptors and views preserve all four swizzles, including explicit zero and one. |
| Copies and raster state | Blits cover the requested mip and slice ranges. Viewport and scissor setters forward every entry, up to 16. |
| Compressed input | A zero-length no-copy compressed texture infers its DroidVM layout size and retains the owner's deallocator through use. |
| Functions | Function constant dictionaries expose names, indices and types. Function and compute-pipeline completion selectors report results. `specializedName` is the exported name; source lookup retains the original definition. |
| Constant tables | Dynamically indexed constant tables larger than 4 KiB use shared constant storage. Constant pointer casts and GEP expressions retain their offsets. |
| Memory accounting | Device allocation totals include pooled, dedicated and imported backing. Texture sizes come from their backing allocation. The recommended working set is RAM / 4, capped at 2 GiB. |
| Queue capacity | `newCommandQueueWithMaxCommandBufferCount:` uses the runtime's outstanding-buffer limit. Uncommitted destruction releases a slot; completion releases it after handlers return. |

A render pass that fails encoding returns an encoder and reports a command-buffer error. This supports callers that cache encoder methods.


Unused owned image backing is reused by pooled and dedicated images. Extra spares have no byte limit, expire after ten seconds, and go sooner under memory pressure or when a new block cannot be made. Blocks are freed off the releasing thread on the runtime's free thread, and on the releasing thread once its queue is full. An allocation failure releases kept spares and waits for posted frees before retrying. Imported memory and owner callbacks keep their release ordering. First-use allocations can still prepare new pages.

## Cache and priority

Clients with the same UID use `Library/Caches/org.unixnu.metal` under their account home when writable. Sandbox restrictions select a private cache. `NATIVE_METAL_SHARED_CACHE_DIR` selects another shared root; an empty value disables sharing. The cache covers Apple frontend output, runtime artifacts and Turnip IR3. Concurrent pack imports use distinct temporary files. Pipeline journals are per process.

Three metal2vulkan work placements are on by default. `metal-flow=<bits>` selects them: 1 for the first, 2 for the second, 4 for the third, and 0 for none:

- Render encoder calls lower on the runtime's lowering thread. A refusal found while lowering fails the command buffer.
- A commit submits on the committing thread when no other submission pass is running.
- Each program appends its pipeline records to `pipeline-records-<name>.bin` in the cache. A new device makes the recorded pipelines again in the background at the utility class.

Any value of `metal-flow=` logs the `FL` counts to os_log every ten seconds when they change.

Turnip chooses tile memory or system memory for each render pass, and concurrent binning is on. `tu-debug=<flags>` sets `TU_DEBUG` for every Metal process: `gmem` renders every pass in tile memory and `nocb` turns concurrent binning off. `tum=a` alternates between Turnip's choice and tile memory every eight seconds for measurement.

The Uke build uses Turnip render-mode selection and concurrent binning by default. The Uke addon stages an empty `tu_debug` to clear the override installed by earlier builds.

Logical Metal queues share one Vulkan queue and kernel queue per process. The frontend forwards the most urgent **current** request among live queues. Lowering or destroying a queue removes its boost. Getters report each queue's own request; setters report backend acceptance. The kernel chooses foreground or background priority from the task's GPU role. Priority policy does not use process names.

## Build and checks

From the resolved iOS 27 target tree:

```sh
python3 scripts/build-turnip-darwin.py --target ios27
python3 scripts/build-adreno-metal-plugin.py --target ios27
python3 scripts/check-native-metal-frontend-host.py
```

The normal build applies the recorded translator and Turnip patches and enables Mesa's disk shader cache. Host checks cover rendered pixels, resolves, resource aliasing, swizzles, copies, callbacks, queue limits and priority aggregation. Hardware qualification covers frame pacing and preemption under concurrent clients.

See the [GPU adaptation procedure](/porting/gpu) for staging and board inputs.

Frame diagnostics retain allocation, command, completion and GPU/display timing. Pixel capture is disabled. See [GPU frame diagnostics](/porting/gpu-diagnostics).

With `gpu-trace=1`, kernel event 65 identifies the Metal device and command queue used by `iconservicesagent`. Up to eight `metal-work` records report completion status, draw count and dispatch count for command buffers with GPU work.

`wallpaper-freeze=1` isolates wallpaper rendering. A Poster renderer retains its first successfully drawn and stored IOSurface output of at least two million pixels, then parks later command buffers before runtime submission. Parked buffers remain committed and unscheduled; their owners and queue leases stay retained. Previously submitted work completes normally. PosterBoard, backboardd and other clients continue submitting. The mode defaults to off.

Detailed latency records identify slow encoder calls, callback invoke addresses and resource destruction. Kernel sampling of the render, encode and completion threads correlates upstream waits.


See [Adreno740](/drivers/adreno740) for the runtime path, staging commands, and checks.


## iOS 27 Turnip load format

Build Turnip with `python3 scripts/build-turnip-darwin.py --target ios27` as well as the plugin's `--target ios27`. The Turnip link explicitly enables `-Wl,-fixup_chains`, including when Meson reconfigures a cached build. Confirm the final signed dylib contains `LC_DYLD_CHAINED_FIXUPS`. The owner trust module must use its new CDHash.

An uke 24A446 iconservicesagent report showed a stack guard fault in dyld `MachOAnalyzer::withChainStarts` while Metal opened Turnip. Legacy arm64e `LC_DYLD_INFO_ONLY` made dyld synthesize chain starts on the workqueue stack: the old library required 439,304 bytes, matching crash register x8 exactly. Chained metadata avoids that legacy synthesis. This is a load-format fix, with rendering behavior and compiler pins preserved; actual icon/widget recovery and freeze acceptance still require hardware testing. See [Apple's implementation](https://github.com/apple-oss-distributions/dyld/blob/main/common/MachOAnalyzer.cpp).


## iOS 27 Core Image library lookup

The uke iOS 27 frontend retains the original `CIKernelLibrary` `internalLibraryWithName:device:` result. A nil result for this frontend's own device retries only the known Core Image standard-library and stitchable-library names at their standard `/System/Library/Frameworks/CoreImage.framework` paths, using the unchanged `newLibraryWithURL:error:` implementation and runtime parser. The original helper's retained return convention is preserved. Successes and other clients are unchanged; a refused retry remains nil and retains its actual failure text. No files are copied and the global VFS view is not changed.

This targets observed library-load failures in uke 24A446 iconservicesagent; its device effect remains unqualified. The earlier source-union VFS experiment caused an Apple-logo boot regression and was reverted. Kernel recovery now records the existing fence/restart/fault result once per recovery, and the existing plugin marker text can terminate with NUL to persist bounded failure summaries. This does not change scheduling, preemption, error propagation or recovery policy.


## Uke device confirmation

On 2026-11-03, the user confirmed all previously reported boot, desktop/Settings icon/widget loading and Settings/Dock UI-restart symptoms resolved on the scoped Core Image retry build, kernel CRC `90B6BC701210D9DB`. This is the current uke GPU27 interactive baseline. Device image identity and acceptance evidence are recorded in the device repository's `docs/GPU-IOS27.md`; independent latency, long-run concurrency and cold-boot cache measurements remain separate.

Encoding drains retain queued-prefix targets. The worker broadcasts only for newly completed targets; producers notify work only on empty-to-nonempty transitions. This reduces redundant condition-variable work while preserving FIFO, scheduling/completion and ownership. Uke also selects sheng's original governor on DT-qualified CPU domains and the existing fixed120Hz refresh-range option; actual throughput requires hardware validation.


`sheng-diag=2` keeps backboardd command summaries, commit-to-encode phases and scanout-client events in the frame trace. Turnip pass stamps and runtime diagnostics stay off. Kernel tracing is configured separately.

The current Uke diagnostic candidate compares GMEM and SYSMEM on a restricted set of large IOSurface passes with memoryless auxiliary targets. Requests and command metadata are recorded for analysis. SYSMEM backing can change memory use. Hardware qualification includes pixels, job timing and memory pressure.

The C352 non-fetch ROAA experiment was withdrawn after icon/rendering regressions. The repair uses the original Turnip ordering code. `sheng-diag=4` adds explicit pass stamps and pass/attachment events to lightweight frontend timing, including its pass-ring consumer. The board exports mode4 after180seconds of its worker and logs addon installation counts. Addon writes set exact file size as well as mode before syncing. Hardware pixel recovery and pass timing delivery remain pending.

The Uke integration includes upstream iconservicesagent device/queue/completion records in mode4. CP preemption completion runs in the board thread call, and the waiting-stack sampler checks thread state and stack bounds before accessing saved registers. Hardware qualification is pending.

Uke now stages upstream sheng iconservicesagent environment policy (FORCE_SOFTWARE_RENDERER=0, CI_ENABLE_METAL_GPU=0) through a signed owner launchd cache and the existing read-only union mount. Original service fields and loader/signature checks remain. Host cache semantics and page hashes pass; private libxpc consumption, boot and pixels remain pending on candidate209862415C7884EC.

Uke modes2/4 now scope per-pass GPU stamps to backboardd, the only process exporting that ring. Icon device/queue/eight-work records and full mode1 diagnostics remain. This removes unused diagnostic writes; hardware speedup remains pending.

The per-pass reader now converts19.2MHz ticks using exact quotient/remainder arithmetic. Frame records24/25 snapshot existing pass split and host texture copy counters from the writer;26 identifies the clock. No rendering change or speedup is inferred. Legacy integer52ns pass times must be scaled625/624 before joining kernel ticks.

## Uke upstream synchronization (2026-11-07)

The Uke integration includes upstream AdrenoMetal main `6d7f734` and metal2vulkan `963f0e64f103d2e682cd0cc454a8fe50f52c8cbb`. The rebased upstream series contains 25 patches; Uke retains `0031-defer-fullscreen-memoryless-pass.patch` as a scoped opt-in experiment. Core Image's original-nil retry and Uke diagnostic modes remain.

`sheng-metal-flow=1` enables worker lowering, commit-thread submission and background pipeline-record warming. The default is off; `=0` and `=1` both enable changing FL count logs. Uke has not qualified these paths on hardware. The old translator cache remains available for rollback; the runtime identity changes with the translator and patch tree.

## Uke runtime recovery compatibility

Runtime recovery invalidates textures and pipelines from its previous generation. After completion handlers receive DeviceLost, GpuHang or GpuRecoveryVictim, the Uke render server enters its existing restart path. The Metal error codes retain their defined values. With diag=1, a bounded os_log callback retains runtime errors and recovery notices. tu-debug=perf also enables Vulkan error logging in the Mesa release build.

With `diag=1`, encoding batch end records (type 14, phase 3) store encoding-thread CPU microseconds in field `d`. Compare this with paired start/end wall time to distinguish work from waits. `TUC` reports Turnip BO cache lookups, hits, inserts, evictions and full flushes.

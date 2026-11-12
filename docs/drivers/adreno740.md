# Adreno740

Adreno740 implements the A740 kernel GPU interface on SM8550. It owns GPU memory mappings, command submission, fences and CP/GMU initialization. The board supplies firmware, power votes and display integration. See the [GPU adaptation procedure](/porting/gpu).

## Runtime path

Metal → AdrenoMetal → metal2vulkan → Turnip → Darwin KMD → Adreno740 → A740.

Each client has an address space and queue range. The GPU uses 4 KiB SMMU pages. Owned buffers use system memory; imported pages retain their owners. Allocation capacity follows available memory. Mapping handles are indexed, and unmap invalidates the affected translations.

## Scheduling

| Requested priority | Ring in mode 2 |
| --- | --- |
| High (0), normal-high (4), real-time (5) | 0 |
| Normal (1), low (2), background (3), unspecified | 1 |

The task's GPU role selects its foreground or background request. Ring 0 takes precedence; ring 1 gets service when ring 0 is idle or its oldest job has waited 250 ms. An aging grant gives ring 1 a 2 ms service interval, preventing immediate switch oscillation. Switch completion immediately reevaluates queued high-priority work. Scanout observes the completed prefix across both rings. A queue stays on its existing ring until its outstanding prefix completes, preserving FIFO across priority changes. IB handles identify command storage and do not infer resource dependencies. Turnip's client queues share one kernel FIFO; unresolved syncs wait for producer submission.

Each ring tracks its queued context and page table. The CP records the executed table after `CP_SMMU_TABLE_UPDATE`, and preemption restores that snapshot. Context switching saves GMEM, runs the performance-counter SRAM postamble and holds the GMU keepalive vote until the incoming WPTR is restored. Read pointers come from each ring's own shadow. Active jobs retain their ring identity when the fence-history table wraps.

The reference enables mode 2 with `gpu-preempt=2`. Mode 1 sends only low/background requests to ring 1; mode 0 uses one ring. CPU-only page-table switching also uses ring 0. The switch watchdog is 1 s. A failed switch disables further preemption and recovery replays pending work on ring 0; diagnostics retain the failure.

Stall detection also checks progress of the concurrent-binning (BV) thread. The stall handler skips recovery while the GPU is advancing. A failed buffer map records the requested IOVA and the mapping at or after that address.

## Build and verification

From the resolved iOS 27 target tree, with `UNIXNU_XNU_ARCH=arm64e` and `UNIXNU_IOS_VERSION=27.0`:

```sh
python3 scripts/build-arm-driver.py Adreno740
python3 scripts/build-adreno740-kits.py
python3 scripts/check-native-adreno-scheduling.py
```

The host scheduling check runs the real ring, preemption and submit code over software register peers with address and undefined-behavior sanitizers. It checks packets, GMEM and keepalive sequencing, timeout handling, page-table snapshots, priority routing, FIFO and fence-history rollover. Hardware qualification requires concurrent clients, repeated ring switches, correct pixels and frame-pacing measurements.

See [AdrenoMetal](/drivers/adreno-metal) for Metal interfaces, caches and plugin staging.

```sh
python3 scripts/check-native-metal-frontend-host.py
python3 scripts/check-turnip-darwin-host.py
python3 scripts/check-smmu4k-live.py
python3 scripts/check-turnip-pipeline-cache-host.py
python3 scripts/check-priming-cache-host.py --output build/priming-cache/run
python3 scripts/probe-turnip-internal-compiler-host.py --qualification <old> --output <new>
```

The device repository adds the original-input checks:

```sh
python3 scripts/build-adreno-compiler-host.py --probe
python3 scripts/build-turnip-ios-compiler-peer.py
python3 scripts/check-turnip-ios-compiler-cache.py
python3 scripts/check-quartzcore-turnip-cache-host.py
```

## Related

- [Xiaomi Pad 6S Pro (sheng)](/devices/sheng)
- [XNU drivers](/drivers/xnu-drivers)
- [Four-kilobyte pages](/xnu/four-k-page-tables)

## SM7675 integration

The gen7_11_0 profile carries chip ID 0x43030b00, 1.5 MiB GMEM,
2196 KiB CP preemption records and gen71100 firmware. uke uses the same
mode-2 scheduler, per-process VM and Metal frontend as sheng. Its iPadOS 27
images are build candidates; hardware qualification is pending.


## Native-XNU page preparation candidate

The uke candidate separates unowned system-BO page preparation from the original IOUserClient mapping-exclusion lock. Optional native prepare/finish callbacks keep active IPC ownership across preflight, locked validation/adoption and post-lock cleanup. A racing close refuses adoption; unused pages are returned outside the lock. The allocation diagnostic's user-stack walk also runs after the lock. Map/unmap/close serialization, request ABI and failure results remain. Without the matching native adapter the original allocation path applies; BO trace flag16 identifies preflight. Host concurrency checks and image assembly pass; hardware latency and120Hz remain unqualified.


The optional preflight path requires runtime readiness after GPU publication, not just linked callback symbols. Early clients retain the original call path without the new IPC pin; the driver repeats the readiness check before class access. Readiness/entry counters distinguish startup-stage behavior from actual GPU work. The BO preflight optimization remains enabled after publication; startup/performance require device validation.


Nonzero-timeout WaitFence calls can use the same runtime-ready preflight context: the original fence wait/validation/timeout/recovery runs before mapping exclusion; the original locked dispatch consumes its real result after checking request and liveness. Close stops or refuses consumption; zero-timeout polls and map/unmap/close locking remain. Board diagnostics report calls/elapsed/max/non-success; timeout is not treated as successful completion.

The preflight context is explicitly value-initialized after IONew, which allocates storage without running C++ default member initializers. Zero-filled storage otherwise leaves the method at0 instead of BoAlloc2, rejecting prepared-page adoption and repeating preparation under mapping exclusion. Uke0A3F recorded58 large BOs with fallback flags11; a raw-allocation host control reproduces this and passes after initialization. The later UI freeze has not yet been causally attributed.

Diagnostic hangs (first eight, sheng-diag) persist CP state before reset erases registers/stamps, with prior stall/IB/switch data explicitly labeled. Register-read failure is reported without changing ring health; the original stallState contract remains. No normal-frame work or recovery policy change is introduced.

## Lightweight shader wait counters

The opt-in uke `sheng-diag=2 sheng-gpu-trace=2` capture keeps the original21
BR counters and appends ten SP counters in event69: UCHE/RB backpressure,
wave context/wait, long/short synchronization, local-memory loads/stores,
fragment half ALU and EFU working. BR SP slots7–16 use RBBM_PERFCTR_SP.
Event69 carries the explicit BR marker0x4252001f. The old marker31 selected
BV slots24–33 and decodes as bv_legacy, excluded from BR attribution.
All-flat extra counters with shader activity are invalid, even if selectors match.
The existing32ms sampling/epoch/readback guards remain; no per-pass GPU
timestamp packets are added. Old21-counter captures still decode. Windows
crossing counter plans are excluded. These aggregate counters classify the
next investigation; they are not exclusive pass times or a proven speedup.


Frame diagnostics retain allocation, command, completion and GPU/display timing. Pixel capture is disabled. See [GPU frame diagnostics](/porting/gpu-diagnostics).

## Completion and memory ownership

The board IRQ handler passes its acknowledged RBBM status to `native_adreno_gpu_interrupt`. The driver's completion pass retires per-ring fences, drives pending switches and wakes the matching waiters. The periodic hang check covers a missed IRQ; it does not replace board interrupt delivery.

A board may register the loader's `darwinboot-memory-outside` ranges with `native_adreno_pool_add` before GPU publication. The ranges must be final-map conventional memory outside XNU's owned window, excluding all firmware/device reservations. The pool supplies write-combined system BOs before the ordinary descriptor fallback; views retain their grants and the default retirement policy prevents reuse of pages exposed to a client. Firmware, ADT and board probe must agree on this handoff.

The hang check captures CP state before recovery and retains it until the next hang. `native_adreno_stall_hang` identifies the snapshot. For faults whose upper address word is zero, `native_adreno_stall_fault` searches the job's IB1s and up to 512 referenced IB2s for the low word and nearby bases followed by zero. These are candidates for inspection, not decoded address operands. A new snapshot clears the previous search.

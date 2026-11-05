# GopFramebuffer

Start with the [adaptation procedure](/porting/display) for board inputs, source changes, build integration and verification order.

Framebuffer presentation using the firmware GOP handoff.

[Source repository](https://github.com/UniXNU/GopFramebuffer).

The implementation reads the firmware framebuffer through PE_current_console and integrates with the selected MobileFramebuffer ABI. Board hooks supply display policy and GPU scanout integration.

For the qualified 24A446 family, the generated ABI enables `NATIVE_LEGACY_BOOT_SCANOUT_REQUESTED`: a validated primary GOP mapping publishes the initial requested and firmware-powered states through the original family setter. The original submit path otherwise discards swaps while its requested field remains zero. This is logical scanout initialization, not a panel power transition; original user-client errors and validation remain in effect. A host build does not establish that frames reach the panel.

## Integration

The catalog records implementation scope, hardware and OS requirements, board dependencies, revision, build stage, outputs, and runtime identifiers. The selected profile orders build commands by dependency.

```sh
./unixnu build kernel -D /path/to/device
```

[Component catalog](/reference/components)
For the qualified 24A446 family, the generated ABI enables `NATIVE_LEGACY_BOOT_SCANOUT_REQUESTED`: a validated primary GOP mapping publishes the initial requested and firmware-powered states through the original family setter. The original submit path otherwise discards swaps while its requested field remains zero. This is logical scanout initialization, not a panel power transition; original user-client errors and validation remain in effect. A host build does not establish that frames reach the panel.


A retry of the same validated direct scanout request checks GPU fence progress first. Once ready, the driver repeats the surface and scanout checks before submitting the flip. Diagnostic mode 2 records the final latch status, including a timeout.

A CP fence IRQ may wake the display work loop to recheck GPU fence progress. The timer fallback, surface checks, and latch-based retirement remain in use.

Fence notifications queue a coalesced thread call. The display gate serializes delivery with the timer and teardown. The fallback stays at 200 µs until an IRQ-triggered fence recheck runs, then uses 500 µs.



Frame diagnostics retain allocation, command, completion and GPU/display timing. Pixel capture is disabled. See [GPU frame diagnostics](/porting/gpu-diagnostics).

Frame diagnostics read physical addresses from prepared direct-display slots. Validation reports zero until mapping, and the flip records the mapped address. Diagnostic observers do not prepare descriptors or query their physical segments.

# GopFramebuffer

Start with the [adaptation procedure](/porting/display) for board inputs, source changes, build integration and verification order.

Framebuffer presentation using the firmware GOP handoff.

[Source repository](https://github.com/UniXNU/GopFramebuffer).

The implementation reads the firmware framebuffer through PE_current_console and integrates with the selected MobileFramebuffer ABI. Board hooks supply display policy and GPU scanout integration.

For the qualified 24A446 family, the generated ABI enables `NATIVE_LEGACY_BOOT_SCANOUT_REQUESTED`: a validated primary GOP mapping publishes the initial requested and firmware-powered states through the original family setter. The original submit path otherwise discards swaps while its requested field remains zero. This is logical scanout initialization, not a panel power transition; original user-client errors and validation remain in effect. A host build does not establish that frames reach the panel.

## Integration

The catalog records implementation scope, hardware and OS requirements, board dependencies, revision, build stage, outputs, and runtime identifiers. The selected profile orders build commands by dependency.

```sh
./unixnu build kernel -D ../UniXNU-sheng
```

[Component catalog](/reference/components)

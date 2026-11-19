# 小米平板 7 / POCO Pad X1（uke）

[Allenwdk/UniXNU-uke](https://github.com/Allenwdk/UniXNU-uke)

<div v-pre>

Xiaomi Pad 7 runs iPadOS 27.0.1 with accelerated internal graphics, Wi-Fi, touch and USB host storage. Native extended desktop is device-observed on the earlier copy path; the XR10 HiDPI direct-scanout candidate has passed host checks and been flashed for hardware validation.

源记录: [porting.toml](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/porting.toml), `cab36c6bc8e3e63be93309a5ccaaa8a607bfc583`.

本页按设备记录自动生成。

| 部分 | 状态 |
| --- | --- |
| [配置](#configuration) | `host-verified` |
| [固件与启动](#firmware) | `implemented` |
| [CPU 与中断](#cpu) | `device-verified` |
| [内存与 DMA](#memory) | `implemented` |
| [存储与根卷](#storage) | `device-verified` |
| [显示](#display) | `host-verified` |
| [输入](#input) | `device-verified` |
| [GPU](#gpu) | `device-verified` |
| [网络](#network) | `device-verified` |
| [cellular](#cellular) | `not-applicable` |
| [音频](#audio) | `implemented` |
| [电源](#power) | `device-verified` |
| [usb](#usb) | `host-verified` |
| [镜像组装](#packaging) | `host-verified` |
| [诊断](#diagnostics) | `host-verified` |

## 配置 {#configuration}

`host-verified`

组件: `ArmDTPlatform`, `ArmCpu`, `SoftwareAES`, `XnuPrelink`, `QcomDwc3`.

### 硬件与依赖

- Xiaomi Pad 7 \(uke\), SM7675 Cliffs, and the arm64e iPad17,3 / J820AP 24A446 profile.
- UniXNU-sm7675-common, the patched XNU 12377.121.6 sources, and the matching Apple RELEASE reference.

### 配置

- board.toml uses schema version 2 and uke\_ipados27\_defconfig.
- The board selects the component set and replaces kernel.archives for the 24A446 ABI. Patch order is arch, SoC, OS, then device. feeds.toml pins the shipped GPU, display, CPU, Wi-Fi, USB, storage and prelink sources.

### 操作步骤

- Run ./unixnu fetch and ./unixnu status from the UniXNU checkout with the Uke device selected.
- Build the kernel and payload from the recorded source pins and matching local firmware and signed root inputs.

### 开发经验

- Uke uses sheng-derived host and peripheral services against the 24A446 ABI. The stock DTB and ABL handoff stay in the boot pair.
- XR10 direct scanout remains opt-in via uke-dp-xr10=1.

### 完成条件

- Boot artifacts contain the expected board ADT, runtime archives and prelink bindings.

### 当前范围

- The formal build depends on the matching IPSW, OEM boot assets and owner-signed root inputs.

### 下一步

- Check the next clean checkout against these feed pins and record the resolved build inputs.

### 证据

- `host`: [Formal XR10 candidate built with pinned inputs and no new unresolved prelink bindings.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

## 固件与启动 {#firmware}

`implemented`

组件: `DarwinBoot`.

### 硬件与依赖

- OEM ABL and boot image assets, Mu-Silicium ukePkg, and the UKEESP FAT payload.

### 配置

- Use Platforms/Xiaomi/ukePkg/uke.dsc, FD base 0xa7100000, a 3 MiB FD, and the OEM memory and framebuffer handoff. PSCI uses SMC.

### 操作步骤

- Build the UEFI firmware with ./unixnu build firmware using the uke platform. Package it with the matched Android boot pair.

### 开发经验

- The UEFI loader exposes memory status and the previous panic line. ABL initrd placement constrains the loader and payload reservations.

### 完成条件

- UEFI hands the ADT, initrd and panel to XNU without overlapping the firmware or reserved ranges.

### 当前范围

- The XR10 boot pair was written successfully. Its firmware handoff and subsequent boot await the next device observation.

### 下一步

- Record UEFI handoff and first XNU progress from the XR10 image.

### 证据

- `source`: [Board firmware build settings, DTB handling and payload reservations.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/board.toml)

## CPU 与中断 {#cpu}

`device-verified`

组件: `ArmCpu`, `ArmDTPlatform`, `ArmVirtPlatform`.

### 硬件与依赖

- Eight Kryo CPU affinities 0x000 through 0x700, GIC, PSCI and the 19.2 MHz architectural counter.

### 配置

- dts/uke.dts describes both clusters. sheng-smp=1 and armcpu-spi-ipi=1 select the SMP and SPI IPI path.

### 操作步骤

- Check the eight CPU nodes in the ADT. Compare per-core IRQ, timer and IPI counters in UUID-matched persistent traces.

### 开发经验

- The battery-refresh trace showed IRQ, timer and IPI progress on all eight CPUs from 184 to 2408 seconds. Later normal use had no reported repeat of the earlier CPU freeze.

### 完成条件

- All eight CPUs online with progressing timers and cross-core IPIs.

### 当前范围

- Crystal-rate timing and prolonged load or suspend qualification remain separate from the observed normal-use trace.

### 下一步

- Collect per-CPU timer and IPI progress if a new stall occurs.

### 证据

- `device`: [All eight CPUs advanced IRQ, timer and IPI counters across the recorded interval.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/CPU-TRACE-READBACK-20261115.md)
  Command: <code>Read back the UUID 77C55B96 battery-refresh trace and compare adjacent valid per-CPU samples.</code>. Revision: `c97bca260a1b831fce889889204dcacc4878c69d`.

## 内存与 DMA {#memory}

`implemented`

组件: `RamBlock`.

### 硬件与依赖

- OEM memory map, loader-owned RAM, a 32 MiB GMU reservation at 0xc8000000, and the apps SMMU at 0x15000000.

### 配置

- The ADT describes the owned DRAM and outside-memory ranges separately. USB has a coherent stage-1 SID 0x40; display uses SID 0x1c00 with mask 0x02.

### 操作步骤

- Compare generated ADT memory ranges against UEFI reservations. Confirm stream mappings and DMA request bounds before I/O.

### 开发经验

- XNU VM sizing follows owned\_memory\_size. USB, Wi-Fi and touch serialize apps-SMMU allocation; display mappings remain held until retirement is confirmed.

### 完成条件

- VM uses only handed-off RAM and DMA stays within the owning stream and mapped aperture.

### 当前范围

- Historical memory counters predate the current USB and external-display allocation changes.

### 下一步

- Compare the current UKE MEM counters and SMMU fault reports during concurrent external display and USB traffic.

### 证据

- `source`: [ADT, GPU memory and DMA configuration.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/board.toml)
- `host`: [Host regressions passed for display IOMMU bounds and fail-safe buffer retirement.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

## 存储与根卷 {#storage}

`device-verified`

组件: `ShengUfs`, `RamBlock`, `VirtioMmioBlock`, `VirtioMmioConsole`, `VerifiedRoot`.

### 硬件与依赖

- UFS at 0x1d84000, UFS PHY and GCC clocks, the OEM LUN0 GPT, and separate APFS OS and SystemOS windows.
- Persistent Data uses RamBlock writeback. USB disks arrive through xHCI, USB Mass Storage and SCSI block commands.

### 配置

- native-source-storage=1 and native-ufs-root=1 select ShengUfs and VerifiedRoot. The signed policy header travels with the kernel, and the hash tables are in the existing userdata layout.
- 24A446 MobileGestalt reports total capacity from the mounted Data volume.

### 操作步骤

- Check both root-window bounds and manifests before building. Boot the matched pair, open Files, and read and write a detachable USB disk.

### 开发经验

- About formerly used the SystemOS-sized disk0 and reported 6 GB. A later device run reported 215 GB after the capacity fix.
- Files opened and the portable drive transferred data at the expected speed in earlier device testing. The disk took about a minute to appear.

### 完成条件

- Verified roots mount, Data retains writes, Settings shows sensible capacity, and USB storage appears and transfers data in Files.

### 当前范围

- Prior images supply the Files acceptance evidence. The roughly one-minute discovery delay still needs a timing breakdown.

### 下一步

- Correlate SCSI enumeration, Files volume publication and the UI appearance time on one boot.

### 证据

- `device`: [The historical LUN0 and partition O\_DIRECT readbacks agreed after the authorized header recovery, and the production reader matched the restored root header.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/CPU-STALL-ROOT-PANIC-20261114.md)
  Command: <code>Read the restored userdata header on both the LUN and its partition with O_DIRECT; run the production RootLayout parser.</code>. Revision: `02757b828aeec889db09ad8f99daa5465c29ccd5`.
- `source`: [Historical Uke user test confirmed Files, USB drive I/O and the later 215 GB About value.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)

## 显示 {#display}

`host-verified`

组件: `GopFramebuffer`, `NativeUfs`.

### 硬件与依赖

- O82 3200×2136 dual-DSI panel, 120 Hz internal timing, two KTZ8866 backlight ICs, and the SM7675 DPU and DPTX0.
- Native iPadOS secondary framebuffer, IOAV and IOSurface bindings; USB-C DisplayPort Alt Mode and the sink EDID.

### 配置

- In the opt-in uke-dp-xr10=1 route, CTL0 moves the internal left half to DMA1 and leaves the right half on VIG1. VIG0 feeds LM2/PP2/CTL2/INTF0 for DP.
- The measured external mode is HBR2 2560×1440 at 60 Hz. The iPadOS workspace is 1920×1080 points at 2×.

### 操作步骤

- Build the 24A446 legacy display archive and validate its native display ABI.
- Connect a sink, select Extend, check full-frame damage and counters, and repeat disconnect and reconnect.

### 开发经验

- The prior full-damage image removed flicker and black blocks. Its log showed the 3840×2160 b3a8 compositor output at 12.15–12.99 new frames/s, with 73.8 ms median CPU frame preparation.
- The XR10 candidate maps the original color plane, uses QSEED for 3:2 scaling and CSC for XR10-to-SDR, and preserves producer fences and CTL latch retirement.

### 完成条件

- Native extended desktop, correct levels and stable frames at the sink timing, with both internal panel halves intact and reliable reconnect.

### 当前范围

- The original driver passed both constituent atomic tests separately. Recovery exposed no usable external DP mode for combined testing. The flashed XR10 candidate awaits hardware acceptance.

### 下一步

- Confirm the direct IOSurface route and measure external producer cadence and latch cadence on the flashed image.

### 证据

- `host`: [Host checks passed for HBR2 modes, full-frame geometry, XR10 scaling and display DMA ownership.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>Run host-test.py, xr10-direct-host.cpp and verify.py from the XR10 candidate.</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.
- `source`: [Matched pre-XR10 readback identifies 1440p wire timing, HiDPI geometry and CPU-copy throughput on vendor\_boot 9a0fc473220661d6c6a350ad3563da520ef7e060af11dab8801b36784017c7d9.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)

## 输入 {#input}

`device-verified`

组件: `ShengHidInput`, `ShengNovatekTouch`, `QcomGeniSpi`.

### 硬件与依赖

- Novatek NT36532 on GENI SPI QUP0 SE4, GPIOs 16–19, GPIO54 IRQ, O82 firmware, and sheng HID transport.
- USB input uses IOUSBHostHIDDevice with the hub and composite-device classes.

### 配置

- The split internal digitizer reports touch axes and contact IDs independently of keyboard/button reports. Native touch axes are 30480×20320.

### 操作步骤

- Check touchscreen reports, swipe through the iPadOS UI, then attach a keyboard and a mouse through the dock and test both.

### 开发经验

- The upward swipe was accepted after the 24A446 transient-surface fix. The user later confirmed external keyboard and mouse input through the dock.

### 完成条件

- Touch contacts reach BackBoard with the correct classification, and USB keyboards and mice work in the UI.

### 当前范围

- Extended mixed HID tests and resume or rapid replug are separate device checks.

### 下一步

- Exercise touch, mouse and keyboard together during repeat external-display reconnect.

### 证据

- `device`: [The owner confirmed upward swipes no longer froze the UI on CRC 0485290E96ACC9B3.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/PROGRESS.md)
  Command: <code>Record hardware swipe feedback for the archived CA surface-tracking release.</code>. Revision: `5ed46420025be331b51d98207ea6aa679faac9c7`.

## GPU {#gpu}

`device-verified`

组件: `Adreno740`, `AdrenoMetal`, `AdrenoFirmware`, `AdrenoPM4`, `ArmSmmu4K`, `Sm7675Platform`, `Sm8550Platform`, `AirNir`.

### 硬件与依赖

- Adreno 732 gen7\_11\_0 \(0x43030b00\), gen71100 GMU firmware, SM7675 power and SMMU, the 24A446 ABI and pinned Metal-to-Vulkan/Turnip inputs.

### 配置

- NativeAdreno per-process VM, mode-2 preemption, RPMh/GMU votes, AdrenoMetal runtime and owner trust cache. Use source pins in feeds.toml.

### 操作步骤

- Build the accelerator and matching GPU addon. Match the runtime lead-in ABI, submit frames, and verify fence progression before display latch.

### 开发经验

- The previously accepted internal GPU release reached the desktop and rendered apps, icons and widgets. External full-frame repaint and host-submit-before-scanout now preserve the target across attachment and detachment.

### 完成条件

- Accelerated apps and system UI present correctly with ordered fences and consistent full-frame output.

### 当前范围

- Earlier internal renderer acceptance predates XR10 direct scanout. Sustained frame-time targets and multi-client recovery remain open.

### 下一步

- Collect producer and scanout timing with both displays active on the XR10 image.

### 证据

- `device`: [Owner accepted the desktop, Settings, widgets and upward gestures on CRC 90B6BC701210D9DB.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/GPU-IOS27.md)
  Command: <code>Inspect user-observation-success.json for that flashed image.</code>. Revision: `10a077a8b4de9b8333069089e808ab8ad2cba8bd`.

## 网络 {#network}

`device-verified`

组件: `Sm7675Platform`, `Ath12kWifi`.

### 硬件与依赖

- WCN6750 WPSS on AHB, PAS6, GLINK/QRTR/QMI and WLFW, with MSI/SMMU-backed DMA.

### 配置

- WPSS at 0x9bb00000 and MSA at 0xa6400000. apps\_smmu SID 0x1400 mask 1, IOVA aperture 0xb0000000 plus 256 MiB. sheng WifiNet publishes en0 and Apple80211.

### 操作步骤

- Validate the firmware and board data, then check WLFW, scan, association, DHCP and TCP on an open and a protected AP.

### 开发经验

- The V4.9.7 baseline passed Settings Wi-Fi, open and password-protected association, DHCP and app/Safari access. Scan-result expiry uses the continuous clock.

### 完成条件

- Settings lists Wi-Fi and en0 carries bidirectional traffic after association.

### 当前范围

- Repeated cold boot, toggle, roaming, sleep/wake and long-run power remain separate checks.

### 下一步

- Measure reconnect and network I/O while USB host and the external display are active.

### 证据

- `device`: [A matched 879437D238BB23B0 capture showed six successful WMI scans, association, DHCP ACK and bidirectional TCP.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/BACKLIGHT-PASS-WIFI-CONTROL-20261111.md)
  Command: <code>Read the same-boot log and read-only Data capture.</code>. Revision: `bdc9a9def4f21c8a4a438b46860882ab2933eb49`.

## cellular {#cellular}

`not-applicable`

### 硬件与依赖

- Xiaomi Pad 7 Wi-Fi board configuration.

### 配置

- The Uke component set contains the WCN6750 Wi-Fi path and omits QcomBaseband.

### 操作步骤

- Confirm the product variant and component inventory before enabling any modem profile.

### 开发经验

- The current Uke board configuration has no cellular modem target.

### 完成条件

- Wi-Fi supplies the network interface for this board.

### 当前范围

- The Wi-Fi-only SKU has no cellular SIM, RF or data-session support to validate.

### 下一步

- Reassess only if a distinct cellular SKU is added.

### 证据

按下一步操作收集证据。

## 音频 {#audio}

`implemented`

### 硬件与依赖

- Cliffs ADSP PAS1 and DTB PAS36, stock ADSP firmware, GLINK, QRTR, GPR, APM and the audio route source data.

### 配置

- The staged adsp=2 battery=1 audio=1 profile queries APM readiness and shares firmware resources with battery service.

### 操作步骤

- Run python3 scripts/check-uke-dsp-host.py. Boot the staged candidate and record UKE ADSP and UKE AUDIO lines.

### 开发经验

- Device captures reached ADSP, GLINK and APM readiness. Audio mode 1 is a control-path readiness check.

### 完成条件

- The DSP boots, APM replies, and separate playback and capture tests pass on actual endpoints.

### 当前范围

- Codec endpoints, playback and capture routes remain open.

### 下一步

- Map codec, clocks and route endpoints to reachable audio firmware services.

### 证据

- `source`: [ADSP, GLINK and APM bring-up history and route scope.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/DSP-AUDIO-POWER.md)

## 电源 {#power}

`device-verified`

组件: `Adreno740`, `AppleKeyStoreState`.

### 硬件与依赖

- RPMh and AOSS clocks and regulators, PMIC GLINK battery service, UCSI connector state, and the dual KTZ8866 backlight.

### 配置

- Use sheng-pmgr=2 and the shared battery event path. Software key-state reports no passcode with sheng-aks-sls=3 for pairing. USB and backlight serialize their shared GENI SE0 access.

### 操作步骤

- With the power profile selected, capture battery percentage, charge status and cable transitions together with regulator, timeout and display reports.

### 开发经验

- The user verified battery percent and charge UI on D4EFA944BD2B2081. The subsequent battery service handles field timeouts independently.

### 完成条件

- Battery status and charger state follow the hardware while repeated attach events and backlight control remain responsive.

### 当前范围

- Reported battery acceptance concerns basic UI. Charge accuracy, long-duration dock behavior and deep suspend remain open.

### 下一步

- Measure charge units and power-role transitions through detach and reattach.

### 证据

- `device`: [User confirmed battery percentage and charging indication on D4EFA944BD2B2081.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/DSP-AUDIO-POWER.md)
  Command: <code>Observe the battery percentage and charging icon with the staged image booted.</code>. Revision: `4eb1665f9295f00d815c31ac847fb265c45b7766`.

## usb {#usb}

`host-verified`

组件: `QcomDwc3`, `Sm7675Platform`, `ArmCpu`.

### 硬件与依赖

- SM7675 DWC3/xHCI, QMP USB3/DP PHY, WCD939x USB2 switch/eUSB2 repeater, PMIC GLINK UCSI and shared GENI SE0.

### 配置

- Use QcomDwc3 from feeds.toml and the 24A446 xDCI/xHCI ABI anchors. The device patch stack brings up native USB host, hub, HID and mass-storage classes.

### 操作步骤

- Build the 24A446 ABI shim and run the controller UCSI and board role/link host tests. Test keyboard, mouse and USB storage through the dock, then exercise USB-C orientation and Alt Mode.

### 开发经验

- UCSI negotiates connector data role, retrieves alternate modes and handles DisplayPort HPD. Hubs, keyboard, mouse and drive transfer were accepted on earlier device builds.

### 完成条件

- USB peripherals enumerate under their correct class, drive I/O succeeds, and Alt Mode retains USB support when the negotiated lane assignment allows it.

### 当前范围

- Current matrix coverage does not include every dock, cable, orientation, drive filesystem or peripheral pairing behavior.

### 下一步

- Measure mount latency and repeated dock reconnect with host and DP active.

### 证据

- `host`: [Controller UCSI, board Alt Mode and HBR2 link-policy tests passed.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>clang++ -std=c++17 -I. tests/ucsi_host.cpp -o ucsi-host &amp;&amp; ./ucsi-host; run the Uke XR10 candidate host-test.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

## 镜像组装 {#packaging}

`host-verified`

组件: `DarwinBoot`, `XnuPrelink`, `VerifiedRoot`.

### 硬件与依赖

- 24A446 IPSW, XNU 12377.121.6, the matched Apple RELEASE/LTO reference, generated 24A446 ADT, owner trust cache and OEM boot assets.

### 配置

- 160 MiB raw FAT with UEFI compression and Android v4 vendor\_boot. Preserve the OEM DTB, vendor table and bootconfig. Keep boot arguments within the 1000-byte Android limit.

### 操作步骤

- Run ./unixnu build kernel and ./unixnu build payload from the core checkout. Package boot and vendor\_boot together and round-trip unpack the vendor payload.

### 开发经验

- The XR10 package used 984 bytes of boot arguments and added zero unresolved prelink bindings. The two-slot boot pair was written successfully.
- CI resolves the XNU revision and four-layer patch order through UniXNU. All 149 patches applied on a clean XNU 12377.121.6 checkout.

### 完成条件

- Validated boot and vendor images fit the destination partitions and the boot chain hands off a matching payload.

### 当前范围

- Successful transport records only the four writes, slot selection and reboot. Runtime acceptance remains pending.

### 下一步

- Attach device boot and XR10 acceptance to the exact vendor\_boot hash once observed.

### 证据

- `host`: [Formal kernel and payload builds and the vendor\_boot payload round trip passed for c0a6f7ec9315.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.
- `host`: [All 149 resolved patches applied to clean XNU 12377.121.6 at ac9718fb1af618d5ce8678d0dc6e8a58f252216f.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>bash scripts/check-xnu-patch-set.sh</code>. Revision: `380cfbf686f41ae2a2ebf44835ce541a10241bcd`.

## 诊断 {#diagnostics}

`host-verified`

组件: `AppleKeyStoreState`, `XnuPrelink`.

### 硬件与依赖

- Persistent UKELLOG1 ring, panic screen, boot progress, and DXE previous-panic readout.

### 配置

- Select sheng-log=1 for persistent logs. Correlate display HPD, EDID, fence, latch, IOSurface and display sink status within the same boot.

### 操作步骤

- Capture the persistent ring through read-only Recovery, select the fresh boot UUID, and symbolize against the exact linked kernel.

### 开发经验

- The ring includes older boots. Image-matched backtraces and CRC-valid sequence filtering are needed before associating a panic or performance sample with a trial.

### 完成条件

- A single boot has a usable event sequence and exact kernel and boot-image identity.

### 当前范围

- The current XR10 image has build and flash evidence. No same-boot device trace is recorded yet.

### 下一步

- Collect the next same-boot trace if XR10 cadence, levels or reconnect behavior fail.

### 证据

- `host`: [XR10 image verification confirmed that DP sink status, CRC, display latch and frame counters are linked.](https://github.com/Allenwdk/UniXNU-uke/blob/cab36c6bc8e3e63be93309a5ccaaa8a607bfc583/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

</div>

# Xiaomi Pad 7 / POCO Pad X1 \(uke\)

[Allenwdk/UniXNU-uke](https://github.com/Allenwdk/UniXNU-uke)

<div v-pre>

Xiaomi Pad 7 runs iPadOS 27.0.1 with accelerated internal graphics, Wi-Fi, touch and USB host storage. Native XR10 HiDPI extended desktop and both panel outputs were device-observed. The current image has DP diagnostics off by default, and its restored Wi-Fi service passed the owner test.

Source record: [porting.toml](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/porting.toml), `358beac17b32e4efec06595c469a4212032af50e`.

This page is generated from the device record.

| Area | Status |
| --- | --- |
| [Configuration](#configuration) | `host-verified` |
| [Firmware and boot](#firmware) | `implemented` |
| [CPU and interrupts](#cpu) | `device-verified` |
| [Memory and DMA](#memory) | `implemented` |
| [Storage and root](#storage) | `device-verified` |
| [Display](#display) | `device-verified` |
| [Input](#input) | `device-verified` |
| [focus-pen-pro](#focus-pen-pro) | `device-verified` |
| [GPU](#gpu) | `device-verified` |
| [Network](#network) | `device-verified` |
| [bluetooth](#bluetooth) | `device-verified` |
| [cellular](#cellular) | `not-applicable` |
| [Audio](#audio) | `implemented` |
| [Power](#power) | `device-verified` |
| [usb](#usb) | `host-verified` |
| [Image assembly](#packaging) | `host-verified` |
| [Diagnostics](#diagnostics) | `host-verified` |

## Configuration {#configuration}

`host-verified`

Components: `ArmDTPlatform`, `ArmCpu`, `SoftwareAES`, `XnuPrelink`, `QcomDwc3`.

### Hardware and dependencies

- Xiaomi Pad 7 \(uke\), SM7675 Cliffs, and the arm64e iPad17,3 / J820AP 24A446 profile.
- UniXNU-sm7675-common, the patched XNU 12377.121.6 sources, and the matching Apple RELEASE reference.

### Configuration

- board.toml uses schema version 2 and uke\_ipados27\_defconfig.
- The board selects the component set and replaces kernel.archives for the 24A446 ABI. Patch order is arch, SoC, OS, then device. feeds.toml pins the shipped GPU, display, CPU, Wi-Fi, USB, storage and prelink sources.

### Procedure

- Run ./unixnu fetch and ./unixnu status from the UniXNU checkout with the Uke device selected.
- Build the kernel and payload from the recorded source pins and matching local firmware and signed root inputs.

### Development findings

- The display source pins include the OEM split-panel handoff and gate DP diagnostics behind uke-dp-debug=1.
- Uke uses sheng-derived host and peripheral services against the 24A446 ABI. The stock DTB and ABL handoff stay in the boot pair.
- The default payload uses panel-only desktop mode with exact scanout and frame diagnostics. The DisplayPort desktop can be selected with uke-dp-desktop=1.

### Completion criteria

- Boot artifacts contain the expected board ADT, runtime archives and prelink bindings.

### Current limits

- The formal build depends on the matching IPSW, OEM boot assets and owner-signed root inputs.

### Next action

- Check the next clean checkout against these feed pins and record the resolved build inputs.

### Evidence

- `host`: [Formal XR10 candidate built with pinned inputs and no new unresolved prelink bindings.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

## Firmware and boot {#firmware}

`implemented`

Components: `DarwinBoot`.

### Hardware and dependencies

- OEM ABL and boot image assets, Mu-Silicium ukePkg, and the UKEESP FAT payload.

### Configuration

- Use Platforms/Xiaomi/ukePkg/uke.dsc, FD base 0xa7100000, a 3 MiB FD, and the OEM memory and framebuffer handoff. PSCI uses SMC.

### Procedure

- Build the UEFI firmware with ./unixnu build firmware using the uke platform. Package it with the matched Android boot pair.

### Development findings

- The UEFI loader exposes memory status and the previous panic line. ABL initrd placement constrains the loader and payload reservations.

### Completion criteria

- UEFI hands the ADT, initrd and panel to XNU without overlapping the firmware or reserved ranges.

### Current limits

- The later split-panel and Wi-Fi service recovery images were used on the device. Broad repeated-boot, sleep and resume qualification remains open.

### Next action

- Trace UEFI and the framebuffer handoff if a future cold boot or suspend test fails.

### Evidence

- `source`: [Board firmware build settings, DTB handling and payload reservations.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/board.toml)

## CPU and interrupts {#cpu}

`device-verified`

Components: `ArmCpu`, `ArmDTPlatform`, `ArmVirtPlatform`.

### Hardware and dependencies

- Eight Kryo CPU affinities 0x000 through 0x700, GIC, PSCI and the 19.2 MHz architectural counter.

### Configuration

- dts/uke.dts describes both clusters. sheng-smp=1 and armcpu-spi-ipi=1 select the SMP and SPI IPI path.

### Procedure

- Check the eight CPU nodes in the ADT. Compare per-core IRQ, timer and IPI counters in UUID-matched persistent traces.

### Development findings

- The battery-refresh trace showed IRQ, timer and IPI progress on all eight CPUs from 184 to 2408 seconds. Later normal use had no reported repeat of the earlier CPU freeze.

### Completion criteria

- All eight CPUs online with progressing timers and cross-core IPIs.

### Current limits

- Crystal-rate timing and prolonged load or suspend qualification remain separate from the observed normal-use trace.

### Next action

- Collect per-CPU timer and IPI progress if a new stall occurs.

### Evidence

- `device`: [All eight CPUs advanced IRQ, timer and IPI counters across the recorded interval.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/CPU-TRACE-READBACK-20261115.md)
  Command: <code>Read back the UUID 77C55B96 battery-refresh trace and compare adjacent valid per-CPU samples.</code>. Revision: `c97bca260a1b831fce889889204dcacc4878c69d`.

## Memory and DMA {#memory}

`implemented`

Components: `RamBlock`.

### Hardware and dependencies

- OEM memory map, loader-owned RAM, a 32 MiB GMU reservation at 0xc8000000, and the apps SMMU at 0x15000000.

### Configuration

- The ADT describes the owned DRAM and outside-memory ranges separately. USB has a coherent stage-1 SID 0x40; display uses SID 0x1c00 with mask 0x02.

### Procedure

- Compare generated ADT memory ranges against UEFI reservations. Confirm stream mappings and DMA request bounds before I/O.

### Development findings

- XNU VM sizing follows owned\_memory\_size. USB, Wi-Fi and touch serialize apps-SMMU allocation; display mappings remain held until retirement is confirmed.

### Completion criteria

- VM uses only handed-off RAM and DMA stays within the owning stream and mapped aperture.

### Current limits

- Historical memory counters predate the current USB and external-display allocation changes.

### Next action

- Compare the current UKE MEM counters and SMMU fault reports during concurrent external display and USB traffic.

### Evidence

- `source`: [ADT, GPU memory and DMA configuration.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/board.toml)
- `host`: [Host regressions passed for display IOMMU bounds and fail-safe buffer retirement.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

## Storage and root {#storage}

`device-verified`

Components: `ShengUfs`, `RamBlock`, `VirtioMmioBlock`, `VirtioMmioConsole`, `VerifiedRoot`.

### Hardware and dependencies

- UFS at 0x1d84000, UFS PHY and GCC clocks, the OEM LUN0 GPT, and separate APFS OS and SystemOS windows.
- Persistent Data uses RamBlock writeback. USB disks arrive through xHCI, USB Mass Storage and SCSI block commands.

### Configuration

- native-source-storage=1 and native-ufs-root=1 select ShengUfs and VerifiedRoot. The signed policy header travels with the kernel, and the hash tables are in the existing userdata layout.
- 24A446 MobileGestalt reports total capacity from the mounted Data volume.

### Procedure

- Check both root-window bounds and manifests before building. Boot the matched pair, open Files, and read and write a detachable USB disk.

### Development findings

- About formerly used the SystemOS-sized disk0 and reported 6 GB. A later device run reported 215 GB after the capacity fix.
- Files opened and the portable drive transferred data at the expected speed in earlier device testing. The disk took about a minute to appear.

### Completion criteria

- Verified roots mount, Data retains writes, Settings shows sensible capacity, and USB storage appears and transfers data in Files.

### Current limits

- Prior images supply the Files acceptance evidence. The roughly one-minute discovery delay still needs a timing breakdown.

### Next action

- Correlate SCSI enumeration, Files volume publication and the UI appearance time on one boot.

### Evidence

- `device`: [The historical LUN0 and partition O\_DIRECT readbacks agreed after the authorized header recovery, and the production reader matched the restored root header.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/CPU-STALL-ROOT-PANIC-20261114.md)
  Command: <code>Read the restored userdata header on both the LUN and its partition with O_DIRECT; run the production RootLayout parser.</code>. Revision: `02757b828aeec889db09ad8f99daa5465c29ccd5`.
- `source`: [Historical Uke user test confirmed Files, USB drive I/O and the later 215 GB About value.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)

## Display {#display}

`device-verified`

Components: `GopFramebuffer`, `NativeUfs`.

### Hardware and dependencies

- O82 3200×2136 dual-DSI panel, 120 Hz internal timing, two KTZ8866 backlight ICs, and the SM7675 DPU and DPTX0.
- Native iPadOS secondary framebuffer, IOAV and IOSurface bindings; USB-C DisplayPort Alt Mode and the sink EDID.

### Configuration

- In the opt-in uke-dp-xr10=1 route, CTL0 moves the internal left half to DMA1 and leaves the right half on VIG1. VIG0 feeds LM2/PP2/CTL2/INTF0 for DP.
- The measured external mode is HBR2 2560×1440 at 60 Hz. The iPadOS workspace is 1920×1080 points at 2×.

### Procedure

- Build the 24A446 legacy display archive and validate its native display ABI.
- Connect a sink, select Extend, check full-frame damage and counters, and repeat disconnect and reconnect.

### Development findings

- During a dual-output run, the panel scanned at 120 Hz and DP at 60 Hz while the measured external presentation rate fell from 35.5 to 22.0 frames/s.
- The owner confirmed both displays work after the VIG1 right-source and opaque mixer stage fix. The panel DMA1 handoff preserved all four measured pixel signatures.
- The prior full-damage image removed flicker and black blocks. Its log showed the 3840×2160 b3a8 compositor output at 12.15–12.99 new frames/s, with 73.8 ms median CPU frame preparation.
- The XR10 candidate maps the original color plane, uses QSEED for 3:2 scaling and CSC for XR10-to-SDR, and preserves producer fences and CTL latch retirement.

### Completion criteria

- Native extended desktop, correct levels and stable frames at the sink timing, with both internal panel halves intact and reliable reconnect.

### Current limits

- Dual-display output is device-observed on the split-stage image. Sustained cadence and a matched quiet-build performance comparison remain open.

### Next action

- Correlate each display presentation with its own IOSurface producer fence and CTL latch on a matched workload.

### Evidence

- `host`: [Host checks passed for HBR2 modes, full-frame geometry, XR10 scaling and display DMA ownership.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>Run host-test.py, xr10-direct-host.cpp and verify.py from the XR10 candidate.</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.
- `source`: [Matched pre-XR10 readback identifies 1440p wire timing, HiDPI geometry and CPU-copy throughput on vendor\_boot 9a0fc473220661d6c6a350ad3563da520ef7e060af11dab8801b36784017c7d9.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
- `device`: [The owner confirmed dual-screen output on vendor\_boot 93c30b07eb1b. Same-boot readback found four matching panel signatures before and after handoff.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>Connect HDMI in Extend mode and compare DMA1, mixer and interface registers across the same-boot capture.</code>. Revision: `dd0e3ec0e882d2aa2d0acf976e14c88f3db643fd`.

## Input {#input}

`device-verified`

Components: `ShengHidInput`, `ShengNovatekTouch`, `QcomGeniSpi`.

### Hardware and dependencies

- Novatek NT36532 on GENI SPI QUP0 SE4, GPIOs 16–19, GPIO54 IRQ, O82 firmware, and sheng HID transport.
- USB input uses IOUSBHostHIDDevice with the hub and composite-device classes.

### Configuration

- The split internal digitizer reports touch axes and contact IDs independently of keyboard/button reports. Native touch axes are 30480×20320.

### Procedure

- Check touchscreen reports, swipe through the iPadOS UI, then attach a keyboard and a mouse through the dock and test both.

### Development findings

- The upward swipe was accepted after the 24A446 transient-surface fix. The user later confirmed external keyboard and mouse input through the dock.

### Completion criteria

- Touch contacts reach BackBoard with the correct classification, and USB keyboards and mice work in the UI.

### Current limits

- Extended mixed HID tests and resume or rapid replug are separate device checks.

### Next action

- Exercise touch, mouse and keyboard together during repeat external-display reconnect.

### Evidence

- `device`: [The owner confirmed upward swipes no longer froze the UI on CRC 0485290E96ACC9B3.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/PROGRESS.md)
  Command: <code>Record hardware swipe feedback for the archived CA surface-tracking release.</code>. Revision: `5ed46420025be331b51d98207ea6aa679faac9c7`.

## focus-pen-pro {#focus-pen-pro}

`device-verified`

Components: `NativeFocusPenPro`.

### Hardware and dependencies

- P81c system BLE bond, NT36532 pen frames, panel calibration and PMIC attachment status.

### Configuration

- The NativeFocusPenPro submodule is embedded by the Uke kernel recipe. The ADT selects the Pencil configuration.

### Procedure

- Run the radio and stroke host tests from the driver checkout, then build the Uke kernel and signed runtime.

### Development findings

- The radio protocol and stroke tests run directly from the extracted component checkout. The owner reported no issues on the flashed split image.

### Completion criteria

- The extracted component resolves to its pinned checkout and supplies the native kernel and userspace sources. The rebuilt split image passed the owner's retest.

### Current limits

- The retest establishes the split-image baseline. First-time pairing, long-run reconnect, continuous roll and Find My are separate acceptance items.

### Next action

- Record individual pairing, reconnect and Pro feature results when they are tested.

### Evidence

- `host`: [The extracted FE11/FE12 radio regression and the C++ stroke regression both passed.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/FOCUS-PEN-PRO-20261122.md)
  Command: <code>Compile and run Test/uke_pen_radio_host.c and Test/uke_pen_stroke_host.cpp from NativeFocusPenPro.</code>. Revision: `b946ec01745f4888020339f2137a634339b9443f`.
- `device`: [The owner reported no issues after retesting vendor\_boot 4f0527af845acad88 from the split component build.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/FOCUS-PEN-PRO-20261122.md)
  Command: <code>Flash the matching boot and vendor_boot pair on Uke, set slot A, reboot and record the owner's retest.</code>. Revision: `b946ec01745f4888020339f2137a634339b9443f`.

## GPU {#gpu}

`device-verified`

Components: `Adreno740`, `AdrenoMetal`, `AdrenoFirmware`, `AdrenoPM4`, `ArmSmmu4K`, `Sm7675Platform`, `Sm8550Platform`, `AirNir`.

### Hardware and dependencies

- Adreno 732 gen7\_11\_0 \(0x43030b00\), gen71100 GMU firmware, SM7675 power and SMMU, the 24A446 ABI and pinned Metal-to-Vulkan/Turnip inputs.

### Configuration

- NativeAdreno per-process VM, mode-2 preemption, RPMh/GMU votes, AdrenoMetal runtime and owner trust cache. Use source pins in feeds.toml.

### Procedure

- Build the accelerator and matching GPU addon. Match the runtime lead-in ABI, submit frames, and verify fence progression before display latch.

### Development findings

- The previously accepted internal GPU release reached the desktop and rendered apps, icons and widgets. The dual-output dirty-region run on vendor\_boot 99861d4cc6b8 recorded 1450 exact producer fence latches on the panel and 1532 on DP. All 1395 independently matched writers used the fence that released the corresponding swap.
- The panel-only readback on vendor\_boot 17d170cbf39b recorded 110115 skipped GMEM tiles out of 361665 and a 17.04 ms median touch presentation interval. All 1802 independently matched writers used the corresponding fence.
- The follow-up encoding cleanup on vendor\_boot 4cbfb64b3d25 passed image assembly. A default build reproduced its kernel, boot arguments, GPU addon and trust inputs. Runtime performance of the follow-up image awaits verification.

### Completion criteria

- Accelerated apps and system UI present correctly with ordered fences and consistent full-frame output.

### Current limits

- Earlier internal renderer acceptance predates XR10 direct scanout. Sustained frame-time targets and multi-client recovery remain open.

### Next action

- Reduce panel encode backlog and large GMEM passes, then compare single-panel animation cadence with a matched workload.

### Evidence

- `device`: [Owner accepted the desktop, Settings, widgets and upward gestures on CRC 90B6BC701210D9DB.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/GPU-IOS27.md)
  Command: <code>Inspect user-observation-success.json for that flashed image.</code>. Revision: `10a077a8b4de9b8333069089e808ab8ad2cba8bd`.

## Network {#network}

`device-verified`

Components: `Sm7675Platform`, `Ath12kWifi`.

### Hardware and dependencies

- WCN6750 WPSS on AHB, PAS6, GLINK/QRTR/QMI and WLFW, with MSI/SMMU-backed DMA.

### Configuration

- WPSS at 0x9bb00000 and MSA at 0xa6400000. apps\_smmu SID 0x1400 mask 1, IOVA aperture 0xb0000000 plus 256 MiB. sheng WifiNet publishes en0 and Apple80211.

### Procedure

- Validate the firmware and board data, then check WLFW, scan, association, DHCP and TCP on an open and a protected AP.

### Development findings

- The current image restores the signed V4.9.7 supplicant matched by the existing signed launch cache and authorization record. The device owner confirmed Wi-Fi works again.
- The V4.9.7 baseline passed Settings Wi-Fi, open and password-protected association, DHCP and app/Safari access. Scan-result expiry uses the continuous clock.

### Completion criteria

- Settings lists Wi-Fi and en0 carries bidirectional traffic after association.

### Current limits

- Repeated cold boot, toggle, roaming, sleep/wake and long-run power remain separate checks.

### Next action

- Measure reconnect and network I/O while USB host and the external display are active.

### Evidence

- `device`: [A matched 879437D238BB23B0 capture showed six successful WMI scans, association, DHCP ACK and bidirectional TCP.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/BACKLIGHT-PASS-WIFI-CONTROL-20261111.md)
  Command: <code>Read the same-boot log and read-only Data capture.</code>. Revision: `bdc9a9def4f21c8a4a438b46860882ab2933eb49`.
- `device`: [The owner confirmed Wi-Fi recovery on vendor\_boot b92e39d1aead. Host checks verified the exact accepted supplicant signature and the control protocol.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/WIFI-WCN6750.md)
  Command: <code>Boot b92e39d1aead and test Wi-Fi while keeping the packaged launch cache and configuration.</code>. Revision: `dd0e3ec0e882d2aa2d0acf976e14c88f3db643fd`.

## bluetooth {#bluetooth}

`device-verified`

Components: `QcaBluetooth`.

### Hardware and dependencies

- Uke WCN6750, QUP1 SE2, the original BTFM firmware image and the 24A446 native Bluetooth daemon.

### Configuration

- The paired runtime uses GENI DMA at 3 Mbaud and publishes the controller through UART.SK. The paired image enables the driver with bluetooth=1. The ADT defaults detailed diagnostics off.

### Procedure

- Run the QcaBluetooth host checks and check-bluetooth-platform.py. Build the matched kernel, runtime and payload before device validation.

### Development findings

- The WCN6750 MBN and TLV fixtures passed, the native capability checks passed, and Apple libxpc and codesign accepted the merged cache.
- The owner confirmed enable, discovery, pairing and audio output on 9c012ce8e068. The same boot showed successful native service launches and connected data and audio pipes.

### Completion criteria

- Classic and LE pairing, reconnect after reboot, power toggle, A2DP, supported AirPods controls and Wi-Fi coexistence pass on the tablet.

### Current limits

- The accepted baseline covers the owner's accessory and the captured session. Reconnect after reboot, repeated toggles, separate LE and Classic tests, microphone, sleep and sustained Wi-Fi coexistence remain open. The quiet image has host evidence.

### Next action

- Confirm the quiet image on the tablet and test reconnection after reboot.

### Evidence

- `host`: [The Mac runner merged BlueTool policy into the accepted Wi-Fi cache and verified the resulting cache with Apple libxpc and codesign.](https://github.com/Allenwdk/UniXNU-uke/actions/runs/44644572925)
  Command: <code>Build Uke Bluetooth launchd cache</code>. Revision: `85953d31543238cf239238ffa9f2573acaa2dffa`.
- `host`: [ASan/UBSan fixtures exercise WCN6750 MBN, TLV fallback, a failed startup followed by retry, and the existing WCN7850 path.](https://github.com/Allenwdk/QcaBluetooth/tree/9243c3c8f50a667135fa857464eeebf0d62d7254)
  Command: <code>python3 tools/test-runtime.py</code>. Revision: `9243c3c8f50a667135fa857464eeebf0d62d7254`.
- `device`: [Image 9c012ce8e068 passed enable, discovery, pairing and audio output in the owner test. The matched log shows ready controller firmware, one observed launch per native job, UART.SK and AudioPipe. Revision identifies the controller component used.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/BLUETOOTH-WCN6750.md)
  Command: <code>Boot 9c012ce8e068, enable Bluetooth in Settings, discover and pair an accessory, play audio and read the same-boot kernel log.</code>. Revision: `a84d7d3117af0e8d723ce7350d247fbec3939a25`.

## cellular {#cellular}

`not-applicable`

### Hardware and dependencies

- Xiaomi Pad 7 Wi-Fi board configuration.

### Configuration

- The Uke component set contains the WCN6750 Wi-Fi path and omits QcomBaseband.

### Procedure

- Confirm the product variant and component inventory before enabling any modem profile.

### Development findings

- The current Uke board configuration has no cellular modem target.

### Completion criteria

- Wi-Fi supplies the network interface for this board.

### Current limits

- The Wi-Fi-only SKU has no cellular SIM, RF or data-session support to validate.

### Next action

- Reassess only if a distinct cellular SKU is added.

### Evidence

Collect evidence using the next action.

## Audio {#audio}

`implemented`

### Hardware and dependencies

- Cliffs ADSP PAS1 and DTB PAS36, stock ADSP firmware, GLINK, QRTR, GPR, APM and the audio route source data.

### Configuration

- The staged adsp=2 battery=1 audio=1 profile queries APM readiness and shares firmware resources with battery service.

### Procedure

- Run python3 scripts/check-uke-dsp-host.py. Boot the staged candidate and record UKE ADSP and UKE AUDIO lines.

### Development findings

- The shared display and battery archive links the quiet DP diagnostic policy for Alt Mode notifications.
- Device captures reached ADSP, GLINK and APM readiness. Audio mode 1 is a control-path readiness check.

### Completion criteria

- The DSP boots, APM replies, and separate playback and capture tests pass on actual endpoints.

### Current limits

- Codec endpoints, playback and capture routes remain open.

### Next action

- Map codec, clocks and route endpoints to reachable audio firmware services.

### Evidence

- `source`: [ADSP, GLINK and APM bring-up history and route scope.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/DSP-AUDIO-POWER.md)

## Power {#power}

`device-verified`

Components: `Adreno740`, `AppleKeyStoreState`.

### Hardware and dependencies

- RPMh and AOSS clocks and regulators, PMIC GLINK battery service, UCSI connector state, and the dual KTZ8866 backlight.

### Configuration

- Use sheng-pmgr=2 and the shared battery event path. Software key-state reports no passcode with sheng-aks-sls=3 for pairing. USB and backlight serialize their shared GENI SE0 access.

### Procedure

- With the power profile selected, capture battery percentage, charge status and cable transitions together with regulator, timeout and display reports.

### Development findings

- The shared PMIC GLINK Alt Mode notifications use the quiet DP diagnostic policy while retaining the same role and power handling.
- The user verified battery percent and charge UI on D4EFA944BD2B2081. The subsequent battery service handles field timeouts independently.

### Completion criteria

- Battery status and charger state follow the hardware while repeated attach events and backlight control remain responsive.

### Current limits

- Reported battery acceptance concerns basic UI. Charge accuracy, long-duration dock behavior and deep suspend remain open.

### Next action

- Measure charge units and power-role transitions through detach and reattach.

### Evidence

- `device`: [User confirmed battery percentage and charging indication on D4EFA944BD2B2081.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/DSP-AUDIO-POWER.md)
  Command: <code>Observe the battery percentage and charging icon with the staged image booted.</code>. Revision: `4eb1665f9295f00d815c31ac847fb265c45b7766`.

## usb {#usb}

`host-verified`

Components: `QcomDwc3`, `Sm7675Platform`, `ArmCpu`.

### Hardware and dependencies

- SM7675 DWC3/xHCI, QMP USB3/DP PHY, WCD939x USB2 switch/eUSB2 repeater, PMIC GLINK UCSI and shared GENI SE0.

### Configuration

- Use QcomDwc3 from feeds.toml and the 24A446 xDCI/xHCI ABI anchors. The device patch stack brings up native USB host, hub, HID and mass-storage classes.

### Procedure

- Build the 24A446 ABI shim and run the controller UCSI and board role/link host tests. Test keyboard, mouse and USB storage through the dock, then exercise USB-C orientation and Alt Mode.

### Development findings

- Routine DP Alt Mode and training diagnostics default to off. Link failures still report their errors.
- UCSI negotiates connector data role, retrieves alternate modes and handles DisplayPort HPD. Hubs, keyboard, mouse and drive transfer were accepted on earlier device builds.

### Completion criteria

- USB peripherals enumerate under their correct class, drive I/O succeeds, and Alt Mode retains USB support when the negotiated lane assignment allows it.

### Current limits

- Current matrix coverage does not include every dock, cable, orientation, drive filesystem or peripheral pairing behavior.

### Next action

- Measure mount latency and repeated dock reconnect with host and DP active.

### Evidence

- `host`: [Controller UCSI, board Alt Mode and HBR2 link-policy tests passed.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>clang++ -std=c++17 -I. tests/ucsi_host.cpp -o ucsi-host &amp;&amp; ./ucsi-host; run the Uke XR10 candidate host-test.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

## Image assembly {#packaging}

`host-verified`

Components: `DarwinBoot`, `XnuPrelink`, `VerifiedRoot`.

### Hardware and dependencies

- 24A446 IPSW, XNU 12377.121.6, the matched Apple RELEASE/LTO reference, generated 24A446 ADT, owner trust cache and OEM boot assets.

### Configuration

- 160 MiB raw FAT with UEFI compression and Android v4 vendor\_boot. Preserve the OEM DTB, vendor table and bootconfig. Keep boot arguments within the 1000-byte Android limit.

### Procedure

- Run ./unixnu build kernel and ./unixnu build payload from the core checkout. Package boot and vendor\_boot together and round-trip unpack the vendor payload.

### Development findings

- The latest image replaced only the add-on supplicant with the verified V4.9.7 file. Boot image, kernel, ADT, arguments, trust cache and GPU contents match the quiet DP base.
- The XR10 package used 984 bytes of boot arguments and added zero unresolved prelink bindings. The two-slot boot pair was written successfully.
- CI resolves the XNU revision and four-layer patch order through UniXNU. All 149 patches applied on a clean XNU 12377.121.6 checkout.

### Completion criteria

- Validated boot and vendor images fit the destination partitions and the boot chain hands off a matching payload.

### Current limits

- The owner confirmed Wi-Fi operation on the repack. Host artifact verification and the device observation cover different parts of the release.

### Next action

- Keep the signed Wi-Fi service paired with its launch cache in future addon builds.

### Evidence

- `host`: [Formal kernel and payload builds and the vendor\_boot payload round trip passed for c0a6f7ec9315.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.
- `host`: [All 149 resolved patches applied to clean XNU 12377.121.6 at ac9718fb1af618d5ce8678d0dc6e8a58f252216f.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>bash scripts/check-xnu-patch-set.sh</code>. Revision: `380cfbf686f41ae2a2ebf44835ce541a10241bcd`.

## Diagnostics {#diagnostics}

`host-verified`

Components: `AppleKeyStoreState`, `XnuPrelink`.

### Hardware and dependencies

- Persistent UKELLOG1 ring, panic screen, boot progress, and DXE previous-panic readout.

### Configuration

- Select sheng-log=1 for persistent logs. Correlate display HPD, EDID, fence, latch, IOSurface and display sink status within the same boot.

### Procedure

- Capture the persistent ring through read-only Recovery, select the fresh boot UUID, and symbolize against the exact linked kernel.

### Development findings

- Same-boot records from the split-panel image isolated GPU fence waits from link timing. Normal DP operation avoids periodic receiver and pixel-signature sampling.
- The ring includes older boots. Image-matched backtraces and CRC-valid sequence filtering are needed before associating a panic or performance sample with a trial.

### Completion criteria

- A single boot has a usable event sequence and exact kernel and boot-image identity.

### Current limits

- The split-panel image has a same-boot trace. The quiet image defaults to bounded operational logging and retains the opt-in capture mode.

### Next action

- Collect the next same-boot trace if XR10 cadence, levels or reconnect behavior fail.

### Evidence

- `host`: [XR10 image verification confirmed that DP sink status, CRC, display latch and frame counters are linked.](https://github.com/Allenwdk/UniXNU-uke/blob/358beac17b32e4efec06595c469a4212032af50e/docs/USB-DP-20261119.md)
  Command: <code>./unixnu build kernel &amp;&amp; ./unixnu build payload; release verify.py</code>. Revision: `d61336190c478c9884334f85433eea44e5fee6d0`.

</div>

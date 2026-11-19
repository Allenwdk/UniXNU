# USB adaptation

Complete [platform interrupts and DMA](/porting/platform) first. [QcomDwc3](https://github.com/UniXNU/QcomDwc3)
derives from Apple's `AppleUSBXDCI` and `AppleUSBXHCI`. The port supplies the register
window, interrupt, power and PHYs. Apple's USB stacks, `configd` and `lockdownd` run
unchanged.

Use [driver build integration](/porting/drivers#build-integration) to connect the
recipe, then run this page's checks.

## Sources and interfaces {#source-map}

| Implementation | Source | What to read and implement |
| --- | --- | --- |
| Controller | [QcomDwc3.cpp](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomDwc3.cpp) | `bringUp`, `qcom_dwc3_publish`, class overrides and role changes |
| PHYs | [QcomEusb2Phy.h](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomEusb2Phy.h), [QcomQmpUsb3.h](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomQmpUsb3.h) | eUSB2, repeater and QMP sequences |
| Cable role | [QcomUcsi.h](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomUcsi.h), [ShengBattery.cpp](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/package/ShengBattery.cpp) | UCSI messages over the charger's GLINK channel |
| Board entry | [UsbProbe.cpp](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/package/UsbProbe.cpp) | Kext loads and class registration |
| Build | [build-gop-legacy-display-27.py](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/scripts/build-gop-legacy-display-27.py), [board.toml](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/board.toml) | Generated class header and prelink roots |

The hardware sequences follow [mainline Linux](https://github.com/ianchb/sm8550-mainline).

## 1. Collect the hardware inputs

Read these from the target's DTS and clock definitions:

| Input | sheng value |
| --- | --- |
| DWC3 base and Apple register window | `0x0a600000`, window at base + `0xc000` |
| Interrupt | GIC INTID 165 |
| SMMU stream | `0x40` |
| eUSB2 reference clock | 38.4 MHz |
| PHYs and rails | eUSB2 PHY, PMIC repeater, QMP combo PHY, retimer, GDSCs, RPMh rails |

The SoC values are constants in `QcomDwc3.cpp`. Generate a QMP table for another SoC from
its Linux tree, in the device repository:

```sh
python3 scripts/gen-qmp-usb3-table.py LINUX_TREE drivers/QcomDwc3/QcomQmpUsb3.h
```

## 2. Bring up the controller

`bringUp` runs in this order and stores each step in `native_usb_stats[0]`. A negative
value is the step that failed.

| Stage | Step |
| --- | --- |
| 1 | Map the clock, TCSR, PHY and QSCRATCH windows |
| 2 | Vote the rails |
| 3 | Enable the GDSCs |
| 4 | Enable clocks and release resets |
| 5 | Create the stream's SMMU context |
| 6 | Start the repeater |
| 7 | Start the eUSB2 PHY, then the QMP PHY; fall back to the UTMI clock if QMP does not start |
| 8 | Read the core ID through the register window |
| 9 | Hardware ready |

`AppleUSBXDCI` does no cache maintenance. Give the controller's stream a stage 1 identity
context with write-back inner shareable blocks.

**Expected result:** stage 9 with a DWC3 core ID in `native_usb_stats[1]`.

## 3. Register the classes

The board starts one worker thread when `usb` is set. It runs:

1. `qcom_dwc3_bring_up`.
2. `OSKextLoadKextWithIdentifier` for `com.apple.driver.AppleUSBXDCI` and
   `com.apple.driver.usb.AppleUSBXHCI`. `AppleUSBXDCI` has no personality, so nothing else
   loads it.
3. `OSMetaClass::preModLoad`, the driver's static initializer and `postModLoad`.
4. `qcom_dwc3_publish`, which attaches the provider nub and starts the device stack.

Add the USB stacks to the prelink roots in `[kernel.prelink]` of `board.toml`.

The class layouts come from the selected kernelcache. `scripts/gen-usb27-abi.py` and
`scripts/gen-usb27-host-abi.py` write `scripts/usb-xdci-24A446.json` and
`scripts/usb-xhci-24A446.json`. Both scripts name the 24A446 kernelcache and class
addresses; change these for another OS build.

Keep two overrides when the layouts change:

- Slot 179 of `AppleUSBXDCI` returns false without an `IOPort` transport object.
- In host mode the xHCI subclass answers on for the family's desired power, and the device
  stack answers 0.

**Expected result:** stage 12, and `IOUSBDeviceFamily` starts on the nub.

## 4. Connect the cable role

Call these from the board's charger driver:

| Function | Use |
| --- | --- |
| `qcom_dwc3_vbus(int)` | The charger's USB online value |
| `qcom_ucsi_start`, `qcom_ucsi_receive`, `qcom_ucsi_tick` | Send each returned message on the GLINK channel |
| `qcom_ucsi_polling` | True while the driver needs the 20 ms timer |

A host on the cable selects the device role and a peripheral selects the host role. With
no answer from either source, the device role runs. Check the UCSI client from
`drivers/QcomDwc3/tests`:

```sh
clang++ -std=c++17 -I.. ucsi_host.cpp && ./a.out
```

## 5. Answer the Mac's pairing checks

| Answer | Where |
| --- | --- |
| `chip-id` | `[payload.adt]` in `board.toml` |
| `board-id`, `security-domain` | `adt.chosen.u32` in the OS profile |
| One file system number for `/System` and system daemons | [`native-union-statfs-fsid`](/xnu/patch-reference) |
| Lock state 3 | [`aks-sls=3`](/xnu/boot-arguments) |

Use the model's row in the device map inside `MobileDevice.framework` for the three IDs.

## 6. Build and verify

From the UniXNU checkout, with `usb=1` and `log-sys=1` in the board's boot arguments:

```sh
./unixnu build kernel payload -D ../UniXNU-<device> --os <profile>
./unixnu bootimg -D ../UniXNU-<device> --os <profile> --dtb <device>.dtb -o boot.img
fastboot boot boot.img
```

Connect the device to a Mac:

```sh
ioreg -p IOUSB -l -w0 | grep -E 'idVendor|idProduct|Device Speed'
```

**Expected result:** the Mac lists the device, with `Device Speed` 4 on a USB 3 cable.
Unlock it and tap Trust; the Mac then reports it as paired and starts a lockdown session.
[Capture the log](/porting/log-capture) to read the `[usb]` rows.

| Symptom | Check |
| --- | --- |
| Chirp passes, high-speed data fails | eUSB2 reference clock table |
| `ep0OutEventOccurred: event 0` | Stage 1 SMMU context |
| PAC panic while creating the TRB pool | `AppleUSBXDCI` kext load before class registration |
| `bNumConfigurations` is 0 and the host resets | Slot 179 |
| The Mac asks for a software update | `chip-id`, `board-id`, `security-domain` |
| `UserDeniedPairing` with no dialog on the panel | File system number of `/System` |
| A passcode prompt after Trust | Lock state |

To test host mode, set `usb-host=<s>` to force it after a delay and
`usb-back=<s>` to return to the cable's role. Record device results as described in
[Porting record](/porting/records).

## Xiaomi Pad 7 (uke)

The SM7675 port uses the stock applied device tree for the PM7550BA repeater, the WCD939x USB path and Cliffs power and clock resources. Its fixed USB 2 candidate uses a checked GCC block reset at the AppleUSBXDCI reset slot. See the [QcomDwc3 Uke source](https://github.com/Allenwdk/QcomDwc3/tree/feat/uke-usb2).

On 2026-11-15 the Uke USB2 shared-bus candidate passed WCD939x revision/routing and AppleUSBDeviceMux configuration in the same boot. Enumeration still fails: the event buffer and endpoints remain unconfigured after `startUSBStack`. The next local candidate records power requests and callbacks without replacing Apple's power state machine. These observations do not establish USB2 acceptance.

The Uke power diagnostic boot returned `kIOPMNotYetInitialized` (8) for its initial power request. Later desired power reached 4 while current power remained 0. A local candidate retains that rejected request and retries only after PM initialization and power-tree attachment, with at most five retries; PM readiness and parent attachment are logged. USB enumeration remains unverified.

The Uke deferred request was accepted after PM initialization and power-plane attachment at 52.35 seconds, but current power remained 0 and hardware callbacks did not execute through 116.32 seconds. Early rejection is not the complete cause. The next diagnostic candidate keeps the component unchanged and records native PM registration, parent capability, request consumption and callback progress, with a limit of 96 trace points for this controller.

For Uke, the comprehensive diagnostic candidate correlates synchronous registration returns and the runtime power table, both request queues, parent capability/ACKs, independent PM/USB worker stacks, CPU state and DWC3/SMMU snapshots in one boot. Per-category call/omission counters distinguish missing coverage from absent execution. USB remains unverified.

Uke comprehensive readback found 40 native PM requests enqueued with none dequeued. The linked arm64e classification compares identical virtual-call thunks, so the repair uses explicit active contracts for native PM queues, root power, interrupt, DMA, command and notification sources. The final binary verifies seven linked flag writes; the legacy command queue is source-only. The candidate is built and paired but unflashed; USB enumeration and shared PM consumers still require device validation.

Uke candidate609e restores native PM processing (58 queued/58 dequeued, power4); the controller starts and configures event DMA/EP0, but IRQ/event counts remain zero. The next local candidate restores and verifies session-valid after external block reset, keeps SS power-present clear for USB2, and records QSCRATCH/PHY/IRQ plus a 300-second window. Raw SMMU FSR0x400 is the AArch64 format, not a fault. This candidate is built but unflashed; the earlier capture did not directly record lost post-reset session, and USB enumeration is still unverified.

On 2026-11-16 the ac456259 image enumerated USB2 and completed the Mux version exchange, but the host's TCP SYN to lockdown port 62078 received no device TCP reply. An official/sheng/Uke source comparison found no evidence yet of a custom Uke Mux parser defect. A new unflashed candidate enables bounded `AppleUSBDeviceMux` `DebugLevel=7` logging for the TCP/session/socket/write path. It also adds Uke's missing `sheng-aks-sls=3`; the owned KeyStore otherwise defaults to lock state 0, while the official pairing gate requires no-passcode state 3. Formal build and paired-image verification passed; lockdown and hardware acceptance remain pending. [Audit and candidate](../../../../docs/status/uke-usb2-mux-debug-2026-11-16.md).

The 2026-11-17 Recovery readback matched the exported Mux diagnostic boot. It reached high-speed configuration 1 and logged 24 reads, 24 short-packet classifications and zero writes by deactivation. DWC3 reported `DCFG=0x00600808`, with bit 22 set despite the OEM `snps,usb2-gadget-lpm-disable` property. The next Uke candidate keeps that bit clear across controller reset and AppleUSBXDCI register updates. The effect on Mux traffic awaits a hardware comparison.

The gadget LPM comparison confirmed bit 22 was clear during enumeration and after reconnect. Mux v2 replied, while the lockdown port still timed out. After reconnect the controller stayed in Suspended even though the host selected configuration 1 again. The next Uke candidate requests On through the existing power queue when connection-done reports a USB2 link and both power states are still Suspended. Hardware validation is pending.

## Next step

Continue with [baseband and cellular](/porting/baseband) on devices with a modem, or
[DSP, audio and power](/porting/power).

On 2026-11-18, the Uke USB3 peripheral candidate used Cliffs QMP power, clocks and reset wiring with the 167 entries from the effective OEM device tree. GPIO122 selects orientation in hardware. `uke-usb3=1` enables the SuperSpeed experiment, with UTMI as the fallback if QMP bring-up fails. The kernel and paired images passed host verification. SuperSpeed enumeration, data transfer, both orientations and host mode remain device tests.

The 2026-11-18 Uke candidate enables automatic DRD with `uke-usb-otg=1`. It uses the PMIC GLINK UCSI client to choose the data role and Cliffs block reset to hand the controller between XDCI and xHCI. The Type-C firmware controls the power role. GPIO122, QMP port selection and LTSSM diagnostics cover the reverse-plug investigation. Host build and prelink checks passed. Hardware role transitions and reverse SuperSpeed remain to be tested.

The next Uke candidate uses the OEM charger CC orientation report to select the QMP lane before bringing up the selected role. Cliffs uses low-word then high-word xHCI register writes. Host diagnostics sample the event ring configuration and IRQ count. This candidate awaits hardware verification.

The latest Uke OTG candidate reapplies the OEM eUSB2 PHY initialization on role changes and uses the Cliffs host-specific timing bits. It records root port objects and PORTSC transitions to diagnose USB 2 keyboard enumeration. The original recovery kernel enumerated the same adapter and keyboard. Candidate hardware verification is pending.

Uke's next OTG candidate explicitly subscribes `QcomDwc3Xhci` to its own power-state notifications. In the previous hardware test the host reached power state 3 with no published root ports. The original IOUSBHostFamily creates them in the gated post-change path. Build and image checks passed. Port creation and enumeration await hardware verification.

Uke's DP Alt Mode readback confirms Pin D with two DP lanes and USB3 in both orientations. HDMI hotplug reaches the board through PMIC GLINK HPD notifications. The board's `uke-dp-aux=1` candidate applies the combined QMP route within the existing USB role handoff, selects WCD939x AUX polarity, then reads DPCD on HPD. AUX and link training still require hardware verification.

Uke has since verified AUX, EDID and two-lane HBR training in both orientations. The next board candidate keeps a DPTX0 test stream active while HPD and the USB role generation remain valid. HPD IRQ checks the active link status.

# USB 适配

先完成[平台中断和 DMA](/zh/porting/platform)。[QcomDwc3](https://github.com/UniXNU/QcomDwc3)
派生自苹果的 `AppleUSBXDCI` 和 `AppleUSBXHCI`。移植时提供寄存器窗口、中断、电源和 PHY。
苹果的 USB 栈、`configd` 和 `lockdownd` 不做修改。

按[驱动接入步骤](/zh/porting/drivers#build-integration)连接构建配方，再执行本页的检查。

## 源码与接口 {#source-map}

| 实现部分 | 源码 | 阅读与实现内容 |
| --- | --- | --- |
| 控制器 | [QcomDwc3.cpp](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomDwc3.cpp) | `bringUp`、`qcom_dwc3_publish`、类覆盖和角色切换 |
| PHY | [QcomEusb2Phy.h](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomEusb2Phy.h)、[QcomQmpUsb3.h](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomQmpUsb3.h) | eUSB2、中继器和 QMP 时序 |
| 线缆角色 | [QcomUcsi.h](https://github.com/UniXNU/QcomDwc3/blob/e4efe95c903a737e0f5955e5b50a8fb4d2a7d718/QcomUcsi.h)、[ShengBattery.cpp](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/package/ShengBattery.cpp) | 通过充电器 GLINK 通道收发 UCSI 消息 |
| 板级入口 | [UsbProbe.cpp](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/package/UsbProbe.cpp) | 加载 kext 和注册类 |
| 构建 | [build-gop-legacy-display-27.py](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/scripts/build-gop-legacy-display-27.py)、[board.toml](https://github.com/UniXNU/UniXNU-sheng/blob/ce0c600fa015964d4ecb6af864fa2ab66efa915f/board.toml) | 生成的类头文件和 prelink 根 |

硬件时序遵循[主线 Linux](https://github.com/ianchb/sm8550-mainline)。

## 1. 收集硬件输入

从目标设备的 DTS 和时钟定义读取：

| 输入 | sheng 的值 |
| --- | --- |
| DWC3 基址和苹果寄存器窗口 | `0x0a600000`，窗口在基址 + `0xc000` |
| 中断 | GIC INTID 165 |
| SMMU 流 | `0x40` |
| eUSB2 参考时钟 | 38.4 MHz |
| PHY 和电源轨 | eUSB2 PHY、PMIC 中继器、QMP combo PHY、retimer、GDSC、RPMh 电源轨 |

SoC 相关的值是 `QcomDwc3.cpp` 里的常量。其他 SoC 的 QMP 表在设备仓库中从其 Linux 源码生成：

```sh
python3 scripts/gen-qmp-usb3-table.py LINUX_TREE drivers/QcomDwc3/QcomQmpUsb3.h
```

## 2. 启动控制器

`bringUp` 按以下顺序执行，并把每一步写入 `native_usb_stats[0]`。负值表示失败的步骤。

| 阶段 | 步骤 |
| --- | --- |
| 1 | 映射时钟、TCSR、PHY 和 QSCRATCH 窗口 |
| 2 | 投票电源轨 |
| 3 | 打开 GDSC |
| 4 | 打开时钟并释放复位 |
| 5 | 创建该流的 SMMU 上下文 |
| 6 | 启动中继器 |
| 7 | 启动 eUSB2 PHY，再启动 QMP PHY；QMP 未启动时改用 UTMI 时钟 |
| 8 | 通过寄存器窗口读取核心 ID |
| 9 | 硬件就绪 |

`AppleUSBXDCI` 不做缓存维护。为控制器的流配置 stage 1 恒等映射上下文，使用 write-back、
inner shareable 块。

**预期结果：** 到达阶段 9，`native_usb_stats[1]` 为 DWC3 核心 ID。

## 3. 注册类

设置 `usb` 后，板级代码启动一个工作线程，依次执行：

1. `qcom_dwc3_bring_up`。
2. 用 `OSKextLoadKextWithIdentifier` 加载 `com.apple.driver.AppleUSBXDCI` 和
   `com.apple.driver.usb.AppleUSBXHCI`。`AppleUSBXDCI` 没有 personality，其他路径不会加载它。
3. `OSMetaClass::preModLoad`、驱动的静态初始化和 `postModLoad`。
4. `qcom_dwc3_publish`，挂接 provider nub 并启动设备栈。

把 USB 栈加入 `board.toml` 中 `[kernel.prelink]` 的 prelink 根。

类布局来自所选的 kernelcache。`scripts/gen-usb27-abi.py` 和 `scripts/gen-usb27-host-abi.py`
生成 `scripts/usb-xdci-24A446.json` 和 `scripts/usb-xhci-24A446.json`。这两个脚本写明了
24A446 的 kernelcache 和类地址，其他 OS 版本需要修改。

布局变化时保留两处覆盖：

- 没有 `IOPort` 传输对象时，`AppleUSBXDCI` 的 179 号槽返回 false。
- 主机模式下，xHCI 子类对 family 的期望电源回答开启，设备栈回答 0。

**预期结果：** 到达阶段 12，`IOUSBDeviceFamily` 在 nub 上启动。

## 4. 连接线缆角色

在板级充电器驱动中调用：

| 函数 | 用途 |
| --- | --- |
| `qcom_dwc3_vbus(int)` | 充电器的 USB 在线值 |
| `qcom_ucsi_start`、`qcom_ucsi_receive`、`qcom_ucsi_tick` | 把每条返回的消息发到 GLINK 通道 |
| `qcom_ucsi_polling` | 驱动需要 20 ms 定时器时为 true |

线缆对端是主机时选择设备角色，是外设时选择主机角色。两个来源都没有回答时运行设备角色。
在 `drivers/QcomDwc3/tests` 中检查 UCSI 客户端：

```sh
clang++ -std=c++17 -I.. ucsi_host.cpp && ./a.out
```

## 5. 回答 Mac 的配对检查

| 回答 | 位置 |
| --- | --- |
| `chip-id` | `board.toml` 的 `[payload.adt]` |
| `board-id`、`security-domain` | OS 配置的 `adt.chosen.u32` |
| `/System` 和系统守护进程使用同一个文件系统编号 | [`native-union-statfs-fsid`](/zh/xnu/patch-reference) |
| 锁状态 3 | [`aks-sls=3`](/zh/xnu/boot-arguments) |

三个 ID 使用 `MobileDevice.framework` 内设备映射表中该机型的行。

## 6. 构建和验证

在 UniXNU 仓库中，确认板级启动参数含 `usb=1` 和 `log-sys=1`：

```sh
./unixnu build kernel payload -D ../UniXNU-<device> --os <profile>
./unixnu bootimg -D ../UniXNU-<device> --os <profile> --dtb <device>.dtb -o boot.img
fastboot boot boot.img
```

把设备连接到 Mac：

```sh
ioreg -p IOUSB -l -w0 | grep -E 'idVendor|idProduct|Device Speed'
```

**预期结果：** Mac 列出设备，USB 3 线缆下 `Device Speed` 为 4。解锁并点“信任”后，Mac 报告已配对并开始
lockdown 会话。[抓取日志](/zh/porting/log-capture)后可查看 `[usb]` 行。

| 现象 | 检查 |
| --- | --- |
| chirp 通过，高速数据失败 | eUSB2 参考时钟表 |
| `ep0OutEventOccurred: event 0` | stage 1 SMMU 上下文 |
| 创建 TRB 池时 PAC panic | 注册类之前是否加载了 `AppleUSBXDCI` |
| `bNumConfigurations` 为 0，主机复位 | 179 号槽 |
| Mac 要求更新软件 | `chip-id`、`board-id`、`security-domain` |
| `UserDeniedPairing`，屏幕上没有弹窗 | `/System` 的文件系统编号 |
| 点“信任”后要求输入密码 | 锁状态 |

测试主机模式时，`usb-host=<s>` 在延时后强制进入主机模式，`usb-back=<s>` 再回到线缆决定的角色。
设备结果按[适配记录](/zh/porting/records)记录。

## 小米平板 7（uke）

SM7675 移植以原厂生效设备树确定 PM7550BA 中继器、WCD939x USB 路径及 Cliffs 电源和时钟资源。固定 USB2 候选在 AppleUSBXDCI 复位槽执行有读回检查的 GCC 块复位。见 [QcomDwc3 的 uke 源码](https://github.com/Allenwdk/QcomDwc3/tree/feat/uke-usb2)。

2026-11-15 的 Uke USB2 共享总线候选在同次启动中通过 WCD939x 识别/路由和 AppleUSBDeviceMux 配置。USB 仍未枚举：`startUSBStack` 后事件缓冲区和端点仍未配置。下一本地候选记录电源请求与回调，保持 Apple 原有电源状态机；上述结果尚不构成 USB2 验收。

Uke 电源诊断启动确认首次电源请求返回 `kIOPMNotYetInitialized`（8），之后期望电源升到 4、实际仍为 0。本地候选保留被拒绝的请求，等待 PM 初始化和电源树挂接后最多重试五次，并直接记录就绪与父节点状态。USB 枚举仍待实机验证。

Uke 延迟请求版在 52.35 秒确认 PM 初始化、power-plane parent 存在且重提请求返回成功，但到 116.32 秒实际电源仍为 0，硬件回调未执行；首次请求过早不是完整根因。下一取证候选保持组件源码不变，在原生 PM 注册、父域能力、请求消费及回调边界记录最多 96 个点。

Uke 全面取证候选在同次启动关联同步注册返回/实际电源表、两级请求队列、父域能力/ACK、独立PM和USB工作线程栈、CPU及DWC3/SMMU快照。分类calls/omitted用于区分缺覆盖和未执行，USB仍未验证通过。

Uke全面回读确认原生PM入队40/出队0。实包arm64e自动分类比较相同虚调用thunk，修正版对原生PM队列、根电源、IRQ、DMA、命令及通知使用显式active契约。七个已链接类已核验机器码，旧命令队列仅源码覆盖。候选已构建配对但未刷，USB枚举及共用PM消费者仍待实机验证。

Uke609e已实证恢复原生PM处理（58入/58出、电源4），控制器启动并配置事件DMA/EP0，但IRQ/事件计数仍0。下一本地候选在外部块复位后恢复并验证session-valid，USB2清SS就绪位，并记录QSCRATCH/PHY/IRQ及300秒窗口。raw SMMU FSR0x400为AArch64格式，不是故障。候选已构建未刷；前版未直接记录post-reset session丢失，USB枚举仍未通过。

2026-11-16：ac456259 USB2枚举和Mux版本握手通过，但主机对62078发送的SYN后无设备TCP回复。官方/sheng/Uke实现对照没有找到可证实的自定义Mux解析错误；诊断候选为AppleUSBDeviceMux设置DebugLevel=7以记录TCP/session/socket/write路径。另确认Uke `sheng-aks=1` 时原先缺少锁状态参数；候选加入`sheng-aks-sls=3`，对应官方配对检查的无密码状态3。正式构建和配对镜像验证通过，未刷，USB lockdown仍未验收。[证据与候选](https://github.com/Allenwdk/UniXNU-uke/blob/main/docs/USB2-20261115.md)。

2026-11-17 Recovery 回读与已导出的 Mux 诊断启动一致。同次启动达到 USB2 高速、配置 1，Mux 在停用前累计 24 次读取、24 次过短包判定、0 次写入。DWC3 的 `DCFG=0x00600808` 显示 bit 22 已置位，原厂生效设备树声明了 `snps,usb2-gadget-lpm-disable`。新 Uke 候选在控制器复位和 AppleUSBXDCI 更新寄存器时均保持该位清零。Mux 流量是否恢复待实机对照。

实机回读确认首次枚举和重插后 bit 22 均清零，Mux v2 有回包，lockdown 仍超时。重插后主机重新选择配置 1，控制器电源状态却停在 Suspended。新候选在 connection-done 确认 USB2 链路且当前与期望状态仍为 Suspended 时，经原有电源队列请求 On。待实机验证。

## 下一步

有基带的设备继续[基带与移动网络](/zh/porting/baseband)，其余设备继续 [DSP、音频和电源](/zh/porting/power)。

2026-11-18，Uke USB3 外设候选接入 Cliffs QMP 供电、时钟和复位，使用原厂生效设备树中的 167 项参数，GPIO122 交由硬件选择方向。`uke-usb3=1` 启用 SuperSpeed 实验，QMP 启动失败时回落到 UTMI。内核与配对镜像已通过主机核验，SuperSpeed 枚举、传输、两种插头方向和 host 仍待实机验证。

2026-11-18，Uke 候选用 `uke-usb-otg=1` 启用自动双角色。PMIC GLINK 上的 UCSI 决定数据角色，Type-C 固件负责供电角色。Cliffs 外部块复位用于 XDCI 和 xHCI 交接。USB3 反插排查增加 GPIO122、QMP 方向输入和 LTSSM 日志。正式构建和预链接核验已通过，实机角色切换及反插 SuperSpeed 待验。

Uke 后续候选在切换角色前从原厂充电服务读取 CC 方向并选择 QMP lane。Cliffs 的 xHCI 寄存器按低位、高位写入。Host 诊断补采事件环配置和中断计数。该候选仍待实机验证。

最新 Uke OTG 候选在角色改变时重新初始化 eUSB2 PHY，并设置 Cliffs 的 host 时序位。新增根端口对象和 PORTSC 状态日志，用于定位 USB2 键盘枚举。原厂 recovery 已实测同一转接头和键盘可以枚举，候选待实机验证。

Uke 后续 OTG 候选显式订阅 `QcomDwc3Xhci` 自身的电源状态通知。上版实机达到电源状态 3 时根端口对象数为 0；原版 IOUSBHostFamily 在电源状态通知的 gated 路径创建根端口。构建和镜像核验通过，根端口创建与枚举待实测。

Uke 的 DP Alt Mode 回读确认正反插均协商 Pin D、DP 两 lane 加 USB3，HDMI 热插拔通过 PMIC GLINK 上报 HPD。板级 `uke-dp-aux=1` 候选在现有 USB 角色交接中应用 QMP 组合路由，并切换 WCD939x 的 AUX 极性，在 HPD 拉高时读取 DPCD。AUX 和链路训练待实机验证。

Uke 后续实测确认正反插均通过 AUX、EDID 和两 lane HBR 训练。新板级候选在 USB 角色代次与 HPD 有效期间保持 DPTX0 测试视频流，HPD IRQ 用于检查在用链路状态。

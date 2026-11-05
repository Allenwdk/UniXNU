# GopFramebuffer

先按[适配流程](/zh/porting/display)准备板级输入、修改源码、接入构建并逐步验证。

使用固件 GOP 交接的 framebuffer 呈现。

[源码仓库](https://github.com/UniXNU/GopFramebuffer).

实现通过 PE_current_console 读取固件 framebuffer，并集成所选 MobileFramebuffer ABI。板级接口提供显示策略和 GPU scanout 集成。

已核对的 24A446 ABI 通过生成头启用 `NATIVE_LEGACY_BOOT_SCANOUT_REQUESTED`：验证主 GOP 映射可用后，使用原族的状态设置函数同时发布初始 requested 和固件已供电状态。原提交路径在 requested 为零时会丢弃 swap。这是逻辑 scanout 初始化，不实现面板电源切换；原客户端错误与校验保持。主机构建通过不能证明画面已到面板。

## 集成

组件目录记录实现范围、硬件与 OS 要求、板级依赖、源码版本、构建阶段、输出和运行时标识符。所选配置按依赖顺序运行构建命令。

```sh
./unixnu build kernel -D /path/to/device
```

[组件目录](/zh/reference/components)
已核对的 24A446 ABI 通过生成头启用 `NATIVE_LEGACY_BOOT_SCANOUT_REQUESTED`：验证主 GOP 映射可用后，使用原族的状态设置函数同时发布初始 requested 和固件已供电状态。原提交路径在 requested 为零时会丢弃 swap。这是逻辑 scanout 初始化，不实现面板电源切换；原客户端错误与校验保持。主机构建通过不能证明画面已到面板。


同一已验证的队头直扫请求在重试时先查 GPU fence。确认完成后，驱动重新校验表面和扫描输出，再提交 flip。轻量诊断模式 2 记录最终 latch 状态，包括超时。

CP fence 中断可唤醒显示工作循环重查 GPU fence。保留定时器兜底、表面复核和 latch 后退休。

fence 中断提交合并的内核回调，由显示工作循环的 gate 串行处理回调、定时器与停用。实际执行过 IRQ 重查后，兜底定时器才从 200 µs 调整为 500 µs。



帧诊断保留分配、命令、完成处理及 GPU、显示时间线，像素抓取关闭。使用方法见 [GPU 帧诊断](/zh/porting/gpu-diagnostics)。

帧诊断从已准备好的直接显示槽位读取物理地址。验证阶段尚未映射时记录零地址，提交切换时补充映射地址。诊断观察代码不准备描述符，也不查询其物理段。

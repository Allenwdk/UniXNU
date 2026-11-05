# AdrenoMetal

AdrenoMetal 通过 `MTLAddDevice` 发布 Metal 设备。metal2vulkan 将 AIR 翻译为 SPIR-V，Turnip 完成编译，并向 [Adreno740](/zh/drivers/adreno740) 提交任务。固件、电源投票和显示集成由设备仓库提供。

## 渲染和接口

| 项目 | 当前行为 |
| --- | --- |
| MSAA 策略 | 所有客户端的纹理、管线和渲染通道默认使用单采样。resolve 目标接收渲染结果，load 和 store-and-resolve 保留源内容。`NATIVE_METAL_SINGLE_SAMPLE=0` 让进程保留请求的采样数，`1` 强制单采样。 |
| Heap 资源 | buffer 和 texture 的 `makeAliasable` 归还 heap 区间。 |
| 纹理通道 | 纹理描述符和 view 保留全部四个 swizzle，包括显式零和一。 |
| 复制和光栅状态 | blit 覆盖指定 mip 和 slice 范围。viewport、scissor 传递完整数组，最多 16 项。 |
| 压缩纹理输入 | 长度为零的 no-copy 压缩纹理按 DroidVM 布局推导大小，使用结束后调用所有者的 deallocator。 |
| 函数 | 函数常量字典提供名称、索引和类型。函数及计算管线的完成回调返回结果。`specializedName` 用作导出名称，源码查找保留原函数名。 |
| 常量表 | 超过 4 KiB 的动态索引常量表使用共享常量存储。常量指针转换和 GEP 表达式保留偏移。 |
| 内存统计 | 设备用量统计池、独立和导入分配。纹理大小来自实际 backing allocation。建议工作集为 RAM / 4，上限 2 GiB。 |
| 队列容量 | `newCommandQueueWithMaxCommandBufferCount:` 使用 runtime 的未完成缓冲数量限制。未提交缓冲销毁时释放名额，已提交缓冲在完成回调返回后释放名额。 |

渲染通道编码失败时仍返回 encoder，通过 command buffer 报错，支持缓存 encoder 方法的调用方。

## 缓存和优先级

相同 UID 的客户端在可写时共用账户 home 下的 `Library/Caches/org.unixnu.metal`。沙箱限制写入时使用私有缓存。`NATIVE_METAL_SHARED_CACHE_DIR` 可指定共享目录，空值关闭共享。缓存覆盖 Apple 前端结果、runtime 产物和 Turnip IR3。并发导入使用独立临时文件，管线日志按进程分开。

同一进程的 Metal 逻辑队列共用一个 Vulkan 队列和内核队列。前端汇总存活队列的当前请求，采用其中最高的优先级；队列降级或销毁后撤回提升。getter 返回各队列自身的请求，setter 返回后端是否接受。内核根据任务的 GPU role 选择前台或后台优先级，策略不使用进程名。


已空闲的自有图像内存可供池化和独立图像复用。额外缓存按设备合计上限为 256 MiB，十秒后过期。至少 256 KiB 的普通自有内存可交给现有后台线程释放，待回收队列上限为 128 MiB；分配失败时先释放排队内存，再重试。导入内存和外部所有者回调保留原有释放顺序。首次使用仍可能需要准备新内存页。

## 构建和检查

在解析后的 iOS 27 目标构建树中执行：

```sh
python3 scripts/build-turnip-darwin.py --target ios27
python3 scripts/build-adreno-metal-plugin.py --target ios27
python3 scripts/check-native-metal-frontend-host.py
```

正常构建应用记录在仓库中的翻译器、Turnip 补丁，并开启 Mesa 磁盘 shader cache。主机检查覆盖渲染像素、resolve、资源回收、swizzle、复制、回调、队列容量及优先级汇总。上机验证项目是并发客户端下的帧间隔和抢占行为。

设备输入和打包方式见 [GPU 适配流程](/zh/porting/gpu)。

帧诊断保留分配、命令、完成处理及 GPU、显示时间线，像素抓取关闭。使用方法见 [GPU 帧诊断](/zh/porting/gpu-diagnostics)。

启用 `sheng-gpu-trace=1` 后，内核事件 65 记录 `iconservicesagent` 获取的 Metal 设备和创建的命令队列。对于含绘制或计算任务的命令缓冲区，最多记录八条 `metal-work`，包含完成状态、绘制次数和计算派发次数。

`sheng-wallpaper-freeze=1` 用于隔离壁纸渲染。名字包含 Poster 的渲染进程首次成功绘制并保存至少 200 万像素的 IOSurface 后，保留该输出，拦下后续 command buffer 的 runtime 提交。被拦下的缓冲保持已 commit、未调度状态，继续持有资源和队列名额；此前已提交的工作正常完成。PosterBoard、backboardd 和其他客户端继续提交。此模式默认关闭。

细分延迟记录标出慢编码调用、回调入口地址和资源析构耗时。内核对渲染、编码和完成线程的采样关联上游等待。


运行时流程、发布命令和检查见 [Adreno740](/zh/drivers/adreno740)。


## iOS 27 Turnip 装载格式

Turnip 与插件均用 `--target ios27` 构建。Turnip 链接显式启用 `-Wl,-fixup_chains`，并向 Meson 已有构建目录重新传递链接参数；最终签名 dylib 应包含 `LC_DYLD_CHAINED_FIXUPS`，owner trust 需使用新 CDHash。

uke 24A446 的同 boot iconservicesagent 报告显示，Metal 打开 Turnip 时在 dyld `MachOAnalyzer::withChainStarts` 中触发线程栈 guard fault。旧 arm64e `LC_DYLD_INFO_ONLY` 导致 dyld 在工作队列栈上临时合成链元数据；旧库需要 439,304 字节，与崩溃 x8 精确相符。显式链元数据避开该兼容分支。修正保留渲染逻辑与编译器 pin；图标/小组件恢复及卡死验收仍需真机。见 [Apple 实现](https://github.com/apple-oss-distributions/dyld/blob/main/common/MachOAnalyzer.cpp)。


## iOS 27 Core Image 原库查找

uke iOS27 前端先保留 `CIKernelLibrary internalLibraryWithName:device:` 的原结果；仅当结果为nil且设备为本前端时，对已知Core Image标准库、stitchable库名从标准 `/System/Library/Frameworks/CoreImage.framework` 路径重试，继续使用原 `newLibraryWithURL:error:` 和运行时解析器。保持原helper的retained返回约定；其他设备/成功结果保持，重试失败仍返回nil并记录真实原因。不复制原资源、不改全局VFS视图。

该修正针对uke24A446图标服务库加载失败，实际效果待真机。上一版source-union VFS实验引入卡Apple标志回归，已撤回。内核仅在恢复时记录已有fence/restart/fault结果，插件原marker文本以NUL结尾时持久保留有界拒绝摘要；不改变调度、抢占、错误传递或恢复策略。


## Uke实机确认

2026-11-03用户确认定向CoreImage原库加载修复版（CRC `90B6BC701210D9DB`）已解决此前启动、桌面/设置图标与小组件加载、设置中上划Dock导致界面重启的问题，设为当前uke27线GPU可交互基线。镜像身份和用户证据见设备仓 `docs/GPU-IOS27.md`；精确延迟、长时间并发、冷启动缓存测试另行量测。

编码drain记录所需排队前缀，batch仅在目标满足时广播，工作队列仅空→非空通知。保留FIFO、scheduled/completed和所有权条件。uke同时在DT验证的CPU域接入sheng原动态频控并启用既有固定120Hz刷新范围，实机收益待验。


`sheng-diag=2` 保留 backboardd 命令摘要、提交至编码阶段和扫描输出客户端事件。Turnip 逐 pass 打点和运行时诊断关闭，内核跟踪独立配置。

本轮 Uke 诊断候选对限定的大尺寸 IOSurface/memoryless pass 请求 GMEM 或 SYSMEM，并记录 command 策略。SYSMEM backing 会改变内存占用，需同时验证画面和整作业耗时。

C352非fetch ROAA实验因图标/渲染回归撤回，修正版使用原Turnip顺序代码。`sheng-diag=4`在轻量前端计时中启用逐pass时间戳和附件事件，前端reader同步接通。板级在worker启动180秒后导出，安装完成记录addon计数。addon写入后显式设置精确文件长度并sync。像素恢复与pass交付仍待真机。

Uke集成在模式4接入上游iconservicesagent设备、队列和完成记录。CP抢占完成移到板级thread call，等待线程栈读取先核线程状态和栈边界。实际稳定性及性能待真机。

Uke已将上游sheng图标服务环境（FORCE_SOFTWARE_RENDERER=0、CI_ENABLE_METAL_GPU=0）通过owner签名launchd缓存和既有只读union挂载接入。原服务字段与装载/签名校验保留。主机缓存语义及页面哈希检查通过；候选209862415C7884EC的私有libxpc消费、启动和图标像素仍待真机。

Uke模式2/4的逐pass GPU时间戳现仅在真正导出pass ring的backboardd启用；图标设备/队列/首八次工作记录及模式1全量诊断保留。仅移除未消费的诊断GPU写入，实际收益待真机。

逐pass reader按19.2MHz商/余数精确换算；旧整数52ns的pass时间需625/624校正后才能与内核整job对齐。前端24/25由writer读取既有拆分/纹理复制累计计数，26标记精确时钟。未改变渲染，不据此宣称提速；26 exact记录不重复校正。

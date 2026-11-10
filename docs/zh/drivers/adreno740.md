# Adreno740

Adreno740 实现 SM8550 上的 A740 内核 GPU 接口，负责内存映射、命令提交、fence 和 CP/GMU 初始化。设备仓库提供固件、电源投票和显示集成。适配入口见 [GPU 适配流程](/zh/porting/gpu)。

## 运行路径

Metal → AdrenoMetal → metal2vulkan → Turnip → Darwin KMD → Adreno740 → A740。

每个客户端拥有独立地址空间和队列编号范围。GPU 使用 4 KiB SMMU 页。自有 buffer 使用系统内存，导入页保留所有者。分配容量随可用内存变化。映射句柄通过索引查找，解除映射时失效对应转换。

## 调度

| 请求优先级 | 模式 2 使用的环 |
| --- | --- |
| High（0）、normal-high（4）、real-time（5） | ring 0 |
| Normal（1）、low（2）、background（3）、未指定 | ring 1 |

任务的 GPU role 决定采用前台还是后台请求。ring 0 优先；ring 0 空闲，或 ring 1 最早的任务等待超过 250 ms 时，调度 ring 1。超时等待获得的执行时间片为 2 ms，避免立即来回切环。切换完成后重新检查排队中的高优先级任务。显示端使用两个环共同完成的连续 fence 范围。队列在已有任务完成前保持原来的环，改优先级时仍按提交顺序执行。IB 句柄只标识命令存储，不用于推断资源依赖。Turnip 客户端的队列共用一个内核 FIFO，未解析的同步等待生产者提交。

每个环独立记录已排队的上下文和页表。CP 在 `CP_SMMU_TABLE_UPDATE` 后记录实际执行的页表，抢占恢复该快照。切环保存 GMEM，执行性能计数器 SRAM postamble，并保持 GMU keepalive，直到目标环 WPTR 恢复。读指针使用各环自己的 shadow。fence 历史表绕回后，未完成任务仍保留正确的环归属。

参考实现用 `gpu-preempt=2` 启用模式 2。模式 1 仅将 low/background 请求送往 ring 1，模式 0 使用单环。由 CPU 切换页表时也仅使用 ring 0。切环超时为 1 秒。切换失败后停止抢占，恢复流程在 ring 0 重放待执行任务，诊断记录保留失败信息。

## 构建和验证

在解析后的 iOS 27 目标构建树中设置 `UNIXNU_XNU_ARCH=arm64e`、`UNIXNU_IOS_VERSION=27.0` 后执行：

```sh
python3 scripts/build-arm-driver.py Adreno740
python3 scripts/build-adreno740-kits.py
python3 scripts/check-native-adreno-scheduling.py
```

主机调度检查使用软件寄存器模型运行实际 ring、preemption 和 submit 代码，并开启地址及未定义行为检查。覆盖命令包、GMEM、keepalive 顺序、超时、页表快照、优先级分环、FIFO 和 fence 历史表绕回。上机验证项目包括并发客户端、反复切环、像素正确性和帧间隔。

Metal 接口、缓存和插件打包见 [AdrenoMetal](/zh/drivers/adreno-metal)。

```sh
python3 scripts/check-native-metal-frontend-host.py
python3 scripts/check-turnip-darwin-host.py
python3 scripts/check-smmu4k-live.py
python3 scripts/check-turnip-pipeline-cache-host.py
python3 scripts/check-priming-cache-host.py --output build/priming-cache/run
python3 scripts/probe-turnip-internal-compiler-host.py --qualification <old> --output <new>
```

设备仓库增加原始输入检查：

```sh
python3 scripts/build-adreno-compiler-host.py --probe
python3 scripts/build-turnip-ios-compiler-peer.py
python3 scripts/check-turnip-ios-compiler-cache.py
python3 scripts/check-quartzcore-turnip-cache-host.py
```

## 相关

- [小米平板 6S Pro（sheng）](/zh/devices/sheng)
- [XNU 驱动](/zh/drivers/xnu-drivers)
- [4 KiB 页表](/zh/xnu/four-k-page-tables)

## SM7675 集成

gen7_11_0 profile 使用真实 chip ID 0x43030b00、1.5 MiB GMEM、2196 KiB 抢占记录和 gen71100 固件。uke 沿用 sheng 的 mode 2 调度、每进程 VM 与 Metal 前端；iPadOS 27 当前为构建候选，待真机验收。


## Native-XNU 页面准备候选

uke候选把尚未发布的系统BO页面准备移到IOUserClient原映射排斥锁之外。可选prepare/finish入口用活动IPC计数覆盖预准备、原锁内校验/采用及锁外清理；close抢先完成时拒绝采用并回收页面。分配诊断的用户栈读取也在锁外。map/unmap/close同步、请求ABI和真实错误保留；未搭配原生适配时走原分配路径，BO trace bit16标识preflight。主机并发检查与镜像构建通过，实机收益和120Hz尚未验证。


可选preflight路径要求GPU发布后的运行时ready，不能只凭回调符号存在即启用。早期client不进入新增IPC pin，driver在类型转换前再次检查ready；记录ready/entries区分启动阶段与实际GPU工作。GPU就绪后的BO锁外准备优化保留；开机和帧时间收益须实机验证。


同一ready门控私有context扩展非零超时WaitFence：原校验/超时/等待/恢复在映射排斥锁前执行，原锁内复核请求/live再消费实际结果；关闭成功使等待停止或拒绝消费。零timeout poll和map/unmap/close原锁不变，不伪造fence完成。板级导出calls/elapsed/max/non-success，后者包含真实timeout。

preflight context在IONew后显式赋值初始化；IONew只分配存储，不执行C++成员默认初始化。仅零填充会让method=0而不是BoAlloc2，导致已准备页面不被采用、在映射排斥锁内再次准备。uke0A3F的58条大BO记录均为回退flags11，真实原始分配语义的宿主负对照已复现，修正后通过。四分多钟无响应的完整因果仍未确认。

开启sheng-diag时，前八次判定挂起在复位前持久记录CP寄存器，并将已有stall/IB/切环记录明确标为此前数据。诊断读取失败只报错，不改变ring健康状态，原stallState失败契约保留。正常帧不加采样，恢复/提交/超时策略不变；该候选用于定位，尚不是性能修复。

## 轻量shader等待计数

uke的`sheng-diag=2 sheng-gpu-trace=2`保留原21个BR计数，以event69追加十个SP计数：UCHE/RB阻塞、wave context/wait、长短同步、local-memory load/store、片元half ALU和EFU working。BR采样使用SP7–16槽及第一组RBBM_PERFCTR_SP，event69显式标记0x4252001f。旧marker31实际选到BV的SP24–33，按bv_legacy解码并排除BR归因；忙于shader时新增计数全平也视为无效，即使selector读回正确。原约32ms采样、epoch及读回校验保持，不加逐pass GPU时间戳。旧21计数可继续解码，跨计数计划的窗口排除。这些聚合计数用于下一步分类，不当作某个pass的独占耗时或已证明的提速；local-memory访问也不全部等于寄存器spill。


帧诊断保留分配、命令、完成处理及 GPU、显示时间线，像素抓取关闭。使用方法见 [GPU 帧诊断](/zh/porting/gpu-diagnostics)。

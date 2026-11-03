# AdrenoMetal

先按[适配流程](/zh/porting/gpu)准备板级输入、修改源码、接入构建并逐步验证。

AdrenoMetal 通过 metal2vulkan 和 Turnip 提供 Metal 前端。它通过 `MTLAddDevice`
发布设备，翻译 AIR，并向内核 GPU 接口提交任务。

| 字段 | 值 |
| --- | --- |
| 仓库 | [UniXNU/AdrenoMetal](https://github.com/UniXNU/AdrenoMetal) |
| 实现 | A740/SM8550 图形栈和所选 OS ABI |
| 依赖 | Adreno740、Turnip、metal2vulkan、IOGPUFamily 和 IOSurface 接口 |
| 板级输入 | 固件、电源策略、内存布局、显示集成 |
| 已验证设备 | sheng |
| 运行时插件 | `NativeAdrenoMetal` |

sheng 已运行 GPU 合成桌面。导出的 pipeline cache 可在后续启动复用。桌面空闲时，
render server 会预编译系统镜像中的全部 Metal 库：payload 带有库列表
（`NativeAdrenoMetal.primelist`），以及一份 cryptex 中 QuartzCore 库的副本，因为
render server 的沙盒访问不到 cryptex 路径。120 Hz 下空闲桌面每 250 ms 提交约
6 个命令缓冲区，所以只有超过 8 个时预编译才会等待。日志 PR 行显示进度；sheng 上
162 个库已全部预编译。有列表时 render server 不扫描目录，并且只在显示空闲时读取
每个库。
列表、pipeline 包和续编译规则见[预热着色器缓存](/zh/porting/gpu#shader-warmup)。

无法编码的 render pass 仍返回 encoder，并拒绝其命令缓冲区：RenderBox 会缓存
encoder 的方法，不能接受 nil。每个进程的第一个问题由出错
的线程写入驱动的进程文本行。

```sh
python3 scripts/build-turnip-darwin.py --target ios
python3 scripts/build-adreno-metal-plugin.py
```

运行时流程、发布命令和检查见 [Adreno740](/zh/drivers/adreno740)。


## iOS 27 Turnip 装载格式

Turnip 与插件均用 `--target ios27` 构建。Turnip 链接显式启用 `-Wl,-fixup_chains`，并向 Meson 已有构建目录重新传递链接参数；最终签名 dylib 应包含 `LC_DYLD_CHAINED_FIXUPS`，owner trust 需使用新 CDHash。

uke 24A446 的同 boot iconservicesagent 报告显示，Metal 打开 Turnip 时在 dyld `MachOAnalyzer::withChainStarts` 中触发线程栈 guard fault。旧 arm64e `LC_DYLD_INFO_ONLY` 导致 dyld 在工作队列栈上临时合成链元数据；旧库需要 439,304 字节，与崩溃 x8 精确相符。显式链元数据避开该兼容分支。修正保留渲染逻辑与编译器 pin；图标/小组件恢复及卡死验收仍需真机。见 [Apple 实现](https://github.com/apple-oss-distributions/dyld/blob/main/common/MachOAnalyzer.cpp)。

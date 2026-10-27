# sheng 日志抓取示例

通用[日志抓取步骤](/zh/porting/log-capture)定义移植流程。本页记录该流程使用的
sheng 参数：存储区域、Linux 读取器镜像、复位参数和执行脚本。

## 板型输入

使用 [sheng 设备仓库](https://github.com/UniXNU/UniXNU-sheng)、已构建的内核与 package、
已填写的[本地输入](/zh/reference/configuration#local-build-inputs)、fastboot 和 Python 3。

```sh
DEVICE_REPO=$(cd ../UniXNU-sheng && pwd)
TARGET="$PWD/out/sheng/ipados-17.7.11-21H461/sheng"
mkdir -p "$TARGET/boot"
fastboot devices
```

sheng 写入器将 `userdata` 最后 32 MiB 作为日志区域。板型参数如下：

| 参数 | 功能 |
| --- | --- |
| `sheng-log=1` | 启动持久化日志写入器 |
| `sheng-autoreset=120` | 日志同步完成并达到 120 秒时限后返回 fastboot |

实现位于设备仓库的 `package/BootLog.c`、`BootReset.c`、`BootResetCore.h`、
`package/linux-log/` 和 `scripts/read-sheng-log.py`。
[sheng Linux release](https://github.com/ianchb/sm8550-mainline/releases)
提供 `boot_sheng_singleboot.img` 和 `nvmem-reboot-mode.ko`。

## 读取器镜像

使用设备仓库脚本构建 sheng Linux 读取器。读取器将预留区域复制到 RAM，提供 USB CDC ACM shell，
源存储保持只读。

```sh
clang++ --target=aarch64-linux-gnu -fuse-ld=lld -nostdlib -static \\
  -fno-stack-protector -fno-exceptions -fno-rtti -Wl,-e,start \\
  "$DEVICE_REPO/package/linux-log/rebootbl.cpp" -o "$TARGET/boot/rebootbl"
python3 "$DEVICE_REPO/package/linux-log/build-linux-log-boot.py" \\
  --boot /path/to/boot_sheng_singleboot.img --busybox /path/to/busybox \\
  --rebootbl "$TARGET/boot/rebootbl" --module /path/to/nvmem-reboot-mode.ko \\
  --out "$TARGET/boot/sheng-linux-log.img"
```

## 手动循环 {#manual-cycle}

构建并启动日志镜像，再启动读取器并取回区域：

```sh
./unixnu payload --kernel-arg=sheng-log=1
./unixnu bootimg
SERIAL=<serial>
fastboot -s "$SERIAL" boot "$TARGET/boot/boot.img"
fastboot -s "$SERIAL" boot "$TARGET/boot/sheng-linux-log.img"
python3 "$DEVICE_REPO/scripts/read-sheng-log.py" \\
  --wait 240 --out "$TARGET/logs/captures"
```

输出目录按启动 ID 保存 `log.bin`、`header.txt`、`msgbuf.txt`、`slots.txt` 和 `latest.txt`。
确认读取器将设备返回 fastboot 后再开始下一次测试。recovery 读取器按[recovery 读取器步骤](/zh/porting/log-capture#persistent-logs)执行。

## 自动循环 {#automated-cycle}

启用定时复位后，使用绝对镜像路径运行板级脚本：

```sh
./unixnu payload --kernel-arg=sheng-log=1 \\
  --kernel-arg=sheng-autoreset=120
./unixnu bootimg
SERIAL="$SERIAL" READER="$TARGET/boot/sheng-linux-log.img" \\
  bash "$DEVICE_REPO/scripts/run-sheng-unattended.sh" \\
  "$TARGET/boot/boot.img" 420
```

脚本将日志保存到 `UniXNU-sheng/build/sheng-logs/<tag>-<boot id>/`。
在[适配记录](/zh/porting/records)中记录镜像版本、参数、检查点、复位结果和输出目录。

## 读取器验证

设备仓库提供 QEMU 检查，覆盖分区查找、复制到 RAM、传输和解码：

```sh
python3 "$DEVICE_REPO/package/linux-log/check-linux-log-qemu.py" \\
  --image "$TARGET/boot/sheng-linux-log.img" \\
  --kernel /path/to/qemu-virt-linux-Image \\
  --work "$TARGET/logs/reader-qemu"
```

将这项主机检查与板级存储写入、USB 传输和复位观察分别记录。

<p align="right">
  <strong>简体中文</strong> · <a href="README.md">English</a>
</p>

# AI Passport 槽位刷写助手

一个小桌面工具:把固件刷进 FoloToy AI Passport 的**切换器槽位**,不碰切换器
本体,也不影响其它槽位。

## 为什么需要它

整片 `0x0` 刷写会覆盖设备上的一切。这个工具让你选一个固件文件、选一个槽位
(A/B/C 或 A/B,自动识别),然后**只写该槽位的偏移**并写后校验。

## 下载

预打包安装包在
[GitHub Releases](https://github.com/RainYufan/ai-passport-slot-flasher/releases)
(最新 `flasher-v1.3.0`):

| 平台 | 文件 |
| --- | --- |
| Windows x64 | `AI-Passport-Flasher.exe`(单文件,免安装) |
| macOS(Apple Silicon / arm64) | `AI-Passport-Flasher-macos-arm64.dmg` |
| Linux x64 | `AI-Passport-Flasher-linux-x64.tar.gz` |
| Linux ARM64 | `AI-Passport-Flasher-linux-arm64.tar.gz` |

> macOS 目前只提供 arm64(Apple Silicon)版;Intel Mac 用户请用源码运行
> (见下方「从源码运行」)。Linux 压缩包解压后运行目录里的 `run.sh` 或
> `./AI-Passport-Flasher`。

配套工具 **extract-play**(玩法固件提取器)也在同一个 Release 里,详见下方
「提取 app 镜像」。

## 功能

- 自动识别设备布局:**三槽版**或**双槽版**,显示每个槽位的偏移与大小限制。
- 校验所选 `.bin`:识别纯 app 镜像(`0xE9` 魔数)与玩法社区的
  `esp-merged-0x0` 合并镜像,显示项目名/版本/日期/真实大小。
- 一键从合并镜像**提取 app 镜像**。
- 槽位空间检查:装不下的槽位自动置灰。
- 进度条 + 完整 esptool 日志。
- 单独的“刷入切换器本体(0x0)”按钮,带醒目警告,用于首次安装。

## 使用(刷固件进槽位)

1. 用数据线把 AI Passport 连到电脑。点 **刷新** → **检测设备与布局**。
2. 选一个固件 `.bin`(纯 app 镜像,或合并镜像)。
3. 选目标槽位,点 **刷入所选槽位**。工具只写该槽位偏移,写后自动校验。
4. 要(重)装切换器本体,用 **刷入切换器本体（0x0）**——会覆盖设备上的一切。

槽位上限:**三槽版 2MB,双槽版约 3.56MB**;布局表见
[切换器仓库](https://github.com/RainYufan/folotoy-ai-passport-firmware-switcher)。

## 提取 app 镜像(重点)

玩法社区下载的是 `esp-merged-0x0` **完整合并镜像**(含 bootloader + 分区表 +
app),而切换器槽位只接受**纯 app 镜像**(文件以 `0xE9` 魔数开头)。所以往槽位
刷之前,通常要先“提取出 app 镜像”。三种方法任选:

### 方法 A:图形界面 extract-play(推荐)

同一个 Release 里有 `extract_play_gui`(Windows `.exe`;macOS/Linux 在
`extract_play-*.dmg` / `extract_play-*.tar.gz` 里):

1. 打开 extract-play 图形界面。
2. **粘贴玩法链接**(如 `https://ai-passport.folotoy.cn/plays/2378/`)到输入框,
   或者**直接把本地合并镜像 `.bin` 拖进窗口**,或点「选择本地文件…」。
3. 点「**提取 app 镜像**」。
4. 完成后弹窗给出 `xxx-app.bin` 的路径,点「打开输出文件夹」直接找到它。
5. 把这个 `xxx-app.bin` 拖进「槽位刷写助手」选为固件,再刷入槽位即可。

### 方法 B:命令行 extract-play

- Windows 直接双击 `extract_play.exe`,粘贴链接回车;或:
- 任意系统有 Python 3 时:

  ```bash
  python extract_play.py "https://ai-passport.folotoy.cn/plays/2378/"
  ```

输出两个文件到当前目录:`xxx-merged.bin`(原始镜像,带 SHA-256 校验)与
`xxx-app.bin`(可刷入槽位的纯 app 镜像)。

### 方法 C:手动 Python 片段(无工具时的兜底)

```python
import struct
data = open("play-merged.bin", "rb").read()
tbl = data[0x8000:0x9000]
ENTRY = struct.Struct("<HBBII16sI")
off = 0
while off + ENTRY.size <= len(tbl):
    magic = int.from_bytes(tbl[off:off+2], "little")
    if magic in (0xFFFF, 0xEBEB):
        break
    _, kind, _, poff, size, _, _ = ENTRY.unpack_from(tbl, off)
    if kind == 0:  # app 分区
        open("extracted-app.bin", "wb").write(data[poff:])  # 整段提取,不裁剪
        break
    off += ENTRY.size
```

> 为什么“整段提取、不裁剪”:app 镜像末尾带 SHA-256 校验摘要,按长度裁剪会
> 切掉摘要,导致 bootloader 校验失败、刷入后无法启动。整段复制 app 分区即可。

### 校验与大小限制

- 用 `esptool image_info xxx-app.bin` 应显示 `Checksum valid · Validation
  Hash valid`;刷写助手选文件时也会自动识别并显示大小。
- **槽位大小上限**:三槽版每个 **2MB**;双槽版每个 **约 3.56MB**。超过上限的
  固件放不进槽位(刷写助手会把对应槽位置灰)。
- 系统级固件(如 `passport-os`,动辄 3.9MB~5.6MB)超限,只能整片刷 `0x0` 使用,
  不能放进切换器槽位。

## 从源码运行

需要 Python ≥3.9:

```bash
pip install -r requirements.txt
python run.py            # 刷写助手
python extract_play_gui.py   # 提取器图形界面
```

## 开发

- 纯逻辑(分区解析、镜像校验/提取、槽位适配)在
  `ai_passport_flasher/model.py`,有单元测试。
- 刷写后端 `ai_passport_flasher/flash.py` 进程内调用 esptool,打包后依然可用。
- 测试:`python -m unittest discover -s tests`(GUI 测试用
  `QT_QPA_PLATFORM=offscreen` 无头运行)。
- 打包:`pyinstaller --noconfirm --windowed --name AI-Passport-Flasher \
  --collect-data esptool run.py`

## 许可

MIT。切换器固件与上游基线为
[FoloToy/ai-passport](https://github.com/FoloToy/ai-passport)(MIT)。

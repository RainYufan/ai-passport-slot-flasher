<p align="right">
  <strong>简体中文</strong> · <a href="README.md">English</a>
</p>

# AI Passport 槽位刷写助手

一个小桌面工具:把固件刷进 FoloToy AI Passport 的**切换器槽位**,不碰切换器
本体,也不影响其它槽位。

## 为什么需要它

整片 `0x0` 刷写会覆盖设备上的一切。这个工具让你选一个固件文件、选一个槽位
(A/B/C 或 A/B,自动识别),然后**只写该槽位的偏移**并写后校验。

## 功能

- 自动识别设备布局:**三槽版**或**双槽版**,显示每个槽位的偏移与大小限制。
- 校验所选 `.bin`:识别纯 app 镜像(`0xE9` 魔数)与玩法社区的
  `esp-merged-0x0` 合并镜像,显示项目名/版本/日期/真实大小。
- 一键从合并镜像**提取 app 镜像**。
- 槽位空间检查:装不下的槽位自动置灰。
- 进度条 + 完整 esptool 日志。
- 单独的“刷入切换器本体(0x0)”按钮,带醒目警告,用于首次安装。

## 获取

- 预打包文件由 [`.github/workflows/build-flasher.yml`](.github/workflows/build-flasher.yml)
  的 Release 构建产出(macOS arm64 `.app`、Windows x64)。
- 或从源码运行:Python ≥3.9,然后

  ```bash
  cd flasher
  pip install -r requirements.txt
  python run.py
  ```

## 使用

1. 用数据线把 AI Passport 连到电脑。点 **刷新**、**检测设备与布局**。
2. 选一个固件 `.bin`(app 镜像或合并镜像;合并镜像先点 **提取 app 镜像**)。
3. 选目标槽位,点 **刷入所选槽位**。工具只写该槽位偏移,写后自动校验。
4. 要(重)装切换器本体,用 **刷入切换器本体（0x0）**——会覆盖设备上的一切。

槽位上限:三槽版 2MB,双槽版约 3.56MB;布局表见[切换器仓库](https://github.com/RainYufan/folotoy-ai-passport-firmware-switcher)。

## 开发

- 纯逻辑(分区解析、镜像校验/提取、槽位适配)在
  `ai_passport_flasher/model.py`,有单元测试。
- 刷写后端 `ai_passport_flasher/flash.py` 进程内调用 esptool,打包后依然可用。
- 测试:`python -m unittest discover -s tests`(GUI 测试用
  `QT_QPA_PLATFORM=offscreen` 无头运行)。
- 打包:`pyinstaller --noconfirm --windowed --name AI-Passport-Flasher run.py`

## 许可

MIT。切换器固件与上游基线为
[FoloToy/ai-passport](https://github.com/FoloToy/ai-passport)(MIT)。

# Changelog · 更新日志

## 1.2.1 — 2026-11-20

**更多平台架构 / more architectures**

- macOS 增加 **Intel(x64)** 版本;Linux 增加 **ARM64** 版本。
- 刷写助手与 extract-play 工具现覆盖:Windows x64、macOS arm64/x64、Linux x64/arm64。

## 1.2.0 — 2026-11-20

**extract-play 多平台 / extract-play multi-platform**

- 新增 `extract_play_gui` 图形界面(粘贴链接或拖入/选择本地合并镜像,一键提取)。
- extract-play 工具现提供 Windows `.exe`、macOS `.dmg`、Linux `.tar.gz` 三个平台版本。
- Release 同步附带 `extract_play`(命令行)与 `extract_play_gui`(图形)两种。

## 1.1.0 — 2026-11-15

**更易安装 / Easier to install**

- macOS 提供 **`.dmg`** 安装镜像（拖入“应用程序”即可）。
- Windows 提供单文件 **`.exe`**（免安装，直接运行）。
- Linux 提供 **AppImage**（免安装，`chmod +x` 后直接运行）。

**修复 / Fixes**

- 修复提取合并镜像时按长度裁剪导致 SHA256 摘要被切掉、刷入的固件无法启动的问题。
- 修复打包后 Qt 默认字体缺失 + 跨线程改界面导致的崩溃（SIGSEGV）。
- 修复合并镜像（`0xE9` 开头）与纯 app 镜像的识别混淆。
- 打包时补齐 esptool 的 stub 数据文件（否则连不上设备）。

**平台说明 / Platform notes**

- iOS：暂不支持。iOS 不允许第三方 App 访问 USB 串口，无法做本地刷写。
- Android：计划中，需另建原生/Kivy 应用（安卓 USB-Serial），不并入桌面版。

## 1.0.0 — 2026-11-15

- 首个版本：自动识别三槽/双槽版切换器布局，选择固件与槽位后安全刷入（只写槽位偏移，不覆盖切换器），支持合并镜像提取与整片 0x0 刷切换器。

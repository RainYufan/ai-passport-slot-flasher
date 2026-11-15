<p align="right">
  <a href="README.zh_CN.md">简体中文</a> · <strong>English</strong>
</p>

# AI Passport Slot Flasher

A small desktop tool that flashes firmware **into a switcher slot** on the
FoloToy AI Passport — without touching the switcher itself or the other slots.

## Why

Flashing a full merged image at `0x0` replaces everything on the device. With
this tool you pick a firmware file, pick a slot (A/B/C or A/B, auto-detected
from the device), and it writes **only that slot's offset** with verify.

## Features

- Auto-detects the connected device's layout: **3-Slot** or **Dual-Slot**
  edition, showing each slot's offset and size limit.
- Validates the chosen `.bin`: recognizes plain app images (`0xE9` magic) and
  `esp-merged-0x0` archives from the play store, shows the firmware's project
  name / version / date / real size.
- One-click extraction of the app image from a merged archive.
- Slot size check: slots that cannot hold the image are disabled.
- Progress bar and full esptool log.
- A separate "flash the switcher itself (0x0)" button behind an explicit
  warning, for first-time installation.

## Download

- Prebuilt packages are attached to releases built by
  [`.github/workflows/build-flasher.yml`](.github/workflows/build-flasher.yml)
  (macOS arm64 `.app`, Windows x64).
- Or run from source: Python ≥3.9, then

  ```bash
  cd flasher
  pip install -r requirements.txt
  python run.py
  ```

## Use

1. Connect the AI Passport over USB (data cable). Click **刷新** and
   **检测设备与布局**.
2. Pick a firmware `.bin` (app image or merged archive; use
   **提取 app 镜像** for merged files).
3. Choose the target slot and click **刷入所选槽位**. The tool writes only
   that slot's offset and verifies afterwards.
4. To (re)install the switcher itself, use **刷入切换器本体（0x0）** — this
   replaces everything on the device.

Slot limits are 2 MB (3-Slot edition) or ≈3.56 MB (Dual-Slot edition); see the layout tables in the [switcher repo](https://github.com/RainYufan/folotoy-ai-passport-firmware-switcher).

## Development

- Pure logic (partition parsing, image validation/extraction, slot fitting)
  lives in `ai_passport_flasher/model.py` and is unit-tested.
- The flash backend (`ai_passport_flasher/flash.py`) calls esptool in-process,
  so it keeps working inside the packaged app.
- Tests: `python -m unittest discover -s tests` (GUI tests run headless with
  `QT_QPA_PLATFORM=offscreen`).
- Package: `pyinstaller --noconfirm --windowed --name AI-Passport-Flasher run.py`

## License

MIT. The switcher firmware and upstream baseline are
[FoloToy/ai-passport](https://github.com/FoloToy/ai-passport) (MIT).

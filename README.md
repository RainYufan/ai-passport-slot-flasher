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

## Download

Prebuilt installers are on
[GitHub Releases](https://github.com/RainYufan/ai-passport-slot-flasher/releases)
(latest `flasher-v1.3.0`):

| Platform | File |
| --- | --- |
| Windows x64 | `AI-Passport-Flasher.exe` (single file, no install) |
| macOS (Apple Silicon / arm64) | `AI-Passport-Flasher-macos-arm64.dmg` |
| Linux x64 | `AI-Passport-Flasher-linux-x64.tar.gz` |
| Linux ARM64 | `AI-Passport-Flasher-linux-arm64.tar.gz` |

> macOS only ships arm64 (Apple Silicon); Intel Mac users can run from source
> (see below). For Linux, unpack and run `run.sh` or `./AI-Passport-Flasher`.

The companion **extract-play** tool (firmware extractor) is in the same release.

## Features

- Auto-detects the connected device's layout: **3-Slot** or **Dual-Slot**.
- Validates the chosen `.bin`: recognizes plain app images (`0xE9` magic) and
  `esp-merged-0x0` archives, showing project name / version / date / size.
- One-click extraction of the app image from a merged archive.
- Slot size check: slots that cannot hold the image are disabled.
- Progress bar and full esptool log.
- A separate "flash the switcher itself (0x0)" button behind an explicit warning.

## Use (flash into a slot)

1. Connect the AI Passport over USB. Click **刷新** → **检测设备与布局**.
2. Pick a firmware `.bin` (app image, or merged archive).
3. Choose the target slot and click **刷入所选槽位**. Only that slot is written.
4. To (re)install the switcher itself, use **刷入切换器本体（0x0）** — replaces
   everything.

Slot limits: **2 MB (3-Slot)** or **≈3.56 MB (Dual-Slot)**; see the
[switcher repo](https://github.com/RainYufan/folotoy-ai-passport-firmware-switcher).

## Extract the app image (important)

The play store serves `esp-merged-0x0` full images (bootloader + partition table
+ app), but a slot only accepts a **plain app image** (file starts with the `0xE9`
magic byte). So before flashing into a slot you usually need to extract the app
image. Three ways:

### A) GUI — extract-play (recommended)

`extract_play_gui` ships in the same release (Windows `.exe`; macOS/Linux inside
`extract_play-*.dmg` / `extract_play-*.tar.gz`):

1. Open the extract-play GUI.
2. **Paste the play link** (e.g. `https://ai-passport.folotoy.cn/plays/2378/`),
   or **drag a local merged `.bin` into the window**, or click **选择本地文件…**.
3. Click **提取 app 镜像**.
4. A dialog shows the `xxx-app.bin` path; click **打开输出文件夹** to open it.
5. Drag that `xxx-app.bin` into the slot flasher and flash it into a slot.

### B) Command line — extract-play

- Windows: double-click `extract_play.exe`, paste the link, press Enter; or
- Any OS with Python 3:

  ```bash
  python extract_play.py "https://ai-passport.folotoy.cn/plays/2378/"
  ```

It writes `xxx-merged.bin` (with SHA-256 verification) and `xxx-app.bin`.

### C) Manual Python snippet (fallback)

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
    if kind == 0:  # app partition
        open("extracted-app.bin", "wb").write(data[poff:])  # whole region, no trim
        break
    off += ENTRY.size
```

> "Whole region, no trim" matters: the app image ends with a SHA-256 digest;
> trimming by a computed length cuts the digest, the bootloader rejects the
> image, and the flashed firmware never boots.

### Verify & size limits

- `esptool image_info xxx-app.bin` should report `Checksum valid · Validation
  Hash valid`; the slot flasher also detects and shows the size when you pick it.
- **Slot limits**: 2 MB each (3-Slot) or ≈3.56 MB each (Dual-Slot). Larger images
  can't fit a slot (the flasher disables those slots).
- System firmwares (`passport-os`, ~3.9–5.6 MB) exceed the limits and can only be
  flashed whole at `0x0`, not into a switcher slot.

## Run from source

Python ≥3.9:

```bash
pip install -r requirements.txt
python run.py              # slot flasher
python extract_play_gui.py # extractor GUI
```

## Development

- Pure logic (partition parsing, image validation/extraction, slot fitting) lives
  in `ai_passport_flasher/model.py` and is unit-tested.
- The flash backend (`ai_passport_flasher/flash.py`) calls esptool in-process.
- Tests: `python -m unittest discover -s tests` (GUI tests run headless with
  `QT_QPA_PLATFORM=offscreen`).
- Package: `pyinstaller --noconfirm --windowed --name AI-Passport-Flasher \
  --collect-data esptool run.py`

## License

MIT. The switcher firmware and upstream baseline are
[FoloToy/ai-passport](https://github.com/FoloToy/ai-passport) (MIT).

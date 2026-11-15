# ai_passport_flasher/model.py
"""纯逻辑层:槽位布局、分区表解析、app 镜像校验/提取。不依赖 GUI 与 esptool,可单元测试。"""

from __future__ import annotations

import dataclasses
import struct

FLASH_SIZE = 8 * 1024 * 1024
APP_DESC_MAGIC = 0xABCD5432
ESP_IMAGE_MAGIC = 0xE9

_PART_ENTRY = struct.Struct("<HBBII16sI")


@dataclasses.dataclass(frozen=True)
class Slot:
    label: str          # slot_a / slot_b / slot_c
    tag: str            # A / B / C
    offset: int
    size: int


@dataclasses.dataclass(frozen=True)
class Layout:
    name_zh: str
    name_en: str
    factory_size: int
    otadata_offset: int
    slots: tuple[Slot, ...]

    def slot_by_label(self, label: str) -> Slot | None:
        for s in self.slots:
            if s.label == label:
                return s
        return None


# 与切换器固件的 partitions.csv 保持一致的两种布局(唯一来源见各分支 partitions.csv)。
LAYOUT_THREE_SLOT = Layout(
    name_zh="三槽版", name_en="3-Slot",
    factory_size=0x100000, otadata_offset=0x110000,
    slots=(
        Slot("slot_a", "A", 0x120000, 0x200000),
        Slot("slot_b", "B", 0x320000, 0x200000),
        Slot("slot_c", "C", 0x520000, 0x200000),
    ),
)
LAYOUT_DUAL_SLOT = Layout(
    name_zh="双槽版", name_en="Dual-Slot",
    factory_size=0xC0000, otadata_offset=0xD0000,
    slots=(
        Slot("slot_a", "A", 0xE0000, 0x390000),
        Slot("slot_b", "B", 0x470000, 0x390000),
    ),
)

# 分区表魔数。factory app 分区 type=0;otadata type=1 sub=0。
PART_TYPE_APP = 0
PART_TYPE_DATA = 1


@dataclasses.dataclass(frozen=True)
class Partition:
    label: str
    kind: int
    subtype: int
    offset: int
    size: int


def parse_partition_table(raw: bytes) -> list[Partition]:
    """解析 4KB 分区表二进制(esptool read_flash 0x8000 0x1000 的输出)。"""
    if len(raw) < 0xC00:
        raise ValueError("分区表数据不完整")
    parts: list[Partition] = []
    for cursor in range(0, 0xC00, _PART_ENTRY.size):
        magic = int.from_bytes(raw[cursor:cursor + 2], "little")
        if magic in (0xFFFF, 0xEBEB):
            break
        if magic != 0x50AA:
            raise ValueError(f"分区表条目非法: 0x{cursor:x}")
        _, kind, subtype, offset, size, label_raw, _ = _PART_ENTRY.unpack_from(raw, cursor)
        label = label_raw.split(b"\0", 1)[0].decode("ascii", "strict")
        parts.append(Partition(label, kind, subtype, offset, size))
    if not parts:
        raise ValueError("分区表为空")
    return parts


def detect_layout(parts: list[Partition]) -> Layout | None:
    """按分区表识别是三槽版还是双槽版;都不是返回 None。"""
    labels = {(p.label, p.kind, p.offset, p.size) for p in parts}
    for layout in (LAYOUT_THREE_SLOT, LAYOUT_DUAL_SLOT):
        expect = {(s.label, PART_TYPE_APP, s.offset, s.size) for s in layout.slots}
        expect.add(("factory", PART_TYPE_APP, 0x10000, layout.factory_size))
        expect.add(("otadata", PART_TYPE_DATA, layout.otadata_offset, 0x2000))
        if expect.issubset(labels):
            return layout
    return None


@dataclasses.dataclass(frozen=True)
class ImageInfo:
    kind: str            # app / merged / invalid
    size: int            # app 镜像实际字节数(kind==app 时;merged 为文件大小)
    project: str
    version: str
    date: str
    first_offset: int    # merged 时 app 分区起始偏移;app 时为 0


def _segments_size(data: bytes) -> int:
    """按 esptool 同样的顺序(段头与数据交错,含对齐)算出 app 镜像真实长度。"""
    if len(data) < 24 or data[0] != ESP_IMAGE_MAGIC:
        raise ValueError("不是 ESP app 镜像(缺少 0xE9 魔数)")
    seg_count = data[1]
    pos = 24
    for _ in range(seg_count):
        if pos + 8 > len(data):
            raise ValueError("镜像段表越界")
        _, data_len = struct.unpack_from("<II", data, pos)
        pos += 8 + data_len
    # 追加的 SHA256 摘要(镜像头 bit0 hash_appended)
    if data[12] & 1:
        pos += 32
    return pos


def _find_app_desc(data: bytes) -> tuple[str, str, str] | None:
    """扫描 app 镜像开头 16KB 内的应用描述魔数,读出 项目名/版本/日期。"""
    window = data[:0x4000]
    for off in range(0x20, len(window) - 4, 4):
        if struct.unpack_from("<I", window, off)[0] != APP_DESC_MAGIC:
            continue
        desc = data[off:off + 256]
        if len(desc) < 256:
            continue
        project = desc[48:80].split(b"\0", 1)[0].decode("ascii", "replace")
        version = desc[16:48].split(b"\0", 1)[0].decode("ascii", "replace")
        date = desc[96:112].split(b"\0", 1)[0].decode("ascii", "replace")
        return project, version, date
    return None


def inspect_image(path: str) -> ImageInfo:
    """识别固件文件:纯 app 镜像 或 esp-merged 合并镜像,并解析元数据。"""
    with open(path, "rb") as f:
        data = f.read()
    if not data:
        raise ValueError("文件为空")
    # 先判合并镜像:bootloader 也以 0xE9 开头,不能只看首字节。
    # 合并镜像的标志是 0x8000 处有一张合法分区表(nvs@0x9000 起步)。
    if len(data) >= 0x9000:
        try:
            parts = parse_partition_table(data[0x8000:0x9000])
            if parts and parts[0].label == "nvs" and parts[0].offset == 0x9000:
                apps = [p for p in parts if p.kind == PART_TYPE_APP]
                if not apps:
                    raise ValueError("合并镜像里没有 app 分区")
                app_part = apps[0]
                app_bytes = data[app_part.offset:app_part.offset + app_part.size]
                size = len(app_bytes)  # 整段区域,不裁剪(镜像末尾有校验摘要,裁剪会坏)
                desc = _find_app_desc(app_bytes) or ("?", "?", "?")
                return ImageInfo("merged", size, *desc, first_offset=app_part.offset)
        except ValueError:
            pass  # 不是合并镜像,继续按 app 镜像判断
    if data[0] == ESP_IMAGE_MAGIC:
        size = len(data)  # app 镜像整文件刷入,大小即文件大小
        desc = _find_app_desc(data) or ("?", "?", "?")
        return ImageInfo("app", size, *desc, first_offset=0)
    raise ValueError("无法识别的固件文件(既不是 app 镜像也不是合并镜像)")


def extract_app_image(path: str, out_path: str) -> ImageInfo:
    """从 esp-merged 合并镜像中提取纯 app 镜像(裁剪到真实长度,去掉 0xFF 填充)。"""
    info = inspect_image(path)
    if info.kind != "merged":
        raise ValueError("只有合并镜像才需要提取")
    with open(path, "rb") as f:
        data = f.read()
    # 整段复制 app 分区区域(不做长度裁剪),与直接整段刷入的字节一致。
    app_bytes = data[info.first_offset:info.first_offset + info.size]
    with open(out_path, "wb") as f:
        f.write(app_bytes)
    return inspect_image(out_path)


def slots_for_layout(layout: Layout, image_size: int) -> list[tuple[Slot, bool]]:
    """返回 (槽位, 能否容纳) 列表;镜像超过槽位大小的置灰。"""
    return [(s, image_size <= s.size) for s in layout.slots]

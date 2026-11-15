#!/usr/bin/env python3
"""model.py 的单元测试:布局识别、分区表解析、镜像校验/提取。无 GUI 依赖。"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ai_passport_flasher.model import (  # noqa: E402
    LAYOUT_DUAL_SLOT,
    LAYOUT_THREE_SLOT,
    Layout,
    Slot,
    detect_layout,
    extract_app_image,
    inspect_image,
    parse_partition_table,
    slots_for_layout,
)


def build_partition_table(entries: list[tuple[str, int, int, int, int]]) -> bytes:
    buf = bytearray(b"\xff" * 0x1000)  # 其余按 0xFF 填充,与 gen_esp32part 一致
    for i, (label, kind, subtype, offset, size) in enumerate(entries):
        struct.pack_into(
            "<HBBII16sI", buf, i * 32, 0x50AA, kind, subtype, offset, size,
            label.encode("ascii"), 0,
        )
    # MD5 标记(可选):写 0xEBEB 即结束
    return bytes(buf)


def entries_for(layout: Layout) -> list[tuple[str, int, int, int, int]]:
    rows = [
        ("nvs", 1, 2, 0x9000, 0x6000),
        ("phy_init", 1, 1, 0xF000, 0x1000),
        ("factory", 0, 0, 0x10000, layout.factory_size),
        ("otadata", 1, 0, layout.otadata_offset, 0x2000),
    ]
    rows += [(s.label, 0, 16 + i, s.offset, s.size) for i, s in enumerate(layout.slots)]
    return rows


def build_app_image(project: str = "FoloToy-AI-Passport", version: str = "abc1234",
                    date: str = "Nov 15 2026", drom_len: int = 0x1000) -> bytes:
    """构造一个结构上合法的 ESP app 镜像(段头交错布局,含 app_desc)。"""
    # 段 0:DROM,数据前 256 字节是 esp_app_desc_t
    desc = bytearray(256)
    struct.pack_into("<I", desc, 0, 0xABCD5432)
    desc[16:16 + len(version)] = version.encode()
    desc[48:48 + len(project)] = project.encode()
    desc[96:96 + len(date)] = date.encode()
    seg0_data = bytes(desc) + b"\x00" * max(0, drom_len - 256)

    header = bytearray(24)
    header[0] = 0xE9
    header[1] = 2            # 两段:DROM + DRAM
    header[4:8] = struct.pack("<I", 0x40380000)  # entry
    header[12] = 1           # hash_appended
    seg0_hdr = struct.pack("<II", 0x3C080020, len(seg0_data))
    seg1_hdr = struct.pack("<II", 0x3FC90000, 0x100)
    seg1_data = b"\x11" * 0x100
    body = bytes(header) + seg0_hdr + seg0_data + seg1_hdr + seg1_data
    return body + b"\x22" * 32  # SHA256 摘要占位


class PartitionTableTests(unittest.TestCase):
    def test_parse_and_detect_three(self):
        parts = parse_partition_table(build_partition_table(entries_for(LAYOUT_THREE_SLOT)))
        self.assertEqual(detect_layout(parts), LAYOUT_THREE_SLOT)

    def test_parse_and_detect_dual(self):
        parts = parse_partition_table(build_partition_table(entries_for(LAYOUT_DUAL_SLOT)))
        self.assertEqual(detect_layout(parts), LAYOUT_DUAL_SLOT)

    def test_unknown_layout(self):
        rows = entries_for(LAYOUT_THREE_SLOT)
        rows[2] = ("factory", 0, 0, 0x10000, 0x200000)  # 改 factory 大小
        parts = parse_partition_table(build_partition_table(rows))
        self.assertIsNone(detect_layout(parts))

    def test_truncated_table(self):
        with self.assertRaises(ValueError):
            parse_partition_table(b"\x50\xaa" * 4)


class ImageTests(unittest.TestCase):
    def test_inspect_app(self):
        data = build_app_image()
        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(data)
            path = f.name
        try:
            info = inspect_image(path)
            self.assertEqual(info.kind, "app")
            self.assertEqual(info.size, len(data))
            self.assertEqual(info.project, "FoloToy-AI-Passport")
            self.assertEqual(info.version, "abc1234")
            self.assertEqual(info.date, "Nov 15 2026")
        finally:
            os.unlink(path)

    def test_inspect_and_extract_merged(self):
        app = build_app_image()
        # 合并镜像:bootloader 区 + 分区表 + app 镜像,文件正好在 app 末尾结束
        merged = bytearray(0x10000 + len(app))
        merged[0] = 0xE9  # bootloader 同样以 0xE9 开头,分类必须靠分区表
        tbl = build_partition_table(entries_for(LAYOUT_THREE_SLOT))
        merged[0x8000:0x9000] = tbl[:0x1000]
        merged[0x10000:0x10000 + len(app)] = app
        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(bytes(merged))
            merged_path = f.name
        out = tempfile.mktemp(suffix=".bin")
        try:
            info = inspect_image(merged_path)
            self.assertEqual(info.kind, "merged")
            self.assertEqual(info.size, len(app))
            extracted = extract_app_image(merged_path, out)
            self.assertEqual(extracted.kind, "app")
            self.assertEqual(extracted.size, len(app))
            with open(out, "rb") as f:
                self.assertEqual(f.read(), app)
        finally:
            os.unlink(merged_path)
            if os.path.exists(out):
                os.unlink(out)

    def test_inspect_invalid(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".bin", delete=False) as f:
            f.write(b"\x00" * 4096)
            path = f.name
        try:
            with self.assertRaises(ValueError):
                inspect_image(path)
        finally:
            os.unlink(path)


class SlotFitTests(unittest.TestCase):
    def test_fit(self):
        pairs = slots_for_layout(LAYOUT_THREE_SLOT, 0x200000)
        self.assertEqual(pairs, [(s, True) for s in LAYOUT_THREE_SLOT.slots])
        pairs = slots_for_layout(LAYOUT_THREE_SLOT, 0x200001)
        self.assertFalse(any(ok for _, ok in pairs))

    def test_dual_fits_stock(self):
        stock = 3688096  # 原厂固件实际大小
        pairs = slots_for_layout(LAYOUT_DUAL_SLOT, stock)
        self.assertTrue(all(ok for _, ok in pairs))


if __name__ == "__main__":
    unittest.main(verbosity=1)

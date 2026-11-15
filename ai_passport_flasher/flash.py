# ai_passport_flasher/flash.py
"""设备发现与刷写后端:进程内调用 esptool(打包后依然可用),只写槽位偏移。"""

from __future__ import annotations

import contextlib
import io
import os
import re
import tempfile

import serial
from typing import Callable

import esptool

from .model import Layout, detect_layout, parse_partition_table

ProgressFn = Callable[[int], None]
LogFn = Callable[[str], None]

_WRITE_RE = re.compile(r"Writing at 0x[0-9a-fA-F]+\.\.\.\s*\((\d+)\s*%\)")


class _Tee(io.TextIOBase):
    """把 esptool 输出逐行转给 log 回调,并解析写入进度。"""

    def __init__(self, progress: ProgressFn | None, log: LogFn | None):
        super().__init__()
        self._progress = progress
        self._log = log
        self._buf = ""

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        self._buf += text
        # esptool 在非 tty 下用 \r 覆盖式更新进度,把 \r/\n 都当行结束。
        while "\n" in self._buf or "\r" in self._buf:
            idx_n = self._buf.find("\n")
            idx_r = self._buf.find("\r")
            candidates = [i for i in (idx_n, idx_r) if i >= 0]
            if not candidates:
                break
            idx = min(candidates)
            line, self._buf = self._buf[:idx], self._buf[idx + 1:]
            if self._log and line:
                self._log(line)
            m = _WRITE_RE.search(line)
            if m and self._progress:
                self._progress(int(m.group(1)))
        return len(text)

    def flush(self) -> None:
        return None


def run_esptool(
    args: list[str],
    progress: ProgressFn | None = None,
    log: LogFn | None = None,
) -> None:
    """进程内运行 esptool;失败抛 RuntimeError(esptool 内部走 FatalError)。"""
    tee = _Tee(progress, log)
    with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
        try:
            esptool.main(["--chip", "esp32c3"] + args)  # 无返回值,异常即失败
        except esptool.FatalError as exc:
            raise RuntimeError(f"esptool 失败: {exc}") from exc
        except serial.SerialException as exc:
            raise RuntimeError(f"串口错误: {exc}") from exc


def list_ports() -> list[tuple[str, str]]:
    """返回 [(设备路径, 描述)]。"""
    from serial.tools import list_ports as lp

    out = []
    for p in lp.comports():
        desc = p.description or p.device
        out.append((p.device, desc))
    return out


def read_partition_table(port: str, log: LogFn | None = None) -> list:
    """读取设备分区表并解析;返回 Partition 列表。"""
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        tmp = f.name
    try:
        run_esptool(
            ["-p", port, "-b", "921600", "read_flash", "0x8000", "0x1000", tmp],
            log=log,
        )
        with open(tmp, "rb") as f:
            return parse_partition_table(f.read())
    finally:
        os.unlink(tmp)


def detect_device_layout(port: str, log: LogFn | None = None) -> Layout | None:
    return detect_layout(read_partition_table(port, log=log))


def flash_slot(
    port: str,
    slot_offset: int,
    image_path: str,
    progress: ProgressFn | None = None,
    log: LogFn | None = None,
) -> None:
    """把 app 镜像写入指定槽位偏移(--verify 写后校验)。不触碰其它区域。"""
    run_esptool(
        ["-p", port, "-b", "921600",
         "--before", "default_reset", "--after", "hard_reset",
         "write_flash", "--verify", f"0x{slot_offset:x}", image_path],
        progress=progress, log=log,
    )


def flash_switcher(
    port: str,
    merged_path: str,
    progress: ProgressFn | None = None,
    log: LogFn | None = None,
) -> None:
    """整片 0x0 写入切换器合并镜像(会覆盖 bootloader/分区表/全部槽位)。"""
    run_esptool(
        ["-p", port, "-b", "921600",
         "--before", "default_reset", "--after", "hard_reset",
         "write_flash", "--verify", "0x0", merged_path],
        progress=progress, log=log,
    )

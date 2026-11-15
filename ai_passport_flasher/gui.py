# ai_passport_flasher/gui.py
"""PySide6 界面:选固件 → 选槽位 → 刷入。刷槽位不碰 0x0,不覆盖切换器。"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import flash as flash_backend
from .model import (
    Layout,
    extract_app_image,
    inspect_image,
    slots_for_layout,
)

APP_TITLE = "AI Passport 固件槽位刷写助手"
ZERO_OFFSET_WARNING = (
    "整片 0x0 刷写会覆盖设备上的 bootloader、分区表和全部槽位内容\n"
    "（包括切换器本体）。确定要继续吗？"
)


class _Signals(QObject):
    progress = Signal(int)
    log = Signal(str)
    done = Signal(str)   # "" = 成功, 否则错误文本
    detect_done = Signal(object, str)


class _FlashTask(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self._fn = fn
        self._args = args
        self.signals = _Signals()

    @Slot()
    def run(self):
        try:
            self._fn(*self._args,
                     progress=self.signals.progress.emit,
                     log=self.signals.log.emit)
            self.signals.done.emit("")
        except Exception as exc:  # noqa: BLE001
            self.signals.done.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(640, 720)
        self._pool = QThreadPool.globalInstance()
        self._layout: Layout | None = None
        self._image_path: str | None = None
        self._image_info = None
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 设备区
        dev_box = QGroupBox("1 · 设备")
        dev = QVBoxLayout(dev_box)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(320)
        row1.addWidget(self.port_combo, 1)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_ports)
        row1.addWidget(refresh_btn)
        detect_btn = QPushButton("检测设备与布局")
        detect_btn.clicked.connect(self._detect_device)
        row1.addWidget(detect_btn)
        dev.addLayout(row1)
        self.device_status = QLabel("尚未检测。")
        dev.addWidget(self.device_status)
        root.addWidget(dev_box)

        # 固件区
        fw_box = QGroupBox("2 · 选择固件")
        fw = QVBoxLayout(fw_box)
        row2 = QHBoxLayout()
        self.fw_label = QLabel("未选择文件")
        row2.addWidget(self.fw_label, 1)
        pick_btn = QPushButton("选择 .bin 文件…")
        pick_btn.clicked.connect(self._pick_image)
        row2.addWidget(pick_btn)
        fw.addLayout(row2)
        self.fw_info = QLabel("支持:纯 app 镜像(0xE9)与玩法社区的 esp-merged 合并镜像。")
        fw.addWidget(self.fw_info)
        self.extract_btn = QPushButton("从合并镜像提取 app 镜像")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self._extract_merged)
        fw.addWidget(self.extract_btn)
        root.addWidget(fw_box)

        # 槽位区
        slot_box = QGroupBox("3 · 选择刷入槽位")
        slot = QVBoxLayout(slot_box)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("目标槽位:"))
        self.slot_combo = QComboBox()
        self.slot_combo.setMinimumWidth(320)
        row3.addWidget(self.slot_combo, 1)
        slot.addLayout(row3)
        self.slot_hint = QLabel("请先检测设备布局。")
        slot.addWidget(self.slot_hint)
        root.addWidget(slot_box)

        # 进度与日志
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        root.addWidget(self.progress)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        root.addWidget(self.log_view, 1)

        # 操作按钮
        row4 = QHBoxLayout()
        self.flash_slot_btn = QPushButton("刷入所选槽位（安全,不覆盖切换器）")
        self.flash_slot_btn.setEnabled(False)
        self.flash_slot_btn.clicked.connect(self._flash_selected_slot)
        row4.addWidget(self.flash_slot_btn)
        self.flash_zero_btn = QPushButton("刷入切换器本体（0x0,覆盖全部）")
        self.flash_zero_btn.clicked.connect(self._flash_zero_offset)
        row4.addWidget(self.flash_zero_btn)
        root.addLayout(row4)

        self._refresh_ports()

    # ---------------- helpers ----------------
    def _port(self) -> str:
        return self.port_combo.currentData() or self.port_combo.currentText()

    def _log(self, text: str):
        self.log_view.appendPlainText(text)

    def _refresh_ports(self):
        self.port_combo.clear()
        for device, desc in flash_backend.list_ports():
            self.port_combo.addItem(f"{device} — {desc}", device)
        if self.port_combo.count() == 0:
            self.port_combo.addItem("未发现串口设备")

    # ---------------- device ----------------
    def _detect_device(self):
        port = self._port()
        self.device_status.setText(f"正在检测 {port} …")
        self._layout = None

        def run():
            try:
                layout = flash_backend.detect_device_layout(port, log=self._log)
                self._on_detect_done(layout, "")
            except Exception as exc:  # noqa: BLE001
                self._on_detect_done(None, str(exc))

        class _Task(QRunnable):
            def __init__(self, fn):
                super().__init__()
                self.fn = fn

            def run(self):
                self.fn()

        self._pool.start(_Task(run))

    def _on_detect_done(self, layout, err):
        if err:
            self.device_status.setText(f"检测失败:{err}")
            self._layout = None
            self._rebuild_slots()
            return
        if layout is None:
            self.device_status.setText(
                "未识别为三槽版或双槽版切换器。请先刷入切换器固件,或检查设备。")
            self._layout = None
            self._rebuild_slots()
            return
        self._layout = layout
        self.device_status.setText(
            f"已识别:{layout.name_zh}({layout.name_en}),"
            f"{len(layout.slots)} 个槽位,"
            f"每槽 {layout.slots[0].size / 1024 / 1024:.2f} MB")
        self._rebuild_slots()

    def _rebuild_slots(self):
        self.slot_combo.clear()
        if self._layout is None:
            self.slot_hint.setText("请先检测设备布局。")
            self.flash_slot_btn.setEnabled(False)
            return
        size = self._image_info.size if self._image_info else 0
        any_fit = False
        for slot, fits in slots_for_layout(self._layout, size or 0):
            suffix = "" if fits else "（空间不足）"
            self.slot_combo.addItem(
                f"槽{slot.tag} · 偏移 0x{slot.offset:x} · {slot.size / 1024 / 1024:.2f}MB{suffix}",
                slot,
            )
            any_fit = any_fit or fits
        self.slot_hint.setText(
            "刷写只写所选槽位偏移,不会覆盖切换器与其他槽位。")
        self.flash_slot_btn.setEnabled(any_fit and self._image_info is not None)

    # ---------------- firmware ----------------
    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择固件文件", "",
            "固件镜像 (*.bin);;所有文件 (*)")
        if not path:
            return
        self._set_image(path)

    def _set_image(self, path: str):
        try:
            info = inspect_image(path)
        except ValueError as exc:
            QMessageBox.warning(self, "无法识别", str(exc))
            return
        self._image_path = path
        self._image_info = info
        self.fw_label.setText(os.path.basename(path))
        kind_txt = {"app": "纯 app 镜像", "merged": "esp-merged 合并镜像"}[info.kind]
        self.fw_info.setText(
            f"类型:{kind_txt} · 项目:{info.project} · 版本:{info.version} · "
            f"日期:{info.date} · 大小:{info.size / 1024 / 1024:.2f} MB"
            + (" · 需先提取 app 镜像" if info.kind == "merged" else ""))
        self.extract_btn.setEnabled(info.kind == "merged")
        self._rebuild_slots()

    def _extract_merged(self):
        if not self._image_path:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "保存提取的 app 镜像",
            os.path.splitext(self._image_path)[0] + "-app.bin",
            "固件镜像 (*.bin)")
        if not out:
            return
        try:
            info = extract_app_image(self._image_path, out)
        except ValueError as exc:
            QMessageBox.warning(self, "提取失败", str(exc))
            return
        self._set_image(out)
        QMessageBox.information(
            self, "提取完成",
            f"已提取 app 镜像({info.size / 1024 / 1024:.2f} MB):\n{out}")

    # ---------------- flashing ----------------
    def _flash_selected_slot(self):
        if self._layout is None or self._image_info is None:
            return
        slot = self.slot_combo.currentData()
        if slot is None:
            QMessageBox.warning(self, "请先选择槽位", "请先检测设备并选择槽位。")
            return
        if self._image_info.size > slot.size:
            QMessageBox.warning(
                self, "空间不足",
                f"固件 {self._image_info.size / 1024 / 1024:.2f} MB 超过"
                f"槽{slot.tag} 上限 {slot.size / 1024 / 1024:.2f} MB。")
            return
        confirm = QMessageBox.question(
            self, "确认刷写",
            f"将把 {os.path.basename(self._image_path)}\n"
            f"刷入 槽{slot.tag}(偏移 0x{slot.offset:x})。\n"
            "此操作只写该槽位,不影响切换器本体。继续？")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._run_flash(
            flash_backend.flash_slot,
            self._port(), slot.offset, self._image_path,
            done_text=f"槽{slot.tag} 刷写完成并校验通过。")

    def _flash_zero_offset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择切换器合并镜像(0x0)", "",
            "固件镜像 (*.bin);;所有文件 (*)")
        if not path:
            return
        confirm = QMessageBox.warning(
            self, "整片刷写警告", ZERO_OFFSET_WARNING,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._run_flash(
            flash_backend.flash_switcher, self._port(), path,
            done_text="切换器已整片刷入并校验通过。")

    def _run_flash(self, fn, *args, done_text=""):
        self.progress.setValue(0)
        self.flash_slot_btn.setEnabled(False)
        self.flash_zero_btn.setEnabled(False)

        task = _FlashTask(fn, *args)
        task.signals.progress.connect(self.progress.setValue)
        task.signals.log.connect(self._log)
        task.signals.done.connect(
            lambda err: self._on_flash_done(err, done_text))
        self._pool.start(task)

    def _on_flash_done(self, err: str, done_text: str):
        self.flash_zero_btn.setEnabled(True)
        self._rebuild_slots()
        if err:
            self.progress.setValue(0)
            QMessageBox.critical(self, "刷写失败", err)
        else:
            self.progress.setValue(100)
            QMessageBox.information(self, "完成", done_text)


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

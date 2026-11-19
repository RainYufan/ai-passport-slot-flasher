#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_play_gui.py —— 图形界面:粘贴玩法链接(或拖入/选择本地合并镜像),一键提取 app 镜像。"""

import os
import sys

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import extract_play


class _Signals(QObject):
    log = Signal(str)
    done = Signal(str, str)  # (merged_path, app_path) 或 ("", 错误文本)


class _Worker(QRunnable):
    def __init__(self, target: str):
        super().__init__()
        self._target = target
        self.signals = _Signals()

    def _emit(self, text: str):
        self.signals.log.emit(text)

    @Slot()
    def run(self):
        target = self._target
        try:
            if target.lower().endswith(".bin") and os.path.isfile(target):
                self._local(target)
            else:
                merged, app = extract_play.process_play(target, log=self._emit)
                self.signals.done.emit(merged, app)
        except Exception as exc:  # noqa: BLE001
            self.signals.done.emit("", str(exc))

    def _local(self, path: str):
        with open(path, "rb") as f:
            data = f.read()
        parts = extract_play.parse_partition_table(data[0x8000:0x9000])
        apps = [p for p in parts if p[1] == extract_play.PART_TYPE_APP]
        if not apps:
            raise RuntimeError("该文件里没有 app 分区(不是合并镜像)。")
        offset = apps[0][3]
        app = data[offset:]
        base = os.path.splitext(os.path.basename(path))[0]
        out_dir = os.path.dirname(os.path.abspath(path))
        app_path = os.path.join(out_dir, base + "-app.bin")
        with open(app_path, "wb") as f:
            f.write(app)
        self._emit(f"app 镜像: {app_path} ({len(app)} 字节, {len(app)/1024/1024:.2f} MB)")
        self.signals.done.emit(os.path.abspath(path), os.path.abspath(app_path))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Passport 玩法固件提取器")
        self.resize(640, 480)
        self.setAcceptDrops(True)
        self._pool = QThreadPool.globalInstance()
        self._out_dir = os.getcwd()
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        root.addWidget(QLabel("粘贴玩法链接,或拖入/选择本地的 esp-merged 合并镜像:"))

        row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://ai-passport.folotoy.cn/plays/2378/")
        row.addWidget(self.url_edit, 1)
        pick = QPushButton("选择本地文件…")
        pick.clicked.connect(self._pick_file)
        row.addWidget(pick)
        root.addLayout(row)

        self.extract_btn = QPushButton("提取 app 镜像")
        self.extract_btn.clicked.connect(self._extract)
        root.addWidget(self.extract_btn)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo", 11))
        root.addWidget(self.log_view, 1)

        self.open_btn = QPushButton("打开输出文件夹")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_dir)
        root.addWidget(self.open_btn)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".bin"):
                self.url_edit.setText(path)
                self._extract()
                return

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择合并镜像", "", "固件镜像 (*.bin);;所有文件 (*)")
        if path:
            self.url_edit.setText(path)
            self._extract()

    def _extract(self):
        target = self.url_edit.text().strip()
        if not target:
            QMessageBox.warning(self, "提示", "请先粘贴链接或选择本地文件。")
            return
        self._log("开始处理…")
        self.extract_btn.setEnabled(False)
        self.open_btn.setEnabled(False)

        worker = _Worker(target)
        worker.signals.log.connect(self._log)
        worker.signals.done.connect(self._on_done)
        self._pool.start(worker)

    def _log(self, text: str):
        self.log_view.appendPlainText(text)

    def _on_done(self, merged: str, app: str):
        self.extract_btn.setEnabled(True)
        if not app:
            self._log("失败:" + (merged or app))
            QMessageBox.critical(self, "提取失败", merged or app)
            return
        self._log("完成!")
        self._log("app 镜像:" + app)
        if os.path.dirname(app):
            self._out_dir = os.path.dirname(app)
        self.open_btn.setEnabled(True)
        QMessageBox.information(
            self, "完成",
            f"已提取 app 镜像:\n{app}\n\n可直接拖进「AI Passport 槽位刷写助手」刷入槽位。")

    def _open_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._out_dir))


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("PingFang SC", 13))
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

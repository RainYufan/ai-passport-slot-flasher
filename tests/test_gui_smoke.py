#!/usr/bin/env python3
"""GUI 离屏冒烟测试:窗口能构建、控件齐全、布局检测状态流转正确。需 PySide6。"""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PySide6.QtWidgets import QApplication  # noqa: E402

from ai_passport_flasher import gui  # noqa: E402
from ai_passport_flasher.model import LAYOUT_THREE_SLOT  # noqa: E402


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_window_builds(self):
        win = gui.MainWindow()
        win.show()
        self.app.processEvents()
        self.assertEqual(win.windowTitle(), gui.APP_TITLE)
        self.assertGreaterEqual(win.port_combo.count(), 1)
        self.assertFalse(win.flash_slot_btn.isEnabled())  # 未检测布局前不可刷
        win.close()

    def test_detect_done_populates_slots(self):
        win = gui.MainWindow()
        win._on_detect_done(LAYOUT_THREE_SLOT, "")
        self.assertEqual(win.slot_combo.count(), 3)
        self.assertIn("三槽版", win.device_status.text())
        win.close()

    def test_detect_unknown_layout(self):
        win = gui.MainWindow()
        win._on_detect_done(None, "")
        self.assertEqual(win.slot_combo.count(), 0)
        self.assertFalse(win.flash_slot_btn.isEnabled())
        win.close()

    def test_detect_error(self):
        win = gui.MainWindow()
        win._on_detect_done(None, "连接超时")
        self.assertIn("连接超时", win.device_status.text())
        win.close()


if __name__ == "__main__":
    unittest.main(verbosity=1)

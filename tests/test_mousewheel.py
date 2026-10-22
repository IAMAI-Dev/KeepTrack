"""使用真实 Tk 控件验证滚轮分发，不启动后台同步或写入用户设置。"""

import tkinter as tk
import unittest
from tkinter import ttk

from main import FITGeneratorGUI


class TestMousewheel(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.root.geometry("400x250+10000+10000")
        self.gui = FITGeneratorGUI.__new__(FITGeneratorGUI)
        self.gui.root = self.root
        frame = self.gui._build_scroll_container()
        self.combo = ttk.Combobox(frame, values=[str(i) for i in range(40)])
        self.combo.pack()
        self.combo.current(0)
        self.text = tk.Text(frame, height=3)
        self.text.insert("1.0", "line\n" * 100)
        self.text.pack()
        self.body = tk.Frame(frame, height=1500, width=200)
        self.body.pack()
        self.root.update()
        self.gui.canvas.yview_moveto(0)
        self.root.update()
        self.addCleanup(self.close_popup)

    def close_popup(self):
        self.root.tk.call("ttk::combobox::Unpost", self.combo)

    def test_page_wheel_scrolls_page(self):
        before = self.gui.canvas.yview()
        self.body.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(self.gui.canvas.yview()[0], before[0])

    def test_closed_combo_wheel_does_not_scroll_page(self):
        before = self.gui.canvas.yview()
        self.combo.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertEqual(self.gui.canvas.yview(), before)

    def test_open_dropdown_scrolls_list_without_moving_page(self):
        self.root.tk.call("ttk::combobox::Post", self.combo)
        self.root.update()
        popup = str(self.combo) + ".popdown.f.l"
        before_page = self.gui.canvas.yview()
        before_list = self.root.tk.call(popup, "yview")
        self.root.tk.call("event", "generate", popup, "<MouseWheel>",
                          "-delta", -120)
        self.root.update()
        self.assertEqual(self.gui.canvas.yview(), before_page)
        self.assertNotEqual(self.root.tk.call(popup, "yview"), before_list)
        self.close_popup()
        self.body.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(self.gui.canvas.yview()[0], before_page[0])

    def test_log_wheel_scrolls_log_without_moving_page(self):
        before_page = self.gui.canvas.yview()
        before_text = self.text.yview()
        self.text.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertEqual(self.gui.canvas.yview(), before_page)
        self.assertGreater(self.text.yview()[0], before_text[0])


if __name__ == "__main__":
    unittest.main()

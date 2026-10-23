"""使用真实 Tk 控件验证任务编辑精度和批量参数来源。"""

import tkinter as tk
import unittest
from contextlib import ExitStack
from datetime import date
from unittest.mock import patch

from main import FITGeneratorGUI


class TestCalendarTaskEditing(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        with ExitStack() as patches:
            patches.enter_context(
                patch("main.PlaygroundRepository.load", return_value=[])
            )
            patches.enter_context(
                patch("main.get_default_playground", return_value=None)
            )
            patches.enter_context(patch("main.threading.Thread.start"))
            self.gui = FITGeneratorGUI(self.root)
        self.gui.run_distance.set("5.123456789")
        self.gui.run_duration.set("30.123456789")
        self.gui.run_time.set("08:00")
        self.gui.batch_mode.set("calendar")
        self.gui._update_batch_mode_visibility()
        self.first_date = date(2026, 10, 23)
        self.second_date = date(2026, 10, 24)

    def select_task(self, selected_date):
        self.gui.task_tree.selection_set(selected_date.isoformat())
        self.root.update()

    def test_save_unchanged_task_preserves_numeric_precision(self):
        self.gui._toggle_calendar_date(self.first_date)
        self.select_task(self.first_date)
        before = self.gui._build_calendar_tasks()[0]

        self.gui._save_current_task_edit()

        self.assertEqual(self.gui._build_calendar_tasks()[0], before)

    def test_clear_tasks_clears_editor_and_blocks_stale_batch_apply(self):
        self.gui._toggle_calendar_date(self.first_date)
        self.select_task(self.first_date)
        self.gui.task_edit_distance.set("10")
        self.gui._save_current_task_edit()
        self.gui._clear_calendar_tasks()
        self.gui._toggle_calendar_date(self.second_date)
        self.root.update()
        before = self.gui._build_calendar_tasks()

        self.assertIsNone(self.gui._editing_task_date)
        for field in (
            self.gui.task_edit_time,
            self.gui.task_edit_distance,
            self.gui.task_edit_duration,
            self.gui.task_edit_playground,
            self.gui.task_edit_lat,
            self.gui.task_edit_lon,
            self.gui.task_edit_angle,
        ):
            self.assertEqual(field.get(), "")
        with patch("main.messagebox.showwarning") as warning:
            self.gui._apply_task_edit_to_all()
        warning.assert_called_once()
        self.assertEqual(self.gui._build_calendar_tasks(), before)
        self.assertEqual(self.gui._calendar_task_overrides, {})

    def test_batch_apply_from_selected_source_preserves_coordinates(self):
        self.gui._toggle_calendar_date(self.first_date)
        self.gui._toggle_calendar_date(self.second_date)
        self.select_task(self.first_date)
        before = self.gui._build_calendar_tasks()
        self.gui.task_edit_distance.set("10")

        self.gui._apply_task_edit_to_all()

        after = self.gui._build_calendar_tasks()
        self.assertEqual([task.distance_km for task in after], [10, 10])
        for original, edited in zip(before, after):
            self.assertEqual(edited.latitude, original.latitude)
            self.assertEqual(edited.longitude, original.longitude)
            self.assertEqual(edited.duration_min, original.duration_min)


if __name__ == "__main__":
    unittest.main()

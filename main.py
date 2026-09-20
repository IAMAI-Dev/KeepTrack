import calendar
import ctypes
import math
import os
import random
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox, ttk
from typing import List

from playground_repository import (
    PlaygroundRepository,
    format_playground_label,
)
from preferences import (
    get_default_playground,
    set_default_playground,
)

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import (
    Event,
    EventType,
    FileType,
    Manufacturer,
    Sport,
    SubSport,
)

VERSION = "1.1.0"
TRACK_STRAIGHT_LENGTH = 85.0
TRACK_CURVE_RADIUS = 36.5
MAX_TRACK_WIDTH = 8.0
EARTH_METERS_PER_DEGREE = 111000.0


@dataclass
class GenerationTask:
    """Single FIT file generation task."""

    index: int
    start_time: datetime
    distance_km: float
    duration_min: float
    latitude: float
    longitude: float
    playground_angle: float
    playground_label: str = ""

    @property
    def end_time(self):
        return self.start_time + timedelta(minutes=self.duration_min)


class FITGeneratorGUI:
    """KeepTrack 的 Tkinter 界面和 FIT 数据生成入口。"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"KeepTrack v{VERSION}")
        self.root.geometry("720x950")
        self.root.minsize(800, 1000)

        now = datetime.now()
        self.run_distance = tk.StringVar(value="0.00")
        self.run_duration = tk.StringVar(value="0")
        self.file_count = tk.StringVar(value="1")
        self.time_interval = tk.StringVar(value="24")
        self.batch_mode = tk.StringVar(value="interval")
        self.run_date = tk.StringVar(
            value=now.strftime("%Y-%m-%d"),
        )
        self.run_time = tk.StringVar(
            value=now.strftime("%H:%M"),
        )
        self._calendar_month = date(now.year, now.month, 1)
        self._selected_dates = set()
        self._calendar_task_overrides = {}
        self._calendar_tasks_by_date = {}
        self._calendar_buttons = []
        self._editing_task_date = None
        self.task_edit_status = tk.StringVar(value="未选择任务")
        self.task_edit_time = tk.StringVar(value=now.strftime("%H:%M"))
        self.task_edit_distance = tk.StringVar(value="0.00")
        self.task_edit_duration = tk.StringVar(value="0")
        self.task_edit_playground = tk.StringVar(value="")
        self.task_edit_lat = tk.StringVar(value="30.5800521")
        self.task_edit_lon = tk.StringVar(value="114.3307788")
        self.task_edit_angle = tk.StringVar(value="62.5")
        self.apply_time = tk.BooleanVar(value=True)
        self.apply_distance = tk.BooleanVar(value=True)
        self.apply_duration = tk.BooleanVar(value=True)
        self.apply_playground = tk.BooleanVar(value=True)

        # 默认位置为湖北大学（武昌校区）一号操场。
        self.playground_lat = tk.StringVar(
            value="30.5800521",
        )
        self.playground_lon = tk.StringVar(
            value="114.3307788",
        )
        self.playground_angle = tk.StringVar(value="62.5")

        self.file_output = tk.StringVar(
            value=os.path.join(
                os.path.expanduser("~"),
                "Desktop",
                "Keep运动数据",
            )
        )

        # 操场数据仓库和操场列表。
        self._repo = PlaygroundRepository()
        self._playgrounds = self._repo.load()
        self._playground_labels = [
            format_playground_label(pg)
            for pg in self._playgrounds
        ]

        self._setup_styles()
        self._build_ui()
        self._apply_default_playground()

        # 启动时在后台静默刷新操场数据。
        threading.Thread(
            target=self._auto_refresh_on_startup,
            daemon=True,
        ).start()

    """UI 辅助方法"""

    def _ui(self, fn, *args, **kwargs):
        # 在主线程中执行 UI 更新，避免 Tkinter 线程安全问题。
        self.root.after(0, lambda: fn(*args, **kwargs))

    def _set_progress(self, value: float):
        self.progress["value"] = max(0, min(100, value))

    def _set_button(self, enabled: bool, text: str):
        self.generate_btn.config(
            state=("normal" if enabled else "disabled"),
            text=text,
        )

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)

    """界面布局构建"""

    def _setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TLabelFrame", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TLabelFrame.Label", foreground="green")
        style.configure("TButton", font=("Microsoft YaHei UI", 10))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_ui(self):
        self._build_title()
        main_frame = self._build_scroll_container()
        self._build_basic_frame(main_frame)
        self._build_time_frame(main_frame)
        self._build_calendar_task_frame(main_frame)
        self._build_output_frame(main_frame)
        self._build_generation_area(main_frame)

        self._update_pace()
        self._update_batch_mode_visibility()
        for task_input in (
            self.run_distance,
            self.run_duration,
            self.run_time,
            self.playground_lat,
            self.playground_lon,
            self.playground_angle,
        ):
            task_input.trace_add(
                "write",
                self._refresh_calendar_tasks_if_visible,
            )

    def _build_title(self):
        title_frame = tk.Frame(self.root, bg="green", height=120)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)

        tk.Label(
            title_frame,
            text=f"KeepTrack v{VERSION}",
            font=("Microsoft YaHei UI", 22, "bold"),
            bg="green",
            fg="white",
        ).pack(pady=(10, 5))

        tk.Label(
            title_frame,
            text="仅供学习交流喵~",
            font=("Microsoft YaHei UI", 10),
            bg="green",
            fg="white",
        ).pack()

    def _build_scroll_container(self):
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            main_container,
            orient="vertical",
            command=self.canvas.yview,
        )
        self.scrollable_frame = tk.Frame(self.canvas)

        canvas_window = self.canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw",
        )
        self.scrollable_frame.bind(
            "<Configure>",
            lambda event: self.canvas.configure(
                scrollregion=self.canvas.bbox("all"),
            ),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfig(
                canvas_window,
                width=event.width,
            ),
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_frame = tk.Frame(self.scrollable_frame, padx=35, pady=25)
        main_frame.pack(fill=tk.BOTH, expand=True)
        return main_frame

    def _build_basic_frame(self, main_frame):
        basic_frame = ttk.LabelFrame(
            main_frame,
            text="基础数据",
            padding=(20, 15),
        )
        basic_frame.pack(fill=tk.X, pady=(0, 20))
        basic_frame.columnconfigure(1, weight=1)

        ttk.Label(
            basic_frame,
            text="距离 (km):",
        ).grid(row=0, column=0, sticky=tk.W, pady=12)
        ttk.Entry(
            basic_frame,
            textvariable=self.run_distance,
        ).grid(row=0, column=1, sticky="ew", padx=15)

        ttk.Label(
            basic_frame,
            text="时长 (min):",
        ).grid(row=1, column=0, sticky=tk.W, pady=12)
        ttk.Entry(
            basic_frame,
            textvariable=self.run_duration,
        ).grid(row=1, column=1, sticky="ew", padx=15)

        self.pace_label = ttk.Label(
            basic_frame,
            text="配速: --'--\"/km",
            foreground="green",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.pace_label.grid(row=1, column=2, sticky=tk.W)

        self.run_distance.trace_add("write", self._update_pace)
        self.run_duration.trace_add("write", self._update_pace)

        ttk.Label(
            basic_frame,
            text="批量模式:",
        ).grid(row=2, column=0, sticky=tk.W, pady=12)
        mode_box = tk.Frame(basic_frame)
        mode_box.grid(row=2, column=1, sticky="w", padx=15)
        ttk.Radiobutton(
            mode_box,
            text="固定间隔",
            variable=self.batch_mode,
            value="interval",
            command=self._update_batch_mode_visibility,
        ).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Radiobutton(
            mode_box,
            text="日历选择",
            variable=self.batch_mode,
            value="calendar",
            command=self._update_batch_mode_visibility,
        ).pack(side=tk.LEFT)

        self.file_count_label = ttk.Label(
            basic_frame,
            text="生成份数:",
        )
        self.file_count_label.grid(row=3, column=0, sticky=tk.W, pady=12)
        self.file_count_entry = ttk.Entry(
            basic_frame,
            textvariable=self.file_count,
        )
        self.file_count_entry.grid(row=3, column=1, sticky="ew", padx=15)
        self.file_count.trace_add("write", self._update_interval_visibility)

        self.interval_label = ttk.Label(
            basic_frame,
            text="每次间隔(小时):",
        )
        self.interval_entry = ttk.Entry(
            basic_frame,
            textvariable=self.time_interval,
        )

    def _build_time_frame(self, main_frame):
        time_frame = ttk.LabelFrame(
            main_frame,
            text="时间与位置",
            padding=(20, 15),
        )
        time_frame.pack(fill=tk.X, pady=(0, 20))
        time_frame.columnconfigure(1, weight=1)

        # 操场选择下拉菜单。
        ttk.Label(
            time_frame,
            text="操场选择:",
        ).grid(row=0, column=0, sticky=tk.W, pady=12)

        self.playground_combo = ttk.Combobox(
            time_frame,
            values=self._playground_labels,
            state="normal",
        )
        self.playground_combo.grid(
            row=0, column=1, sticky="ew", padx=15,
        )
        self.playground_combo.set("搜索或选择操场...")
        self.playground_combo.bind(
            "<<ComboboxSelected>>",
            self._on_playground_selected,
        )
        self.playground_combo.bind(
            "<KeyRelease>",
            self._filter_playgrounds,
        )

        # 操场操作按钮行。
        btn_box = tk.Frame(time_frame)
        btn_box.grid(
            row=1, column=1, sticky="w", padx=15, pady=(0, 5),
        )
        self._refresh_btn = ttk.Button(
            btn_box,
            text="刷新数据",
            width=10,
            command=self._refresh_playground_data,
        )
        self._refresh_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            btn_box,
            text="设为默认",
            width=10,
            command=self._set_default_playground,
        ).pack(side=tk.LEFT)

        self._refresh_status = ttk.Label(
            time_frame,
            text="",
            foreground="gray",
            font=("Microsoft YaHei UI", 8),
        )
        self._refresh_status.grid(
            row=1, column=0, sticky=tk.E, padx=(0, 5),
        )

        # 开始时间。
        ttk.Label(
            time_frame,
            text="开始时间:",
        ).grid(row=2, column=0, sticky=tk.W, pady=12)
        date_box = tk.Frame(time_frame)
        date_box.grid(
            row=2, column=1, sticky="ew", padx=15,
        )
        ttk.Entry(
            date_box,
            textvariable=self.run_date,
            width=14,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(date_box, text=" ").pack(side=tk.LEFT)
        ttk.Entry(
            date_box,
            textvariable=self.run_time,
            width=10,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 经纬度。
        ttk.Label(
            time_frame,
            text="纬度 / 经度:",
        ).grid(row=3, column=0, sticky=tk.W, pady=12)
        geo_box = tk.Frame(time_frame)
        geo_box.grid(
            row=3, column=1, sticky="ew", padx=15,
        )
        ttk.Entry(
            geo_box,
            textvariable=self.playground_lat,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(geo_box, text=" / ").pack(side=tk.LEFT)
        ttk.Entry(
            geo_box,
            textvariable=self.playground_lon,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 跑道方位角。
        ttk.Label(
            time_frame,
            text="跑道方位角:",
        ).grid(row=4, column=0, sticky=tk.W, pady=12)
        ttk.Entry(
            time_frame,
            textvariable=self.playground_angle,
        ).grid(row=4, column=1, sticky="ew", padx=15)
        ttk.Label(
            time_frame,
            text="单位：°",
            foreground="green",
            font=("Microsoft YaHei UI", 9),
        ).grid(row=4, column=2)

    def _build_calendar_task_frame(self, main_frame):
        self.calendar_task_frame = ttk.LabelFrame(
            main_frame,
            text="日历任务",
            padding=(20, 15),
        )
        self.calendar_task_frame.columnconfigure(0, weight=1)
        self.calendar_task_frame.rowconfigure(1, weight=1)

        calendar_box = tk.Frame(self.calendar_task_frame)
        calendar_box.grid(row=0, column=0, sticky="w")

        nav_box = tk.Frame(calendar_box)
        nav_box.grid(row=0, column=0, columnspan=7, sticky="ew")
        ttk.Button(
            nav_box,
            text="<",
            width=3,
            command=lambda: self._change_calendar_month(-1),
        ).pack(side=tk.LEFT)
        self.calendar_month_label = ttk.Label(
            nav_box,
            anchor="center",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.calendar_month_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            nav_box,
            text=">",
            width=3,
            command=lambda: self._change_calendar_month(1),
        ).pack(side=tk.LEFT)

        week_names = ("一", "二", "三", "四", "五", "六", "日")
        for col, week_name in enumerate(week_names):
            ttk.Label(
                calendar_box,
                text=week_name,
                anchor="center",
            ).grid(row=1, column=col, sticky="ew", pady=(8, 4))

        self._calendar_buttons = []
        for row in range(6):
            button_row = []
            for col in range(7):
                button = tk.Button(
                    calendar_box,
                    width=4,
                    relief=tk.FLAT,
                    font=("Microsoft YaHei UI", 9),
                    cursor="hand2",
                )
                button.grid(row=row + 2, column=col, padx=2, pady=2)
                button_row.append(button)
            self._calendar_buttons.append(button_row)

        task_box = tk.Frame(self.calendar_task_frame)
        task_box.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        task_box.columnconfigure(0, weight=1)
        task_box.rowconfigure(0, weight=1)

        columns = ("index", "start", "distance", "duration", "playground")
        self.task_tree = ttk.Treeview(
            task_box,
            columns=columns,
            show="headings",
            height=8,
            selectmode="extended",
        )
        self.task_tree.bind(
            "<<TreeviewSelect>>",
            self._on_task_tree_selected,
        )
        headings = {
            "index": ("#", 48),
            "start": ("开始时间", 170),
            "distance": ("距离(km)", 80),
            "duration": ("时长(min)", 82),
            "playground": ("操场", 220),
        }
        for column, (text, width) in headings.items():
            self.task_tree.heading(column, text=text)
            self.task_tree.column(column, width=width, minwidth=50)

        task_scrollbar = ttk.Scrollbar(
            task_box,
            orient="vertical",
            command=self.task_tree.yview,
        )
        self.task_tree.configure(yscrollcommand=task_scrollbar.set)
        self.task_tree.grid(row=0, column=0, sticky="nsew")
        task_scrollbar.grid(row=0, column=1, sticky="ns")

        task_btn_box = tk.Frame(task_box)
        task_btn_box.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )
        ttk.Button(
            task_btn_box,
            text="删除选中",
            command=self._remove_selected_calendar_tasks,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            task_btn_box,
            text="清空任务",
            command=self._clear_calendar_tasks,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            task_btn_box,
            text="刷新预览",
            command=lambda: self._refresh_calendar_tasks(show_error=True),
        ).pack(side=tk.LEFT)

        self._build_task_edit_panel(task_box)

        self.calendar_task_status = ttk.Label(
            task_box,
            text="",
            foreground="gray",
        )
        self.calendar_task_status.grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )
        self._render_calendar()

    def _build_task_edit_panel(self, task_box):
        edit_frame = ttk.LabelFrame(
            task_box,
            text="任务编辑",
            padding=(12, 10),
        )
        edit_frame.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(10, 0),
        )
        edit_frame.columnconfigure(1, weight=1)
        edit_frame.columnconfigure(3, weight=1)
        edit_frame.columnconfigure(5, weight=1)

        ttk.Label(
            edit_frame,
            textvariable=self.task_edit_status,
            foreground="green",
            font=("Microsoft YaHei UI", 9, "bold"),
        ).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        ttk.Label(edit_frame, text="开始时间:").grid(
            row=1, column=0, sticky=tk.W, pady=5,
        )
        ttk.Entry(
            edit_frame,
            textvariable=self.task_edit_time,
            width=10,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 16))

        ttk.Label(edit_frame, text="距离(km):").grid(
            row=1, column=2, sticky=tk.W, pady=5,
        )
        ttk.Entry(
            edit_frame,
            textvariable=self.task_edit_distance,
            width=10,
        ).grid(row=1, column=3, sticky="ew", padx=(8, 16))

        ttk.Label(edit_frame, text="时长(min):").grid(
            row=1, column=4, sticky=tk.W, pady=5,
        )
        ttk.Entry(
            edit_frame,
            textvariable=self.task_edit_duration,
            width=10,
        ).grid(row=1, column=5, sticky="ew", padx=(8, 0))

        ttk.Label(edit_frame, text="操场:").grid(
            row=2, column=0, sticky=tk.W, pady=5,
        )
        self.task_edit_playground_combo = ttk.Combobox(
            edit_frame,
            textvariable=self.task_edit_playground,
            values=self._playground_labels,
            state="normal",
        )
        self.task_edit_playground_combo.grid(
            row=2,
            column=1,
            columnspan=5,
            sticky="ew",
            padx=(8, 0),
        )
        self.task_edit_playground_combo.bind(
            "<<ComboboxSelected>>",
            self._on_task_edit_playground_selected,
        )

        ttk.Label(edit_frame, text="纬度:").grid(
            row=3, column=0, sticky=tk.W, pady=5,
        )
        ttk.Entry(
            edit_frame,
            textvariable=self.task_edit_lat,
            width=12,
        ).grid(row=3, column=1, sticky="ew", padx=(8, 16))

        ttk.Label(edit_frame, text="经度:").grid(
            row=3, column=2, sticky=tk.W, pady=5,
        )
        ttk.Entry(
            edit_frame,
            textvariable=self.task_edit_lon,
            width=12,
        ).grid(row=3, column=3, sticky="ew", padx=(8, 16))

        ttk.Label(edit_frame, text="方位角:").grid(
            row=3, column=4, sticky=tk.W, pady=5,
        )
        ttk.Entry(
            edit_frame,
            textvariable=self.task_edit_angle,
            width=10,
        ).grid(row=3, column=5, sticky="ew", padx=(8, 0))

        field_box = tk.Frame(edit_frame)
        field_box.grid(row=4, column=0, columnspan=6, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            field_box,
            text="时间",
            variable=self.apply_time,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            field_box,
            text="距离",
            variable=self.apply_distance,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            field_box,
            text="时长",
            variable=self.apply_duration,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            field_box,
            text="操场",
            variable=self.apply_playground,
        ).pack(side=tk.LEFT)

        button_box = tk.Frame(edit_frame)
        button_box.grid(
            row=5,
            column=0,
            columnspan=6,
            sticky="w",
            pady=(10, 0),
        )
        ttk.Button(
            button_box,
            text="保存当前任务",
            command=self._save_current_task_edit,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            button_box,
            text="应用到选中任务",
            command=self._apply_task_edit_to_selected,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            button_box,
            text="应用到全部任务",
            command=self._apply_task_edit_to_all,
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            button_box,
            text="重置当前任务",
            command=self._reset_current_task_edit,
        ).pack(side=tk.LEFT)

    def _build_output_frame(self, main_frame):
        self.output_frame = ttk.LabelFrame(
            main_frame,
            text="输出",
            padding=(20, 15),
        )
        self.output_frame.pack(fill=tk.X, pady=(0, 20))
        self.output_frame.columnconfigure(0, weight=1)

        ttk.Entry(
            self.output_frame,
            textvariable=self.file_output,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(
            self.output_frame,
            text="浏览",
            width=8,
            command=self._choose_output,
        ).grid(row=0, column=1)

    def _build_generation_area(self, main_frame):
        self.generate_btn = tk.Button(
            main_frame,
            text="生成 FIT 运动数据",
            command=self.start_generation,
            bg="green",
            fg="white",
            font=("Microsoft YaHei UI", 14, "bold"),
            relief=tk.FLAT,
            height=2,
            cursor="hand2",
        )
        self.generate_btn.pack(fill=tk.X, pady=12)

        self.progress = ttk.Progressbar(main_frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(15, 5))

        log_frame = ttk.LabelFrame(
            main_frame,
            text=" 日志 ",
            padding=(10, 10),
        )
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            log_frame,
            height=8,
            font=("Consolas", 10),
            bg="white",
            spacing1=5,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    """回调函数"""

    def _update_batch_mode_visibility(self):
        if self.batch_mode.get() == "calendar":
            self.file_count_label.grid_remove()
            self.file_count_entry.grid_remove()
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()
            self.calendar_task_frame.pack(
                fill=tk.X,
                pady=(0, 20),
                before=self.output_frame,
            )
            self._refresh_calendar_tasks()
            return

        self.calendar_task_frame.pack_forget()
        self.file_count_label.grid(
            row=3, column=0, sticky=tk.W, pady=12,
        )
        self.file_count_entry.grid(
            row=3, column=1, sticky="ew", padx=15,
        )
        self._update_interval_visibility()

    def _update_interval_visibility(self, *_):
        if self.batch_mode.get() != "interval":
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()
            return

        try:
            count = int(self.file_count.get() or 0)
        except ValueError:
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()
            return

        if count > 1:
            self.interval_label.grid(
                row=4, column=0, sticky=tk.W, pady=12,
            )
            self.interval_entry.grid(
                row=4, column=1, sticky="ew", padx=15,
            )
        else:
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()

    def _update_pace(self, *_):
        try:
            distance_km = float(
                self.run_distance.get() or 0
            )
            duration_min = float(
                self.run_duration.get() or 0
            )
        except ValueError:
            self.pace_label.config(
                text="配速: --'--\"/km",
            )
            return

        if distance_km <= 0 or duration_min <= 0:
            self.pace_label.config(
                text="配速: --'--\"/km",
            )
            return

        pace = (duration_min * 60) / distance_km
        pace_text = (
            f"配速: {int(pace // 60)}'"
            f"{int(pace % 60):02d}\"/km"
        )
        self.pace_label.config(text=pace_text)

    def _choose_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.file_output.set(folder)

    """日历任务相关回调"""

    def _change_calendar_month(self, delta_months: int):
        month_index = (
            self._calendar_month.year * 12
            + self._calendar_month.month
            - 1
            + delta_months
        )
        year = month_index // 12
        month = month_index % 12 + 1
        self._calendar_month = date(year, month, 1)
        self._render_calendar()

    def _render_calendar(self):
        self.calendar_month_label.config(
            text=self._calendar_month.strftime("%Y-%m"),
        )
        month_days = list(
            calendar.Calendar(firstweekday=0).itermonthdates(
                self._calendar_month.year,
                self._calendar_month.month,
            )
        )
        while len(month_days) < 42:
            month_days.append(month_days[-1] + timedelta(days=1))

        for index, current_date in enumerate(month_days[:42]):
            row = index // 7
            col = index % 7
            button = self._calendar_buttons[row][col]
            is_current_month = (
                current_date.month == self._calendar_month.month
            )
            is_selected = current_date in self._selected_dates

            if is_selected:
                bg = "green"
                fg = "white"
            elif is_current_month:
                bg = "white"
                fg = "black"
            else:
                bg = "#eeeeee"
                fg = "#999999"

            button.config(
                text=str(current_date.day),
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                state=("normal" if is_current_month else "disabled"),
                command=lambda selected=current_date: (
                    self._toggle_calendar_date(selected)
                ),
            )

    def _toggle_calendar_date(self, selected_date: date):
        if selected_date in self._selected_dates:
            self._selected_dates.remove(selected_date)
            self._calendar_task_overrides.pop(selected_date, None)
        else:
            self._selected_dates.add(selected_date)

        self._render_calendar()
        self._refresh_calendar_tasks()

    def _refresh_calendar_tasks(self, show_error=False):
        previous_selection = set(self.task_tree.selection())
        try:
            tasks = self._build_calendar_tasks()
            self._validate_tasks(tasks)
        except ValueError as error:
            if self._selected_dates and show_error:
                messagebox.showerror("输入错误", str(error))
            selected_count = len(self._selected_dates)
            if selected_count == 0:
                for item_id in self.task_tree.get_children():
                    self.task_tree.delete(item_id)
                self._calendar_tasks_by_date = {}
                self._clear_task_editor()
                self.calendar_task_status.config(
                    text="已选择 0 个日期，暂无可预览任务",
                    foreground="gray",
                )
                return

            has_preview = bool(self.task_tree.get_children())
            if has_preview:
                status_text = f"输入无效，已保留上次预览: {error}"
            else:
                status_text = (
                    f"已选择 {selected_count} 个日期，暂无可预览任务: "
                    f"{error}"
                )
            self.calendar_task_status.config(
                text=status_text,
                foreground="red",
            )
            return

        for item_id in self.task_tree.get_children():
            self.task_tree.delete(item_id)

        self._calendar_tasks_by_date = {
            task.start_time.date(): task
            for task in tasks
        }
        for position, task in enumerate(tasks, start=1):
            item_id = task.start_time.date().isoformat()
            self.task_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    position,
                    task.start_time.strftime("%Y-%m-%d %H:%M"),
                    f"{task.distance_km:g}",
                    f"{task.duration_min:g}",
                    task.playground_label or "手动坐标",
                ),
            )
            if item_id in previous_selection:
                self.task_tree.selection_add(item_id)

        self.calendar_task_status.config(
            text=f"已选择 {len(tasks)} 个任务",
            foreground="green",
        )
        if self._editing_task_date in self._selected_dates:
            self._load_task_edit(self._editing_task_date)
        elif self._editing_task_date is not None:
            self._clear_task_editor()

    def _refresh_calendar_tasks_if_visible(self, *_):
        if self.batch_mode.get() == "calendar":
            self._refresh_calendar_tasks()

    def _on_task_tree_selected(self, _event):
        selected_items = self.task_tree.selection()
        if not selected_items:
            return

        selected_date = date.fromisoformat(selected_items[0])
        self._load_task_edit(selected_date)

    def _load_task_edit(self, selected_date: date):
        try:
            values = self._get_calendar_task_values(selected_date)
        except ValueError:
            self._clear_task_editor()
            return

        self._editing_task_date = selected_date
        self.task_edit_status.set(
            f"当前任务: {selected_date.strftime('%Y-%m-%d')}"
        )
        self.task_edit_time.set(values["time"].strftime("%H:%M"))
        self.task_edit_distance.set(f"{values['distance_km']:g}")
        self.task_edit_duration.set(f"{values['duration_min']:g}")
        self.task_edit_playground.set(values["playground_label"])
        self.task_edit_lat.set(f"{values['latitude']:g}")
        self.task_edit_lon.set(f"{values['longitude']:g}")
        self.task_edit_angle.set(f"{values['playground_angle']:g}")

    def _clear_task_editor(self):
        self._editing_task_date = None
        self.task_edit_status.set("未选择任务")

    def _remove_selected_calendar_tasks(self):
        selected_items = self.task_tree.selection()
        if not selected_items:
            return

        for item_id in selected_items:
            selected_date = datetime.strptime(item_id, "%Y-%m-%d").date()
            self._selected_dates.discard(selected_date)
            self._calendar_task_overrides.pop(selected_date, None)

        self._render_calendar()
        self._refresh_calendar_tasks()

    def _clear_calendar_tasks(self):
        self._selected_dates.clear()
        self._calendar_task_overrides.clear()
        self._clear_task_editor()
        self._render_calendar()
        self._refresh_calendar_tasks()

    def _on_task_edit_playground_selected(self, _event):
        selected = self.task_edit_playground.get()
        for pg in self._playgrounds:
            if format_playground_label(pg) == selected:
                self.task_edit_lat.set(str(pg["latitude"]))
                self.task_edit_lon.set(str(pg["longitude"]))
                self.task_edit_angle.set(str(pg["angle"]))
                break

    def _save_current_task_edit(self):
        if self._editing_task_date is None:
            messagebox.showwarning("提示", "请先选择一个任务。")
            return

        try:
            previous_values = self._calendar_task_overrides.get(
                self._editing_task_date,
            )
            values = self._read_task_edit_values()
            self._calendar_task_overrides[self._editing_task_date] = values
            self._validate_tasks(self._build_calendar_tasks())
        except ValueError as error:
            if previous_values is None:
                self._calendar_task_overrides.pop(
                    self._editing_task_date,
                    None,
                )
            else:
                self._calendar_task_overrides[
                    self._editing_task_date
                ] = previous_values
            messagebox.showerror("输入错误", str(error))
            return

        selected_id = self._editing_task_date.isoformat()
        self._refresh_calendar_tasks()
        if selected_id in self.task_tree.get_children():
            self.task_tree.selection_set(selected_id)
            self.task_tree.see(selected_id)
        self.log(f"已更新任务: {selected_id}")

    def _apply_task_edit_to_selected(self):
        target_dates = self._get_selected_task_dates()
        if not target_dates:
            messagebox.showwarning("提示", "请先选择要批量应用的任务。")
            return
        self._apply_task_edit_to_dates(target_dates)

    def _apply_task_edit_to_all(self):
        if not self._selected_dates:
            messagebox.showwarning("提示", "请先在日历中选择日期。")
            return
        self._apply_task_edit_to_dates(sorted(self._selected_dates))

    def _apply_task_edit_to_dates(self, target_dates):
        fields = self._get_apply_fields()
        if not fields:
            messagebox.showwarning("提示", "请至少选择一个应用字段。")
            return

        try:
            previous_overrides = {
                target_date: dict(self._calendar_task_overrides[target_date])
                for target_date in target_dates
                if target_date in self._calendar_task_overrides
            }
            source_values = self._read_task_edit_values(fields)
            for target_date in target_dates:
                values = self._get_calendar_task_values(target_date)
                values.update(source_values)
                self._calendar_task_overrides[target_date] = values
            self._validate_tasks(self._build_calendar_tasks())
        except ValueError as error:
            for target_date in target_dates:
                if target_date in previous_overrides:
                    self._calendar_task_overrides[target_date] = (
                        previous_overrides[target_date]
                    )
                else:
                    self._calendar_task_overrides.pop(target_date, None)
            messagebox.showerror("输入错误", str(error))
            return

        previous_selection = [
            target_date.isoformat()
            for target_date in target_dates
        ]
        self._refresh_calendar_tasks()
        for item_id in previous_selection:
            if item_id in self.task_tree.get_children():
                self.task_tree.selection_add(item_id)
        self.log(f"已批量更新 {len(target_dates)} 个任务。")

    def _reset_current_task_edit(self):
        if self._editing_task_date is None:
            messagebox.showwarning("提示", "请先选择一个任务。")
            return

        selected_date = self._editing_task_date
        self._calendar_task_overrides.pop(selected_date, None)
        self._refresh_calendar_tasks()
        item_id = selected_date.isoformat()
        if item_id in self.task_tree.get_children():
            self.task_tree.selection_set(item_id)
            self.task_tree.see(item_id)
        self.log(f"已重置任务: {item_id}")

    def _get_selected_task_dates(self):
        return [
            date.fromisoformat(item_id)
            for item_id in self.task_tree.selection()
        ]

    def _get_apply_fields(self):
        fields = set()
        if self.apply_time.get():
            fields.add("time")
        if self.apply_distance.get():
            fields.add("distance_km")
        if self.apply_duration.get():
            fields.add("duration_min")
        if self.apply_playground.get():
            fields.update(
                {
                    "playground_label",
                    "latitude",
                    "longitude",
                    "playground_angle",
                }
            )
        return fields

    def _read_task_edit_values(self, fields=None):
        values = {}
        if fields is None or "time" in fields:
            values["time"] = datetime.strptime(
                self.task_edit_time.get(),
                "%H:%M",
            ).time()
        if fields is None or "distance_km" in fields:
            values["distance_km"] = float(self.task_edit_distance.get())
        if fields is None or "duration_min" in fields:
            values["duration_min"] = float(self.task_edit_duration.get())
        if fields is None or "playground_label" in fields:
            values["playground_label"] = (
                self.task_edit_playground.get().strip()
            )
        if fields is None or "latitude" in fields:
            values["latitude"] = float(self.task_edit_lat.get())
        if fields is None or "longitude" in fields:
            values["longitude"] = float(self.task_edit_lon.get())
        if fields is None or "playground_angle" in fields:
            values["playground_angle"] = float(
                self.task_edit_angle.get() or 0
            )
        return values

    """操场选择相关回调"""

    def _on_playground_selected(self, _event):
        """用户从下拉菜单选择操场后自动填充坐标。"""
        selected = self.playground_combo.get()
        for pg in self._playgrounds:
            if format_playground_label(pg) == selected:
                self.playground_lat.set(
                    str(pg["latitude"]),
                )
                self.playground_lon.set(
                    str(pg["longitude"]),
                )
                self.playground_angle.set(
                    str(pg["angle"]),
                )
                self._refresh_calendar_tasks_if_visible()
                break

    def _filter_playgrounds(self, _event):
        """根据用户输入关键词过滤下拉列表。"""
        keyword = self.playground_combo.get().strip()
        if not keyword:
            self.playground_combo["values"] = (
                self._playground_labels
            )
            return

        filtered = [
            label
            for label in self._playground_labels
            if keyword.lower() in label.lower()
        ]
        self.playground_combo["values"] = filtered

    def _refresh_playground_data(self):
        """在后台线程中从远程拉取最新操场数据。"""
        self._refresh_btn.config(state="disabled")
        self._ui(
            self._refresh_status.config,
            text="正在刷新...",
            foreground="gray",
        )

        def _do_refresh():
            try:
                data = self._repo.refresh()
                self._playgrounds = data
                self._playground_labels = [
                    format_playground_label(pg)
                    for pg in data
                ]
                self._ui(
                    self._update_combo_values,
                )
                self._ui(
                    self._refresh_status.config,
                    text="刷新成功",
                    foreground="green",
                )
                self._ui(
                    self.log,
                    f"操场数据已更新，共 {len(data)} 条。",
                )
            except Exception as err:
                self._ui(
                    self._refresh_status.config,
                    text="刷新失败",
                    foreground="red",
                )
                self._ui(
                    self.log,
                    f"刷新操场数据失败: {err}",
                )
            finally:
                self._ui(
                    self._refresh_btn.config,
                    state="normal",
                )

        threading.Thread(
            target=_do_refresh,
            daemon=True,
        ).start()

    def _set_default_playground(self):
        """将当前选中的操场保存为用户默认操场。"""
        selected = self.playground_combo.get()
        for pg in self._playgrounds:
            if format_playground_label(pg) == selected:
                set_default_playground(pg)
                self._ui(
                    self.log,
                    f"已设为默认操场: {selected}",
                )
                return

        messagebox.showwarning(
            "提示",
            "请先从下拉菜单中选择一个操场。",
        )

    def _apply_default_playground(self):
        """加载并应用用户的默认操场设置。"""
        default_pg = get_default_playground()
        if default_pg is None:
            return

        label = format_playground_label(default_pg)
        self.playground_combo.set(label)
        self.playground_lat.set(
            str(default_pg["latitude"]),
        )
        self.playground_lon.set(
            str(default_pg["longitude"]),
        )
        self.playground_angle.set(
            str(default_pg["angle"]),
        )

    def _update_combo_values(self):
        """刷新下拉菜单的可选值列表。"""
        self.playground_combo["values"] = (
            self._playground_labels
        )
        if hasattr(self, "task_edit_playground_combo"):
            self.task_edit_playground_combo["values"] = (
                self._playground_labels
            )

    def _auto_refresh_on_startup(self):
        """启动时在后台静默拉取最新操场数据。

        失败时不打扰用户，仅在日志中记录。
        """
        try:
            data = self._repo.refresh()
            self._playgrounds = data
            self._playground_labels = [
                format_playground_label(pg)
                for pg in data
            ]
            self._ui(self._update_combo_values)
            self._ui(
                self._refresh_status.config,
                text="数据已同步",
                foreground="green",
            )
        except Exception:
            # 启动时网络不可用属于正常情况，不提示用户。
            pass

    """数据生成算法"""

    @staticmethod
    def _calculate_base_params(dist_km: float, dur_min: float) -> dict:
        dur_sec = dur_min * 60
        pace_sec_km = dur_sec / max(dist_km, 1e-6)

        if pace_sec_km < 300:
            cadence = random.randint(180, 185)
            heart_rate = random.randint(160, 170)
        elif pace_sec_km < 360:
            cadence = random.randint(172, 178)
            heart_rate = random.randint(145, 155)
        elif pace_sec_km < 420:
            cadence = random.randint(162, 168)
            heart_rate = random.randint(130, 140)
        else:
            cadence = random.randint(150, 160)
            heart_rate = random.randint(120, 130)

        return {"hr_base": heart_rate, "cadence_base": cadence}

    @staticmethod
    def _track_point(
        progress: float,
        total_laps: float,
        center_lat: float,
        center_lon: float,
        seed: int,
        playground_angle_deg: float,
    ):
        # 根据真实跑步轨迹，让直道更稳、弯道更飘，并加入低频漂移。
        point_seed = seed + int(progress * 1000000)
        rng = random.Random(point_seed)

        theta = math.radians(-playground_angle_deg)
        current_lap = progress * total_laps
        lap_progress = current_lap % 1
        segment = int(lap_progress * 4)
        segment_progress = (lap_progress * 4) - segment

        if segment == 0:
            base_x = -TRACK_CURVE_RADIUS
            base_y = -TRACK_STRAIGHT_LENGTH / 2
            base_y += TRACK_STRAIGHT_LENGTH * segment_progress
        elif segment == 1:
            angle = math.pi * (1 - segment_progress)
            base_x = TRACK_CURVE_RADIUS * math.cos(angle)
            base_y = TRACK_STRAIGHT_LENGTH / 2
            base_y += TRACK_CURVE_RADIUS * math.sin(angle)
        elif segment == 2:
            base_x = TRACK_CURVE_RADIUS
            base_y = TRACK_STRAIGHT_LENGTH / 2
            base_y -= TRACK_STRAIGHT_LENGTH * segment_progress
        else:
            angle = math.pi * segment_progress
            base_x = TRACK_CURVE_RADIUS * math.cos(angle)
            base_y = -TRACK_STRAIGHT_LENGTH / 2
            base_y -= TRACK_CURVE_RADIUS * math.sin(angle)

        drift_wave_1 = math.sin(current_lap * 0.8 + seed / 50.0)
        drift_wave_2 = math.sin(current_lap * 2.5 + seed / 20.0)
        lane_offset = 1.8 + drift_wave_1 * 1.5 + drift_wave_2 * 0.5
        lane_offset = max(0.2, min(MAX_TRACK_WIDTH, lane_offset))

        if segment == 0:
            drift_dx = -lane_offset
            drift_dy = 0.0
        elif segment == 1:
            angle = math.pi * (1 - segment_progress)
            drift_dx = lane_offset * math.cos(angle)
            drift_dy = lane_offset * math.sin(angle)
        elif segment == 2:
            drift_dx = lane_offset
            drift_dy = 0.0
        else:
            angle = math.pi * segment_progress
            drift_dx = lane_offset * math.cos(angle)
            drift_dy = lane_offset * math.sin(angle)

        noise_sigma = 0.25 if segment in (0, 2) else 0.6
        gps_noise_x = rng.gauss(0, noise_sigma)
        gps_noise_y = rng.gauss(0, noise_sigma)

        global_drift_x = math.sin(current_lap * 0.2) * 1.5
        global_drift_y = math.cos(current_lap * 0.2) * 1.5

        final_x = base_x + drift_dx + gps_noise_x + global_drift_x
        final_y = base_y + drift_dy + gps_noise_y + global_drift_y

        x_rot = final_x * math.cos(theta) - final_y * math.sin(theta)
        y_rot = final_x * math.sin(theta) + final_y * math.cos(theta)

        lat = center_lat + (y_rot / EARTH_METERS_PER_DEGREE)
        lon_scale = EARTH_METERS_PER_DEGREE * max(
            math.cos(math.radians(center_lat)),
            1e-6,
        )
        lon = center_lon + (x_rot / lon_scale)
        return lat, lon

    """生成工作流程"""

    def start_generation(self):
        try:
            out_dir = self.file_output.get().strip()
            if not out_dir:
                raise ValueError("输出目录不能为空")

            if self.batch_mode.get() == "calendar":
                tasks = self._build_calendar_tasks()
            else:
                dist_km = float(self.run_distance.get())
                dur_min = float(self.run_duration.get())
                count = int(self.file_count.get())
                interval_hours = float(self.time_interval.get() or 0)
                lat = float(self.playground_lat.get())
                lon = float(self.playground_lon.get())
                playground_angle = float(
                    self.playground_angle.get() or 0
                )
                start_dt = datetime.strptime(
                    f"{self.run_date.get()} {self.run_time.get()}",
                    "%Y-%m-%d %H:%M",
                )

                if count <= 0:
                    raise ValueError("生成份数必须大于 0")
if not math.isfinite(interval_hours):
                    raise ValueError("生成间隔必须是有限数")
                if interval_hours < 0:

                tasks = self._build_interval_tasks(
                    dist_km=dist_km,
                    dur_min=dur_min,
                    count=count,
                    interval_hours=interval_hours,
                    start_dt=start_dt,
                    lat=lat,
                    lon=lon,
                    playground_angle=playground_angle,
                )
            self._validate_tasks(tasks)
        except ValueError as error:
            messagebox.showerror("输入错误", str(error))
            return

        os.makedirs(out_dir, exist_ok=True)
        base_params = self._calculate_base_params(
            tasks[0].distance_km,
            tasks[0].duration_min,
        )

        self._set_button(False, "生成中...")
        self._set_progress(0)
        self.log(
            "基准参数: "
            f"心率~{base_params['hr_base']} | "
            f"步频~{base_params['cadence_base']}"
        )

        generation_thread = threading.Thread(
            target=self._run_task,
            daemon=True,
            args=(
                tasks,
                out_dir,
            ),
        )
        generation_thread.start()

    def _build_interval_tasks(
        self,
        dist_km,
        dur_min,
        count,
        interval_hours,
        start_dt,
        lat,
        lon,
        playground_angle,
    ) -> List[GenerationTask]:
        playground_label = self.playground_combo.get().strip()
        tasks = []
        for index in range(count):
            tasks.append(
                GenerationTask(
                    index=index,
                    start_time=(
                        start_dt + timedelta(hours=interval_hours * index)
                    ),
                    distance_km=dist_km,
                    duration_min=dur_min,
                    latitude=lat,
                    longitude=lon,
                    playground_angle=playground_angle,
                    playground_label=playground_label,
                )
        )
        return tasks

    def _build_calendar_tasks(self) -> List[GenerationTask]:
        if not self._selected_dates:
            raise ValueError("请先在日历中选择日期")

        tasks = []
        for index, selected_date in enumerate(sorted(self._selected_dates)):
            values = self._get_calendar_task_values(selected_date)
            tasks.append(
                GenerationTask(
                    index=index,
                    start_time=datetime.combine(
                        selected_date,
                        values["time"],
                    ),
                    distance_km=values["distance_km"],
                    duration_min=values["duration_min"],
                    latitude=values["latitude"],
                    longitude=values["longitude"],
                    playground_angle=values["playground_angle"],
                    playground_label=values["playground_label"],
                )
            )
        return tasks

    def _get_calendar_task_values(self, selected_date: date):
        values = self._get_default_calendar_task_values()
        values.update(
            self._calendar_task_overrides.get(selected_date, {})
        )
        return values

    def _get_default_calendar_task_values(self):
        return {
            "time": datetime.strptime(
                self.run_time.get(),
                "%H:%M",
            ).time(),
            "distance_km": float(self.run_distance.get()),
            "duration_min": float(self.run_duration.get()),
            "latitude": float(self.playground_lat.get()),
            "longitude": float(self.playground_lon.get()),
            "playground_angle": float(self.playground_angle.get() or 0),
            "playground_label": self.playground_combo.get().strip(),
        }

    def _validate_tasks(self, tasks: List[GenerationTask]):
        if not tasks:
            raise ValueError("请至少添加一个生成任务")

        seen = {}
        for task in tasks:
            task_no = task.index + 1
            numeric_values = (
                task.distance_km,
                task.duration_min,
                task.latitude,
                task.longitude,
                task.playground_angle,
            )
            if not all(math.isfinite(value) for value in numeric_values):
                raise ValueError(f"任务 {task_no} 包含无效数值")
            if task.distance_km <= 0 or task.duration_min <= 0:
                raise ValueError(f"任务 {task_no} 的距离和时长必须大于 0")
            if not -90 <= task.latitude <= 90:
                raise ValueError(f"任务 {task_no} 的纬度超出范围")
            if not -180 <= task.longitude <= 180:
                raise ValueError(f"任务 {task_no} 的经度超出范围")

            task_key = (
                task.start_time,
                round(task.distance_km, 6),
                round(task.duration_min, 6),
                round(task.latitude, 7),
                round(task.longitude, 7),
                round(task.playground_angle, 6),
            )
            if task_key in seen:
                raise ValueError(
                    f"任务 {seen[task_key] + 1} 和任务 {task_no} 重复"
                )
            seen[task_key] = task.index

        ordered_tasks = sorted(tasks, key=lambda item: item.start_time)
        for prev_task, next_task in zip(ordered_tasks, ordered_tasks[1:]):
            if prev_task.end_time > next_task.start_time:
                raise ValueError(
                    f"任务 {prev_task.index + 1} 和任务 "
                    f"{next_task.index + 1} 时间重叠"
                )

    def _run_task(self, tasks, out_dir):
        current_task = None
        try:
            total = len(tasks)
            for position, task in enumerate(tasks, start=1):
                current_task = task
                start_text = task.start_time.strftime("%m-%d %H:%M")
                base_params = self._calculate_base_params(
                    task.distance_km,
                    task.duration_min,
                )
                self._ui(
                    self.log,
                    f"正在生成第 {position}/{total} 个文件 "
                    f"(任务 {task.index + 1}, 开始时间: {start_text})...",
                )
                filename = self._generate_fit_file(
                    task=task,
                    out_dir=out_dir,
                    params=base_params,
                )
                self._ui(
                    self.log,
                    f"任务 {task.index + 1} 生成成功: "
                    f"{os.path.basename(filename)}",
                )
                self._ui(self._set_progress, (position / total) * 100)

            self._ui(messagebox.showinfo, "成功", f"生成完毕！\n路径: {out_dir}")
            self._ui(self.log, "所有任务完成。")
        # 后台线程需要兜底，确保异常后按钮和进度条状态能恢复。
        except Exception as error:
            if current_task is None:
                error_msg = str(error)
            else:
                error_msg = f"任务 {current_task.index + 1} 生成失败: {error}"
            self._ui(self.log, f"错误: {error_msg}")
            self._ui(messagebox.showerror, "错误", error_msg)
        finally:
            self._ui(self._set_button, True, "生成 FIT 运动数据")
            self._ui(self._set_progress, 0)

    def _generate_fit_file(
        self,
        task,
        out_dir,
        params,
    ):
        this_dur_sec = int(task.duration_min * 60)
        this_dist_m = task.distance_km * 1000
        start_ts = int(task.start_time.timestamp() * 1000)

        builder = FitFileBuilder(auto_define=True, min_string_size=50)

        file_id = FileIdMessage()
        file_id.type = FileType.ACTIVITY
        file_id.manufacturer = Manufacturer.GARMIN.value
        file_id.product = 3589
        file_id.serial_number = random.randint(3000000000, 4000000000)
        file_id.time_created = start_ts
        builder.add(file_id)

        event_start = EventMessage()
        event_start.event = Event.TIMER
        event_start.event_type = EventType.START
        event_start.timestamp = start_ts
        builder.add(event_start)

        track_len = 400.0
        laps = this_dist_m / track_len
        seed = random.randint(1, 999999)
        num_points = max(10, int(this_dur_sec / 2))

        sum_cadence = 0
        sum_power = 0
        sum_stride = 0
        sum_gct = 0
        max_cadence = 0

        for point_index in range(num_points):
            progress = point_index / (num_points - 1)
            curr_ts = start_ts + int(progress * this_dur_sec * 1000)
            curr_dist = this_dist_m * progress

            lat, lon = self._track_point(
                progress,
                laps,
                task.latitude,
                task.longitude,
                seed,
                task.playground_angle,
            )

            avg_speed = this_dist_m / max(this_dur_sec, 1)
            current_speed = max(
                0.1,
                avg_speed + random.uniform(-0.05, 0.05),
            )

            current_cadence = int(
                params["cadence_base"] + random.randint(-2, 2)
            )
            max_cadence = max(max_cadence, current_cadence)

            if current_cadence > 0:
                current_stride = int(
                    (current_speed / (current_cadence / 60)) * 1000
                )
            else:
                current_stride = 0

            current_power = int(
                current_speed * 70 * 1.05 * random.uniform(0.98, 1.02)
            )
            current_gct = int(
                300 - (current_cadence - 150) * 2.8
                + random.randint(-5, 5)
            )
            current_hr = int(
                params["hr_base"]
                + (progress - 0.5) * 8
                + random.randint(-1, 1)
            )
            current_hr = max(60, min(200, current_hr))

            sum_cadence += current_cadence
            sum_power += current_power
            sum_stride += current_stride
            sum_gct += current_gct

            record = RecordMessage()
            record.timestamp = curr_ts
            record.position_lat = lat
            record.position_long = lon
            record.distance = curr_dist
            record.altitude = 20.0 + random.uniform(-0.2, 0.2)
            record.speed = current_speed
            record.heart_rate = current_hr
            record.cadence = current_cadence
            record.power = current_power
            record.step_length = current_stride
            record.stance_time = current_gct
            builder.add(record)

        event_stop = EventMessage()
        event_stop.event = Event.TIMER
        event_stop.event_type = EventType.STOP_ALL
        event_stop.timestamp = start_ts + (this_dur_sec * 1000)
        builder.add(event_stop)

        avg_cadence = int(sum_cadence / num_points)
        avg_power = int(sum_power / num_points)
        avg_stride = int(sum_stride / num_points)
        avg_gct = int(sum_gct / num_points)
        total_calories = int(task.distance_km * 70 * 1.036)

        # FIT 中的循环数按 strides 记录，因此由步数折半得到。
        total_cycles = int((avg_cadence / 2) * (this_dur_sec / 60))

        lap = LapMessage()
        lap.timestamp = start_ts + (this_dur_sec * 1000)
        lap.start_time = start_ts
        lap.total_elapsed_time = this_dur_sec
        lap.total_timer_time = this_dur_sec
        lap.total_distance = this_dist_m
        lap.total_calories = total_calories
        lap.avg_heart_rate = params["hr_base"]
        lap.max_heart_rate = params["hr_base"] + 15
        lap.avg_speed = this_dist_m / max(this_dur_sec, 1)
        lap.avg_cadence = avg_cadence
        lap.max_cadence = max_cadence
        lap.avg_power = avg_power
        lap.avg_running_cadence = avg_cadence
        lap.total_cycles = total_cycles
        lap.total_strides = total_cycles
        builder.add(lap)

        session = SessionMessage()
        session.timestamp = start_ts + (this_dur_sec * 1000)
        session.start_time = start_ts
        session.total_elapsed_time = this_dur_sec
        session.total_timer_time = this_dur_sec
        session.total_distance = this_dist_m
        session.sport = Sport.RUNNING
        session.sub_sport = SubSport.GENERIC
        session.total_calories = total_calories
        session.avg_speed = this_dist_m / max(this_dur_sec, 1)
        session.max_speed = (this_dist_m / max(this_dur_sec, 1)) * 1.2
        session.avg_heart_rate = params["hr_base"]
        session.max_heart_rate = params["hr_base"] + 15
        session.avg_cadence = avg_cadence
        session.max_cadence = max_cadence
        session.avg_power = avg_power
        session.avg_step_length = avg_stride
        session.avg_stance_time = avg_gct
        session.avg_running_cadence = avg_cadence
        session.total_cycles = total_cycles
        session.total_strides = total_cycles
        builder.add(session)

        activity = ActivityMessage()
        activity.timestamp = start_ts + (this_dur_sec * 1000)
        activity.total_timer_time = this_dur_sec
        activity.num_sessions = 1
        builder.add(activity)

        fit_file = builder.build()
        filename = os.path.join(
            out_dir,
            f"keep_fit_{task.index}_{int(start_ts / 1000)}.fit",
        )
        fit_file.to_file(filename)
        return filename


def _enable_windows_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


if __name__ == "__main__":
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    app = FITGeneratorGUI(root)
    root.mainloop()

import ctypes
import math
import os
import random
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

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

VERSION = "1.0.1"
TRACK_STRAIGHT_LENGTH = 85.0
TRACK_CURVE_RADIUS = 36.5
MAX_TRACK_WIDTH = 8.0
EARTH_METERS_PER_DEGREE = 111000.0


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
        self.run_date = tk.StringVar(value=now.strftime("%Y-%m-%d"))
        self.run_time = tk.StringVar(value=now.strftime("%H:%M"))

        # 默认位置为湖北大学（武昌校区）一号操场。
        self.playground_lat = tk.StringVar(value="30.5800521")
        self.playground_lon = tk.StringVar(value="114.3307788")
        self.playground_angle = tk.StringVar(value="62.5")

        self.file_output = tk.StringVar(
            value=os.path.join(
                os.path.expanduser("~"),
                "Desktop",
                "Keep运动数据",
            )
        )

        self._setup_styles()
        self._build_ui()

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
        self._build_output_frame(main_frame)
        self._build_generation_area(main_frame)

        self._update_pace()
        self._update_interval_visibility()

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
            text="生成份数:",
        ).grid(row=2, column=0, sticky=tk.W, pady=12)
        ttk.Entry(
            basic_frame,
            textvariable=self.file_count,
        ).grid(row=2, column=1, sticky="ew", padx=15)

        self.interval_label = ttk.Label(
            basic_frame,
            text="每次间隔(小时):",
        )
        self.interval_entry = ttk.Entry(
            basic_frame,
            textvariable=self.time_interval,
        )
        self.file_count.trace_add("write", self._update_interval_visibility)

    def _build_time_frame(self, main_frame):
        time_frame = ttk.LabelFrame(
            main_frame,
            text="时间与位置",
            padding=(20, 15),
        )
        time_frame.pack(fill=tk.X, pady=(0, 20))
        time_frame.columnconfigure(1, weight=1)

        ttk.Label(
            time_frame,
            text="开始时间:",
        ).grid(row=0, column=0, sticky=tk.W, pady=12)
        date_box = tk.Frame(time_frame)
        date_box.grid(row=0, column=1, sticky="ew", padx=15)
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

        ttk.Label(
            time_frame,
            text="纬度 / 经度:",
        ).grid(row=1, column=0, sticky=tk.W, pady=12)
        geo_box = tk.Frame(time_frame)
        geo_box.grid(row=1, column=1, sticky="ew", padx=15)
        ttk.Entry(
            geo_box,
            textvariable=self.playground_lat,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(geo_box, text=" / ").pack(side=tk.LEFT)
        ttk.Entry(
            geo_box,
            textvariable=self.playground_lon,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(
            time_frame,
            text="跑道方位角:",
        ).grid(row=2, column=0, sticky=tk.W, pady=12)
        ttk.Entry(
            time_frame,
            textvariable=self.playground_angle,
        ).grid(row=2, column=1, sticky="ew", padx=15)
        ttk.Label(
            time_frame,
            text="单位：°",
            foreground="green",
            font=("Microsoft YaHei UI", 9),
        ).grid(row=2, column=2)

    def _build_output_frame(self, main_frame):
        output_frame = ttk.LabelFrame(
            main_frame,
            text="输出",
            padding=(20, 15),
        )
        output_frame.pack(fill=tk.X, pady=(0, 20))
        output_frame.columnconfigure(0, weight=1)

        ttk.Entry(
            output_frame,
            textvariable=self.file_output,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(
            output_frame,
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

    def _update_interval_visibility(self, *_):
        try:
            count = int(self.file_count.get() or 0)
        except ValueError:
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()
            return

        if count > 1:
            self.interval_label.grid(row=3, column=0, sticky=tk.W, pady=12)
            self.interval_entry.grid(row=3, column=1, sticky="ew", padx=15)
        else:
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()

    def _update_pace(self, *_):
        try:
            distance_km = float(self.run_distance.get() or 0)
            duration_min = float(self.run_duration.get() or 0)
        except ValueError:
            self.pace_label.config(text="配速: --'--\"/km")
            return

        if distance_km <= 0 or duration_min <= 0:
            self.pace_label.config(text="配速: --'--\"/km")
            return

        pace = (duration_min * 60) / distance_km
        pace_text = f"配速: {int(pace // 60)}'{int(pace % 60):02d}\"/km"
        self.pace_label.config(text=pace_text)

    def _choose_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.file_output.set(folder)

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
            dist_km = float(self.run_distance.get())
            dur_min = float(self.run_duration.get())
            count = int(self.file_count.get())
            interval_hours = float(self.time_interval.get() or 0)
            lat = float(self.playground_lat.get())
            lon = float(self.playground_lon.get())
            playground_angle = float(self.playground_angle.get() or 0)
            start_dt = datetime.strptime(
                f"{self.run_date.get()} {self.run_time.get()}",
                "%Y-%m-%d %H:%M",
            )
            out_dir = self.file_output.get().strip()

            if dist_km <= 0 or dur_min <= 0:
                raise ValueError("距离和时长必须大于 0")
            if count <= 0:
                raise ValueError("生成份数必须大于 0")
            if interval_hours < 0:
                raise ValueError("生成间隔不能为负数")
            if not out_dir:
                raise ValueError("输出目录不能为空")
        except ValueError as error:
            messagebox.showerror("输入错误", str(error))
            return

        os.makedirs(out_dir, exist_ok=True)
        base_params = self._calculate_base_params(dist_km, dur_min)

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
                dist_km,
                dur_min,
                count,
                interval_hours,
                start_dt,
                lat,
                lon,
                playground_angle,
                out_dir,
                base_params,
            ),
        )
        generation_thread.start()

    def _run_task(
        self,
        dist_km,
        dur_min,
        count,
        interval_hours,
        start_dt,
        lat,
        lon,
        playground_angle,
        out_dir,
        base_params,
    ):
        try:
            current_start_dt = start_dt
            for index in range(count):
                start_text = current_start_dt.strftime("%m-%d %H:%M")
                self._ui(
                    self.log,
                    f"正在生成第 {index + 1}/{count} 个文件 "
                    f"(开始时间: {start_text})...",
                )
                self._generate_fit_file(
                    index=index,
                    dist_km=dist_km,
                    dur_min=dur_min,
                    start_time=current_start_dt,
                    lat_center=lat,
                    lon_center=lon,
                    playground_angle=playground_angle,
                    out_dir=out_dir,
                    params=base_params,
                )
                self._ui(self._set_progress, ((index + 1) / count) * 100)
                current_start_dt += timedelta(hours=interval_hours)

            self._ui(messagebox.showinfo, "成功", f"生成完毕！\n路径: {out_dir}")
            self._ui(self.log, "所有任务完成。")
        # 后台线程需要兜底，确保异常后按钮和进度条状态能恢复。
        except Exception as error:
            self._ui(self.log, f"错误: {error}")
            self._ui(messagebox.showerror, "错误", str(error))
        finally:
            self._ui(self._set_button, True, "生成 FIT 运动数据")
            self._ui(self._set_progress, 0)

    def _generate_fit_file(
        self,
        index,
        dist_km,
        dur_min,
        start_time,
        lat_center,
        lon_center,
        playground_angle,
        out_dir,
        params,
    ):
        this_dur_sec = int(dur_min * 60)
        this_dist_m = dist_km * 1000
        start_ts = int(start_time.timestamp() * 1000)

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
                lat_center,
                lon_center,
                seed,
                playground_angle,
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
        total_calories = int(dist_km * 70 * 1.036)

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
            f"keep_fit_{index}_{int(start_ts / 1000)}.fit",
        )
        fit_file.to_file(filename)


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

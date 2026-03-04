import math
import os
import random
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk

# FIT文件处理相关依赖
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

VERSION = "1.0.0"

""" GUI创建与数据默认值 """
class FITGeneratorGUI:
    def __init__(self, root: tk.Tk):
        # 初始化主窗口
        self.root = root
        self.root.title(f"KeepTrack v{VERSION}")
        self.root.geometry("720x950")
        self.root.minsize(800, 1000)

        # 定义参数变量并设置默认值
        now = datetime.now()
        # 跑步距离（单位：公里）
        self.run_distance = tk.StringVar(value="0.00")
        # 跑步时长（单位：秒）
        self.run_duration = tk.StringVar(value="0")
        # 生成文件的个数（默认1个）
        self.file_count = tk.StringVar(value="1")
        # 每次生成的时间间隔（单位：小时，默认24小时）
        self.time_interval = tk.StringVar(value="24")
        # 跑步数据的日期（默认当前日期）
        self.run_date = tk.StringVar(value=now.strftime("%Y-%m-%d"))
        # 跑步数据的时间（默认当前时间）
        self.run_time = tk.StringVar(value=now.strftime("%H:%M"))
        # 操场的经纬度与方位角（默认为湖北大学（武昌校区）一号操场的数据，就是7栋8栋宿舍旁边的那个）
        self.playgroud_lat = tk.StringVar(value="30.5800521")
        self.playgroud_lon = tk.StringVar(value="114.3307788")
        self.playgroud_angle = tk.StringVar(value="62.5")
        # 生成的FIT文件保存路径（默认桌面一个叫“Keep运动数据”的文件夹，没有会自动创建）
        self.file_output = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Desktop", "Keep运动数据")
        )

        self._setup_styles()
        self._build_ui()



    """ UI 辅助方法 """
    # 在主线程上异步执行UI更新
    def _ui(self, fn, *args, **kwargs):
        self.root.after(0, lambda: fn(*args, **kwargs))

    # 设置进度条值
    def _set_progress(self, value: float):
        self.progress["value"] = max(0, min(100, value))

    #  设置生成按钮状态与文本
    def _set_button(self, enabled: bool, text: str):
        self.generate_btn.config(state=("normal" if enabled else "disabled"), text=text)

    # 日志输出
    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)



    """ 界面布局构建 """
    # 设置界面样式和字体
    def _setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # 设置全局字体大小
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("TLabelFrame", font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("TLabelFrame.Label", foreground="green")
        style.configure("TButton", font=("Microsoft YaHei UI", 10))

    # 处理鼠标滚轮事件
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # 构建界面布局
    def _build_ui(self):
        # 标题区域
        title_frame = tk.Frame(self.root, bg="green", height=120)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(
            title_frame,
            text=f"KeepTrack v{VERSION}",
            font=("Microsoft YaHei UI", 22, "bold"),  # 在这里设置标题字体
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


        # 主容器区域
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollable_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfig(canvas_window, width=e.width)
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # 绑定鼠标滚轮事件
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_frame = tk.Frame(self.scrollable_frame, padx=35, pady=25)
        main_frame.pack(fill=tk.BOTH, expand=True)


        # 基础数据输入区域
        basic_frame = ttk.LabelFrame(main_frame, text="基础数据", padding=(20, 15))
        basic_frame.pack(fill=tk.X, pady=(0, 20))
        basic_frame.columnconfigure(1, weight=1)

        ttk.Label(basic_frame, text="距离 (km):").grid(row=0, column=0, sticky=tk.W, pady=12)
        ttk.Entry(basic_frame, textvariable=self.run_distance).grid(
            row=0, column=1, sticky="ew", padx=15
        )

        ttk.Label(basic_frame, text="时长 (min):").grid(row=1, column=0, sticky=tk.W, pady=12)
        ttk.Entry(basic_frame, textvariable=self.run_duration).grid(
            row=1, column=1, sticky="ew", padx=15
        )

        self.pace_label = ttk.Label(
            basic_frame,
            text="配速: --'--\"/km",
            foreground="green",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.pace_label.grid(row=1, column=2, sticky=tk.W)

        self.run_distance.trace_add("write", self._update_pace)
        self.run_duration.trace_add("write", self._update_pace)

        ttk.Label(basic_frame, text="生成份数:").grid(row=2, column=0, sticky=tk.W, pady=12)
        ttk.Entry(basic_frame, textvariable=self.file_count).grid(
            row=2, column=1, sticky="ew", padx=15
        )

        self.interval_label = ttk.Label(basic_frame, text="每次间隔(小时):")
        self.interval_entry = ttk.Entry(basic_frame, textvariable=self.time_interval)
        self.file_count.trace_add("write", self._update_interval_visibility)


        # 时间与位置输入区域
        time_frame = ttk.LabelFrame(main_frame, text="时间与位置", padding=(20, 15))
        time_frame.pack(fill=tk.X, pady=(0, 20))
        time_frame.columnconfigure(1, weight=1)

        ttk.Label(time_frame, text="开始时间:").grid(row=0, column=0, sticky=tk.W, pady=12)
        date_box = tk.Frame(time_frame)
        date_box.grid(row=0, column=1, sticky="ew", padx=15)
        ttk.Entry(date_box, textvariable=self.run_date, width=14).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(date_box, text=" ").pack(side=tk.LEFT)
        ttk.Entry(date_box, textvariable=self.run_time, width=10).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(time_frame, text="纬度 / 经度:").grid(row=1, column=0, sticky=tk.W, pady=12)
        geo_box = tk.Frame(time_frame)
        geo_box.grid(row=1, column=1, sticky="ew", padx=15)
        ttk.Entry(geo_box, textvariable=self.playgroud_lat).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(geo_box, text=" / ").pack(side=tk.LEFT)
        ttk.Entry(geo_box, textvariable=self.playgroud_lon).pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(time_frame, text="跑道方位角:").grid(row=2, column=0, sticky=tk.W, pady=12)
        ttk.Entry(time_frame, textvariable=self.playgroud_angle).grid(row=2, column=1, sticky="ew", padx=15)
        ttk.Label(time_frame, text="单位：°", foreground="green", font=("Microsoft YaHei UI", 9)).grid(
            row=2, column=2
        )


        # 输出设置区域
        output_frame = ttk.LabelFrame(main_frame, text="输出", padding=(20, 15))
        output_frame.pack(fill=tk.X, pady=(0, 20))
        output_frame.columnconfigure(0, weight=1)

        ttk.Entry(output_frame, textvariable=self.file_output).grid(
            row=0, column=0, sticky="ew", padx=(0, 5)
        )
        ttk.Button(output_frame, text="浏览", width=8, command=self._choose_output).grid(
            row=0, column=1
        )


        # 生成按钮 + 进度 + 日志区域
        # 生成按钮
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

        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(15, 5))

        # 日志
        log_frame = ttk.LabelFrame(main_frame, text=" 日志 ", padding=(10, 10))
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=8, font=("Consolas", 10), bg="white", spacing1=5)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._update_pace()
        self._update_interval_visibility()



    """ 回调函数 """
    # 根据生成份数动态显示或隐藏时间间隔输入框
    def _update_interval_visibility(self, *_):
        try:
            count = int(self.file_count.get() or 0)
            if count > 1:
                self.interval_label.grid(row=3, column=0, sticky=tk.W, pady=12)
                self.interval_entry.grid(row=3, column=1, sticky="ew", padx=15)
            else:
                self.interval_label.grid_remove()
                self.interval_entry.grid_remove()
        except ValueError:
            self.interval_label.grid_remove()
            self.interval_entry.grid_remove()

    # 实时计算并显示配速
    def _update_pace(self, *_):
        try:
            d = float(self.run_distance.get() or 0)
            t = float(self.run_duration.get() or 0)
            if d > 0 and t > 0:
                pace = (t * 60) / d  # 计算配速
                self.pace_label.config(text=f"配速: {int(pace // 60)}'{int(pace % 60):02d}\"/km")
            else:
                self.pace_label.config(text="配速: --'--\"/km")
        except Exception:
            self.pace_label.config(text="配速: --'--\"/km")

    # 选择输出目录
    def _choose_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.file_output.set(folder)



    """ 数据生成算法 """
    # 计算基础数据
    @staticmethod
    def _calculate_base_params(dist_km: float, dur_min: float) -> dict:
        # 根据配速计算心率、步频
        dur_sec = dur_min * 60
        pace_sec_km = dur_sec / max(dist_km, 1e-6)

        if pace_sec_km < 300:      # 配速 < 5:00/km
            cadence = random.randint(180, 185)  # 高步频
            hr = random.randint(160, 170)   # 高心率
        elif pace_sec_km < 360:    # 配速 < 6:00/km
            cadence = random.randint(172, 178)  # 较高步频
            hr = random.randint(145, 155)   # 较高心率
        elif pace_sec_km < 420:    # 配速 < 7:00/km
            cadence = random.randint(162, 168)  # 中步频
            hr = random.randint(130, 140)   # 中心率
        else:
            cadence = random.randint(150, 160)  # 低步频
            hr = random.randint(120, 130)   # 低心率

        return {"hr_base": hr, "cadence_base": cadence}  # 返回基础心率和步频


    # 计算跑步轨迹
    @staticmethod
    def _track_point(progress: float, total_laps: float, center_lat: float, center_lon: float, seed: int, playgroud_angle_deg: float):
        # 根据多个我自己实际跑步轨迹数据得出“直道稳、弯道飘、整体低频漂移”的轨迹点
        # 更加符合真实跑步轨迹
        point_seed = seed + int(progress * 1000000)
        rng = random.Random(point_seed)

        theta = math.radians(-playgroud_angle_deg)
        L = 85.0
        R = 36.5
        max_track_width = 8.0

        current_lap = progress * total_laps
        lap_progress = current_lap % 1

        segment = int(lap_progress * 4)
        segment_progress = (lap_progress * 4) - segment

        if segment == 0:
            base_x, base_y = -R, -L / 2 + L * segment_progress
        elif segment == 1:
            ang = math.pi * (1 - segment_progress)
            base_x, base_y = R * math.cos(ang), L / 2 + R * math.sin(ang)
        elif segment == 2:
            base_x, base_y = R, L / 2 - L * segment_progress
        else:
            ang = math.pi * segment_progress
            base_x, base_y = R * math.cos(ang), -L / 2 - R * math.sin(ang)

        drift_wave_1 = math.sin(current_lap * 0.8 + seed / 50.0)
        drift_wave_2 = math.sin(current_lap * 2.5 + seed / 20.0)
        lane_offset = 1.8 + drift_wave_1 * 1.5 + drift_wave_2 * 0.5
        lane_offset = max(0.2, min(max_track_width, lane_offset))

        if segment == 0:
            drift_dx, drift_dy = -lane_offset, 0.0
        elif segment == 1:
            ang = math.pi * (1 - segment_progress)
            drift_dx, drift_dy = lane_offset * math.cos(ang), lane_offset * math.sin(ang)
        elif segment == 2:
            drift_dx, drift_dy = lane_offset, 0.0
        else:
            ang = math.pi * segment_progress
            drift_dx, drift_dy = lane_offset * math.cos(ang), lane_offset * math.sin(ang)

        noise_sigma = 0.25 if segment in (0, 2) else 0.6
        gps_noise_x = rng.gauss(0, noise_sigma)
        gps_noise_y = rng.gauss(0, noise_sigma)

        global_drift_x = math.sin(current_lap * 0.2) * 1.5
        global_drift_y = math.cos(current_lap * 0.2) * 1.5

        final_x = base_x + drift_dx + gps_noise_x + global_drift_x
        final_y = base_y + drift_dy + gps_noise_y + global_drift_y

        x_rot = final_x * math.cos(theta) - final_y * math.sin(theta)
        y_rot = final_x * math.sin(theta) + final_y * math.cos(theta)

        lat = center_lat + (y_rot / 111000.0)
        lon = center_lon + (x_rot / (111000.0 * max(math.cos(math.radians(center_lat)), 1e-6)))
        return lat, lon



    """ 生成工作流程 """
    # 开始生成FIT文件
    def start_generation(self):
        # 1.验证用户输入
        # 2.计算基础参数
        # 3.启动后台生成线程
        try:
            dist_km = float(self.run_distance.get())
            dur_min = float(self.run_duration.get())
            count = int(self.file_count.get())
            interval_hours = float(self.time_interval.get() or 0)
            lat = float(self.playgroud_lat.get())
            lon = float(self.playgroud_lon.get())
            playgroud_angle = float(self.playgroud_angle.get() or 0)
            start_dt = datetime.strptime(
                f"{self.run_date.get()} {self.run_time.get()}", "%Y-%m-%d %H:%M"
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

        except Exception as e:
            messagebox.showerror("输入错误", str(e))
            return

        os.makedirs(out_dir, exist_ok=True)
        base_params = self._calculate_base_params(dist_km, dur_min)

        self._set_button(False, "生成中...")
        self._set_progress(0)
        self.log(f"基准参数: 心率~{base_params['hr_base']} | 步频~{base_params['cadence_base']}")

        t = threading.Thread(
            target=self._run_task,
            daemon=True,
            args=(dist_km, dur_min, count, interval_hours, start_dt, lat, lon, playgroud_angle, out_dir, base_params),
        )
        t.start()

    # 生成多个FIT文件
    def _run_task(self, dist_km, dur_min, count, interval_hours, start_dt, lat, lon, playgroud_angle, out_dir, base_params):
        # 1.循环生成指定数量的文件
        # 2.更新进度条和日志
        try:
            current_start_dt = start_dt
            for i in range(count):
                self._ui(self.log, f"正在生成第 {i + 1}/{count} 个文件 (开始时间: {current_start_dt.strftime('%m-%d %H:%M')})...")
                self._generate_fit_file(
                    index=i,
                    dist_km=dist_km,
                    dur_min=dur_min,
                    start_time=current_start_dt,
                    lat_center=lat,
                    lon_center=lon,
                    playgroud_angle=playgroud_angle,
                    out_dir=out_dir,
                    params=base_params,
                )
                self._ui(self._set_progress, ((i + 1) / count) * 100)
                current_start_dt += timedelta(hours=interval_hours)

            self._ui(messagebox.showinfo, "成功", f"生成完毕！\n路径: {out_dir}")
            self._ui(self.log, "所有任务完成。")
        except Exception as e:
            self._ui(self.log, f"错误: {e}")
            self._ui(messagebox.showerror, "错误", str(e))
        finally:
            self._ui(self._set_button, True, "生成 FIT 运动数据")
            self._ui(self._set_progress, 0)

    # 生成FIT文件的核心逻辑
    def _generate_fit_file(self, index, dist_km, dur_min, start_time, lat_center, lon_center, playgroud_angle, out_dir, params):
        # 1.构建FIT文件结构
        # 2.生成轨迹点数据
        # 3.添加各种运动数据
        # 4.保存FIT文件
        # 1.0版本修正：直接使用用户输入的时长和距离，不添加随机波动
        this_dur_sec = int(dur_min * 60)
        this_dist_m = dist_km * 1000

        # 1.0版本修正：直接使用用户输入的开始时间，不添加随机偏移
        start_time_offset = start_time
        start_ts = int(start_time_offset.timestamp() * 1000)

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

        for i in range(num_points):
            p = i / (num_points - 1)
            curr_ts = start_ts + int(p * this_dur_sec * 1000)
            curr_dist = this_dist_m * p

            lat, lon = self._track_point(p, laps, lat_center, lon_center, seed, playgroud_angle)

            avg_speed = this_dist_m / max(this_dur_sec, 1)
            current_speed = max(0.1, avg_speed + random.uniform(-0.05, 0.05))

            current_cadence = int(params["cadence_base"] + random.randint(-2, 2))
            max_cadence = max(max_cadence, current_cadence)

            current_stride = (
                int((current_speed / (current_cadence / 60)) * 1000) if current_cadence > 0 else 0
            )
            current_power = int(current_speed * 70 * 1.05 * random.uniform(0.98, 1.02))
            current_gct = int(300 - (current_cadence - 150) * 2.8 + random.randint(-5, 5))
            current_hr = int(params["hr_base"] + (p - 0.5) * 8 + random.randint(-1, 1))
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

        # 计算总循环数 (strides)
        # 平均步频 avg_cadence 是 spm (steps per minute)
        # 总步数 = avg_cadence * (duration_sec / 60)
        # 总循环数 (strides) = 总步数 / 2
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
        
        # 添加平均跑步步频和总循环数
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

        # 添加平均跑步步频和总循环数
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
        filename = os.path.join(out_dir, f"keep_fit_{index}_{int(start_ts/1000)}.fit")
        fit_file.to_file(filename)



""" 整个程序的入口 """
# 启用Windows 高DPI支持
def _enable_windows_dpi_awareness():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


if __name__ == "__main__":
    _enable_windows_dpi_awareness()     # 调用高DPI支持函数
    root = tk.Tk()                      # 创建主窗口
    app = FITGeneratorGUI(root)         # 实例化主应用
    root.mainloop()                     # 启动主事件循环

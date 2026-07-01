"""KeepTrack 核心算法模块（无 UI 依赖，可独立测试）。

包含：星期调度、轨迹点生成、配速参数映射等纯计算逻辑。
"""

import math
import random
from datetime import datetime, timedelta

# ---- 操场几何常量 ----
TRACK_STRAIGHT_LENGTH = 85.0
TRACK_CURVE_RADIUS = 36.5
MAX_TRACK_WIDTH = 8.0
EARTH_METERS_PER_DEGREE = 111000.0


# ---- 星期调度 ----

def next_run_date(current_dt: datetime, selected_days: list) -> datetime:
    """计算从 current_dt 之后最近的一个符合选中星期的日期。

    如果 current_dt 本身落在选中的某一天，直接返回它；
    否则向后搜索最多 7 天，返回第一个匹配的日期。

    Args:
        current_dt: 当前参考日期时间。
        selected_days: 选中的星期列表，0=周一，6=周日。
    Returns:
        下一个符合选中星期的日期时间。
    """
    if current_dt.weekday() in selected_days:
        return current_dt
    for offset in range(1, 8):
        candidate = current_dt + timedelta(days=offset)
        if candidate.weekday() in selected_days:
            return candidate
    # 兜底：理论上不会到这里（7 天内必定找到匹配或回到同一天）。
    return current_dt + timedelta(days=1)


# ---- 配速 → 心率 / 步频 参数映射 ----

def calculate_base_params(dist_km: float, dur_min: float) -> dict:
    """根据距离和时长推算配速，并返回对应的心率/步频基准值。

    Args:
        dist_km: 跑步距离（公里）。
        dur_min: 跑步时长（分钟）。
    Returns:
        {"hr_base": int, "cadence_base": int}
    """
    dur_sec = dur_min * 60
    pace_sec_km = dur_sec / max(dist_km, 1e-6)

    if pace_sec_km < 300:          # < 5:00 /km
        cadence = random.randint(180, 185)
        heart_rate = random.randint(160, 170)
    elif pace_sec_km < 360:        # 5:00 ~ 6:00 /km
        cadence = random.randint(172, 178)
        heart_rate = random.randint(145, 155)
    elif pace_sec_km < 420:        # 6:00 ~ 7:00 /km
        cadence = random.randint(162, 168)
        heart_rate = random.randint(130, 140)
    else:                           # > 7:00 /km
        cadence = random.randint(150, 160)
        heart_rate = random.randint(120, 130)

    return {"hr_base": heart_rate, "cadence_base": cadence}


# ---- 操场绕圈轨迹点 ----

def track_point(
    progress: float,
    total_laps: float,
    center_lat: float,
    center_lon: float,
    seed: int,
    playground_angle_deg: float,
):
    """计算操场绕圈轨迹在某个进度下的 GPS 坐标。

    根据真实跑步轨迹，让直道更稳、弯道更飘，并加入低频漂移。

    Args:
        progress: 当前进度，0.0 ~ 1.0。
        total_laps: 总圈数。
        center_lat: 操场中心纬度。
        center_lon: 操场中心经度。
        seed: 随机种子（每条轨迹不同）。
        playground_angle_deg: 跑道方位角（度）。
    Returns:
        (latitude, longitude) 元组。
    """
    point_seed = seed + int(progress * 1000000)
    rng = random.Random(point_seed)

    theta = math.radians(-playground_angle_deg)
    current_lap = progress * total_laps
    lap_progress = current_lap % 1
    segment = int(lap_progress * 4)
    segment_progress = (lap_progress * 4) - segment

    # 直道 / 弯道四个分段的基础坐标。
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

    # 低频漂移 + 跑道宽度偏移。
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

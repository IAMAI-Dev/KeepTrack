"""对 fit_algorithms.py 中批量生成优化的单元测试。

覆盖：
- next_run_date 星期调度逻辑
- 距离 / 时长误差范围随机化
- calculate_base_params 配速-参数映射
- track_point 轨迹点生成
- 向后兼容（未启用新功能时行为不变）
"""

import math
import random
import unittest
from datetime import datetime, timedelta

from fit_algorithms import (
    EARTH_METERS_PER_DEGREE,
    advance_run_date,
    calculate_base_params,
    next_run_date,
    normalize_advanced_options,
    prepare_run_variant,
    resolve_advanced_options,
    track_point,
)


# ---------------------------------------------------------------------------
# next_run_date
# ---------------------------------------------------------------------------

class TestNextRunDate(unittest.TestCase):
    """测试星期调度辅助函数 next_run_date。"""

    def test_same_day_when_weekday_matches(self):
        """当前日期的星期在选中列表中时应直接返回当前日期。"""
        # 2026-07-01 是周三 (weekday=2)
        dt = datetime(2026, 7, 1, 8, 30)
        result = next_run_date(dt, [2])
        self.assertEqual(result, dt)

    def test_advance_to_next_day(self):
        """当前日期不在选中列表中时，应返回下一个匹配日期。"""
        dt = datetime(2026, 7, 1, 8, 30)  # 周三 (2)
        result = next_run_date(dt, [3])     # 选中周四
        self.assertEqual(result, datetime(2026, 7, 2, 8, 30))

    def test_advance_across_week_boundary(self):
        """跨周边界：周日应返回下周一。"""
        dt = datetime(2026, 7, 5, 8, 30)  # 周日 (6)
        result = next_run_date(dt, [0])     # 选中周一
        self.assertEqual(result, datetime(2026, 7, 6, 8, 30))

    def test_multiple_selected_days_current_matches(self):
        """选中多天时，当前匹配直接返回。"""
        dt = datetime(2026, 7, 1, 8, 30)  # 周三 (2)
        result = next_run_date(dt, [0, 1, 2, 3])  # 选一二三四
        self.assertEqual(result, dt)

    def test_multiple_selected_days_advance(self):
        """选中多天时，不在列表中则返回下一个匹配。"""
        dt = datetime(2026, 7, 3, 8, 30)  # 周五 (4)
        result = next_run_date(dt, [0, 1, 2, 3])  # 选一二三四 → 下周一
        self.assertEqual(result, datetime(2026, 7, 6, 8, 30))

    def test_all_days_selected(self):
        """选中全部 7 天时永远返回当天。"""
        dt = datetime(2026, 7, 4, 8, 30)  # 周六
        result = next_run_date(dt, list(range(7)))
        self.assertEqual(result, dt)

    def test_empty_selected_days(self):
        """空列表兜底：应向后推一天。"""
        dt = datetime(2026, 7, 1, 8, 30)
        result = next_run_date(dt, [])
        self.assertEqual(result, datetime(2026, 7, 2, 8, 30))

    def test_preserves_time_and_seconds(self):
        """调度只改变日期，时分秒保持不变。"""
        dt = datetime(2026, 7, 1, 18, 45, 30)
        result = next_run_date(dt, [2])
        self.assertEqual(result.hour, 18)
        self.assertEqual(result.minute, 45)
        self.assertEqual(result.second, 30)

    def test_scheduling_sequence_over_two_weeks(self):
        """模拟两周的 一三四 调度序列，验证日期顺序正确。"""
        selected = [0, 2, 3]  # 周一、周三、周四
        dt = datetime(2026, 7, 1, 7, 0)  # 周三

        expected_dates = [
            datetime(2026, 7, 1),   # 周三 (当天匹配)
            datetime(2026, 7, 2),   # 周四
            datetime(2026, 7, 6),   # 周一 (跨周)
            datetime(2026, 7, 8),   # 周三
            datetime(2026, 7, 9),   # 周四
            datetime(2026, 7, 13),  # 周一
        ]

        for expected in expected_dates:
            dt = next_run_date(dt, selected)
            self.assertEqual(
                dt.date(), expected.date(),
                f"Expected {expected.date()}, got {dt.date()}",
            )
            dt += timedelta(days=1)  # 前进到当天结束后


# ---------------------------------------------------------------------------
# calculate_base_params
# ---------------------------------------------------------------------------

class TestCalculateBaseParams(unittest.TestCase):
    """测试配速 → 心率/步频 的参数映射。"""

    def test_fast_pace_returns_high_cadence_and_hr(self):
        """高配速（< 5:00/km）应返回高步频和高心率范围。"""
        params = calculate_base_params(3.0, 12.0)  # 4:00/km
        self.assertGreaterEqual(params["cadence_base"], 180)
        self.assertLessEqual(params["cadence_base"], 185)
        self.assertGreaterEqual(params["hr_base"], 160)
        self.assertLessEqual(params["hr_base"], 170)

    def test_moderate_pace_returns_mid_range(self):
        """中等配速（5:00-6:00/km）应返回中档步频和心率。"""
        params = calculate_base_params(5.0, 28.0)  # ~5:36/km
        self.assertGreaterEqual(params["cadence_base"], 172)
        self.assertLessEqual(params["cadence_base"], 178)
        self.assertGreaterEqual(params["hr_base"], 145)
        self.assertLessEqual(params["hr_base"], 155)

    def test_slow_pace_returns_low_range(self):
        """低配速（> 7:00/km）应返回低步频和低心率范围。"""
        params = calculate_base_params(3.0, 24.0)  # 8:00/km
        self.assertGreaterEqual(params["cadence_base"], 150)
        self.assertLessEqual(params["cadence_base"], 160)
        self.assertGreaterEqual(params["hr_base"], 120)
        self.assertLessEqual(params["hr_base"], 130)

    def test_very_short_distance_still_works(self):
        """极短距离不应触发除零错误。"""
        params = calculate_base_params(0.1, 3.0)
        self.assertIn("cadence_base", params)
        self.assertIn("hr_base", params)
        self.assertGreater(params["cadence_base"], 0)

    def test_result_is_deterministic_with_same_seed(self):
        """相同输入+相同随机种子应产生相同结果。"""
        random.seed(42)
        p1 = calculate_base_params(5.0, 30.0)
        random.seed(42)
        p2 = calculate_base_params(5.0, 30.0)
        self.assertEqual(p1, p2)


# ---------------------------------------------------------------------------
# track_point
# ---------------------------------------------------------------------------

class TestTrackPoint(unittest.TestCase):
    """测试操场轨迹点生成算法。"""

    def setUp(self):
        self.lat = 30.5800521
        self.lon = 114.3307788
        self.angle = 62.5

    def test_returns_valid_lat_lon(self):
        """返回值应是两个浮点数。"""
        lat, lon = track_point(0.5, 10.0, self.lat, self.lon, 42, self.angle)
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lon, float)

    def test_start_point_near_center(self):
        """起点应靠近操场中心（偏移在操场尺寸范围内）。"""
        lat, lon = track_point(0.0, 10.0, self.lat, self.lon, 42, self.angle)
        lat_diff = abs(lat - self.lat) * EARTH_METERS_PER_DEGREE
        lon_diff = abs(lon - self.lon) * EARTH_METERS_PER_DEGREE * max(
            math.cos(math.radians(self.lat)), 1e-6,
        )
        self.assertLess(lat_diff, 80, f"lat offset {lat_diff:.1f}m too large")
        self.assertLess(lon_diff, 80, f"lon offset {lon_diff:.1f}m too large")

    def test_end_point_near_center(self):
        """终点也应靠近操场中心（绕圈回到起点附近）。"""
        lat_end, lon_end = track_point(
            1.0, 10.0, self.lat, self.lon, 42, self.angle,
        )
        lat_diff = abs(lat_end - self.lat) * EARTH_METERS_PER_DEGREE
        lon_diff = abs(lon_end - self.lon) * EARTH_METERS_PER_DEGREE * max(
            math.cos(math.radians(self.lat)), 1e-6,
        )
        self.assertLess(lat_diff, 80)
        self.assertLess(lon_diff, 80)

    def test_different_seeds_produce_different_points(self):
        """不同 seed 应产生不同的轨迹点。"""
        lat1, lon1 = track_point(0.5, 10.0, self.lat, self.lon, 1, self.angle)
        lat2, lon2 = track_point(0.5, 10.0, self.lat, self.lon, 999, self.angle)
        self.assertTrue(lat1 != lat2 or lon1 != lon2)

    def test_progress_from_0_to_1_generates_different_points(self):
        """同一 seed 下，不同 progress 应产生不同位置。"""
        lat_start, lon_start = track_point(
            0.0, 10.0, self.lat, self.lon, 42, self.angle,
        )
        lat_mid, lon_mid = track_point(
            0.5, 10.0, self.lat, self.lon, 42, self.angle,
        )
        self.assertTrue(lat_start != lat_mid or lon_start != lon_mid)

    def test_near_north_pole_coordinates(self):
        """高纬度（接近北极）不应崩溃且仍返回合法值。"""
        lat, lon = track_point(0.5, 10.0, 89.0, 0.0, 42, 0.0)
        self.assertIsInstance(lat, float)
        self.assertIsInstance(lon, float)
        self.assertTrue(math.isfinite(lat))
        self.assertTrue(math.isfinite(lon))

    def test_near_equator_coordinates(self):
        """赤道附近坐标工作正常。"""
        lat, lon = track_point(0.5, 10.0, 0.0, 0.0, 42, 0.0)
        self.assertTrue(math.isfinite(lat))
        self.assertTrue(math.isfinite(lon))


# ---------------------------------------------------------------------------
# 误差范围随机化
# ---------------------------------------------------------------------------

class TestErrorRangeRandomization(unittest.TestCase):
    """验证距离/时长误差范围的随机化逻辑。"""

    def test_random_within_distance_error_range(self):
        """距离在误差范围内的随机化不超出边界。"""
        base_dist = 5.0
        dist_error = 0.3
        rng = random.Random(42)
        for _ in range(100):
            actual, _, _ = prepare_run_variant(
                base_dist, 30.0, dist_error, 0.0, rng=rng,
            )
            self.assertGreaterEqual(actual, base_dist - dist_error)
            self.assertLessEqual(actual, base_dist + dist_error)
            self.assertGreaterEqual(actual, 0.01)

    def test_random_within_duration_error_range(self):
        """时长在误差范围内的随机化不超出边界。"""
        base_dur = 30.0
        dur_error = 5.0
        rng = random.Random(123)
        for _ in range(100):
            _, actual, _ = prepare_run_variant(
                5.0, base_dur, 0.0, dur_error, rng=rng,
            )
            self.assertGreaterEqual(actual, base_dur - dur_error)
            self.assertLessEqual(actual, base_dur + dur_error)
            self.assertGreaterEqual(actual, 1)

    def test_zero_error_means_exact_value(self):
        """误差为 0 时距离/时长不变并复用整批参数。"""
        batch_params = {"hr_base": 150, "cadence_base": 175}
        variants = [
            prepare_run_variant(
                5.0, 30.0, 0.0, 0.0, batch_params,
                rng=random.Random(seed),
            )
            for seed in range(5)
        ]
        for actual_dist, actual_dur, params in variants:
            self.assertEqual(actual_dist, 5.0)
            self.assertEqual(actual_dur, 30.0)
            self.assertIs(params, batch_params)

    def test_large_error_bounded_by_minimum(self):
        """大误差不应使距离/时长低于最小值。"""
        rng = random.Random(99)
        for _ in range(100):
            actual_dist, actual_dur, _ = prepare_run_variant(
                0.5, 3.0, 2.0, 10.0, rng=rng,
            )
            self.assertGreaterEqual(actual_dist, 0.01)
            self.assertGreaterEqual(actual_dur, 1)

    def test_error_range_distribution_is_uniform_approx(self):
        """采样足够多的点，中位数应接近基准值。"""
        base = 5.0
        error = 1.0
        rng = random.Random(7)
        samples = [
            prepare_run_variant(
                base, 30.0, error, 0.0, rng=rng,
            )[0]
            for _ in range(1000)
        ]
        median = sorted(samples)[500]
        self.assertAlmostEqual(median, base, delta=error * 0.2)


# ---------------------------------------------------------------------------
# 向后兼容
# ---------------------------------------------------------------------------

class TestBackwardCompatibility(unittest.TestCase):
    """验证未启用新功能时行为和原来一致。"""

    def test_single_count_ignores_hidden_invalid_values(self):
        """单条生成完全不读取隐藏的高级选项。"""
        def fail_if_called():
            raise AssertionError("hidden option getter must not be called")

        result = resolve_advanced_options(
            1,
            fail_if_called,
            fail_if_called,
            fail_if_called,
        )
        self.assertEqual(result, ([], 0.0, 0.0))

    def test_batch_count_parses_advanced_values(self):
        """批量生成会读取、排序并校验高级选项。"""
        result = resolve_advanced_options(
            3,
            lambda: [4, 0, 2],
            lambda: "0.2",
            lambda: "3",
        )
        self.assertEqual(result, ([0, 2, 4], 0.2, 3.0))

    def test_batch_count_rejects_invalid_values(self):
        """批量模式中的非法误差仍应明确报错。"""
        with self.assertRaises(ValueError):
            normalize_advanced_options(2, [], "invalid", "0")

    def test_interval_mode_advances_by_hours(self):
        """未选择星期时保持旧版固定小时间隔行为。"""
        current = datetime(2026, 7, 1, 8, 0)
        self.assertEqual(
            advance_run_date(current, [], 24),
            datetime(2026, 7, 2, 8, 0),
        )

    def test_schedule_mode_advances_to_selected_day(self):
        """选择星期时推进到下一个匹配日期。"""
        current = datetime(2026, 7, 1, 8, 0)  # 周三
        self.assertEqual(
            advance_run_date(current, [0, 4], 24),
            datetime(2026, 7, 3, 8, 0),  # 周五
        )


if __name__ == "__main__":
    unittest.main()

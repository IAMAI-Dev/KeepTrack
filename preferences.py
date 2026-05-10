"""用户偏好持久化模块。

使用 JSON 文件保存用户偏好，存储在 ~/.keeptrack/preferences.json。
"""

import json
import os

PREFERENCES_DIR = os.path.join(
    os.path.expanduser("~"),
    ".keeptrack",
)
PREFERENCES_FILENAME = "preferences.json"
PREFERENCES_PATH = os.path.join(
    PREFERENCES_DIR,
    PREFERENCES_FILENAME,
)

DEFAULT_PREFERENCES = {
    "default_playground": None,
}


def load_preferences():
    """加载用户偏好。

    文件不存在或损坏时返回默认值。
    """
    if not os.path.isfile(PREFERENCES_PATH):
        return dict(DEFAULT_PREFERENCES)
    try:
        with open(
            PREFERENCES_PATH, "r", encoding="utf-8"
        ) as fh:
            prefs = json.load(fh)
        # 合并默认值，确保新增字段不丢失。
        merged = dict(DEFAULT_PREFERENCES)
        merged.update(prefs)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_PREFERENCES)


def save_preferences(prefs):
    """保存用户偏好到文件。"""
    os.makedirs(PREFERENCES_DIR, exist_ok=True)
    with open(
        PREFERENCES_PATH, "w", encoding="utf-8"
    ) as fh:
        json.dump(
            prefs,
            fh,
            ensure_ascii=False,
            indent=4,
        )


def get_default_playground(prefs=None):
    """获取默认操场配置。

    Returns:
        操场字典，或 None。
    """
    if prefs is None:
        prefs = load_preferences()
    return prefs.get("default_playground")


def set_default_playground(playground):
    """设置默认操场并持久化。

    Args:
        playground: 操场字典，包含 school、campus、
            name、latitude、longitude、angle 字段。
    """
    prefs = load_preferences()
    prefs["default_playground"] = playground
    save_preferences(prefs)

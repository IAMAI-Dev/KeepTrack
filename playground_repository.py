"""操场数据仓库模块。

负责操场数据的加载、本地缓存管理和远程同步。
数据来源优先级：本地缓存 > 内置 playgrounds.json。
远程拉取优先级：Gitee > GitHub。
"""

import http.client
import json
import math
import os
import urllib.error
import urllib.request

# Gitee 优先，GitHub 备选。
REMOTE_SOURCES = [
    (
        "https://gitee.com/iiamaii/KeepTrack"
        "/raw/main/playgrounds.json"
    ),
    (
        "https://raw.githubusercontent.com"
        "/IAMAI-Dev/KeepTrack/main/playgrounds.json"
    ),
]

CACHE_DIR = os.path.join(
    os.path.expanduser("~"),
    ".keeptrack",
)
CACHE_FILENAME = "playgrounds_cache.json"

# 远程请求超时秒数。
REQUEST_TIMEOUT = 8

# 内置数据文件相对于本模块所在目录的路径。
_BUILTIN_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "playgrounds.json",
)


class PlaygroundRepository:
    """操场数据的加载、缓存与远程同步。"""

    def __init__(self, cache_dir=None):
        self._cache_dir = cache_dir or CACHE_DIR
        self._cache_path = os.path.join(
            self._cache_dir,
            CACHE_FILENAME,
        )

    def load(self):
        """加载操场列表。

        优先从本地缓存读取；缓存不存在或损坏时回退到
        项目内置的 playgrounds.json。
        """
        data = self._load_cache()
        if data is not None:
            return data
        return self._load_builtin()

    def refresh(self):
        """从远程仓库拉取最新数据并更新本地缓存。

        Returns:
            拉取成功时返回操场列表；失败时抛出异常。
        """
        parsed = self._fetch_remote()
        playgrounds = parsed["playgrounds"]
        self._save_cache(parsed)
        return playgrounds

    # ---- 私有方法 ----

    def _fetch_remote(self):
        """依次尝试各远程源，返回第一个通过内容校验的数据。

        Raises:
            ConnectionError: 所有远程源均不可用。
        """
        errors = []
        for url in REMOTE_SOURCES:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "KeepTrack"},
                )
                with urllib.request.urlopen(
                    req,
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    raw = resp.read().decode("utf-8-sig")
                # HTTP 成功不代表内容有效，例如登录页或损坏的 JSON。
                # 解析和校验必须在循环内，失败后才能继续尝试备用源。
                return self._parse_remote_data(raw)
            except (
                urllib.error.URLError,
                OSError,
                http.client.HTTPException,
                ValueError,
            ) as err:
                errors.append(f"{url}: {err}")
                continue

        raise ConnectionError(
            "所有远程数据源均不可用: " + "; ".join(errors)
        )

    @staticmethod
    def _parse_remote_data(raw):
        """拒绝无法供界面使用的数据，避免污染本地缓存。"""
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("操场数据必须是 JSON 对象")
        playgrounds = parsed.get("playgrounds")
        if not isinstance(playgrounds, list) or not playgrounds:
            raise ValueError("操场列表缺失或为空")
        for pg in playgrounds:
            if not isinstance(pg, dict):
                raise ValueError("操场记录必须是 JSON 对象")
            for key in ("school", "campus", "name"):
                if not isinstance(pg.get(key), str) or not pg[key].strip():
                    raise ValueError(f"操场记录缺少有效的 {key}")
            for key, limit in (
                ("latitude", 90), ("longitude", 180), ("angle", None),
            ):
                value = pg.get(key)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or (isinstance(value, float) and not math.isfinite(value))
                    or (limit is not None and abs(value) > limit)
                ):
                    raise ValueError(f"操场记录的 {key} 无效")
        return parsed

    def _save_cache(self, data):
        """将完整数据结构写入本地缓存文件。"""
        os.makedirs(self._cache_dir, exist_ok=True)
        with open(
            self._cache_path, "w", encoding="utf-8"
        ) as fh:
            json.dump(data, fh, ensure_ascii=False, indent=4)

    def _load_cache(self):
        """从本地缓存加载操场列表。

        Returns:
            解析成功时返回列表，文件不存在或损坏时返回 None。
        """
        if not os.path.isfile(self._cache_path):
            return None
        try:
            with open(
                self._cache_path, "r", encoding="utf-8"
            ) as fh:
                parsed = json.load(fh)
            return parsed.get("playgrounds", [])
        except (json.JSONDecodeError, OSError):
            return None

    def _load_builtin(self):
        """从项目内置 playgrounds.json 加载操场列表。"""
        try:
            with open(
                _BUILTIN_PATH, "r", encoding="utf-8"
            ) as fh:
                parsed = json.load(fh)
            return parsed.get("playgrounds", [])
        except (json.JSONDecodeError, OSError):
            return []


def format_playground_label(pg):
    """将操场字典格式化为下拉菜单显示文本。

    格式：学校（校区）- 操场名
    """
    return (
        f"{pg['school']}（{pg['campus']}）"
        f"- {pg['name']}"
    )

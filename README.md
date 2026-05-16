# KeepTrack

模拟跑步轨迹数据生成工具。在指定日期范围内，按照用户设定的参数批量生成符合 Garmin 标准的 `.fit` 文件。

## 功能

- **参数化配置** — 设置运动距离范围、时长范围、日期区间、每日起始时间
- **操场选择** — 下拉选择已保存的操场，支持自定义添加（经纬度 + 方位角）
- **操场数据持久化** — 添加的操场自动落盘保存，下次启动无需重新输入
- **拟真轨迹算法** — 400 米标准跑道模型，含旋转矩阵和随机噪声模拟真实跑步
- **FIT 文件构建** — 使用 `fit_tool` 生成符合 Garmin 标准的 `.fit` 文件
- **批量处理** — 一键生成连续多日的运动记录，带进度条
- **系统分享** — 生成后可通过系统分享将文件发送到其他应用

## 技术栈

- **Flutter** (Dart) — 跨平台 UI 框架
- **fit_tool** — FIT 文件构建库
- **path_provider** — 文件路径管理
- **share_plus** — 系统分享
- **intl** — 日期格式化

## 项目结构

```
lib/
├── main.dart                          # 入口，Material 3 主题
├── models/
│   ├── track.dart                     # 操场数据模型
│   └── generation_params.dart         # 生成参数模型
├── services/
│   ├── track_repository.dart          # 操场 CRUD + JSON 持久化
│   ├── track_generator.dart           # 400m 跑道轨迹算法
│   └── fit_file_writer.dart           # FIT 文件构建与写入
└── screens/
    ├── home_screen.dart               # 主界面（参数配置）
    └── track_manage_screen.dart       # 操场管理（添加/编辑/删除）
```

## 使用说明

1. 选择或添加操场（中心经纬度 + 方位角）
2. 设置运动距离和时长范围
3. 设置日期范围及每日起始时间
4. 点击「开始按天批量生成」
5. 生成完成后可通过分享按钮发送 `.fit` 文件

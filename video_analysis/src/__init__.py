"""健身分析后端 - src 包。

模块组织：
  models.py            数据类（VideoSegment、WorkoutSession 等）
  config.py            常量配置（AI 模型、器械库、tempo 表、MET 表）
  keyframe_extractor   视频抽帧
  frame_classifier     GPT 视觉识别每帧
  segment_merger       关键帧 → VideoSegment
  set_detector         段内切组 + tempo 估次数
  heart_rate_loader    CSV 心率数据解析
  calorie_calculator   心率法 / MET 法 / 混合法
  visualizer           matplotlib 图表
  report_generator     MD 日报
  calendar_view        月历汇总
  pipeline             CLI 入口，编排全流程
"""

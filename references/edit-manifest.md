# Edit Manifest

EDL 使用 JSON 保存剪辑判断，让粗剪、精剪、渲染和回看共享同一份时间线。路径、标题和参数都应来自当前请求或 Profile，不要在 Skill 源码中写死个人工作区。

## Minimal schema

```json
{
  "schema": "lovstudio/media-edit/v1",
  "iteration": {
    "phase": "draft",
    "state": "work/iteration-current.json",
    "plan": "work/iteration-plan.json",
    "timings": "work/iteration-timings.json"
  },
  "source": {
    "video": "SOURCE_VIDEO",
    "audio": ["OPTIONAL_AUDIO"],
    "duration_seconds": 1065.877
  },
  "target": {
    "platform": "video-channel",
    "aspect_ratio": "16:9",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "duration_target_seconds": 65
  },
  "opening": {
    "strategy": "auto",
    "resolved_strategy": "direct",
    "decision_origin": "automatic",
    "decision_reason": "第一句直接抛出具体问题，不需要重复高光",
    "post_problem_title": {
      "enabled": true,
      "source_after": 12.12,
      "text": "本期内容｜如何智能打开被归档的 Codex 对话"
    }
  },
  "segments": [
    {
      "id": "hook",
      "source_start": 512.4,
      "source_end": 516.8,
      "role": "result-clue",
      "speed": 1.0,
      "protected_audio": false,
      "notes": "先给出最终状态的一角"
    },
    {
      "id": "result-playback",
      "source_start": 932.2,
      "source_end": 940.6,
      "role": "final-evidence",
      "speed": 1.0,
      "protected_audio": true,
      "bgm": "duck"
    }
  ],
  "audio": {
    "bgm": "BGM_FILE",
    "duck_during": ["voice", "result-playback"],
    "target_lufs_i": -16,
    "true_peak_ceiling_dbfs": -1
  }
}
```

## 字段约束

- `source_start` 和 `source_end` 使用秒数，`source_end` 必须大于 `source_start`。
- `iteration.phase` 只能是 `draft` / `locked` / `approved`；每轮先由 `iteration_plan.py` 计算失效范围，
  不能把所有文件 mtime 变化都解释为全量重建。
- `id` 唯一；`role` 说明这段画面在叙事中的作用，不只写“clip-1”。
- `protected_audio: true` 表示原声必须进入最终混音并在回看中单独验收。
- `speed` 只改变节奏，不改变关键按钮、输入和结果的可辨认性。
- `bgm: duck` 表示 BGM 退到氛围层；成果段可使用 `original-only` 让原声单独收束。
- 允许时间线出现有意留白，但不允许片段重叠；是否要求连续由项目目标决定。
- EDL 的 `source` 路径只存在于项目文件，不复制进可复用 Skill 源代码。
- `opening.strategy` 接受 `auto` / `direct` / `highlights`；当前请求的显式值优先于 Profile 和自动判断。
- `resolved_strategy` 必须落成 `direct` 或 `highlights`，并记录 `decision_origin` 与可复核的 `decision_reason`。
- `direct` 在第一段问题说清前不得插 Highlights 或开场标题；`post_problem_title` 可独立开关、改文案和移动锚点。

## 运行顺序

1. 先用 `media_probe.py` 获取源时长，避免引用超出边界的时间。
2. 更新 iteration state 并运行 `iteration_plan.py plan`，只执行 `run` 的 stage。
3. 写入 EDL 后运行 `timeline_check.py`，处理所有 overlap、无效时长和重复 ID。
4. 渲染时按 EDL 明确映射视频、原声和 BGM；不要让 FFmpeg 自动猜流。
5. 终版回看每个 `protected_audio` 片段，并把实际结果写入交付报告。

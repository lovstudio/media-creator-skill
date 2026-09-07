# Incremental Iteration Contract

这份契约解决一个具体问题：小改字幕、布局或 BGM 时，不得重新跑整套长视频生产链。
工作流只有一份剪辑事实，但分成 `draft`、`locked`、`approved` 三个阶段。

## 1. 三阶段门禁

| 阶段 | 允许做什么 | 明确不做什么 |
| --- | --- | --- |
| `draft` | 建源索引、转写，按 EDL 需要懒生成 source-scoped 低码率代理分片；快速拼成当前输出时长的预览轨；只跑受影响的局部 canary | 不预转完整 85 分钟级源轨，不生成全长最终连续母版，不做最终混音，不跑整片渲染和全量 QC |
| `locked` | 画面与对白锁定后生成 timeline-scoped 连续母版和最终混音；跑完整解码、全片 ASR、响度和关键帧检查 | 未获批准不生成平台终版 |
| `approved` | 以批准的剪辑、字幕、混音和布局执行平台渲染与全量交付 QC | 不因封面或文案变化重建媒体母版 |

`draft` 的 Studio 主预览可以使用低码率代理与临时预览混音；`locked` 后才把同一个 Composition
切换到连续母版和最终混音。任何状态描述都要写明当前阶段，不能把 draft 预览称为最终成片。

### approved 阶段的平台顺序

跨平台输出默认先完成视频号 9:16：制作、渲染、完整解码、参数检查、响度检查与烧录字幕抽帧都通过后，
才开始 B 站 16:9。两路读取同一份 locked 连续母版与最终混音，不复制 EDL。全片渲染默认顺序执行；
并行前先用代表性 20–30 秒窗口测量总吞吐、峰值内存与剩余时间，只有并行实测更快时才采用，不能仅凭
空闲 CPU 核数推断。若前一路失败，停在该平台局部修复，不启动后一路。

## 2. 缓存按事实域分层

- `source`：源包索引、源转写、display/webcam/audio 代理分片；已生成分片只在源素材变动时失效，
  新 EDL 引用未缓存区间时只补那一段。
- `timeline`：EDL、速度映射、切点 canary、最终连续母版；只在剪辑事实变动时失效。
- `presentation`：字幕、布局、章节、鼠标和卡片；不应触发源代理或最终混音重建。
- `audio`：对白、系统声、BGM、ducking 与最终混音；BGM 改动不应重建视频母版。
- `platform`：横竖版、编码、烧字幕和最终渲染；只有批准后执行。
- `creative`：封面与标题；可并行，不应阻塞 draft 审片，也不触发媒体重建。

源代理分片命名必须由 `source revision + channel + source time range + proxy profile` 决定，不能把
EDL 版本放进键名。draft 每轨允许把本轮命中的分片快速拼成输出时长的低码率连续预览轨；
最终连续母版才由 `source revision + edit revision + final profile` 决定。
计划中的对应 stage 分别叫 `source-proxies` 与 `final-mezzanine`，方便报告稳定聚合。

## 3. 变更失效矩阵

| 改动 | 必跑 | 必须复用 |
| --- | --- | --- |
| 仅字幕 | draft 预览、字幕边界检查 | 源代理、最终连续视频、最终混音 |
| 仅布局/隐私遮挡 | 视觉 canary；批准后重渲染成片 | 源代理、最终连续视频、最终混音 |
| 仅 BGM/ducking | 音频 canary；locked 后最终混音；批准后重封装/渲染 | 源代理、最终连续视频 |
| EDL/变速/切点 | 接缝 canary；locked 后连续母版与最终混音 | 源索引、源转写、源代理 |
| 平台规格 | 对应平台渲染与平台 QC | 源代理、连续母版、最终混音 |
| 封面/标题 | 封面渲染与创意检查 | 全部视频与音频媒体 |

如果执行结果违反“必须复用”，先解释缓存为何无效；不能悄悄回退成全量重跑。

## 4. 机器可执行的迭代计划

每次改动前写 `work/iteration-current.json`。revision token 可以是 Git SHA、文件 SHA-256、manifest
版本或稳定的内容哈希，但不要为规划阶段重新读取并哈希几十 GB 原素材。

```json
{
  "schema": "lovstudio/media-iteration/v1",
  "phase": "draft",
  "revisions": {
    "source": "screenstudio-package-v1",
    "edit": "edl-v3",
    "subtitles": "srt-v7",
    "layout": "layout-v2",
    "audio": "voice-v3",
    "bgm": "bright-lounge-v1",
    "platform": "channels-1080x1920-v1",
    "cover": "cover-v2"
  }
}
```

运行：

```bash
python3 "$SKILL_DIR/scripts/iteration_plan.py" plan \
  --previous work/iteration-previous.json \
  --current work/iteration-current.json \
  --output work/iteration-plan.json
```

第一次运行省略 `--previous`。执行者只运行 `status=run` 的 stage；`skip` 是缓存复用证据，
`blocked` 是阶段门禁，不得绕过。成功一轮后再把 current 原子替换为 previous。

## 5. Canary 先于长任务

- `seam-canary`：只覆盖所有新增或移动切点前后各 1–2 秒，检查残词、爆音和映射。
- `visual-canary`：只渲染开场、每种摄像头布局、章节卡、产品卡、资源页和改动帧。
- `audio-canary`：只覆盖普通人声、ducking、系统声/成果原声和 BGM 接缝。

任一 canary 失败就停在局部，不启动全长任务。全长渲染前必须确认 canary 使用的 revision token
与当前计划一致，防止“测的是旧版，跑的是新版”。

## 6. QC 分层

- 每次 draft：只检查受影响的语义、画面或音频窗口，并确认 Studio 无新控制台错误。
- locked：连续轨完整解码、最终人声全片 ASR、最终混音 LUFS/dBTP、关键帧联系表。
- approved：编码成片完整解码、平台参数、烧录/字幕回抽、全片抽帧、封面与发布交接门禁。

不得把 locked/approved 的全量检查机械复制到每次字幕或布局微调。

## 7. 耗时必须可回读

每个实际执行的 stage 记录墙钟时间；被复用的 stage 不伪造为 0 秒。示例：

```bash
python3 "$SKILL_DIR/scripts/iteration_plan.py" record \
  --report work/iteration-timings.json \
  --stage visual-canary \
  --started-at 2026-09-01T10:00:00+08:00 \
  --finished-at 2026-09-01T10:00:18+08:00 \
  --status passed \
  --detail layout-only
```

交付报告至少汇总本轮总墙钟、最长 stage、缓存复用列表和 blocked 列表。若一次普通 draft 仍超过
15 分钟，先用 timing 报告定位等待链，不用“素材很大”作笼统解释。

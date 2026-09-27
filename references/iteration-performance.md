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

## 8. 作者在线快速迭代

作者在线审片、方向已经确定时，速度本身就是交付质量的一部分。「观测实例」来自冈仁波齐转山 vlog，只作观测。

- 每轮由主 agent 直接改剪辑表，只重渲变动的镜头（360 镜头仍要先重投影成平面片段，Studio 不能实时做
  `v360`）、重混音频、同步 Studio 数据，让作者按时间点提意见。一轮含剪辑判断的目标是 15–40 分钟；这和
  上一节“普通 draft 超过 15 分钟要用 timing 报告解释等待链”不矛盾：后者只算机器等待。不等整片渲染和
  全套质检，不每轮渲染手机预览、不每轮重发审片页，作者要或进入 `locked` 时再出（见
  [`review-page.md`](review-page.md)）。
- 多个 agent 各出一版再评审合成的长工作流，以宿主允许子 agent 为前提，只在作者离线、或方向未定且明确要
  多方案比较时使用；启动前用一句话说明机制，并按实测给出耗时。观测实例：4 个剪辑 agent + 3 个评审 +
  合成嫁接 + 两轮对抗审校，每个剪辑 agent 31–39 分钟、整轮剪辑 3.6 小时、配乐另 2.4 小时，嫁接反而让
  结构更碎；改成主 agent 直剪约 40 分钟出一版，作者回复“片段切换好多了”，下一轮文案改动约 20 分钟。
- 作者直接指出的具体错误（拍错人、画面错、字幕错），由主 agent 帧级核对后立即修好并同步到 Studio，不挂在
  后台批量复核后面；每次汇报分开写哪些已进 Studio、哪些还没进。
- 作者提过的每条要求记进请求清单（`request-list`，见 [`delivery-contract.md`](delivery-contract.md)）直到
  做完，每轮汇报列出未完成项和原因。作者点名的素材类需求优先级高于顺手的小修改，要当轮落地；做不完就说明
  卡在哪一步、预计哪一版交付，不能被后面的零碎意见反复挤掉。
- 作者催问时立即用文字回复：卡在哪一步、剩余步骤、预计时间，不只继续调工具。
- 只在 Studio 里审过的项目，作者说“可以发布”不等于字幕已批准。先把当前 Studio 字幕导出为 SRT，列出其
  SHA-256，请作者确认这就是批准版本；拿到明确确认后记 `subtitle_status=approved`，再在后台启动最终渲染，
  按实测帧率报剩余时间（观测实例：24810 帧、约 11.7 帧/秒、约 35–40 分钟）。想加速先看 CPU 与内存余量，
  满载时加并发只会更慢。等待期间可以并行做封面方案。发布字段预填只在作者同意、且进入发布交接后交给
  `lov-media-publisher`（只填文字，不上传、不提交）。

## 9. 多 agent 批量复核

以宿主允许子 agent 为前提；不允许时由主 agent 按同样的口径分批自查。

- 大批量重取景或复核用“执行 agent + 独立复核员”配对：复核员的职责是挑错，必须用最终参数独立重渲（至少
  4 fps 看完整段），说话镜头实测眼位，不复用执行方的图和数字；结果按 `ok / fallback / needs_author`
  结构化，并附证据图路径。
- 结果逐批落盘；参数一确定就后台渲染，渲染缓存以参数加区间为键，复核不通过的只重渲改动过的镜头。
- 部分失败时用 resume 复用已完成批次；全部失败或判定口径已变时，改脚本后重新启动，不续跑过时的 prompt。
- 作者中途改口径或澄清口径：立刻停掉按旧口径运行的任务，用决策备注关键词和非 ok 决策筛出受影响的项重做，
  不受影响的部分照常推进；按旧口径定下的约束（例如裁切安全线）降为“待复核”，不再当硬约束；与新口径矛盾的
  旧记录（Profile、项目笔记）同步修改。观测实例：口径澄清后按决策备注筛出 17–18 项重做，其余 34 个镜头和
  43 张照片先开始渲染。

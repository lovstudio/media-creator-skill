# Skill Group Composition

这个记录把相邻媒体能力和本 Skill 的最终验收边界分开，避免因为名称相近而形成隐藏依赖。

## Nearby Skills Inspected

| Skill | 实际输入 → 输出 | 关系 |
| --- | --- | --- |
| `lov-media-preprocessor` | 原始实录 → 全片增强/内容分段 + `media-preprocess-handoff/v1` | 可选上游；本 Skill 复用增强画面与原时间映射，承担句子精剪和独立成片，不重复调色。 |
| `FFmpeg Video Editor` | 自然语言编辑请求 → 单条 FFmpeg 命令 | 可参考的上游原子；本 Skill 负责完整流程、EDL、音频门禁和报告，不只返回命令。 |
| `lov-video-chapter` | SRT/视频 → 章节项目、透明层、烧录视频和编辑包 | 下游可选能力；接收已确认的成品或字幕，不参与本 Skill 的核心剪辑判断。 |
| `lov-subtitle-freedom-skill` | 视频/SRT + 学习者 Profile → 保持时间轴的 SRT/ASS | 下游可选能力；只在明确要求学习字幕时交接。 |
| `lov-channels-cover` | 标题钩子 + 人像素材 → `cover_3x4.png`、`cover_4x3.png`、`spec.json` | 可发现时作为视频号封面的首选上游；缺失不能阻断或跳过正式封面。 |
| `lov-image-creator` | 图像 brief → PNG、HTML 或外部模型 Prompt | 通用图像回退；专用封面 Skill 缺失时也可生成实际平台槽位图片。 |
| `lov-media-fetch` | 检索需求 → 已下载并核验的本地媒体 | 上游可选能力；只负责取得素材，不负责剪辑与成片验收。 |
| `lov-media-crawler` | 视频号 / B 站 / 小红书等平台链接 → 解析信息与下载后的本地媒体、诊断报告 | 上游可选能力；叙事片回忆段要用作者在平台上的旧视频时，先只解析元信息，作者同意后再由它下载并校验。 |
| `lov-wdb-cli` | 本地微信数据的只读查询 → 朋友圈等记录与媒体线索 | 上游可选能力；作者同意取用本地社交缓存里的旧照片时，由它按帖子记录的宽高与时间范围匹配原图；本 Skill 只接收匹配出的文件。 |
| `lov-voice2srt` | 录音或视频 → SRT、JSON 与纯文本，可带热词表，付费云端 ASR 前显示成本 | 可选转写能力；云端 ASR 是 Profile 选择，上传第三方与计费先向作者说明；本 Skill 仍负责剪点回转写与字幕校对。 |
| `lov-media-publisher` | 字幕已批准的平台媒体 → 视频号 / B 站终稿确认、发布状态与列表回读 | 下游可选能力（免费）；只接收字幕已批准、`platform-ready` 且封面已批准的文件和交付报告，最终发布状态由发布能力负责。宿主发现它才交接，未发现时停在 `platform-ready` 并给出安装命令；安装时由 frontmatter 的 `dependencies:` 预检提示，不写进 `depends_on`。 |

## Atomic Handoffs

- 已增强素材 handoff + 全片语义证据 → `clip_batch.py` 的独立切片计划、实际 MP4/封面/字幕和 `delivery.json`。增强程度与分段取舍归上游，独立传播价值、剪口流畅和成片验收归本 Skill。
- `SOURCE_VIDEO`、音频和字幕流 → `media_probe.py` → `source-probe.json`：本 Skill 自己拥有输入完整性判断。
- EDL JSON → `timeline_check.py` → `timeline-check.json`：本 Skill 自己拥有时间线不重叠和 protected segment 门禁。
- Remotion 工程 + 当前字幕 + 最终音频 → 现有 Remotion Studio → 主预览与刷新证据：本 Skill 拥有画面、声音和字幕的审片门禁。
- 需要 Subtitle Edit 时，无旁白硬字幕画面 + 音频母带 + SRT → `subtitle_gate.py review` → 字幕修正 MKV + 回抽证据：本 Skill 拥有字幕修正门禁；该 MKV 不是主预览。
- 审校 MKV + 用户批准 SRT → `subtitle_gate.py approve` → 归档 MKV：视频/音频 stream copy，不重复有损编码。
- 平台文件 → `media_probe.py`、`audio_qc.py` 和 FFmpeg decode smoke test → `final-probe.json`、`audio-qc.json`：本 Skill 自己拥有渲染与音频验收。
- `subtitle_status=approved`、`delivery_status=platform-ready` 且 `cover_status=approved` 的文件 + 交付报告 → `lov-media-publisher`（宿主可发现且作者要求发布时；否则停在 `platform-ready`、不启动交接，`publish_status` 保持 `not-requested`，作者要求过发布时报告写明「未发现发布能力」并给出 `npx skills add lovstudio/media-publisher-skill -g -y`）：发布 Skill 拥有账号交互、终稿确认、发布和线上回读；本 Skill 只记录交接状态。发布页文字字段预填只在作者同意且进入发布交接后交给它，只填文字，不上传、不提交；已发布版本的下架、替换或重发同样归它，由作者决定（见 delivery-contract「发布前隐私扫描」）。
- 作者在平台上发布过的旧视频链接 → `lov-media-crawler` / `lov-media-fetch`（先只解析标题、时长，作者同意后下载并校验）→ 本地可读文件：获取归上游，本 Skill 负责取舍、模糊底、静音与时间水印。
- 本地社交缓存里的旧照片 → `lov-wdb-cli`（按帖子记录的宽高与时间范围匹配原图，临时文件用完即删）→ 原图文件：读取归上游，逐张审片、裁切与隐私处理归本 Skill。
- 作者原声 + 题材热词表 → `lov-voice2srt`（云端 ASR 由 Profile 选择，上传与计费先向作者说明）→ SRT / JSON：转写归上游，剪点定位、逐句回转写和字幕校对归本 Skill。
- 已确认成片或字幕 → `lov-video-chapter` / `lov-subtitle-freedom-skill`：这些能力拥有章节或学习字幕输出；本 Skill 不复制其专门逻辑。
- 封面方向 brief → `lov-image-creator`：图像能力拥有生图/渲染；本 Skill 负责封面在标题、主题和成片证据中的位置。
- 标题钩子 + 人像/界面素材 → 可用的 `lov-channels-cover`，否则当前图像能力、`lov-image-creator` 或 Remotion `Cover` composition → 实际平台槽位图片；专用能力缺失时记录回退路径，不得省略封面。
- 定稿开场静帧 + `body.mp4` → `check_opening_still.py` → 画幅判定与 FFmpeg 片段：**做开场静帧时方向被反转**，那张图成为渲染的输入而非产物。画幅不一致时脚本默认退出码 1，逼调用方显式选 crop / pad / 另做一张同画幅的图，不允许静默 scale-pad。

## Overlap Decisions

- 整场实录的“智能分段”在上游准备素材；能独立理解的传播切片与精包装在本 Skill。二者通过原时间码交接，保留 Single Skill 结构，不新建同职能切片 Skill。
- 与 `FFmpeg Video Editor` 有命令级重叠，保留其作为参考，不把本 Skill 缩减成命令生成器，因为用户要的是从素材到成片的完整闭环。
- 与 `lov-video-chapter`、`lov-subtitle-freedom-skill`、`lov-image-creator` 只在文件级交接，不复制章节、学习字幕或生图实现。
- 与 `lov-channels-cover` 的边界在「封面已定稿」：它可用时沿用其钩子与整墙门禁；不可用时由本 Skill 组织回退生成与同等交付验收。成片画幅、首帧停留时长和声画同步始终归本 Skill。
- **首帧不是封面的一个比例档。** 视频号把封面（3:4，主页九宫格与分享卡片）和视频画面（竖版普遍 9:16）分给了不同场景，本来就不期待同比例。所以不要为了首帧去给 `lov-channels-cover` 加 9:16 档——需要首帧就单独设计一张 9:16 图，也不在本 Skill 里用 `scale`/`pad` 把 3:4 硬凑成 9:16。
- 与 `lov-media-fetch`、`lov-media-crawler`、`lov-wdb-cli` 的边界在“素材已可读”；平台下载、社交缓存解析和
  媒体获取失败都交回上游，不在此 Skill 内加入下载器或缓存解析器。
- 与 `lov-voice2srt` 的边界在“有带时间戳的转写”；本 Skill 不内置云端 ASR 客户端，只决定用哪份转写、怎么校对。
- 与 `lov-media-publisher` 的边界在“字幕已批准、平台文件已通过质检、封面已批准”；审校 MKV 不得发布，发布失败或回读缺失也不得倒写成片状态。

## Composition Decision

选择 **Single Skill**。用户可见的结果是一个经过编辑、混音和质检的成片，扫描、剪辑规划、渲染、音频检查和交付报告共享同一份项目上下文；它们拆成独立 Skill 只会增加交接成本。相邻 Skill 通过明确的文件与状态交接保持可选，不作为源目录外的硬依赖。

发布能力的安装方式单独说明。目录 `skills.yaml` 的 `depends_on` 会被 lovstudio CLI 纳入安装闭包，写进去就等于强制安装，会让只剪辑的用户也背上 ego-browser、平台登录态和 macOS 通知这些前提；把 `lov-media-publisher` 作为 Kit 模块内嵌，又会多出一份需要手工同步的源码。所以目录和 SKILL.md 的 `depends_on` 都不写它，只用 frontmatter 的 `dependencies:` 做安装预检：`npx lovstudio skills add media-creator` 会列出这项可选搭配，加 `--with-deps` 才安装；`npx skills add` 路径不读这一项，靠 README 与运行时提示补足。

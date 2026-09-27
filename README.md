# 天才剪辑师 · Video Studio

![Version](https://img.shields.io/badge/version-0.18.0-CC785C)

把 MP4 或 `.screenstudio` 源工程整理成两阶段交付：先做 Remotion Studio 与字幕审校版本，再以批准字幕生成归档母版、平台文件和正式封面图片。源工程模式保留独立屏幕、摄像头、麦克风、系统声、鼠标和快捷键事件；跨平台任务先完成并质检视频号 9:16，再顺序派生 B 站 16:9。

麦克风先解码为 PCM 再做样本级口水词/口误剪辑。`draft` 只为 EDL 命中区间懒生成 source-scoped 代理分片，不预转完整长源轨；`locked` 后才生成最终连续媒体与混音，`approved` 后才全片渲染。字幕、布局或 BGM 微调通过差异化失效与局部 canary 验证，不再触发五轨和整片重跑。录屏与知识系列的 BGM 默认使用已授权的 `Screen Studio Lo-fi / Bright Lounge`；早期程序合成路径已废弃。
Vlog、旅行片等叙事片则把用户给的整个曲库纳入选曲，按叙事混合多首，并用 cue 校验、语音频段 SMR 与 Whisper 可懂度三道客观门禁验收。
口播加速使用保持原音高的 time-stretch，禁止用重采样改变对白时长。

Screen Studio 模式还执行双层语义门禁：每个高风险切点做局部短窗 ASR，最终连续人声再做全片 ASR；
章节导航全程展示全部宏观章节，官网产品卡与片尾资源索引都是正式包装的一部分。

竖版按最终发布容器而不是裸画布计算安全区：视频号默认先预留顶部约 160px，避开 iPhone
刘海 / 灵动岛状态栏与微信导航；再用真实手机截图校准。章节导航、标题、网址和关键控件不得进入
遮挡区，背景画面可以延伸到边缘。

## 安装

从公开仓库全局安装：

```bash
npx skills add lovstudio/media-creator-skill -g -y
```

开发当前源码时，也可以在本仓库根目录用本地路径安装：

```bash
export SKILL_SOURCE_DIR="$(pwd)"
npx skills add "$SKILL_SOURCE_DIR"
```

## 使用

整场课程、活动或多人交流可以直接做成**独立切片批次**：通读全片并记录取舍，提取全部有价值的完整内容，再精修词头句尾、校正字幕、连续混音、统一包装。无需另建 Skill，也不强制做成系列课。

新增 `scripts/clip_batch.py` 与可复制的 Remotion 工程模板，可导出实际 MP4、两种封面、字幕和交付清单；已完成文件经哈希核验后复用，半成品保留再重试。详细输入、命令、授权审校与真实验收见 [独立切片工作流](references/independent-clips.md)。该分支接受 `lov-media-preprocessor` 的增强交接，避免重复调色；普通录屏流程保持原有审校方式。

示例一：

> 把这段录屏剪成视频号成片，保留最后有声音的成果段；第一遍只给我内嵌 SRT 的 MKV 和外置 SRT，我用 Subtitle Edit 改完确认后，再生成平台 MP4。

输入是源视频、可选 BGM 和明确的关键证据段；Remotion Studio 是主预览。需要 Subtitle Edit
修正字幕时，额外输出审校 MKV + 外置 SRT；第二阶段才输出批准字幕归档母版、平台成片、EDL、
各平台槽位的正式封面图片、质检 JSON 和交付报告。

## 字幕审校门

Remotion Studio 负责画面、节奏、声音、BGM 与当前字幕的主预览。只有需要 Subtitle Edit 修正字幕时，
`review` 阶段才把 SRT 作为 MKV 的默认 SubRip 轨封装；状态是
`review-ready / awaiting-review`。作者可在 Subtitle Edit 中改文字、断句和时间码。只有明确确认后，
先把作者 SRT 同步回 Remotion 预览复核，`approve` 阶段才以 stream copy 替换字幕轨生成归档 MKV，
并按平台生成 MP4 或平台 CC 字幕。

```bash
python3 scripts/subtitle_gate.py review --help
python3 scripts/subtitle_gate.py approve --help
```

MKV 是 Subtitle Edit 字幕修正与归档容器，不是通用预览。即使平台允许上传 MKV，也不等于会保留内嵌字幕轨；平台交付默认使用
兼容性更稳的 H.264/AAC MP4，字幕按平台选择 CC 或批准后烧录。

## 快速迭代

每轮先比较 `iteration-previous.json` 与 `iteration-current.json`，再按计划只运行失效 stage：

```bash
python3 scripts/iteration_plan.py plan \
  --previous work/iteration-previous.json \
  --current work/iteration-current.json \
  --output work/iteration-plan.json
```

字幕或布局修改复用源代理；BGM 修改复用视频母版；封面修改不触碰视频。长任务前先跑局部 canary，
并用 `iteration_plan.py record` 把实际墙钟写入 `iteration-timings.json`。完整契约见
[`references/iteration-performance.md`](references/iteration-performance.md)。

## 叙事片多曲配乐

Vlog、旅行、纪录和宣传片不套用系列默认曲。用户给的曲库整体可用，不按对话里点名的几首收窄，只以成片效果取舍；
作者点名的曲目先按作者建议的位置试，选曲按这一段当时的真实心境。每条 cue 写明叙事或情绪理由；配乐默认从头连到尾，
一首放到下一首接手，口播只压低不停歌，静默只给作者要求的段落，交付前扫音乐 stem 上 2 秒以上的断档。同语种歌词
默认不压对白，只有作者明确点名该曲垫对白、或明确说不为口播停歌时才有条件放行：cue 上记理由与作者原话，放行句
按组求 CER 均值对比纯人声底线，逐句差值只排抽听顺序；歌词默认避开屏幕字卡。
人声与音乐不必互斥：每个时刻选 `clear`（音乐让开）、`blend`（音乐在人声下持续在场）或 `feature`（音乐主导），
段落之间留足气口，不用一串 3–5 秒字卡连续推进。局部都合规的片子仍可能碎成马赛克：以场景为单位、少换曲、
agent 自发的修改只做减法（作者点名的补充照做并记录），并用 `cut_metrics.py` 测量画面与配乐的碎片化（上限为暂定值，默认只报警）。

```bash
python3 scripts/bgm_tracks.py --library MUSIC_DIR --output work/music/tracks.json --summary work/music/tracks.md
python3 scripts/validate_cues.py --cues work/music/cues.json --tracks work/music/tracks.json --film work/music/film.json
python3 scripts/smr_check.py --voice work/audio/voice.json --cues work/music/cues.json --tracks work/music/tracks.json
python3 scripts/score_mix.py --voice work/audio/voice.json --cues work/music/cues.json --tracks work/music/tracks.json --out-dir work/audio/mix --stems
python3 scripts/intelligibility.py --mix work/audio/mix/final-mix.wav --srt subs.srt --floor work/audio/mix/stem-voice.wav --output work/music/cer.json
python3 scripts/cut_metrics.py --film work/music/film.json --cues work/music/cues.json --json work/music/cut-metrics.json
```

门禁是防止听不清的底线，数值为校准参考：cue 表 0 ERROR（作者放行的歌词冲突除外，列入放行清单）；语音频段 SMR 按意图判定（`clear` 中位数 ≥ 16 dB、p10 ≥ 8 dB，
`blend` 中位数 ≥ 10 dB、p10 ≥ 4 dB，`feature` 只记录）；逐条字幕切片转写的平均 CER 比纯人声底线高出不超过 0.02；
母带线性处理到 `-16 LUFS-I / -3 dBTP`，给 AAC 编码后的峰值回升留余量。数据格式与规则见
[`references/audio-mix.md`](references/audio-mix.md)。

示例二：

> Create a publish-ready 16:9 video from this screen recording. Keep the real result audio and separate rendered, audio, creative, and publish status.

示例三：

> 直接读取这个 `.screenstudio` 工程，做横版和十分钟内的竖版；摄像头保持连续，动画不要遮住实际操作，重要产品用官网信息卡，最后列出全部素材与网址。

## 叙事长片、360 素材与多平台派生

旅行、纪录类长片另有五份参考：

- [`references/narrative-vlog.md`](references/narrative-vlog.md)：按设备盘点素材、校准拍摄时间、字卡只交代信息、现场口播剪点、照片与合照、人物口径（默认以“脸能否被认出”为界）、时间水印与片名 / 结尾卡。
- [`references/360-reframe.md`](references/360-reframe.md)：双鱼眼拼缝的四角角距检查、对话机位、整段复核与防抖、镜头内运镜、16:9 重投影。
- [`references/platform-variants.md`](references/platform-variants.md)：从锁定的首发版本派生第二个平台画幅，按帧号比 PSNR 回归、平台码率与派生版质检。
- [`references/review-page.md`](references/review-page.md)：素材多、跨设备、跨多天时从第一版起维护的分镜表与全量素材表审片页。
- [`references/remotion-pipeline-pitfalls.md`](references/remotion-pipeline-pitfalls.md)：Studio `from=` 偏移、音频软链接 404、渲染磁盘、亚帧片段、Whisper 提示词污染、打码等管线踩坑。

作者在线审片时由主 agent 直接改剪辑表、只重渲变动镜头并推进 Studio；多个 agent 各出一版再评审的长工作流以宿主允许子 agent 为前提，只在作者离线或明确要多方案比较时用，见 [`references/iteration-performance.md`](references/iteration-performance.md)「作者在线快速迭代」。

示例四：

> 把全景相机和手机拍的旅行素材剪成 vlog，先发视频号竖版，再出 B 站横版。

## Profile 契约

`skill.yaml` 声明 `user-profile/v1`。运行时读取用户、品牌、工作区、偏好和 `skills.lov-media-creator` 专属记录；长期偏好通过 `scripts/profile_store.py` 原子写回。源代码不保存个人绝对路径、凭据或临时素材位置。详见 [`references/user-profile.md`](references/user-profile.md)。

## 封面，和可选的开场静帧

**这是两个交付物**，平台把它们分给了不同场景，本来就不期待同比例：封面出现在主页九宫格
和聊天分享卡片（视频号 3:4），视频画面出现在信息流全屏播放（竖版通常 9:16）。

默认不制作开场静帧，也不再询问；但发布或 `platform-ready` 任务默认生成正式封面，并与渲染并行。只有用户主动要求视频内静态
首帧时，才另做一张与成片同画幅的图，把它作为渲染输入并执行画幅门禁。

视频号封面优先交给可用的 `lov-channels-cover`；未安装时回退到当前图像能力、`lov-image-creator` 或项目 Remotion `Cover` composition，不得把缺口拖到发布阶段。开场静帧不是它的一个比例档，把 3:4 封面当
9:16 首帧要裁掉左右 25%，标题组必然被切到。选「要」时，本 Skill 在渲染前跑
`scripts/check_opening_still.py` 判画幅，不一致时默认退出码 1，逼你显式选裁切、补边，
或另做一张同画幅的图，而不是渲染几分钟后从画面里发现。

## 交付质量门

- 成片可解码，画幅、帧率、编码和音频流符合目标平台。
- Studio 是主预览，加载当前权威字幕与最终音频；需要 Subtitle Edit 时，审校 MKV 恰有一个默认 SubRip 字幕轨，回抽后与外置 SRT 逐条一致；批准前不生成平台文件。
- 最终结果段连续且有原声；BGM 不遮挡人声或关键反馈。
- 叙事片配乐混合多首且每条 cue 有理由；配乐从头连到尾、音乐 stem 无 2 秒以上断档，口播只压低不停歌；同语种歌词默认不压对白，作者明确放行的冲突在 cue 上记理由与作者原话并列入报告，放行句按组求 CER 均值对比纯人声底线；按时刻声明混音意图，SMR 与全片 CER 底线通过，母带留到 `-3 dBTP`；碎片化指标对照暂定上限报告，agent 自发的修改不让碎片指标上升。
- 首个平台发布前在编码成片上做隐私扫描（检测器逐帧、人工联系表不低于 5 fps）；已发布版本发现瑕疵时的处理见 [`references/delivery-contract.md`](references/delivery-contract.md)「发布前隐私扫描」。
- 章节标题由该幕实际内容证据归纳；知识传播类章卡默认留 1.8–2.4 秒，只显示章号和标题；顶部导航全程显示全部宏观章节。
- 竖版章节导航、标题、网址和关键控件避开 iPhone 状态栏、刘海 / 灵动岛与平台顶部导航；安全区由统一常量驱动，并用平台实机截图复核。
- 每个高风险切点做局部 ASR，最终连续人声做全片 ASR；不得残留独立口水词、错误重念或半句跳转。
- 摄像头在同一种正文形态中保持连续；解释动画结束后及时恢复真实操作画面。
- 开场先在 `auto` 模式判别：原片第一句已直接抛出问题或结果时直接开场，问题说清前不加 Highlights 或标题；原开场铺垫弱时才重组高光。用户可显式覆盖为 `direct` / `highlights`，并单独调整问题后标题。
- 用户给出的字幕 cue 只作语义锚点；需要高光时用 PCM 保留完整词头与句尾，并对实际渲染后的片段复核。
- Studio 与最终渲染可能分别使用 `video` / `img`；摄像头样式覆盖两者，终版从编码文件抽各布局联系表目视检查。
- 自研或重点产品使用官网事实源制作 4.5–5.5 秒信息卡；片尾资源页列出名称、完整 URL 与 BGM 来源。
- 上传弹窗、等待和卡顿只保留必要信息，不占据主体。
- 封面只保留用户批准的钩子主标题与系列标识，不再叠加解释型副标题；人物优先复用已确认的品牌职业照。
- 系列标识可用满宽底条但文字保持克制、稳定且低于主标题活跃度；主标题可按语义重音异字号破调，并通过信息流缩略图检查。
- `cover-brief.md` 只算方向稿；发布型交付必须存在平台各槽位的真实封面图片，并通过尺寸、
  安全区、四边条带与目视检查，才能写 `cover_status=approved / creative_status=passed`。
- 做了开场静帧时，抽出第一帧目视确认标题组完整、四边无黑条、音频没有整体前移。
- 报告分开记录 `render_status`、`audio_status`、`creative_status` 和 `publish_status`；
  开场静帧另记 `opening_still`、`opening_still_source` 和 `opening_still_fit`。

## 原子组合

做系列片的第二期及以后，先读 [`references/series-template.md`](references/series-template.md)：开场分支、逐章黑幕标题卡、片尾资源卡、章节进度条、字幕位置、气口处理、重点词、配乐同源、响度口径，每期逐条过。前一期的版式常量与进度条实现可以复用；BGM 不复用程序合成器，统一使用约定的 `Bright Lounge`。

`.screenstudio` + Remotion 项目另外执行 [`references/screen-studio-remotion-qc.md`](references/screen-studio-remotion-qc.md)，覆盖完整句、无静音钩子、摄像头连续性、官网产品卡、资源索引、连续 BGM 与 Studio 实播验收。

每个新 Skill 都带有 [`references/skill-composition.md`](references/skill-composition.md)，记录相邻能力、文件级交接和 Single Skill 决策。相邻 Skill 保持可选；发布型任务的正式封面是必需交付物，专用能力缺失时走本地回退路径。

## 系列工作区

栏目持续录多期时采用混合结构：顶层按 `episodes/epNN-topic/` 分期，每期内部固定
`sources/`、`work/`、`deliverables/`；真正跨两期以上复用的资产才进入根级 `shared/`。
这让一期可以整体归档，也让输入、过程和成品的生命周期保持清楚。

迁移旧工作区前先按内容、报告和媒体探测确认归属，不凭文件夹名猜；不明文件进入
`sources/legacy-*` 或 `work/legacy-*`，不在整理时删除。移动完成后更新脚本、报告和质检 JSON
里的旧路径，并回读既有成片。完整规则见 [`references/project-workspace.md`](references/project-workspace.md)。

## 可信度卡与用户案例

- [`skill-card.yaml`](skill-card.yaml) / [`skill-card.md`](skill-card.md)：用途、负责人、依赖、风险、输出与维度地图。
- [`cases/cases.json`](cases/cases.json)：真实 Input → Prompt → Output 证据。
- [`pricing-card.yaml`](pricing-card.yaml)：价值锚点、免费边界和复评条件。

## 质量门

```bash
python3 scripts/validate_skill.py .
python3 scripts/media_probe.py --help
python3 scripts/timeline_check.py --help
python3 scripts/audio_qc.py --help
python3 scripts/check_opening_still.py --help
python3 scripts/subtitle_gate.py --help
python3 scripts/iteration_plan.py --help
for s in bgm_tracks validate_cues smr_check score_mix intelligibility cut_metrics; do python3 scripts/$s.py --help >/dev/null; done
```

## 依赖

- Python 3.8+
- PyYAML（仅验证 Skill 结构时需要）
- FFmpeg 与 FFprobe（媒体处理与音频质检时需要）
- numpy（叙事片配乐分析、SMR 与混音需要）；mlx-whisper 或 openai-whisper（可懂度门禁需要），优先用已有的持久 venv 运行
- Pillow、Playwright 或图像工具（仅新封面资产需要）

## License

MIT

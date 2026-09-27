# Delivery Contract

成片交付由 Remotion Studio 主预览、文件、字幕批准、参数、创意判断和状态证据共同组成。字幕修正 MKV 不代表字幕已批准，单独存在的 MP4 也不代表已经发布。

## Required deliverables

- Remotion Studio 主预览：加载当前画面、最终音频/BGM 与当前权威字幕；报告记录 URL、主 Composition、字幕 SHA-256 和刷新验证；
- `review-vN.mkv`：仅在需要 Subtitle Edit 修正字幕时生成；画面不烧旁白字幕，内嵌一个默认 SubRip 字幕轨；
- `review-vN.srt`：仅在字幕修正流程中生成，与 MKV 同源的 UTF-8 外置字幕；
- `subtitle-review.json`：字幕修正 MKV/SRT 的流信息、条数、状态和 SHA-256；
- `subs-approved-vN.srt`：用户批准后的唯一权威字幕源；批准前不得出现；
- `master-vN.mkv`：以批准 SRT 替换字幕轨的归档母版，视频/音频 stream copy；
- `platform-<name>-vN.mp4`：目标平台文件；按平台采用批准字幕烧录或平台 CC；
- `cover_<ratio>.png` / `.jpg`：目标平台每个实际封面槽所需的正式图片；必须记录尺寸、哈希、
  安全区与目视结论。`cover-brief.md` 只能作为规划附件，**不能替代正式封面，也不能让
  `creative_status` 通过**；
- `first-frame.png`：仅在做了开场静帧时——从成片抽出的实际第一帧，用于目视确认；
- `edit-manifest.json`：源素材、时间线、保护段和混音策略；
- `iteration-plan.json`：本轮 phase、revision 变化、实际运行、缓存复用与阶段阻塞；
- `iteration-timings.json`：实际执行 stage 的墙钟记录；被复用的 stage 不伪造为 0 秒；
- `final-probe.json`：当前阶段媒体的视频、音频、字幕、时长、尺寸、帧率和编码信息；
- `audio-qc.json`：响度、峰值、采样率、声道和检查状态；
- `timeline-check.json`：**由脚本从 EDL 生成**的结构与时间码（片头分镜、片名卡、逐章黑幕
  标题卡、各章正文、片尾，加细章节与资源的成片时间码）。每张章标题卡记录语义标题、命名依据、
  起止帧和正文起点；报告和发布文案里的每个时间码都从这里抄，不手写、
  不从上一版文档抄——改片头长度会让全部时间码同时静默失效；
- `review-page`（素材多、跨设备、跨多天的叙事长片）：由剪辑数据生成的分镜表 + 全量素材表审片页及同版 CSV，
  从第一版起维护；Studio 快速迭代期不每轮更新，作者要看或进入 `locked` 时在同一链接更新；宿主没有托管
  页面能力时交本地 HTML；格式见 [`review-page.md`](review-page.md)；
- `request-list`（多轮审片项目）：作者提过的每条要求及状态（done / in-studio / pending + 原因），每轮汇报
  列出未完成项；
- `delivery-report.md`：人类可读的判断、证据和剩余缺口。

## Status fields

```yaml
render_status: review-ready
subtitle_status: awaiting-review
delivery_status: blocked-on-subtitle-approval
audio_status: passed
creative_status: passed
cover_status: approved
publish_status: not-requested
readback_evidence: []

# 仅在做了开场静帧时出现，缺一项就说明这版成片的首帧来源不可追
opening_still: true
opening_still_source: output/covers/e01/opening-still-1080x1920.png · v0.5
opening_still_fit: match  # match / crop:<比例> / pad
opening_still_hold: 1.5s
```

状态解释：

- `render_status=review-ready`：Remotion Studio 主预览可访问且加载当前字幕/最终音频；若进入 Subtitle Edit 流程，字幕修正 MKV 还须可解码且内嵌 SRT 与外置 SRT 回抽一致；
- `render_status=passed`：批准后的归档母版或平台文件存在、可解码，且媒体参数符合目标；
- `subtitle_status=awaiting-review`：字幕仍可编辑，不能称为最终成片；
- `subtitle_status=approved`：用户明确确认了报告所列 SHA-256 对应的 SRT；
- `delivery_status=blocked-on-subtitle-approval`：平台文件不得生成或交接；
- `delivery_status=approved-master-ready`：批准字幕已进入归档母版且质检通过；尚未请求或生成平台文件；
- `delivery_status=platform-ready`：批准字幕已按目标平台方式封装或烧录并通过质检；
- `audio_status=passed`：原声保护、混音、响度和峰值检查通过；叙事片多曲配乐还要求 `cue-check.json` 0 ERROR（作者放行的同语种歌词冲突在 cue 上写 `lyric_override`，报 INFO，`released` 即报告放行清单的来源，须附作者原话，放行句按组求 CER 均值对比纯人声底线，逐句只排抽听顺序并附抽听结论）、`smr.json` 全部通过、`cer.json` 的全片均值未超过纯人声底线的允许差值，音乐 stem 无 2 秒以上非作者要求的断档；
- `creative_status=passed`：标题、封面、叙事结构和证据段完成；
- `cover_status=missing`：没有封面图片；`brief-only`：只有方向稿；`rendered`：已出图但尚未完成
  尺寸、安全区、四边条带和目视检查；`approved`：所有目标槽位的正式图片均已验收；
- 发布型交付中，`creative_status=passed` 必须同时满足 `cover_status=approved`。用户明确不要
  封面时才可记 `cover_status=waived-by-user`；执行者不得用 brief、prompt、脚本或默认抽帧自行豁免；
- `publish_status=uploaded`：平台已接收文件，但线上可见性或回读尚未确认；
- `publish_status=published`：有平台回读证据支持，例如对象 ID、状态字段和成功标志；
- `publish_status=not-requested`：本次只制作成片，没有启动发布交接。

## Report minimum

报告至少记录：

1. 输入文件的可识别名称、源时长和源媒体参数；
2. 当前阶段（draft / locked / approved）、目标规格与实际输出规格；
3. 被压缩、被跳过和被保护的时间段；
4. 开场请求策略、最终策略、判别来源与理由；是否使用 Highlights，以及问题后标题的文案和锚点；
5. BGM 文件名、ducking 规则和高潮段原声处理；叙事片另附 cue 表（每条的曲目、区间与理由）、声明的留白、
   混音意图区间与理由、各意图下 SMR 最低的句子、CER 与底线的差值、`cut-metrics.json` 的碎片化指标
   与上一版对比，以及母带 I/TP 与编码后 TP；作者放行的同语种歌词冲突清单（cue、区间、作者原话、放行句组的
   CER 均值对比）与音乐 stem 断档扫描结果；
6. 视频解码、时间线、响度、峰值和人工回看的结论；
7. 标题、封面文案、每个目标比例的正式图片路径/尺寸/SHA-256、目视结论和未验证假设；
8. 做了开场静帧时：静帧图路径与版本、画幅适配方式（裁掉多少 / 是否补边）、停留时长，
   以及一条明确前提——**这版成片的第一帧绑定了这一版静帧图，换图必须重渲染**；
9. 审校 MKV、外置 SRT、批准 SRT 的 SHA-256，以及字幕批准人/确认时间（如果已批准）；
10. 平台容器支持证据、验证日期和字幕交付方式（embedded / platform-cc / burned-in）；
11. 发布对象、回读时间和原始状态字段（如果发生发布）。
12. 有逐章黑幕卡时：每张卡的序号、语义标题、命名依据、停留时长、卡片起点和正文起点；另记
    “没有切进 cue / 音画字幕累计偏移一致”的验证结论。
13. 本轮 changed domains、实际运行和复用的 stage、总墙钟与最长 stage；普通 draft 超过 15 分钟时，
    必须基于 timing 报告解释具体等待链。
14. 多平台版本：每个平台文件的码率与平台建议值（视频号建议 ≤ 10 Mbps；B 站无码率上限，交渲染出的原码率
    H.264/AAC MP4）、派生版本与首发版本的时长 / 响度 / 真峰值对照，以及发布前隐私扫描的检测器范围、人工
    联系表密度和处理清单。
15. 交付文件链接：报告内写相对本期目录的路径；回复作者时给绝对路径，或用宿主的文件发送能力直接发文件，
    不写依赖脚本运行目录的相对路径。

## 发布前隐私扫描

首个平台版本发布前，扫完最终编码 MP4 的全片：二维码、人脸、车牌这类能自动检测的目标逐帧跑检测器；人工看的
联系表不低于 5 fps（间隔 0.2 秒）。范围是每个镜头在时间线上实际用到的区间，含叠化尾巴；要查的有：作者点名
不出镜的人、按作者口径需要处理的人脸、收款码与二维码、车牌、电话号码、票证上的实名与证件号、屏幕上的订单
或聊天、遗照。结论以实际渲染画面为准，不以镜头备注里的“只用到 X 秒”代替。发现问题在渲染层按时间段打码后
再发布，技法见 [`remotion-pipeline-pitfalls.md`](remotion-pipeline-pitfalls.md)「打码」；检测器范围、人工密度
和处理清单写进报告。派生其他平台版本时，对新画幅再扫一遍。观测实例（冈仁波齐转山 vlog）：首版只抽关键帧
就交付，一处不到 1 秒闪过的二维码直到派生第二个画幅复核时才被发现。

### 已提交或已发布的版本发现瑕疵

这是本 Skill 关于已发布版本瑕疵的唯一正文，其他文件只指向这里。

- 默认不删、不改、不重发已发布条目，但必须附证据（截图与片中时间点）告诉作者，不能因为“已经发了”就不说。
- 按严重程度给选项，由作者决定：证件号、收款码、电话号码这类严重泄露，或作者点名不出镜的人露出可辨认的
  正脸，把“下架或替换”与“保持不动”的代价并列；轻微瑕疵（背影、远景小人、画面小错）默认建议保持不动，
  修正只做进还没发布的平台版本。
- 下架、替换、重发都是发布动作，归 `lov-media-publisher`，作者确认后才执行；本 Skill 只负责告知、给选项，
  以及把修正做进未发布版本。
- 观测实例：派生版复核时回头扫到首版里有一处不到 1 秒的第三方收款码；按上面的流程附证据告诉作者、给出选项，由作者决定，派生版照常打码。

## Handoff boundary

交给发布 Skill 时只发送 `subtitle_status=approved`、`delivery_status=platform-ready` 且
`cover_status=approved` 的平台文件、正式封面图片、标题、简介/标签、批准 SRT（平台支持 CC 时）
和交付报告。正式封面必须由 Creator 在交接前解决；专用封面 Skill 缺失时走图像或 Remotion
回退，Publisher 不负责补图。只有 `cover-brief.md` 时不得进入发布交接。审校 MKV 不得进入发布交接。账号、
Cookie、验证码和平台内部令牌留在运行时，不进入源目录或报告。发布 Skill 返回的状态与回读
证据再写入交付报告的 `publish_status` 区域。

做了开场静帧时多一条约束：**上传的封面与首帧必须共用同一套视觉语言**。它们是两个不同
画幅的文件，不可能是同一张图，但观众会连着看到——列表页一张、点开第一帧另一张——两者
风格不统一就像两个来源。在报告里点名两个文件的路径与版本，不要只写「已附封面」。

上游边界在「封面已定稿」。发现 `lov-channels-cover` 时使用其钩子、风格锁定与整墙门禁；
未发现时改走可用图像能力或 Remotion 回退，并保留同等尺寸、安全区与目视验收。

**首帧不是封面的一个比例档**：平台把封面（3:4，主页九宫格与分享卡片）和视频画面
（竖版普遍 9:16）分给了不同场景，本来就不期待同比例。需要首帧时单独设计一张 9:16 图，
不要为此给 `lov-channels-cover` 加比例档。

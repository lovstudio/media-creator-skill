# Changelog

## [0.20.0] - 2026-09-28

### Added

- SKILL.md frontmatter 新增顶层 `dependencies:`，把免费的 `lov-media-publisher` 声明为 lovstudio CLI 的安装预检项：`npx lovstudio skills add media-creator` 会列出这项可选搭配，加 `--with-deps` 才安装。`depends_on` 仍只有 `lov-branding-consistency`，不强制安装发布能力，也不把它内嵌为 Kit 模块。
- validate_skill.py 放行并校验顶层 `dependencies`（每项必须是 {name, check, install}），新增 tests/test_validate_skill.py 的 5 个测试。生态侧同步放行：skill-publisher-skill 0.7.7（lov-skill-publish 第 1 步的 source 校验）与 skill-creator-skill 4.6.5，否则 0.20.0 无法走正式发布流程。
- README 新增「可选搭配：视频分发助手（免费）」，写明它需要 ego-browser、已登录的创作者账号和 macOS 通知，以及两条安装路径的差别；skill-card.yaml 与 skill-card.md 的依赖清单同步加上这一项。

### Changed

- Step 1.5 的发布交接改为：宿主能发现 `lov-media-publisher` 且作者要求发布时才交接，交接门禁与 delivery-contract「Handoff boundary」一致（字幕已批准、`platform-ready`、封面已批准）；发现不了就停在 `platform-ready`、不启动交接（`publish_status` 保持 `not-requested`），作者要求过发布时在报告里写明「未发现发布能力」并给出能用的安装命令 `npx skills add lovstudio/media-publisher-skill -g -y`。
- skill-composition.md 的相邻能力表、Atomic Handoffs、Overlap Decisions 与 Composition Decision 同步上述边界（三处门禁都含封面已批准），并记录不用 `depends_on`、不做 Kit 内嵌的原因：强制安装的是目录 `skills.yaml` 的 `depends_on`。
- 可选发布的环境说明放在 metadata.compatibility，顶层 `compatibility` 保持 406 字符（规范上限 500）。frontmatter 的 metadata.tags 改为单行列表，内容不变；SKILL.md 为 494 行。

### Verification

- 本 Skill、skill-publisher（`--target source`）与 skill-creator 三个校验器都通过；同一份 SKILL.md 把预检项改成缺 install、带未知键时，三者都报同一条错误。原有测试与新增 5 个测试共 67 个全部通过。
- 用 lovstudio CLI 依赖的 yaml ^2.8.3 按 `readSkillFrontmatter` 的方式解析新 frontmatter：识别为 1 项预检；check 在本机（已装发布能力）返回满足，在空 HOME 下返回缺失，会打印安装提示。
- lint_skill.py 0 错误 0 警告；新增一条 info LOCAL_AGENTS_PATH，来自预检的 check 路径 `$HOME/.agents/skills/…`，与 CLI 的 `globalSkillDir()` 一致，属预期。
- 目录仓库 lovstudio/skills：media-creator 与 media-publisher 加双向 `related`，validate_deps.py 通过，重新渲染的 README 只变这两行。

## [0.19.0] - 2026-09-27

### Added

- validate_cues.py 新增 cue 级歌词放行字段 lyric_override: {reason, author_quote}：作者明确点名该曲垫对白、或明确说不为口播停歌时，同语种歌词压对白从 ERROR 降为 INFO，输出新增 released 列表（cue、合并后的冲突区间、秒数、理由、作者原话），直接作为交付报告的放行清单；缺理由或原话仍判 ERROR，lyric_override: true 这类简写不放行。
- validate_cues.py 新增 --preset narrative：未声明无乐段上限默认 2 秒，对应叙事 vlog 配乐从头连到尾；显式 --max-gap 仍优先，不带预设时保持 6 秒。
- cut_metrics.py 的 shots 支持 "flashback": true：回忆段镜头不计入拍摄时间倒跳，之后从最后一个当下镜头接着算（回忆段后的真实倒跳仍计入），另报 flashbacks 段数。
- score_mix.py 的 level_db 新增电平基准 level_ref："cue"（默认，按 cue 截取片段，行为不变）、"track"（整首）或 [t0, t1]（曲内参考窗口）；可写在 cue 上、表头或用 --level-ref cue|track 指定（smr_check.py 通用），整首与窗口电平按曲目缓存只解码一次；mix-report.json 每条 music 记录 level_ref 与 ref_rms_db。
- tests/test_bgm_scoring.py 新增 11 个测试：歌词放行与不完整放行、叙事预设（含 CLI 端到端与 --max-gap 覆盖）、回忆段倒跳、换曲交叉淡化默认值、level_ref 窗口解析、优先级与实际增益。

### Changed

- cut_metrics.py 的 --min-change-xfade-s 默认从 3 秒改为 1 秒，与 validate_cues.py 的交叉淡化下限一致。依据是作者接受的冈仁波齐终版：10 次换曲交接为 1.0–3.0 秒（中位 1.5 秒），旧默认对其中 9 次报 WARN。v0.4 计划里的 3 秒只作设计起点，要按它查时显式传 --min-change-xfade-s 3。
- 文档同步：audio-mix 的歌词放行、断档检查、换曲交叉淡化、数据契约、level_db 基准、门禁命令与通过标准；narrative-vlog 的回忆段；delivery-contract 的 audio_status；SKILL.md 与 README 补上 lyric_override 与 --preset narrative。SKILL.md 全部为同行替换，仍为 499 行。0.18.0 Known limitations 的前三条已解决。

### Verification

- 在冈仁波齐终版（v0.8，827 秒，11 条 cue）上只读回归，输出只写临时目录，项目文件未改动：原 cue 表仍报同样 4 条同语种歌词 ERROR（向后兼容）；副本加 lyric_override 后 0 ERROR，4 条进入 released；--preset narrative 不报断档（终版最长无乐 0.2 秒）；cut_metrics.py 新默认下换曲交叉淡化告警从 9 条降为 0；按整首测电平时，只用前 70 秒的 M2-day1 比按片段测低 6.8 dB，M1n-night 低 4.4 dB。
- 62 个单测全部通过；validate_skill.py 通过。

### Known limitations

- level_ref 默认仍是 "cue"，保证旧 cue 表的混音不变；只截安静局部的 cue 要显式写 "track" 或参考窗口。validate_cues.py 不检查 level_ref，写错时 score_mix.py 与 smr_check.py 会带说明退出。
- intelligibility.py 还不读 released，放行句按组求 CER 均值仍需手工按区间挑句。
- 360、平台码率与审片页里的数值只来自一台双鱼眼相机、一部片和当时的宿主工具，换机型、ffmpeg 版本或宿主都要重测。SKILL.md 为 499 行，已贴近 500 行上限。

## [0.18.0] - 2026-09-27

吸收《我所看见的冈仁波齐》转山 vlog 的创作经验：旅行叙事片、360 重投影、横竖双平台派生与发布前隐私扫描。

### Added

- 新增 references/narrative-vlog.md：按设备盘点素材，空目录主动报告，交付报告附素材对照表；逐设备校准拍摄时间；字卡只交代信息，文章独白不进字幕；现场口播用语音频段包络定剪点并逐句回转写；手机照片逐张审，合照放到人物出场处；回忆段用作者当年的旧素材，获取交给 lov-media-crawler / lov-media-fetch / lov-wdb-cli；人物口径默认以“脸能否被认出”为界；作者有品牌 logo 时的片名卡、REC 时间水印与结尾卡。
- 新增 references/360-reframe.md：拼缝检查改为取景窗四角到光轴的角距 arccos(cos pitch · cos Δyaw)，符号都有定义；对话场景先认人再定机位；整段复核与 vidstab 防抖；ffmpeg 9 v360 sendcmd 的增量语义；16:9 重投影，脸在横版里不明显大于竖版（约 1.2 倍以内）。
- 新增 references/platform-variants.md：从锁定时间线派生第二个平台画幅，包括缓存隔离、醒目占位、按帧号比 PSNR 回归、独立版式常量、平台码率和派生版质检。
- 新增 references/review-page.md：分镜表 + 全量素材表审片页，从第一版起维护；Studio 迭代期不每轮重发，作者要看或进入 locked 时再更新；宿主没有托管页面时回退为本地 HTML；体积上限标为观测实例。
- 新增 references/remotion-pipeline-pitfalls.md：Studio from= 偏移、音频软链接 404、渲染磁盘、PID 等待、亚帧片段、补丁脚本断言、Whisper 提示词污染与繁转简、找回原图、车牌与收款码打码。
- delivery-contract：新增 review-page 与 request-list 两项交付物、报告第 14–15 条，以及「发布前隐私扫描」（检测器逐帧，人工联系表不低于 5 fps）。已发布版本发现瑕疵的处理以这里为唯一正文：默认不删、不改、不重发，但必须附证据告诉作者，按严重程度给选项，由作者决定；下架或重发归 lov-media-publisher。
- iteration-performance 新增「作者在线快速迭代」与「多 agent 批量复核」（以宿主允许子 agent 为前提）；cover-and-title 新增片名优先级与「改编作品与叙事片封面」；skill-composition 补上 lov-media-crawler、lov-wdb-cli、lov-voice2srt 的交接，以及发布字段预填的交接；skill.yaml 新增 records.people_privacy_scope；cases.json 新增 kailash-kora-travel-vlog 案例，含素材对照表，发布状态如实记为视频号 platform_pending、B 站已退回（作者已申诉，结果待回读）。

### Changed

- 叙事片配乐默认从头连到尾：一首放到下一首接手，口播只压低不停歌，这条在叙事片里覆盖 Step 4 第 3 条与 audio-mix 基本策略的暂时静音；静默只给作者要求的段落；交付前扫 score_mix.py --stems 输出的 stem-music.wav，2 秒以上的断档要补，极轻前奏按例外注明。撤回 0.15.0 起“身体到极限、独白可以留白”的写法。作者自己唱歌、呐喊写进 voice.json 按口播句处理，不走 ambient 总线。
- 同语种歌词压对白从一律避让改为有条件放行：只在作者明确点名该曲垫对白，或明确说不为口播停歌时放行，cue 上记理由与作者原话，并列入报告的放行清单。可懂度仍只按全片配对均值判定；放行句按组求 CER 均值，与纯人声底线对比，逐句差值只用来排抽听顺序。
- 选曲按当时的真实心境和作者建议的位置；“修改只做减法”限定为 agent 自发的修改；换曲交叉淡化 3 秒改为 cut_metrics.py 的默认下限（终版实测 1–3 秒，中位 1.5 秒）；暂定碎片上限补记 v0.4 的正面反馈，以及终版超限但被作者接受的数据；补充 env 包络的 np.interp 语义，以及 level_db 按片段归一的坑。
- 作者在线审片时由主 agent 直接改剪辑表、在 Studio 迭代，不默认启动多 agent 长工作流。作者说可以发布不等于字幕已批准：平台 MP4 仍需 subtitle_status=approved 与对应 SRT 的 SHA-256。
- 片名优先级：用户逐字给定的片名 > 已发表文章的标题 > brief 主题句。视频号封面创建页只有一个 3:4 槽；B 站有 4:3 与 16:9 两个独立槽。作者已选用的封面优先于 lov-channels-cover 的风格锁定，风格锁定只在需要新做封面时套用。
- 平台码率：视频号按建议 ≤ 10 Mbps 一次出，并写全 bt709 三项；B 站交渲染出的原码率 H.264/AAC MP4，不为码率重压。
- 不在每轮回复里重复提示授权，但曲目与来源照常记在 cue 表、交付报告或片尾资源页。
- SKILL.md 描述与 Triggers 补上旅行 Vlog、全景素材、先竖版再横版的触发语，Step 0 路由到五份新 reference，全部为同行替换，行数仍为 499。README 新增“叙事长片、360 素材与多平台派生”一节与示例四。skill-card 同步 use_case、Known Risks、references 与 User Cases，Known Risks 新增两条：首发版本漏掉的隐私画面，以及 360 跨拼缝与横版新露出的区域。

### Known limitations

- validate_cues.py 没有 cue 级放行字段，作者放行的同语种歌词冲突仍判 ERROR，靠报告的放行清单说明；--max-gap 默认仍是 6 秒，叙事片要显式传 2。
- cut_metrics.py 的 --min-change-xfade-s 默认仍是 3 秒，会对已接受的 1–3 秒交接报 WARN；进入回忆段会被计成一次拍摄时间倒跳。
- score_mix.py 的 level_db 仍按 cue 截取的片段归一，只截安静前奏的 cue 会被抬高，需要手工改 gain_db。
- 360、平台码率与审片页里的数值只来自一台双鱼眼相机、一部片和当时的宿主工具，换机型、ffmpeg 版本或宿主都要重测。
- SKILL.md 为 499 行，已贴近 500 行上限。

## [0.17.0] - 2026-09-26

### Added

- 新增叙事片碎片化门禁：作者判冈仁波齐 v0.3“片段与 bgm 切来切去的，太琐碎，叙事感太差”（重复抱怨），v0.3 比 v0.2 各项碎片指标都更高；规定以场景为单位、写五句以内主线、画面与配乐同表设计、换曲只在章节或场景边界且交叉淡化 ≥ 3 秒、修改只做减法。
- 新增 cut_metrics.py：量 ASL、短镜头、素材切换、拍摄时间倒跳、字卡、cue、曲目、换曲、cue 中位长度、每章曲目数与非边界换曲；v0.4 计划的上限作为暂定值默认只报警，--strict 才失败；--baseline 拒绝让碎片指标上升的修改。在 v0.2 / v0.3 上与项目脚本逐项一致。
- 纠正 0.16.0 把被否决的 v0.3 过渡做法写成“起始值”：改为反面证据，并注明 v0.3 的 SMR 下限只说明人声能听清、不证明结构成立；多曲混合改为“多曲但少换曲”。

## [0.16.1] - 2026-09-26

### Fixed

- 更新冈仁波齐导演剪辑版 v0.3 的可懂度证据：改用逐条测法重测为混音 0.242 / 底线 0.250（−0.008），旧整片测法的 −0.037 标为作废；两部片都落在 −0.008 附近，并说明差值最大的两句属于识别噪声而非遮蔽。

## [0.16.0] - 2026-09-26

### Added

- 按冈仁波齐导演剪辑版 v0.3 校准叙事片配乐（门禁全部通过但尚未听审，数值标为暂定）：feature 深度改为 -4/-3 dB，意图之间 0.8 秒居中平滑，口播句可自带 intent 让 J-cut 保持本段深度，blend 句增加 p10 ≥ 4 dB。
- 声明的留白改为强制：留白开始 2 秒后仍有音乐在响，validate_cues.py 判 ERROR。
- 新增剪辑节奏提示（WARN）：字卡阅读时长 max(2.2, 字数/4.5+0.6)、段落最后一字后不足 1 秒就切、连续 3 段以上短于 4 秒、章节以硬切开场；参考文档记录 v0.3 的溶解、dip、停留与间奏长度。
- 修复同源环境声整段丢弃导致句尾数字静音：改为只静音口播用到的源时段和本句时段 ±0.3 秒；环境声总线单独 -10 dBFS 限幅，避免母带限幅器抽吸音乐。
- 可懂度门禁改为逐条字幕切片转写并加简体中文提示：整片转写会被窗口内别处的音频改变结果（同一句本段音频不变，差值从 +0.012 跳到 +0.024）；旧测法的底线 JSON 不再接受。
- 意图平滑改用累积和滑动平均，并在参考文档记录长窗口 np.convolve 的 O(N·k) 性能坑。

## [0.15.0] - 2026-09-26

### Added

- 新增叙事片多曲配乐流程：Vlog、旅行、纪录与宣传片从用户整个曲库选曲，按章节与情绪混合多首，每条 cue 必须写叙事或情绪理由；录屏与知识系列仍默认 Bright Lounge。
- 歌词门禁：与对白同语种的演唱歌词不得压在对白下（中文对白下不放中文歌词），歌词默认避开屏幕字卡，只有歌词本身是这一刻的意义时才标 lyric_feature；无 LRC 的曲目按歌词未知处理。
- 混音意图：人声与音乐不必互斥，按时刻声明 clear / blend / feature，ducking 深度随意图 250 ms 渐变切换；留白写进 silences；段落过渡留气口，连续 3 张以上短字卡报 WARN。
- 新增脚本 bgm_tracks.py、validate_cues.py、smr_check.py、score_mix.py、ducking.py、intelligibility.py：整库分析、cue 校验、按意图分档的语音频段 SMR、Whisper CER 对比纯人声底线（temperature 0、剔除重复循环幻觉），数值作为校准参考。
- 混音引擎：150 ms look-ahead 双段 ducking（整体 -13 dB + 语音频段额外 -8 dB）与 look-ahead 峰值限幅；线性母带（限幅、ebur128 测 I/TP、单一静态增益），不用 loudnorm 做母带，母带留到 -3 dBTP 以吸收 AAC 编码后的峰值回升。
- 运行环境说明：优先用已存在的持久 venv 运行 numpy / Whisper 脚本，不依赖可能被清理的 uv 缓存；skill.yaml 登记 bgm_multi_track Profile 记录。

## [0.14.1] - 2026-09-07

### Fixed

- 根据用户反馈，将同场分段发布统一合集、统一编号及发布后成员回读列为独立切片交付要求。

## [0.14.0] - 2026-09-07

### Added

- 将整场课程和多人交流的独立切片流程工具化：全片取舍、源区间去重、帧/样本级裁切、词级转录与字幕草稿、实际审校锁定。
- 新增连续音乐床、一次混音、AAC 时钟与声学对齐验证，以及注入素材/字体/品牌的 Remotion 正片与双比例封面模板。
- 提供可恢复批处理、输入哈希失效检查、实际 MP4 和可点击交付列表；复用预处理增强文件，不重复调色。

## [0.13.3] - 2026-09-07

### Fixed

- 中文展示名由「视频工坊」改为用户指定的「天才剪辑师」，同步 SKILL、README 和 Skill Card；保留英文名、调用 ID 与能力契约。

## [0.13.2] - 2026-09-07

### Added

- 统一展示名为「视频工坊」，保持调用 ID 与能力契约。

## [0.13.1] - 2026-09-01

### Fixed

- prioritize video channel platform renders
- render and fully QC video channel 9:16 before deriving Bilibili 16:9
- run full platform renders sequentially unless a short-window benchmark proves parallel is faster

## [0.13.0] - 2026-09-01

### Added

- add a machine-readable incremental iteration planner and wall-clock timing recorder
- split production into draft, locked, and approved phases with explicit cache scopes
- add seam, visual, and audio canaries before long-running final work

### Changed

- keep source proxies stable across EDL, subtitle, layout, BGM, platform, and cover revisions
- defer full continuous mezzanines, final mix, full-track ASR, final render, and full QC to their phase gates

## [0.12.2] - 2026-08-31

### Fixed

- Generate platform covers by default for publish-ready runs
- Separate the always-on platform cover branch from the disabled-by-default opening still
- Fall back to available image tooling or Remotion when lov-channels-cover is unavailable

## [0.12.1] - 2026-08-31

### Changed

- choose between direct cold open and highlight montage before building the opening
- keep direct openings free of pre-roll titles, while allowing an optional title after the problem statement
- let the current request override `auto`, `direct`, `highlights`, and post-problem title settings

## [0.12.0] - 2026-08-30

### Added

- add final-render parity gates
- treat subtitle cues as semantic anchors and verify complete rendered hook sentences
- cover OffthreadVideo video/img divergence and require encoded webcam contact-sheet review

## [0.11.0] - 2026-08-29

- deprecate and prohibit the early programmatic BGM synthesis workflow
- make the authorized `Screen Studio Lo-fi / Bright Lounge` the default agreed BGM
- block audio delivery when the agreed asset is unavailable instead of synthesizing or silently substituting music

## [0.10.8] - 2026-08-28

- require the primary Remotion Studio composition to mount one final mix that is source-identical to the approved master audio
- keep raw microphone, system-audio, and BGM stems for diagnostics instead of rebuilding a second delivery-preview mix
- add Studio component-tree, loudness, peak, and audio-hash verification for preview parity

## [0.10.7] - 2026-08-28

- make Remotion Studio the primary picture, audio, BGM, and subtitle preview surface
- limit MKV generation to Subtitle Edit subtitle-correction handoff and archival master use
- require author-corrected SRT to be synchronized back into Remotion Studio before approval
- skip the opening-still question by default; only enable it when the user explicitly requests a video-internal still

## [0.10.6] - 2026-08-28

### Fixed

- require pitch-preserving time-stretch for accelerated dialogue and real system feedback
- forbid resampling-based speed changes, lock transformed audio to frame-derived sample counts, and require source-versus-output A/B listening

## [0.10.5] - 2026-08-26

### Fixed

- respect vertical platform chrome safe areas
- calibrate iPhone and WeChat top overlays with real-device screenshots and one shared Remotion inset

## [0.10.4] - 2026-08-26

### Fixed

- stabilize series marker hierarchy
- keep full-width series bars typographically restrained and allow readable serif selection from the series profile

## [0.10.0] - 2026-08-26

### Added

- harden Screen Studio and Remotion review workflow
- verify complete sentence boundaries with local and full-track ASR
- keep all chapter titles visible and remove teaser kickers from chapter cards
- add camera continuity, official-site product cards, resource index, and fresh Studio playback gates

## [0.9.0] - 2026-08-26

- promote `.screenstudio` bundles to first-class, read-only source projects with independent display, webcam, microphone, system-audio, pointer and keystroke tracks
- require sample-accurate PCM dialogue editing and adjacent-seam checks for fillers, false starts and self-corrections
- rank opening highlights with semantic conflict/result signals plus acoustic emphasis
- use one continuous media element per track in Remotion and mount one equal-duration BGM bed only after picture/dialogue lock
- make horizontal the primary composition and add a vertical composition by default when the locked cut is under ten minutes
- add a Remotion Studio preview gate before subtitle approval and platform rendering

## [0.8.3] - 2026-08-23

- make delivered review MKV paths immutable and require a new review version on reruns
- add `approve --expect-edits` so declared author edits cannot silently collapse back to the review baseline
- record review/approved subtitle hashes, mtimes, cue counts, and change state in approval reports
- require explicit author-SRT migration after timeline changes and frame proofs for burned-in platform files

## [0.8.2] - 2026-08-23

### Fixed

- classify FFmpeg and FFprobe as runtime requirements, not embedded Skill dependencies
- unblock self-contained WorkBuddy packaging without weakening runtime compatibility checks

## [0.8.1] - 2026-08-23

### Fixed

- require rendered cover assets for publish-ready delivery
- treat cover briefs as planning artifacts and add cover_status evidence gates

## [0.8.0] - 2026-08-23

### Added

- add semantic chapter titles and black opening cards
- recompute subtitle, audio, and delivery timestamps after inserted chapter cards
- record EP.03 sentence-boundary validation and review evidence

## [0.7.0] - 2026-08-23

### Added

- add subtitle-review MKV approval workflow
- package and verify editable SubRip tracks with subtitle_gate.py
- block platform output until the user approves the SRT
- document MKV archival and platform-specific MP4 handoff

## [0.6.0] - 2026-08-23

### Added

- 新增持续栏目的工作区契约
- 固定“顶层按期、期内按 sources / work / deliverables 分层”，并明确 shared 的提升边界
- 迁移旧工作区时要求先确认归属、不删除未知文件、修复路径，并在搬迁后回读媒体

## [0.5.0] - 2026-08-18

沉淀 EP.03 三轮返工暴露的判据，全部是「跑完全绿但成片是错的」那一类。

### Added

- references/pip-research.md：片中念到的三方产品，检索 → 官网 → 截 hero 区 → 画中画贴回去；
  位置只能量不能挑（三个候选区占比都在 30-34%，没有空区），晚于人声 0.35s 出现，必须有边框和域名条
- series-template.md 补齐响度、地址栏 OCR、多素材分块、画中画、字幕回灌等判据：
  - 响度口径：折混成单声道**只对峰值是假象**（等能量下混凭空报出削顶），**对 LUFS 是真的**（BS.1770-4 按加权能量求和，先折混再测比标准表低 3 dB）——两件事长得一样结论相反
  - 地址栏 OCR 四条判据：`--psm 12`/`--psm 6` 取并集、域名匹配按长度降序且 `i>=0`、用剩余英文单词数（≤3）判是否为地址栏行、原始 OCR 文本落盘缓存
  - 字幕回灌用 SequenceMatcher 而不是按序号（按序号会把几十条挂错画面）；按「与保留下来的人声段有没有重叠」过滤，否则被删段的 cue 会塌在切点上叠成一堆
  - 不能裁顶栏时画底板要量实际带高（菜单栏 vs 边缘空白），章节标签要排两遍并用真实字体测宽
  - 一个分块不许跨素材，成片帧数从盘上逐 clip 回读 `ffprobe` 再对总数下断言
  - 画中画裁切下界先躲第三方 IP 和真人脸（按饱和度扫，不是亮度）；单帧 PNG 输入不加 `loop=-1`，否则驱动 overlay 越过主输入结尾，编码永不停止
- 进度条颗粒度改为 3-10 幕（细章节太细只留给剪辑节奏与 B 站目录），分幕表只记起点，顶栏与发布文案读同一张表
- 身份块三面墙（字幕底板下沿 / dock 上沿 / 画面左缘）量并写成断言，dock 按亮度台阶扫（饱和度扫会被应用图标骗）

### Fixed

- 覆盖层底板一律全不透明：此前给身份块留 92% 是「它压在深色 UI 上」的假设，浅色界面下页面正文会透到标题背后
- 本期文案改成单一来源脚本读取，标题散在多个脚本各一份字面量会漏改，成片开头念旧标题而所有门禁仍是绿的
- 删用户点名内容要另立 CUT_SPEECH 表，断言方向与「防止误删」的 EXCISE 表相反，两种情况在成片里听起来完全一样
- 钩子出点：10ms 包络会漏掉比它粒度还短的句界，需要覆盖表 + 复量 + 转写反向验证
- 画中画裁切下界改成 `keep_out` 断言，不写成看似绝对行号实为分数的值，避免重抓截图后静默脱锚
- 改了 EDL 音频链或 `subs.ass` 后必须按顺序全部重跑；脚本互相不检查上游是否比自己新，改完不重跑会渲出上一版覆盖层
- 交付报告改为脚本生成，质检结论不许写死，产物缺失就印「未跑」

## [0.4.0] - 2026-08-17

### Added

- series-template.md 清单补到 14 条：**13 封面第二行（锚点条）永远是系列名**——它是系列在信息流里唯一稳定的识别锚点，主标题超宽也不许拿本期概括去换；**14 交付时间码由脚本从 EDL 重算**，不手抄上一版
- series-template.md 新增「交付时间码必须由脚本生成」：给出 src→out 映射的实现与两条断言，以及验证映射本身的办法（用上一版的 `body_out_start` 跑一遍必须精确复现上一版全部数字）
- series-template.md 新增「测响度不要让 ffmpeg 折混成单声道」：`-ac 1` 的下混是等能量的，dual-mono 母版会读高恰好 3.01 dB 并凭空报出削顶
- cover-and-title.md 新增两行文案的归属与「门禁拦下用户指定文案时写本期包装脚本」：monkeypatch `MAX_VISUAL_WIDTH` / `DISPLAY_TIERS` 后 `runpy` 调 render_cover，新字号档按可用列宽推导（`928 / 7.12em = 130px`），不改 skill 常量
- delivery-contract.md 交付清单加入 `timeline-check.json`

### Changed

- 清单第 1/2 条按 EP.02 修正：冷开场用 **2–3 个**高光镜头（一句 2.5s 撑不住 19 分钟演示片），片名卡从「1–2s」改为 **≥2.5s**（1–2s 读不完系列名 + EP 号 + 本期标题三行）

## [0.3.0] - 2026-08-17

### Added

- references/series-template.md：系列片每期都要过的成片标准清单（12 条硬性项）。写它的直接原因是 EP.02 初剪只做了「删空档 + 烧字幕 + 章标」就交付被退回——上一期的规范当时只活在那个仓库的代码里，规范不进 Skill 就等于没有规范
- Step 1 增加前置动作：系列片第 N 期（N>1）先读 series-template.md，再读前一期的工程代码；配乐/版式/进度条一律 import 复用而非重写
- Step 4 补进剪辑节奏口径：停顿检测用 10ms 粒度扫包络而不是只枚举大空档（实测语气词值 9.0s，死气值 216s）；静止停顿剪到 0.14s，有画面动作的停顿抽帧不删
- Step 4 补进重点词强调的上限规则与配乐同源要求

### Fixed

- 拼接密度高时（几百处人声切点）淡入淡出应缩到 ~6ms，30ms 会磨掉短句首尾辅音

## [0.2.1] - 2026-08-17

### Fixed

- 纠正首帧与封面的关系：两者是平台分开的两个交付物，不是一张图的两种比例
- 删掉「让 lov-channels-cover 增加 9:16 比例档」这条错误指引：视频号封面槽是 3:4（服务主页九宫格与分享卡片），视频画面竖版普遍 9:16（服务信息流全屏），平台本就不期待同比例，需要首帧应单独设计一张 9:16 图
- 标注 9:16 是主流与推荐而非硬门槛（4:3/16:9 也能发但在竖屏容器里被放大裁切），封面 3:4 则为创建页实测
- 术语与接口随之改名，避免名字本身教人拿错素材：`check_cover_frame.py` → `check_opening_still.py`，`--cover` → `--still`；交付字段 `cover_as_first_frame` / `cover_source` / `first_frame_fit` / `first_frame_hold` → `opening_still` / `opening_still_source` / `opening_still_fit` / `opening_still_hold`
- 画幅不一致的报错文案点明「若传的是 3:4 主页封面，那是拿错了素材」

## [0.2.0] - 2026-08-17

### Added

- 支持把封面作为成片首帧，并把 lov-channels-cover 定为视频号封面上游
- 新增 scripts/check_cover_frame.py：渲染前判定封面与成片画幅，不一致时默认拒绝，逼调用方显式选裁切/补边/回上游
- Step 1 用 AskUserQuestion 问清封面是并列交付物还是成片首帧；选首帧时封面成为渲染的前置条件
- references/cover-and-title.md 新增封面两种位置对照、画幅不匹配的三条路、音频垫等长静音、首帧停留下限
- 交付契约新增 cover_as_first_frame / cover_source / first_frame_fit / first_frame_hold 与 first-frame.png
- skill-composition 记录 lov-channels-cover 为视频号封面上游，边界在封面已定稿；新比例档属于那个 Skill
- 补齐 frontmatter compatibility 与 description 触发语，修 README 安装段

## 0.1.0

- Added a portable media-production workflow for screen recordings, demos, source audio and BGM.
- Added timeline, media-probe and audio-QC helpers with FFmpeg/FFprobe integration.
- Added a verified video-channel case covering protected result audio, shortened upload UI, BGM ducking and publish read-back.

---
name: lov-media-creator
description: >
  把整场课程/多人交流实录剪成独立切片，或把 MP4、Screen Studio 源工程、旅行 Vlog 与全景素材剪成 Remotion 成片；完成精剪、字幕、连续混音、动画、横竖版与封面。
  Use when editing recordings or .screenstudio projects into review or publish-ready videos.
license: MIT
compatibility: >
  Portable Agent Skills format. Requires Python 3.8+ and FFmpeg/FFprobe; narrative BGM scoring gates need numpy, and the intelligibility gate needs mlx-whisper or openai-whisper.
  Screen Studio source-project integration additionally requires Node.js and Remotion.
  Publish-ready runs require an image tool or a Remotion Cover composition for cover assets.
  视频号封面优先交给可用的 `lov-channels-cover`；缺失时必须回退，开场静帧仍默认关闭。
depends_on:
  - lov-branding-consistency
dependencies:
  - name: "lov-media-publisher（可选：发视频号 / B 站；需 ego-browser 与已登录的创作者账号，只剪辑不需要）"
    check: 'test -f "$HOME/.agents/skills/lov-media-publisher/SKILL.md"'
    install: "npx -y lovstudio@latest skills add media-publisher -y"
metadata:
  author: contributors
  version: "0.21.0"
  card_standard: lovstudio/skill-card/v1
  tags: [media-production, video-editing, ffmpeg, audio-mix, delivery-qc, cover-assets, opening-still, screen-studio, remotion]
  compatibility: "Python 3.8+, FFmpeg/FFprobe, numpy for narrative BGM gates, optional Whisper, Pillow or an image tool for cover assets; optional lov-media-publisher hand-off needs ego-browser and logged-in creator accounts, editing needs neither."
---

# 天才剪辑师 · Video Studio

把 MP4 录屏或 `.screenstudio` 源工程、演示素材、原声和 BGM 组织成两阶段视频交付：先提供可交互的 Remotion Studio 与字幕审校版本，再以用户批准的 SRT 生成归档母版和平台文件；同时交付剪辑清单、横竖版包装、正式封面图片和可回读的质检报告。叙事重点放在真实工作流和实际问题上，工具只作为过程中的一个环节出现。

## Triggers

### Activate when

- 用户说“从整场实录选出全部有传播价值的独立切片，剪得流畅并精包装”，包括未完整录下的分享与多人交流。
- 用户说“把这段录屏剪成视频号成片，保留最后有声音的成果段”。
- 用户说“压缩上传卡顿、加 BGM、做 16:9 封面，并给我质检报告”，或嫌 Vlog “bgm 太单一，按叙事混合多首配乐”，或“把全景相机和手机拍的旅行素材剪成 vlog，先发视频号竖版再出 B 站横版”。
- 用户希望把长录屏整理成有开场、问题、操作证据和最终结果的短视频。
- 用户提供 `.screenstudio` 源工程，希望重新控制摄像头位置、鼠标/快捷键、背景、音乐和画面包装。
- 用户要求结合 Remotion 做动画、转场、可视化解释、专业字幕、横竖版和封面。
- 用户要做一条第一人称讲自己产品或 Skill 的讲解片，片中引用已发布成片作佐证。
- 用户说“把已经录了几期的素材、work 和成片按期整理，后面还要持续做这个栏目”。
- 用户说“先给我内嵌 SRT 的 MKV，我用 Subtitle Edit 改完再出最终成片”。
- 用户明确说“把封面当第一帧”或“开头停一下再进正片”时，才启用可选开场静帧；否则直接跳过，不再提问。
- User asks to create a publish-ready video from a screen recording while preserving the original result audio.
- User asks for an opening still frame before the video body starts.

### Do not activate when

- 用户只要生成标题、正文或社交平台文案；交给文案或内容策略能力。
- 用户只要学习字幕、词汇注释或 ASS 人物卡；交给 `lov-subtitle-freedom-skill`。
- 用户只要章节进度条、透明章节层或剪映章节包；交给 `lov-video-chapter`。
- 用户已经有字幕批准后的平台成片，只要求上传并回读发布状态；交给 `lov-media-publisher`。

## User Profile (cross-session)

每次运行都读取 `skill.yaml` 声明的 `user-profile/v1`：用户语言与时区、品牌语气、工作区输出位置、共享偏好，以及 `skills.lov-media-creator` 下的 Skill 专属记录。解析顺序是当前请求、项目上下文、Skill 记录、共享偏好、用户/品牌 Profile、默认值。

用户直接说出的长期剪辑偏好或品牌事实，通过 `scripts/profile_store.py record --confirm` 写回 Profile，并在结果中报告保存路径。源代码保持可移植，不写入个人绝对路径、凭据或临时素材位置。完整契约见 [`references/user-profile.md`](references/user-profile.md)。

## Skill Group Composition
运行前阅读 [`references/skill-composition.md`](references/skill-composition.md)。相邻 Skill 只通过文件、JSON、字幕或成品视频交接，不作为此 Skill 的隐藏运行依赖。

## Workflow (MANDATORY)

**先按成片目标分支。** 整场课程、活动或多人分享要独立切片时，执行 [`references/independent-clips.md`](references/independent-clips.md) 与 `scripts/clip_batch.py`：全片取舍 → 精确区间 → 字幕复核 → 连续混音 → 锁定 → 批量包装 → 实际 MP4 验收。
该分支不强制系列编号、章节卡、官网卡或片尾资源页；全片增强可交给 `lov-media-preprocessor` 并复用其已验证 handoff，不重复提亮。已有明确全自动审校授权时，记录真实代理审核与依据后继续，不能写成用户逐条听审；发布授权与平台回读仍交给发布能力。其他录屏/Screen Studio 流程按以下步骤执行。

### Step 0: 解析运行环境
- 使用环境中的 `SKILL_DIR`；没有时从当前 Skill 上下文推断安装目录。
- 先验证 `$SKILL_DIR/scripts/media_probe.py`、`timeline_check.py`、`audio_qc.py`、`check_opening_still.py`、`subtitle_gate.py`、`profile_store.py` 与 `iteration_plan.py` 是否存在；叙事片多曲配乐另验证 `bgm_tracks.py`、`validate_cues.py`、`smr_check.py`、`score_mix.py`、`intelligibility.py`、`cut_metrics.py`。
- 再验证 media workflow、edit manifest、audio mix、cover/title、delivery contract 与 [`references/iteration-performance.md`](references/iteration-performance.md)；Screen Studio / Remotion 项目还要读取 [`references/screen-studio-remotion-qc.md`](references/screen-studio-remotion-qc.md)。
- 持续栏目或已有多期素材时，另外验证并读取 `$SKILL_DIR/references/project-workspace.md`；Vlog / 旅行 / 纪录等叙事片读 [`references/narrative-vlog.md`](references/narrative-vlog.md)，素材多、跨设备、跨多天的长片另读 [`references/review-page.md`](references/review-page.md)；作者第一人称讲产品或 Skill、引用已发布成片的讲解片读 [`references/explainer-film.md`](references/explainer-film.md)；含 360 素材读 [`references/360-reframe.md`](references/360-reframe.md)，派生第二个平台画幅读 [`references/platform-variants.md`](references/platform-variants.md)，Remotion / FFmpeg / ASR 管线踩坑见 [`references/remotion-pipeline-pitfalls.md`](references/remotion-pipeline-pitfalls.md)。
- 视频检查或渲染需要 `ffprobe` 与 `ffmpeg`。发布或 `platform-ready` 且没有已批准封面时，新图是必需项：立即启动封面分支。
- 永远不覆盖源视频、源音频或原字幕；输出先落到独立的 `deliverables` 或用户指定目录。
- `.screenstudio` 是只读源工程包：不得原地改写 `project.json`、`recording/*.m4s`、transcript 或事件文件。

手工运行脚本时：

```bash
export SKILL_DIR="/path/to/lov-media-creator"
```

每次调用都解析 `context.profile`。若用户明确提出要长期保留的剪辑原则、音频偏好或品牌事实，调用 `scripts/profile_store.py record` 并带 `--confirm`，随后简短报告保存路径。

### Step 1: 明确输入与成片目标
如果工作区混有多期素材、根级 `work` / `output` 或不明归属的旧成片，先按 [`references/project-workspace.md`](references/project-workspace.md) 做只读盘点，再移动文件。
默认结构是**顶层按期、每期内按生命周期分层**；不要在“全部按期”和“全部按媒介”之间二选一。
移动后必须更新工程代码、交付报告与质检 JSON 里的旧路径，并对现有成片做可读/解码回读。

记录以下事实，不替用户臆造内容：

1. 源视频、补充片段、原声轨、BGM、截图和已有封面；输入可为单个录屏、多个素材或一个 `.screenstudio` 源工程包。
2. 目标平台、画幅、预期时长、受众、发布标题、封面文案和字幕是否需要烧录或平台 CC。
3. 必须保留的证据段，尤其是最终结果播放、真实声音、状态回读或失败反馈。
4. 交付文件：Remotion Studio 主预览、批准后的归档母版、平台成片、封面、剪辑清单、音频/编码质检报告，以及可选的发布交接信息；只有需要 Subtitle Edit 修正字幕时，才增加审校 MKV + 外置 SRT。

目标包含发布或 `platform-ready` 时默认 `cover_required=true`；复用匹配当前平台且已批准的封面，否则在标题钩子与素材稳定后并行生成。仅预览任务可暂缓；只有用户明确不要才记 `waived-by-user`。这与 `opening_still=false` 相互独立。

跨平台任务默认以视频号为首个 production target：先制作、渲染并完整质检 9:16、1080×1920、
30fps、H.264、AAC 48kHz 竖版，首发前按 [`references/delivery-contract.md`](references/delivery-contract.md)「发布前隐私扫描」扫完编码成片（检测器逐帧、人工联系表 ≥ 5 fps）；
达到 `platform-ready` 后先核对交付约定，把“按约定派生”与“复用现有版本”连同工时交作者选，再从同一锁定时间轴派生并质检
B 站 16:9、1920×1080 横版（见 [`references/platform-variants.md`](references/platform-variants.md)）。两个全片渲染默认顺序执行，只有短窗 benchmark 证明并行能缩短总墙钟时才并行。两个画幅共用场景代码时的双画幅自检、已发布画幅静帧门禁与音频原样复制，见 platform-variants「同一条时间线，只换画面与版式」。
已发布版本发现瑕疵时按 delivery-contract 同节告知作者、给选项。明确请求或 Profile 有其他设置时，以当前请求为准。

#### Screen Studio 源工程是一等输入

输入是 `.screenstudio` 时，不先压成一个扁平 MP4。先只读解析 `project.json`、`recording-markers.json`、
`transcripts/`、`recording/channel-*-*.m4s`、`mouseclicks-*.json` 与 `keystrokes-*.json`，按 channel 重建：

- display：屏幕内容；
- webcam：独立摄像头，可逐段选全屏、右下角、侧栏、并排或隐藏；
- microphone：口播权威音轨；
- system-audio：系统反馈与演示原声；
- pointer/events：鼠标位置、点击与快捷键，用于 Remotion 的聚焦、缩放和提示动画。

先把工程事实写入 source manifest，再生成工作区内的可重建代理轨；源工程包保持原位。任何 channel 缺失、近乎静音、时间戳异常或事件不完整都要记为源素材事实，不用其他轨伪造。

**这是系列片的第 N 期（N>1）时，先读 [`references/series-template.md`](references/series-template.md)，
再读前一期留下的工程代码。** 那份文件是每期都要过的成片标准（开场策略、片尾资源卡、
章节进度条、字幕位置、气口处理、重点词、配乐同源、响度口径）。复用前一期的版式常量、
进度条实现与已确认 BGM 配置；**早期程序合成 BGM 已废弃**，不得 import 前作的配乐合成器。
不做这一步的后果是可预期的：只做「删空档 + 烧字幕」就交付，会被判为粗糙初剪，然后整期重做。
默认 `opening_still=false`：封面独立制作并与渲染并行，不再询问。只有用户主动要求视频内静态
首帧时，才将 `opening_still=true` 写入运行记录，并在渲染前确认同画幅素材与适配方式。

### Step 1.5: 读取相邻能力与交接边界

先看 `references/skill-composition.md`，判断是否需要可选交接：

- 章节条：交给 `lov-video-chapter`，输入为已确认的成品或字幕，输出为章节项目/透明层。
- 学习字幕：交给 `lov-subtitle-freedom-skill`，输入为成片或原字幕，输出为保持原时间轴的 SRT/ASS。
- 视频号封面：发现 `lov-channels-cover` 时优先交接；未发现则用当前图像能力、`lov-image-creator` 或项目 Remotion `Cover` composition 生成实际槽位图片，不得跳过。
- 通用配图或其他平台封面：交给 `lov-image-creator` 或当前图像能力，输入为封面方向 JSON 或文字 brief，输出为 PNG/可编辑 HTML。
- 视频来源获取：交给 `lov-media-fetch` / `lov-media-crawler`（平台旧视频先只解析元信息，作者同意再下载），本地社交缓存原图交给 `lov-wdb-cli`，输出为经过核验的本地素材；云端转写可交 `lov-voice2srt`，上传与计费先向作者说明。
- 视频号 / B 站发布：发现 `lov-media-publisher` 且作者要求发布时交接，输入为 `subtitle_status=approved`、`delivery_status=platform-ready`、`cover_status=approved` 的平台成片与交付报告，输出为终稿确认、发布状态与列表回读证据；未发现则停在 `platform-ready`、不启动交接（`publish_status` 保持 `not-requested`），作者要求过发布时在报告里写明「未发现发布能力」并给出安装命令 `npx skills add lovstudio/media-publisher-skill -g -y`（或 `npx lovstudio skills add media-publisher`）。
本 Skill 负责最终成片的编辑判断、音频完整性和交付门禁；可选下游不得替代这些验收。

#### 开场静帧：默认跳过，仅在用户主动要求时启用

**封面和开场静帧是两个交付物，不是同一张图的两种用法。** 视频号把它们分给了不同场景：
封面服务主页九宫格与分享卡片（2026-08-17 实测创建页只有一个槽，标签「个人主页和分享
卡片(3:4)」），视频画面服务信息流全屏播放（竖版普遍 1080×1920）。平台本就不期待两者
同比例。
封面默认是**并列交付物**，应与渲染并行，互不阻塞。但用户要求「开头停一下再进
正片」时，那一帧变成**渲染的前置条件**——它就是成片的第一帧，没定稿就没法渲染，改它
等于重渲染。
默认不询问并直接跳过；用户主动提出后再记录选择：

| 用户选择 | 后果 |
| --- | --- |
| 未主动要求开场静帧（默认） | 封面只做卡片，可与渲染并行，改封面不重渲染；不询问 |
| 要 | 需另做一张与成片同画幅的图，先定稿；每次改它都要重渲染 |

把 3:4 封面直接当 9:16 首帧要裁掉左右 25%，标题组必然被切到。这不是工具缺一个比例档，
而是**拿错了素材**——`lov-channels-cover` 只负责封面，不该为此长出 9:16 档。三条路，
按代价从低到高：

1. 另做一张与成片同画幅的开场静帧，与封面共用视觉语言但各自适配安全区；
2. 接受裁切，但裁完必须目视确认标题组完整，并把裁掉的比例写进交付报告；
3. 放弃开场静帧，只交封面（默认，多数情况下是对的——封面已经承担了让人停下来的职责）。

**不要在本 Skill 里用 scale/pad 硬凑**：补边或拉伸会毁掉第一印象，而且渲染完才看得出来。

### Step 2: 扫描素材并建立编辑清单
先运行：

```bash
python3 "$SKILL_DIR/scripts/media_probe.py" \
  --input SOURCE_VIDEO \
  --output WORK_DIR/source-probe.json \
  --pretty
```

读取时长、分辨率、帧率、编码、音频声道、采样率和字幕流。长录屏先按真实内容找出“结果/承诺、问题、关键操作、证据、最终结果”几个节点，再写入 [`references/edit-manifest.md`](references/edit-manifest.md) 所定义的 EDL；不要按固定时长机械切段。

`.screenstudio` 不能把目录直接传给 `media_probe.py`：先为 EDL 命中区间建立只随源素材失效的低码率代理分片，
再逐轨 probe，并校验它们的起点、终点和时钟一致。麦克风编辑必须先解码为 48kHz PCM/WAV，随后从
PCM 样本级寻址；禁止在每个片段上对 AAC/M4S 做 input-side seek，它会把切点吸附到压缩包边界，
造成口水词重新出现、完整词被截断或说话卡顿。

#### 口水词、重说与口误门禁

先做保留语气的逐字转写，再识别独立的“啊 / 呃 / 嗯 / 额 / 那个”、未完成起句、同词回滚和
“说错后立刻重说”的修正。只删不承载语义的部分；若一个音节同时可能是完整词的首尾，默认保留，
直到相邻 PCM 片段和句义都证明可以删除。每个微切点至少检查：

1. 前段结尾是完整词或自然停顿；
2. 后段开头没有残留填充音，也没有丢失完整词；
3. 拼接后的短窗逐字转写不再出现重复起句；
4. 长窗 ASR 若与两个相邻短窗冲突，以可听原声和短窗证据为准，避免把模型幻觉当成口误。

```bash
python3 "$SKILL_DIR/scripts/timeline_check.py" \
  --input WORK_DIR/edit-manifest.json \
  --duration SOURCE_DURATION \
  --output WORK_DIR/timeline-check.json \
  --pretty
```

上传弹窗、等待、卡住的文件选择器等低信息段应被压缩到能交代状态的长度；若它们遮挡了真实结果，直接跳过。为最终结果和原声设置 `protected_audio: true`，后续所有剪辑与混音都不得误删。

#### Step 2.5: 先规划本轮失效范围

每轮先更新 `iteration-current.json` 的 `draft / locked / approved` 阶段和八类 revision token，再运行
`iteration_plan.py plan`。只执行 `run`，复用 `skip`，尊重 `blocked`；字幕、布局、BGM、平台或封面微调
不得重建无关媒体。状态格式与失效矩阵见 [`references/iteration-performance.md`](references/iteration-performance.md)。

### Step 3: 设计叙事、标题与封面

阅读 [`references/media-workflow.md`](references/media-workflow.md) 与 [`references/cover-and-title.md`](references/cover-and-title.md)：

- 主角是工作流解决的实际问题，以及“终于跑通”的证据；工具名称只在确实帮助理解时出现。
- 保留信息差和悬念，但不虚构速度、权限、成功率或发布状态；“一键”“秒发”“完全自动”只有在有对应证据时才能使用。
- 用户给出封面主标题时原样尊重；封面只保留这个钩子与系列标识，不再补解释型副标题或泄底说明。片名优先级：用户逐字给定的片名 > 改编来源（已发表文章）的标题 > brief 主题句（「主题《…》」默认是创作方向，首次交付列为待确认）；改编作品封面先用作者已公开选用的图，征求意见时直接发 2–3 张图并排，见 [`references/cover-and-title.md`](references/cover-and-title.md)「改编作品与叙事片封面」。
- 封面需要人物时优先复用用户指定或 Profile/品牌资产中已确认的职业照；录屏摄像头抽帧只作回退，
  且必须避开表情整理、半闭眼和口型中的帧。屏幕截图是可选辅助层，不为信息量强行加入。
- 系列标识遵循版式模板并进入手机安全区，活跃度低于主标题；满宽底条可轻斜，但栏目文字保持
  稳定字体与基线。主标题可按语义异字号破调，但须保持 Z 形阅读顺序，缩小后仍一眼读清。
- 章节标题必须从该段真实口播、画面与结果证据中归纳，并在分幕数据里保留一句命名依据；
  不用“参与开源”“共创风格”这类过程词代替该幕真正讲的“背景”“自定义 Prompt”等主题。
- 避免模板化的 AI 句式、空泛的“重新定义效率”和过量大字。封面优先展示状态、界面证据或前后对照。
- 剪辑节奏先服务理解，再服务刺激；成果段出现后，隐藏解释性字幕和多余顶栏，让真实画面与原声完成收束。

#### 开场先判别，再走自动或用户覆盖两条路径
先审计清理后的原始开场，不默认加 Highlights 或片名卡。把决定写入 manifest 的 `opening`：
1. **自动判别（默认 `strategy=auto`）**：第一句或第一个完整意群已经直接抛出具体问题、结果、冲突或代价，且没有试讲、寒暄或必要铺垫时，解析为 `direct`。从第一句有效语音开始，问题说清前不插 Highlights、片名卡或特效字幕；需要方向感时，只在完整问题后插短的 `post_problem_title`。短视频更偏向这条路径。原开场偏泛、铺垫长，且后文存在更强闭环时，才解析为 `highlights`，使用 2–4 个完整短句。
2. **用户覆盖**：用户可显式设为 `direct` / `highlights`，并独立开关、改写或移动问题后标题。当前请求优先于 Profile 与自动判断；记录 `resolved_strategy`、`decision_origin` 和 `decision_reason`。
走 `highlights` 时按语义与声学显著性选 6–15 秒闭环。SRT cue 只作**语义锚点，不是剪点**；用 PCM 保留完整词头和句尾，并对渲染片段跑短窗 ASR 与首尾试听；完整门禁见 QC reference。
封面走 `lov-channels-cover` 时，标题钩子由那个 Skill 的门禁判定；走回退路径时沿用同一标题、系列与事实约束。本 Skill 负责**封面声称的事实与成片是否一致**——封面上的数字、平台状态、结果承诺必须在片子里真的出现过。标题钩子与人像/界面素材稳定后即并行出图，不等发布交接才补。Step 1.5 选了要开场静帧时，那张图
必须在进入 Step 5 之前定稿。

**`cover-brief.md` 只是计划，不是封面交付。** 一旦目标包含发布或 `platform-ready`，必须拿到
当前平台实际槽位需要的 PNG/JPEG，并逐张核对尺寸、四边条带、安全区和目视构图；只有 brief、
prompt、方向稿或生成脚本时，`creative_status` 仍是 `blocked-on-cover-render`。不得因为视频、
字幕和文案都已通过，就把缺封面的交付写成完成。

### Step 4: 编辑画面并保护关键原声

系列片在这一步逐条对照 [`references/series-template.md`](references/series-template.md) 的硬性清单；
以下是通用部分。

**节奏：气口不是重点，死气才是。** 用户说「剪掉语气词」时，真正拖节奏的通常不是那些词。
实测账目（EP.02）：语气词 + 句尾拖音合计 9.0s，而没人说话、屏幕也没动的段落有 216s。
所以停顿检测要用 **10ms 粒度扫整条包络**，不要只枚举「≥1.2s 的大空档」。处置分两类：
静止停顿剪到 0.14s（章节交界留 0.40s），**有画面动作的停顿抽帧不删**——演示片删掉就断了。

拼接密度上去之后（几百处人声拼接），淡入淡出要跟着缩短到 ~6ms，30ms 的斜坡会磨掉短句的
首尾辅音；前提是每个切点已吸附到附近最静的 10ms 窗口。

1. 先按 EDL 做粗剪，再做一次连贯性检查；转场、加速和裁切都要服务信息密度。
2. 上传弹窗只保留必要的进入、选择和完成信号；卡顿段短暂呈现即可，不让等待成为视频主体。
3. BGM 是氛围层，不是主角。有人声、点击反馈或最终视频播放时，降低 BGM；成果段需要听清原声时可暂时只保留原声（叙事片按 6a 保持配乐连续）。
4. BGM 采用淡入淡出和 ducking，避免循环接缝、突兀起音与尾部截断。具体滤镜和参数见 [`references/audio-mix.md`](references/audio-mix.md)。
5. 若源素材本身没有可用原声，标记这一事实，不用 BGM 冒充真实反馈。
6. **系列片默认使用已约定的 `Screen Studio Lo-fi / Bright Lounge`**：从已授权素材构建连续音乐床，不再运行或复用前作的程序合成器、`make_music.py` 或同类生成脚本；素材缺失时阻塞并报告，不得回退到程序合成或临时替代曲。
6a. **Vlog、旅行、纪录、宣传等叙事片不套系列默认**：用户给的曲库整体可用，不按其顺口点名的几首收窄；作者点名的曲目先按其建议位置试，按章节与当时的真实心境混合多首，每条 cue 写明叙事理由。配乐默认从头连到尾、一首放到下一首接手，口播只压低不停歌（叙事片不适用上文第 3 条与 audio-mix「基本策略」的暂时静音），静默只给作者要求的段落，交付前扫音乐 stem 上 2 秒以上的断档；同语种歌词默认不压对白，只有作者明确点名该曲垫对白或明确说不为口播停歌时有条件放行，cue 上用 `lyric_override` 记理由与作者原话，放行句按组求 CER 均值对比纯人声底线、逐句只排抽听顺序；字卡下默认避开歌词；人声与音乐不必互斥，按时刻选 clear / blend / feature，段落过渡留足气口；以场景为单位、少换曲，agent 自发的修改只做减法，用 `cut_metrics.py` 量碎片化。字卡、照片、口播剪点与人物口径见 [`references/narrative-vlog.md`](references/narrative-vlog.md)。
   `validate_cues.py --preset narrative`、`smr_check.py`、`intelligibility.py` 三道防听不清的客观门禁（数值是校准参考）与 `score_mix.py` 线性母带（`-3 dBTP`）见 [`references/audio-mix.md`](references/audio-mix.md) 的「叙事片多曲配乐」。
6b. **片中念到的重点产品要做 research 再贴回画面，自研产品优先**（检索 → 官网 → 提炼当前定位
   → 截 hero/品牌资产 → 画中画停 4.5–5.5 秒）。流程、位置怎么量、以及 `$ego-browser` 的坑见
   [`references/pip-research.md`](references/pip-research.md)。
7. **重点词强调要设上限**：同一个词有次数上限、每行最多一处、半数句子都出现的高频词
   不进表；配套音效按「每 N 秒最多一次」稀释。满屏都是重点等于没有重点。
8. **系列长视频的章节卡服从开场策略**：知识传播类推荐 1.8–2.4s，显示“第 N 章 + 语义标题”；卡片必须落在口播句界或 EDL 片段边界，期间暂停人声，可延续低声配乐和轻转场声。`highlights`
   路径可把第一章卡放在总片名卡之后；`direct` 路径可跳过第一章卡，避免打断已成立的开场，后续章卡照常。
   插卡会改变后续字幕与章节时间码，必须由同一映射函数累计偏移。

#### Screen Studio + Remotion 分阶段媒体架构

`draft` 按 EDL 懒生成 source-scoped 低码率代理分片，不预转完整长源轨；字幕、布局和卡片只更新上层数据。
`locked` 后才按 EDL 生成等长的 display、webcam、microphone、system-audio 连续母版；Remotion 每轨
只挂一个连续媒体元素。`approved` 后才跑平台终版。长任务前先跑接缝、视觉或音频 canary，失败即停在局部。

本期口播明显偏慢时，默认从 1.08×–1.15× 试剪并保持原音高；以句子可懂、辅音不损失和演示动作仍可跟上为门禁。横版锁定后用同一数据时间轴派生竖版，不另复制剪辑事实。

**口播变速不得通过重采样实现。** `resample` / `resample_poly` 会同时改变时长和音高；对白与真实系统声只用 FFmpeg `atempo` / Rubber Band 等保音高 time-stretch，并按 `output_frames × samples_per_frame` 锁定样本数。验收要与 1.0× 源声 A/B，响度报告不能替代音高听感。

竖版安全区按最终发布容器而非裸画布定义；视频号 1080×1920 首轮预留顶部约 160px 并以真机截图校准，章节栏、正文舞台和调试框共用一份常量，详见 [`references/screen-studio-remotion-qc.md`](references/screen-studio-remotion-qc.md)。
**BGM 永远最后挂载。** 先锁定画面、口播、系统声、字幕与章节，再把已授权的
`Screen Studio Lo-fi / Bright Lounge` 扩展为一条与最终时间轴
等长、无缝交叉淡化的连续音乐床，最后在 Remotion 根层只挂一次并全局 ducking。不得让 BGM 跟着 EDL
逐片段裁切、重复 mount 或在转场处重启。程序合成 BGM 是已废弃路径；不能取得约定曲目或授权来源时，
记录 `audio_status=blocked-on-agreed-bgm`，不得自行生成或换曲。

Remotion 同时负责按开场策略启用的动画标题、章节进度条、摄像头 B-roll 布局、可视化解释、专业字幕、转场、横竖版和封面 Composition。动画必须由 `useCurrentFrame()` 等时间轴驱动，不使用运行时 CSS 动画；最终时长、fps 和画幅由数据/Composition 注册统一计算。

### Step 5: 以 Studio 为主预览；按阶段升级证据

`draft` 先启动或复用 Studio，以代理、当前 EDL/字幕/布局和预览混音快速审片；只跑本轮受影响的
局部 canary，不等待最终连续母版、最终混音、全片 ASR 或全轨完整解码。`locked` 后才切换到连续母版
与最终混音，执行完整解码、全片 ASR、关键帧和响度检查。`approved` 后才渲染平台文件并做全量 QC。
Remotion Studio 始终是画面、节奏、声音和字幕的主预览；MKV 只用于 Subtitle Edit 字幕交接。作者在线审片时由主 agent 直接改剪辑表、只重渲变动镜头并推进 Studio，不默认启动多 agent 各出一版再评审的长工作流、不每轮渲染预览；交链接前确认服务在跑且加载的是本轮数据（见 [`references/iteration-performance.md`](references/iteration-performance.md)「作者在线快速迭代」）。
完整矩阵见 [`references/screen-studio-remotion-qc.md`](references/screen-studio-remotion-qc.md)。

**Studio 通过不等于最终编码画面通过。** `OffthreadVideo` 预览可为 `<video>`、终版为 `<img>`；样式应落
稳定 wrapper 或同时覆盖 `video, img`。终版须从**编码成片本身**抽摄像头代表帧联系表；详见 QC reference。

**锁定后的主预览音频不得重新拼原始 stems。** 画面与对白锁定、BGM ducking 和整体响度处理完成后，先生成
一条最终混音；主 Studio Composition 只挂载这一条，并与批准母版的音频同源或从中 stream copy。
`microphone`、`system-audio` 与独立 BGM 轨只保留作诊断，不得同时留在主预览里重复混音。验收须
记录最终混音的 SHA-256、LUFS-I、dBTP，并在 Studio 组件树确认只有一个音频实例。

字幕存在时先在 Studio 中预览；需要作者用 Subtitle Edit 修正时才执行两道字幕门。批准前不生成
平台 MP4，也不把文件称为最终成片。作者返回 SRT 后，必须在不覆盖作者文件的前提下将其同步回
Remotion 字幕数据，刷新现有 Studio 并复核字幕、画面和声音。

#### Step 5A: 生成无旁白硬字幕的画面母版

使用 FFmpeg 统一重编码一次，避免多次有损导出。片名卡、章标题卡、章节条、身份块和非字幕图形可以留在
画面中；需要作者校对的旁白字幕不得烧入这一版。常用画面母版参数：

```bash
ffmpeg -y -hide_banner \
  -i SOURCE_VIDEO \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=30" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
  -an WORK_DIR/video-master-no-subs.mp4
```

若涉及多段画面、原声与 BGM，使用 `filter_complex` 显式映射视频与音频；不要依赖默认流选择。源素材保持原位。

#### Step 5B: 按需封装 Subtitle Edit 字幕修正 MKV

只有需要 Subtitle Edit 修正字幕时，才把无旁白硬字幕的画面母版、最终音频和成片时间轴 SRT
封装为 MKV，同时把同一份 SRT 单独放在
`deliverables/`。Subtitle Edit 可直接打开 MKV；外置 SRT 让作者无需抽轨就能校对。两者的
SHA-256 必须同时写入报告。这个 MKV 是字幕修正交换件，不是 Remotion 主预览，也不用于画面审片。

```bash
python3 "$SKILL_DIR/scripts/subtitle_gate.py" review \
  --video WORK_DIR/video-master-no-subs.mp4 \
  --audio WORK_DIR/audio-master.wav \
  --srt DELIVERABLE_DIR/review-v0.1.srt \
  --output DELIVERABLE_DIR/review-v0.1.mkv \
  --report DELIVERABLE_DIR/subtitle-review.json
```

此时只能记录：

```yaml
render_status: review-ready
subtitle_status: awaiting-review
delivery_status: blocked-on-subtitle-approval
```

不得生成或交接平台 MP4，不得写 `final`、`approved` 或 `publish-ready`。用户可以在 Subtitle Edit
中改文字、断句和时间码；保存后的 UTF-8 SRT 是后续唯一权威字幕源。

**作者所有权门禁（强制）**：审校 MKV/SRT 一旦交给作者，就成为不可变的作者输入。自动化不得再向
同一路径导出字幕，也不得从 transcript、旧 timeline 或 ASR 结果重建并覆盖它；重跑审校包装必须换
新的 review 版本号。作者校对后如果又插入章标题卡、片头或删改 EDL，必须把作者 SRT 通过显式时间
映射迁移到新时间轴，输出新的 approved SRT，并报告迁移前后文字是否逐字保留。禁止用重新转写替代迁移。

#### Step 5C: 字幕批准后封装归档母版与平台文件

只有用户明确确认字幕通过后，才运行批准门禁：

```bash
python3 "$SKILL_DIR/scripts/subtitle_gate.py" approve \
  --review DELIVERABLE_DIR/review-v0.1.mkv \
  --srt DELIVERABLE_DIR/subs-approved-v0.2.srt \
  --expect-edits \
  --output DELIVERABLE_DIR/master-v0.2.mkv \
  --report DELIVERABLE_DIR/subtitle-approved.json
```

用户明确说“字幕已经改过”时，`--expect-edits` 是必选项：若批准 SRT 与审校 MKV 内嵌字幕逐条完全
相同，门禁必须失败，先查 Subtitle Edit 自动备份或作者保存路径，不得把相同文件复制成 `approved`。
批准报告必须记录 review MKV、approved SRT 的路径、mtime、SHA-256、条数和
`changed_from_review`；有时间轴迁移时还要附迁移报告。即使作者只改了断句或时间码，也属于有效差异。

脚本验证 UTF-8、时间码、正时长、顺序、无重叠、成片边界和内嵌字幕回抽一致性，并以 stream copy
替换字幕轨；视频和音频不再有损编码。`master.mkv` 是归档母版，不自动等于平台上传文件。

平台容器每次以当前上传界面为准。默认策略：

- B 站即使允许 MKV，也优先交 H.264/AAC MP4：直接交渲染出的原码率 H.264/AAC MP4，不为码率二次压制；并把批准 SRT 作为平台 CC 字幕上传；如果用户要求字幕始终可见，则从无字幕画面母版烧录一次。
- 微信视频号优先交 H.264/AAC MP4；平台没有明确承诺保留 MKV 内嵌字幕轨时，使用批准 SRT 烧录的 MP4；视频码率按平台建议 ≤ 10 Mbps 一次出（CRF + maxrate 约 9M + `+faststart`，见 platform-variants），不等上传预检再重压。
- 只需要换容器且视频/音频已是 H.264/AAC 时使用 `-c copy -movflags +faststart`，不要把 MKV 再转码一次；只有烧字幕才重编码视频。

平台“接受 MKV”不等于“保留 MKV 里的字幕轨”。报告必须分别记录容器支持证据、字幕交付方式
（`embedded` / `platform-cc` / `burned-in`）和验证日期。每个派生平台文件还必须记录
`subtitle_source_sha256`，并与本次 approved SRT 的 SHA-256 相同；视频号烧录版须从最终文件抽取
至少三张命中作者修改点的实帧，目视确认修改文字和字幕样式后才可交给发布 Skill。

#### 开场静帧：先判画幅，再渲染

Step 1.5 选了要开场静帧时，渲染前必须跑一次只读判定，**不要直接 `-loop 1` 拼上去**：

```bash
# --still 传的是与成片同画幅的静帧图，不是主页卡片用的 3:4 封面
python3 "$SKILL_DIR/scripts/check_opening_still.py" \
  --still DELIVERABLE_DIR/opening-still-1080x1920.png \
  --video WORK_DIR/body.mp4 \
  --hold 1.5 --json
```

画幅一致时它返回 `ok: true` 和可直接执行的 `ffmpeg_command`。画幅不一致时**默认退出码 1**，
必须由你显式选一条路：`--allow-crop`（裁掉画面边缘）或 `--allow-pad`（首帧带黑边）。
这个门禁的意义是把「裁掉多少」变成一个写进交付报告的决定，而不是渲染几分钟之后才
从画面里发现。裁切损失超过 12% 或需要放大超过 1.05x 时它会另外告警——此时标题组
很可能已经被切到，裁完必须目视确认第一帧，不能只看退出码。

音频侧要垫一段与首帧等长的静音，否则 `concat` 之后整条声画会前移，成果段的原声会
和画面错开；脚本给出的命令已经包含 `anullsrc`。成片无音轨时改成 `-an` 并删掉音频链。

首帧停留默认 1.5s，低于 0.6s 会告警：观众来不及读完标题，等于白留一帧。

### Step 6: 做媒体与音频质检

```bash
python3 "$SKILL_DIR/scripts/media_probe.py" \
  --input REVIEW_OR_APPROVED_OUTPUT \
  --output DELIVERABLE_DIR/final-probe.json \
  --pretty

python3 "$SKILL_DIR/scripts/audio_qc.py" \
  --input REVIEW_OR_APPROVED_OUTPUT \
  --output DELIVERABLE_DIR/audio-qc.json \
  --pretty

ffmpeg -v error -i REVIEW_OR_APPROVED_OUTPUT -f null -
```

逐项回看开头、每张章标题卡、每个关键切点、最终结果连续播放和结尾。至少确认：章标题概括实际内容、
黑幕卡没有切进一句话、卡片之后音画与字幕同步、最终段仍有声音、BGM 没盖住人声、画面没有非设计黑帧
或意外静帧、上传弹窗没有占据主体、正式封面缩略图仍能读出主题。封面必须打开实际图片目视检查；
`spec.json`、生成日志、文件名和 `cover-brief.md` 都不能替代看图。审校版还要确认 MKV 中恰有一个默认
SubRip 字幕轨，并回抽与外置 SRT 逐条一致。目标响度参考 `-16 LUFS-I ±1.5`，True Peak 控制在
`-1 dBFS` 以下；实际值以报告为准。口播加配乐、留有纯配乐段的片子，母带用静态增益加峰值限制器，不用会退回动态模式的 `loudnorm`；单条音乐床的录屏不受此限，见 [`references/audio-mix.md`](references/audio-mix.md)「通用线性母带」。

最终 MP4 / MKV 另抽覆盖实际开场策略、`camera-full`、画中画、并排和收尾的代表帧联系表，确认脸部主体、
裁切与 `object-position` 正确，无胡须或额头异常局部；证据必须来自编码文件，不来自 Studio / DOM。

做了开场静帧时另外抽出第一帧目视确认，**不能以脚本退出码 0 代替看图**：

```bash
ffmpeg -y -v error -i REVIEW_OR_APPROVED_OUTPUT -vframes 1 DELIVERABLE_DIR/first-frame.png
```

看三件事：标题组完整没被裁掉、四边没有黑条、首帧到正片的切换不突兀。另外确认音频
没有整体前移——首帧那一段应当是静音，正片第一句话的位置与 `body.mp4` 里一致。

### Step 7: 交付与发布交接

持续栏目中，交付物落到本期 `deliverables/`，过程文件落到本期 `work/`，原始素材留在
本期 `sources/`；跨两期以上复用的背景、字体说明或栏目级模板才提升到根级 `shared/`。
报告优先写相对本期目录的路径，避免工作区改名或迁移后证据链接整体失效。

按 [`references/delivery-contract.md`](references/delivery-contract.md) 生成交付报告，分别写清：

- `render_status`：成片是否导出且通过解码与参数检查；
- `subtitle_status`：`awaiting-review` / `approved`；只有用户确认后才能写 `approved`；
- `delivery_status`：是否仍被字幕批准门禁阻塞，或已经 `platform-ready`；
- `audio_status`：原声、BGM、响度和峰值是否通过；
- `creative_status`：标题、封面、叙事和证据段是否完成；
- `publish_status`：是否交给发布 Skill、是否已发布、是否有线上回读。

“审校版已渲染”“字幕已批准”“平台文件已生成”“已上传”“已发布”“已回读”是六个不同状态。只有出现真实平台回读证据时，才把 `publish_status` 写成 `published`。

发布型交付另外记录 `cover_status`：`missing` / `brief-only` / `rendered` / `approved`。
`creative_status=passed` 只能与 `cover_status=approved` 同时出现；`rendered` 仅表示图片已生成，
还没有完成尺寸、安全区、四边条带和目视检查。用户明确表示本期不要封面时才可记
`cover_status=waived-by-user`，不得由执行者自行豁免。

做了开场静帧时，`creative_status` 另外记三项，因为它们决定了这版成片还能不能改那一帧：

| 字段 | 内容 |
| --- | --- |
| `opening_still` | `true` |
| `opening_still_source` | 静帧图的文件路径与版本号 |
| `opening_still_fit` | `match` / `crop:<裁掉比例>` / `pad`，以及停留秒数 |

写清一条前提：**这版成片的第一帧绑定了这一版静帧图**，换图必须重渲染。静帧与封面是两个文件，应共用同一套视觉语言，否则观众在列表页看到的封面和点开后的第一帧像两个来源。
## Validation

完成前运行：

```bash
python3 "$SKILL_DIR/scripts/validate_skill.py" "$SKILL_DIR"
python3 "$SKILL_DIR/scripts/media_probe.py" --help
python3 "$SKILL_DIR/scripts/timeline_check.py" --help
python3 "$SKILL_DIR/scripts/audio_qc.py" --help
python3 "$SKILL_DIR/scripts/check_opening_still.py" --help
python3 "$SKILL_DIR/scripts/subtitle_gate.py" --help
python3 "$SKILL_DIR/scripts/iteration_plan.py" --help
for s in bgm_tracks validate_cues smr_check score_mix intelligibility cut_metrics; do python3 "$SKILL_DIR/scripts/$s.py" --help >/dev/null; done
```

同时检查 `skill-card.yaml`、`skill-card.md`、`cases/cases.json` 和 `pricing-card.yaml`。至少保留一个真实 Input → Prompt → Output 案例，记录三项以上有证据的质量维度，并标明免费/付费渠道状态。
## Dependencies

- Python 3.8+ 标准库；`PyYAML` 用于 Skill 结构验证；叙事片配乐门禁与混音需要 `numpy`，可懂度门禁另需 `mlx-whisper` 或 `openai-whisper`，优先用已有的持久 venv 运行（见 audio-mix「运行环境」）。
- FFmpeg 与 FFprobe 用于视频解码、转码、帧提取和音频质检。
- 可选 Pillow、Playwright 或图像生成能力，用于新封面资产；已有封面时不强制安装。
- Screen Studio 源工程工作流需要 Node.js 与 Remotion；Remotion 只读取工作区代理轨，不修改源工程包。可选的字幕、章节和媒体发布 Skill 只通过交付文件交接，不是本 Skill 的安装依赖；`npx lovstudio skills add media-creator` 会用 frontmatter 的 `dependencies:` 提示可选的 `lov-media-publisher`，加 `--with-deps` 才安装，`npx skills add` 路径不读此项。

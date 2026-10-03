# 从整场实录到独立切片

适用于课程、访谈、活动和多人交流。录制不完整、讲话者不止一人时，优先产出能独立理解的片段。沿用本 Skill，无需建立另一个剪辑 Skill；全片曝光与素材准备交给可选上游 `lov-media-preprocessor`。

## 先看全片，再选完整内容

1. 建立原片身份、完整转录、讲话者切换、视觉状态与全覆盖取舍表。先读完全文，按话题组织候选，再回看候选和所有待核验区间。稀疏缩略图不能代表内容审阅完成。
2. 每个候选回答三个问题：观众能否独立理解；能带走什么具体观点、方法、案例或真实感受；有没有完整开头与收束。给出取舍理由和源时间码证据，不能仅按音量、清晰度、关键词次数评分。
3. 用户要“全部有传播价值的”时，遍历所有候选，记录入选、重复、缺上下文、无独立内容或待核验的原因；不预设 Top 5/10，不用固定时长填配额。结合既有发布区间去重。未核实候选进入 review，不能写全片选取完成。
4. 保留问答对应、否定词、条件、举例与结论。不要把学员的话接成主讲人的回答，不为制造观点删掉限定语。独立切片不强制 EP 编号、连续剧情、系列课目录或虚构章节。
5. 开场从有效句或必要问题开始。字幕时间只作语义锚点，结合局部词级 ASR、波形、画面与可用听审能力，在完整词头和句尾处落到视频帧边界。保留自然气口；6ms 音频淡化只能去点击，不能修复截断的语义。

`coverage` 使用**原片秒数**连续覆盖全片，每段声明 `candidate / exclude / review`、reason、evidence；`clips[].ranges` 也使用原片秒数，但可以拼接不连续的保留区间。字幕、摘要 beat、增益窗口使用**当前切片的本地秒数**。两者绝不能混用。机器检查覆盖、重叠、帧边界和来源，不替代宿主的内容判断。

## 输入与可复用脚本

`scripts/clip_batch.py` 接收 [计划示例](independent-clips.example.json)。文件路径相对于计划文件；`init` 解析成绝对路径并保留只读原片指纹。用户品牌、字体、音乐与素材通过计划注入，模板不携带个人照片、字体、音乐、模型或私人绝对路径。

- Python 3.9+、FFmpeg/FFprobe。混音与音频对齐需要 NumPy。
- 当前转录适配器为 Apple Silicon 本地 `mlx-whisper`，显式指定包含权重的模型目录；使用任务中最高质量的可用模型，不静默换小模型。其他宿主可生成同结构且源哈希一致的 `asr.json`，明确记录实际引擎；没有适配器时不要声称脚本跨硬件运行成功。
- Remotion 模板依赖 Node.js；版本锁定于已验证的组合，运行目录内执行 `npm install`，生成该工程 lockfile。不是最新版本承诺。模型、字体和 Remotion 浏览器运行时需要事先准备；安装失败须报告原错误。
- CLI 支持整数帧率 1–60 且可整除 48000 的固定帧率；非整数或可变帧率走专门时间线流程，不偷偷改帧率。
- 可选 `handoff` 是上游导出的 `media-preprocess-handoff/v1`；画面复用已增强文件，不重复调色。音频仍从原片按同一组源时间码读取。映射不能跨越缺失的已删除素材。
- 两种版式：`source-led` 保留真实画面并提供人物局部；`audio-led` 适用于固定机位拍不到说话者、声音有价值的片段，显示有依据的观点摘要与真实人声波形。它不是给没有声音的片段补造内容。
- `privacyMasks` 在准备阶段烧入规范化 1920×1080 主体，确保视频、裁切和照片封面都遮挡同一区域。坐标必须从实际画面核验，禁止复用上一场课程的固定遮挡坐标。

```bash
python3 "$SKILL_DIR/scripts/clip_batch.py" check-plan --plan "$PLAN"
python3 "$SKILL_DIR/scripts/clip_batch.py" init --plan "$PLAN" --output "$RUN"
cd "$RUN/remotion"
npm install
python3 "$SKILL_DIR/scripts/clip_batch.py" prepare --run "$RUN"
python3 "$SKILL_DIR/scripts/clip_batch.py" transcribe --run "$RUN" --model "$LOCAL_MLX_MODEL"
python3 "$SKILL_DIR/scripts/clip_batch.py" subtitles --run "$RUN"
```

`prepare` 是选片完成后的生产裁切：整条原声只解码一次为 48kHz PCM，按样本裁切与拼接；视频按同一范围落帧。不能在尚未选片时为了看几个缩略图就全转原音。`subtitles` 只写 `draft.srt`；使用词时间戳，词内字符时间为插值，必须复核。英文术语不逐字拆开；单行约 13 个汉字宽，最多两行。专名、产品名、否定词和误识别依据上下文纠正，不做无依据的全局替换。

逐条保存 `reviewed.srt` 和真实审查记录。文件哈希必须对应当前主体与字幕。用户已经授权全自动审校时，由代理完成审核并记录 `reviewer=delegated-agent`、具体授权和证据；不得冒称用户逐条批准或人工听审。无法直接听审时，结合词级转录、波形、声学对齐及真实画面复核；无法消除的语义疑问应保留待核验状态。

```json
{
  "reviewer": "delegated-agent",
  "authorization_evidence": "当前任务中用户授予的具体审校范围",
  "content": "passed", "boundaries": "passed", "subtitles": "passed",
  "privacy": "passed", "presentation": "passed",
  "evidence": "实际查过的源时间段、词级识别、字幕与画面记录",
  "human_auditory_review": false,
  "srt": "reviewed.srt", "srt_sha256": "实际SHA256", "body_sha256": "实际SHA256"
}
```

不要复制示例中的 passed 当作审核结果。脚本只能检查审核记录和文件对应关系，不能证明人的判断正确。

## 连续音频、包装与分批渲染

```bash
python3 "$SKILL_DIR/scripts/clip_batch.py" mix --run "$RUN"
python3 "$SKILL_DIR/scripts/clip_batch.py" lock --run "$RUN" --clip "$ID" --review "$REVIEW_JSON"
python3 "$SKILL_DIR/scripts/clip_batch.py" render --run "$RUN" --clip "$ID" --mode covers
python3 "$SKILL_DIR/scripts/clip_batch.py" render --run "$RUN" --clip "$ID" --mode canary
python3 "$SKILL_DIR/scripts/clip_batch.py" render --run "$RUN" --clip "$ID" --mode video
python3 "$SKILL_DIR/scripts/clip_batch.py" verify --run "$RUN" --clip "$ID"
python3 "$SKILL_DIR/scripts/clip_batch.py" status --run "$RUN"
```

先稳定切口、字幕和版式，再连续混音、锁定生产版本；逐条 lock，之后可省略 `--clip` 顺序批量渲染。canary 是开头最多 10 秒的可播放检查片，不能替代剪口、中段、片尾或全片验收。对疑难剪口另取局部窗口检查。`covers` 不执行完整视频渲染；已完成同版本文件经哈希匹配后复用。

按切片内容选曲或生成（见 audio-mix「按内容选曲或生成」），作者已点名的音乐照用，显式填写来源/授权。用户要求无配乐时写 `music: null`，不要把素材缺失擅自解释为用户免除要求。脚本不下载音乐、不合成替代曲。原始音乐先延长成无缝交叉淡化的连续床，再 ducking 一次；不随画面切口重启。对不同讲话者可在本地时间轴声明 `voice_gain_windows`，只调整音量，不改变语速/音高。

人声参考 -16 LUFS-I；最终 AAC 实测容差 ±1.5 LU，True Peak ≤ -1 dBTP。限制器补偿其延迟，检查 AAC 包时钟。Remotion 预览只有一条最终混音；正式视频先静音渲染，再 stream-copy 已核验 AAC，避免按视频帧拼 AAC 引入周期性音频问题。最终音频与规范化原声在开头、中段、末尾及拼接处做相关性检查，目标延迟 ≤40ms、相关性 ≥0.8；静音窗口不算自动通过，换成附近可听的窗口并留依据。

模板提供 1080×1920 正片、1080×1440 和 1440×1080 两张正式封面，使用当前标题、真实帧或摘要关键词，顶部预留约 160px。它是本 Skill 的 Remotion 封面回退。可用专用封面能力时沿用外部文件与相同实际审阅门禁。独立片段的关键词为静态标签，只有存在真实内容转换才使用随时间变化的摘要；不把时长等分伪装成章节。摘要正文和标题需按实际字体预览溢出，手机与平台 UI 安全区仍以实际截图校准。

`lock.json` 绑定剪辑数据、主体、PCM、最终混音、字幕、字体、封面照片、品牌、模板与渲染入口哈希。已完成 stage 的输入变化会拒绝复用，要求新 revision 目录；该批量 CLI 当前不跨 revision 自动推导局部失效。复杂迭代仍用本 Skill 的 `iteration_plan.py`。中断的未完成输出先改名保留再重试；人工字幕文件不会被自动覆盖。一个 run 同时只开一个生产进程，避免多个 render 共写工程数据。

## 实际交付与状态

同一场访谈、课程或活动拆成多条独立切片并发布时，必须统一归入同一个平台合集，不能把合集当作可省略的发布字段。先回读现有合集，复用对应系列；用户已授权建立该系列时，在平台限制内创建一次，并逐条核对相同合集名或 ID。封面、交付清单与发布顺序使用一致编号，发布完成后回读合集的实际成员，确认没有漏片、错放或重复。无合集能力的平台在交付记录中说明限制，不伪称已归集。此要求不强迫独立片段采用连续剧情。

`verify` 从真正的 `final.mp4` 全量解码，检查视频尺寸/帧率/帧数/时长、H.264/yuv420p、48k AAC、混音比特流一致性、对齐与封面尺寸，抽出最终头/中/尾画面。`encoded-awaiting-visual-review` 不能当 `platform-ready`。

代理实际查看成片代表帧、所有不同版式与两张封面，确认文字完整、画面明亮、遮挡有效、摘要有依据，再写 `clips/ID/visual-review.json`：

```json
{
  "status": "passed", "reviewer": "delegated-agent",
  "evidence": "实际查看的最终帧、版式、封面及发现/修正",
  "video_sha256": "实际SHA256",
  "cover-3x4_sha256": "实际SHA256", "cover-4x3_sha256": "实际SHA256"
}
```

再次 `status` 才升级到 `platform-ready`。每次交付都提供 `delivery.md` 中可直接打开的 MP4、封面、reviewed/locked SRT、`delivery.json` 与真实 QC，不只交 HTML 或计划表。`delivery.json` 区分选中数与通过数，失败片段不隐藏。

该工具始终写 `publication: not-published`。只有发布能力能根据用户授权操作账号，并用平台列表回读记录已提交、审核中或已发布。此 Skill 的技术验收、代理审校和线上发布是不同证据。

## 回归依据

本流程来自一次长约 4 小时 10 分钟、多人参与且分享录制不完整的线下课程；原任务最终有 48 条独立片段，用户认可剪辑效果。本次工具化使用其中 30.8 秒主体做隔离的本地回归，不重写原片或已发布文件，不把旧项目“发布成功”当新 CLI 的验收结果。每次优化仍须用当前脚本实际导出和检查新 MP4。

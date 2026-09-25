# Audio Mix

原声承担事实，BGM 承担氛围。两者同时存在时，观众应先听清人声、点击反馈和最终结果播放。

## 基本策略

- 录屏、知识系列与 Screen Studio 栏目的默认 BGM 是已授权的 `Screen Studio Lo-fi / Bright Lounge`。早期程序合成 BGM 已废弃；不得运行、
  import 或复制前作的配乐合成脚本，也不得在约定素材缺失时自动生成替代曲。
- 约定 BGM 素材不可用时停止混音，记录 `audio_status=blocked-on-agreed-bgm` 并报告缺失项。
- Vlog、旅行片、纪录短片、宣传片等叙事片不套用这条系列默认，按下文「叙事片多曲配乐」选曲和验收。
  程序合成同样禁止；没有可用曲库时记录 `audio_status=blocked-on-bgm-library` 并报告。
- 先检查源视频是否有可用音频轨；没有原声时在报告中明确写出。
- BGM 先降到较低电平，再根据人声和成果段做 ducking；不要用持续大音量覆盖整条视频。
- 开头和结尾使用短淡入淡出，避免循环接缝和突然截断。
- `protected_audio` 片段默认使用原声优先；必要时让 BGM 暂时静音。
- 混音完成后统一检查综合响度、True Peak、声道布局和是否出现数字削波。

## 对白变速必须保持原音高

- 改变口播节奏时，画面和对白使用同一份 EDL 速度映射；对白使用 FFmpeg `atempo`、Rubber Band
  或等价的 pitch-preserving time-stretch。
- 禁止用 `aresample`、`resample_poly`、改变采样率后重新标记采样率等方式缩短或拉长对白；这些方法
  会同时改变基频和共振峰，产生明显的“变声”感。
- 输出按帧锁定到精确样本数：`samples = output_frames × (sample_rate / fps)`。time-stretch 后不足则
  补静音，超出则裁切；不得靠修改容器时长掩盖声画漂移。
- 对 0.5×–2.0× 以外的速度，将 `atempo` 拆成多个合法因子串联；系统声中含真实反馈时同样保持音高。
- 交付前至少选择三处自然口播（低音、正常语气、强调句）与 1.0× 源声 A/B 抽听，并记录
  `pitch_preservation: passed`。响度、True Peak 和“可完整解码”均不能证明音高没有改变。

示例（1.12×，保持音高）：

```bash
ffmpeg -i dialogue.wav -af "atempo=1.12,apad,atrim=end_sample=OUTPUT_SAMPLES" \
  -ar 48000 -c:a pcm_s16le dialogue-1.12x.wav
```

## 可复用的 FFmpeg 结构

对完整视频添加 BGM 时，可用 sidechain compressor 让原声控制 BGM 的衰减：

```bash
ffmpeg -y -hide_banner \
  -i SOURCE_VIDEO \
  -stream_loop -1 -i BGM_FILE \
  -filter_complex \
  "[1:a]volume=0.12,afade=t=in:st=0:d=1[bgm];\
   [bgm][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[ducked];\
   [0:a][ducked]amix=inputs=2:duration=first:dropout_transition=2,\
   loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
  -map 0:v:0 -map "[a]" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -ac 2 -shortest OUTPUT_MP4
```

该命令是结构示例。素材时长、BGM 起止点、视频段落和平台限制应以当前项目为准；渲染后仍需运行 `audio_qc.py`。
它只适合单条音乐床的录屏：单遍 `loudnorm` 是动态模式，会压扁多曲配乐设计好的电平，叙事片改用下文的线性母带。

## 分段混音

当最终播放段必须突出原声时，先把 BGM 处理成独立轨，再按 EDL 做以下决策：

1. 语音/操作段：原声 + 低电平 BGM。
2. 弹窗/等待段：原声保留到足以交代状态，BGM 可稍微抬起，但不能制造“成功”暗示。
3. 最终结果段：原声优先；关键播放声音出现时 BGM 降到听不见或暂时静音。
4. 结尾：保留真实余音，再让 BGM 和画面一起淡出。

## 叙事片多曲配乐（Vlog / 旅行 / 纪录 / 宣传片）

这组规则来自冈仁波齐 Vlog 的几轮纠偏：第一版只用同一作者的三首曲子分段进出，被判“太单一”；
第二版又把用户给的曲库收窄到对话里点名的几首，被纠正为“不限定范围，一切以成品效果为唯一依据”。
v0.2 用 8 首曲子、15 条 cue 通过了客观门禁，审片时又得到两条反馈：音乐和人声不必总是互斥，
有时一起放更好；很多段落之间的切换太短，意犹未尽或生硬突兀。下文的混音意图和过渡要求来自这两条。

### 选曲

- **用户给的曲库整体在范围内。** 先用 `bgm_tracks.py` 分析全部文件。用户在对话里提到的曲目只是线索，
  不是白名单；不按作者、歌单或“用户大概想要哪首”预筛，取舍只看成片效果。
- 无法解码的文件（例如加密的下载格式）会列进 `unplayable`，报告给用户并由用户提供可播放文件；
  不静默跳过，也不自行解密。
- **多曲混合。** 按章节和情绪曲线组合多首，不整片只用一首或同一作者的作品。同一段可以作为主题回环
  再次出现（例如开头与结尾呼应），重复同样要写理由。
- **每条 cue 都要有叙事或情绪理由。** 写进 cue 的 `rationale`：对应哪一幕、要带出什么情绪、
  为什么是这首的这一段、进出点落在什么画面或口播上。写不出理由的 cue 不进混音。
- 字卡或口播点名了某首歌或某位歌手时，那一段优先用被点名的音乐，其他段落不再用它，保住点名处的分量。
- **留白也是设计。** 身体到极限、到达顶点、人物独白、黑场问题卡这类时刻可以不放音乐，只留干声和
  环境声；一声铃或单个音效也可以代替整段配乐。超过 6 秒的无乐区间写进 `silences` 并注明理由，
  否则按疏漏处理。

### 歌词

- **与对白同语种的演唱歌词不得压在对白下。** 中文对白下不能出现中文歌词；`validate_cues.py` 把超过
  1 秒的重叠判为 ERROR（1 秒容差只用来吸收 LRC 行尾的估计误差）。解决办法是挪动 cue，或改用器乐段、
  前奏、间奏，不靠压低电平把歌词“藏”起来。
- 其他语种的演唱或吟唱压在对白下记为 WARN，需要在理由里说明它为什么不妨碍听懂。
- 歌词和屏幕字卡同时出现会抢阅读注意力，默认错开。只有歌词本身就是这一刻的意义时（例如唱句正好
  落在与它呼应的字卡上），才在 cue 上标 `"lyric_feature": true`，并在理由里写明呼应关系。
- 没有 `.lrc` 的曲目视为“歌词未知”，不能默认当纯音乐；确认是器乐后用 `bgm_tracks.py --instrumental KEY` 声明。

### 混音意图：人声和音乐不必互斥

每个时刻由剪辑判断选一种意图，写进 cue 表的 `mix_intents[{t0, t1, intent, reason}]`，未声明的时段按 `clear` 处理：

| 意图 | 听感 | 默认 ducking（整体 / 语音频段额外） |
| --- | --- | --- |
| `clear` | 音乐让开，信息句一字不漏 | `-13 dB` / `-8 dB` |
| `blend` | 音乐在人声下持续在场，一起推情绪 | `-7 dB` / `-6 dB` |
| `feature` | 音乐主导，人声骑在音乐上 | `-3 dB` / `-4 dB` |

- 情绪高点、抵达、回忆和收尾常用 `blend` 或 `feature`，这是正当的剪辑选择，不是混音失误；
  但要写 `reason`，说明为什么这里要让音乐留在人声下面。
- 交代事实、数字、地名、第一次出现的人物时用 `clear`。
- 区间可以单独写 `duck_db` / `band_cut_db` 覆盖默认深度；意图之间按 250 ms 渐变切换，不产生增益跳变。
- `blend` / `feature` 的默认深度是起始值，按耳朵和下面的 SMR、CER 结果校准，不是定律。
- 无论哪种意图，与对白同语种的演唱歌词都不能压在对白下。

### 结构与过渡

- 同一时刻最多两条 cue 发声。
- 段间要么交叉淡化（重叠 ≥ 1 秒，双方淡变都覆盖重叠区），要么在节拍或重音处卡点切换（不重叠）。
  1 秒只是能听成交叉淡化的下限；章节和段落之间用更长的溶解，硬切只留给有意的冲击。
- **过渡要留气口。** 关键句说完后停留一会儿再切；章节之间留一段由音乐主导的间奏；用 J-cut /
  L-cut 让声音先进或后出，而不是声画同时切。不要用一串 3–5 秒的字卡连续推进，`validate_cues.py`
  会把 3 张及以上、每张 ≤ 5 秒、间隔 ≤ 1 秒的连续字卡报为 WARN。
- 进出点避开曲子的响段；必须从响段进出时淡变 ≥ 2 秒。`tracks.json` 里的 `quiet_windows_s`、
  `rises_s`、`change_points_s` 用来找干净的进出点和卡点。
- 需要在某句对白或某张字卡下临时压低时，用 cue 的 `env` 包络点 `[[相对秒数, dB], ...]`，不要整条调低。

### 数据契约

| 文件 | 内容 |
| --- | --- |
| `tracks.json` | `bgm_tracks.py` 输出：每首的时长、逐秒响度与亮度、速度估计、安静窗/起势点/变化点、带语种标记的歌词行、`instrumental`（`true` / `false` / `null`），以及 `unplayable` |
| `film.json` | `duration`、`dialogue_language`（默认 `zh`）、`voice_spans[{t0,t1}]`、`text_spans[{t0,t1,text}]`（屏幕字卡） |
| `cues.json` | `cues[{id, track, track_in, at, dur, level_db 或 gain_db, fade_in, fade_out, env?, rationale, lyric_feature?}]`、`silences[{t0,t1,reason}]`、`mix_intents[{t0,t1,intent,reason,duck_db?,band_cut_db?}]`，可选 `duck_db` / `band_cut_db`（clear 的深度） |
| `voice.json` | `duration`、`lines[{id, file, at, lufs?, source?}]`、可选 `ambient[{file, at, dur, ss?, level_db?, source?}]`；相对路径按该文件所在目录解析 |

`level_db = 0` 对应该 cue 有声部分 `-27 dBFS RMS` 的音乐床，不同曲目按同一基准对齐听感响度。

### 客观门禁

```bash
python3 "$SKILL_DIR/scripts/bgm_tracks.py" --library MUSIC_DIR \
  --output WORK_DIR/music/tracks.json --summary WORK_DIR/music/tracks.md
python3 "$SKILL_DIR/scripts/validate_cues.py" --cues WORK_DIR/music/cues.json \
  --tracks WORK_DIR/music/tracks.json --film WORK_DIR/music/film.json --json WORK_DIR/music/cue-check.json
python3 "$SKILL_DIR/scripts/smr_check.py" --voice WORK_DIR/audio/voice.json --cues WORK_DIR/music/cues.json \
  --tracks WORK_DIR/music/tracks.json --output WORK_DIR/music/smr.json
python3 "$SKILL_DIR/scripts/score_mix.py" --voice WORK_DIR/audio/voice.json --cues WORK_DIR/music/cues.json \
  --tracks WORK_DIR/music/tracks.json --out-dir WORK_DIR/audio/mix --stems
python3 "$SKILL_DIR/scripts/intelligibility.py" --mix WORK_DIR/audio/mix/final-mix.wav --srt SUBS.srt \
  --floor WORK_DIR/audio/mix/stem-voice.wav --floor-output WORK_DIR/music/cer-floor.json \
  --output WORK_DIR/music/cer.json
```

| 门禁 | 通过标准 | 不通过时 |
| --- | --- | --- |
| `validate_cues.py` | 0 ERROR；每条 WARN 已修复，或在 cue 理由里写明原因 | 挪 cue、换段落、补理由或补 `silences` |
| `smr_check.py` | 500–3000 Hz 语音频段 SMR 按该句的混音意图判定：`clear` 中位数 ≥ 16 dB 且 p10 ≥ 8 dB；`blend` 中位数 ≥ 10 dB；`feature` 只记录 | 调低该句下的 cue、加 `env`、换更稀疏的段落，或有意改选意图 |
| `score_mix.py` | 母带 `-16 LUFS-I ±0.5`，True Peak ≤ `-3 dBTP` | 看 `mix-report.json` 的限幅量和重试记录 |
| `intelligibility.py` | 全片平均 CER 比纯人声底线高出不超过 0.02 | 按 `largest_regressions` 逐句抽听，找出被遮住的句子 |
| `audio_qc.py`（编码后） | 平台文件 True Peak < `-1 dBFS` | 回到母带降低天花板 |

SMR 和 CER 都是防止“听不清”的底线，不是“人声下音乐必须消失”的规则；表里的数值是校准参考，
不是定律。`clear` 的 16 / 8 dB 在冈仁波齐 v0.2 上验证过；`blend` 的 10 dB 是暂定值，等导演剪辑版
定稿后回填。`feature` 不看 SMR，但仍要过 CER 底线。

`smr_check.py` 与 `score_mix.py` 共用同一套总线构建和 ducking 代码，所以 SMR 在混音前就能跑，
模拟值就是最终混音的值。可懂度只按全片均值判定：单句 CER 噪声很大，已被接受的版本也有个别句子
比底线高出 1.0，逐句差值只用来决定先听哪几句。`intelligibility.py` 固定 `temperature=0`，同一音频
重跑结论一致；Whisper 的重复循环幻觉（例如 `icangoicango…`）会被单列为 `asr_loops` 供抽听，
混音和底线两侧同时剔除，不算作遮蔽证据。

冈仁波齐 v0.2 用本 Skill 脚本复跑：18 句全部是 `clear`，SMR 中位数最低 22.1 dB、p10 最低 9.7 dB；
69 条字幕 CER 混音 0.249，纯人声底线 0.237（+0.012）；母带 `-16.00 LUFS-I / -3.00 dBTP`，与项目
原混音做 null test 的残差为 `-78 dBFS RMS`。

### 混音引擎

- 人声：每句增益对齐到 `-20 LUFS`（最多提升 14 dB），整条人声总线用 look-ahead 限幅到 `-6 dBFS`。
- Ducking（`ducking.py`）：人声包络带 150 ms look-ahead，约 60 ms 起、500 ms 释放。`clear` 时说话期间
  音乐整体压 `-13 dB`，再只对音乐的 500–3000 Hz 语音频段额外压 `-8 dB`；低频和空气感保留，音乐床
  不会突然“消失”。`blend` / `feature` 按上文意图表用更浅的深度。环境声按一半深度跟随。
- 环境声片段与同时段口播来自同一源片段（`source` 相同）时丢弃这段环境声，否则同一句话会播两遍。
- 母带线性处理：先 look-ahead 限幅，再用 `ebur128` 测 I 和 TP，最后只乘一个静态增益到 `-16 LUFS`；
  增益后的 TP 超过天花板时压低限幅阈值重试。
- 不用 `loudnorm` 给叙事片做母带。单遍模式本身是动态的；双遍模式在线性增益会突破 TP 目标时，也会
  静默退回 dynamic（报告里是 `normalization_type: dynamic`），把设计好的 cue 电平和 ducking 一起压扁。
  `loudnorm` 只用来测量。
- **母带打到 `-3 dBTP`。** AAC 编码会让 True Peak 回升：冈仁波齐的 WAV 母带是 `-3.01 dBTP`，封装成 AAC
  后实测 `-2.37 dBTP`（+0.64 dB）。母带只留到 `-1.5` 的话，编码后就可能越过 `-1 dBFS`。编码后仍用
  `audio_qc.py` 复测平台文件。

### 运行环境

- `validate_cues.py` 只用标准库；`bgm_tracks.py`、`score_mix.py`、`smr_check.py` 需要 `numpy`；
  `intelligibility.py` 需要 `mlx-whisper`（Apple Silicon）或 `openai-whisper`，模型已缓存时加 `HF_HUB_OFFLINE=1`。
- 优先用已存在的持久虚拟环境运行这些脚本，例如作者机器上装好 numpy 与 mlx-whisper 的 `~/.venvs/mlxwhisper`。
  不要依赖 `uv run --with` 的临时环境：作者机器上的其他清理任务会清空 uv cache，重跑时要重新下载依赖，
  离线时直接失败。

## 质检门槛

参考目标为 `-16 LUFS-I ±1.5`，True Peak 低于 `-1 dBFS`；叙事片母带另按上文留到 `-3 dBTP`。如果平台或项目有不同规格，报告中同时写出目标与实际值。响度通过不代表内容听感通过，仍要人工确认人声、点击声和最终视频播放段。

Remotion Studio 是主预览时，必须播放这条已通过质检的最终混音，不能在 Studio 里重新叠加原始
麦克风、系统声和 BGM。预览音频与批准母版音频应同源；可直接从批准母版 stream copy 为浏览器友好
的 M4A，并在组件树中只挂载一次。

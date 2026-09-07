# Audio Mix

原声承担事实，BGM 承担氛围。两者同时存在时，观众应先听清人声、点击反馈和最终结果播放。

## 基本策略

- 默认 BGM 是已授权的 `Screen Studio Lo-fi / Bright Lounge`。早期程序合成 BGM 已废弃；不得运行、
  import 或复制前作的配乐合成脚本，也不得在约定素材缺失时自动生成替代曲。
- 约定 BGM 素材不可用时停止混音，记录 `audio_status=blocked-on-agreed-bgm` 并报告缺失项。
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

## 分段混音

当最终播放段必须突出原声时，先把 BGM 处理成独立轨，再按 EDL 做以下决策：

1. 语音/操作段：原声 + 低电平 BGM。
2. 弹窗/等待段：原声保留到足以交代状态，BGM 可稍微抬起，但不能制造“成功”暗示。
3. 最终结果段：原声优先；关键播放声音出现时 BGM 降到听不见或暂时静音。
4. 结尾：保留真实余音，再让 BGM 和画面一起淡出。

## 质检门槛

参考目标为 `-16 LUFS-I ±1.5`，True Peak 低于 `-1 dBFS`。如果平台或项目有不同规格，报告中同时写出目标与实际值。响度通过不代表内容听感通过，仍要人工确认人声、点击声和最终视频播放段。

Remotion Studio 是主预览时，必须播放这条已通过质检的最终混音，不能在 Studio 里重新叠加原始
麦克风、系统声和 BGM。预览音频与批准母版音频应同源；可直接从批准母版 stream copy 为浏览器友好
的 M4A，并在组件树中只挂载一次。

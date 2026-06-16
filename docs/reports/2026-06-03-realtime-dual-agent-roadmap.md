# 实时会议说话人分离：双 Agent 技术路线调研

> Date: 2026-06-03  
> Scope: 按当前“强音频基线 + 视觉一次注册 + 声纹记忆 + 语义后处理”路线，设计下一阶段实时/长期矫正方案。

## 核心结论

下一阶段不要只继续追求离线 DER。更有研究价值的路线是：

> **Fast Agent 负责实时输出可用但可被修正的 speaker timeline；Slow Agent 负责利用更长上下文、视觉一次注册、声纹记忆库和语义信息，对实时结果做延迟矫正与全局 ID 稳定。**

这样可以同时满足两个目标：

- 实时场景需要低延迟输出，不能等 DiariZen 全局推理。
- 研究指标需要更准确、更稳定的全局 speaker ID，不能只依赖短窗口在线模型。

## 1. 为什么要双 Agent

### 单一离线 Agent 的问题

DiariZen 在当前实验中是最强离线基线：

- 24 段 AliMeeting：DER 11.76%。
- 48 段：raw DER 21.04%，但中位数 11.14%，去掉一个极端 FA 段后均值 13.84%。

但它在 Mac CPU 上每 30s 段约 22-26s，不能直接支撑实时输出。

### 单一实时 Agent 的问题

Streaming Sortformer 这类模型适合 bounded latency，但准确率和 speaker ID 稳定性仍然是问题。NVIDIA 的 streaming Sortformer 官方模型卡给出了低延迟/超低延迟配置：

- low latency: input buffer latency 1.04s, RTF 0.093。
- ultra low latency: input buffer latency 0.32s, RTF 0.180。

但官方也说明它最多检测 4 个说话人，5 人及以上会退化；非英语、噪声、域外数据也可能退化。我们本地 24 段 Sortformer DER 为 23.45%，主要问题是 Miss 18.07%。

### 双 Agent 的合理性

实时系统天然可以分成两层：

- **Fast Agent**: 低延迟、持续输出、允许后续修正。
- **Slow Agent**: 高精度、长上下文、可回看历史、更新全局身份。

这和文献趋势一致：

- Streaming Sortformer 使用 speaker cache 维持在线说话人顺序和状态。
- LS-EEND 通过在线 attractor 处理长音频和灵活说话人数。
- S2SND 使用 speaker-embedding buffer，在线处理 block，并最终用最后的 buffer 重新打分整段音频。
- DiarizationLM 证明 LLM 更适合作为后处理，而不是直接做底层 diarization。

## 2. 推荐系统架构

```text
Audio stream + optional camera
        |
        v
Fast Agent: Streaming diarization
  - VAD / chunking
  - Streaming Sortformer or online embedding clustering
  - output: provisional segments, local speaker IDs, confidence
        |
        v
Shared State: Speaker Memory
  - global speaker profiles
  - voiceprint centroids
  - optional face embeddings / seat ID
  - local-to-global mapping history
        |
        +------------------------------+
        |                              |
        v                              v
UI / live transcript              Slow Agent
provisional result                - DiariZen offline resegmentation
                                  - visual one-shot enrollment
                                  - voiceprint memory update
                                  - LLM semantic speaker-label correction
                                  - abnormal-window detection
        |                              |
        +------------- correction patch+
                      |
                      v
          corrected global speaker timeline
```

## 3. Fast Agent 做什么

Fast Agent 的任务不是一次性做对，而是提供**实时、稳定、可修正**的初稿。

### 推荐输入输出

输入：

- 16kHz mono audio stream。
- 0.32s / 1.04s / 10s 三档 latency 配置。
- 可选：ASR token timestamps。

输出：

- `start`, `end`, `local_speaker_id`。
- 每帧或每段 speaker activity probability。
- `confidence`: 由 speech probability、speaker probability、embedding distance、overlap flag 合成。
- `revision_window_id`: 方便 Slow Agent 回写修正。

### 优先尝试方案

1. **Streaming Sortformer v2/v2.1**

最适合做第一版实时 baseline。原因：

- 官方支持 streaming 配置。
- 有 0.32s、1.04s、10s、30.4s 多档 latency。
- 和已有 `.venv_sortformer` 路线兼容。

下一步实验：

- 在 AliMeeting 上跑 0.32s、1.04s、10s、30.4s 四档。
- 指标不仅看 DER，还要看 latency、speaker count accuracy、跨窗口 ID switch。

2. **在线 embedding clustering baseline**

这是论文实现风险最低的工程备选：

- VAD 切 speech segment。
- 每 1-2s 提 ECAPA/Wespeaker embedding。
- 增量聚类到 speaker memory centroid。
- 低置信度片段先标 `unknown`，等待 Slow Agent 修正。

它不一定 DER 最好，但容易解释，也容易和声纹库结合。

3. **LS-EEND / S2SND 作为论文参考，不建议第一阶段实现**

这两个方向非常符合你的研究路线，但实现成本比 Sortformer 高：

- LS-EEND 是 frame-wise online EEND，目标是长音频和最多 8 人灵活说话人数。
- S2SND 使用 speaker-embedding buffer，在线 block 处理，并能用最终 buffer 重新打分整段音频。

建议先作为方法论支撑和后续增强方向。

## 4. Slow Agent 做什么

Slow Agent 的任务是**长期矫正**，不是实时输出。

### 4.1 离线强基线重分割

使用 DiariZen 对最近 N 分钟或完整会议做高精度重跑。

建议策略：

- 会议中：每 2-5 分钟对最近窗口做一次后台修正。
- 会议后：对全量音频做最终 resegmentation。
- 对 Fast Agent 的低置信度区域优先重跑。

### 4.2 视觉一次注册

视觉不是全程依赖，而是做 speaker identity prior：

- 会议开头或某人第一次明显发言时，检测 active speaker face。
- 抽取 face embedding / seat ID / person track。
- 将 active speaker face 与同时段 voice embedding 绑定。
- 后续视觉缺失时，用 voiceprint memory 维持身份。

这比持续 audio-visual fusion 更现实，也更像你的创新点。

### 4.3 声纹记忆库

Speaker memory 是整个系统的核心，而不是附属模块。

建议字段：

```json
{
  "global_speaker_id": "P01",
  "voice_centroids": [...],
  "face_embedding": "...",
  "seat_or_track_id": "cameraA_track3",
  "positive_segments": ["seg_001", "seg_010"],
  "negative_segments": ["seg_007"],
  "confidence": 0.91,
  "last_seen": 183.2,
  "update_policy": "high_confidence_only"
}
```

关键规则：

- 只用高置信度、非重叠、较长 speech segment 更新声纹。
- 如果 embedding distance 接近两个 speaker，暂不合并，标为 conflict。
- 对短回应“嗯/对/好”不直接更新声纹，只允许继承上下文 speaker。
- 允许新说话人发现，但要设置阈值，防止把同一个人拆成多个人。

### 4.4 LLM 语义级矫正

LLM 不直接做 diarization。只在有 ASR 文本和候选 speaker timeline 时做：

- speaker label smoothing。
- 称呼/角色推断。
- 连续问答关系修正。
- 短回应归属修正。

这和 DiarizationLM 的定位一致：把 ASR 和 diarization 输出转成紧凑文本，让 LLM 做后处理。

## 5. 你接下来最应该做的实验

## 5.0 当前落地进展

已完成第一版工程入口：

- Sortformer wrapper 已支持 `pipeline_params`。
- 新增 Streaming Sortformer checkpoint：
  - `nvidia/diar_streaming_sortformer_4spk-v2`
- 新增 latency preset：
  - `ultra_low_latency`
  - `low_latency`
  - `high_latency`
  - `very_high_latency`
- 新增脚本：
  - `scripts/run_streaming_sortformer_latency_sweep.sh`
  - `scripts/analyze_one_shot_identity_memory.py`
  - `scripts/analyze_voiceprint_memory.py`

Streaming Sortformer low-latency smoke：

```bash
SAMPLES=2 PRESETS=low_latency WINDOW_SIZE=90 \
OUTPUT_DIR=outputs/streaming_sortformer_latency_smoke \
bash scripts/run_streaming_sortformer_latency_sweep.sh
```

结果：

| Model | Preset | Samples | DER | Miss | FA | Conf | Spk match | Runtime |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Streaming Sortformer v2 | low_latency | 2 | 14.68% | 6.55% | 7.44% | 0.69% | 50.0% | 40.9s / 90s segment on Mac CPU |

解释：

- 代码路径和 streaming preset 已跑通。
- Mac CPU 运行不满足真实实时，但这不代表模型不能实时；NVIDIA 官方 RTF 是在 RTX 6000 Ada GPU 上给出的。
- 下一步应迁移到 GPU 跑完整 latency sweep。

One-shot identity memory simulation：

```bash
python scripts/analyze_one_shot_identity_memory.py \
  outputs/sortformer_uv_24/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  outputs/diarizen_uv_24/diarizen-large-v2/default__spk_none/summary.json \
  --enrollment-windows 1 \
  --output outputs/one_shot_memory/sortformer_diarizen_24.csv
```

平均结果：

| Model | Fixed first-window mapping | Per-window oracle mapping | Stability gap |
|---|---:|---:|---:|
| Sortformer 4spk v1 | 42.6% | 79.4% | 36.8% |
| DiariZen Large v2 | 38.1% | 72.8% | 34.6% |

解释：

- 如果只依赖首段注册后的固定 local speaker mapping，后续身份稳定性很差。
- 每窗口 oracle 明显更高，说明问题主要是跨窗口 speaker label 漂移，而不是所有片段本身完全不可分。
- 这直接支持“声纹记忆库 + Slow Agent 全局重分配”的必要性。

Real voiceprint memory prototype：

```bash
.venv_diarizen/bin/python scripts/analyze_voiceprint_memory.py \
  outputs/sortformer_uv_24/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  outputs/diarizen_uv_24/diarizen-large-v2/default__spk_none/summary.json \
  --enrollment-windows 1 \
  --match-threshold 0.35 \
  --update-threshold 0.55 \
  --output outputs/voiceprint_memory/sortformer_diarizen_24.csv
```

做法：

- 从每个窗口的预测 local speaker 片段中抽取 ECAPA speaker embedding。
- 首个窗口模拟视觉一次注册，初始化 global speaker memory。
- 后续窗口不再使用 GT，只按 embedding cosine similarity 映射到全局 speaker memory。
- GT 只在最后用于评估 global identity accuracy。

结果：

| Model | Fixed first-window mapping | Voiceprint memory | Per-window oracle | Assigned speech | Avg global spk |
|---|---:|---:|---:|---:|---:|
| Sortformer 4spk v1 | 42.6% | 79.1% | 79.4% | 99.8% | 3.2 |
| DiariZen Large v2 | 38.1% | 69.6% | 72.8% | 99.9% | 3.1 |

48 段扩展验证：

| Model | Fixed first-window mapping | Voiceprint memory | Per-window oracle | Assigned speech | Avg global spk |
|---|---:|---:|---:|---:|---:|
| Sortformer 4spk v1 | 31.5% | 68.8% | 74.0% | 99.9% | 3.9 |
| DiariZen Large v2 | 32.5% | 58.6% | 68.6% | 99.9% | 4.1 |

48 段 DER 对照：

| Model | DER | Miss | FA | Conf | Spk match | Latency |
|---|---:|---:|---:|---:|---:|---:|
| Sortformer 4spk v1 | 29.30% | 17.12% | 8.90% | 3.27% | 50.0% | 0.4s |
| DiariZen Large v2 | 21.04% raw / 11.14% median | 4.92% | 10.66% | 5.45% | 66.7% | 25.6s |

Latency / RTF 对照：

```bash
python scripts/analyze_latency_tradeoff.py \
  outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json \
  --output outputs/latency_tradeoff/main_models.csv
```

| Role | Model | Samples | Window | DER | Avg latency | P95 latency | RTF | Throughput |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Fast Agent | Sortformer 4spk v1 | 24 | 30s | 23.45% | 0.46s | 0.66s | 0.015 | 65.4x |
| Fast Agent | Sortformer 4spk v1 | 48 | 30s | 29.30% | 0.39s | 0.43s | 0.013 | 76.6x |
| Slow Agent | DiariZen Large v2 | 24 | 30s | 11.76% | 22.61s | 27.71s | 0.754 | 1.3x |
| Slow Agent | DiariZen Large v2 | 48 | 30s | 21.04% | 25.56s | 31.18s | 0.852 | 1.2x |
| Baseline | PyAnnote C1 no-count | 24 | 30s | 23.96% | 1.93s | 2.15s | 0.064 | 15.5x |
| Streaming smoke | Streaming Sortformer v2 | 2 | 90s | 14.68% | 40.85s | 41.09s | 0.454 | 2.2x |

时间口径：

- `avg_latency / p95_latency` 是模型拿到完整窗口后的本地推理耗时，不等同于在线首出延迟。
- `RTF < 1` 表示处理速度快于音频时长；Mac CPU 上 DiariZen 仍能接近实时吞吐，但它需要完整窗口/更长上下文，不适合直接作为 live first-pass。
- Sortformer 的 0.39-0.46s 是 Fast Agent 的核心优势：可以快速给出 provisional timeline。
- DiariZen 的价值是后台成熟窗口回写：它慢得多，但能把 48 段 DER 从 29.30% 修到 21.04%。
- Streaming Sortformer smoke 在 Mac CPU 上可跑通代码路径；真实实时性还需要 GPU latency sweep 验证。

DER-latency Pareto 汇总：

```bash
python scripts/build_der_latency_pareto.py
```

| Candidate | Role | Scope | DER | Avg delay | P95 delay | RTF | Evidence | Verdict |
|---|---|---|---:|---:|---:|---:|---|---|
| Sortformer 120 | fast provisional | 120 windows / 30s | 28.56% | 0.38s | 0.44s | 0.013 | direct benchmark | fast but high miss |
| DiariZen 120 | slow correction | 120 windows / 30s | 16.88% | 24.65s | 28.33s | 0.822 | strong slow baseline; async, one extreme outlier remains | slow baseline |
| DiariZen 120 median | slow correction robust statistic | 120 windows / 30s | 10.83% | 24.65s | 28.33s | 0.822 | median reduces single outlier effect | strong slow baseline, not first-output path |
| Dual Agent first output | system stage | 120 windows / staged | 28.56% | 0.38s | 0.45s | 0.013 | provisional timeline | user-visible real-time layer |
| Dual Agent rule writeback | system stage | 120 windows / staged | 26.40% | 24.65s | 28.33s | 0.822 | timeline v0; 93 recover patches; recover 60.2% Fast miss | main deployable correction layer |
| Dual Agent selector holdout | recording-holdout selector validation | 8 recording splits / 120 windows | 26.51% | 24.65s | 28.33s | 0.822 | 8/8 held-out positive; +2.05pp vs Fast | selector threshold check before true held-out |
| Dual Agent runtime-safe LLM guard | runtime-safe safety layer | 104 proxy-flag windows / staged | n/a | 44.92s | 63.85s | n/a | 1917 patches; harmful accept 0; conservative blocks 1811; window override 2 | runtime-safe guard; conservative by design |
| Dual Agent LLM review signal | system stage | 120 windows / staged | n/a | 46.10s | 55.80s | n/a | blocks writeback 0 / memory 4 | review/memory protection only; no timeline writeback |

Pareto 结论：

- 单模型 Pareto 没有同时满足低 DER 和低延迟：Sortformer 0.38s 可首出但 miss 高，DiariZen median DER 10.83% 但只能作为异步慢层。
- 双 Agent 的真实目标不是让一个模型同时最优，而是把体验拆成四个到达/审计时间：`0.38s first output`、`24.65s rule writeback`、`44.92s runtime-safe LLM guard`、`46.10s LLM review/memory signal`。
- 长期 DER 的改进方向应集中在 selector/writeback 学习：当前 recording-holdout selector 120 段 DER 26.51%，8/8 held-out split 均正向，说明策略不是单录音过拟合。
- 这也解释了为什么 LLM/Omni 不应该直接做 diarization：它们更适合做兜底、风险识别、证据补充和高风险隔离，而不是替代专业声学分离模型。

解释：

- 48 段上 fixed first-window mapping 继续下降，说明窗口越长，local speaker label drift 越严重。
- 声纹记忆在 48 段仍能显著提升全局身份一致性，但低于 24 段，说明下一阶段的真正优化点是 memory drift / speaker fragmentation 治理。
- Sortformer 48 段 raw DER 出现 324.6% 极端段，DiariZen 48 段也有 359.49% 极端 FA 段；异常窗口检测需要成为 Slow Agent 的一部分。

Abnormal-window detector：

```bash
python scripts/analyze_abnormal_windows.py \
  outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json \
  --output outputs/abnormal_windows/sortformer_diarizen_48.csv
```

异常规则：

- `DER >= 100%`
- `FA >= 50%`
- `Miss >= 50%`
- predicted speech / GT speech `>= 2.0` 或 `<= 0.5`
- predicted speaker count 与 GT speaker count 不一致

48 段异常分布：

| Model | Abnormal windows | Speaker count mismatch | High Miss | High FA | Speech too short | Speech too long |
|---|---:|---:|---:|---:|---:|---:|
| Sortformer 4spk v1 | 25 | 24 | 3 | 1 | 3 | 1 |
| DiariZen Large v2 | 17 | 16 | 0 | 1 | 0 | 1 |

解释：

- 两个模型的大部分异常都和 speaker count mismatch 有关，说明 Slow Agent 不应只看 DER，而应主动监控 speaker count、speech ratio 和异常 FA/Miss。
- Sortformer 的典型错误是少说话人/漏语音，适合由 DiariZen 或长上下文重分割补救。
- DiariZen 的典型错误少，但一旦出现极端 FA，会严重污染 raw DER 和声纹库，需要异常窗口隔离。

Fast-to-Slow correction prototype：

```bash
python scripts/analyze_fast_slow_correction.py \
  --fast-summary outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  --slow-summary outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json \
  --output outputs/fast_slow_correction/sortformer_diarizen_48_patches.csv
```

窗口级 correction 结果：

| Setting | Samples | DER | Miss | FA | Conf | 说明 |
|---|---:|---:|---:|---:|---:|---|
| Fast only: Sortformer | 24 | 23.45% | 18.07% | 2.44% | 2.95% | 低延迟初稿 |
| Delayed Slow: DiariZen | 24 | 11.76% | 3.70% | 4.05% | 4.01% | 后台成熟窗口替换 |
| Heuristic Fast+Slow | 24 | 17.20% | 9.72% | 4.11% | 3.38% | 只替换 11/24 个可疑窗口 |
| Oracle selector upper | 24 | 11.69% | 3.80% | 3.94% | 3.95% | 每窗选择 Fast/Slow 较低 DER，上限 |
| Fast only: Sortformer | 48 | 29.30% | 17.12% | 8.90% | 3.27% | 低延迟初稿 |
| Delayed Slow: DiariZen | 48 | 21.04% | 4.92% | 10.66% | 5.45% | 后台成熟窗口替换 |
| Heuristic Fast+Slow | 48 | 24.78% | 12.09% | 9.29% | 3.40% | 只替换 15/48 个可疑窗口 |
| Oracle selector upper | 48 | 20.04% | 5.80% | 9.39% | 4.85% | 每窗选择 Fast/Slow 较低 DER，上限 |

Routing 统计：

| Samples | Slow better windows | Heuristic selected Slow | Coverage | Precision | Regressions |
|---:|---:|---:|---:|---:|---:|
| 24 | 23/24 | 11/24 | 43.5% | 90.9% | 1 |
| 48 | 44/48 | 15/48 | 34.1% | 100.0% | 0 |

解释：

- 双 Agent 不是只“叠模型”：Fast 提供 0.4s 量级的实时初稿，Slow 在后台把成熟窗口从 23-29% DER 拉到 12-21% DER。
- 24 段上 Delayed Slow 与 Oracle selector 几乎重合，说明 DiariZen 后台替换已经接近窗口级最优。
- 48 段上 Oracle selector 只比 Delayed Slow 多降 1.00 DER point，说明主要收益来自 Slow 重分割；下一步重点不是复杂 routing，而是隔离 DiariZen 极端 FA 窗口。
- 当前 heuristic routing 精度高但覆盖低，适合作为“低风险早期修正”；真正的系统应采用“默认后台回写 + 异常窗口隔离 + 片段级 patch”。

Segment-level correction patch：

```bash
python scripts/analyze_segment_level_patches.py \
  --fast-summary outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  --slow-summary outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json \
  --patch-output outputs/segment_patches/sortformer_diarizen_48_patches.csv
```

patch 类型：

- `keep_fast_supported`: Fast 段被 Slow 时间重叠支持，可以保留。
- `boundary_fix_or_relabel`: Fast 段被 Slow 支持，但边界/标签应以后者为准。
- `recover_slow_segment`: Slow 检出而 Fast 缺失的段，候选补漏检。
- `suppress_fast_candidate`: Fast 检出但 Slow 不支持的段，候选抑制 FA。

结果：

| Samples | Patch rows | Fast miss | Slow recovers Fast miss | Recovery rate | Fast FA | Slow suppresses Fast FA | Suppression rate | Slow added FA |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 467 | 46.68s | 42.32s | 90.7% | 13.28s | 8.06s | 60.7% | 6.26s |
| 48 | 953 | 87.38s | 80.04s | 91.6% | 50.20s | 19.88s | 39.6% | 12.42s |

patch 计数：

| Samples | keep_fast_supported | boundary_fix_or_relabel | recover_slow_segment | suppress_fast_candidate |
|---:|---:|---:|---:|---:|
| 24 | 57 | 168 | 21 | 0 |
| 48 | 114 | 338 | 47 | 4 |

解释：

- Slow 对 Fast 的漏检补偿非常稳定：24/48 段都能补回约 91% 的 Fast missed speech。
- FA 抑制不稳定：24 段可抑制 60.7%，48 段只有 39.6%，并且 Slow 自己新增 FA；这解释了为什么 DiariZen Miss 很低但 FA 会拉高 raw DER。
- `recover_slow_segment` 可信度高：24 段 21/21、48 段 43/47 有真实语音支撑；适合做积极补漏检。
- `suppress_fast_candidate` 数量少且不总是纯 FA：48 段 2/4 是真正 FA；抑制策略必须谨慎，不能简单“Slow 不支持就删除”。
- 最合理的片段级策略是：**积极 recover_miss，保守 suppress_fa，边界和 label 以后端 Slow + memory 为准，极端窗口 quarantine**。

Policy Agent / LLM 规范指导层：

```bash
python scripts/policy_agent_decisions.py \
  --patches outputs/segment_patches/sortformer_diarizen_48_patches.csv \
  --windows outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --abnormal-windows outputs/abnormal_windows/sortformer_diarizen_48.csv \
  --memory outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --output-jsonl outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl
```

Agent 输入：

- segment-level patch 表：`keep_fast_supported / boundary_fix_or_relabel / recover_slow_segment / suppress_fast_candidate`
- abnormal-window flags：`high_der / high_fa / high_miss / speaker_count_mismatch / speech_ratio`
- speaker memory quality：global identity accuracy、assigned speech rate、global speaker count

Agent 输出：

```json
{
  "patch_id": "R8001_M8004:30:1:slow:slow_4",
  "decision": "accept | reject | defer | quarantine",
  "reason": "recover_miss_high_confidence",
  "constraints": ["do_not_update_memory_on_short_segment"],
  "next_action": "write_slow_segment_to_timeline",
  "confidence": 0.9
}
```

规则版 Policy Agent 结果：

| Samples | Decisions | Accept | Defer | Quarantine | Accepted recover true speech | Accepted suppress true FA |
|---:|---:|---:|---:|---:|---:|---:|
| 24 | 467 | 441 | 26 | 0 | 100.0% | n/a |
| 48 | 953 | 802 | 150 | 1 | 100.0% | 100.0% |

48 段 defer / quarantine 主要原因：

| Reason | Count | 解释 |
|---|---:|---|
| `memory_low_confidence_relabel_deferred` | 112 | 声纹身份一致性低，暂不自动 relabel |
| `recover_segment_too_short` | 22 | 片段太短，不更新声纹，等待合并/上下文 |
| `boundary_patch_from_slow_abnormal_window` | 14 | Slow 窗口异常，边界修正暂缓 |
| `do_not_suppress_without_strong_evidence` | 2 | FA 抑制证据不足，保留 Fast |
| `recover_from_slow_abnormal_window` | 1 | 极端 FA 窗口进入 quarantine |

解释：

- 这就是 Agent/LLM 的合理位置：**不直接做 diarization，而是做规范约束、patch 仲裁、异常隔离和语义级 label smoothing**。
- 规则 Agent 先提供可复现 baseline；LLM 后续可以读取这些结构化字段，生成更细致的理由或处理规则冲突，但不能自由改时间戳。
- 这条路线能把“LLM 输出不稳定”的缺点转成优势：让 LLM 只在受约束的 patch decision space 里工作。

真实 LLM Policy Agent mixed patch 对照：

```bash
python scripts/llm_policy_agent_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --selection mixed \
  --include-accept \
  --model qwen3.6-flash-2026-04-16 \
  --max-items 18 \
  --output-jsonl outputs/llm_policy_agent/qwen36_flash_48_mixed18.jsonl
```

测试模型来自阿里百炼 OpenAI-compatible 接口，本轮真实可用模型池为 `qwen3.7-plus`、`deepseek-v4-flash`、`qwen3.6-flash-2026-04-16`、`qwen3.6-35b-a3b`、`glm-5.1`。mixed set 不只抽 high-risk，也覆盖 `accept/defer/quarantine` 和 `recover/boundary/suppress/keep/align` 五类 patch：

| Model | Samples | LLM decisions | Agreement | Avg call | P95 call | 观察 |
|---|---:|---|---:|---:|---:|---|
| qwen3.6-flash-2026-04-16 | 18 | accept 3 / defer 10 / quarantine 5 | 44.4% | 8.91s | 12.98s | mixed 样本下仍偏保守，但会接受少量明确 patch |
| qwen3.7-plus | 8 | accept 1 / defer 5 / quarantine 2 | 50.0% | 14.44s | 18.57s | 更慢，策略偏 defer/quarantine |
| deepseek-v4-flash | 8 | defer 6 / reject 1 / quarantine 1 | 50.0% | 7.33s | 8.79s | 当前最快；更倾向 reject/defer 而不是 accept |
| glm-5.1 | 8 | defer 5 / reject 1 / quarantine 2 | 25.0% | 17.09s | 23.33s | 最慢，适合离线复核，不适合在线 |
| qwen3.6-35b-a3b | 8 | defer 5 / reject 1 / quarantine 2 | 37.5% | 10.25s | 12.43s | 比 flash 慢，保守性接近 glm |

解释：

- LLM 没有被允许直接改时间戳或重写 diarization，只能在 `accept/reject/defer/quarantine` 中仲裁。
- 在 R8003_M8001 seg=5 这类双方都 high-DER/high-FA 的异常窗口上，LLM 倾向比规则 Agent 更保守，把部分 `defer` 升级为 `quarantine`。
- mixed patch 里，LLM 会把不少规则 `accept` 降级为 `defer/reject/quarantine`，说明它更像安全审计器，而不是自动写回器。
- 调用延迟在 7.33s-17.09s/patch 之间，远高于 Sortformer 的 0.39s/window，因此 LLM Policy Agent 只能进入 Slow Agent 的异步修正链路，不能进入实时首出路径。
- 这证明 LLM/Agent 的价值点可以是“规范指导与风险仲裁”，而不是替代底层 diarization 模型。

LLM 触发预算：

```bash
python scripts/analyze_llm_trigger_budget.py
```

48 段当前共有 953 个结构化 patch，覆盖 48 个 30s 窗口。关键不是“能不能调用 LLM”，而是**用规则 gating 控制调用量**：

| Trigger policy | LLM calls | Patch rate | Windows touched | 说明 |
|---|---:|---:|---:|---|
| all_patch_audit | 953 | 100.0% | 48 | 诊断上界，不适合真实系统 |
| non_accept_review | 151 | 15.8% | 21 | 只审 `defer/quarantine`，1 个 deepseek worker 可异步跟上 |
| semantic_label_smoothing | 136 | 14.3% | 20 | 主要处理 memory-low relabel、短 recover、suppress 冲突 |
| writeback_guard | 177 | 18.6% | 28 | 审所有 risky writeback，更保守 |
| high_risk_quarantine | 23 | 2.4% | 4 | 只审 high-DER/high-FA 和 suppress candidate |

用当前最快的 `deepseek-v4-flash` 估算：

| Trigger policy | Calls | Total avg LLM time | Async RTF | Workers to keep up |
|---|---:|---:|---:|---:|
| all_patch_audit | 953 | 6981.7s | 4.848 | 5 |
| non_accept_review | 151 | 1106.2s | 0.768 | 1 |
| semantic_label_smoothing | 136 | 996.3s | 0.692 | 1 |
| high_risk_quarantine | 23 | 168.5s | 0.117 | 1 |

系统含义：

- **实时路径**：Sortformer 输出 + 规则异常检测，不等待 LLM。
- **慢路径默认**：DiariZen 成熟窗口回写 + Rule Policy Agent。
- **LLM 触发**：优先 `high_risk_quarantine`；需要语义修正时开启 `semantic_label_smoothing`。
- 这个设计把 LLM 成本从“每个 patch 都审”压到 2.4%-15.8% 的触发率，才真正适合实时会议场景。

LLM 安全画像：

```bash
python scripts/analyze_llm_policy_safety.py
```

该评估在 LLM 调用后离线 join `gt_support_ratio_eval_only`，没有把真值暴露给 LLM。安全口径：

- `suppress_fast_candidate` 被 accept 时，要求 `gt_support_ratio <= 0.2`，否则可能误删真人声。
- 其他 patch 被 accept 时，要求 `gt_support_ratio >= 0.5`，否则可能把非真实语音或低质量片段写回。
- 规则 `accept` 被 LLM 改成 `defer/reject/quarantine` 记为 conservative block，代表安全但降低自动写回率。

| Model | Samples | Decisions | Safe accepts | Harmful accepts | Conservative blocks | Accept precision |
|---|---:|---|---:|---:|---:|---:|
| qwen3.6-flash-2026-04-16 | 18 | accept 3 / defer 10 / quarantine 5 | 3 | 0 | 7 | 100.0% |
| qwen3.7-plus | 8 | accept 1 / defer 5 / quarantine 2 | 1 | 0 | 3 | 100.0% |
| deepseek-v4-flash | 8 | defer 6 / reject 1 / quarantine 1 | 0 | 0 | 4 | n/a |
| glm-5.1 | 8 | defer 5 / reject 1 / quarantine 2 | 0 | 0 | 4 | n/a |
| qwen3.6-35b-a3b | 8 | defer 5 / reject 1 / quarantine 2 | 0 | 0 | 4 | n/a |

解释：

- 这批 mixed patch 中没有模型产生 harmful accept，说明受约束 JSON decision space 有效压住了 LLM 的危险自由度。
- `qwen3.6-flash` 和 `qwen3.7-plus` 在单 patch mixed 样本里出现过少量 safe accept，但这只能说明“候选写回器值得继续测”，不能说明已经可以自动写回；后续 window-batch 与声纹增强实验显示它们明显更保守。
- `deepseek-v4-flash` 最快，但完全不自动 accept，更适合作为“快速复核/异常隔离”模型，而不是自动写回模型。
- `glm-5.1` 延迟最高且一致率较低，当前更适合离线参考，不适合作为主路由。
- 下一步如果要提高自动修正率，不能单靠 prompt 催 LLM 更激进，而应给 LLM 增加 ASR 语义证据、speaker memory confidence、邻接段一致性，让它有证据从 `defer` 转 `accept`。

推荐 LLM 路由：

```bash
python scripts/build_llm_policy_routing.py
```

| Route | Trigger | Model | Calls | Async RTF | Safety | Action |
|---|---|---|---:|---:|---|---|
| live_first_pass | none | none | 0 | 0.000 | n/a | never wait for LLM |
| rule_writeback | writeback_gate | none | 172 | 0.000 | rule support / harmful 0 / recover 57.5% Fast miss | rule agent writeback |
| high_risk_guard | high_risk_quarantine | deepseek-v4-flash | 23 | 0.117 | harmful 0 / conservative 4 | defer or quarantine |
| backup_high_risk_guard | high_risk_quarantine | qwen3.6-flash-2026-04-16 | 23 | 0.142 | batch safe 0 / harmful 0 / conservative 9 | backup defer or quarantine |
| llm_candidate_audit | low_risk_writeback_gate | qwen3.6-flash-2026-04-16 | 0 | 0.000 | single-patch safe 3 / batch safe 0 / gate candidates 0 | audit only, no current writeback |
| semantic_review_ablation | semantic_label_smoothing | qwen3.6-flash-2026-04-16 | 136 | 0.842 | single-patch safe 3 / batch safe 0 | offline evidence-design ablation |
| offline_cross_check | non_accept_review | qwen3.7-plus | 151 | 1.514 | safe 1 / harmful 0 | second opinion only |
| excluded_from_main_path | manual_only | glm-5.1 | 0 | 0.000 | latency too high | offline reference |
| excluded_from_main_path | manual_only | qwen3.6-35b-a3b | 0 | 0.000 | slower than flash / no accept in mixed eval | offline reference |

最终系统策略：

- **规则 Agent = 当前写回执行器**：172 个 patch 已通过 low-risk gate，其中 recover 类覆盖 57.5% Fast miss；这是现阶段真正能带来修正收益的写回路径。
- **deepseek-v4-flash = 守门员**：只处理 high-DER/high-FA、suppress candidate、quarantine 类事件；目标是快速隔离污染窗口。
- **qwen3.6-flash = 备用守门 + 候选写回审计器**：full high-risk batch 延迟接近 deepseek，但隔离更不积极；单 patch 下有少量 safe accept，但 window-batch、真实声纹、oracle transcript 后仍偏 `defer/quarantine`，当前 gate 中 `llm_writeback_candidate=0`。
- **qwen3.7-plus = 离线二审**：用于论文/汇报中解释模型分歧，不进入实时主链路。
- **qwen3.6-35b-a3b = 离线参考**：比 flash 慢，且 mixed safety eval 没有表现出更强的 accept 能力，不适合替换 flash 做主路由。
- **glm-5.1 = 暂不主路由**：当前延迟和一致率都不支持把它放进核心系统。

端到端时间线模拟与当前系统时间指标：

```bash
python scripts/simulate_dual_agent_timeline.py
python scripts/build_system_timeline_summary.py
```

口径：旧模拟用于证明 “逐 patch 调 LLM 会排队失控”；当前系统口径以实测 Fast/Slow/LLM batch 时间为准。Fast 在窗口结束后输出 provisional timeline，DiariZen 后台输出 mature patch，Rule Agent 先做 low-risk writeback，LLM 只处理高风险 guard 或离线审计。

| Stage | Agent | Avg delay | P95 delay | Patches | Benefit | Metric |
|---|---|---:|---:|---:|---|---|
| fast_provisional | Sortformer | 0.38s | 0.45s | 0 | provisional timeline | DER 28.56% / RTF 0.013 |
| rule_writeback | DiariZen + Rule Agent | 24.65s | 28.33s | 599 | recover 60.2% Fast miss | 197.36s unique miss recovered |
| llm_guard | DiariZen + deepseek-v4-flash | 44.92s | 63.85s | 1917 | runtime-safe quarantine/review guard | 104 windows / harmful accept 0 / P95 63.8s |

系统含义：

- LLM 不能按 patch 逐条调用，否则 burst queue 会把修正推迟到数分钟后；这也是放弃 “LLM 直接写回主链路” 的主要实时性理由。
- 正确做法是**规则先写回、LLM 只批量守门**：一个成熟窗口内的高风险 patch 一起交给 LLM，低风险修正由 Rule Agent 直接落地。
- 当前可陈述的用户体验是：0.38s 首出，约 24.65s 后完成规则写回，约 44.92s 平均 / 63.85s P95 完成 runtime-safe LLM 隔离/复核。
- 因此双 Agent 架构应显式区分：
  - `Fast provisional`: 0.38s/window，本轮会议实时可见。
  - `Slow correction`: DiariZen + Rule Agent，约 24-28s 后写回主要修正。
  - `LLM guard`: runtime-safe deepseek window batch，约 45-64s 后隔离高风险窗口；qwen 当前只保留为候选审计/离线二审。

真实 window-batch LLM 验证（legacy 4-window development probe，当前主口径见后文 runtime-safe 104-window guard）：

```bash
python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy high_risk_quarantine \
  --model deepseek-v4-flash \
  --output-jsonl outputs/llm_window_batch/deepseek_high_risk_48.jsonl

python scripts/summarize_llm_window_batch_results.py
```

| Run | Model | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay |
|---|---|---:|---:|---|---|---:|---:|---:|
| deepseek_high_risk_48 | deepseek-v4-flash | 4 | 23 | quarantine 1 / review 3 | defer 4 / quarantine 19 | 14.93s | 40.50s | 47.95s |

batch safety：

```bash
python scripts/analyze_llm_window_batch_safety.py
```

| Windows | Patches | Window decisions | Patch decisions | Safe accepts | Harmful accepts | Conservative blocks | Safe blocks | High-error quarantined |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 4 | 23 | quarantine 1 / review 3 | defer 4 / quarantine 19 | 0 | 0 | 9 | 14 | 1 |

解释：

- 真实 batch 调用覆盖了 high-risk guard 的全部 4 个窗口/23 个 patch，schema 全部通过。
- 最危险窗口 `R8003_M8001:30:5` 一次处理 19 个 patch，模型给出 window-level `quarantine`，并将 19 个 patch 全部 `quarantine`。
- 小窗口更倾向 `review/defer`，没有产生自动 accept，符合 high-risk guard 的守门员定位。
- batch safety 中 `harmful_accepts = 0`，同时 `conservative_blocks = 9`；这说明 deepseek 守门员足够安全，但不会主动提高自动写回率。
- 实测平均 LLM batch call 为 14.93s，高于单 patch deepseek 均值 7.33s；因此 high-risk guard 的真实平均到达时间应按 `25.56s DiariZen + 14.93s LLM = 40.50s` 估算。
- 这组 4-window legacy probe 证明了 batch guard 可行，但它依赖旧 high-risk/eval-derived 异常口径；当前主系统表已经切换到 runtime-safe 104-window guard，完整 correction arrival 为 44.92s avg / 63.85s P95。这条链路的时间指标已经和 DER 同等重要：Sortformer 决定首出体验，DiariZen + LLM 决定后台修正到达时间。

high-risk guard 模型对比：

```bash
python scripts/build_guard_model_comparison.py
```

| Role | Model | Scope | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay | Safety |
|---|---|---|---:|---:|---|---|---:|---:|---:|---|
| primary_guard | deepseek-v4-flash | full high-risk set | 4 | 23 | quarantine 1 / review 3 | defer 4 / quarantine 19 | 14.93s | 40.50s | 47.95s | safe 0 / harmful 0 / conservative 9 |
| backup_guard_candidate | qwen3.6-flash-2026-04-16 | full high-risk set | 4 | 23 | quarantine 1 / clean 3 | defer 21 / quarantine 1 / reject 1 | 18.50s | 44.06s | 59.21s | safe 0 / harmful 0 / conservative 9 |
| offline_second_opinion | qwen3.7-plus | top-2 high-risk windows | 2 | 21 | quarantine 1 / review 1 | defer 16 / quarantine 5 | 54.22s | 79.78s | 106.03s | safe 0 / harmful 0 / conservative 8 |

对比结论：

- `deepseek-v4-flash` 仍是 primary guard：覆盖完整 high-risk set，平均修正延迟最低，patch-level quarantine 最积极。
- `qwen3.6-flash-2026-04-16` 可以作为 backup guard candidate：全量 high-risk 延迟接近 deepseek，但更偏 `clean/defer`，patch-level quarantine 只有 1 个，隔离积极性明显弱于 deepseek。
- `qwen3.7-plus` 安全但太慢：平均修正延迟接近 80s，最大超过 100s，只适合离线二审。
- 三者均为 `harmful_accepts=0`，说明受约束 JSON decision space 有效；真正区分模型角色的是**延迟和隔离积极性**，不是 accept 数量。

Omni audio guard smoke：

这一步测试全模态模型不是为了替代 diarization，而是验证它能否作为实时系统的“早期兜底感知 Agent”：听短音频，给结构化风险、粗 speaker count、是否 defer/quarantine。

```bash
python scripts/omni_audio_guard_smoke.py \
  --model qwen3.5-omni-flash \
  --model qwen3.5-omni-plus \
  --duration-sec 8 \
  --output-jsonl outputs/omni_guard/omni_flash_plus_audio_guard_8s.jsonl

python scripts/omni_audio_guard_smoke.py \
  --model qwen3.5-omni-flash-2026-03-15 \
  --model qwen3.5-omni-plus-2026-03-15 \
  --duration-sec 8 \
  --output-jsonl outputs/omni_guard/omni_dated_audio_guard_8s.jsonl

python scripts/omni_realtime_guard_smoke.py \
  --model qwen3.5-omni-flash-realtime \
  --duration-sec 8 \
  --timeout-sec 30 \
  --output-jsonl outputs/omni_guard/qwen35_omni_flash_realtime_guard_8s.jsonl

python scripts/build_omni_guard_summary.py
```

| Model | Interface | Clip | Call | First text | Schema | Risk | Quarantine | Defer | Direct diarizer | Reason |
|---|---|---:|---:|---:|---|---|---|---|---|---|
| qwen3.5-omni-flash | openai_compatible_audio | 8.0s | 1.288s |  | True | medium | False | True | False | brief_overlap_detected |
| qwen3.5-omni-plus | openai_compatible_audio | 8.0s | 5.895s |  | True | medium | False | True | False | brief_overlap_detected |
| qwen3.5-omni-flash-2026-03-15 | openai_compatible_audio | 8.0s | 1.372s |  | True | medium | False | True | False | minor_overlap_and_fade |
| qwen3.5-omni-plus-2026-03-15 | openai_compatible_audio | 8.0s | 7.289s |  | True | high | True | True | False | heavy_overlap_at_start_confuses_turn_boundaries |
| qwen3.5-omni-flash-realtime | dashscope_realtime_websocket | 8.0s | 1.356s | 0.744 | True | low | False | True | False | short_snake_case |

Omni 结论：

- `qwen3.5-omni-flash` 系列能在 1.3s 左右给出结构化风险 JSON，适合做“早期听觉风险探针”：发现 overlap/crosstalk、提示 defer、给粗粒度 speaker_count_guess。
- `qwen3.5-omni-plus` 更慢但更保守，dated plus 对同一片段给出 high risk + quarantine，可作为离线或慢速二审兜底。
- `qwen3.5-omni-flash-realtime` WebSocket 已跑通，首个文本事件 0.744s、总耗时 1.356s；这很适合实时 UI/Agent 提前打风险标签，但当前 reason 仍偏模板化，需要更严格 prompt 和多片段统计。
- 所有 Omni smoke 都返回 `usable_as_direct_diarizer=false`，这与旧 Omni-Plus DER>30% 的经验一致：Omni 不做主分离，做兜底感知/规范指导/异常解释。
- 下一步更规范的实验应把 Omni guard 输出接入 Rule Agent：若 Omni 检测 `strong overlap/high risk`，则提高 slow review 优先级或触发 quarantine；若 Omni 只给 medium risk，则只打标签，不直接改 timeline。当前已完成一个 12-window fusion smoke，验证这条接入规则不会给 Omni 写回时间戳的权限。

Omni window-batch 小样本：

为验证 Omni 是否能区分真实异常窗口，自动从 48 窗口中选取 high / medium / clean 各 2 个窗口，每个窗口取开头 8s 音频：

```bash
python scripts/omni_guard_window_batch.py \
  --model qwen3.5-omni-flash \
  --model qwen3.5-omni-plus-2026-03-15 \
  --per-bucket 4 \
  --clip-sec 8 \
  --output-jsonl outputs/omni_guard/omni_flash_plus_window_batch_12.jsonl

python scripts/summarize_omni_window_batch.py \
  outputs/omni_guard/omni_flash_plus_window_batch_12.csv
```

| Model | Windows | Risk counts | High positive | Clean false positive | Quarantine | Defer | Avg call | P95 call | Max call | Verdict |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| qwen3.5-omni-flash | 12 | low 8 / medium 4 | 2/4 | 2/4 | 0 | 7 | 2.113s | 6.408s | 12.426s | fast risk hint, weak recall |
| qwen3.5-omni-plus-2026-03-15 | 12 | high 1 / low 8 / medium 3 | 2/4 | 1/4 | 1 | 12 | 5.059s | 6.138s | 6.278s | conservative high-risk sentinel |

窗口级结论：

- Omni 能抓住部分重叠/串扰窗口：`R8007_M8010:30:4` 被 flash 判 medium、plus dated 判 high + quarantine；`R8003_M8001:30:5` 也被两个模型判到 medium。
- 但 `R8001_M8004:30:1` 和 `R8001_M8004:30:3` 这类 high DER 窗口是“声学模型漏检/人数错但 8s 片段听起来清晰”的类型，Omni 判 low；这说明 Omni 不适合做全面 DER 异常检测。
- clean 窗口中 `R8009_M8019:30:0` 和 `R8003_M8001:30:3` 被 flash 判 medium，plus dated 也对 `R8009_M8019:30:0` 判 medium，说明保守/听觉风险模型会产生 false positive。
- 时间上也不能只看 flash 均值：12-window batch 中 flash 平均 2.113s，但 P95 到 6.408s、最大 12.426s；plus 更稳定但平均更慢。因此 realtime UI 应把 flash 作为早期 hint，把 plus 作为慢速 sentinel/offline check。
- 因此更合理的系统设计是：Omni guard 只作为加权证据。如果 Omni high risk 且声学异常也 high，则提升 quarantine 优先级；如果只有 Omni medium/unknown，不直接改 timeline。

Omni + acoustic proxy fusion smoke：

```bash
python scripts/analyze_omni_acoustic_fusion.py
```

产物：

- `outputs/omni_guard/omni_acoustic_fusion.csv`
- `outputs/omni_guard/omni_acoustic_fusion.md`
- `outputs/omni_guard/omni_acoustic_fusion_summary.json`

| Windows | Acoustic flagged | Omni fast hints | Omni high sentinels | Review priority | High sentinel recall | High review recall | Clean sentinel FP | Clean review FP |
|---:|---:|---:|---:|---:|---|---|---|---|
| 12 | 11 | 4 | 1 | 12 | 1/4 (25.0%) | 4/4 (100.0%) | 0/4 (0.0%) | 4/4 (100.0%) |

解读：

- `Omni high sentinel` 只由 high risk、strong crosstalk 或 quarantine 触发；它在 12-window 小样本上抓到 1/4 high，并且 clean sentinel FP 为 0/4，适合作为早期 quarantine priority boost，但 recall 明显不足。
- 把 acoustic proxy 和普通 Omni hint 都纳入 review priority 后，可以覆盖 4/4 high，但 clean review FP 也达到 4/4；因此 review priority 只能是“排队/标注/解释”，不能变成 timeline writeback。
- 这一步把 Omni 从“单独返回 JSON”推进到“可与 acoustic proxy 合并的 Agent evidence”，但样本仍只有 12 窗口，下一步需要扩到 120-window proxy set 或重新抽样的 held-out audio clips。

qwen3.7-plus high-risk 二审补测：

```bash
python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy high_risk_quarantine \
  --model qwen3.7-plus \
  --max-windows 2 \
  --output-jsonl outputs/llm_window_batch/qwen37_plus_high_risk_2w_48.jsonl

python scripts/summarize_llm_window_batch_results.py \
  --batch-jsonl outputs/llm_window_batch/qwen37_plus_high_risk_2w_48.jsonl \
  --output-csv outputs/llm_window_batch/qwen37_plus_high_risk_2w_summary.csv \
  --output-md outputs/llm_window_batch/qwen37_plus_high_risk_2w_summary.md
```

| Run | Model | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay |
|---|---|---:|---:|---|---|---:|---:|---:|
| qwen37_plus_high_risk_2w_48 | qwen3.7-plus | 2 | 21 | quarantine 1 / review 1 | defer 16 / quarantine 5 | 54.22s | 79.78s | 106.03s |

batch safety：

| Windows | Patches | Window decisions | Patch decisions | Safe accepts | Harmful accepts | Conservative blocks | Safe blocks | High-error quarantined |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| 2 | 21 | quarantine 1 / review 1 | defer 16 / quarantine 5 | 0 | 0 | 8 | 13 | 1 |

解释：

- qwen3.7-plus 在 high-risk 二审里仍然没有自动 accept，`harmful_accepts=0`，安全性可以接受。
- 但平均 LLM call 已达 54.22s，叠加 DiariZen 后平均修正延迟 79.78s、最大 106.03s；这已经明显超过 deepseek guard 的 40.50s/47.95s。
- 因此 qwen3.7-plus 更适合作为离线二审/论文解释模型，不适合作为实时 guard 主模型。

qwen candidate-audit batch smoke：

```bash
python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --max-windows 5 \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_semantic5_48.jsonl
```

| Run | Model | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay |
|---|---|---:|---:|---|---|---:|---:|---:|
| qwen36_flash_semantic5_48 | qwen3.6-flash-2026-04-16 | 5 | 76 | quarantine 5 | defer 76 | 28.13s | 53.69s | 61.95s |

batch safety：

| Windows | Patches | Safe accepts | Harmful accepts | Conservative blocks | Safe blocks |
|---:|---:|---:|---:|---:|---:|
| 5 | 76 | 0 | 0 | 76 | 0 |

解释：

- qwen 单 patch mixed 评估中出现过少量 safe accept，但 window-batch 后显著变保守。
- 这 5 个 semantic-label-smoothing 窗口全部 window-level `quarantine`，patch-level 全部 `defer`。
- `harmful_accepts = 0` 证明安全；但 `conservative_blocks = 76` 说明它目前不能直接承担“自动有限写回”。
- 新结论：**qwen 是 candidate-audit 候选，不是已验证的写回器**。下一步必须把 ASR 语义、speaker memory confidence、邻接段一致性显式加入 batch prompt，再验证它能否把部分 defer 转成 safe accept。

evidence-enhanced qwen batch：

为避免把 eval-only 真值泄漏给 LLM，增强 prompt 只加入部署时可获得或近似可获得的证据：

- window evidence：Fast/Slow speaker count、segment count、speech duration、Fast/Slow disagreement。
- memory evidence：global speaker count、assigned speech rate。
- 不加入 DER、GT speech、label correctness、global identity accuracy 等 eval-only 字段。

```bash
python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --max-windows 3 \
  --window-evidence outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --memory-evidence outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_semantic3_evidence_48.jsonl
```

| Run | Model | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay | Max correction delay |
|---|---|---:|---:|---|---|---:|---:|---:|
| qwen36_flash_semantic3_evidence_48 | qwen3.6-flash-2026-04-16 | 3 | 51 | quarantine 3 | defer 51 | 32.19s | 57.75s | 68.80s |

batch safety：

| Windows | Patches | Safe accepts | Harmful accepts | Conservative blocks | Safe blocks |
|---:|---:|---:|---:|---:|---:|
| 3 | 51 | 0 | 0 | 51 | 0 |

解释：

- 基础 deployable evidence 没有解决 qwen 的过度保守：3 个窗口/51 个 patch 仍然全部 `defer`。
- 平均调用时间从未增强 batch 的 28.13s 上升到 32.19s，说明简单堆统计字段会增加延迟，却不带来写回收益。
- 下一步不应继续只调 prompt 文案，而应补齐真正能支持写回的证据：
  - ASR 语义：相邻 utterance 是否是同一说话人的连续发言、是否存在问答/称呼/自我指代。
  - 细粒度声纹：每个 patch 与注册 speaker 的 top-1/top-2 相似度差值、memory confidence、最近邻稳定性。
  - 邻接一致性：patch 前后同一 global speaker 的连续性、边界移动是否减少碎片。

ASR semantic evidence 接口：

```bash
python scripts/build_asr_semantic_evidence.py \
  --input docs/examples/asr_semantic_evidence_input_example.csv \
  --output outputs/asr_semantic_evidence/example_window_evidence.csv

python scripts/llm_window_batch_policy_eval.py \
  --mode export \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --max-windows 2 \
  --window-evidence outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --memory-evidence outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --asr-evidence outputs/asr_semantic_evidence/example_window_evidence.csv \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_semantic2_asr_example_prompts.jsonl
```

ASR input schema：

| Field | 说明 |
|---|---|
| `recording_id` | 录音 ID |
| `window_size` / `segment_idx` | 对齐 30s window |
| `start` / `end` | utterance 在原音频中的时间 |
| `text` | ASR 文本 |
| `asr_speaker` | 可选，ASR 侧弱 speaker 标记 |

生成的 deployable ASR evidence：

| Field | 说明 |
|---|---|
| `utterance_count` / `char_count` | 当前窗口文本密度 |
| `has_question` | 是否包含问句/疑问提示 |
| `has_addressing` | 是否出现称呼/对话指向 |
| `has_self_reference` | 是否出现“我/我们”等自指 |
| `asr_speaker_count` | ASR 侧弱说话人数量 |
| `transcript_excerpt` | capped transcript snippet，控制 prompt 长度 |

接口验证：

- 示例 prompt 每个窗口只增加约 270-300 字符。
- 默认不加入 DER、GT speech、label correctness、global identity accuracy 等 eval-only 真值。
- 这一步只是打通接口，还不是 ASR 实验结果；下一步需要用真实 ASR 输出替换 example CSV 后重新跑 qwen batch。

细粒度声纹 evidence 接口：

现有 `outputs/voiceprint_memory/*.csv` 只有 recording-level 指标，不能直接支持 patch 写回。因此新增 patch-level voiceprint evidence schema：

```bash
python scripts/build_voiceprint_patch_evidence.py \
  --input docs/examples/voiceprint_patch_evidence_input_example.csv \
  --output outputs/voiceprint_patch_evidence/example_patch_evidence.csv

python scripts/llm_window_batch_policy_eval.py \
  --mode export \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --max-windows 2 \
  --window-evidence outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --memory-evidence outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --asr-evidence outputs/asr_semantic_evidence/example_window_evidence.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/example_patch_evidence.csv \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_semantic2_asr_voiceprint_example_prompts.jsonl
```

Voiceprint input schema：

| Field | 说明 |
|---|---|
| `patch_id` | 对齐 Policy Agent patch |
| `top1_global_speaker` / `top1_similarity` | 最相似注册说话人与相似度 |
| `top2_global_speaker` / `top2_similarity` | 次相似说话人与相似度 |
| `memory_confidence` | voiceprint memory 对该 patch 的置信度 |
| `enrollment_source` | 可选，例如 `visual_first_window` |

生成字段：

| Field | 说明 |
|---|---|
| `similarity_margin` | `top1_similarity - top2_similarity` |
| `confidence_bucket` | high / medium / low，便于 LLM 做保守仲裁 |

接口验证：

- ASR + voiceprint 双增强 prompt 每个窗口增加约 1.2k 字符。
- `voiceprint_evidence` 已按 patch 挂载；没有 evidence 的 patch 保持 `{}`。
- 默认不加入任何 GT speaker label 或 DER 真值。
- 下一步需要让 `analyze_voiceprint_memory.py` 或在线 voiceprint memory 输出真实 patch-level top1/top2/margin，再用 qwen batch 验证是否能从 `defer` 转为 safe accept。后续已经用 `generate_patch_voiceprint_evidence.py` 产出真实 patch-level evidence，并通过 writeback gate 审计，见下文。

真实 patch-level voiceprint smoke：

```bash
.venv_diarizen/bin/python scripts/generate_patch_voiceprint_evidence.py \
  --trigger-policy semantic_label_smoothing \
  --patch-ids-from-prompt outputs/llm_window_batch/qwen36_flash_semantic2_asr_example_prompts.jsonl \
  --max-patches 80 \
  --output outputs/voiceprint_patch_evidence/real_semantic2_prompt_patch_evidence.csv

python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --max-windows 2 \
  --window-evidence outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --memory-evidence outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/real_semantic2_prompt_patch_evidence.csv \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_semantic2_real_voiceprint_48.jsonl
```

Voiceprint evidence 覆盖：

| Rows | OK | Buckets | Avg margin | Max margin |
|---:|---:|---|---:|---:|
| 36 | 36 | medium 20 / low 16 | 0.277 | 0.367 |

qwen batch with real voiceprint：

| Run | Model | Windows | Patches | Window decisions | Patch decisions | Avg call | Avg correction delay |
|---|---|---:|---:|---|---|---:|---:|
| qwen36_flash_semantic2_real_voiceprint_48 | qwen3.6-flash-2026-04-16 | 2 | 36 | quarantine 2 | defer 36 | 33.73s | 59.29s |

Safety：

| Windows | Patches | Safe accepts | Harmful accepts | Conservative blocks |
|---:|---:|---:|---:|---:|
| 2 | 36 | 0 | 0 | 36 |

解释：

- 真实 ECAPA patch-level evidence 已经能产出，并且 36/36 成功挂载。
- 但该批 semantic windows 的 voiceprint bucket 只有 medium/low，没有 high confidence；qwen 仍然全部 `defer`。
- 这说明“声纹证据”不能只接入接口，还要有**足够强的 top1/top2 margin 与 memory confidence**，否则 LLM 合理地不写回。
- 当时的新假设是：只有同时满足 `voiceprint confidence_bucket=high`、ASR 语义支持连续同一说话人、邻接段一致性不冲突时，qwen 才允许尝试 `accept`。下一步专门补测了 high-confidence 声纹窗口，结果进一步收紧了这个判断。

high-confidence voiceprint targeted test：

```bash
python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --window-id R8007_M8010:30:0 \
  --window-evidence outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --memory-evidence outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/real_semantic_all_patch_evidence.csv \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_highconf_r8007_m8010_0_48.jsonl
```

| Run | Model | Windows | Patches | Voiceprint buckets | Window decision | Patch decisions | Avg call | Avg correction delay |
|---|---|---:|---:|---|---|---|---:|---:|
| qwen36_flash_highconf_r8007_m8010_0_48 | qwen3.6-flash-2026-04-16 | 1 | 9 | high 9 / 9 | review | defer 9 | 21.61s | 47.18s |

Safety：

| Windows | Patches | Safe accepts | Harmful accepts | Conservative blocks |
|---:|---:|---:|---:|---:|
| 1 | 9 | 0 | 0 | 9 |

解释：

- 这次没有使用 eval-only DER/GT 字段；prompt 中只包含 deployable window stats、recording-level memory stats 和 patch-level voiceprint top1/top2/margin。
- 即使 9 个 patch 都是 high-confidence voiceprint，qwen 仍然给出 window-level `review` 和 patch-level `defer 9`。
- 该窗口属于首窗/注册窗口附近，部分相似度可能有自匹配色彩，因此即便模型 accept 也需要谨慎解释；但实际结果更保守，说明 **high-confidence 声纹本身仍不足以触发自动写回**。
- 新的写回 gating 应收紧为：`voiceprint high` 只是必要条件之一，还必须同时有 ASR 语义连续性、非首窗身份先验、邻接段一致性，并通过规则 Agent 的污染检查。当前 qwen 更适合作为“候选审计器”，不是已验证的写回执行器。

oracle transcript upper-bound control：

为了隔离“ASR 语义是否足够强”这个变量，新增了一个非部署型控制实验：从 benchmark summary 里的 `gt_text` 导出窗口对齐文本，再压缩成 ASR semantic evidence。该证据明确标记为 `oracle_transcript_upper_bound_not_deployable`，不把 ground-truth speaker label、DER、support correctness 暴露给 LLM。

```bash
python scripts/build_oracle_asr_transcript_input.py \
  --window-id R8007_M8010:30:0 \
  --output outputs/asr_semantic_evidence/oracle_highconf_r8007_m8010_0_input.csv

python scripts/build_asr_semantic_evidence.py \
  --input outputs/asr_semantic_evidence/oracle_highconf_r8007_m8010_0_input.csv \
  --output outputs/asr_semantic_evidence/oracle_highconf_r8007_m8010_0_evidence.csv

python scripts/llm_window_batch_policy_eval.py \
  --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --trigger-policy semantic_label_smoothing \
  --model qwen3.6-flash-2026-04-16 \
  --window-id R8007_M8010:30:0 \
  --window-evidence outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --memory-evidence outputs/voiceprint_memory/sortformer_diarizen_48.csv \
  --asr-evidence outputs/asr_semantic_evidence/oracle_highconf_r8007_m8010_0_evidence.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/real_semantic_all_patch_evidence.csv \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_highconf_oracle_asr_r8007_m8010_0_48.jsonl
```

结果对照：

| Run | Evidence | Windows | Patches | Window decision | Patch decisions | Avg call | Avg correction delay | Conservative blocks |
|---|---|---:|---:|---|---|---:|---:|---:|
| qwen36_flash_highconf_r8007_m8010_0_48 | high voiceprint only | 1 | 9 | review 1 | defer 9 | 21.61s | 47.18s | 9 |
| qwen36_flash_highconf_oracle_asr_r8007_m8010_0_48 | high voiceprint + oracle transcript | 1 | 9 | quarantine 1 | defer 9 | 18.48s | 44.04s | 9 |

再对 medium/low 声纹的两个 semantic 窗口补充 oracle transcript：

| Run | Evidence | Windows | Patches | Window decision | Patch decisions | Avg call | Avg correction delay | Conservative blocks |
|---|---|---:|---:|---|---|---:|---:|---:|
| qwen36_flash_semantic2_real_voiceprint_48 | medium/low voiceprint | 2 | 36 | quarantine 2 | defer 36 | 33.73s | 59.29s | 36 |
| qwen36_flash_semantic2_oracle_asr_voiceprint_48 | medium/low voiceprint + oracle transcript | 2 | 36 | quarantine 2 | defer 36 | 31.02s | 56.59s | 36 |

解释：

- 即使加入 oracle transcript，上述两组仍然没有任何 `accept`，`harmful_accepts = 0`，但 `conservative_blocks` 也保持满额。
- high-confidence 窗口在加入文本后从 `review` 变成 `quarantine`，说明文本语义并没有突破 `memory_low_confidence + speaker_count_mismatch/abnormal_flags` 的安全约束。
- 这不是坏消息，而是把 Agent 分工进一步明确了：**ASR 语义不能作为无条件写回钥匙；它只能在低风险窗口内帮助 label smoothing。高风险窗口应固定进入隔离/复核，不应该让 LLM 自动 accept。**
- 下一步优化方向应从“让 qwen 更大胆”改成“构造低风险 writeback gate”：只有无 abnormal flags、voiceprint high 且非首窗自匹配、邻接段一致、ASR 文本支持连续发言时，才允许 LLM 尝试 `accept`；否则保持 `defer/quarantine`。

low-risk writeback gate 审计：

```bash
python scripts/analyze_writeback_gate.py \
  --decisions outputs/policy_agent/sortformer_diarizen_48_decisions.jsonl \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/real_semantic_all_patch_evidence.csv \
  --output-csv outputs/writeback_gate/gate_decisions.csv \
  --summary-json outputs/writeback_gate/gate_summary.json \
  --summary-md outputs/writeback_gate/gate_summary.md
```

Gate 规则：

- `rule_auto_writeback`：Rule Agent 已 accept，且无 abnormal flags、duration >= 0.6s、support >= 0.8、patch type 可写回。
- `rule_label_only_writeback`：短边界修正可以写回 speaker/boundary，但不更新声纹记忆。
- `rule_recover_writeback`：Slow Agent 补回 Fast 漏检语音；该类 support_ratio 低是定义内现象，因此不使用 cross-model support 作为 blocker。
- `rule_reference_only`：Slow segment 只作为参考对齐，不代表要重复写回。
- `llm_writeback_candidate`：semantic defer patch，且无 abnormal flags、非首窗、duration >= 0.6s、support >= 0.8、voiceprint bucket=high。
- 其他非 accept 或高风险 patch 保持 review/defer/quarantine。

当前 48 窗口结果：

| Gate category | Patches | 系统动作 |
|---|---:|---|
| rule_auto_writeback | 119 | 规则 Agent 常规写回，不需要 LLM |
| rule_label_only_writeback | 29 | 短边界/短回应写回，但不更新声纹 |
| rule_recover_writeback | 24 | Slow Agent 补 Fast 漏检语音 |
| llm_writeback_candidate | 0 | 当前没有值得 qwen 自动写回的候选 |
| llm_defer_review | 136 | 维持 defer/review；等待更强证据或人工/慢路径 |
| guard_or_quarantine | 19 | 高风险隔离 |
| rule_reference_only | 446 | Slow 对齐参考，不作为写回 patch |
| rule_accept_needs_review | 180 | 主要是 abnormal accept 或 suppress，需要继续审计 |

semantic defer 被挡住的主因：

| Blocker | Count |
|---|---:|
| abnormal_flags | 128 |
| voiceprint_low | 71 |
| voiceprint_medium | 50 |
| short_duration | 51 |
| low_cross_model_support | 28 |
| unsupported_patch_type | 2 |
| enrollment_or_first_window | 12 |

patch-level voiceprint evidence 汇总：

```bash
python scripts/summarize_voiceprint_patch_evidence.py
```

产物：

- `outputs/voiceprint_patch_evidence/patch_evidence_summary.json`
- `outputs/voiceprint_patch_evidence/patch_evidence_summary.md`

| Rows | OK | Missing | High | Medium | Low | Avg confidence | Avg margin | P95 margin | LLM candidates |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 136 | 133 | 3 | 12 | 50 | 71 | 0.536 | 0.290 | 0.637 | 0 |

这一步把 L5 从“只有 recording-level memory 指标”推进到“patch-level top1/top2/margin 已能作为 deployable gate 输入”：136 个 semantic patch 中 133 个有可用 ECAPA evidence，12 个 high bucket，但低风险写回 gate 仍给出 `llm_writeback_candidate=0`。原因不是缺少声纹接口，而是当前 semantic patches 绝大多数仍同时命中 abnormal flags、短时长、低 support 或 low/medium voiceprint；因此声纹 high 只能作为必要条件，不能单独授予 LLM 写回权。

120-window patch-level voiceprint 扩展：

```bash
.venv_diarizen/bin/python scripts/generate_patch_voiceprint_evidence.py \
  --patches outputs/policy_agent/sortformer_diarizen_120_decisions.csv \
  --fast-summary outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  --slow-summary outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json \
  --trigger-policy semantic_label_smoothing \
  --max-patches 0 \
  --output outputs/voiceprint_patch_evidence/real_semantic_120_patch_evidence.csv

python scripts/analyze_writeback_gate.py \
  --decisions outputs/policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/real_semantic_120_patch_evidence.csv \
  --output-csv outputs/writeback_gate_120/gate_decisions.csv \
  --summary-json outputs/writeback_gate_120/gate_summary.json \
  --summary-md outputs/writeback_gate_120/gate_summary.md

python scripts/summarize_voiceprint_patch_evidence.py \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/real_semantic_120_patch_evidence.csv \
  --gate-summary outputs/writeback_gate_120/gate_summary.json \
  --output-json outputs/voiceprint_patch_evidence/patch_evidence_120_summary.json \
  --output-md outputs/voiceprint_patch_evidence/patch_evidence_120_summary.md
```

| Rows | OK | Missing | High | Medium | Low | Avg confidence | Avg margin | P95 margin | LLM candidates |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 88 | 82 | 6 | 9 | 18 | 55 | 0.461 | 0.254 | 0.570 | 0 |

120-window 口径说明：之前 `outputs/writeback_gate_120/gate_summary.json` 使用占位的 `nonexistent_120.csv`，导致 88 个 semantic patch 全部被 `missing_voiceprint` 挡住；现在已替换为真实 `real_semantic_120_patch_evidence.csv`，`missing_voiceprint` 降到 6。但 `llm_writeback_candidate` 仍为 0，因为 88 个 semantic patch 仍全部命中 low cross-model support，85 个短时长，66 个 abnormal flags，且 high voiceprint 只有 9 个。这进一步支持当前结论：声纹 evidence 已经接入，但低风险 LLM 写回候选需要重新构造更干净的 no-abnormal candidate set。

clean no-abnormal + high-support candidate audit：

```bash
python scripts/audit_clean_voiceprint_candidates.py

.venv_diarizen/bin/python scripts/generate_patch_voiceprint_evidence.py \
  --patches outputs/policy_agent/sortformer_diarizen_120_decisions.csv \
  --fast-summary outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  --slow-summary outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json \
  --trigger-policy all \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_candidate_120_patch_ids.txt \
  --max-patches 0 \
  --output outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv

python scripts/audit_clean_voiceprint_candidates.py \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv
```

| Clean patches | With voiceprint | High bucket | Medium bucket | LLM candidates | Rule auto | Rule reference | Avg margin | P95 margin |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 620 | 620 | 226 | 199 | 0 | 386 | 234 | 0.376 | 0.611 |

这个审计把“低风险候选集”拆清楚了：满足 no-abnormal、非首窗、duration/support 阈值的 620 个 patch 全部已经是 deterministic accept，其中 386 个是 `rule_auto_writeback`、234 个是 `rule_reference_only`；声纹 high bucket 有 226 个，其中 138 个属于 rule-auto。换句话说，干净且高声纹的面已经由规则 Agent 安全处理，不是 LLM defer backlog。后续如果要接 LLM，也应该只抽样做 audit/解释一致性验证，而不是把 LLM 变成写回执行器。

clean high rule-auto LLM audit：

```bash
python scripts/llm_window_batch_policy_eval.py --mode export \
  --decisions outputs/policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --trigger-policy all \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_patch_ids.txt \
  --window-evidence outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv \
  --model qwen3.6-flash-2026-04-16 \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_prompts.jsonl

python scripts/llm_window_batch_policy_eval.py --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --trigger-policy all \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_patch_ids.txt \
  --window-evidence outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv \
  --model qwen3.6-flash-2026-04-16 \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit.jsonl

python scripts/summarize_clean_llm_audit.py
```

| Windows | Patches | Window clean | LLM accepts | Non-accepts | Rule-auto agreement | Avg call | Max call | Total tokens |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 23 | 2 | 23 | 0 | 100.0% | 23.79s | 28.51s | 15060 |

这次专门抽样 2 个 no-abnormal、high-voiceprint、rule-auto 窗口做真实 qwen 审计。LLM 对 23 个 patch 全部返回 `accept`，与 deterministic Rule Agent 100% 一致；但这仍是 audit-only 证据，结论是“LLM 可以给 clean rule-auto patch 做解释/一致性复核”，不是“LLM 获得 timeline 写回权”。下一步应扩大 clean high 样本覆盖不同 recording 和说话人组合，同时保持 Rule Agent 作为写回执行器。

expanded clean high rule-auto LLM audit：

```bash
python scripts/select_clean_llm_audit_sample.py

python scripts/llm_window_batch_policy_eval.py --mode export \
  --decisions outputs/policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --trigger-policy all \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_patch_ids.txt \
  --window-evidence outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv \
  --model qwen3.6-flash-2026-04-16 \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded_prompts.jsonl

python scripts/llm_window_batch_policy_eval.py --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --trigger-policy all \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_patch_ids.txt \
  --window-evidence outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv \
  --model qwen3.6-flash-2026-04-16 \
  --parallel-workers 2 \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded.jsonl

python scripts/summarize_clean_llm_audit.py \
  --llm-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded.jsonl \
  --llm-summary outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded_summary.json \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_expanded_patch_ids.txt \
  --output-json outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded_agreement.json \
  --output-md outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_expanded_agreement.md
```

扩样样本覆盖 4 个 recording、6 个窗口、44 个 high-voiceprint rule-auto patch：

| Windows | Patches | Recordings | Window clean | LLM accepts | Non-accepts | Rule-auto agreement | Avg call | Max call | Wall | Total tokens |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 44 | 4 | 6 | 42 | 2 | 95.5% | 21.07s | 24.46s | 64.42s | 34684 |

两个 non-accept 都是 `R8009_M8018:30:2` 中的短边界 patch（0.88s、0.64s），qwen 返回 `defer` 而不是 `accept`。这说明 LLM 作为审计器会对非常短的边界调整保守，即使 no-abnormal、support=1.0、voiceprint margin=0.6519；因此 expanded audit 的结论更精确：Rule Agent 仍是写回执行器，LLM 可以作为解释/复核层，且其保守 disagree 应进入后续的短片段策略分析，而不是直接覆盖 Rule。

full clean high rule-auto surface audit：

```bash
python scripts/select_clean_llm_audit_sample.py \
  --max-windows 25 \
  --output-patch-ids outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_patch_ids.txt \
  --output-window-ids outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_window_ids.txt \
  --output-csv outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_windows.csv \
  --summary-json outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_summary.json

python scripts/llm_window_batch_policy_eval.py --mode call \
  --decisions outputs/policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --trigger-policy all \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_patch_ids.txt \
  --window-evidence outputs/segment_patches/sortformer_diarizen_120_patches_windows.csv \
  --voiceprint-evidence outputs/voiceprint_patch_evidence/clean_candidate_120_voiceprint.csv \
  --model qwen3.6-flash-2026-04-16 \
  --parallel-workers 3 \
  --output-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full.jsonl

python scripts/summarize_clean_llm_audit.py \
  --llm-jsonl outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full.jsonl \
  --llm-summary outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_summary.json \
  --patch-id-file outputs/voiceprint_patch_evidence/clean_high_rule_auto_audit_full_patch_ids.txt \
  --output-json outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_agreement.json \
  --output-md outputs/llm_window_batch/qwen36_flash_clean_high_rule_auto_audit_full_agreement.md

python scripts/compare_clean_llm_audit_runs.py
```

| Windows | Patches | Recordings | Window clean | LLM accepts | Non-accepts | Rule-auto agreement | Avg call | Max call | Wall | Total tokens |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 138 | 4 | 25 | 136 | 2 | 98.6% | 20.24s | 31.15s | 173.03s | 128004 |

full-surface 的两个 non-accept 都是 `defer`：`R8009_M8018:30:3:fast:fast_8`（0.64s，support=1.0，margin=0.5971）和 `R8009_M8020:30:14:fast:fast_1`（1.92s，support=0.819，margin=0.4492）。这把 L5 结论从“抽样一致”推进到“完整 clean high rule-auto surface 上高度一致”：qwen 对 138 个 deterministic high-voiceprint rule-auto patch 中 136 个同意 accept，剩余 2 个保持 defer。

重复运行一致性：

| Overlap patches | Same decision | Changed decision | Agreement | Expanded non-accepts | Full-run non-accepts on overlap |
|---:|---:|---:|---:|---:|---:|
| 44 | 42 | 2 | 95.5% | 2 | 0 |

这说明 LLM 审计在 clean surface 上总体稳定，但仍有少量 patch-level decision drift：expanded run 中 `R8009_M8018:30:2:fast:fast_8/9` 为 `defer`，full run 中变成 `accept`。因此工程策略更稳：Rule Agent 执行 bounded writeback，LLM 只输出 review/explanation；LLM 的 disagree 或 drift 进入审计队列，不直接覆盖 Rule。

LLM disagreement / drift triage：

```bash
python scripts/analyze_clean_llm_disagreements.py
```

| Surface patches | Full accepts | Full defers | Repeat drift | Review-signal cases | Avg review duration |
|---:|---:|---:|---:|---:|---:|
| 138 | 136 | 2 | 2 | 4 | 1.02s |

| Duration bucket | Patches | Full defers | Defer rate |
|---|---:|---:|---:|
| <0.9s | 18 | 1 | 5.6% |
| 0.9-1.5s | 20 | 0 | 0.0% |
| 1.5-3.0s | 45 | 1 | 2.2% |
| >=3.0s | 55 | 0 | 0.0% |

| Patch ID | Case | Duration | Support | Margin | Runtime policy |
|---|---|---:|---:|---:|---|
| `R8009_M8018:30:2:fast:fast_8` | repeatability drift | 0.88s | 1.000 | 0.652 | review signal only |
| `R8009_M8018:30:2:fast:fast_9` | repeatability drift | 0.64s | 1.000 | 0.652 | review signal only |
| `R8009_M8018:30:3:fast:fast_8` | full defer | 0.64s | 1.000 | 0.597 | review signal only |
| `R8009_M8020:30:14:fast:fast_1` | full defer | 1.92s | 0.819 | 0.449 | review signal only |

运行时策略因此可以写得更具体：clean high rule-auto patch 仍由 deterministic Rule 写回；LLM 的 `defer` 或跨 run decision drift 只打 review/explanation 标签，尤其提醒短片段 memory update 风险，不撤销已经满足边界写回条件的 Rule 决策。

offline timeline review audit：

```bash
python scripts/build_timeline_review_audit.py
```

| Review cases | Blocks timeline writeback | Blocks memory update | Avg rule arrival | Avg LLM review arrival |
|---:|---:|---:|---:|---:|
| 4 | 0 | 4 | 24.65s | 46.10s |

| Patch ID | Case | Gate | Rule action | LLM action | Block timeline | Block memory | LLM arrival |
|---|---|---|---|---|---:|---:|---:|
| `R8009_M8018:30:2:fast:fast_8` | repeatability drift | rule_auto_writeback | keep rule bounded writeback | review repeatability drift | 0 | 1 | 43.48s |
| `R8009_M8018:30:2:fast:fast_9` | repeatability drift | rule_auto_writeback | keep rule bounded writeback | review repeatability drift | 0 | 1 | 43.48s |
| `R8009_M8018:30:3:fast:fast_8` | full defer | rule_auto_writeback | keep rule bounded writeback | review llm defer | 0 | 1 | 55.80s |
| `R8009_M8020:30:14:fast:fast_1` | full defer | rule_auto_writeback | keep rule bounded writeback | review llm defer | 0 | 1 | 41.63s |

这个表把 LLM 审计真正接入 timeline 口径：4 个 review signal 都不阻塞 Rule 的 bounded timeline writeback，但全部阻塞 speaker-memory update 或要求审计说明。这样既保留 Rule Agent 的 24.65s 写回收益，又让 LLM 在约 46.10s 到达时承担解释、标注和 memory 污染防护职责。

解释：

- 这解释了为什么 qwen 在 high-confidence/oracle transcript 实验里仍然全 defer：当前被送去 semantic smoothing 的窗口几乎都是 abnormal 或 memory-low 的安全敏感窗口。
- 真正的自动写回不是“让 LLM 更激进”，而是先让 Rule Agent 写回 172 个稳定 patch（119 常规 + 29 label-only + 24 recover）；LLM 只处理未来出现的低风险冲突候选。
- 下一步实验应把 `outputs/timeline_review_audit/llm_review_signal_timeline_audit.csv` 接入 timeline audit UI 或批量审计日报：Rule 可保持 bounded writeback，但 LLM disagree/drift 只提示短片段/memory-update 风险，而不是覆盖 Rule。

writeback impact 评估：

```bash
python scripts/analyze_writeback_impact.py \
  --gate-decisions outputs/writeback_gate/gate_decisions.csv \
  --patches outputs/segment_patches/sortformer_diarizen_48_patches.csv \
  --windows outputs/segment_patches/sortformer_diarizen_48_patches_windows.csv \
  --fast-summary outputs/sortformer_uv_48/nemo-sortformer-4spk-v1/default__spk_none/summary.json \
  --slow-summary outputs/diarizen_uv_48/diarizen-large-v2/default__spk_none/summary.json \
  --output-csv outputs/writeback_gate/writeback_impact.csv \
  --summary-json outputs/writeback_gate/writeback_impact_summary.json \
  --summary-md outputs/writeback_gate/writeback_impact.md
```

离线评估口径：join `gt_overlap_sec` 和 mask-level Fast miss，只用于汇报评估，不进入 runtime prompt。

| Category | Patches | Windows | GT overlap sec | True support rate | 系统含义 |
|---|---:|---:|---:|---:|---|
| rule_auto_writeback | 119 | 19 | 504.48 | 100.0% | 常规边界/说话人写回 |
| rule_label_only_writeback | 29 | 11 | 13.55 | 100.0% | 短边界写回，不更新声纹 |
| rule_recover_writeback | 24 | 15 | 200.90 | 100.0% | Slow 补 Fast 漏检 |

关键收益：

- Rule Agent 当前可写回 172 个 patch，覆盖 718.93s GT speech overlap。
- 24 个 recover 写回唯一覆盖 50.28s Fast miss，占 48 窗口 Fast miss 87.38s 的 57.5%，也就是 Slow 可恢复漏检 80.04s 的 62.8%。
- 48 段开发集平均到达时间曾按 DiariZen latency 估算为 25.56s；当前 120 段主口径为规则写回 24.65s，runtime-safe LLM guard 44.92s avg / 63.85s P95。
- 这说明双 Agent 的实际收益不是靠 LLM accept，而是：Fast 首出实时可用，Slow/Rule 在约 26s 后补回大半漏检，LLM 只负责阻止污染性写回。

Rule writeback timeline materialization v0：

为了避免只停留在 patch 覆盖率，本轮把 gate 后的 recover patch 真正合成到 Fast timeline，再用同一 DER evaluator 重算 48 窗口结果：

```bash
python scripts/evaluate_rule_writeback_timeline.py
```

| Variant | DER | Median DER | Miss | FA | Conf | 说明 |
|---|---:|---:|---:|---:|---:|---|
| Fast base | 29.30% | 18.73% | 17.12% | 8.90% | 3.27% | 原始实时首出 |
| Rule recover, policy sweep best | 27.56% | 17.44% | 14.03% | 9.18% | 4.36% | `slow_spk > fast_spk` 或 `fast/slow speech ratio <= 0.60` 时补重叠，否则只补 silent |
| Rule recover, identity selector | 27.65% | 17.44% | 14.12% | 9.17% | 4.36% | Slow speaker count > Fast 时允许补重叠；否则只补 Fast silent 区域 |
| Rule recover, matched label | 27.71% | 17.44% | 14.00% | 9.35% | 4.36% | 24 个 recover patch 接到匹配 Fast speaker |
| Rule recover + speaker union | 27.71% | 17.44% | 14.00% | 9.35% | 4.36% | 同 speaker 重叠合并，平均段数 10.0 -> 8.73，但 DER 不变 |
| Rule recover, uncovered only | 27.91% | 17.44% | 14.43% | 9.14% | 4.33% | 只补 Fast silent 区域，更安全但少补一部分 overlap speech |
| Rule recover, new label | 31.46% | 21.96% | 13.13% | 13.87% | 4.46% | 漏检降了，但新标签引入 FA/Conf |
| Boundary + recover | 34.77% | 26.61% | 12.19% | 18.47% | 4.11% | 边界替换过早落地，产生重叠/过说话 |
| Slow base | 21.04% | 11.24% | 4.92% | 10.66% | 5.45% | 完整 DiariZen 后台替换 |

解释：

- 这一步证明 Rule writeback 已经能在 timeline DER 上产生真实收益：`29.30% -> 27.56%`，主要来自 Miss 从 `17.12%` 降到 `14.03%`。
- 但直接新增 speaker label 或直接替换边界会恶化 DER，说明问题不是 acoustic detection 不够，而是 **identity binding + patch selector** 还不够成熟。
- identity-aware selector 比固定 matched-label recover 略优；进一步的小型策略搜索找到 `spk_gt_or_ratio_le_0.60`，DER 从 `27.71%` 降到 `27.56%`。
- overlap-aware sanitizer 已经验证：合并同 speaker 重叠能减少 timeline 复杂度，但没有继续降低 DER；`uncovered_only` 更保守，FA `9.14%`，但 Miss 回升到 `14.43%`。
- 因此下一步不应该扩大自动写回范围，而应该做两个更细的模块：
  - recover patch 必须先接到稳定 global speaker / matched Fast speaker，不能默认创建新 speaker。
  - boundary patch 暂不自动落地；先学习一个低风险 selector，只有在不增加 FA/Conf 且 speaker memory 稳定时才替换边界。
- 这个结果也让 LLM/Agent 的作用更明确：LLM 不负责“决定多写一点”，而是检查写回是否违反身份一致性、重叠约束和异常窗口隔离规则。

Recover selector policy search：

```bash
python scripts/search_recover_selector_policies.py
```

| Rank | Policy | DER | Miss | FA | Conf | Matched | Uncovered | Fast |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `spk_gt_or_ratio_le_0.60` | 27.56% | 14.03% | 9.18% | 4.36% | 8 | 7 | 33 |
| 2 | `spk_gt_or_ratio_le_0.65` | 27.56% | 14.03% | 9.18% | 4.36% | 8 | 7 | 33 |
| 3 | `spk_gt_or_ratio_le_0.70` | 27.56% | 14.03% | 9.18% | 4.36% | 8 | 7 | 33 |
| 4 | `spk_gt` | 27.65% | 14.12% | 9.17% | 4.36% | 7 | 8 | 33 |

说明：

- selector 使用的都是 deployable 特征：Fast/Slow speaker count、Fast/Slow speech ratio，不读 DER/GT。
- 48 窗口里 33 个窗口不写回，8 个窗口用 matched recover，7 个窗口用 uncovered-only recover。
- 这个搜索只是在当前 48 窗口上的开发集结果；下一步要在更大的 held-out 窗口上验证阈值 `0.60-0.70` 是否稳定。

Selector stability bootstrap：

```bash
python scripts/bootstrap_realtime_contract_metrics.py
```

产物：

- `outputs/realtime_contract_bootstrap/realtime_contract_bootstrap.csv`
- `outputs/realtime_contract_bootstrap/realtime_contract_bootstrap.md`
- `outputs/realtime_contract_bootstrap/realtime_contract_bootstrap.json`

| Variant | DER | 95% CI | Delta vs Fast | Delta 95% CI | P(beats Fast) |
|---|---:|---:|---:|---:|---:|
| Slow base | 21.04% | 11.87% - 36.62% | +8.26% | +4.52% - +12.47% | 100.0% |
| Rule recover, policy sweep best | 27.56% | 18.48% - 42.05% | +1.73% | +0.72% - +3.12% | 100.0% |
| Rule recover, identity selector | 27.65% | 18.73% - 43.03% | +1.65% | +0.64% - +3.00% | 100.0% |
| Rule recover, uncovered-only | 27.91% | 18.86% - 42.17% | +1.39% | +0.54% - +2.66% | 100.0% |
| Fast base | 29.30% | 19.92% - 44.02% | 0.00% | 0.00% - 0.00% | 0.0% |
| Boundary recover | 34.77% | 24.67% - 50.44% | -5.47% | -10.75% - -0.79% | 0.9% |

解释：

- 这是 development-set bootstrap，不是 held-out 成绩；它只能说明当前 48 窗口上 policy sweep 的 paired improvement 对窗口重采样不敏感。
- policy sweep 相对 Fast 的 paired DER delta 为 `+1.73 points`，95% CI 为 `+0.72` 到 `+3.12` points，说明当前规则写回确实有稳定收益。
- DER 本身的 CI 很宽，反映 48 窗口仍然偏小且存在极端 FA 段；因此论文/汇报里应把它表述为“当前开发集稳定为正，下一步做 held-out 扩展验证”，而不是最终 SOTA 结论。
- boundary recover 是重要反例：Miss 更低但 FA 暴涨，DER 显著变差。这支持当前“只补 recover miss，不自动替换边界”的安全策略。

Recording-level stability：

```bash
python scripts/analyze_realtime_contract_by_recording.py
```

产物：

- `outputs/realtime_contract_recording_stability/per_recording.csv`
- `outputs/realtime_contract_recording_stability/leave_one_recording_out.csv`
- `outputs/realtime_contract_recording_stability/recording_stability.md`

| Check | Result | 解释 |
|---|---:|---|
| Per-recording positive gain | 7/8 | 只有 `R8009_M8019` 是 0.00pp，未出现负收益 |
| Leave-one-recording-out positive gain | 8/8 | 去掉任一会议后，policy sweep 相对 Fast 仍为正 |
| Largest per-recording gain | +6.39pp | `R8001_M8004`，主要来自补漏检 |
| Hardest recording | +1.85pp on `R8003_M8001` | 该会议 Fast/Rule DER 都高，主要问题是 DiariZen/Slow 极端 FA，需要异常隔离 |

解释：

- recording-level analysis 进一步说明当前 `27.56%` 不是由单个录音撑出来；即便 leave-one-recording-out，平均收益仍为正。
- 但这仍然不是独立 held-out；它只能降低 concentration risk。下一步真正要做的是对 Slow/Rule 链路重新采样新窗口，扩到 120 段或全 482 段，并固定 selector 后不再调阈值。

Fast Agent 120-window expansion：

```bash
.venv_sortformer/bin/python -m alimeeting_diarization_bench.run \
  --model sortformer \
  --sampling-mode stratified \
  --total-samples 120 \
  --window-size 30 \
  --speaker-count-mode none \
  --output-dir outputs/sortformer_uv_120
```

产物：

- `outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json`
- `outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/results.csv`

结果：

| Scope | DER | Miss | FA | Conf | Spk match | Avg latency | P95 latency | RTF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Sortformer 48 | 29.30% | 17.12% | 8.90% | 3.27% | 50.0% | 0.39s | 0.43s | 0.013 |
| Sortformer 120 | 28.56% | 19.96% | 5.41% | 3.20% | 54.2% | 0.38s | 0.44s | 0.013 |

解释：

- Fast Agent 的实时性在 120 个 30s 窗口上仍稳定：平均 0.38s、P95 0.44s、RTF 0.013。
- 120 段 DER 与 48 段接近，但 Miss 更高，说明实时首出仍然主要受短回应/漏检限制；这正是 Slow/Rule writeback 要补的部分。
- 这一步建立了 L0 Fast Agent 的 120 段实时首出口径；下面继续把 Slow/Rule 链路扩到同一批 120 窗口。

### 120 段闭环：实时首出 + 异步强校正

120 段扩样本后，系统口径不再只是“Fast 快、Slow 准”，而是三个分开的验收问题：

1. Fast Agent 是否能稳定在 1s 内给用户可见初稿。
2. Slow Agent 是否在成熟窗口上提供明显更强的声学候选。
3. Rule/Policy Agent 是否能把低风险候选写回，同时不让边界替换和高风险冲突污染 timeline。

当前 120 段主结果：

| Variant | DER | Median DER | Miss | FA | Conf | Avg / P95 delay | 说明 |
|---|---:|---:|---:|---:|---:|---:|---|
| Fast base: Sortformer 120 | 28.56% | 21.29% | 19.96% | 5.41% | 3.20% | 0.38s / 0.44s | 实时首出，Miss-heavy |
| Slow base: DiariZen 120 | 16.88% | 10.83% | 4.99% | 6.92% | 4.98% | 24.65s / 28.33s | 强声学候选；仍有极端 FA 风险 |
| Rule recover writeback | 26.40% | 20.16% | 15.57% | 5.77% | 5.05% | 24.65s / 28.33s | 599 个 bounded writeback；recover 覆盖 60.2% Fast miss |
| Selector best: ratio <= 0.65 else uncovered | 26.30% | n/a | 15.58% | 5.64% | 5.08% | 24.65s / 28.33s | 当前 selector 搜索最优，但仍需 held-out 固定验证 |
| Boundary + recover negative control | 32.54% | n/a | n/a | 14.84% | n/a | 24.65s / 28.33s | 负例：盲目替换边界会让 FA 暴涨 |

稳定性检查：

| Check | Result | 解释 |
|---|---:|---|
| Bootstrap delta vs Fast | +2.17pp | 95% CI +1.10pp 到 +3.47pp，P(beats Fast)=100% |
| Per-recording positive gain | 8/8 | 每个 recording 上 rule recover 相对 Fast 都为正 |
| Leave-one-recording-out positive gain | 8/8 | 去掉任一 recording 后平均收益仍为正 |
| Selector recording-holdout | 8/8 | 每次用 7 个 recording 选策略，再固定到 held-out recording；加权 DER 26.51%，相对 Fast +2.05pp |
| Slow base delta vs Fast | +11.68pp | Slow 本身证明成熟窗口强校正有充足上界 |

解释：

- 120 段闭环支持“实时首出 + 异步修正”的系统路线：用户先在 0.4s 内看到 Fast timeline，后台约 25s 到达 Slow/Rule 修正。
- 当前可部署写回仍然应该保守：只允许 bounded recover / label-only / low-risk patch，不允许 Slow 直接替换完整边界。
- LLM/Omni 的位置更清楚：它们不创造时间戳，不直接优化 DER；它们只负责 block/quarantine/review 高风险 patch group，防止长期 memory 或 timeline 被污染。
- selector 的 `ratio_le_0.65_else_uncovered` 是下一批实验要固定的候选策略；recording-holdout 已经证明它不是只靠单个 recording 撑起来，但真正 test/held-out 上不能继续调阈值。

system timeline 汇总：

```bash
python scripts/build_system_timeline_summary.py \
  --latencies outputs/latency_tradeoff/main_models.csv \
  --segments 120 \
  --writeback-impact outputs/writeback_gate_120/writeback_impact_summary.json \
  --guard-summary outputs/llm_window_batch/window_batch_summary.csv \
  --runtime-safe-guard-summary outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_safety_summary.json \
  --review-audit-summary outputs/timeline_review_audit/llm_review_signal_timeline_audit_summary.json \
  --output-csv outputs/system_timeline/system_timeline.csv \
  --output-md outputs/system_timeline/system_timeline.md \
  --summary-json outputs/system_timeline/summary.json
```

| Stage | Agent | Avg delay | P95 / upper delay | Patches | Benefit | Metric |
|---|---|---:|---:|---:|---|---|
| fast_provisional | Sortformer | 0.38s | 0.44s | 0 | provisional timeline | DER 28.56% / RTF 0.013 |
| rule_writeback | DiariZen + Rule Agent | 24.65s | 28.33s | 599 | recover 60.2% Fast miss | 197.36s unique miss recovered |
| llm_guard | DiariZen + deepseek-v4-flash | 44.92s | 63.85s | 1917 | runtime-safe quarantine/review guard | 104 windows / harmful accept 0 / P95 63.8s |
| llm_review_signal | Rule + qwen3.6 audit | 46.10s | 55.80s | 4 | review-only memory protection | blocks writeback 0 / memory 4 |

这张表可以作为汇报中的核心系统口径：**0.4s 内给可用初稿，约 25s 后后台修正主要漏检，约 45-64s 完成 runtime-safe 高风险隔离，约 46s 给出 clean-high review/memory 防护信号**。因此时间指标不再只是模型耗时，而是用户会看到的分阶段体验；LLM review signal 是异步审计层，不阻塞 Rule timeline writeback。

### 当前进展快照

为了减少汇报前人工翻多个 artifact 的误差，新增 progress snapshot：

```bash
python scripts/refresh_latest_research_artifacts.py
python scripts/build_research_progress_snapshot.py
```

生成产物：

- `outputs/research_progress_snapshot/refresh_latest_artifacts.md`
- `outputs/research_progress_snapshot/snapshot.json`
- `outputs/research_progress_snapshot/snapshot.md`
- `outputs/research_progress_snapshot/claims_manifest.json`
- `outputs/research_progress_snapshot/claims_manifest.md`
- `outputs/research_progress_snapshot/runtime_latency_budget_ledger.json`
- `outputs/research_progress_snapshot/runtime_latency_budget_ledger.md`
- `outputs/research_progress_snapshot/runtime_latency_budget_ledger.csv`
- `outputs/research_progress_snapshot/stage_latency_slo_audit.json`
- `outputs/research_progress_snapshot/stage_latency_slo_audit.md`
- `outputs/research_progress_snapshot/stage_latency_slo_audit.csv`
- `outputs/research_progress_snapshot/latency_risk_margin_audit.json`
- `outputs/research_progress_snapshot/latency_risk_margin_audit.md`
- `outputs/research_progress_snapshot/latency_risk_margin_audit.csv`
- `outputs/research_progress_snapshot/latency_risk_mitigation_plan.json`
- `outputs/research_progress_snapshot/latency_risk_mitigation_plan.md`
- `outputs/research_progress_snapshot/latency_risk_mitigation_plan.csv`
- `outputs/research_progress_snapshot/memory_update_replay.json`
- `outputs/research_progress_snapshot/memory_update_replay.md`
- `outputs/research_progress_snapshot/memory_update_replay.csv`
- `outputs/research_progress_snapshot/omni_expansion_manifest.json`
- `outputs/research_progress_snapshot/omni_expansion_manifest.md`
- `outputs/research_progress_snapshot/omni_expansion_manifest.csv`
- `outputs/research_progress_snapshot/omni48_live_call_manifest.json`
- `outputs/research_progress_snapshot/omni48_live_call_manifest.md`
- `outputs/research_progress_snapshot/omni48_live_call_manifest.csv`
- `outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.json`
- `outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.md`
- `outputs/research_progress_snapshot/selector_true_heldout_candidate_scan.csv`
- `outputs/research_progress_snapshot/selector_true_heldout_split_validation.json`
- `outputs/research_progress_snapshot/selector_true_heldout_split_validation.md`
- `outputs/research_progress_snapshot/selector_true_heldout_split_validation.csv`
- `outputs/research_progress_snapshot/selector_true_heldout_protocol.json`
- `outputs/research_progress_snapshot/selector_true_heldout_protocol.md`
- `outputs/research_progress_snapshot/selector_true_heldout_protocol_gates.csv`
- `outputs/research_progress_snapshot/split20_full_live_manifest.json`
- `outputs/research_progress_snapshot/split20_full_live_manifest.md`
- `outputs/research_progress_snapshot/split20_full_live_manifest.csv`
- `outputs/research_progress_snapshot/split20_resume_export_audit.json`
- `outputs/research_progress_snapshot/split20_resume_export_audit.md`
- `outputs/research_progress_snapshot/split20_resume_after_top3_export_prompts.jsonl`
- `outputs/research_progress_snapshot/split15_stretch_reexport_audit.json`
- `outputs/research_progress_snapshot/split15_stretch_reexport_audit.md`
- `outputs/research_progress_snapshot/split15_stretch_reexport_audit.csv`
- `outputs/research_progress_snapshot/split15_stretch_reexport_prompts.jsonl`
- `outputs/research_progress_snapshot/split_policy_optimization.json`
- `outputs/research_progress_snapshot/split_policy_optimization.md`
- `outputs/research_progress_snapshot/split_policy_optimization.csv`
- `outputs/research_progress_snapshot/runtime_replay_manifest.json`
- `outputs/research_progress_snapshot/runtime_replay_manifest.md`
- `outputs/research_progress_snapshot/phase_result_scorecard.json`
- `outputs/research_progress_snapshot/phase_result_scorecard.md`
- `outputs/research_progress_snapshot/phase_result_scorecard.csv`
- `outputs/research_progress_snapshot/live_provider_routing_decision.json`
- `outputs/research_progress_snapshot/live_provider_routing_decision.md`
- `outputs/research_progress_snapshot/live_provider_routing_decision.csv`
- `outputs/research_progress_snapshot/live_run_readiness.json`
- `outputs/research_progress_snapshot/live_run_readiness.md`
- `outputs/research_progress_snapshot/live_agent_execution_plan.json`
- `outputs/research_progress_snapshot/live_agent_execution_plan.md`
- `outputs/research_progress_snapshot/live_agent_execution_plan.csv`
- `outputs/research_progress_snapshot/live_postrun_metrics_closure.json`
- `outputs/research_progress_snapshot/live_postrun_metrics_closure.md`
- `outputs/research_progress_snapshot/live_postrun_metrics_closure.csv`
- `outputs/research_progress_snapshot/live_output_audit.json`
- `outputs/research_progress_snapshot/live_output_audit.md`
- `outputs/research_progress_snapshot/live_output_audit.csv`
- `outputs/research_progress_snapshot/live_scoring_readiness.json`
- `outputs/research_progress_snapshot/live_scoring_readiness.md`
- `outputs/research_progress_snapshot/live_scoring_readiness.csv`
- `outputs/research_progress_snapshot/post_live_scoring_execution_plan.json`
- `outputs/research_progress_snapshot/post_live_scoring_execution_plan.md`
- `outputs/research_progress_snapshot/post_live_scoring_execution_plan.csv`
- `outputs/research_progress_snapshot/post_live_scoring_launcher.json`
- `outputs/research_progress_snapshot/post_live_scoring_launcher.md`
- `outputs/research_progress_snapshot/post_live_scoring_launcher.csv`
- `outputs/research_progress_snapshot/post_live_scoring_receipt_audit.json`
- `outputs/research_progress_snapshot/post_live_scoring_receipt_audit.md`
- `outputs/research_progress_snapshot/post_live_scoring_receipt_audit.csv`
- `outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.json`
- `outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.md`
- `outputs/research_progress_snapshot/post_live_time_metric_receipt_audit.csv`
- `outputs/research_progress_snapshot/post_live_scoring_output_audit.json`
- `outputs/research_progress_snapshot/post_live_scoring_output_audit.md`
- `outputs/research_progress_snapshot/post_live_scoring_output_audit.csv`
- `outputs/research_progress_snapshot/post_live_promotion_preflight_audit.json`
- `outputs/research_progress_snapshot/post_live_promotion_preflight_audit.md`
- `outputs/research_progress_snapshot/post_live_promotion_preflight_audit.csv`
- `outputs/research_progress_snapshot/post_live_evidence_dependency_dag.json`
- `outputs/research_progress_snapshot/post_live_evidence_dependency_dag.md`
- `outputs/research_progress_snapshot/post_live_evidence_dependency_dag.csv`
- `outputs/research_progress_snapshot/live_input_integrity_audit.json`
- `outputs/research_progress_snapshot/live_input_integrity_audit.md`
- `outputs/research_progress_snapshot/live_input_integrity_audit.csv`
- `outputs/research_progress_snapshot/live_execution_runbook.json`
- `outputs/research_progress_snapshot/live_execution_runbook.md`
- `outputs/research_progress_snapshot/live_execution_runbook.csv`
- `outputs/research_progress_snapshot/live_execution_bundle.json`
- `outputs/research_progress_snapshot/live_execution_bundle.md`
- `outputs/research_progress_snapshot/live_execution_bundle.csv`
- `outputs/research_progress_snapshot/live_execution_handoff_packet.json`
- `outputs/research_progress_snapshot/live_execution_handoff_packet.md`
- `outputs/research_progress_snapshot/live_execution_handoff_packet.csv`
- `outputs/research_progress_snapshot/live_command_surface_audit.json`
- `outputs/research_progress_snapshot/live_command_surface_audit.md`
- `outputs/research_progress_snapshot/live_command_surface_audit.csv`
- `outputs/research_progress_snapshot/live_execution_eligibility_gate.json`
- `outputs/research_progress_snapshot/live_execution_eligibility_gate.md`
- `outputs/research_progress_snapshot/live_execution_eligibility_gate.csv`
- `outputs/research_progress_snapshot/live_execution_receipt_audit.json`
- `outputs/research_progress_snapshot/live_execution_receipt_audit.md`
- `outputs/research_progress_snapshot/live_execution_receipt_audit.csv`
- `outputs/research_progress_snapshot/live_execution_launcher.json`
- `outputs/research_progress_snapshot/live_execution_launcher.md`
- `outputs/research_progress_snapshot/live_execution_launcher.csv`
- `outputs/research_progress_snapshot/live_output_repair_plan.json`
- `outputs/research_progress_snapshot/live_output_repair_plan.md`
- `outputs/research_progress_snapshot/live_output_repair_plan.csv`
- `outputs/research_progress_snapshot/live_resume_state_audit.json`
- `outputs/research_progress_snapshot/live_resume_state_audit.md`
- `outputs/research_progress_snapshot/live_resume_state_audit.csv`
- `outputs/research_progress_snapshot/live_runtime_environment_audit.json`
- `outputs/research_progress_snapshot/live_runtime_environment_audit.md`
- `outputs/research_progress_snapshot/live_runtime_environment_audit.csv`
- `outputs/research_progress_snapshot/live_execution_timing_plan.json`
- `outputs/research_progress_snapshot/live_execution_timing_plan.md`
- `outputs/research_progress_snapshot/live_execution_timing_plan.csv`
- `outputs/research_progress_snapshot/live_retry_budget_audit.json`
- `outputs/research_progress_snapshot/live_retry_budget_audit.md`
- `outputs/research_progress_snapshot/live_retry_budget_audit.csv`
- `outputs/research_progress_snapshot/live_token_quota_budget_audit.json`
- `outputs/research_progress_snapshot/live_token_quota_budget_audit.md`
- `outputs/research_progress_snapshot/live_token_quota_budget_audit.csv`
- `outputs/research_progress_snapshot/live_failure_recovery_playbook.json`
- `outputs/research_progress_snapshot/live_failure_recovery_playbook.md`
- `outputs/research_progress_snapshot/live_failure_recovery_playbook.csv`
- `outputs/research_progress_snapshot/live_metric_extraction_contract.json`
- `outputs/research_progress_snapshot/live_metric_extraction_contract.md`
- `outputs/research_progress_snapshot/live_metric_extraction_contract.csv`
- `outputs/research_progress_snapshot/live_output_schema_contract.json`
- `outputs/research_progress_snapshot/live_output_schema_contract.md`
- `outputs/research_progress_snapshot/live_output_schema_contract.csv`
- `outputs/research_progress_snapshot/post_live_acceptance_scorecard.json`
- `outputs/research_progress_snapshot/post_live_acceptance_scorecard.md`
- `outputs/research_progress_snapshot/post_live_acceptance_scorecard.csv`
- `outputs/research_progress_snapshot/post_live_latency_claim_matrix.json`
- `outputs/research_progress_snapshot/post_live_latency_claim_matrix.md`
- `outputs/research_progress_snapshot/post_live_latency_claim_matrix.csv`
- `outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.json`
- `outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.md`
- `outputs/research_progress_snapshot/post_live_time_metric_statistics_plan.csv`
- `outputs/research_progress_snapshot/post_live_time_metric_extractor.json`
- `outputs/research_progress_snapshot/post_live_time_metric_extractor.md`
- `outputs/research_progress_snapshot/post_live_time_metric_extractor.csv`
- `outputs/research_progress_snapshot/live_parallelism_sensitivity.json`
- `outputs/research_progress_snapshot/live_parallelism_sensitivity.md`
- `outputs/research_progress_snapshot/live_parallelism_sensitivity.csv`
- `outputs/research_progress_snapshot/next_experiment_queue.json`
- `outputs/research_progress_snapshot/next_experiment_queue.md`
- `outputs/research_progress_snapshot/post_live_claim_promotion_gate.json`
- `outputs/research_progress_snapshot/post_live_claim_promotion_gate.md`
- `outputs/research_progress_snapshot/post_live_claim_promotion_gate.csv`
- `outputs/research_progress_snapshot/post_live_claim_promotion_receipt_audit.json`
- `outputs/research_progress_snapshot/post_live_claim_promotion_receipt_audit.md`
- `outputs/research_progress_snapshot/post_live_claim_promotion_receipt_audit.csv`
- `outputs/research_progress_snapshot/report_ppt_traceability.json`
- `outputs/research_progress_snapshot/report_ppt_traceability.md`
- `outputs/research_progress_snapshot/report_ppt_traceability.csv`

| Area | Current evidence |
|---|---|
| Four-stage timeline | 0.38s first output; 24.65s rule writeback; 44.92s LLM guard; 46.10s LLM review |
| Runtime latency budget ledger | Runtime latency budget ledger; runtime_latency_budget_ledger_from_existing_artifacts; Claim-now rows: `4`; smoke-only rows 2; pending/blocked rows 2 |
| Stage latency SLO audit | stage_latency_slo_audit_from_latency_ledger_no_live_calls; Claim-now SLO pass: `4/4`; Guard P95 margin: `1.151`; pending/blocked rows 2 |
| Latency risk margin audit | latency_risk_margin_audit_from_slo_no_live_calls; Tight-margin rows: `1`; Guard risk level `tight_margin`; Guard P95 margin ratio `0.0177`; no new metric claim |
| Latency risk mitigation plan | latency_risk_mitigation_plan_no_live_calls; Primary mitigation: `max20_resume`; stretch candidate `max15_reexport`; stretch export pass 178 prompts; blocked actions 3; no new metric claim |
| Phase result scorecard | phase_result_scorecard_from_existing_artifacts_no_live_calls; Result rows: `8`; Selector DER +2.05pp; bootstrap DER +2.17pp; claim-now SLO 4/4; guard harmful accepts 0; Qwen fallback calls 4; DeepSeek API no-go |
| Live provider routing decision | live_provider_routing_decision_no_live_calls_no_secret_values; Route rows: `4`; Default execute scope: `none`; DeepSeek no-go true; DeepSeek planned calls not selected 139; Qwen fallback calls 147; Omni label calls 96 |
| Runtime evidence audit | pass; 16 artifacts; blocking 0 |
| Rule writeback | 599 patches; recovers 60.2% Fast miss; 197.36s unique miss recovered |
| Selector generalization | holdout 8/8 positive; DER 26.51% vs Fast 28.56%; delta 2.05%; fixed ratio_le_0.65_else_uncovered 26.30%; bootstrap delta 2.17% (1.10% - 3.47%) |
| Selector true-heldout candidate scan | selector true-heldout candidate scan; selector_true_heldout_candidate_scan_no_metric_claim; Eligible true-heldout recordings: `0`; Missing new recordings to minimum: `8` |
| Selector true-heldout split validation | selector true-heldout split validation; selector_true_heldout_split_validation_no_metric_claim; True-heldout recordings: `0`; status `blocked_waiting_for_valid_sealed_split` |
| Selector true-heldout protocol | selector true-heldout protocol status `needs_new_recording_split`; fixed policy `ratio_le_0.65_else_uncovered`; no metric claim |
| Runtime-safe LLM guard | 104 windows / 1917 patches; harmful accept 0; delay 44.92s / P95 63.85s |
| Split20 LLM guard optimization | 147 prompts / 104 parent windows; top3 live wall 29.01s vs original max 48.47s; split max 28.99s; harmful 0; qwen backup wall 44.02s slower; deepseek top4/5 AllocationQuota.FreeTierOnly |
| Split20 full-live manifest | split20 full-live manifest: 104 parents / 147 calls / 1917 patches; DeepSeek completed 3 parents / 8 calls; quota failed 2 parents / 4 calls; resume calls 139 |
| Split20 resume export audit | resume export audit pass; 139 prompts / 101 parents; completed top3 overlap 0; live calls 0 |
| Split15 stretch re-export audit | split15_stretch_reexport_audit_no_live_calls; Export prompts: `178`; Parent windows 104; split parent windows 58; max subcalls 3; live calls 0; no new metric claim |
| Split policy optimization | split_policy_optimization_from_existing_artifacts_no_live_calls; Primary policy: `max20`; Stretch policy: `max15`; max20 P95 21.358s / token 1.118x; max15 P95 18.047s; fresh export audited, waiting live/scoring |
| Guard tuning contract | combined_review0.5_keepfast0.5 recovers 260 conservative blocks; materialized safe 323 / harmful 0; boundary auto-writeback DER 33.84% vs recover-best 26.40% |
| Clean high LLM audit | 136/138 accept; 2 non-accept; agreement 98.6% |
| Timeline review audit | 4 review cases; blocks writeback 0; blocks memory 4; arrival 46.10s |
| Omni fusion | 12 windows; high sentinel recall 1/4 (25.0%); clean sentinel FP 0/4 (0.0%); review FP 4/4 (100.0%) |
| Omni48 call manifest | Omni48 call manifest: 48 windows / 96 calls; 2 models; audio missing 0; label_only_no_timeline_writeback |
| Live readiness | live readiness 0/3 ready; P0 blocked 1; DeepSeek resume 139 calls / 101 parents; Qwen full backup 147; Omni48 96; no live calls performed |
| Live Agent execution plan | live_agent_execution_plan_no_live_calls; Planned live calls: `382`; DeepSeek resume calls: `139`; Omni label-only calls 96; live calls performed 0 |
| Live postrun metrics closure | live_postrun_metrics_closure_no_live_calls; DeepSeek success calls: `8` / 147; resume expected 139; Omni48 successful calls: `0` / 96; full latency claim pending |
| Live output audit | live_output_audit_no_live_calls; Expected live calls: `382`; observed rows 0; Missing output surfaces: `3`; claim-ready surfaces 0 |
| Live scoring readiness | live_scoring_readiness_no_live_calls; Scoring steps: `5`; P0 scoring steps: `2`; Ready to score: `0`; scoring commands executed false |
| Post-live scoring execution plan | post_live_scoring_execution_plan_no_live_calls; Scoring execution steps: `6`; P0/P1 steps 3/3; Blocked execution steps: `6`; Ready execution steps 0; Scoring commands 6; Missing output surfaces 3; Ready to promote 0; no scoring commands executed |
| Post-live scoring launcher | post_live_scoring_launcher_dry_run_no_scoring_calls; Available scoring rows: `6`; Ready scoring rows: `0`; Selected scoring rows 0; Executed scoring rows: `0`; Scoring execute record exists: `False`; output missing surfaces 3; no live/scoring commands executed |
| Post-live scoring receipt audit | post_live_scoring_receipt_audit_no_live_or_scoring_calls_no_secret_values; Scoring receipt rows: `6`; Scoring execute record exists: `False`; Executed scoring rows 0; Promotion-ready scoring rows 0; Computed time metric rows 0; Ready for promotion review false |
| Post-live scoring output audit | post_live_scoring_output_audit_no_scoring_calls; Scoring output rows: `6`; Blocked current-state rows 6; Promotion-ready rows: `0`; no live/scoring commands executed |
| Post-live promotion preflight audit | post_live_promotion_preflight_audit_no_live_or_scoring_calls; Preflight rows: `6`; Pass rows 2; Blocked rows 4; Ready for promotion review: `False`; Post-live ready-to-promote count 0; no live/scoring commands executed |
| Post-live evidence dependency DAG | post_live_evidence_dependency_dag_no_live_calls; DAG nodes: `10`; P0/P1 nodes 8/2; Blocked nodes: `10`; Fallback-only nodes 1; Label-only nodes 1; Expected live calls 382; Missing output surfaces 3; Ready to score 0; Ready to promote 0; no new metric claim |
| Live input integrity audit | live_input_integrity_audit_no_live_calls; Input-ready surfaces: `3` / 3; DeepSeek resume 139 prompts; Qwen full 147 prompts; Omni48 96 calls; no live call |
| Live execution runbook | live_execution_runbook_no_live_calls_no_secret_values; Steps: `7`; P0 planned live calls: `139`; DeepSeek primary policy: `max20`; no secret values written |
| Live execution bundle | live_execution_bundle_no_live_calls_no_secret_values; Bundle steps: `8`; P0/P1 steps 6/2; Blocked/waiting steps: `8`; Live-call steps 3; Command-ready 3/3; Planned live calls 382; P0 calls 139; Credential ready false; quota blockers 1; no new metric claim |
| Live execution handoff packet | live_execution_handoff_packet_no_live_calls; Packet rows: `7`; P0 rows 5; Handoff blocked/waiting rows 6; Credential ready: `False`; Known provider quota blockers: `1`; Command-ready 3/3; Planned live calls 382; no new metric claim |
| Live command surface audit | live_command_surface_audit_no_live_calls; Command-ready: `3` / 3; P0 command-ready 1; planned live calls 382; skip-existing commands 3; bounded-retry commands 3; missing inputs 0; duplicate outputs 0; secret literal commands 0 |
| Live execution eligibility gate | live_execution_eligibility_gate_no_live_calls_no_secret_values; Eligibility rows: `7`; Pass rows 2; Blocked rows 5; Ready to execute live: `False`; Input-ready 3; Command-ready 3; Credential ready false; P0 selected live calls 139; no live calls performed |
| Live execution receipt audit | live_execution_receipt_audit_no_live_calls_no_secret_values; Receipt rows: `6`; Execute record exists: `False`; Started live command calls 0; Observed live output rows 0; Claim-ready surfaces 0; Ready for postrun scoring review false |
| Live execution launcher | live_execution_launcher_dry_run_no_live_calls; Available live commands: `3`; Selected live commands: `1`; Launcher selected calls: `139`; Available live calls 382; Execute live false; Credential ready false; Executed live command rows 0; Failed live command rows 0; Started live command calls: `0`; Passed live command calls: `0`; Failed live command calls: `0`; Postrun refresh executed: `False`; Execute record exists: `False`; no secret values written; no new metric claim |
| Live output repair plan | live_output_repair_plan_no_live_calls_no_scoring; Repair rows: `3`; Clean-run rows 3; skip-existing rerun rows 0; quarantine rows 0; Missing calls: `382`; no live/scoring commands executed |
| Live resume state audit | live_resume_state_audit_no_live_calls; Clean-run surfaces: `3` / 3; current commands safe 3; skip-existing supported 3; bounded retry supported 3; append resume supported 0; quarantine required 0; missing live calls 382 |
| Live runtime environment audit | live_runtime_environment_audit_no_live_calls; Checks passed: `14` / 14; modules 6/6; scripts 3/3; output dirs 3/3; credential ready false; quota blockers 1 |
| Live execution timing plan | live_execution_timing_plan_no_live_calls; DeepSeek estimated wall: `384.444`; 139 calls / 8 workers / 18 waves; Qwen backup 836.456s fallback-only; no new metric claim |
| Live retry budget audit | live_retry_budget_audit_no_live_calls; Max attempted requests: `764`; P0 max attempted requests 278; DeepSeek retry ceiling wall 804.888s; backoff ceiling 764.0s; no new metric claim |
| Live token quota budget audit | live_token_quota_budget_audit_no_live_calls; LLM retry token proxy ceiling: `1658856`; P0 retry token proxy ceiling 801724; Omni48 retry clip-model seconds ceiling 1536.0; no new metric claim |
| Live failure recovery playbook | live_failure_recovery_playbook_no_live_calls; Scenarios: `8`; Current blocker scenarios 5; Max attempted requests 764; LLM retry token proxy ceiling 1658856; Ready to score 0; Ready to promote 0; no new metric claim |
| Live metric extraction contract | live_metric_extraction_contract_no_live_calls; Metric contracts: `8`; Time metric contracts 3; Safety metric contracts 2; Omni metric contracts 2; Ready to score 0; Expected input calls 676; no new metric claim |
| Live output schema contract | live_output_schema_contract_no_live_calls; Schema contracts: `8`; Required fields 62; Live output schema contracts 3; Scoring output schema contracts 3; Expected live output rows 382; Missing output surfaces 3; no new metric claim |
| Post-live acceptance scorecard | post_live_acceptance_scorecard_no_live_calls; Scorecard rows: `9`; P0 rows 6; Blocked rows 6; Claim-now SLO pass 4/4; Expected live calls 382; Missing output surfaces 3; Ready to promote 0; no new metric claim |
| Post-live latency claim matrix | post_live_latency_claim_matrix_no_live_calls; Latency claim rows: `8`; Claim-now preserve rows 4; Blocked/waiting rows 4; Fallback-only rows 1; Label-only rows 1; Guard P95 margin 1.151s; Ready to promote 0; no new metric claim |
| Post-live time metric statistics plan | post_live_time_metric_statistics_plan_no_live_calls; Time statistic rows: `9`; P0/P1 rows 7/2; Claim-now preserve rows 4; Blocked/waiting rows 5; Stage-arrival rows 4; Post-live statistic rows 4; Formula count 9; Planned live calls 382; no new metric claim |
| Post-live time metric extractor | post_live_time_metric_extractor_no_live_calls; Extractor rows: `3`; P0/P1 rows 1/2; Missing output rows 3; Ready time metric rows 0; Expected rows total 382; Observed rows 0; Successful rows 0; no new metric claim |
| Post-live time metric receipt audit | post_live_time_metric_receipt_audit_no_live_or_scoring_calls_no_secret_values; Time metric receipt rows: `6`; Pass rows 1; Blocked rows 5; Computed time metric rows 0; Successful rows total 0; Ready for time claim promotion: `False` |
| Live parallelism sensitivity | live_parallelism_sensitivity_no_live_calls; Recommended policy/workers: `max20` / `8`; worker12 wall 256.296s but quota-burst risk; max15/8 requires re-export |
| Post-live claim promotion gate | post_live_claim_promotion_gate_no_live_calls; Gates: `8`; Ready to promote: `0`; Blocked: `5`; Promotion policy `promote_only_after_output_audit_scoring_slo_and_traceability_pass` |
| Post-live claim promotion receipt audit | post_live_claim_promotion_receipt_audit_no_live_or_scoring_or_claim_writes_no_secret_values; Claim promotion receipt rows: `6`; Pass rows 3; Blocked rows 3; Ready to promote count 0; Report/PPT synced true; Validation passed true; Ready for claim write: `False` |
| Report/PPT traceability | report_ppt_traceability_from_existing_artifacts_no_live_calls; Rows: `54`; Fully covered rows: `54`; Missing report rows: `0`; Missing PPT rows: `0` |
| Voiceprint gate | 620/620 clean patches with voiceprint; high 226; high rule-auto 138; LLM candidates 0 |

Claims manifest 把上述汇报级结论拆成 12 条可追溯 claim，并为每条 claim 标注 source artifact、validation check、contract scope、claim strength 和 writeback right。关键边界是：`selector_generalization_positive` 标为 `dev_only_validation`，`omni_fusion_label_only` 标为 `runtime_pass_no_timeline_writeback`，`boundary_auto_writeback_negative_control` 标为 `do_not_deploy`。这使报告/PPT 中的结论可以直接追溯到当前 artifact，而不是依赖手工同步。

Phase result scorecard 把当前真正可讲的结果从执行计划里抽出来：runtime contract 是 `phase_result_scorecard_from_existing_artifacts_no_live_calls`，Result rows: `8`。当前最适合放进最终汇报的正向结果是：selector recording-holdout DER 从 28.56% 到 26.51%，weighted delta 为 +2.05pp，8/8 split 为 positive；development bootstrap 中 rule-recover policy 相比 fast baseline 的 DER delta 为 +2.17pp，P(beats fast)=100.0%；claim-now latency SLO 为 4/4，fast first output avg/P95 为 0.383/0.445s，rule writeback avg/P95 为 24.647/28.334s；runtime-safe guard 在 1917 patches 上 harmful accepts 为 0，safe accepts 为 323。Omni 当前是 12-window acoustic smoke，只支持 review routing / label-only；Qwen fallback 已完成 4 calls 且 harmful accepts 为 0，但 wall 44.024s，只能作为 fallback smoke。DeepSeek full-live path 因 API 耗尽标记为 no-go，本 scorecard 明确记录 no DeepSeek API calls、no live calls、no scoring commands、no new metric claim。

Live provider routing decision 把上述 no-go 结论推进到真实执行入口前的 provider 路由：runtime contract 是 `live_provider_routing_decision_no_live_calls_no_secret_values`，Route rows: `4`，Default execute scope 为 `none`，DeepSeek no-go 为 true，DeepSeek planned calls not selected 为 139，Qwen fallback calls 为 147，Omni label calls 为 96。这个 artifact 明确覆盖旧 runbook 中“P0 DeepSeek resume first”的默认执行文案：当前不推荐默认执行任何 primary live scope；DeepSeek 只有在 quota/capacity 被明确清除并重新打开 route 后才可恢复；Qwen 只能作为显式 fallback/safety route，Omni 只能作为 label/review route，二者都不能单独支撑 primary latency claim。该决策不执行 live/API/model/scoring call，不写 secret，也不新增 metric claim。

Runtime latency budget ledger 把所有时间指标拆成 claim-now、smoke-only、offline-budget 与 pending/blocked 四类：Fast first output、Rule writeback、runtime-safe LLM guard、LLM review signal 是 4 个 claim-now latency rows；Omni realtime single-smoke 与 DeepSeek split20 top3 live 只能作为 smoke；split20 simulation 只是 offline budget；DeepSeek full resume 与 Omni48 live 仍是 pending/blocked。该 ledger 的 runtime contract 是 `runtime_latency_budget_ledger_from_existing_artifacts`，不做 live call，专门防止把 smoke 或 planning budget 误写成 full-surface latency claim。

Stage latency SLO audit 从 latency ledger 派生出汇报级验收状态：runtime contract 是 `stage_latency_slo_audit_from_latency_ledger_no_live_calls`，不做 live call，也不新增 metric claim。当前 Claim-now SLO pass: `4/4`：Fast first output、Rule writeback、runtime-safe LLM guard、LLM review signal 都可作为当前汇报级时间指标；其中 guard P95 为 63.849s，距离 65s 阈值只剩 `1.151s` margin，应在后续 live split20 恢复中重点优化。Omni realtime single-smoke 与 split20 top3 仍是 smoke；DeepSeek full resume 和 Omni48 仍是 pending/blocked，不进入 claim-now latency。

Latency risk margin audit 把 SLO margin 再转成 risk label，避免“4/4 pass”遮住薄弱环节。当前 runtime contract 是 `latency_risk_margin_audit_from_slo_no_live_calls`，Claim-now rows: `4`，Tight-margin rows: `1`，Guard risk level 为 `tight_margin`，Guard P95 margin ratio 为 `0.0177`。结论是：Fast first output 和 Rule writeback 仍可保留当前 latency claim；runtime-safe LLM guard 虽然 pass，但 P95 余量只有 1.151s，需要优先用 split20 resume 或更小 max-patch policy 去降低 live 之后的 guard 延迟风险；smoke/planning/fallback/blocked rows 不进入 claim-now latency。

Latency risk mitigation plan 把上述 tight-margin 风险转成可执行优先级，而不是新增指标。当前 runtime contract 是 `latency_risk_mitigation_plan_no_live_calls`，Primary mitigation: `max20_resume`，即优先恢复 DeepSeek max20 的 139 个 pending calls / 101 parents，因为它已有导出 prompts、top3 live smoke 和 resume surface；`max15_reexport` 作为 quota 稳定后的 stretch candidate，模拟 P95 call 可比 max20 低 3.311s，且当前 split15 stretch re-export audit 已通过：Export prompts: `178`，覆盖 104 个 parent windows、58 个 split parent windows、max subcalls 3。它仍不能复用 max20 top3 作为 full-surface evidence，必须等 fresh live output 与 scoring 通过后才能 promotion。Qwen backup 保持 fallback-only，Omni48 保持 label-only，selector true-heldout 保持 generalization/data blocker；这些都不支撑当前 primary guard-latency mitigation claim。该 artifact 不做 live call、不写 secret、不新增 metric claim。

selector true-heldout protocol 已把 P0 `true_heldout_selector_recordings` 的下一步验收面落成 artifact：固定 policy 为 `ratio_le_0.65_else_uncovered`，sealed split 预期文件为 `data/selector_true_heldout_split.csv`，要求至少 8 个不在当前 120-window development pool 中的新 recording，并检查 recording overlap、必需字段、audio path 和 runtime feature surface。当前 protocol status 为 `needs_new_recording_split`，blockers 是 `missing_sealed_split_file` 与 `not_enough_true_heldout_recordings`；因此它只证明实验协议就绪，不产生 true-heldout metric claim。

selector true-heldout candidate scan 已扫描本机 `/Users/haojiang/data/AliMeeting/Eval_Ali` 的 far/near audio 与 far TextGrid。当前 local recordings 为 8，且 8/8 全部已经在 120-window development/selector pool 中；因此 `eligible_true_heldout_recordings=0`，`missing_new_recordings_to_minimum=8`。该 scan 的 runtime contract 是 `selector_true_heldout_candidate_scan_no_metric_claim`，不会写入 sealed split，也不会产生 DER/GT metric claim；它只是把 P0 true-heldout 的数据缺口量化。

selector true-heldout split validation 把 `data/selector_true_heldout_split.csv` 的验收入口单独落成 artifact：runtime contract 是 `selector_true_heldout_split_validation_no_metric_claim`，只检查 sealed split 是否存在、必需字段、true-heldout recording 数量、是否与 120-window development pool 重叠、audio/TextGrid 路径是否存在，以及是否保持 no-metric-claim。当前 split 文件不存在，状态为 `blocked_waiting_for_valid_sealed_split`，True-heldout recordings: `0`，blockers 是 `missing_sealed_split_file` 与 `not_enough_true_heldout_recordings`；validator 不会创建 split，也不会计算 DER/GT/support。

runtime replay manifest 已把 `end_to_end_runtime_replay_manifest` 落成 6 阶段 artifact：Fast provisional、Rule writeback、LLM guard、LLM review signal、Omni label 和 memory gate。每一行都标出 arrival time、writeback right、source artifact、validation check 和 runtime-audit status；其中只有 `fast_provisional` 与 `rule_writeback` 有 timeline writeback 权，LLM/Omni/memory 只做 guard、review、label 或 memory gate。

memory replay 已把 4 个 review/defer/repeatability drift case 逐条过 memory update gate：memory candidates before 为 4，allowed after 为 0，blocked 为 4，同时 4 个 Rule timeline writeback 全部 preserved。这把“LLM review 只保护 memory、不回滚 timeline”的边界从计数审计推进到逐 patch replay。

Omni48 manifest 已为 `omni_fusion_expand_48_or_120` 准备 48 个窗口，其中 12 个复用现有 smoke anchor，36 个来自 deployable acoustic proxy；目标模型为 flash 与 plus 两路，计划 live model calls 为 96。该 manifest 只准备输入与验收边界，live call status 仍为 `not_run_manifest_only`，因此不把 48-window recall/precision 当作已完成结论。

Omni48 call manifest 进一步把 48 个窗口展开为 96 条逐模型调用清单：每行包含 recording/window、模型、audio path、clip start/sec、proxy reason、source artifact、输出 JSONL 和 `label_only_no_timeline_writeback` 权限。该 artifact 只做 dry-run 编排，`live_calls_performed=0`，用于保证后续 live Omni48 运行可以逐调用恢复、核对和审计。

Live Agent execution plan 把后续真实 LLM/Omni 接入整理成 5 个可交接步骤：credential preflight、DeepSeek split20 resume after top3、Qwen full-surface backup、Omni48 label-only live、postrun refresh/validation。该计划的 runtime contract 是 `live_agent_execution_plan_no_live_calls`，Planned live calls: `382`，其中 P0 DeepSeek resume 为 139 calls / 101 parents；Qwen backup 为 147 calls 但当前只作为执行 fallback；Omni48 为 96 label-only calls。DeepSeek resume wall budget 使用 split20 simulated P95 call 与 8 workers 做保守估算，Omni48 first-text/total latency 明确标为待 live 实测，不把 dry-run 预算伪装成 latency claim。

Live execution runbook 把真实接入的执行顺序压成一张 7 步交接表：credential preflight、P0 DeepSeek max20 resume、post-live output audit、DeepSeek safety/comparison scoring、P1 Omni48 label-only、P1 Qwen full backup、最终 refresh/report/PPT validation。该 artifact 的 runtime contract 是 `live_execution_runbook_no_live_calls_no_secret_values`，Steps: `7`，P0 planned live calls: `139`，DeepSeek primary policy: `max20`，Claim-now SLO pass `4/4`。当前状态仍是 `blocked_waiting_for_credentials_or_live_outputs`，不会写入任何 secret value，也不会执行 live call；它只是把后续真正开跑时的命令、输出 artifact 和 success gate 统一到一个入口。

Live execution handoff packet 把 runbook、command surface、runtime env、timing/retry/token budget、failure recovery、scorecard 和 promotion gate 压成一页执行交接：runtime contract 是 `live_execution_handoff_packet_no_live_calls`，Packet rows: `7`，P0 rows: `5`，Handoff blocked/waiting rows: `6`。当前 Credential ready 为 `False`，Known provider quota blockers 为 `1`，Command-ready 为 `3/3`，Input-ready surfaces 为 `3`，Planned live calls 为 `382`，P0 planned live calls 为 `139`；因此下一次真实执行仍应先设置 runner shell 里的 DashScope/Bailian credential 并确认 DeepSeek quota/capacity，再跑 max20 resume。该 packet 只做交接，不执行 live/scoring call，不写 secret，不新增 metric claim。

Live command surface audit 把 runbook 中真正会消耗 quota 的 3 条 live command 单独做命令面审计：runtime contract 是 `live_command_surface_audit_no_live_calls`，Command-ready: `3` / 3，P0 command-ready 为 1，Planned live calls 为 `382`。它用本地解析检查 DeepSeek resume、Omni48 label-only、Qwen full backup 的必需参数、输入文件、输出目录、输出 JSONL 唯一性、`--skip-existing-output`、`--max-call-attempts 2`、`--retry-backoff-seconds 2.0` 和 secret 字面量；当前 skip-existing commands 为 3，bounded-retry commands 为 3，missing inputs 为 0、duplicate output paths 为 0、secret literal commands 为 0。该 artifact 不执行 API/model call，也不把 command-ready 当作 metric claim，只把 credential/quota 就绪后的开跑入口提前变成可审计状态。

Live execution eligibility gate 把真实开跑前的 go/no-go 条件压成 7 行：runtime contract 是 `live_execution_eligibility_gate_no_live_calls_no_secret_values`，Eligibility rows: `7`，Pass rows 为 2，Blocked rows 为 5，Ready to execute live: `False`。当前 input surface 与 command surface 已通过（Input-ready 3/3、Command-ready 3/3），但 runtime credential/quota、live readiness、launcher execute flag、operator handoff 和 post-live promotion preflight 仍 blocked；P0 selected live calls 为 `139`，推荐的第一条 execute command 是 `python scripts/run_live_execution_sequence.py --execute-live --live-scope p0`。该 gate 只记录操作入口与阻断原因，不执行 live call、不写 secret、不新增 metric claim。

Live execution receipt audit 是显式 `--execute-live` 之后的第一层回执验收：runtime contract 是 `live_execution_receipt_audit_no_live_calls_no_secret_values`，Receipt rows: `6`，Execute record exists: `False`，Started live command calls 为 0，Observed live output rows 为 0，Claim-ready surfaces 为 0，Ready for postrun scoring review 为 false。它只读取 `live_execution_launcher_execute_latest.json`、launcher、output audit、promotion preflight 与 traceability，不执行 live/API/model call；未来真实 run 留下 execute record 后，它会核对 scope、started/passed/failed calls、postrun refresh、output audit 是否观察到 live rows，再决定是否进入 postrun scoring review。

Live execution launcher 把 command surface audit 变成真实可调用入口，同时默认保持 dry-run 安全边界：runtime contract 是 `live_execution_launcher_dry_run_no_live_calls`，Available live commands: `3`，Selected live commands: `1`，默认 `--live-scope p0` 只选择 DeepSeek resume，Launcher selected calls: `139`，Available live calls 为 `382`。当前 Execute live 为 false，Credential ready 为 false，Executed live command rows 为 `0`，Failed live command rows 为 `0`，Started live command calls: `0`，Passed live command calls: `0`，Failed live command calls: `0`，Postrun refresh executed: `False`，Live calls performed by launcher 为 `0`，Execute record exists: `False`；只有显式传入 `--execute-live` 且 runner shell 里存在 DashScope/Bailian credential 时，它才会执行选中的 live command。若 live command 失败，postrun refresh 会被 `blocked_by_failed_live_commands` 阻断，避免把失败 live run 误推进 report/PPT promotion 链；若 live command 已启动，则执行态 ledger 会额外写入 `outputs/research_progress_snapshot/live_execution_launcher_execute_latest.json/.md/.csv`，后续普通 refresh 可以继续覆盖 dry-run 主账本而不丢失真实执行记录。该入口复用 command audit 已验证的命令参数，因此 skip-existing、bounded retry、input path、output path 和 secret-literal checks 与 runbook 保持一致；它不新增 metric claim。

Live output repair plan 把 live output audit、command surface audit 和 scoring readiness 合成逐 surface 的下一步动作表：runtime contract 是 `live_output_repair_plan_no_live_calls_no_scoring`，Repair rows: `3`，当前 3 个 surface 全部是 `clean_run_waiting_credentials_or_quota`，Missing calls: `382`，skip-existing rerun rows 为 0，quarantine-required rows 为 0，scoring-ready rows 为 0。未来如果输出变成 partial/invalid，它会把动作切到 skip-existing rerun 或 quarantine-before-rerun；如果输出完整，则切到 scoring commands。该 artifact 不执行 live call、不执行 scoring command、不新增 metric claim。

Live resume state audit 把真实输出文件出现前后的恢复策略单独固化：runtime contract 是 `live_resume_state_audit_no_live_calls`，Clean-run surfaces: `3` / 3，Current commands safe to run: `3`，P0 safe 为 1，Missing live calls 为 `382`。当前 LLM/Omni runner 已支持 `--skip-existing-output` 和有界重试：它会复用 successful existing rows，再覆盖写完整 merged JSONL/CSV；每个未完成 call 最多尝试 2 次，失败间隔 2.0s，它仍不做盲目 append。当前输出全缺失时可以在 credential/quota 就绪后 clean run；未来若出现 partial JSONL，应优先用 skip-existing rerun，若存在 parse/duplicate/invalid row 则先 quarantine/archive 再恢复。该 artifact 不执行 live call、不写 secret、不新增 metric claim，只把中途失败后的恢复决策提前变成可审计状态。

Live runtime environment audit 把真实调用前的本地运行环境也纳入 preflight：runtime contract 是 `live_runtime_environment_audit_no_live_calls`，Checks passed: `14` / 14，其中 module checks `6/6`、script checks `3/3`、output dir checks `3/3`，Omni48 audio manifest 为 48 rows / missing audio 0。当前 status 为 `runtime_ready_waiting_credentials_or_quota`：本地 Python/import/script/path 面已 ready，但 credential ready 为 false，且仍继承 DeepSeek `AllocationQuota.FreeTierOnly` 的 provider quota/capacity blocker。该 artifact 只写 env presence boolean，不写 secret value，也不发起网络或模型调用。

Live execution timing plan 把 runbook 的执行顺序再压成时间预算：runtime contract 是 `live_execution_timing_plan_no_live_calls`，DeepSeek estimated wall: `384.444`，来自 139 个 max20 resume calls、8 workers、18 个并行 waves 与 21.358s simulated P95 call。Qwen full backup 估算为 836.456s，且仍是 fallback-only，不支撑主 latency claim；Omni48 只有 768.0 clip-model seconds proxy，first-text/total latency 必须等 96-call live output 后才能统计。这个 artifact 的边界是 timing plan，不是 live metric claim：DeepSeek resume 仍需 JSONL、output audit、safety summary、full split comparison 和 refresh validation 通过后，才能把 split20 从 smoke/planning 推向 full-surface latency evidence。

Live retry budget audit 把 `--max-call-attempts 2` 的配额和墙钟风险显式化：runtime contract 是 `live_retry_budget_audit_no_live_calls`，3 个 live surface 都是 bounded retry surface，Planned live calls 为 `382`，Max attempted requests 为 `764`，Additional retry attempt budget 为 `382`，Backoff ceiling seconds 为 `764.0`。P0 DeepSeek max20 resume 在 139 calls / 8 workers / 18 waves 下，P0 max attempted requests 为 `278`，DeepSeek retry ceiling wall 为 `804.888`，比单次尝试 timing plan 多 `420.444s`。这些都是最坏情况执行预算，不是新的 latency metric claim；真实 claim 仍必须等 live output、output audit、scoring、SLO/traceability gate 通过。

Live token quota budget audit 把真实 LLM/Omni 接入前的 token/配额 proxy 也纳入刷新链：runtime contract 是 `live_token_quota_budget_audit_no_live_calls`，token proxy policy 是 `prompt_chars_div4_proxy_not_provider_billing_tokens`，只把本地 prompt 字符数除以 4 作为预算 proxy，不声称是 provider billing token。当前两个 LLM live surface 共 `286` prompts，LLM token proxy chars/4 为 `829428`；在 2-attempt policy 下，LLM retry token proxy ceiling 为 `1658856`。P0 DeepSeek resume 的 token proxy 为 `400862`，P0 retry token proxy ceiling 为 `801724`；Qwen full backup 为 `428566` / `857132`，仍是 P1 fallback-only。Omni48 不按文本 token 统计，而用 clip-model seconds proxy：当前 768.0，2-attempt ceiling 为 `1536.0`。这些都是 quota planning proxy，不执行 live call、不写 secret、不新增 metric claim。

Live failure recovery playbook 把真实运行前后的失败处理路径也固化成 artifact：runtime contract 是 `live_failure_recovery_playbook_no_live_calls`，Scenarios: `8`，P0 scenarios: `7`，Current blocker scenarios: `5`，Ready recovery actions: `8`。当前 blocker 覆盖 missing credentials、known provider quota、missing output clean run、scoring blocked missing output、promotion blocked；future recovery path 覆盖 partial/invalid JSONL 与 retry exhausted errors；planning guardrail 则把 Max attempted requests `764` 和 LLM retry token proxy ceiling `1658856` 固定为执行前预算边界。该 playbook 的恢复顺序是先 credential/runtime preflight，再处理 quota，再跑 skip-existing/bounded-retry live command，再做 output audit、scoring 和 promotion gate；它不执行 live call、不写 secret、不新增 metric claim。

Live metric extraction contract 把“live 输出齐了以后到底统计哪些指标”单独固化：runtime contract 是 `live_metric_extraction_contract_no_live_calls`，Metric contracts: `8`，P0 metric contracts: `4`，Time metric contracts: `3`，Safety metric contracts: `2`，Omni metric contracts: `2`。DeepSeek P0 的统计口径包括 harmful_accepts/conservative_blocks、split max call、parent avg max、wall_seconds 与 token_multiplier；Qwen 只保留 fallback safety/latency；Omni48 只统计 label quality 与 avg/P95/max call latency，不拥有 timeline writeback 权。当前 Ready to score 为 `0`，Expected input calls 为 `676`，Missing output surfaces 为 `3`，因此该 contract 只定义 post-live metric schema，不执行 scoring command、不执行 live call、不新增 metric claim。

Live output schema contract 把 live output、scoring summary 和 promotion summary 之间的字段接口也固化：runtime contract 是 `live_output_schema_contract_no_live_calls`，Schema contracts: `8`，P0 schema contracts: `5`，Live output schema contracts: `3`，Scoring output schema contracts: `3`，Required fields: `62`。LLM success JSONL 要有 window_id、parent_window_id、window_decision、patch_decisions、call_seconds、total_tokens、call_attempts 和 max_call_attempts；Omni48 success JSONL 要有 call_id、window_id、recording_id、model、diarization_risk、should_quarantine、call_seconds、schema_ok 和 retry 字段；scoring summary 还要保留 harmful_accepts、token_multiplier、avg/P95/max latency 与 promotion traceability 字段。当前 Expected live output rows 为 `382`、Missing output surfaces 为 `3`，所以该 contract 是 preflight schema，不对缺失输出做 schema validation，也不新增 metric claim。

Post-live acceptance scorecard 把 output coverage、schema、scoring、metric extraction 和 promotion gate 收成一个准入表：runtime contract 是 `post_live_acceptance_scorecard_no_live_calls`，Scorecard rows: `9`，P0 rows: `6`，Blocked rows: `6`，Fallback-only rows: `1`，Claim-now SLO pass: `4/4`。当前 Expected live calls 为 `382`，Missing output surfaces 为 `3`，Ready to score 为 `0`，Ready to promote 为 `0`；因此它只保留现有 reportable SLO claim，并把 DeepSeek resume、Omni48 和 Qwen fallback 的 post-live 升级条件写清楚，不执行 live/scoring call，也不新增 metric claim。

Post-live latency claim matrix 把“哪些时间指标现在能讲、哪些必须等 live 后才能升级”单独拉成 8 行矩阵：runtime contract 是 `post_live_latency_claim_matrix_no_live_calls`，Latency claim rows: `8`，Claim-now preserve rows: `4`，Blocked/waiting rows: `4`，Fallback-only rows: `1`，Label-only rows: `1`。当前 4 个可讲的时间 claim 仍是 fast first output、rule writeback、runtime-safe LLM guard 和 LLM review signal；DeepSeek split20 full-surface latency 需要 139 resume calls、output audit、safety/comparison scoring 和 traceability 后才能 promotion；Omni48 只允许 label-only latency，Qwen 只允许 fallback latency。Guard P95 margin 仍为 `1.151s`，Ready to promote 为 `0`，所以该矩阵不新增 metric claim，只固化报告/PPT 的时间指标边界。

Post-live time metric statistics plan 进一步把“时间指标怎么算”固定成 9 行统计口径：runtime contract 是 `post_live_time_metric_statistics_plan_no_live_calls`，Time statistic rows: `9`，P0/P1 rows 为 `7/2`，Claim-now preserve rows 为 `4`，Blocked/waiting rows 为 `5`。当前 fast first output、rule writeback、runtime-safe guard 和 LLM review signal 继续保留 avg/P95 stage-arrival 口径；DeepSeek resume live 后需要从 JSONL 统计 count、avg、p50、p95、max、wall_seconds 和 retry_count，再由 split comparison 统计 original max vs split max、parent avg/max 和 token_multiplier；Qwen 只做 fallback timing context，Omni48 只做 label-only first-text/total/call latency。当前 Planned live calls 为 `382`，Missing output surfaces 为 `3`，Ready to promote 为 `0`，所以该 plan 只定义统计公式，不执行 live/scoring command、不新增 metric claim。

Post-live time metric extractor 把上述公式落成可执行的只读统计器：runtime contract 是 `post_live_time_metric_extractor_no_live_calls`，Extractor rows: `3`，P0/P1 rows 为 `1/2`，分别对应 DeepSeek resume、Qwen backup 和 Omni48 label-only 三个 live output JSONL surface。当前 Missing output rows 为 `3`，Ready time metric rows 为 `0`，Expected rows total 为 `382`，Observed rows total 为 `0`，Successful rows total 为 `0`；因此 extractor 现在只报告 blocked_missing_output。后续真实 JSONL 出现后，它会直接计算 avg/P50/P95/max call_seconds、first_text_seconds（Omni 如有）、retry_rows 与 wall_seconds，但仍必须等 output audit、scoring、promotion 和 traceability 通过后才能进入汇报 claim。

Post-live time metric receipt audit 把“公式已定义”和“真实时间统计已产出”分开验收：runtime contract 是 `post_live_time_metric_receipt_audit_no_live_or_scoring_calls_no_secret_values`，Time metric receipt rows: `6`，Pass rows 为 1，Blocked rows 为 5，Computed time metric rows 为 0，Successful rows total 为 0，Ready for time claim promotion 为 false。当前唯一通过的是 `time_statistics_plan_alignment`，说明 9 行统计公式、4 行 post-live statistic 和 382 expected live calls 与 traceability 对齐；其余 extractor coverage、computed metrics、parse/retry quality、scoring receipt dependency 和 promotion preflight 都在等待 live/scoring evidence。该 audit 不执行 live/API/model/scoring call，不新增 metric claim；未来真实 JSONL 和 scoring receipt 出现后，它会核对 extractor rows、successful rows、parse errors、retry rows、scoring receipt 与 promotion preflight，再决定是否允许 time claim promotion。

Live parallelism sensitivity 把 P0 live run 的并行度选择显式化：runtime contract 是 `live_parallelism_sensitivity_no_live_calls`，Recommended policy/workers: `max20` / `8`，对应 139 calls、18 waves、384.444s estimated wall，与当前 runbook 和已导出的 resume surface 对齐。`max20` / 12 workers 可把估算墙钟降到 256.296s，理论收益 128.148s，但属于 medium burst，需要 provider quota/capacity 稳定后再尝试；`max15` / 8 workers 估算 415.081s，比 max20/8 略慢且必须重新导出 178 calls，不能复用 max20 top3 live evidence。该表只做 worker/policy planning，不产生 live latency metric claim。

Live postrun metrics closure 把“跑完以后如何判断能不能 claim”也落成 artifact：当前 runtime contract 是 `live_postrun_metrics_closure_no_live_calls`，DeepSeek success calls 只有 `8` / 147，top4/top5 quota-failed calls 为 4，resume expected calls 为 139 且输出尚不存在；因此 `split20_latency_claim_status=blocked_by_quota_or_missing_resume`。Omni48 当前 expected calls 为 96、successful calls 为 `0`，`omni48_latency_claim_status=pending_omni48_live_outputs`；已有 realtime single-smoke 只支持 0.744s first text / 1.356s total 的单样本链路 smoke，不支持 Omni48 recall/precision/latency claim。

Live output audit 是 postrun closure 后的逐输出文件覆盖审计：它读取 DeepSeek resume、Qwen full backup 和 Omni48 label-only 三个待出现 JSONL surface，核对 expected calls、parent coverage、重复 call、解析错误、成功行数、错误类型和 call latency 分布。当前 runtime contract 是 `live_output_audit_no_live_calls`，Expected live calls: `382`，Observed live output rows 为 0，Missing output surfaces: `3`，claim-ready surfaces 为 0；因此它不会产生 live metric claim，只负责在真实输出文件出现后把“能不能进入 safety/latency/Omni scoring”的门槛自动化。

Live scoring readiness 把“输出文件齐了以后该跑哪些评分命令”也落成 artifact：当前 runtime contract 是 `live_scoring_readiness_no_live_calls`，Scoring steps: `5`，其中 P0 是 `deepseek_resume_safety` 与 `deepseek_full_split20_comparison`；P1 是 Qwen full backup safety/comparison 与 Omni48 label summary。当前 Ready to score: `0` / 5，所有步骤都因 `blocked_missing_output` 等待 live JSONL/CSV；artifact 只记录 `analyze_runtime_safe_llm_guard.py`、`summarize_split_llm_runs.py`、`summarize_omni_window_batch.py` 的后处理命令、输入/输出 artifact 和 success gate，不执行 scoring command，也不产生 live call。

Post-live scoring execution plan 把上述评分命令再排成 live output 后的执行顺序：runtime contract 是 `post_live_scoring_execution_plan_no_live_calls`，Scoring execution steps: `6`，P0/P1 execution steps 为 `3/3`，Blocked execution steps 为 `6`，Ready execution steps 为 `0`，Scoring commands 为 `6`。顺序是 DeepSeek resume safety、DeepSeek full split20 comparison、Omni48 label summary、Qwen fallback safety、Qwen fallback comparison，最后 refresh/promotion/validation；P0 safety 必须先过 harmful_accepts == 0，full comparison 才能支撑 split20 latency promotion。当前 Missing output surfaces 为 `3`，Ready to promote 为 `0`，所以该 artifact 只做执行编排，不执行 scoring command、不写 secret、不新增 metric claim。

Post-live scoring launcher 把 scoring execution plan 变成可调用入口，同时默认保持 dry-run：runtime contract 是 `post_live_scoring_launcher_dry_run_no_scoring_calls`，Available scoring rows: `6`，Ready scoring rows: `0`，Selected scoring rows 为 0，Executed scoring rows: `0`，Output missing surfaces 为 3，Scoring execute record exists: `False`。只有显式传入 `--execute-scoring` 且对应 rows 在 scoring readiness 中已经 ready，它才会执行 scoring command；当前所有 rows 都因 live outputs missing 而 blocked，因此 launcher 不执行 live call、不执行 scoring command、不写 secret、不新增 metric claim。未来如果 scoring command 启动，执行态 ledger 会额外写入 `outputs/research_progress_snapshot/post_live_scoring_launcher_execute_latest.json/.md/.csv`，后续普通 refresh 可以继续覆盖 dry-run 主账本而不丢失真实 scoring 执行记录。

Post-live scoring receipt audit 是显式 `--execute-scoring` 之后的第一层评分回执验收：runtime contract 是 `post_live_scoring_receipt_audit_no_live_or_scoring_calls_no_secret_values`，Scoring receipt rows: `6`，Scoring execute record exists: `False`，Executed scoring rows 为 0，Promotion-ready scoring rows 为 0，Computed time metric rows 为 0，Ready for promotion review 为 false。它只读取 `post_live_scoring_launcher_execute_latest.json`、scoring launcher、scoring output audit、time metric extractor、promotion preflight 与 traceability，不执行 live/API/model/scoring call；未来真实 scoring run 留下 execute record 后，它会核对 scope、executed/passed/failed rows、scoring output audit、time metric extractor 和 promotion preflight，再决定是否进入 claim promotion review。

Post-live scoring output audit 把 scoring launcher 之后、promotion gate 之前的输出验收面单独落成 artifact：runtime contract 是 `post_live_scoring_output_audit_no_scoring_calls`，Scoring output rows: `6`，Blocked current-state rows 为 6，Promotion-ready rows: `0`。该审计读取 execution plan 的 output artifacts 并检查磁盘上哪些已经存在、哪些缺失，但不会把“文件存在”等同于可 promotion；row 还必须摆脱 blocked/waiting 状态，并通过 scoring readiness、launcher 和 promotion gate 的前置约束。当前 live/scoring 输出仍未产生，因此它不执行 live call、不执行 scoring command、不写 secret、不新增 metric claim。

Post-live promotion preflight audit 是 scoring/time/promotion 之后的总闸门：runtime contract 是 `post_live_promotion_preflight_audit_no_live_or_scoring_calls`，Preflight rows: `6`，Pass rows 为 2，Blocked rows 为 4，Ready for promotion review: `False`，Post-live ready-to-promote count 为 0。它把 live execution、scoring outputs、time metrics、promotion gate、report/PPT traceability 和 claim-boundary safety 放在同一个 preflight 表中检查；当前只有 traceability 与 no-new-metric-claim 边界通过，live/scoring/time/promotion 四个面仍 blocked。因此它不会把任何 post-live 计划、部分文件存在状态或 smoke 结果提升成汇报 claim。

Post-live evidence dependency DAG 把 live output 到 report/PPT promotion 的依赖顺序固定成 10 个节点：runtime contract 是 `post_live_evidence_dependency_dag_no_live_calls`，DAG nodes: `10`，P0/P1 nodes 为 `8/2`，Blocked nodes: `10`，Ready nodes 为 `0`。顺序是 live outputs complete -> output schema clean -> DeepSeek safety -> DeepSeek split20 latency comparison -> Omni48 label metrics / Qwen fallback metrics -> metric extraction -> latency claim matrix -> promotion gate -> report/PPT refresh validation。当前 Expected live calls 仍为 `382`，Missing output surfaces 为 `3`，Ready to score 为 `0`，Ready to promote 为 `0`；因此该 DAG 只固化证据依赖，不执行 live/scoring call、不写 secret、不新增 metric claim。

Live input integrity audit 把真实调用前的输入面单独审计：runtime contract 是 `live_input_integrity_audit_no_live_calls`，Input-ready surfaces: `3` / 3。P0 DeepSeek resume surface 已有 139 条 prompts、101 个 parent windows、pending window id 文件和 0 parse errors；Qwen full backup 已有 147 条 full prompts、104 个 parent windows；Omni48 label-only manifest 覆盖 48 windows / 96 planned calls，audio missing 为 0。这个 artifact 说明本地输入已经齐到可以交给 live runner，但输出 surface 仍是 3/3 missing，因此不会产生 live metric claim。

Live execution bundle 把 readiness、Agent plan、runbook、command audit、handoff packet 和 post-live evidence DAG 连接成一份可执行交接包：runtime contract 是 `live_execution_bundle_no_live_calls_no_secret_values`，Bundle steps: `8`，P0/P1 steps 为 `6/2`，Blocked/waiting steps: `8`，Live-call steps 为 `3`。它把 P0 DeepSeek resume live call、output audit、safety scoring、split20 latency comparison、promotion refresh 和 final validation 串成一个顺序，并把 Omni48 标为 label-only、Qwen 标为 fallback-only；当前 Command-ready 为 `3/3`，Planned live calls 为 `382`，P0 planned live calls 为 `139`，Credential ready 为 `False`，Known provider quota blockers 为 `1`。该 bundle 不执行 live/scoring command、不写 secret、不新增 metric claim，只把拿到 key 之后的执行面固定下来。

Post-live claim promotion gate 把“真实输出出现后哪些结论可以升级成汇报 claim”单独固化：runtime contract 是 `post_live_claim_promotion_gate_no_live_calls`，Gates: `8`，Ready to promote: `0`，Blocked: `5`，Fallback-only gates: `1`，Preserve/current sync gates: `2`。promotion policy 是 `promote_only_after_output_audit_scoring_slo_and_traceability_pass`：DeepSeek split20 latency/safety 必须先有 resume JSONL、output audit、safety/comparison scoring；Omni48 必须先有 96-call label-only 输出和 scoring；selector true-heldout 必须先有 sealed split 与 >=8 个新 recording。当前 gate 保留现有 4/4 SLO claim 与 report/PPT sync gate，但不会把任何 post-live 计划或 smoke 提升成 metric claim。

Post-live claim promotion receipt audit 是 post-live claim promotion gate 之后、真正改写报告/PPT claim 文案之前的最终 no-write 回执：runtime contract 是 `post_live_claim_promotion_receipt_audit_no_live_or_scoring_or_claim_writes_no_secret_values`，Claim promotion receipt rows: `6`，Pass rows 为 3，Blocked rows 为 3，Ready to promote count 为 0，Report/PPT synced 为 true，Validation passed 为 true，Ready for claim write 为 false。当前通过的三行是 promotion gate presence、report/PPT traceability receipt 和 validation receipt；阻塞的三行是没有 ready_to_promote gate、promotion preflight 仍未 ready、scoring/time receipts 仍未 ready。该 audit 不执行 live/API/model/scoring call，不写 claim text，不写 secret，也不新增 metric claim；它只在真实 live 输出、scoring、time metric、promotion preflight、traceability 和 validation 同时通过后，才允许把 post-live 结论提升成报告/PPT claim。

Report/PPT traceability 把报告、PPT 和源 artifact 的同步状态也纳入刷新链：当前 runtime contract 是 `report_ppt_traceability_from_existing_artifacts_no_live_calls`，Rows: `54`，Fully covered rows: `54`，Missing report rows: `0`，Missing PPT rows: `0`。矩阵覆盖 phase result scorecard、live provider routing decision、latency ledger、SLO audit、latency risk margin audit、Latency risk mitigation plan、selector true-heldout、Omni48、split20、split15 stretch re-export、live readiness/Agent/runbook/execution bundle/handoff packet/command audit/live execution eligibility/live receipt/live launcher/output repair/resume state/runtime env/timing/retry budget/token quota budget/failure recovery/metric extraction/output schema/acceptance scorecard/latency claim matrix/time metric statistics plan/time metric extractor/time metric receipt/scoring execution plan/scoring launcher/scoring receipt/scoring output audit/promotion preflight/claim promotion receipt/evidence dependency DAG/parallelism/input/output/scoring、post-live promotion gate、runtime replay、memory replay、claims manifest 和 next queue；它只读取现有 JSON/Markdown/PPT 文本，不执行 live call，也不新增 metric claim。

split20 full-live manifest 已把 P0 `full_split20_live_104w` 的执行面单独落成 artifact：全量 surface 为 104 个 parent windows、147 个 split20 subcalls、1917 个 patch references；DeepSeek 目前只完成 top3 parallel smoke（3 parents / 8 calls，wall 29.01s，harmful 0），top4/top5 有 2 parents / 4 calls 因 `AllocationQuota.FreeTierOnly` 在生成前失败；最少还需 139 个 DeepSeek subcalls 才能把 full-surface latency claim 跑完。manifest 同时生成 `outputs/research_progress_snapshot/split20_deepseek_resume_after_top3_window_ids.txt`，只包含排除已完成 top3 之后的 101 parents，可直接作为 `--window-id-file` 恢复运行入口。qwen backup 对 top4/top5 的 4 个 calls harmful 0，但 wall 44.02s 且 verdict 为 `slower_than_original_max`，所以只能证明执行链路可跑，不能支撑主 latency claim。

split20 resume export audit 已用现有 runner 的 `--mode export` 对上述 pending window-id file 做 dry run：导出 139 条 prompts，覆盖 101 个 parent windows，不包含已完成 top3，且保留 2 个 quota-failed top4/top5 parent；该 audit 的 live calls 为 0。这说明一旦 DeepSeek quota/capacity 与 API key 就绪，可以直接从该 resume surface 恢复，而不需要重新选择窗口。

split15 stretch re-export audit 已把上述 stretch candidate 从“待导出计划”推进成可审计输入面：runtime contract 是 `split15_stretch_reexport_audit_no_live_calls`，Export prompts: `178`，覆盖 104 个 parent windows，split parent windows 为 58，max subcalls per parent 为 3，prompt patch references 仍为 1917。该导出只运行 `--mode export`，live calls performed 为 0；它证明 max15 对照面已经准备好，但仍是 stretch，不是默认 P0 live path，也不会产生 latency metric claim。

Split policy optimization 进一步把 `max_patches_per_call` 的选择固定成可审计策略，而不是临时手调。当前 runtime contract 是 `split_policy_optimization_from_existing_artifacts_no_live_calls`，只读 split simulation、manifest、live output audit 和 scoring readiness，不做 live call，也不产生 metric claim。结论是：`max20` 仍是 primary resume path，因为它已有导出的 147 prompts、已完成 top3 live smoke、剩余 139 calls 的 resume surface，模拟 P95 call 为 21.358s，token multiplier 为 1.118x；`max15` 是 latency stretch candidate，模拟 P95 call 可降到 18.047s、token multiplier 1.182x，当前 fresh export 已审计通过，但不能把 max20 top3 smoke 直接复用成 max15 full-surface evidence。因此下一次真实 DeepSeek 恢复仍应优先跑 max20；只有在 quota 稳定后再把 max15 作为重导出对照。

live readiness artifact 把真实调用前的运行条件也落成非 secret、无 live call 的检查：当前 shell 下 `omni48_live`、`split20_deepseek_full`、`split20_qwen_backup` 均未 ready，ready runs 为 0/3；原因是未检测到 DashScope/Bailian API key 环境变量，且 P0 DeepSeek resume surface 仍继承 top4/5 `AllocationQuota.FreeTierOnly` 的已知 provider quota 阻塞。该 readiness 行已对齐当前执行入口：DeepSeek P0 使用排除 top3 后的 139 calls / 101 parents 与 `--window-id-file` 恢复运行；Qwen backup 仍保留完整 147 calls / 104 windows；Omni48 仍为 96 label-only calls。该 artifact 只记录 env presence、manifest 完整度、计划调用规模和 run command，不写入任何密钥值。

Next experiment queue 将后续路线拆成 5 个实验项，其中 `full_split20_live_104w` 和 `true_heldout_selector_recordings` 是 P0：前者受 deepseek top4/5 quota 阻塞，用于把 split20 从 top3 smoke 推到 104-window 全量 live latency claim；后者需要新 recording split，用于把 selector 从 development validation 推向更强的 held-out evidence。P1 项中 `end_to_end_runtime_replay_manifest` 与 `memory_update_audit_replay` 已完成，`omni_fusion_expand_48_or_120` 已进入 `prepared_manifest_pending_live_calls`。`boundary_auto_writeback` 继续列为 do-not-deploy。

### 系统化实验协议：把“巧妙设计”变成可复现实验

如果最终目标是类似实时系统的效果，实验不能只比较单模型 DER。更规范的口径应该是：**每一层都同时报告 DER/误差分解、用户可见到达时间、写回权限和兜底安全性**。因此后续实验统一用 system experiment matrix 管理：

```bash
python scripts/build_system_experiment_matrix.py
```

生成产物：

- `outputs/system_experiment_matrix/system_experiment_matrix.csv`
- `outputs/system_experiment_matrix/system_experiment_matrix.md`

核心矩阵：

| Layer | Runtime path | Writeback right | Primary metric | Current latency | Current effect |
|---|---|---|---|---|---|
| L0 fast provisional | Sortformer / streaming diarization | timeline first output | first-output latency, DER, Miss, speaker-count accuracy | 0.38s avg / 0.44s P95 | 120段 DER 28.56%；Miss 19.96%；spk match 54.2% |
| L1 slow acoustic correction | DiariZen mature-window rerun | candidate only until rule gate | DER/Miss/FA/Conf, recoverable Fast miss, extreme FA rate | 24.65s avg / 28.33s P95 | 120段 raw DER 16.88%；median 10.83%；FA 6.92%；spk match 67.5% |
| L2 rule writeback | deterministic Policy Agent | bounded timeline writeback | writeback precision, recovered miss seconds, harmful writeback count | 24.65s avg / 28.33s P95 | 120 timeline DER 26.40%；Miss 15.57%；recover 覆盖 60.2% Fast miss；selector holdout 26.51% DER，8/8 为正 |
| L3 LLM guard | deepseek-v4-flash window batch | block/quarantine only | harmful accept=0, quarantine recall, async correction delay | 44.92s avg / 63.85s P95 | runtime-safe proxy guard 104 窗口 / 1917 patches；harmful accept 0；passthrough v2 safe accept 323 / conservative 1551；auto-boundary negative control 33.84% DER；split20 top3 parallel wall 29.01s；qwen top4/5 backup 44.02s 但更慢 |
| L4 Omni realtime risk probe | qwen3.5-omni-flash-realtime | label-only weighted evidence | first text latency, high-risk recall, clean false positive | 0.744s first text / 1.356s total | 12-window fusion：high sentinel recall 1/4，clean sentinel FP 0/4，review clean FP 4/4；flash batch avg/P95/max 2.114s / 6.408s / 12.426s |
| L5 speaker memory | one-shot anchor + conservative voiceprint memory | identity label after gate | global ID accuracy, ID switch rate, merge/split error | 不阻塞首出 | Sortformer 48 ID memory 68.8% vs fixed 31.5%；semantic voiceprint 82/88 ok、LLM candidates 0；clean audit 620/620 ok、high 226，其中 138 个 rule-auto；clean LLM audit full 136/138 accept、2 defer；repeat 42/44 same；timeline audit 4 cases blocks writeback 0 / memory 4 |

运行时不变量：

- **LLM/Omni 不产生时间戳**：它们只能读取 patch graph，在 `accept/reject/defer/quarantine` 受限空间内工作。
- **Omni 是兜底感知，不是 diarizer**：Omni high risk 只能提高 acoustic quarantine 优先级；medium/unknown 或普通 review hint 只打标签/排队/解释，不改 timeline。12-window smoke 显示普通 review clean FP 可到 4/4，所以不能给写回权。
- **Rule Agent 是当前写回执行器**：低风险 patch 由规则写回；LLM 只守门高风险或审计未来低风险候选。
- **评估真值和运行证据严格分离**：DER、GT overlap、oracle speaker label 只能用于离线评估，不能进入 runtime prompt。
- **每个实验必须同时报时间指标**：DER/Miss/FA/Conf 之外，还要报 avg latency、P95 latency、RTF、stage arrival time。
- **声纹库更新有硬门槛**：只允许高置信、足够长、非重叠、非异常窗口片段更新 memory，防止长期系统被污染。

这套协议让 LLM 的角色更清楚：它不是“帮模型变准”的魔法模块，而是系统里的**规范指导与兜底层**。它负责发现高风险、解释冲突、隔离污染窗口、避免错误写回；长期 DER 的实际下降来自 Fast/Slow selector、Rule writeback、speaker memory 和低风险候选的长期积累。

#### Runtime evidence audit：把开发集证据和可部署证据拆开

为了避免“看起来像 Agent，实际偷看了评估真值”的问题，新增 runtime evidence audit：

```bash
python scripts/build_deployable_abnormal_windows.py
python scripts/audit_runtime_evidence_contract.py
```

生成产物：

- `outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv`
- `outputs/deployable_abnormal_windows/deployable_abnormal_windows.md`
- `outputs/runtime_evidence_audit/runtime_evidence_audit.md`

审计结果：

总体：16 个 artifact 被审计，8 个 runtime surface `pass`、8 个 development-only surface 标为 `dev_only`，runtime blocking artifact 为 0。

| Artifact | Status | 结论 |
|---|---|---|
| deployable abnormal proxy flags | pass | 只用 Fast/Slow 预测统计；104/120 窗口被 prediction proxy 标记 |
| runtime-safe policy-agent decisions | pass | 2664 个 patch 决策不含 GT/DER/Miss/FA/oracle 字段；1584 accept、911 defer、169 quarantine |
| four-stage system timeline | pass | `fast_provisional`、`rule_writeback`、`llm_guard`、`llm_review_signal` 四阶段时间线不含 eval-derived 字段 |
| LLM review-signal timeline audit | pass | 4 个 review signal：timeline writeback blocker 0、memory update blocker 4；无 GT/DER/eval 字段 |
| Omni fusion no-writeback contract | pass | Omni fusion 只产生 early quarantine/review/label actions；runtime contract 为 no timeline writeback |
| runtime-safe proxy window-batch prompts | pass | 104 个 proxy prompt 已导出并全量审计，prompt 内无 eval-derived 字段 |
| runtime-safe split20 replay prompts | pass | 严格复用 104w 实测 patch_id surface；147 个 sub-batch prompts / 104 parent windows / 1917 patches |
| runtime-safe deepseek guard call | pass / measured | 104 个 proxy-flag 窗口真实调用；1917 patch；raw harmful accept 2；window quarantine override 2 后 effective harmful accept 0；avg 44.92s / P95 63.85s correction arrival |
| eval abnormal flags | dev_only | 包含 DER/Miss/FA/GT speaker count，只能做离线风险分析 |
| selector recording-holdout validation | dev_only | selector 阈值选择/评分使用 DER，只能作为开发集泛化证据，不是 runtime context |
| legacy 120 writeback gate decisions | dev_only | 旧 gate 仍含 `high_der/high_fa/high_miss`，只保留为开发集对照 |
| legacy single/window-batch LLM prompts | dev_only | 旧 prompt 没有直接 GT 字段，但带入 eval-derived abnormal flags，只能作为 development risk probe |
| selector policy source | pass | selector 使用 Fast/Slow 预测侧特征；DER 只用于训练集排序和评分 |
| deterministic policy-agent source | dev_only | 使用 `gt_support` 做开发集 oracle-style 决策，不能声称可部署 |

关键修正：

- 真实 runtime 可以使用 `deployable_abnormal_windows` 里的代理信号：pred speech 太长/太短、Fast/Slow speaker count 不一致、跨模型分歧过大、segment count gap。
- 当前 `deepseek` high-risk guard 的 40-48s 结果仍然是**development risk probe**，因为它来自旧 eval-derived abnormal flags。
- runtime-safe proxy prompt 已通过审计并完成全部 104 个 proxy-flag 窗口的真实 `deepseek-v4-flash` 调用：96 window quarantine、8 window review；raw patch 输出出现 2 个 harmful accept，说明模型仍会在窗口级 quarantine 下给出局部 accept。
- 执行层新增 window-quarantine override：当 window_decision 为 quarantine 时，patch accept 被统一降级为 quarantine/defer；effective 口径下 1917 patch harmful accept 0、safe accept 63、conservative block 1811、safe block 43。
- 这条 runtime-safe LLM guard 全量覆盖后平均完整 correction arrival 为 44.92s，P95 为 63.85s；相比 24w 小样本更慢，下一步重点不是继续扩样本，而是调低 conservative block 并把 review/quarantine 分层。

#### Runtime-safe Guard Latency Breakdown

为了定位 104-window guard 的慢点，新增 window-level latency breakdown：

```bash
python scripts/analyze_runtime_safe_llm_latency.py
```

生成产物：

- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency.csv`
- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency.md`
- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_latency_summary.json`

核心结果：

| Slice | Windows | Patches | Avg call | P95 call | Avg correction | P95 correction |
|---|---:|---:|---:|---:|---:|---:|
| all runtime-safe guard | 104 | 1917 | 20.27s | 35.35s | 44.92s | 59.99s |
| quarantine windows | 96 | 1740 | 19.61s | 33.16s | 44.25s | 57.81s |
| review windows | 8 | 177 | 28.26s | 41.47s | 52.91s | 66.11s |
| patch count 3-5 | 17 | 62 | 9.60s | 16.72s | 34.25s | 41.37s |
| patch count 6-15 | 29 | 331 | 15.99s | 24.15s | 40.64s | 48.80s |
| patch count >15 | 58 | 1524 | 25.54s | 36.94s | 50.18s | 61.59s |

解释：

- 主 safety summary 的 P95 contract 仍按 `slow P95 + LLM call P95 = 63.85s` 汇报；breakdown 表中的 `59.99s` 是用 slow avg 叠加每个窗口 call 后的 window-level P95，适合分析瓶颈但不替代保守验收口径。
- 慢点主要来自大 patch 窗口和长输出：`>15 patches` 的 58 个窗口贡献了 1524/1917 个 patch，平均 call 25.54s。
- `review` 窗口只有 8 个，但平均 call 28.26s，比 quarantine 更慢，说明后续优化不只是少 quarantine，而是要**拆分大窗口、限制 patch 列表长度、压缩每 patch 输出字段**。

#### Split-window Latency Simulation

为了决定下一步是否值得真实调用拆分 prompt，新增了一个只基于实测 104-window latency 表的离线仿真：

```bash
python scripts/simulate_runtime_safe_llm_splitting.py

python scripts/llm_window_batch_policy_eval.py \
  --mode export \
  --decisions outputs/runtime_safe_policy_agent/sortformer_diarizen_120_decisions.jsonl \
  --trigger-policy proxy_flagged_window \
  --window-evidence outputs/deployable_abnormal_windows/sortformer_diarizen_120_proxy.csv \
  --patch-id-file outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_patch_ids.txt \
  --max-patches-per-call 20 \
  --model deepseek-v4-flash \
  --output-jsonl outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl
```

生成产物：

- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation.csv`
- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation.md`
- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split_simulation_summary.json`
- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompts.jsonl`
- `outputs/runtime_safe_llm_window_batch/deepseek_proxy_high_risk_104w_split20_replay_prompt_summary.json`

模型口径：先拟合 `total_tokens ~= 1699.85 + 339.67 * patch_count` 和 `call_seconds ~= 4.02 + 0.002042 * total_tokens`，再估算大窗口被拆成多个并行子批次后的窗口完成时间。它只能作为下一轮 live-call 预算，不替代真实 LLM 结果。

| Max patches/subcall | Split windows | Calls | Added calls | Est. avg call | Est. P95 call | Est. avg correction | Est. P95 correction | Token multiplier |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| observed no split | 0 | 104 | 0 | 20.27s | 35.35s | 44.92s | 59.99s | 1.00x |
| 20 | 40 | 147 | 43 | 16.58s | 21.36s | 41.23s | 46.01s | 1.12x |
| 15 | 58 | 178 | 74 | 14.98s | 18.05s | 39.62s | 42.69s | 1.18x |
| 12 | 70 | 209 | 105 | 13.86s | 16.19s | 38.51s | 40.84s | 1.25x |

结论：下一轮真实调用优先验证 `max_patches_per_call=20`，因为它用较小成本换来最大的一阶收益：估计 P95 call 从 35.35s 降到 21.36s，只增加 43 次调用和约 1.12x token。若 live split 验证成立，再评估 15-patch 策略是否值得额外调用成本。

当前已经完成 live-call 前置准备：严格复用既有 104w 实测输出中的 1917 个 patch_id，导出 147 个 split20 replay prompts，覆盖 104 个 parent windows，其中 40 个 parent windows 被拆分，最大每个父窗口 3 个 subcall。该 prompt surface 已纳入 runtime evidence audit，状态为 pass；下一步可以只对最慢窗口先做 live split 调用，验证模型在 sub-batch prompt 下是否保持同等安全约束。

已完成最慢父窗口 `R8007_M8010:30:0` 的真实 split20 smoke：

| Parent window | Patches | Original call | Split subcalls | Parallel split call | Sequential script time | Token multiplier | Harmful accepts | Parent override |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| R8007_M8010:30:0 | 45 | 48.47s | 3 | 24.49s | 57.88s | 1.14x | 0 | true |

解释：当前脚本按顺序调用 3 个 sub-batch，所以实际脚本运行时间是 57.88s；部署收益来自并行 subcall，墙钟按最慢子调用估算为 24.49s，比原始单窗口 48.47s 降约 49.5%。安全上，3 个 subcall 中有 2 个 quarantine、1 个 review；父窗口聚合规则是“任一 subcall quarantine 则父窗口 quarantine”，因此 review subcall 中的 1 个 accept 被父窗口 quarantine override 降级，effective harmful accept 仍为 0。

随后扩展到 104w 中原始 call 最慢的 top3 父窗口，真实调用 8 个 split20 subcall，并用 `--parallel-workers 8` 复跑测量实际并行 wall-clock：

| Scope | Parent windows | Patches | Original avg call | Parallel split avg call | Measured wall | Original max | Split max | Token multiplier | Harmful accepts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| top3 slowest windows | 3 | 127 | 44.25s | 24.81s | 29.01s | 48.47s | 28.99s | 1.10x | 0 |

这把 split20 从“仿真预算”推进到了小样本真实并行验证：top3 并行实测 wall-clock 为 29.01s，低于原始最慢单窗口 48.47s，且没有引入 harmful accept。限制仍然清楚：这是最慢 top3 的小样本 smoke，不代表全量 104w 已重跑；同时 parent-window quarantine override 会牺牲一部分局部 accept，换取窗口级污染隔离。

继续扩展 top4/top5 时触发了外部配额限制：`deepseek-v4-flash` 返回 `AllocationQuota.FreeTierOnly`，4 个 subcall 全部在模型生成前失败。因此 top4/top5 不计入 split20 有效性能样本；当前可报告的真实 split20 证据停在 top3，后续需启用 paid quota 或切换等价 guard model 后恢复验证。

为确认 top4/top5 样本和 split20 执行链路本身不是问题，我用 backup guard candidate `qwen3.6-flash-2026-04-16` 对同两个父窗口做了并行 split20 补测：

| Scope | Model | Parent windows | Patches | Split calls | Original avg call | Split parent avg max | Measured wall | Original max | Split max | Token multiplier | Harmful accepts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| top4/top5 backup smoke | qwen3.6-flash-2026-04-16 | 2 | 60 | 4 | 36.09s | 42.67s | 44.02s | 36.45s | 44.00s | 1.38x | 0 |

这个补测的价值主要是负向边界：qwen backup 在 parent-window override 后仍保持 harmful accept 0，但没有带来 latency 收益，且 token multiplier 升到 1.38x。它说明 split20 脚本和 top4/top5 样本可执行，但 qwen 不能替代 deepseek primary guard 来支撑“拆分后更快”的结论；qwen 仍应保留为备用守门/审计候选，而不是当前实时延迟优化主路线。

#### Runtime-safe Guard Tuning

为了避免 LLM guard 变成“全量隔离器”，我在 104 窗口输出上做了一轮只使用 deployable 特征的后处理调参。策略输入只包含 LLM window decision、patch type、cross-model support；GT support 只在事后用于判定 harmful accept。

| Candidate policy | Candidate accepts | Conservative recovered | Harmful accepts | Safe accepts after | Conservative after | 结论 |
|---|---:|---:|---:|---:|---:|---|
| review support >= 0.5 non-suppress | 104 | 104 | 0 | 167 | 1707 | review 窗口可局部放行 |
| keep_fast_supported support >= 0.5 passthrough | 165 | 165 | 0 | 228 | 1646 | 保留已可见 Fast 片段可作为低风险 passthrough |
| combined review0.5 + keepfast0.5 | 260 | 260 | 0 | 323 | 1551 | 当前最佳零 harmful 候选 |
| negative: quarantine support >= 0.95 | 1134 | 1117 | 17 | 1180 | 694 | 负对照：quarantine 内仅靠高 support 会伤害 |

结论：下一版 guard 不应该直接放开 quarantine window；更稳的路线是把 `review` window 里的高 support 非 suppress patch 放行，并把 `keep_fast_supported` 当作“保留已有实时首出”而不是新增 slow writeback。严格 window override 下可 materialize 104 个新增 safe accept；加入 `keep_fast_supported_passthrough_exception` 的 v2 contract 后，样本内 best candidate 可 materialize 260 个 conservative block 恢复，safe accept 323，harmful accept 仍为 0。

把该 v2 候选进一步 materialize 成边界自动写回后，结果反而给出负对照：`boundary_fix_or_relabel` 被升级为 auto-writeback 后，边界替换数从 359 增到 403，但 `rule_boundary_recover` timeline DER 从 32.54% 升到 33.84%，FA 从 14.84% 升到 16.14%。因此 v2 的定位应固定为 **review/passthrough safety contract**：它可以减少不必要的 conservative block、保护已可见 Fast 片段，但不能把 LLM 放行的边界修正直接当作可部署时间线写回。

| Materialization | Boundary replaced | Timeline DER | Miss | FA | Conf | 结论 |
|---|---:|---:|---:|---:|---:|---|
| rule boundary+recover baseline | 359 | 32.54% | 12.86% | 14.84% | 4.83% | 边界写回已是负对照 |
| tuned v2 boundary auto-writeback | 403 | 33.84% | 12.77% | 16.14% | 4.93% | 更多边界替换提高 FA，不能自动写回 |

#### Realtime Acceptance Spec v1

为了把最终系统做成“实时可用 + 长期 DER 好”的形态，后续每个实验都按下面的验收 contract 汇报，而不是只报单点 DER。

| Contract item | 验收口径 | 当前基线 | 下一步优化目标 |
|---|---|---:|---|
| First visible timeline | 用户可见首出延迟、RTF、首版 DER/Miss | 0.38s avg / 0.44s P95；DER 28.56% | GPU streaming sweep 后确定 `<1s` 展示档位 |
| Mature acoustic correction | 慢模型候选到达时间、raw/median DER、异常 FA 段比例 | 24.65s avg / 28.33s P95；raw DER 16.88%，median 10.83% | 隔离 DiariZen 极端 FA 窗口，避免污染写回 |
| Safe writeback | 写回后 timeline DER、Miss/FA/Conf、harmful writeback | 120 policy sweep DER 26.40%；selector recording-holdout 26.51%，8/8 为正；recover 60.2% Fast miss | 在新采样窗口固定验证 `ratio_le_0.65_else_uncovered` |
| Guard and fallback | LLM/Omni 调用延迟、quarantine recall、harmful accept | runtime-safe deepseek guard 44.92s avg / 63.85s P95；104 windows / 1917 patches；raw harmful accept 2，override 后 harmful accept 0；passthrough v2: safe accept 323 / conservative 1551；auto-boundary negative control DER 33.84% | 固化 review0.5 + keepfast0.5 为 review/passthrough contract，禁止直接自动边界写回；不再使用 `high_der/high_fa` |
| Long-term identity | global ID accuracy、ID switch、memory pollution | Sortformer 48 memory 68.8% vs fixed 31.5% | 输出在线 top1/top2/margin，接入 writeback gate |

这个 contract 也定义了 LLM 的合理边界：

- **规范指导**：LLM 读 patch graph、ASR 摘要、声纹 margin、邻接一致性，判断是否违反系统规则。
- **兜底隔离**：LLM/Omni 可以把窗口升级为 `defer/quarantine/review`，但不能自由生成时间戳。
- **长期纠偏**：LLM 可以帮助解释跨窗口 speaker label 冲突，辅助 label smoothing；真正改 timeline 仍由 Rule/Policy gate 执行。
- **实验防泄漏**：prompt 里只放部署时可获得证据；DER、GT support、oracle speaker label 只用于离线评分。
- **时间同等重要**：任何降低 DER 的方案，如果让 first output 或 correction arrival 超过协议预算，不能作为主实时路线，只能作为离线二审。

因此技术路线的主要改进点可以正式表述为：**把 diarization 从单模型任务改造成分阶段、可写回、可审计的实时系统优化问题**。Fast Agent 先保证体验，Slow/Rule/Memory 保证长期 DER 和身份一致性，LLM/Omni 只负责兜底、规范仲裁和污染隔离。这比“继续调 PyAnnote 阈值”更有研究空间，也更贴近真实会议系统。

Threshold sweep：

| Match threshold | Sortformer acc | DiariZen acc | 说明 |
|---:|---:|---:|---|
| 0.25 | 78.0% | 69.6% | 阈值偏低，部分不同说话人被合并 |
| 0.30 | 78.0% | 69.6% | 合并风险仍存在 |
| 0.35 | 79.1% | 69.6% | 当前最稳折中 |
| 0.40 | 79.0% | 69.6% | 与 0.35 接近，但更容易拆分 |
| 0.45 | 78.8% | 69.1% | global speaker 变多，拆分开始增加 |

Enrollment / update ablation：

| Setting | Sortformer acc | DiariZen acc | 说明 |
|---|---:|---:|---|
| 1-window enrollment, conservative update | 79.1% | 69.6% | 当前主配置 |
| 2-window enrollment, conservative update | 79.4% | 69.7% | 提升很小，说明一次注册基本够用 |
| 1-window enrollment, static memory | 79.0% | 67.6% | 不更新对 DiariZen 更差 |
| 1-window enrollment, aggressive update | 78.6% | 68.5% | 错误片段污染声纹库 |

解释：

- 这组结果直接支持“视觉一次注册 + 声纹记忆”的核心路线：只用首段固定映射不够，但加入声纹记忆后，Sortformer 的全局身份一致性几乎达到逐窗口 oracle 上限。
- Sortformer 的 voiceprint memory 表现高于 DiariZen，说明实时 Fast Agent 的短窗口边界虽然 Miss 高，但它产生的局部 speaker 片段更适合作为声纹记忆候选；DiariZen 更强 DER 仍适合 Slow Agent 做边界和漏检修正。
- 两窗口注册几乎不提升，说明视觉不必持续参与；它更适合作为开场 identity anchor。
- conservative update 优于 static/aggressive，说明声纹库需要“只用高置信、较长、非重叠片段更新”的策略，而不是无脑累积。
- 因此双 Agent 分工更清楚：Fast Agent 负责可实时的候选身份流，Slow Agent 负责离线强重分割、声纹库清洗和全局回写。

### Experiment A: Streaming Sortformer latency sweep

目标：建立 Fast Agent baseline。

变量：

- latency: 0.32s, 1.04s, 10.0s, 30.4s。
- window/chunk config: 按官方 streaming config。
- 数据：AliMeeting 当前 24/48 段；后续扩到 120 段。

指标：

- DER / Miss / FA / Conf。
- latency / RTF。
- speaker count accuracy。
- cross-window ID switch rate。
- short response recall。

预期：

- 0.32s 最快但 DER 较高。
- 1.04s 可能是实时展示最合理折中。
- 10s/30.4s 可作为“准实时修正层”。

### Experiment B: Fast-to-Slow correction

目标：证明双 Agent 有价值。

流程：

1. Fast Agent 产出 streaming Sortformer timeline。
2. Slow Agent 用 DiariZen 对同一窗口重跑。
3. 建立 patch：`local_speaker_id -> global_speaker_id` 和边界修正。
4. 比较修正前后 DER、ID switch、speaker count accuracy。

核心指标：

- DER improvement。
- ID switch reduction。
- correction latency。
- 修正覆盖率：多少实时错误能被后台修正。

### Experiment C: One-shot visual enrollment simulation

目标：即使没有完整视觉 pipeline，也先验证“视觉一次注册”的上限。

可行做法：

- 用 oracle speaker ID 模拟视觉注册结果。
- 每个 speaker 只取最早一个高质量 speech segment 当 enrollment。
- 后续所有窗口做 voice embedding matching。
- 评估 global ID consistency 是否提升。

这个实验很重要，因为它能先证明你的核心假设：

> 一次性身份注册 + 声纹记忆能否减少跨窗口 speaker drift。

### Experiment D: Memory update ablation

目标：把“声纹库”从想法变成可发表的模块。

对比：

- no memory: 每个窗口独立 diarization。
- static memory: 只用初始 enrollment，不更新。
- conservative memory: 只用高置信度片段更新。
- aggressive memory: 所有片段都更新。

指标：

- ID switch rate。
- speaker purity。
- DER。
- 误合并率 / 误拆分率。

预期：

- static memory 能降低漂移，但对音质变化不稳。
- aggressive memory 容易被错误片段污染。
- conservative memory 最可能成为主方案。

### Experiment E: LLM delayed correction

目标：验证 LLM 作为 Slow Agent 的价值边界。

输入：

- ASR transcript。
- Fast/Slow diarization candidates。
- speaker memory 中的角色信息。

输出：

- 只允许修改 speaker label，不允许重新发明时间戳。

指标：

- WDER。
- speaker label accuracy。
- short response attribution。
- hallucination / invalid edit rate。

## 6. 建议论文/汇报里的主张

可以这样讲：

> 现有实时 diarization 方法追求低延迟，但容易出现 speaker count error、跨窗口身份漂移和短回应漏检；离线强模型如 DiariZen 精度更高但无法直接实时。本文拟采用双 Agent 架构：Fast Agent 用 streaming diarization 提供低延迟初稿，Slow Agent 利用视觉 one-shot enrollment、声纹记忆库、离线强基线和语义后处理进行长期矫正，从而兼顾实时可用性和全局身份一致性。

真正的改进点：

- 不是“多用了一个视觉模型”，而是**把视觉从持续依赖变成一次性身份注册**。
- 不是“LLM 做 diarization”，而是**LLM 只做语义级 speaker label correction**。
- 不是“离线 DER 更低”，而是**实时输出可用，后台可修正，全局 ID 更稳定**。

## 7. 风险和边界

- Streaming Sortformer 最大 4 speaker，超过 4 人需要 fallback 或分组策略。
- 中文会议域外性能不一定稳定，需要 AliMeeting 实测。
- DiariZen 权重是非商业许可，论文研究可以用，商业系统需要换权重或重新训练。
- 视觉注册依赖摄像头视角；如果人脸不可见，要退化成 audio enrollment。
- LLM 只能改 label，不能让它自由生成时间戳，否则会不可控。

## Sources

[1] [NVIDIA Streaming Sortformer model card](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2) — streaming configs, latency/RTF, limitations.

[2] [NVIDIA NeMo Curator speaker separation docs](https://docs.nvidia.com/nemo/curator/curate-audio/process-data/quality-filtering/speaker-separation) — offline vs streaming Sortformer usage.

[3] [Streaming Sortformer, Interspeech 2025 PDF](https://www.isca-archive.org/interspeech_2025/medennikov25_interspeech.pdf) — AOSC/speaker cache and online diarization framing.

[4] [LS-EEND: Long-Form Streaming End-to-End Neural Diarization](https://arxiv.org/abs/2410.06670) — online attractor and long-form streaming EEND.

[5] [DiariZen GitHub](https://github.com/BUTSpeechFIT/DiariZen) — DiariZen benchmark and AliMeeting far result.

[6] [Leveraging Self-Supervised Learning for Speaker Diarization](https://arxiv.org/abs/2409.09408) — WavLM + Conformer for DiariZen-style strong offline baseline.

[7] [Audio-Visual Speaker Diarization: Current Databases, Approaches and Challenges](https://arxiv.org/abs/2409.05659) — AVSD landscape and identity assignment challenge.

[8] [AVA-ActiveSpeaker, Google Research](https://research.google/pubs/ava-activespeaker-an-audio-visual-dataset-for-active-speaker-detection/) — active speaker detection dataset and real-time audio-visual model.

[9] [A lightweight approach to real-time speaker diarization: from audio toward audio-visual data streams](https://link.springer.com/article/10.1186/s13636-024-00382-2) — real-time audio and audio-visual diarization design.

[10] [Target Speech Diarization with Multimodal Prompts](https://arxiv.org/abs/2406.07198) — target diarization with pre-enrolled speech and pre-registered face image prompts.

[11] [Sequence-to-Sequence Neural Diarization with Automatic Speaker Detection and Representation](https://arxiv.org/abs/2411.13849) — speaker-embedding buffer for online/offline diarization.

[12] [DiarizationLM](https://arxiv.org/abs/2401.03506) — LLM as post-processing for ASR + diarization outputs.

[13] [LLM-based speaker diarization correction](https://arxiv.org/abs/2406.04927) — generalizable LLM diarization correction and ASR dependency limitations.

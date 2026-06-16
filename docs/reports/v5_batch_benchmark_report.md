# AliMeeting Speaker Diarization Benchmark — Phase 2 Report

> **Date**: 2026-04-22  
> **Dataset**: AliMeeting Eval (8 recordings, 252 min, 2-4 speakers)  
> **Method**: Stratified random sampling → 120 segments screening (6 models) → full 482 segments validation (top 3)  
> **Repo**: `alimeeting-diarization-bench/`

---

## 1. Executive Summary

对 6 个说话人分离（Speaker Diarization）模型进行了两阶段基准测试：

- **Phase A**：120 段分层随机采样，6 个模型横向对比
- **Phase B**：全量 482 段（完整 252 分钟数据集），对 Top 3 模型验证

**核心结论**：

- **PyAnnote 3.1** 以 DER 29.7%（全量）和说话人匹配率 96.7% 取得全面领先
- **Paraformer-v2**（DER 41.4%）和 **Fun-ASR**（DER 44.7%）位列二三，但 API 模型失败率较高
- 120 段采样对 PyAnnote 的代表性极好（DER 30.3% vs 29.7%，误差 <1%）
- 4 人会议是所有模型的共同难点，DER 普遍超过 39%
- 2 人场景下 PyAnnote 表现接近实用水平（DER 18.1%）

---

## 2. Experimental Setup

### 2.1 Dataset

| 录音 ID | 时长 | 说话人数 | 标注段数 |
|---------|------|---------|---------|
| R8009_M8020 | 31.8 min | 2 | 874 |
| R8009_M8018 | 27.6 min | 2 | 665 |
| R8009_M8019 | 32.9 min | 2 | 959 |
| R8008_M8013 | 37.3 min | 3 | 732 |
| R8003_M8001 | 34.5 min | 4 | 674 |
| R8007_M8010 | 30.9 min | 4 | 1181 |
| R8007_M8011 | 31.0 min | 4 | 768 |
| R8001_M8004 | 26.2 min | 4 | 604 |
| **Total** | **252.3 min** | **2~4** | **6457** |

### 2.2 Sampling Strategy

分层随机采样（stratified random sampling），seed=42：

| 说话人数 | 录音数 | 分配段数 | 每段时长 |
|---------|--------|---------|---------|
| 2 人 | 3 | 45 | 30s |
| 3 人 | 1 | 15 | 30s |
| 4 人 | 4 | 60 | 30s |
| **合计** | **8** | **120** | — |

采样保证同一录音内段与段不重叠，覆盖录音不同时间段。

### 2.3 Models

| 模型 | 类型 | 运行方式 |
|------|------|---------|
| PyAnnote 3.1 | 开源 | 本地 MPS (Apple Silicon) |
| Fun-ASR (SOND) | 阿里云 | DashScope API |
| Paraformer-v2 | 阿里云 | DashScope API |
| Qwen3.5-Omni-Plus | 阿里云 | DashScope API |
| Qwen3-ASR-Flash | 阿里云 | DashScope API |
| GPT-4o Audio | OpenAI | OpenAI API |

### 2.4 Metrics

- **DER** (Diarization Error Rate) = Miss + False Alarm + Confusion，collar=0s
- **说话人匹配率**: 预测说话人数 == 真实说话人数的比例
- **CER** (Character Error Rate): 转写准确率
- **Latency**: 单段推理耗时

---

## 3. Phase A Results (120-Segment Screening)

### 3.1 Overall Ranking

| Rank | Model | DER (%) | Median DER (%) | Spk Match (%) | Latency (s) | N |
|------|-------|---------|----------------|---------------|-------------|---|
| 🥇 | **PyAnnote 3.1** | **30.3** | **27.6** | **99.2** | 2.7 | 120 |
| 🥈 | **Paraformer-v2** | **38.4** | **34.0** | 53.4 | 5.2 | 116 |
| 🥉 | **Fun-ASR** | **39.4** | **34.8** | 46.7 | 4.7 | 107 |
| 4 | Omni-Plus | 43.8 | 42.8 | 53.3 | 11.7 | 120 |
| 5 | GPT-4o Audio | 61.8 | 60.1 | 46.7 | 5.7 | 120 |
| 6 | ASR-Flash | N/A | N/A | 0.0 | 1.0 | 120 |

> ASR-Flash 无说话人识别能力（返回空段），DER 无法计算。

### 3.2 DER by Speaker Count (120-Segment)

| Model | 1-spk | 2-spk | 3-spk | 4-spk |
|-------|-------|-------|-------|-------|
| PyAnnote 3.1 | 5.7% | **20.8%** | **31.3%** | **41.7%** |
| Paraformer-v2 | 11.8% | 29.5% | 44.8% | 47.0% |
| Fun-ASR | **8.4%** | 31.9% | 35.9% | 49.3% |
| Omni-Plus | 6.2% | 35.7% | 35.9% | 60.5% |
| GPT-4o Audio | 26.8% | 64.1% | 60.0% | 64.6% |

### 3.3 Speaker Count Match Rate by Group

| Model | 1-spk | 2-spk | 3-spk | 4-spk |
|-------|-------|-------|-------|-------|
| **PyAnnote 3.1** | **100%** | **100%** | **100%** | **97.8%** |
| Paraformer-v2 | 83.3% | 92.9% | 47.8% | 15.6% |
| Fun-ASR | 100% | 90.6% | 44.0% | 13.0% |
| Omni-Plus | 100% | 71.4% | 61.5% | 26.1% |
| GPT-4o Audio | 83.3% | 97.6% | 26.9% | 6.5% |

**关键发现**：PyAnnote 是唯一在 3-4 人场景下仍能准确识别说话人数的模型。

### 3.4 DER Error Decomposition

| Model | Miss (%) | FA (%) | Confusion (%) |
|-------|----------|--------|---------------|
| **PyAnnote 3.1** | **8.9** | **7.0** | **14.4** |
| Fun-ASR | 29.5 | 5.7 | 4.2 |
| Paraformer-v2 | 27.9 | 6.9 | 3.6 |
| Omni-Plus | 35.1 | 5.0 | 3.6 |
| GPT-4o Audio | 32.7 | 8.6 | 20.6 |

**分析**：
- PyAnnote 的 Miss 最低（8.9%），但 Confusion 较高（14.4%）
- DashScope 系列模型（Fun-ASR、Paraformer-v2、Omni-Plus）的 Confusion 很低（~4%），但 Miss 很高（28-35%），说明存在大量漏检
- GPT-4o 的 Confusion 最高（20.6%），说话人混淆严重

### 3.5 Per-Recording Results (Top 3, 120-Segment)

| Recording | Speakers | PyAnnote DER% | Fun-ASR DER% | Paraformer-v2 DER% |
|-----------|----------|---------------|--------------|-------------------|
| R8009_M8019 | 2 | **8.6** | 21.9 | 22.4 |
| R8009_M8018 | 2 | **13.0** | 21.6 | 22.0 |
| R8009_M8020 | 2 | **14.9** | 15.6 | **18.6** |
| R8008_M8013 | 3 | **32.2** | 40.2 | 54.6 |
| R8007_M8011 | 4 | **35.0** | 38.2 | 32.3 |
| R8001_M8004 | 4 | **35.1** | 47.7 | 48.4 |
| R8007_M8010 | 4 | **45.3** | 57.5 | 57.9 |
| R8003_M8001 | 4 | 58.4 | 55.4 | **52.9** |

---

## 4. Phase B Results (Full-Dataset Validation, 482 Segments)

基于 Phase A 排名，对 Top 3 模型进行全量 482 段测试（覆盖完整 252 分钟数据集），验证采样结果的代表性。

### 4.1 Full-Dataset Overall Ranking

| Rank | Model | DER (%) | Median DER (%) | Spk Match (%) | Latency (s) | N (ok/total) |
|------|-------|---------|----------------|---------------|-------------|-------------|
| 🥇 | **PyAnnote 3.1** | **29.7** | **31.8** | **96.7** | 3.3 | 482/482 |
| 🥈 | **Paraformer-v2** | **41.4** | **35.8** | 19.0 | 8.0 | 100/482 |
| 🥉 | **Fun-ASR** | **44.7** | **46.4** | 13.9 | 5.0 | 151/482 |

> ⚠️ API 模型存在较多失败段：Paraformer-v2 仅 100/482 成功（79% 失败），Fun-ASR 仅 151/482 成功（69% 失败）。PyAnnote 本地运行 482/482 全部成功。

### 4.2 Sampling vs Full-Dataset Comparison

| Model | 120-Segment DER% | Full-Dataset DER% | Delta | 采样代表性 |
|-------|-----------------|-------------------|-------|-----------|
| PyAnnote 3.1 | 30.3% | **29.7%** | -0.6% | ✅ 极好 |
| Paraformer-v2 | 38.4% | **41.4%** | +3.0% | ⚠️ 偏差较大 |
| Fun-ASR | 39.4% | **44.7%** | +5.3% | ⚠️ 偏差较大 |

**分析**：
- PyAnnote 的 120 段采样与全量结果高度一致（误差 <1%），说明分层采样策略有效
- API 模型全量 DER 偏高，主要原因是大量失败段导致可用数据不均衡（成功段可能集中在特定录音）

### 4.3 DER by Speaker Count (Full-Dataset)

| Model | 1-spk | 2-spk | 3-spk | 4-spk |
|-------|-------|-------|-------|-------|
| **PyAnnote 3.1** | **5.9%** | **18.1%** | **34.3%** | **39.5%** |
| Paraformer-v2 | — | 65.4% | 20.7% | 45.8% |
| Fun-ASR | 4.8% | 59.8% | 29.2% | 47.3% |

> Paraformer-v2 无 1-spk 成功段；API 模型在 2-spk 场景下全量 DER 显著高于采样值。

### 4.4 Speaker Count Match Rate (Full-Dataset)

| Model | 1-spk | 2-spk | 3-spk | 4-spk |
|-------|-------|-------|-------|-------|
| **PyAnnote 3.1** | **100%** | **99.4%** | **97.0%** | **93.7%** |
| Paraformer-v2 | — | 50.0% | 27.3% | 13.9% |
| Fun-ASR | 100% | 57.1% | 20.8% | 9.2% |

### 4.5 DER Error Decomposition (Full-Dataset)

| Model | Miss (%) | FA (%) | Confusion (%) |
|-------|----------|--------|---------------|
| **PyAnnote 3.1** | **9.0** | **4.6** | **16.0** |
| Paraformer-v2 | 32.2 | 6.1 | 3.1 |
| Fun-ASR | 36.6 | 4.0 | 4.1 |

全量数据与采样趋势一致：PyAnnote 的 Miss 最低（9.0%），Confusion 偏高（16.0%）；API 模型 Miss 高、Confusion 低。

### 4.6 Per-Recording Results (Full-Dataset)

| Recording | Speakers | PyAnnote DER% | Fun-ASR DER% | Paraformer-v2 DER% |
|-----------|----------|---------------|--------------|-------------------|
| R8009_M8019 | 2 | **14.4** | — | — |
| R8009_M8018 | 2 | **13.6** | — | — |
| R8009_M8020 | 2 | **17.9** | — | — |
| R8008_M8013 | 3 | **35.3** | — | 20.7% (avg) |
| R8007_M8011 | 4 | **37.8** | 37.2 | 31.3 |
| R8001_M8004 | 4 | **34.3** | — | — |
| R8007_M8010 | 4 | **42.7** | 54.5 | 55.6 |
| R8003_M8001 | 4 | 40.6 | **38.4** | **33.9** |

> "—" 表示该录音无足够成功段。PyAnnote 全量覆盖所有 8 个录音，API 模型数据覆盖不完整。

---

## 5. Key Findings

### 5.1 PyAnnote 3.1 综合最优，全量验证稳健

- 全量 DER 29.7%，与采样 30.3% 高度一致（Δ -0.6%）
- 说话人匹配率 96.7%（全量 482 段），仅 16 段判断错误
- 482/482 零失败，本地 MPS 运行稳定
- 2 人场景 DER 18.1%，已接近实际应用水平

### 5.2 说话人数量是核心挑战

| 场景 | PyAnnote DER | 说明 |
|------|-------------|------|
| 2 人 | 18.1% | 接近实用 |
| 3 人 | 34.3% | 需要优化 |
| 4 人 | 39.5% | 显著困难 |

### 5.3 API 模型失败率是瓶颈

- Paraformer-v2：79% 段失败，仅 100/482 成功
- Fun-ASR：69% 段失败，仅 151/482 成功
- 可能原因：DashScope API 限流/超时，长音频处理不稳定
- 建议：对 API 模型增加重试机制和速率控制

### 5.4 模型差异化分析

| 维度 | 最优 | 最差 | 说明 |
|------|------|------|------|
| 整体 DER | PyAnnote (29.7%) | Fun-ASR (44.7%) | 差距 1.5x |
| 说话人计数 | PyAnnote (96.7%) | ASR-Flash (0%) | ASR-Flash 无此能力 |
| 稳定性 | PyAnnote (482/482) | Paraformer-v2 (100/482) | API 可靠性不足 |
| 漏检率 (Miss) | PyAnnote (9.0%) | Fun-ASR (36.6%) | PyAnnote 检测最完整 |
| 混淆率 (Conf) | Paraformer-v2 (3.1%) | PyAnnote (16.0%) | PyAnnote 偏混淆，API 偏漏检 |

### 5.5 ASR-Flash 不适用于说话人分离

ASR-Flash 返回空段列表，无法完成说话人分离任务。该模型仅做语音识别，不具备说话人聚类能力。

---

## 6. Reproducibility

```bash
# Phase A: 120 段采样测试（6 个模型）
python -m alimeeting_diarization_bench.run \
  --model pyannote \
  --sampling-mode stratified \
  --total-samples 120 \
  --seed 42 \
  --window-size 30

# Phase B: 全量 482 段测试（Top 3 模型）
python -m alimeeting_diarization_bench.run \
  --model pyannote \
  --sampling-mode stratified \
  --total-samples 504 \
  --seed 42 \
  --window-size 30

# 查看排名
python scripts/analysis/analyze_results.py ~/data/AliMeeting/batch_results_v2     # Phase A
python scripts/analysis/analyze_results.py ~/data/AliMeeting/batch_results_full   # Phase B
```

数据文件位置：
- Phase A 采样结果：`~/data/AliMeeting/batch_results_v2/{model}/results.csv`
- Phase B 全量结果：`~/data/AliMeeting/batch_results_full/{model}/results.csv`
- 模型对比 CSV：`{output_dir}/model_comparison.csv`
- Checkpoint（可断点续跑）：`{output_dir}/{model}/checkpoint.json`

# AliMeeting 说话人分离离线增强系统技术报告

## 1. 项目概述

本项目面向 AliMeeting 会议语音数据集中的说话人分离任务，目标是在现有强基线模型输出的基础上，构建一个可复现、可审计、默认离线运行的说话人分离增强系统。最终交付版本将核心运行逻辑整理为 Python package 模块，并提供一键 quick start、批处理、完整 regression、自检和结果审计能力。

当前提交的默认系统为：

```text
slow_guarded_fast_fallback_rare_audio_rule_recover
```

该系统不是重新训练一个单一模型，而是在 Fast/Slow 两类 diarization 输出之上增加离线增强层，包括 slow-first selector、安全 fallback、稀疏 rule-recover overlay、guard/quarantine gate 和完整评估审计。

## 2. 数据集

本项目使用的数据集为 AliMeeting。

最终离线复现实验使用：

- 数据集：AliMeeting
- 使用划分：AliMeeting Eval set
- 评估规模：8 条 Eval recordings
- 切窗数量：120 个窗口
- 窗口大小：30 秒
- 评估音频总量：3600.0 秒 cached-window audio

默认本地数据路径为：

```text
~/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir/
~/data/AliMeeting/AliMeeting_manifests/
```

离线复现路径不重新读取完整原始模型推理流程，而是使用仓库中保留的 cached model outputs 和 frozen artifacts。

## 3. 使用模型

核心提交系统使用两个主要 diarization 模型输出作为基础：

| 类型 | 模型 | 用途 | 当前 DER |
|---|---|---|---:|
| Fast baseline | Sortformer | 快速基础 diarization 输出 | 28.5637% |
| Slow baseline | DiariZen | 高质量基础 diarization 输出 | 16.8809% |
| Final system | Offline enhancement over Sortformer + DiariZen | 最终增强结果 | 16.4923% |

对应 cached summary：

```text
outputs/sortformer_uv_120/nemo-sortformer-4spk-v1/default__spk_none/summary.json
outputs/diarizen_uv_120/diarizen-large-v2/default__spk_none/summary.json
```

此外，benchmark package 中保留了以下模型适配器，用于扩展实验或重新评估：

- PyAnnote / PyAnnote Community
- Fun-ASR
- Paraformer v2
- ASR Flash
- Omni Plus
- GPT-4o audio adapter

默认交付系统不调用 live API，不依赖 DeepSeek、Qwen、Omni 或 GPT 的在线调用。

## 4. 方法设计

最终系统采用离线增强框架：

1. 使用 Sortformer 作为 Fast baseline，提供快速 diarization 结果。
2. 使用 DiariZen 作为 Slow baseline，提供更强的基础 diarization 结果。
3. 读取 frozen LLM/agent-prepared artifacts，包括 gates、guards、patch evidence 和 selector evidence。
4. 使用 slow-first selector 作为主路径，在安全条件满足时采用慢模型优势。
5. 使用 fast fallback 避免高风险修改。
6. 使用 sparse rule-recover overlay 修复少量高置信可恢复窗口。
7. 使用 guard/quarantine gate 阻止潜在有害更改进入最终 timeline。
8. 输出 final timeline、RTTM、CSV、JSON metrics、baseline comparison 和审计报告。

简化框架如下：

```text
AliMeeting audio
  -> Sortformer cached output
  -> DiariZen cached output
  -> Offline enhancement runtime
  -> Slow-first selector / safe fallback / rule recover / guard gate
  -> Final diarization timeline
  -> DER + baseline audits + timeline integrity + self-check
```

## 5. 系统实现

最终交付版本已模块化为 Python package。

核心代码位置：

```text
alimeeting_diarization_bench/
  run.py                         # 通用 benchmark CLI
  cli.py                         # installed command dispatcher
  final/                         # 最终离线系统模块
  models/                        # 模型适配器
  evaluation/                    # 评估逻辑
  metrics/                       # DER/CER 等指标
```

核心 final 模块包括：

| 模块 | 作用 |
|---|---|
| `final/quick_start.py` | 最短离线复现入口 |
| `final/realtime_system.py` | 最终离线增强系统 |
| `final/realtime_batch.py` | 批处理运行 |
| `final/regression.py` | 完整 29 步 regression |
| `final/self_check.py` | 系统自检 |
| `final/timeline_integrity.py` | timeline 完整性检查 |
| `final/search_*` / `final/audit_*` / `final/build_*` | selector、overlay、baseline、promotion gate 等验证模块 |

安装后提供命令：

```bash
alimeeting-quick-start
alimeeting-realtime
alimeeting-batch
alimeeting-regression
alimeeting-self-check
alimeeting-timeline-check
```

## 6. 实验结果

当前最终开发池结果如下：

| 指标 | 数值 |
|---|---:|
| Evaluation pool | 8 AliMeeting Eval recordings, 120 windows |
| Window size | 30 seconds |
| Final DER | 16.4923% |
| Fast baseline DER | 28.5637% |
| Slow baseline DER | 16.8809% |
| Best tracked baseline | slow_base |
| Margin vs best tracked baseline | +0.3886pp |
| Beats tracked same-window baselines | true, 5/5 |
| Miss / FA / Confusion | 5.2621% / 6.3883% / 4.8431% |
| Live API calls in default system | 0 |
| First-output latency proxy avg / p95 | 0.383s / 0.444s |
| Rule-writeback latency proxy avg / p95 | 24.65s / 28.33s |
| Processed cached-window audio | 3600.0s |
| Offline replay RTF | 0.000855 |
| Full system regression | pass, 29/29 |
| System self-check | warn, 40 pass / 4 warn / 0 fail |

结果说明：

- 最终系统 DER 为 16.4923%，优于当前 best tracked baseline `slow_base` 的 16.8809%。
- 相比 best tracked baseline，提升为 +0.3886pp。
- 默认系统 live API calls 为 0，说明交付复现路径为离线 replay。
- 完整 regression 通过 29/29。
- self-check 为 warn，不是 fail；warn 主要来自 promotion boundary，即目前仍缺少 sealed true-heldout split 和更强 recording-level robustness。

## 7. 与 Baseline 的区别

Baseline 是单一模型直接输出 diarization timeline。本项目最终系统是一个增强框架：

| 方面 | Baseline | 本项目 |
|---|---|---|
| 输入 | 单模型输出 | Sortformer + DiariZen cached outputs |
| 核心方法 | 直接 timeline | selector + fallback + rule recover + guard |
| LLM 参与方式 | 无 | 离线准备 gates/guards/patch evidence |
| 默认运行是否调用 API | 不适用 | 0 live API calls |
| 风险控制 | 通常无 | guard/quarantine gate |
| 复现方式 | 依赖重新推理或缓存 | cached outputs + frozen artifacts |
| 验证方式 | DER 为主 | DER + baseline audits + timeline integrity + self-check + promotion gate |

## 8. 复现方式

进入项目目录：

```bash
cd /Users/haojiang/Documents/2026/school/AI+/alimeeting-diarization-bench-final
```

安装为本地可编辑包：

```bash
python -m pip install -e .
```

最短复现：

```bash
alimeeting-quick-start
```

预期输出包含：

```text
final DER: 16.4923%
margin vs best baseline: 0.3886pp
live API calls: DeepSeek=0, Qwen=0, Omni=0
```

完整验收：

```bash
alimeeting-regression
```

预期结果：

```text
status=pass steps=29/29 final=16.49% self_check=warn
```

## 9. 交付内容

最终交付目录包括：

- `README.md`：完整复现说明、模型/数据集、指标和架构说明。
- `TECHNICAL_REPORT.md`：本技术报告。
- `SUBMISSION_MANIFEST.md`：交付清单。
- `pyproject.toml`：package 和命令注册。
- `alimeeting_diarization_bench/`：最终代码包。
- `outputs/`：复现所需 cached outputs、metrics、audit reports 和 PPT。
- `outputs/final_effect_presentation.pptx`：最终展示 PPT。

已删除开发期散脚本、旧报告草稿和无关 exploratory artifacts，交付版本只保留最终复现与评估所需内容。

## 10. 局限性

当前结果是 development-pool result，不应直接表述为最终泛化结论。主要限制包括：

- 尚未完成 sealed true-heldout split 上的最终验证。
- selector robustness 和 recording-level stability 仍是 promotion gate 中的主要边界。
- 当前提升来自 cached candidate pool 和离线增强策略，后续若要进一步提高，需要引入新的 deployable candidate surface 或额外 heldout 数据验证。

因此，当前结论应表述为：

```text
在 AliMeeting Eval development-pool 的 8 条录音、120 个 30 秒窗口上，
最终离线增强系统 DER 达到 16.4923%，优于当前跟踪的 best baseline
slow_base 16.8809%，并可通过离线 quick start 与完整 regression 复现。
```

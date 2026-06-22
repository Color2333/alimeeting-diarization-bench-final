# 基于双基线融合与离线安全增强的 AliMeeting 说话人分离系统

## 摘要

会议语音中的说话人分离任务旨在回答“谁在什么时候说话”，是会议转写、纪要生成和多人语音理解系统中的关键前处理环节。现有说话人分离模型通常可以直接输出时间轴，但在复杂会议场景中仍容易受到重叠语音、短说话片段、边界偏移和误检片段的影响。针对这一问题，本文基于 AliMeeting 数据集构建了一个默认离线运行的说话人分离增强系统。系统不重新训练单一模型，而是在 Sortformer 快速基线和 DiariZen 高质量慢速基线的基础上，引入 slow-first selector、安全 fallback、稀疏 rule-recover overlay、guard/quarantine gate 以及完整的离线审计流程，从而在保证可复现和可追踪的前提下改善最终 DER 表现。

在 AliMeeting Eval development-pool 的 8 条录音、120 个 30 秒窗口上，本文系统最终 DER 为 16.4923%，优于当前跟踪的 best baseline `slow_base` 的 16.8809%，相对提升 0.3886 个百分点；同时优于当前跟踪的 5 个同窗口 baseline。默认交付路径不调用在线 API，live API calls 为 0，并通过 29/29 步完整 regression 验证。实验表明，在强基线已经较优的情况下，通过受控的离线增强框架仍可获得稳定、可审计的性能收益。

**关键词**：说话人分离；AliMeeting；DER；离线增强；Sortformer；DiariZen；可复现评测

## 1. 引言

随着在线会议和远程协作场景的普及，会议语音理解系统需要同时处理多人发言、轮流打断、语音重叠和长时段上下文等问题。说话人分离是其中的基础任务，其目标是将一段会议语音切分为若干带有说话人标签的时间片段。若说话人分离结果出现大量混淆或边界错误，后续的 ASR、会议摘要、角色归因和行动项抽取都会受到影响。

传统评测中，系统通常以单一模型的 diarization timeline 作为最终输出，并使用 DER（Diarization Error Rate）衡量错误率。然而，在真实会议语音中，不同模型往往具有不同优势：快速模型推理成本低、响应快，但容易在复杂片段上出错；慢速高质量模型整体更稳，但也可能在局部边界或短片段上产生不必要修改。因此，本项目的核心思路不是盲目替换基线模型，而是将多个基线输出纳入统一增强框架，利用离线证据和安全门控进行有约束的选择与修正。

本文工作主要贡献如下：

1. 构建了面向 AliMeeting 的模块化说话人分离 benchmark package，提供 quick start、批处理、regression、自检和审计入口。
2. 设计了基于 Sortformer 与 DiariZen 双基线输出的离线增强框架，在强慢速基线之上继续降低 DER。
3. 引入 guard/quarantine gate 与 offline frozen artifacts，使最终系统默认不依赖在线 LLM/API 调用，同时保留可审计的增强证据链。
4. 给出完整可复现实验结果、baseline 对比、实时性参数和最终交付说明。

## 2. 任务定义与数据集

本文研究任务为会议语音说话人分离。给定一段多人会议音频，系统需要输出若干时间片段，每个片段包含开始时间、结束时间和说话人标签。评测指标采用 DER，其误差主要由 Miss、False Alarm 和 Confusion 三部分组成。

实验数据来自 AliMeeting 数据集。最终离线复现实验使用 AliMeeting Eval set 中的 8 条录音，并按 30 秒窗口组织为 120 个评估窗口。评估音频总量为 3600.0 秒 cached-window audio。默认本地数据路径如下：

```text
~/data/AliMeeting/Eval_Ali/Eval_Ali_far/audio_dir/
~/data/AliMeeting/AliMeeting_manifests/
```

需要说明的是，当前结果定位为 development-pool result。也就是说，本文结论严格限定在当前 AliMeeting Eval development-pool 与当前冻结的同窗口评估配置上，不将其夸大为未知数据上的最终泛化结论。

## 3. 系统框架

最终系统名为：

```text
slow_guarded_fast_fallback_rare_audio_rule_recover
```

系统整体框架可概括为：先读取 Sortformer 与 DiariZen 的 cached diarization outputs，再读取离线冻结的 gates、guards、patch evidence、selector evidence 等增强证据，随后由 runtime 按照 slow-first selector、safe fallback、rule recover 和 guard gate 的顺序生成最终 timeline，最后输出 RTTM、CSV、JSON metrics、baseline comparison 和审计报告。

简化框架如下：

```text
AliMeeting Eval audio/windows
        |
        v
+---------------------+        +---------------------+
| Sortformer baseline |        | DiariZen baseline   |
| fast cached output  |        | slow cached output  |
+----------+----------+        +----------+----------+
           |                              |
           +---------------+--------------+
                           |
                           v
          +---------------------------------------+
          | Offline enhancement runtime           |
          | slow-first selector                   |
          | safe fast fallback                    |
          | sparse rule-recover overlay           |
          | guard / quarantine gate               |
          +-------------------+-------------------+
                              |
                              v
          +---------------------------------------+
          | Final diarization timeline            |
          | RTTM / CSV / metrics / audit reports  |
          +---------------------------------------+
```

与常规单模型 baseline 相比，本文系统的核心区别在于：baseline 只给出单一路径输出，而本文框架同时维护快速输出、高质量输出和离线增强证据，并通过门控策略决定哪些修改可以进入最终结果。这种设计牺牲了一部分系统复杂度，但换来了更强的可审计性和风险控制能力。

## 4. 方法设计

### 4.1 双基线输入

系统使用两个主要 diarization 模型作为基础输出来源：

| 类型 | 模型 | 作用 | 当前 DER |
|---|---|---|---:|
| Fast baseline | Sortformer | 快速基础 diarization 输出 | 28.5637% |
| Slow baseline | DiariZen | 高质量基础 diarization 输出 | 16.8809% |
| Final system | Offline enhancement over Sortformer + DiariZen | 最终增强输出 | 16.4923% |

Sortformer 提供快速响应能力，适合作为实时性或 fallback 路径参考；DiariZen 作为慢速强基线，整体 DER 明显低于 fast baseline。因此最终系统采用 slow-first 策略，即默认尊重慢速强基线的整体优势，但不无条件接受所有局部修改。

### 4.2 离线 LLM/Agent 证据注入

项目早期探索过 LLM 或 agent 参与策略搜索、patch evidence 生成与规则整理。最终交付版本没有在运行时调用在线 LLM，而是将相关结果冻结为本地 artifact。也就是说，LLM/agent 的作用被放在离线准备阶段，形成 gates、guards、patch evidence 和 selector evidence；最终系统运行时只读取这些冻结文件，不发起 DeepSeek、Qwen、Omni 或 GPT 在线调用。

这种设计的好处是复现路径更稳定，也更适合课程交付：评测结果不会因为外部 API 变化、网络状态或模型版本漂移而改变。对应指标中，默认系统 live API calls 为 0。

### 4.3 Selector、Fallback 与 Guard

最终增强层包含三个关键机制。

第一，slow-first selector。该模块优先选择 DiariZen 输出作为主路径，因为其整体 DER 明显优于 Sortformer。selector 的目标不是在每个窗口上频繁切换模型，而是在确保整体稳定性的前提下保留慢速基线优势。

第二，safe fast fallback。当某些窗口或片段存在较高风险时，系统允许回退到 fast baseline 或原始安全输出，避免离线增强层引入有害修改。fallback 的作用不是追求激进提升，而是控制最坏情况。

第三，guard/quarantine gate。rule-recover overlay 只允许少量高置信、可解释的修正进入最终 timeline；若修改缺少足够证据，或可能破坏 timeline 完整性，则会被 guard 阻止或隔离。该机制使系统不仅关注 DER 数值，也关注提交结果是否可解释、可追踪、可复查。

## 5. 系统实现与可复现入口

最终代码已整理为 Python package，而不是散落脚本。核心目录如下：

```text
alimeeting_diarization_bench/
  run.py
  cli.py
  final/
  models/
  evaluation/
  metrics/
```

其中 `alimeeting_diarization_bench/final/` 保存最终交付系统的 quick start、realtime runtime、batch、regression、自检、timeline 检查、baseline audit 和 promotion gate 等模块。安装后可使用以下命令：

```bash
alimeeting-quick-start
alimeeting-realtime
alimeeting-batch
alimeeting-regression
alimeeting-self-check
alimeeting-timeline-check
```

最短复现流程为：

```bash
cd /Users/haojiang/Documents/2026/school/AI+/alimeeting-diarization-bench-final
python -m pip install -e .
alimeeting-quick-start
```

完整验收流程为：

```bash
alimeeting-regression
```

当前 regression 结果为 `pass`，通过 29/29 步验证。

## 6. 实验设置

本文实验使用 frozen cached outputs 与 frozen artifacts 进行离线 replay。这样做的目的不是规避模型推理，而是保证交付版本在不同机器上能够稳定复现同一组结果。实验设置如下：

| 项目 | 设置 |
|---|---|
| 数据集 | AliMeeting |
| 划分 | Eval set development-pool |
| 录音数量 | 8 条 |
| 评估窗口 | 120 个 |
| 窗口大小 | 30 秒 |
| 评估音频总量 | 3600.0 秒 |
| 主指标 | DER |
| 分项指标 | Miss / FA / Confusion |
| 默认在线 API 调用 | 0 |

为评价实时性，系统报告两类参数：first-output latency proxy 与 rule-writeback latency proxy。前者衡量系统产生首个输出的延迟代理指标，后者衡量规则回写路径的延迟代理指标。当前 first-output latency proxy 平均值为 0.383 秒，p95 为 0.444 秒；rule-writeback latency proxy 平均值为 24.65 秒，p95 为 28.33 秒。离线 replay RTF 为 0.000855。

## 7. 实验结果与分析

最终结果如下：

| 指标 | 数值 |
|---|---:|
| Final DER | 16.4923% |
| Fast baseline DER | 28.5637% |
| Slow baseline DER | 16.8809% |
| Best tracked baseline | slow_base |
| Margin vs best tracked baseline | +0.3886pp |
| Beats tracked same-window baselines | true, 5/5 |
| Miss / FA / Confusion | 5.2621% / 6.3883% / 4.8431% |
| Live API calls | 0 |
| Full system regression | pass, 29/29 |
| System self-check | warn, 40 pass / 4 warn / 0 fail |

从结果看，Sortformer fast baseline 的 DER 为 28.5637%，适合作为快速路径，但在当前评估池中与最终系统存在明显差距。DiariZen slow baseline 的 DER 为 16.8809%，已经是较强基线。最终系统在该强基线上进一步降低到 16.4923%，提升幅度为 0.3886 个百分点。

该提升幅度从绝对值看并不夸张，但在强基线场景下具有实际意义。原因在于，当 baseline DER 已经低于 17% 时，剩余错误往往集中在复杂边界、短时片段和局部混淆中，简单替换模型或激进规则容易造成负收益。本文框架通过稀疏、受控、可回退的增强方式，仅允许高置信修改进入最终 timeline，因此能够在保持风险可控的情况下获得小幅但可复现的提升。

self-check 状态为 `warn`，不是 `fail`。warn 主要来自 promotion boundary：当前仍缺少 sealed true-heldout split 上的最终验证，且 selector robustness 与 recording-level stability 仍需要在更大范围数据上继续确认。因此，本文不将结果表述为通用最优，而是表述为在当前 AliMeeting Eval development-pool 与当前同窗口 baseline 集合上优于所有已跟踪 baseline。

## 8. 与 Baseline 的区别

本文系统与 baseline 的差异可以从输入、运行方式、风险控制和验证方式四个方面理解。

| 方面 | Baseline | 本文系统 |
|---|---|---|
| 输入 | 单模型输出 | Sortformer + DiariZen cached outputs |
| 决策方式 | 直接使用模型 timeline | selector + fallback + rule recover |
| LLM 参与 | 无 | 离线准备证据，运行时不调用 API |
| 风险控制 | 通常较少 | guard/quarantine gate |
| 默认复现 | 依赖模型推理或缓存 | cached outputs + frozen artifacts |
| 验证 | DER 为主 | DER + baseline audit + timeline integrity + self-check |

因此，本文最终框架不是“再跑一个模型”，而是一个围绕强基线输出构建的离线增强与审计系统。它的重点在于让每一次性能提升都能被复现、被解释，并且在 regression 中被持续验证。

## 9. 可交付物

最终交付包包含以下内容：

- `README.md`：完整启动说明、模型与数据集说明、指标、架构和复现步骤。
- `PAPER.md`：本文小论文正文。
- `TECHNICAL_REPORT.md`：技术报告，便于快速检查系统实现和指标。
- `SUBMISSION_MANIFEST.md`：交付清单。
- `DOWNLOAD_MANIFEST.md`：外部数据、模型和依赖检查清单。
- `pyproject.toml` 与 `requirements.txt`：包安装与依赖说明。
- `alimeeting_diarization_bench/`：最终 Python package 代码。
- `outputs/`：复现所需 cached outputs、metrics、审计报告和最终 PPT。
- `outputs/final_effect_presentation.pptx`：最终展示 PPT。

交付版本已经移除开发期散脚本、旧草稿和无关 exploratory artifacts；保留内容围绕最终复现、评估、审计和展示组织。

## 10. 局限性与后续工作

本文系统仍有三点限制。

第一，当前实验属于 development-pool result。虽然系统在当前跟踪的同窗口 baseline 上取得最优结果，但仍需要 sealed true-heldout split 验证其泛化能力。

第二，selector robustness 仍需增强。当前 selector 与 guard 已经可以避免明显有害修改，但如果未来引入更多 candidate surface，需要继续扩展对异常窗口、录音级别漂移和边界偏移的诊断。

第三，当前性能提升依赖 frozen cached outputs 与 offline artifacts。该设计有利于交付复现，但如果要进一步提升上限，需要重新引入可部署的新候选来源，例如更强的模型输出、更细粒度的音频特征或经过 heldout 验证的规则搜索。

## 11. 结论

本文面向 AliMeeting 会议语音说话人分离任务，构建了一个基于双基线融合与离线安全增强的最终交付系统。系统以 Sortformer 和 DiariZen 的 cached outputs 为基础，通过 slow-first selector、safe fallback、sparse rule-recover overlay 和 guard/quarantine gate 生成最终 diarization timeline。实验结果显示，在 AliMeeting Eval development-pool 的 8 条录音、120 个 30 秒窗口上，最终 DER 达到 16.4923%，优于当前 best tracked baseline 的 16.8809%，并通过 29/29 步 regression 验证。

更重要的是，本文系统将性能指标、运行入口、离线缓存、审计报告和交付文档统一整理为可复现 package，使最终结果不只是一次实验记录，而是一个可以被老师或评审独立检查、启动和复核的完整交付版本。

## 参考资料

[1] AliMeeting 数据集及其会议语音说话人分离任务说明。

[2] Sortformer diarization model documentation and cached benchmark outputs.

[3] DiariZen diarization model documentation and cached benchmark outputs.

[4] pyannote.audio speaker diarization evaluation tools and DER protocol.

[5] 本项目 `README.md`、`TECHNICAL_REPORT.md`、`SUBMISSION_MANIFEST.md` 与 `outputs/` 中的离线评估报告。

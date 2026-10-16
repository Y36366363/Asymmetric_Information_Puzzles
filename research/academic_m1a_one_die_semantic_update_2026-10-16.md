# 第二次学术目标更新：一骰私有信息泄露语义实验

## 这次研究的问题

本次只检验一个具体问题：普通完整树审计能否发现 adapter 把对手私骰
错误地透露给行动者？如果不能，一份独立于 adapter 信息集划分的观察不变性
合同能否发现它？

执行前合同已在 commit `1d0f715` 冻结：正确模型和一个单点故障模型使用
完全相同的 chance、行动、转移和收益；故障模型只把信息集从
`(own_die, public_bids)` 改成 `(both_dice, public_bids)`。本实验无随机数、
无 LLM 调用，也没有根据结果调整门槛。

## 方法为什么能检查“谁知道什么”

合同枚举 58 个公开决策历史、每个历史的 6 种自己的骰子，以及对手骰子的
15 个无序取值对，共 5,220 对状态。每一对具有相同的行动者、自己的骰子和
公开叫骰历史，只改变规则规定不可见的对手骰子。

对每一对状态比较四项：是否终局、当前玩家、合法行动和 information-set key。
这些状态对来自可信规则合同，不能从待检查 adapter 自己的信息集反推；否则
一个已经泄露信息的 adapter 会自己宣称这些状态本来就不同，形成循环验证。

普通结构审计继续检查有限树、chance 概率、合法行动一致性和 perfect recall。
此外，正确与故障模型各自接受 sequence-form LP 求解和完整树独立最佳回应。
该内部求解只是演示“错误模型也能被正确求解”，不作为语义通过门槛。

## 实际结果

| 检查 | 正确模型 | 泄露对手骰子的模型 |
|---|---:|---:|
| 完整历史 | 4,141 | 4,141 |
| information sets | 348 | 2,088 |
| perfect recall | 通过 | 通过 |
| 普通结构审计 | 通过 | 通过 |
| 观察不变性状态对 | 5,220 | 5,220 |
| 语义违规 | 0 | 5,220 |
| 模型内部 exploitability | 0 | 0 |
| 玩家 0 的模型内部博弈价值 | 0.5 | 1.0 |

五项预先冻结的主要门槛全部通过。泄露模型的全部违规都只发生在
`information_set`，合法行动、当前玩家和终局状态没有变化，符合单点故障设计。
结构审计没有发现泄露；外部语义合同发现了全部 5,220 对违规。

故障模型自己的 LP 和独立 BR 都给出 exploitability 0，但这是双方都能看到
两颗骰子的另一个游戏。其价值从 0.5 变成 1.0，进一步说明错误的信息结构会
改变战略问题。独立 BR 不读取训练 regret，却仍与求解器共享这个错误 adapter，
所以“算法层独立”不能替代“规则语义层独立”。

## 这次新增的可复用机制

`audit_observation_invariance` 接收外部声明的状态对，检查观察、玩家和合法行动
是否保持不变。它不专属于骗子骰子；后续可以为 Goofspiel 的同时秘密行动、
Love Letter 的私牌与公开轨迹构造各自合同。合同生成仍需可信规则来源，目前
没有声称能够自动从自然语言得到正确合同。

实验 artifact 保存执行环境、冻结合同哈希、结构审计、语义反例、两个内部解
和解释边界。回归测试同时保留正确正控制与故障负控制，防止以后把“全部通过”
误写成语义机制成功。

## 本次结果没有证明什么

- 只检验了一个人工注入故障和一个小型游戏，尚未测自然产生的 LLM 建模错误。
- 人工观察合同本身可能写错；它需要与候选 adapter 分离的规则依据和审查。
- 5,220 对全部命中是因为故障直接写入每个信息集，不代表未来故障都有满覆盖。
- 故障模型内部 exploitability 0 不能转移到真实游戏，也不能认证运行时策略。
- 本次没有训练 CFR、RL 或自适应对抗器，没有改变任何游戏运行时标签。

## 建议的下一步

我建议先做一个很小的 GameSpec 观察字段切片：显式声明公共字段、每位玩家的
私有字段和 observation projection，并从该声明生成同类不变性义务。先要求它
在一骰上逐项复现本次人工合同，再原样横向接入 Goofspiel 的“玩家 1 不应看到
玩家 0 本轮待提交牌”故障。这样能检验的是机制复用，而不是再手写第二个检查器。

如果自动生成的合同与人工 reference 不一致，应先保留反例并修复表示层；不要
直接进入 LLM pilot。两类不同信息泄露都能被同一机制发现后，再设计 LLM 生成
GameSpec、结构反馈和语义反馈的配对实验。自适应对抗器 B 线继续保留，但应在
合法观察 schema 稳定后开展，否则历史学习器可能把泄露字段当成有效经验。

你在进入下一步前应能解释两点：perfect recall 为什么允许“记住本来不该知道的
信息”；以及为什么同一个错误 adapter 上的 solver 与独立 BR 一致，仍不能证明
原规则被求解。这两点是下一阶段设计 GameSpec observation 字段的直接依据。

## 文件与复现

- 冻结合同：`configs/one_die_private_information_semantic_audit_v1.json`
- 通用检查：`src/aip/core/semantic_audit.py`
- 一骰合同生成：`src/aip/puzzles/liars_dice/semantics.py`
- 执行脚本：`scripts/audit_one_die_private_information_semantics.py`
- 结果：`research/results/one_die_private_information_semantic_audit_2026-10-16.json`
- 回归测试：`tests/test_observation_semantics.py`

复现实验：

```bash
PYTHONPATH=src python scripts/audit_one_die_private_information_semantics.py
```

本次本地统一验证实际完成：535 项 Python 测试、7 条主张证据完整性检查、
worker/static 构建和 14 项浏览器测试全部通过。实验脚本另输出到临时路径重跑，
与保存 artifact 逐字节一致。远端 CI 状态须以本次实现提交后的 Actions 结果为准。

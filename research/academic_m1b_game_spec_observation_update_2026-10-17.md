# 第三次学术目标更新：GameSpec 观察字段切片与跨游戏复用

## 这次究竟检验了什么

本次把上一轮人工编写的一骰观察不变性合同，缩成一个很小、可组合的
GameSpec 组件：明确列出公共字段、每位玩家的私有字段，并由声明自动计算玩家
可见的 observation projection。通用生成器按照相同 projection 对决策世界分组，
再把组内仅隐藏字段不同的状态两两配对，形成外部观察不变性义务。

实验在实现前冻结于 commit `16aa32a`。最重要的停止规则是：一骰自动生成的
状态对必须与上一轮独立保留的 5,220 对人工 reference 逐项、同序一致；若有任意
不一致，就保存第一个反例并停止，不得进入 Goofspiel，更不得进入 LLM pilot。

## GameSpec 切片如何工作

一骰的声明是：`bids` 为公共字段，`die_0` 和 `die_1` 分别只属于对应玩家。
因此玩家 0 的 projection 是 `(bids, die_0)`，玩家 1 的 projection 是
`(bids, die_1)`。生成器不读取待检查 adapter 的 `information_set`；否则泄露模型
可以用自己的错误信息集把本应相同的世界拆开，造成循环验证。

Goofspiel 的同时秘密出牌用标准的顺序化表示：玩家 0 先提交一张牌，玩家 1
随后行动，但 `pending_player_0_card` 在揭示前是玩家 0 的私有字段。公开字段包括
阶段、双方剩余牌、剩余奖分牌和当前奖分牌。这个顺序只是扩展式表示，不代表
真实规则允许玩家 1 看到先提交的牌。

声明本身也采用 fail-closed 验证：玩家私有字段必须逐人声明；公共和私有字段
不能重叠；状态记录不能缺字段、多字段、重复字段或使用不可哈希值。生成义务的
输入仍来自可信、人工审阅的规则枚举，而不是候选 adapter 的信息集。

## 一骰 reference 门槛

自动枚举得到：

- 2,088 个决策世界；
- 348 个 observation groups；
- 5,220 对自动生成义务。

自动义务与人工 reference 的 5,220 对左右状态逐项完全相同，第一个不一致为
`null`。正确 adapter 仍为 0 违规；泄露对手骰子的故障 adapter 仍为 5,220 个
违规，且全部只发生在 `information_set`。因此表示层没有触发停止规则，才允许
执行横向实验。

这一比较不是“新代码和自己比较”。旧的手写函数仍被保留为独立 reference；
新生成器只接收字段声明和完整状态记录。回归测试直接比较两套函数输出的每一对
状态，未来任一侧发生漂移都会失败。

## Goofspiel 横向结果

四牌切片覆盖所有剩余 2–4 张牌的公开库存组合、每个当前奖分牌和每个合法的
玩家 0 待提交牌。计数可在运行前由组合数得到：

- 四张牌阶段：4 个公开组 × 每组 4 条记录，产生 `4 × C(4,2) = 24` 对；
- 三张牌阶段：192 个公开组 × 每组 3 条记录，产生 `192 × C(3,2) = 576` 对；
- 两张牌阶段：432 个公开组 × 每组 2 条记录，产生 `432 × C(2,2) = 432` 对。

合计 628 个 observation groups、1,456 条状态记录和 1,032 对义务，全部与预注册
数量一致。

| 检查 | 正确隐藏提交模型 | 玩家 1 看见待提交牌的故障模型 |
|---|---:|---:|
| 单轮结构历史数 | 85 | 85 |
| information sets | 8 | 20 |
| perfect recall | 通过 | 通过 |
| 普通结构审计 | 通过 | 通过 |
| 自动观察义务 | 1,032 | 1,032 |
| 语义违规 | 0 | 1,032 |

故障模型的 1,032 个违规仍全部只来自 `information_set`。这与一骰的“对手私骰
泄露”不是同一个字段或同一种游戏时序，却由同一个 GameSpec projection 与配对
生成器发现。因此本次提供的是一项机制复用证据，而不是第二个手写专用检查器。

## 结果的学术含义和边界

这一步支持一个受限主张：人工审阅的声明式观察字段切片，可以在两个结构不同的
小型游戏中生成独立于候选 adapter 的观察不变性合同，并拒绝两种结构上仍自洽的
私有信息泄露。

它没有证明以下内容：

- GameSpec 的人工声明天然正确；错误的可信声明仍会生成错误义务；
- LLM 能可靠地从自然语言生成 GameSpec；本次没有调用任何模型；
- 1,032 对 Goofspiel 检查认证了完整多轮策略或新的 GTO；现有精确动态 solver
  没有被替换或修改；
- 机制已经覆盖 chance 概率、收益函数、遗漏状态或所有时序错误；
- 自适应对抗器可以开始学习。若 observation schema 仍有泄露，学习器会把非法
  字段当成预测信号，历史越多反而可能越稳定地利用错误信息。

M1b 因而只是“观察语义子层完成”，不是整个可验证规则接口完成。payoff、chance、
terminal 和 action legality 仍需要各自的声明、故障注入与独立 reference。

## 下一步建议

下一次不应立即扩大游戏数。我建议先设计、不执行一个小型配对 LLM pilot：固定
规则、模型、提示、修复轮数与预算，比较“仅结构反馈”和“结构 + 本次语义反馈”。
主要终点应是完整的可信 reference 通过率，另报误认证率、拒绝率、修复次数和
成本；人工正确 GameSpec 作为 solver 上限。自然产生的错误必须与人工注入故障
分开报告。

在实际调用 LLM 前，还应先补一个很小的受限序列化格式和 compiler 边界，并为
payoff/chance 各放一个负控制。否则 pilot 失败时无法区分是观察声明、解析器、
收益、chance 还是 solver 的问题。B 线继续保留但维持 hold，至少等 observation
schema 的版本、字段来源和揭示时机全部稳定，再定义合法历史日志。

你现在应能复述三个关键点：projection 是“规则允许玩家看到什么”；义务生成器
只在相同 projection 的世界之间改变隐藏字段；结构审计和 perfect recall 只检查
模型内部自洽，不能判断该 projection 是否符合原规则。

## 文件与复现

- 预注册：`configs/game_spec_observation_slice_preregistration_2026-10-17.json`
- 通用字段切片：`src/aip/core/game_spec.py`
- 一骰声明与人工 reference：`src/aip/puzzles/liars_dice/semantics.py`
- Goofspiel 隐藏提交切片：`src/aip/puzzles/goofspiel/semantics.py`
- 实验脚本：`scripts/audit_game_spec_observation_slice.py`
- 结果：`research/results/game_spec_observation_slice_2026-10-17.json`
- 回归测试：`tests/test_game_spec_observation.py`

复现实验：

```bash
PYTHONPATH=src python scripts/audit_game_spec_observation_slice.py
```

# AIP 学术定位、证据审查与发展路线（2026-10-15）

本文依据用户提出的 AAMAS workshop → 长期 AAMAS 正会目标制定。它是研究路线，不是新实验预注册；具体模型调用、预算、统计方法和阈值须在各实验开始前另行冻结。审查基线为 `9ee7057`。本次不运行新的付费模型实验，不修改既有实验结论或运行时标签。

## 1. 建议的中心定位

**面向有限不完全信息博弈的、可验证的 LLM 辅助建模与策略求解方法。**

长期“通解”应理解为统一问题表示、求解路由、验证与失败诊断流程。初期可认证范围限定为有限、两人、零和或已正确转换的常和、perfect-recall 游戏。多人一般和、未知对手模型、连续空间和不完整规则需单独声明解决概念与保证，不能直接继承 CFR 的均衡结论。

推荐方法链：自然语言规则 → 有类型的 GameSpec → adapter → 语义/信息集审计 → matrix/DP/sequence-form/CFR 求解 → 独立 BR/数值误差验证 → 带作用域证据的结果或明确拒绝。

LLM 的首要职责是识别玩家、观察、行动、chance、收益和缺失假设，以及基于验证反馈修复模型。精确数值计算交由适用求解器。CFR 是这一框架的重要后端，而不是所有游戏唯一入口。已有停止时间矩阵、Goofspiel DP 和 sequence-form 应继续保留。

## 2. 当前已具备的研究资产

| 资产 | 代码或证据 | 能支撑的结论 | 当前边界 |
|---|---|---|---|
| 通用 sequence-form 编译 | `src/aip/core/sequence_form.py`、`tests/test_sequence_form.py` | 从满足声明与结构审计的 adapter 生成 realization-plan LP | adapter 仍主要人工编写；不能证明自然语言规则翻译正确 |
| 独立评估与策略绑定 | `src/aip/core/evaluation.py`、`tree_evaluation.py` | 报告 NashConv、exploitability、BR 和策略指纹 | 与 trainer 共用 adapter 时仍可能存在共同模型错误 |
| 精确与迭代交叉验证 | Kuhn、一骰、Goofspiel、E-Card、受限 Love Letter/Guess Who | 多种结构的有限规则实例有可复核解 | 不等于完整商业游戏或任意规则已求解 |
| LLM 中间量评分 | `src/aip/benchmark/value_decomposition.py` | prior、reach、posterior、value、action 可以独立评分 | oracle 提供 continuation/payoff 的计算实验不能当自主求解证据 |
| 正反实验历史 | 9/22 方法审计、9/28 fixed-policy 修订、10/7 Love Letter target 退役 | 可定位估计目标、输入信息与控制条件的问题 | 旧失败仍须保留；跨游戏迁移效果未被普遍确立 |
| 五骰观测机制 | 10/15 pilot 与 bounded confirmation | 固定 seed 下观测覆盖提升且训练轨迹隔离 | 单确认 seed；均衡质量略变差；没有渐近无偏性或更快收敛证明 |

9/28 的 Liar/Goofspiel fixed-policy v2 已通过输入明确的计算实验，不能只引用此前 9/27 的失败。10/7 四牌 Love Letter 在折叠获得顺序后，48 个行动后信息集的战略隐藏状态支持均为 1，已退役为 belief-update target；它仍可作为 later-chance 编译/求解对照。

五骰最新 bounded confirmation：coverage 26.61% → 32.67%，exploitability 0.100590 → 0.103625。它通过的是事先冻结的中间机制阈值，不是最终 ε-GTO 认证。10/14 全预算候选的 exploitability 为 0.040003，但覆盖验收失败且完整树审计未结束。

## 3. 必须优先弥补的问题

### A. 语义正确性和结构正确性尚未连通

perfect recall、合法概率、action consistency 可以在一个“错误但自洽”的模型内全部通过。例如把对手私牌错误地公开，可能产生更细且仍满足 perfect recall 的信息集。需要从独立规则合同导出 observation invariance 测试：只改变不可见状态，不应改变行动者看到的信息或其 information-set key。同时覆盖 payoff 符号、chance 多重计数、同时行动泄露和停止条件错误。

语义合同与评分器不能完全由同一模型输出生成。以人工审查/程序生成的可信规则规范及隐藏测试作为外部依据；自生成测试通过只算自洽证据。

### B. “独立”需要写清是哪一层独立

当前 BR 不读取训练 regret 是重要隔离，但与求解器共用 adapter 并不等于独立规则实现。增加解析小例、手算反例、第二实现或 OpenSpiel 的匹配规则对照，检查模型层的共同错误。浮点 LP 的 exact-in-model 与数值容差也应明确，不能等同于形式化实数证明。

### C. 覆盖比例不等于均衡误差

对于已知有限博弈和完整策略，准确的全局 BR 可直接量化 exploitability；每个信息集都被训练访问并非 ε-Nash 的必要条件。旧覆盖门槛是额外的工程/研究验收，历史失败判定照旧保留。未来报告分开列出：规则语义、结构完整性、数值求解误差、策略完整性、观测覆盖和运行时政策。

`exploitability = NashConv/2` 与 `maximum_unilateral_deviation_gain` 要区分：若声称每个玩家的偏离收益都不超过 ε，应检查后者；只检查 NashConv/2 ≤ ε，通常只能推出每人偏离收益 ≤ 2ε。命名不能代替保证说明。

### D. 当前“通过”大多是工程验收，尚非统计性非劣结论

一个新 seed 上满足差值阈值不能证明总体非劣。相同 seed 重跑是复现，不是独立样本。多个剂量、连续多轮探索仍需计入研究历史；提前写 JSON 也不等于可由外部核验的预注册时间戳。下一轮采用 pilot/confirmation 严格划分、执行前 Git commit/tag 或外部时间戳、冻结主要终点和 seed 集合，报告所有结果和置信区间。

### E. 观测机制的理论与成本证据不足

原平均策略累计与 post-update 额外 observation pass 混合后的估计目标应写成公式；需分析信息集入样概率、策略时点和归一化。每 epoch 的 chance 边际精确，并不能单独证明对自适应策略序列的平均策略估计无偏。

下一比较应包含相同总资源下的更多标准 MCCFR 迭代、非分层额外 observation、分层 observation；只比较相同 regret iterations 会给新方法更多计算。墙钟需同时报告训练、观察、BR 和内存，固定硬件。覆盖提高不足以推出效率提升。

### F. 统一验证入口遗漏研究测试

本次实际发现：`scripts/verify.py` 使用 unittest discovery，发现 342 项；pytest collection 为 523 项，差 181 项。仓库现有 workflow 主要检查静态构建并发布 Pages，未运行完整 Python 研究测试。下一工程里程碑应统一 pytest 入口及 CI、固定依赖环境，并区分单元测试、静态 artifact 回归与重新运行实验。

本次是审查与规划，没有顺带更改这些行为。历史“523 tests passed”说明当时 pytest 成功，不能自动推出统一 verify 入口或 CI 覆盖了相同测试。

## 4. 最小 workshop 论文

建议题目方向：**From Rules to Auditable Strategies: Verifying LLM-Assisted Imperfect-Information Game Models**。

核心问题：在固定资源下，基于语义合同与独立求解反馈的修复，是否提高新规则实例上的“正确建模且通过独立评估”的比例，并降低错误认证率？

冻结两类主要目标：一骰 stepwise Liar's Dice（隐藏类型、顺序挑战）与四牌 Goofspiel（同时隐藏承诺、公共库存）。Kuhn 为解析控制；E-Card 为 solver 退化/无差异控制；小 Love Letter 为 later-chance 编译验证，不强行当 belief-transfer 正控制。五骰与完整 Love Letter 为扩展研究，不让它们阻塞第一篇论文。

建议先定义一个受限声明式 GameSpec，避免一开始让 LLM 任意生成整套 Python。包括 players、chance law、observations、legal actions、transition、payoff、termination、solution scope、规则文本来源。参数化模板仍须支持真实的 payoff/chance/information 变化，而非只改游戏名字。

实验臂：

1. LLM 直接输出行动/策略（测决策效果，不要求它生成 adapter）。
2. LLM → GameSpec → solver，无验证反馈。
3. LLM → GameSpec → solver，仅语法与通用结构反馈。
4. 同样工具和修复预算，加语义/独立验证反馈（主方法）。
5. 人工正确 GameSpec → 相同 solver，作为求解上限与故障定位控制。

主要比较为 4 对 3，隔离语义验证的增量。模型固定，repair 次数、可访问规则、工具预算与总时间上限一致。把直接行动臂的决策指标单列，不能因它不输出 GameSpec 而判定建模失败。

主要终点建议为 held-out 实例上的端到端验证成功率：可信语义测试通过、策略合法且完整、独立 BR 达到预先声明误差、预算未超限。分母包括全部实例；超时、解析失败、拒绝均记录。并报告 false certification rate、覆盖—错误率曲线，防止“全部拒绝”获得虚假高可靠性。

次要指标：最终 oracle 上的 action regret/完整策略 exploitability、建模错误类型、修复次数、token/墙钟/内存成本、prior 与 policy-conditioned posterior 误差。有限次 LLM 动作抽样无法直接提供精确策略 exploitability；必须明确求得的完整行为策略还是有采样不确定性的估计。

验证集按结构/规则生成族划分，避免同一游戏仅换皮就称为 held-out transfer；可信 reference 与隐藏评测不给 agent。随机 payoff、chance 参数、行动重命名及单规则反事实变体用于检测记忆依赖，但不能单凭这些测试宣称排除训练污染。

先用 pilot 估计方差与失败率，再通过功效模拟冻结正式实例数、至少两个模型系列及每实例独立重复数。以基础规则实例/模板为 cluster 计算配对置信区间，重复调用不能冒充独立游戏。平局用 ε-optimal action set 评分。缺失对手策略时拒绝唯一 posterior 评分，或者显式提供 policy/reach 假设。

## 5. 里程碑与停走条件

| 阶段 | 交付物 | 进入下一阶段的依据 |
|---|---|---|
| M0：证据整理，约 1 周 | claim→artifact 索引、测试入口/CI 修复、术语和作用域表、环境锁定 | clean checkout 能重建选择的精确基准；历史负结果可追溯 |
| M1：可验证规则接口，约 1–2 周 | 两个现有游戏的 GameSpec、受限 compiler、语义合同、故障注入集 | 手工 reference 等价；关键泄露/payoff/chance 错误能被拒绝 |
| M2：LLM 建模 pilot，约 1–2 周 | 四个方法臂、修复日志、成本与失败分解 | 能定位 LLM 增量；如语义验证无增益则保留负结果并改写研究问题 |
| M3：前瞻确认，约 2–3 周 | 隐藏规则集、固定模型预算、时间戳预注册、多模型结果与区间 | 主终点可重复计算；不得按结果挑游戏/seed/阈值 |
| M4：写作与 artifact，约 1–2 周 | 论文、匿名复现包、单命令小样例、主图和限制说明 | 每一主张有证据；按具体 workshop 页数/匿名/归档要求准备 |

这是按依赖的工作量估计，不是保证工期。建议大部分工作投向 M0–M3；五骰可完成已冻结配对研究作为次线，但不能再成为无限追加观测剂量的主线。跨游戏战略记忆作为后续假设，待端到端方法稳定后加入，以免一篇同时证明建模、求解、记忆迁移三件事。

## 6. 正会升级的具体门槛

workshop 之后选择一个明确突破：具有语义保真约束的自动建模/修复方法，或有误差传播保证的求解与抽象流程，或多个真正 held-out 结构族上具有稳定收益的策略迁移。至少需更强基线、跨模型与规则族复现、足量独立样本、误认证分析与资源可扩展性证据。仅增加游戏数量、测试数量或再封装 CFR 不足以保证原创性。

若做理论，优先尝试受限 GameSpec 编译的观察/收益保持性质，以及在明确收益误差或策略近似假设下的证书组合；不要预先声称适用于任意 abstraction。LLM 应贡献可测的模型构建、路由或修复能力；人工正确模型交给经典 solver 的成绩必须单列。

## 7. 文献与投稿定位（本次核验）

- [OpenSpiel](https://arxiv.org/abs/1908.09453)：已有通用多游戏及算法基础设施；AIP 不能只以“统一平台”作为新颖性。
- [CFR 原论文](https://papers.nips.cc/paper_files/paper/2007/hash/08d98638c6fcd194a4b1e6992063e944-Abstract.html)：用其适用假设界定收敛保证；模拟/采样方法并不天然不科学或不准确。
- [Autoformalization of Game Descriptions using Large Language Models](https://arxiv.org/abs/2409.12300)：自然语言游戏形式化已有先例，需逐项比较语言范围、反馈类型和语义评估。
- [Steering Language Models with Game-Theoretic Solvers](https://arxiv.org/abs/2402.01704)：LLM 与博弈求解器结合已有研究，不能把工具组合本身当作首创。
- [GAMABench](https://arxiv.org/abs/2403.11807)、[GameBench](https://arxiv.org/abs/2406.06613)：多游戏 LLM 决策评测已存在；突出信息结构、独立证据及失败诊断。
- [AAMAS 2026 Strategic Explainability workshop](https://sites.google.com/view/se-aamas2026)：主题包含 LLM 将情境转成博弈模型，可作选 venue 的历史参考，不推定 2027 必定延续。
- [AAMAS 2027 main track](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-main-track/)：常规论文截止 2026-10-08；以当前日期已过。GAAI/GTEP 的定位取决于方法贡献，而非标题关键词。
- [AAMAS 2027 workshop call](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-workshops/)：10/29 是组织 workshop 的 proposal 截止，非作者论文截止；官方建议 workshop 论文截止 2027-01-24。具体 workshop CFP 决定最终安排、归档和后续扩展政策。

这些是定位起点，不是穷尽的 systematic review。临投稿再次核对来源与最接近方法，论文录用无法由路线本身保证。

## 8. 后续更新默认顺序

下一次更新首先执行 M0 的测试入口与证据索引，然后为一骰/Goofspiel建立 GameSpec 和语义错误测试。任何大额新 LLM 实验需先形成可审阅的实验合同；任何新的通过结论必须列出规则范围、被检验假设和未覆盖边界。既有五骰全预算预注册保持冻结且未执行，完整 Love Letter 继续维持未认证。

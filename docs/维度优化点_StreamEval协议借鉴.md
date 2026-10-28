# 维度优化点备忘：借鉴 StreamEval 协议

> 日期：2026-10-27  
> 范围：先只记与 **StreamEval** 相关的可优化点（当前对话结论）。  
> 主路径不变：评测输入仍是「提示词 + 生成视频 + 可选参考」的短 clip，**不上** StreamEval 整套交互流式会话调度。  
> 相关材料：`StreamEval/docs/evaluation.md`；本地仓 `StreamEval/`；总计划见 `视频评估方法持续调研计划.md`。

---

## 0. 「借鉴」含义（边界）

| 做 | 不做 |
|----|------|
| 借指标背后的**成功/失败定义**与**检查点出题形状** | 不整包复现 WebSocket 会话、按时释放输入 |
| 改 `facts` / checklist 题面，必要时旁路对照 | 不把 StreamEval Overall 直接当对外维度分 |
| 短 clip 上弱化实现「稳定段 / 目标–保护成对」 | 不做 15–300s 五层时长等权聚合 |

可借的核心指标形状：

| StreamEval 指标 | 可操作定义（摘要） |
|-----------------|-------------------|
| **Edit Success** | 在截止前目标属性变为期望状态且稳定；超时 / 改错对象 / 旧效果残留 = 失败 |
| **Preservation** | 检查点上，声明的非目标内容必须保持 |
| **Following** | 每个控制事件是否对指定目标执行了请求操作（机会成功率） |
| **Reference** | 参考生效检查点上，按外观属性逐项评分 |
| **Identity** | 相对初始化肖像的保真（可双裁判取低） |
| **A–V Sync** | 口型–音频相关与偏移窗口的规则化判定 |
| **Continuity** | 路径 / 物体持久 / 空间关系等探针 |

---

## 1. 优化点清单（按维度）

### 1.1 D14 编辑与可控生成（优先）

| 当前不足 | 可优化成什么 | 主要依据 | 落地方式 |
|----------|--------------|----------|----------|
| 「局部修改准确性」偏整体印象，缺「期望状态是否成立」的原子判据 | 检查题拆成：目标属性是否达到 `active_state`；是否在成片稳定段可见 | **StreamEval Edit Success**；旁路可对照 **IVEBench** 遵循维、**OmniVBench** 编辑轨 | 改 `facts`（强制 `edit_targets` / 期望状态）+ checklist 题面；小样本人工对齐后再考虑加权 |
| 「非目标区域保持」与「改对」未成对约束 | 每个编辑检查点同时答：目标通过？保护列表是否未改？ | **StreamEval Preservation**（`protected` 列表） | facts 增加 `protected`；清单两题或一题两栏；与 Edit Success 成对出现 |
| 无「稳定住」要求，闪一下也可能高分 | 短 clip 版：要求中后段连续若干秒（或抽帧子集）保持目标状态 | Edit Success 的 `stable_window` / `check_window` 思想 | 题面加「稳定呈现」；可选抽帧规则进 judge 协议（不必真 deadline 毫秒） |
| ArcFace / LPIPS / PSNR 只管身份与接缝，不管指令语义是否改对 | 数值组件保留；语义「改对」交给上述检查点 | StreamEval 不替代像素指标；**分工**：像素保真现有组件，语义保真借协议 | 文档与权重说明写清：组件 ≠ Edit Success |

**建议试点子项：** `local_edit_accuracy`、`non_target_preservation`（及有替换时的保持条款）。

### 1.2 D16 音视频同步

| 当前不足 | 可优化成什么 | 主要依据 | 落地方式 |
|----------|--------------|----------|----------|
| SyncNet 人相关不稳，口型分波动大 | 明确「规则化同步」对照，不单绑 SyncNet | StreamEval **A–V Sync** 的规则写法（相关阈值 + 偏移窗）；实现优先 **AVGen-Bench Sync 模块**、AV-HuBERT / Synchformer 等 | 学协议口径写旁路对照；**工程实现不依赖** StreamEval 跑通会话 |
| 动作音 / 环境音同步几乎纯清单 | 事件级「画面事件 ↔ 声音是否同窗」的题面更硬 | StreamEval 对事件窗口的写法；专项仍看 AVGen 等 | 先改 checklist（事件 + 时间窗）；自动指标另立项 |

**说明：** D16 以「借规则形态」为主；StreamEval 整套 A–V 流水线不作为第一复现目标。

### 1.3 D20 人物表演与情绪表达

| 当前不足 | 可优化成什么 | 主要依据 | 落地方式 |
|----------|--------------|----------|----------|
| 无数值组件；表情 / 视线 / 微动作 / 台词表演全靠清单 | 对「写明的表演指令」做成 Following 式是否题：该手势 / 视线 / 动作有没有做到 | **StreamEval Avatar Performance Following** | 出题时从 prompt 抽 `performance_controls`；每条控制一道题；emotion2vec 仍只覆盖语音情绪（D15），不与 D20 混用 |
| 情绪、表情、台词是否同一意图，缺一体约束 | 题面要求「语音情绪 + 表情 / 视线」同向（仍人工 / VLM） | Following + 现有 D20 子项结构 | 仅协议；客观一体指标仍缺口，不假装已有自动分 |

### 1.4 D12 / D4（参考与身份，旁路相关）

| 当前不足 | 可优化成什么 | 主要依据 | 落地方式 |
|----------|--------------|----------|----------|
| 参考条件是否「按属性」落地，题面有时偏笼统 | 参考生效时按外观属性检查点打分 | **StreamEval Reference**；本地已有 **OmniVBench** RF；**OpenS2V** 主体分 | r2va case：facts 列属性检查点；与 OmniV 清单对齐，不新开流式参考切换 |
| 身份保持 | 相对初始化 / 参考肖像的对照题（可取低分保守） | **StreamEval Identity**；现有 ArcFace | 题面与 ArcFace 并列说明；双裁判取低仅作可选试验 |

### 1.5 明确不靠 StreamEval 补的维（记一笔，避免误用）

| 维度 | 原因 | 若要优化应看 |
|------|------|----------------|
| D13 风格 | StreamEval 几乎无风格控制维 | CLIP/CSD、OmniV Style、CineTech 光色 |
| D15 音频内容 / 音质 | 非其主场 | DNSMOS / ECAPA / CLAP / AVGen 音质模块 |
| D17 异常「率 / 秒数」 | Stability 定义不同，且你们缺的是客观发生率与持续秒数 | TRAJAN、VBench-2.0、VMBench |
| D18 字幕 OCR | 不覆盖 | TextVBench / VTR 协议 + 现有 OCR CER |

---

## 2. 推荐落地顺序（仅 StreamEval 相关）

1. **D14**：facts 增加期望状态 + `protected`；改局部修改 / 非目标保持题面 → 小样本与人工对齐。  
2. **D20**：表演指令 Following 式检查题（无数值组件也可先上题面）。  
3. **D16**：用 A–V Sync 口径写清旁路对照需求；实现侧挂 AVGen 等，不绑 StreamEval 会话。  
4. **D12/D4**：参考属性检查点与 OmniV / OpenS2V 对齐（StreamEval Reference/Identity 作协议参考）。

每步符合总计划 §3：先精读判断 → **仅借鉴协议** 改题 / 挂维验证；不整包复现。

---

## 3. 依据项目速查

| 用途 | 项目 | 路径 / 备注 |
|------|------|-------------|
| 协议原文（Edit Success / Preservation / Following / Sync 等） | StreamEval | `StreamEval/docs/evaluation.md`；`evaluation/protocol/` |
| 指令编辑 case 示例（检查点形态） | StreamEval bench | `datasets/.../benchmark/v1/*/cases.jsonl` + `oracles.jsonl`（如 `sa.v1.001.instruction_edit`） |
| D14 开源对照（可复现优先于 StreamEval） | IVEBench | 计划 §1.3；编辑质量 / 遵循 / 保真 |
| D12–D14 参考生旁路 | OmniVBench | 本地已有调研报告 |
| D4/D12 主体一致 | OpenS2V-Eval | Nexus 等 |
| D16 同步实现对照 | AVGen-Bench 等 | Sync 模块；并联 SyncNet |

---

## 4. 后续增补约定

- 本文**只积累「借鉴 StreamEval」**的优化点；IVEBench、VideoScore2、FilmOps 等另开文档或在本文追加独立章节。  
- 某条优化完成试点后，在对应行补「状态：已改题 / 验证中 / 已采用 / 放弃」即可。

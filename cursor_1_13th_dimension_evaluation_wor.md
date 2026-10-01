# (1) 13th dimension evaluation workflow
_Exported on 2026/10/1 at GMT+8 13:36:37 from Cursor (3.22.12)_

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
你先梳理一下这个里面第13维度的评估工作流。然后写成说明文档输出在docs文件夹中。

---

**Cursor**

我先检查 `vgen_eval` 的目录结构、评估脚本和现有第 13 维度文档，再根据实际代码整理完整工作流并写入 `docs`。

现有文档描述了设计方案，但代码还需要逐层核对，尤其是 case 读取、清单缓存、评委调用、抽帧、CSD/FIRM/调色板和最终计分。我会以实际执行路径为主，并把“已实现”和“配置中声明但当前可能未接入”的部分区分开。

我会先以 `tools/vgen_eval` 的当前实现为准，核对第 13 维度从输入解析、清单生成、评委调用、数值组件到最终汇总的完整路径，然后在该目录的 `docs` 下新增一份可执行说明，并运行基础检查。文档会明确标注代码已实现的行为，以及旧设计文档与当前代码不一致的地方。

我会先核对第 13 维度从数据解析、清单生成、评委调用到数值组件和最终聚合的实际代码路径，再在 `tools/vgen_eval/docs` 下编写一份以当前实现为准的工作流说明，并标明与旧设计文档不一致或仍属条件性/降级行为的部分。完成后会做一次静态检查。

已核对第 13 类的主路径：`cases.py` 负责输入和素材解析，`checklist.py` 负责从需求生成冻结清单，`base.py` 负责评委答案、门槛和子项合成，`d13.py` 只接入四个数值组件。当前实现与旧表格的关键差异是：首尾帧永远不会作为 CSD 风格参考；没有合格的纯风格参考图时，风格准确性只使用清单分。接下来我会把这些实际行为整理成可直接执行的文档。

说明文档已经写入 `docs`，覆盖了输入解析、清单冻结、评委调用、四个实际数值组件、降级规则、缓存、结果字段、命令示例以及与旧说明的差异。就绪检查也已通过：第 13 类发现 15 个 case，但当前默认数据目录中没有待评视频，因此本次只验证了环境和服务状态，没有执行视频评测。

我会按之前的计划用项目虚拟环境完成语法检查，并顺带确认第 13 维度说明文档仍然符合 Markdown 公式和 Unix 换行约定。

系统虚拟环境实际位于 `tools/vgen_eval/.venv`，而不是项目根目录的 `.venv`。我已定位到正确解释器，接下来用它完成同一项编译检查。

完整目录编译误把 `tools/vgen_eval/.venv` 里的第三方包也递归进去了，当前只产生了第三方包的既有语法警告，并非项目代码错误。我会停止这次过宽检查，改为只编译评测源码，避免无关依赖拖延结果。

---

**User**

你已经完成了清单，后面的这些是在做什么？

---

**Cursor**

清单完成后，后续流程就是**真正看视频、计算指标并汇总分数**。清单本身只负责把需求转换成可执行的评测标准，还没有给视频打分。

流程如下：

1. **冻结清单**
   - 保存需求事实，例如目标风格、光照、目标颜色和参考图用途。
   - 生成门槛题和具体检查题。
   - 后续评测都使用这份缓存清单，避免每次重新出题导致标准变化。

2. **评委回答清单**
   - `evaluate` 阶段读取待评视频和清单。
   - 视觉评委查看视频抽帧，回答门槛题和视觉检查题。
   - 如果清单中出现音频或音视频题，则交给音频评委。
   - 每道题得到“是/否”或选项结果，并附带证据。
   - 门槛题失败时，该 case 会标记为 `invalid_gate_failed`，不进入有效平均分。

3. **运行第 13 类的数值组件**
   这些组件不负责出题，而是从视频中计算补充指标：

   - **CSD 参考风格相似度**：比较视频画面和合格风格参考图的相似程度，影响 `style_accuracy`。
   - **CSD 时间漂移**：检查视频不同镜头和时间段的风格是否稳定，影响 `style_persistence`。
   - **FIRM 世界一致性**：检查主体结构、动作和物理逻辑是否崩坏，影响 `style_content_compat`。
   - **palette match**：检查画面像素是否接近需求中的目标颜色，影响 `color_control`。
   - **lighting_control**：目前没有独立光照模型，只使用视觉评委对光照检查题的结果。

   缺少参考图、模型权重或输入时，对应组件会被标记为 `not_applicable`、`blocked` 或 `error`，剩余组件会重新归一化，而不是直接让整个 case 失败。

4. **合成子项分和维度分**
   - 清单题按权重计算通过率，再映射到 1–5 分。
   - 数值组件也映射到 1–5 分。
   - 每个子项按照配置权重合成。
   - 不适用或失败的组件被剔除，剩余权重重新归一。
   - 五个子项的平均值作为第 13 类总分。

5. **保存单 case 结果**
   结果写入：

   ```text
   outputs/runs/<run_name>/13_style_visual_control/<case_id>/
   ```

   其中包括：

   - `result.json`
   - 各评委结果
   - CSD、FIRM、调色板等组件结果
   - `full_score`
   - `comparable_score`
   - 参考图实际使用策略和缺失原因

6. **汇总多个 case**
   `score` 阶段只读取已经生成的 `result.json`，输出：

   ```text
   outputs/runs/<run_name>/per_case.jsonl
   outputs/runs/<run_name>/summary.json
   outputs/runs/<run_name>/summary.md
   ```

   它不会自动补生成视频、清单或缺失的评测结果。

所以可以简单理解为：

```text
需求
  ↓
checklist：确定“应该检查什么”
  ↓
evaluate：评委回答“视频是否做到”
  ↓
数值组件：计算风格、稳定性、颜色等指标
  ↓
result.json：得到单条 case 分数
  ↓
score：汇总所有 case
```

目前执行的 `check` 只是确认服务和依赖是否就绪；由于默认数据目录中没有待评视频，真正的 `evaluate` 和后续打分需要指定 `--videos-root` 和 `--run-name`。

第 13 维度评估工作流说明已写入 `tools/vgen_eval/docs/d13_style_visual_control_workflow.md`。文档涵盖从 case 解析、清单生成到视频评委、数值组件、分数合成和结果汇总的流程，并标明了当前未实现或有条件运行的功能。

已使用项目虚拟环境对第 13 维度相关的 Python 源文件完成语法检查；Markdown 公式定界符及换行格式检查也通过。

---

**User**

目前是不是会存在视频没有通过门槛，而没有得分的现象？

---

**Cursor**

是的。**如果任一门槛题被明确判为“不通过”，该视频会标记为 `invalid_gate_failed`，维度分为 `null`，不计入有效视频的平均分。** 汇总中仍会统计它，并计入 `invalid` 数量。

门槛题最多两道，检查视频是否具备基本可评条件，不是第 13 维度的质量评分。触发失败后，流程不会运行 CSD、FIRM 等数值组件；检查清单子项可能仍会记录，但不会产生维度总分。

```46:48:tools/vgen_eval/vgen_eval/scoring.py
def evaluate_gates(checklist: dict, answers: dict) -> dict:
    res = {g["id"]: is_correct(g, answers.get(g["id"])) for g in checklist.get("gates", [])}
    return {"passed": not any(v is False for v in res.values()), "gates": res}
```

需留意：代码是遇到**明确答错**才判门槛失败；未作答或答案无法判定不会被这段逻辑直接视为失败。

---

**User**

我希望每个视频都会有分数，应该怎么实现？分析一下，不要修改

---

**Cursor**

**可以改成每个进入评测的视频都有 1–5 分，但需要先定好“无法评测”时的计分规则。** 我建议门槛失败不再让总分为空，而是把门槛作为诊断信息保留，并按最低分处理。

目前的逻辑是：门槛题有明确错误答案时，跳过数值组件，再由评分函数返回 `score: null` 和 `invalid_gate_failed`。因此这种视频会被排除在有效均分之外。未回答或无法判定的门槛题则不会因此直接失败。```136:154:tools/vgen_eval/vgen_eval/dims/base.py
        gate = evaluate_gates(ctx.checklist, answers)
        ...
            comps = {} if (audio_failed or not gate["passed"]) else dict(self.components(ctx, sp))
            comps["checklist"] = checklist_component(ctx.checklist, answers, sp, cfg["scoring"])
            ...
        out = score_dimension(dim_cfg, results, cfg, gate=gate, audio_gate_failed=audio_failed)
```

```115:118:tools/vgen_eval/vgen_eval/scoring.py
    if gate is not None and not gate["passed"]:
        return {"score": None, "status": "invalid_gate_failed", "gate": gate, "subpoints": subpoint_results}
```

### 推荐的计分策略

- **门槛明确失败**：总分记为 `1`，保留失败的门槛题及原因；不再把视频排除出均分。通常也应给适用子项记 `1`，避免出现有总分但子项缺分的情况。
- **门槛通过**：按现有清单和数值组件正常计分。
- **门槛未回答或评委调用失败**：这是“评测结果不完整”，不应和视频质量差混为一谈。若要求任何情况下都必须有数值，可以采用最低分 `1` 作为保底分，同时标记 `evaluation_error` 或类似状态，供汇总时单独识别。

要注意汇总逻辑也要同步调整：现在 `score` 非空的视频会被计入 `valid`，而状态以 `invalid` 开头的又会计入 `invalid`。若只是给 `invalid_gate_failed` 补上 `score: 1`，同一条视频可能同时被算作有效和无效；状态名称及汇总口径需要一起设计。```137:147:tools/vgen_eval/vgen_eval/scoring.py
        valid = [r for r in rs if r["result"]["score"] is not None]
        ...
        entry = {"n": len(rs), "valid": len(valid),
                 "invalid": sum(1 for r in rs if r["result"]["status"].startswith("invalid")),
```

还有一个范围限制：这只能保证**已有视频文件并成功进入 `evaluate` 的 case** 有分数。缺视频、视频无法解码、没有清单而导致评测跳过的 case，还没有评测结果；如果也要求这些 case 有分数，就必须另外定义缺失或技术错误时的兜底规则。

因此核心决策是：把“门槛失败”视为视频质量最低档（推荐记 1 分），还是视为评测失败并采用单独的兜底分。前者最容易保证所有已评视频进入均分，但会把“视频不可评”和“视频质量很差”合并解释；后者保留了诊断区别，但汇总报告应同时展示分数和兜底状态。

---

**User**

是对可以读取，但是没有通过门槛的计为最低分，不是对于哪些视频损坏，无法去读取的可以不进行评测。再分析一下

---

**Cursor**

按这个口径，规则应是：**视频能正常读取，就一定产生分数；读不出来的视频跳过评测。** 门槛只决定可读取视频是否按正常流程评分，还是直接记最低分。

建议把流程明确分成两步：

1. **先做技术可读性检查。** 能打开视频并成功解码所需帧，才进入评测；文件不存在、损坏或解码失败则跳过，并记录 `unreadable_video` 等原因，不给分。
2. **再处理门槛。** 可读取的视频若任一门槛题明确失败，总分记为最低分 `1`；保留门槛答案作为诊断信息，不运行 CSD、FIRM 等数值组件。门槛通过的视频仍按现有方式评分。

这样避免把“视频内容不符合基本评测条件”和“视频文件无法读取”混为一谈。当前代码在门槛失败时会短路数值组件，并返回空分数；而且 case 能找到视频文件，并不等于文件一定能成功解码。因此要分别处理**可读性检查**和**门槛计分**，不能只把现有空分改成 `1`。

汇总口径也需同步调整：

- 门槛失败但可读取：分数为 `1`，计入总分均值，并单独统计门槛失败数。
- 文件不可读：不计分，单独统计跳过数及原因。
- 状态名称不要再把“已给最低分”的视频归为无分的 `invalid`；否则它会同时被算进有效分和无效数。
- 第 13 维度的 `comparable_score` 是附加可比指标，门槛失败时应继续设为 `null`，避免把部分清单结果误当作正常可比成绩。

还有一个范围问题：门槛评分逻辑位于多个维度共用的代码中。如果只希望第 13 维度采用这个规则，应做成按维度配置的策略；若第 13–18 维度都要如此，再统一应用。以上是实现建议，我没有修改代码。

---

**User**

目前先把所有视频都作为可以读取的，且所有维度都是这样处理。

---

**Cursor**

明白。当前先按这两个前提设计：**所有进入评测流程的视频都视为可读取；所有维度共用同一条门槛处理规则。** 因此暂时不加入视频解码预检，也不区分不可读视频。

这意味着门槛失败的视频在所有维度中都应获得最低分 `1`，而不是 `score: null`。门槛通过的视频继续走各维度现有的评分流程。由于门槛评分逻辑是多维度共用的，处理应放在共用评分层，而不是只改第 13 维度。

汇总时应把门槛失败的视频纳入均分，同时另行统计门槛失败数量；第 13 维度的 `comparable_score` 仍应为空，避免将门槛失败的结果误认为正常可比成绩。音频门失败已有最低分处理，也应与这条规则保持一致。

这是对需求和实现范围的确认；按你之前“先分析，不要修改”的要求，我还没有改代码。

---

**User**

你现在进行修改优化一下吧。

---

**Cursor**

我会在共用评分层处理门槛失败：可评测的视频门槛失败时记 1 分，门槛通过时维持原有评分；同时调整汇总统计和第 13 维度的 `comparable_score`，并同步更新说明文档。

已完成修改：**13–18 维度的共用评分逻辑**现在会将门槛明确失败的视频记为最低分 `1`，而不是空分；门槛通过的视频仍按原流程评分。门槛失败时数值组件不会运行，适用子项记为 `1`，并保留覆盖前的子项分数和状态供诊断。```115:140:tools/vgen_eval/vgen_eval/scoring.py

汇总会把这些视频计入有效样本和均分，并单独统计 `gate_failed`；第 13 维度的 `comparable_score` 在门槛失败时保持为空。```159:170:tools/vgen_eval/vgen_eval/scoring.py``` ```100:108:tools/vgen_eval/vgen_eval/dims/d13.py```

我也更新了第 13 维度工作流文档。按当前约定，没有添加视频可读性预检。相关 Python 文件语法检查、门槛计分和汇总逻辑验证均已通过，文档格式检查无诊断。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/ref2va
这个路径下有一些r2va的case，里面的提示词使用@work-log/work_924/face_50cases_sxdevops/ref2va/r2va_01/prompt_final.txt ,用这个工作流测试两个视频试一下。输出结果放在这个路径下：/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test

---

**Cursor**

已用第 13 维度工作流评测 `r2va_01` 和 `r2va_02` 两个视频。清单输入使用了各 case 自己的 `prompt_final.txt`；原始 case 文件未改动。

**初步分数**：`r2va_01` 为 4.0，`r2va_02` 为 4.3，两条门槛均通过，平均分为 4.15。结果和临时测试输入均放在：

`/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/d13_r2va_trial/`

汇总报告：`output/runs/r2va_d13_smoke/summary.md`  
单条结果：`output/runs/r2va_d13_smoke/13_style_visual_control/<case_id>/result.json`

这次测试**未能完整运行所有数值组件**：CSD 正常运行；FIRM 因 GPU 显存不足报错，所以“风格与内容兼容”子项只用了清单分。此外，目标颜色描述未被调色板组件解析，因此色彩子项也只用了清单分。分数应视为本次试跑结果，不是所有组件完整运行后的最终评测。

为解决 FIRM 的依赖报错，我在评测虚拟环境安装了 `accelerate`；随后重跑时 FIRM 遇到显存不足。

两条视频的第 13 维度试跑已完成，平均分为 4.15。汇总报告位于 `work-log/work_928/test/d13_r2va_trial/output/runs/r2va_d13_smoke/summary.md`；FIRM 组件因 GPU 显存不足未能运行，结果中保留了该错误记录。

---

**User**

目前在进行评估之前，框架期望的文件的存放方式是什么样的？以及我觉得可以设置配置文件，来进行特定任务的选择。给出回答  不要修改代码

---

**Cursor**

目前框架支持两种 case 目录格式。对于你刚才测试的 `r2va`，**推荐使用 `300case` 格式**：它能按提示词里的 `<Picture N>`、`<Audio N>` 等引用序号，把参考素材映射到正确文件。当前加载逻辑按下面的目录结构查找 `meta.json`，并从 case 目录读取 `intent_en.txt` 和 `prompt_official.txt`。```114:129:tools/vgen_eval/vgen_eval/cases.py

```text
<data_root>/
└── 13_style_visual_control/
    └── r2va/                       # input_form
        └── r2va_01/                # case_id
            ├── meta.json           # 至少含 id、input_form、duration
            ├── intent_en.txt       # 当前生成清单所用的需求文本
            ├── prompt_official.txt # 官方增强提示词，也参与参考素材引用解析
            ├── video.mp4           # 待评视频
            └── media/
                ├── image_00.png    # [Picture 1] / 参考图 1
                ├── image_01.png    # [Picture 2] / 参考图 2
                ├── audio_00.mp3    # [Audio 1] / 参考音频 1
                └── ...
```

文件编号从零开始：提示词里的 `Picture 1` 对应 `image_00.*`，`Audio 1` 对应 `audio_00.*`。如果待评视频不放在 case 目录内，也可以通过 `--videos-root` 指定视频目录；框架会按维度、输入形式和 case ID 等几种约定布局查找。```84:90:tools/vgen_eval/vgen_eval/cases.py

另一种是 `face50` 格式：目录为 `<root>/<subset>/<case_id>/metadata.json`，同目录放 `video.mp4`、`input_*.png/jpg`、`ref_audio_*`、`prompt_input.txt` 和 `prompt_final.txt`。不过当前 `face50` 加载逻辑用 `prompt_input.txt` 生成清单，把 `prompt_final.txt` 作为官方提示词；如果希望 `prompt_final.txt` 本身作为评估标准，目前需要像这次试跑那样，将它复制为临时数据里的 `intent_en.txt`。```151:167:tools/vgen_eval/vgen_eval/cases.py

**目前任务选择主要靠命令行参数**，例如指定数据集、维度、case ID、阶段、输出目录和 run 名称。现有 `--config` 参数指向的是维度评分配置 `dims_13_18.yaml`，不是用于挑选本次评测任务的配置文件。```101:111:tools/vgen_eval/run.py

你提出的任务配置文件很有用。建议将它与评分配置分开，例如：

```yaml
task_name: r2va_d13_smoke
dataset: 300case
root: /path/to/prepared_cases
dimensions:
  - 13_style_visual_control
case_ids:
  - r2va_01
  - r2va_02
prompt_file: prompt_final.txt
videos_root: null
stages:
  - check
  - checklist
  - evaluate
  - score
run_name: r2va_d13_smoke
out: /path/to/results
workers: 1
```

其中 `prompt_file` 可以让任务明确选择用哪个文件生成清单；但这是对现有命令行功能的改进建议，**当前框架还不支持读取这种任务配置文件**。当前的清单缓存和评测结果会分别写入 `out/checklists/...` 与 `out/runs/<run_name>/...`。```6:8:tools/vgen_eval/run.py```

---

**User**

我目前想改一下这种读取方式，我可以在配置文件中读取mode，来表示接下来的评价是针对t2va还是fl2va，以及其他三种模式，同时还有就是评估的时候只可以读取：要评估的视频，以及对应的提示词，还有参考的内容，其他全都不应该读取。分析一下，给出回答  不要修改代码

---

**Cursor**

可以这样改：配置文件为**每个待评 case 指定模式、视频、提示词和该模式允许使用的参考素材**；加载器只读取配置列出的文件，不再扫描整个 case 根目录。这样模式和数据边界都由任务配置明确控制。

当前模式可映射为五种输入形式：

- `t2va`：待评视频、提示词；不加载参考素材。
- `f2va`：再加载首帧图。
- `l2va`：再加载尾帧图。
- `fl2va`：加载首帧图和尾帧图。
- `r2va`：只加载配置指定或提示词明确引用的参考图、参考视频、参考音频；未引用的素材不加载。

## 目前框架与这个要求的差距

现有命令行可以选数据集、维度、case ID 和阶段，但 `--ids` 过滤发生在 case 加载之后：加载器先枚举并读取 case 信息，之后才按 ID 过滤。```124:129:tools/vgen_eval/run.py```

两种现有加载方式也会扫描目录：`300case` 会遍历维度下的 `meta.json`、读取提示词，并在 `r2va` 下枚举 `media/`；`face50` 会遍历查找 `metadata.json`，再读取提示词和枚举输入素材。```114:139:tools/vgen_eval/vgen_eval/cases.py``` ```151:166:tools/vgen_eval/vgen_eval/cases.py```

所以，单纯新增 `mode` 配置还不能保证“其他文件都不读取”。需要让任务配置先确定具体 case 和允许访问的路径，再由加载器读取这些路径；不能先扫描全量数据、最后才筛选 ID。

## 配置文件建议

建议每个 case 都显式写出模式及文件路径。这样同一个任务文件也可以包含不同模式的 case：

```yaml
task_name: ref2va_d13_test
dimension: 13_style_visual_control
run_name: ref2va_d13_test
out: /path/to/results

cases:
  - id: r2va_01
    mode: r2va
    video: /path/to/r2va_01/video.mp4
    prompt: /path/to/r2va_01/prompt_final.txt
    references:
      - type: image
        path: /path/to/r2va_01/input_01.png
      - type: audio
        path: /path/to/r2va_01/ref_audio_01.mp3

  - id: endpoint_test
    mode: fl2va
    video: /path/to/endpoint_test/video.mp4
    prompt: /path/to/endpoint_test/prompt_final.txt
    references:
      - type: first_frame
        path: /path/to/endpoint_test/first.png
      - type: last_frame
        path: /path/to/endpoint_test/last.png

stages: [check, checklist, evaluate, score]
workers: 1
```

加载器应按 `mode` 校验并限定素材：

- `t2va` 不接受参考素材。
- `f2va` 必须且只能配置首帧。
- `l2va` 必须且只能配置尾帧。
- `fl2va` 必须同时配置首尾帧。
- `r2va` 只读取 `references` 明列的文件；如果依靠提示词标记选择参考图，则只解析这些标记对应的准确路径，不遍历目录。

提示词文件也应由配置明确指定。当前 `face50` 会用 `prompt_input.txt` 生成清单，而 `prompt_final.txt` 只是另存为官方提示词；若需要评测标准直接来自 `prompt_final.txt`，配置和加载逻辑就应明确支持 `prompt` 路径，而不能依赖默认文件名。```151:166:tools/vgen_eval/vgen_eval/cases.py```

## 建议的读取边界

加载阶段只读取任务配置，以及其中列明的待评视频、提示词和参考素材。评测仍必须读取维度评分配置、模型权重和程序自身配置；这些属于运行依赖，不属于 case 输入。视频评测产生的抽帧、临时音轨和组件缓存也属于基于指定视频派生的数据，应放在配置指定的输出目录中。

另外，配置中的路径最好都做存在性、文件类型和模式一致性检查。缺少必需素材时应在评测前报告配置错误，而不是悄悄从目录中寻找替代文件。

**结论：**任务配置文件可以同时解决模式选择和输入白名单问题，但要达到“其他 case 和素材完全不读取”，还需要调整加载顺序：先读任务配置、锁定选中的 case 和文件，再执行加载；现有 `--ids` 参数本身不足以实现这一点。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
你可以参考一下这个文件夹下面的内容，这个文件夹中全都是t2va的case，我想要的效果是，我在配置文件中会填写这个路径，且配置好是t2va的测评模式，且配置好需要读取的提示词的文件名，例如这个文件夹中的prompt_final.txt,且只可以读取这个，其他的文件全都不可以去读取，如果是其他模型，也可以读取对应需要的参考内容。然后通过运行脚本，可以一键开始进行评估。分析一下，不修改代码。

---

**Cursor**

这个 `t2va` 文件夹适合按“**任务配置 + case 子目录**”的方式评测。每个 case 目录都有 `video.mp4` 和 `prompt_final.txt`；还存在 `metadata.json` 和 `prompt_input.txt`，但按你的要求，新读取流程应完全忽略这两个文件。

例如配置可以写成：

```yaml
task_name: t2va_d13
dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []  # 空列表表示处理 root 下的各 case 子目录

evaluation:
  stages: [check, checklist, evaluate, score]
  run_name: t2va_d13
  output_dir: /path/to/results
  workers: 1
```

对每个被选中的 case，读取器只打开配置指定的提示词和视频。case ID 可以直接取子目录名；`mode` 由配置提供，因此不需要打开 `metadata.json` 推断模式。扫描 case 子目录只需读取目录项，不打开其中其他文件。

其他模式通过配置声明允许的参考文件：

- `f2va`：提示词、视频、首帧图。
- `l2va`：提示词、视频、尾帧图。
- `fl2va`：提示词、视频、首帧图和尾帧图。
- `r2va`：提示词、视频，以及配置列出或提示词明确引用的参考素材。
- `t2va`：提示词和视频，不读取参考素材。

对 `r2va`，建议显式列出引用素材路径，或只按提示词中的引用标记解析对应文件；不要枚举 `media/` 或整个 case 目录。若模式需要的参考文件缺失，应在开始评估前报告配置错误，不要尝试从其他文件中寻找替代品。

有一点需要特别说明：**现有框架还不能保证这种读取边界。** `face50` 加载器会读取 `metadata.json`、`prompt_input.txt` 和 `prompt_final.txt`，而且命令行的 `--ids` 过滤是在 case 加载之后才执行。```151:166:tools/vgen_eval/vgen_eval/cases.py``` ```124:129:tools/vgen_eval/run.py``` 因此，要实现你描述的一键流程，需要增加任务配置加载器，先读取配置、确定允许的文件清单，再构造评测 case；不能继续使用会遍历并读取整批 case 元数据的旧加载方式。

这里的“只读取”应针对 case 输入数据理解。评测运行仍需要读取任务配置、维度评分规则和模型权重；评测器也会从指定视频生成抽帧、音轨等派生数据，并写入输出目录。除此之外，不应读取 case 中的其他文件。配置文件准备好后，一键命令可以类似：

```bash
.venv/bin/python run.py --task-config /path/to/t2va_d13.yaml
```

以上是建议的行为和配置设计；**没有修改代码**。

---

**User**

你现在按照我预设的这种方式进行优化修改，求修改后不要进行全额的测试，修改后我还需要你进行其他的修改后再进行完整的评估测试。

---

**Cursor**

我会加一个独立的任务配置入口：配置指定 case 根目录、五种模式之一、提示词文件名、视频文件名以及模式对应的参考素材规则；加载器只打开这些指定文件，不读取 `metadata.json`、其他提示词或目录中的无关素材。按你之前的要求，这次只做代码和加载器级验证，不启动完整模型评测。

已加入**任务配置驱动的一键评测入口**，支持 `t2va`、`f2va`、`l2va`、`fl2va` 和 `r2va`。

新增的配置示例 `tools/vgen_eval/configs/task_t2va_example.yaml` 指向你给出的 `t2va` 目录，并指定使用 `prompt_final.txt` 和 `video.mp4`。运行：

```bash
tools/vgen_eval/.venv/bin/python tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

新加载器只打开配置指定的提示词、视频，以及该模式明确需要的参考文件；不会读取 `metadata.json`、`prompt_input.txt` 或其他未列入任务的 case 文件。空的 `case_ids` 会枚举根目录下的 case 子目录名，但不会打开其中的文件；填写 ID 则只处理指定 case。`r2va` 会从配置指定的素材命名规则中解析提示词实际引用的素材。

实现位于 `vgen_eval/cases.py` 和 `run.py`，输入规则说明在 `tools/vgen_eval/docs/task_config_and_input_allowlist.md`。我只做了 Python 语法、单 case 的 `t2va` 加载和 `r2va` 引用素材解析检查，**没有启动完整模型评估**，按你的要求留待后续修改完成后再统一测试。

---

**User**

前面测试的时候发现FIRM和CLE_lab会出现问题  那可以不可以先进行屏蔽，类似与也在配置文件中也进行模块化的设计，对各子项是否只依据检查清单，或者添加争对子项的小模型来设置，True或false。先分析，不修改代码

---

**Cursor**

可以。建议把**组件启用开关放在任务配置中，按子项选择检查清单和数值模型**。这样当前可以先屏蔽出错组件；等环境或组件修复后，再在配置中打开，不用改维度评分代码。

例如：

```yaml
evaluation:
  subpoints:
    style_accuracy:
      components:
        checklist: true
        csd_ref_similarity: true

    style_persistence:
      components:
        checklist: true
        csd_temporal_drift: true

    style_content_compat:
      components:
        checklist: true
        firm_world_consistency: false

    lighting_control:
      components:
        checklist: true

    color_control:
      components:
        checklist: true
        palette_match: false
```

这个配置会让 `style_content_compat` 和 `color_control` 暂时只依据检查清单评分；其他子项仍可使用检查清单和启用的模型组件。

实现时有个关键点：**关闭组件必须阻止组件函数运行，而不只是丢弃它的结果。** 对禁用的组件应跳过模型加载和计算，不记录成运行错误；合成分数时只在已启用且有有效结果的组件间重新归一权重。这样关闭 FIRM 后，`style_content_compat` 就不会因为 FIRM 报错而产生错误状态；关闭 `palette_match` 后，`color_control` 只用清单分。

我建议采用以下配置规则：

- `checklist: true` 默认必需，避免子项没有任何评分依据。
- 小模型或数值组件分别用 `true` / `false` 控制。
- 未写出的组件沿用维度评分配置的默认设置。
- 被显式设为 `false` 的组件标记为 `disabled`，与 `error`、`blocked`、`not_applicable` 区分。
- 如需完全不评某个子项，再单独提供子项级 `enabled: false`；它不参与维度平均，并在结果里标为未启用。
- 单次结果记录实际启用配置，确保之后能知道分数是“清单单独评分”还是“清单加模型组件”。

FIRM 和 CIE Lab 调色板匹配可以先在这个任务配置中分别关闭。要注意，屏蔽组件会改变子项的评分依据，因此不同模型或不同批次比较时，应使用相同的组件开关配置，并在报告中注明。以上是实现方案分析，**本次没有修改代码**。

---

**User**

那就按照这样来修改一下。修改完也不需要进行完整的测试。

---

**Cursor**

我会把组件开关做成任务配置里的逐子项设置。关闭时在共用上下文中拦截组件调用，确保 FIRM 或调色板组件不会被加载/执行；清单仍保留为评分依据，剩余已启用组件的权重自动重新归一。也会支持整项子项停用，并在结果中区分 `disabled` 与运行错误。

已添加按子项配置评分组件的开关。比如可以在任务配置中将 `firm_world_consistency` 和 `palette_match` 设为 `false`，让这两个子项只使用检查清单评分。关闭的组件会被跳过，不会尝试加载或运行；其权重会从子项合成中排除，剩余组件重新归一。也可以通过子项级 `enabled: false` 将整个子项排除出维度均分。

配置校验会拒绝未知的子项或组件，也不允许关闭仍参与评分的子项中的 `checklist`。每条结果会保存实际的 `evaluation_overrides`，并将组件状态标为 `disabled`，与运行错误区分。

`t2va` 示例任务配置已加入 FIRM 和调色板组件的关闭示例；配置说明也已更新。本次只做了语法、配置校验、组件确实不会执行和权重归一的针对性检查，**没有启动完整评估**。

---

**User**

那这个配置文件是哪一个？

---

**Cursor**

你要填写的是这个**任务配置文件**：

[task_t2va_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_t2va_example.yaml)

它不是原来的评分配置 `dims_13_18.yaml`。两者作用不同：

- `task_t2va_example.yaml`：选择本次评测任务，包括数据路径、模式、提示词文件名、视频文件名、评测维度、要关闭的组件和输出路径。
- `dims_13_18.yaml`：定义各维度的固定评分规则、子项权重和阈值，一般不需要为了选择任务而修改。

当前任务配置中的关键位置是：

```1:15:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_t2va_example.yaml
# One-click task configuration for the t2va face50-style layout.
# The loader opens only prompt_final.txt and video.mp4 for each selected case.
task_name: face50_t2va_d13
run_name: face50_t2va_d13

dimension: 13_style_visual_control
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
```

当前配置已经表示：

- 评测目录：`.../face_50cases_sxdevops/t2va`
- 评测模式：`t2va`
- 提示词：每个 case 下的 `prompt_final.txt`
- 视频：每个 case 下的 `video.mp4`
- `case_ids: []`：处理该目录下的所有 case 子目录

FIRM 和 CIE Lab 调色板组件的开关在这里：

```17:28:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_t2va_example.yaml
# Per-subpoint component switches. Unspecified components retain scoring-config defaults.
# Keep the checklist enabled; disabled numerical components are skipped, not run-and-discarded.
evaluation:
  subpoints:
    style_content_compat:
      components:
        checklist: true
        firm_world_consistency: false
    color_control:
      components:
        checklist: true
        palette_match: false
```

启动方式是：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self

tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

程序通过 `--task-config` 读取这个 YAML 配置，参数定义在：```132:145:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py

如果以后评测 `fl2va`、`r2va` 或其他模型，建议复制一份新的任务配置，例如：

```text
tools/vgen_eval/configs/task_t2va_example.yaml
tools/vgen_eval/configs/task_fl2va_example.yaml
tools/vgen_eval/configs/task_r2va_example.yaml
```

不要直接复用同一个配置文件反复修改，这样可以保留每次评测的输入路径、模式和组件开关记录。

---

**User**

那你在帮我创建两个

---

**Cursor**

我会创建两个独立的任务配置：`fl2va` 和 `r2va`。它们分别指定对应模式、提示词/视频文件名、参考素材命名规则，以及当前已知会屏蔽的 FIRM 和 CIE Lab 组件；只创建配置，不启动完整评估。

<thinking>**Creating two task configurations**</thinking>

<thinking>**Validating new task YAML files**</thinking>

已创建两个任务配置文件：

- [task_fl2va_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_fl2va_example.yaml)
- [task_r2va_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_r2va_example.yaml)

其中：

- `fl2va` 配置使用 `prompt_final.txt`、`video.mp4`、`input_01` 作为首帧、`input_02` 作为尾帧。
- `r2va` 配置使用 `prompt_final.txt`、`video.mp4`，并根据提示词中的 `<Picture N>`、`<Audio N>` 等标记读取对应的 `input_NN` 和 `ref_audio_NN` 文件。
- 两个配置都暂时关闭了 `firm_world_consistency` 和 `palette_match`，保留检查清单评分。
- `case_ids: []` 表示处理对应根目录下的全部 case；填写具体 ID 后可以只处理指定 case。

两个 YAML 文件已经完成解析、评分组件配置校验和 LF 换行检查。本次没有启动评估。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
假如我想手动测试这个里面的t2va视频，我应该怎么配置我的文件？你不要进行测试，你教一下我，我自己手动测试

---

**Cursor**

要手动测试 `t2va` 中的一个视频，只需编辑现有配置 `tools/vgen_eval/configs/task_t2va_example.yaml`，将 `case_ids` 填为对应目录名，并确认根目录、提示词文件名和输出目录正确。例如测试 `t2va_01`：

```yaml
dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids:
    - t2va_01
```

这个配置会读取 `t2va_01/prompt_final.txt` 和 `t2va_01/video.mp4`，不需要改动 case 目录中的文件。测试其他视频时，把 `t2va_01` 换成相应目录名；要评测全部 case，则设为 `case_ids: []`。

保存后，在项目根目录运行：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self

tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

该配置中的 stages 会依次执行就绪检查、生成清单、视频评估和结果汇总。输出位置由 `output_dir` 指定；运行前可以把它改成专门用于这次手动测试的目录，避免与其他运行结果混在一起。

---

**User**

那其他的配置是什么意思？

---

**Cursor**

`task_t2va_example.yaml` 里的配置可以分成几组：

**任务和结果命名**

- `task_name`：任务名称，主要用于识别这份配置。
- `run_name`：本次运行的名称，会用于结果目录名。重复使用同一个名称可能复用或覆盖该 run 下已有的组件结果；想保留独立结果时，换一个名称。
- `output_dir`：结果根目录，报告和中间缓存都会写到这里。

**评测对象**

- `dimension`：要评测的维度。当前配置是 `13_style_visual_control`，即第 13 维度。
- `input.root`：case 所在目录。每个直接子目录视为一个 case。
- `input.mode`：输入模式。`t2va` 表示没有首尾帧或参考素材。
- `prompt_filename`：每个 case 目录中用来生成评测清单的提示词文件。
- `video_filename`：每个 case 目录中的待评视频。
- `case_ids`：要评测的 case 子目录名。填 `[]` 表示全部；要只测一个，写成 `case_ids: [t2va_01]`。

**评分组件开关**

`evaluation.subpoints` 用来控制子项及其组件：

- `style_content_compat`：风格与内容兼容。`checklist: true` 保留清单评分；`firm_world_consistency: false` 暂停运行 FIRM，因此这个子项只按清单评分。
- `color_control`：色彩控制。`checklist: true` 保留清单评分；`palette_match: false` 暂停运行调色板匹配，因此这个子项只按清单评分。
- 其他未写出的子项和组件沿用默认评分配置。比如，其他子项仍会按原配置调用 CSD。
- 某个子项可以设置 `enabled: false` 来整体排除，但当前示例没有这么做。

**运行流程**

- `stages`：要依次执行的阶段。`check` 检查依赖和评委服务；`checklist` 生成清单；`evaluate` 评测视频；`score` 汇总结果。如果清单已经生成且没有修改需求或任务输入，可以去掉 `checklist`，只重跑后续阶段。
- `workers`：并行处理清单生成的工作数。单个视频保持 `1` 即可；批量生成清单时可适当调大。
- 注释行以 `#` 开头，不参与配置。

当前配置会用 `prompt_final.txt` 和 `video.mp4`，将 FIRM 和调色板组件设为关闭，并评测 `t2va` 根目录下的所有 case。

---

**User**

如果我需要评估两个case，应该怎么填，最后执行的命令是什么？

---

**Cursor**

在 `task_t2va_example.yaml` 中，把 `case_ids` 改成两个 case 的目录名，例如评测 `t2va_01` 和 `t2va_02`：

```yaml
  case_ids:
    - t2va_01
    - t2va_02
```

然后在项目根目录执行：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self

tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

结果会写到配置中的 `output_dir`。如果希望这次结果与之前运行分开保存，可以同时修改 `run_name` 和 `output_dir`。

---

**User**

目前裁判模型是如何拉起的  怎么配置可以运行的gpu？

---

**Cursor**

我先核对评测脚本里裁判客户端的连接方式、默认服务地址和 GPU 参数，区分“评估脚本使用哪张 GPU”和“裁判模型服务本身占用哪张 GPU”。

目前裁判模型**不是由 `run.py` 直接拉起的**。流程是：

1. 先用两个启动脚本分别启动视觉和音频裁判服务。
2. 服务以 OpenAI 兼容接口监听端口。
3. `run.py` 只通过 HTTP 调用这些服务，不负责加载 Qwen3-VL 或 Qwen2.5-Omni。

**1. 视觉裁判模型**

启动脚本：

```text
tools/vgen_eval/scripts/serve_judge.sh
```

默认配置：

- 模型：`Qwen3-VL-32B-Instruct`
- 地址：`http://127.0.0.1:8011/v1`
- 默认 GPU：`GPU=0`
- 默认端口：`8011`
- 默认显存占用比例：`0.85`
- 默认最大并发：`16`

脚本中的关键逻辑是：

```1:18:tools/vgen_eval/scripts/serve_judge.sh
#!/usr/bin/env bash
# Vision judge + checklist generator: Qwen3-VL-32B-Instruct on vLLM 0.11 (cu128), OpenAI-compatible API.
# Usage: GPU=0 PORT=8011 bash scripts/serve_judge.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GPU="${GPU:-0}"
PORT="${PORT:-8011}"
MODEL="${MODEL:-/kwkj-k8s/research-eval-group/Eval-kzy/judge_models/Qwen3-VL-32B-Instruct}"
NAME="${NAME:-qwen3-vl-32b}"
MAX_LEN="${MAX_LEN:-32768}"
GPU_UTIL="${GPU_UTIL:-0.85}"
TP="$(echo "${GPU}" | tr ',' '\n' | wc -l)"
```

例如使用 GPU 0：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

GPU=0 PORT=8011 bash scripts/serve_judge.sh
```

如果希望视觉模型使用多张 GPU，例如 GPU 0、1、2、3：

```bash
GPU=0,1,2,3 PORT=8011 bash scripts/serve_judge.sh
```

脚本会自动计算：

```text
CUDA_VISIBLE_DEVICES=0,1,2,3
tensor-parallel-size=4
```

也就是说，视觉服务的 `GPU` 参数既控制可见 GPU，也决定 vLLM 的张量并行卡数。

如果需要指定其他模型路径或显存比例：

```bash
GPU=0,1 \
PORT=8011 \
MODEL=/kwkj-k8s/research-eval-group/Eval-kzy/judge_models/Qwen3-VL-32B-Instruct \
GPU_UTIL=0.85 \
bash scripts/serve_judge.sh
```

**2. 音频裁判模型**

启动脚本：

```text
tools/vgen_eval/scripts/serve_audio_judge.sh
```

默认配置：

- 模型：`Qwen2.5-Omni-7B`
- 地址：`http://127.0.0.1:8012/v1`
- 默认 GPU：`GPU=3`
- 默认端口：`8012`
- 默认显存占用比例：`0.45`
- 默认最大并发：`8`

启动命令：

```bash
GPU=3 PORT=8012 bash scripts/serve_audio_judge.sh
```

如果改用 GPU 5：

```bash
GPU=5 PORT=8012 bash scripts/serve_audio_judge.sh
```

音频服务脚本没有设置 `--tensor-parallel-size`，因此通常按单 GPU 启动。它会通过：

```bash
export CUDA_VISIBLE_DEVICES="${GPU}"
```

限制模型只能看到指定 GPU。

**3. 评估脚本如何连接裁判**

`run.py` 默认连接：

```text
视觉裁判：http://127.0.0.1:8011/v1
音频裁判：http://127.0.0.1:8012/v1
```

对应客户端定义在：

```75:80:tools/vgen_eval/vgen_eval/llm_client.py
def vision_client() -> JudgeClient:
    return JudgeClient(env_prefix="VGEN_JUDGE", default_url="http://127.0.0.1:8011/v1")


def audio_client() -> JudgeClient:
    return JudgeClient(env_prefix="VGEN_AUDIO_JUDGE", default_url="http://127.0.0.1:8012/v1")
```

如果服务不在本机或端口不同，可以在运行评估前设置：

```bash
export VGEN_JUDGE_URL=http://127.0.0.1:8011/v1
export VGEN_AUDIO_JUDGE_URL=http://127.0.0.1:8012/v1
```

也可以指定服务暴露的模型名称：

```bash
export VGEN_JUDGE_MODEL=qwen3-vl-32b
export VGEN_AUDIO_JUDGE_MODEL=qwen2.5-omni-7b
```

对于第 13 维度，通常只会使用视觉裁判，因为主要是视觉检查题。音频裁判主要用于第 15、16 维度，或者清单中生成了音频相关题目时。

**4. 评估进程本身使用哪张 GPU**

启动裁判服务之后，执行 `run.py` 时还要考虑评估进程自己的 GPU。它可能运行：

- CSD；
- FIRM；
- 其他本地视觉组件；
- 外部评测子进程。

例如：

```bash
CUDA_VISIBLE_DEVICES=5 \
VGEN_EXTERNAL_GPU=5 \
tools/vgen_eval/.venv/bin/python \
tools/vgen_eval/run.py \
--task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

其中：

- `CUDA_VISIBLE_DEVICES=5`：限制评估主进程内部的 PyTorch 模型使用 GPU 5。
- `VGEN_EXTERNAL_GPU=5`：限制外部子进程组件使用 GPU 5。

`VGEN_EXTERNAL_GPU` 的默认逻辑在这里：

```1:27:tools/vgen_eval/vgen_eval/components/external.py
def _gpu_env(extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = os.environ.get("VGEN_EXTERNAL_GPU", os.environ.get("CUDA_VISIBLE_DEVICES", "0"))
    if extra:
        env.update(extra)
    return env
```

**5. 推荐的 GPU 分配方式**

如果有多张 GPU，建议把裁判服务和评估组件分开。例如：

```text
GPU 0,1,2,3：Qwen3-VL-32B 视觉裁判
GPU 4：Qwen2.5-Omni-7B 音频裁判
GPU 5：评估进程中的 CSD、FIRM 或其他组件
```

对应启动方式：

终端 1：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
GPU=0,1,2,3 PORT=8011 bash scripts/serve_judge.sh
```

终端 2：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
GPU=4 PORT=8012 bash scripts/serve_audio_judge.sh
```

终端 3：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self

CUDA_VISIBLE_DEVICES=5 \
VGEN_EXTERNAL_GPU=5 \
tools/vgen_eval/.venv/bin/python \
tools/vgen_eval/run.py \
--task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

如果当前任务配置已经关闭 FIRM、CIE Lab 和其他本地数值组件，那么评估进程主要负责调用裁判服务，单独预留一张 GPU 的必要性会降低。但建议仍然明确设置 `CUDA_VISIBLE_DEVICES`，避免评估进程默认占用 GPU 0，和视觉裁判发生显存竞争。

**6. 启动顺序**

先启动裁判服务，再执行评估：

```bash
# 先确认视觉服务
curl http://127.0.0.1:8011/v1/models

# 再确认音频服务
curl http://127.0.0.1:8012/v1/models

# 最后运行就绪检查
CUDA_VISIBLE_DEVICES=5 \
VGEN_EXTERNAL_GPU=5 \
tools/vgen_eval/.venv/bin/python \
tools/vgen_eval/run.py \
--task-config tools/vgen_eval/configs/task_t2va_example.yaml \
--stages check
```

就绪检查看到类似结果即可：

```text
vision (Qwen3-VL)     up: qwen3-vl-32b
audio  (Qwen2.5-Omni) up: qwen2.5-omni-7b
13_style_visual_control: cases=... with_video=... READY
```

当前任务配置文件中的 `workers` 只控制清单生成阶段的并发任务数，**不控制裁判模型使用哪张 GPU**。裁判 GPU 需要通过启动脚本中的 `GPU=...` 设置；评估进程 GPU 则通过 `CUDA_VISIBLE_DEVICES` 和 `VGEN_EXTERNAL_GPU` 设置。

---

**User**

你现在再创建一个配置文件，用来可以配置视频和音频裁判模型启动的一些参数。

---

**Cursor**

我会创建一个独立的裁判服务配置文件，覆盖视觉和音频服务的 GPU、端口、模型路径、模型名、上下文长度、显存比例、并发数等参数，并让两个启动脚本通过同一个配置文件读取这些参数。不会启动模型服务或进行完整评估。

<thinking>**Planning config parser implementation**
**Defining YAML schema and script integration**</thinking 

我会把配置真正接到两个启动脚本上，而不是只放一个未使用的 YAML：启动脚本默认读取 `configs/judge_servers.yaml`，同时保留环境变量覆盖单项参数的能力。这样可以统一配置 GPU、端口、模型路径、并行度、上下文长度、显存比例和多模态输入限制。

<thinking>**Updating audio script**</thinking>

<thinking>**Planning executable permissions and docs**

<thinking>**Testing config resolver and bash syntax without launching vLLM**</thinking>

已创建统一的裁判服务配置：`tools/vgen_eval/configs/judge_servers.yaml`，并修改两个启动脚本，让它们从该文件读取配置：

- `scripts/serve_judge.sh`：视觉裁判 Qwen3-VL
- `scripts/serve_audio_judge.sh`：音频裁判 Qwen2.5-Omni

配置里可以分别设置 GPU、端口、模型路径和服务名称、最大上下文长度、显存使用比例、并发数、张量并行度、多模态输入限制等。默认 GPU 延续原设置：视觉裁判使用 `0`，音频裁判使用 `3`。例如要改视觉裁判的 GPU，可编辑配置中的 `vision.gpu`；多个 GPU 写成 `"0,1,2,3"`，`tensor_parallel_size: null` 时会自动设为 GPU 数量。

启动方式仍是：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

bash scripts/serve_judge.sh
bash scripts/serve_audio_judge.sh
```

也可以用 `GPU=...`、`PORT=...` 等同名环境变量临时覆盖配置，或通过 `JUDGE_CONFIG=/path/to/file.yaml` 指定另一份配置。

我验证了配置解析和两个脚本的 Bash 语法，**没有启动裁判服务，也没有运行评估**。

---

**User**

目前这两个服务已经拉起了  我怎么停下，自己手动重新拉起？

---

**Cursor**

如果两个服务是在前台终端中启动的，直接切换到对应终端按：

```text
Ctrl+C
```

即可停止。由于启动脚本最后执行的是 `vllm serve`，`Ctrl+C` 会终止对应的 vLLM 服务。

如果找不到原来的终端，可以先查看 8011 和 8012 端口对应的进程：

```bash
fuser -v 8011/tcp
fuser -v 8012/tcp
```

确认进程确实是两个裁判服务后，再停止：

```bash
fuser -k 8011/tcp
fuser -k 8012/tcp
```

也可以先查看进程详情：

```bash
ps -ef | grep '[v]llm serve'
```

确认后按进程号停止：

```bash
kill -TERM <PID>
```

等待几秒后仍未退出，再使用：

```bash
kill -KILL <PID>
```

重新启动时，进入评测工具目录：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
```

启动视觉裁判：

```bash
bash scripts/serve_judge.sh
```

启动音频裁判：

```bash
bash scripts/serve_audio_judge.sh
```

这两个命令默认读取：

```text
tools/vgen_eval/configs/judge_servers.yaml
```

因此你修改 `judge_servers.yaml` 中的 GPU、端口或模型参数后，停止旧服务再重新执行脚本即可生效。

推荐使用两个 `tmux` 会话启动，便于后台运行和随时查看日志：

```bash
tmux new -s judge-vision
```

在会话中运行：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
bash scripts/serve_judge.sh
```

按 `Ctrl+B`，再按 `D` 退出会话但保持服务运行。音频服务同理：

```bash
tmux new -s judge-audio
```

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
bash scripts/serve_audio_judge.sh
```

查看会话：

```bash
tmux ls
```

重新进入会话查看日志：

```bash
tmux attach -t judge-vision
tmux attach -t judge-audio
```

启动后可以通过下面的命令确认服务是否正常：

```bash
curl http://127.0.0.1:8011/v1/models
curl http://127.0.0.1:8012/v1/models
```

看到模型列表返回后，再执行评估脚本。停止和重新启动裁判服务不会删除模型权重、清单缓存或评估结果。

---

**User**

你帮我停一下吧

---

**Cursor**

我先确认 8011 和 8012 端口对应的进程，只停止这两个裁判服务，不影响其他进程。

确认到两个目标服务分别是 8011 的视觉裁判和 8012 的音频裁判；另有一个无关的 30180 vLLM 服务，我不会触碰。现在停止这两个服务并检查端口是否释放。

两个裁判服务已经停止：

- 视觉裁判：`8011`
- 音频裁判：`8012`

我确认这两个端口已经释放。无关的 `30180` vLLM 服务没有被停止。

---

**User**

cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self

tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_t2va_example.yaml
这是什么运行代码？

---

**Cursor**

这是一条**启动一次 t2va 视频评测任务**的命令。它不会启动裁判模型服务，而是使用已经运行中的视觉/音频裁判服务，完成配置文件中指定的评测流程。

命令分成两部分：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self
```

进入项目根目录，保证相对路径 `tools/vgen_eval/...` 能正确解析。

```bash
tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_t2va_example.yaml
```

含义是：

- `tools/vgen_eval/.venv/bin/python`：使用评测项目自己的 Python 虚拟环境。
- `tools/vgen_eval/run.py`：执行评测主程序。
- `--task-config ...`：读取任务配置文件，由该文件决定：
  - 评测哪个目录下的 case；
  - 使用哪种模式，例如 `t2va`；
  - 读取哪个提示词文件，例如 `prompt_final.txt`；
  - 读取哪个视频文件，例如 `video.mp4`；
  - 评测哪些 case；
  - 执行哪些阶段；
  - 启用或关闭哪些评分组件；
  - 结果保存到哪里。

当前配置中的阶段是：

```yaml
stages:
  - check
  - checklist
  - evaluate
  - score
```

所以这条命令会依次执行：

1. **`check`**：检查视觉裁判、音频裁判和本地评测依赖是否就绪。
2. **`checklist`**：根据每个 case 的 `prompt_final.txt` 生成评测事实、门槛题和检查题，并缓存清单。
3. **`evaluate`**：读取视频，调用裁判服务回答检查题，并运行配置中启用的数值组件。
4. **`score`**：计算每个 case 的分数，并生成总体汇总报告。

当前 `task_t2va_example.yaml` 使用：

```yaml
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
```

因此它会读取该目录下各 case 的：

```text
<case_id>/prompt_final.txt
<case_id>/video.mp4
```

`case_ids: []` 表示评测全部 case。如果只测试两个 case，可以改成：

```yaml
case_ids:
  - t2va_01
  - t2va_02
```

这条命令要求裁判服务已经提前启动。如果服务没有启动，`check` 可能显示服务不可用，后面的 `checklist` 或 `evaluate` 阶段会失败。需要先启动：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

bash scripts/serve_judge.sh
```

如果任务需要音频题，再启动：

```bash
bash scripts/serve_audio_judge.sh
```

不过第 13 维度通常主要使用视觉裁判。

结果会写入配置中的：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/face50_t2va_d13
```

通常可以重点查看：

```text
runs/face50_t2va_d13/summary.md
runs/face50_t2va_d13/summary.json
runs/face50_t2va_d13/<dimension>/<case_id>/result.json
```

简化理解就是：

```text
任务配置
  ↓
run.py
  ↓
读取 prompt_final.txt 和 video.mp4
  ↓
调用已启动的裁判服务
  ↓
计算分数
  ↓
输出 result.json 和 summary.md
```

---

**User**

目前第14维度是如何进行评估的？
我也想按照目前的/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_t2va_example.yaml
来进行配置  你先分析一下，不要修改代码

---

**Cursor**

我会先按当前代码梳理第 14 维度的子项、适用条件、评委与数值组件，再说明怎样把现有 `task_t2va_example.yaml` 改成第 14 维度任务；这次只分析，不修改配置或代码。

<thinking>**Checking D14 configuration and component behavior**</thinking>

第 14 维度当前评估的是**编辑与可控生成能力**。它不是固定评估所有子项，而是先由清单模型从提示词中抽取编辑事实，再根据事实决定哪些子项适用。

## 1. 第 14 维度包含哪些子项

配置位于 `configs/dims_13_18.yaml` 的 `14_edit_controllable_gen`：

```90:121:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/dims_13_18.yaml
  14_edit_controllable_gen:
    name_zh: 编辑与可控生成
    subpoints:
      local_edit_accuracy:
        name_zh: 局部修改准确性
        applies: facts.edit_targets
        components: {checklist: 1.0}
      non_target_preservation:
        name_zh: 非目标区域保持
        components: {checklist: 0.4, dino_bg_consistency: 0.3, masked_lpips_static: 0.3}
      subject_replacement:
        name_zh: 主体替换一致性
        applies: facts.has_subject_replacement
        components: {checklist: 0.6, arcface_identity_keep: 0.4}
      add_remove_object:
        name_zh: 增删物体
        applies: facts.add_objects or facts.remove_objects
        components: {checklist: 0.7, gdino_presence: 0.3}
      video_extension:
        name_zh: 视频延长
        applies: facts.is_continuation
        components: {checklist: 0.5, continuation_seam_lpips: 0.5}
      first_last_frame:
        name_zh: 首尾帧控制
        applies: case.first_frame or case.last_frame
        components: {checklist: 0.5, endpoint_psnr: 0.25, endpoint_lpips: 0.25}
```

具体含义如下：

### `local_edit_accuracy`

仅当提示词中明确存在编辑目标 `facts.edit_targets` 时适用。

主要依赖检查清单，检查：

- 是否修改了正确对象；
- 修改顺序是否正确；
- 初始状态、变化过程和最终状态是否符合提示词。

当前没有额外数值模型，权重为 `1.0`。

### `non_target_preservation`

当前没有 `applies` 条件，通常每个 case 都会尝试评估。

检查提示词要求保持不变的区域，包括：

- 背景；
- 场景布局；
- 其他主体；
- 非编辑对象；
- 标识或其他指定保留内容。

组件包括：

- `checklist`：权重 `0.4`；
- `dino_bg_consistency`：权重 `0.3`；
- `masked_lpips_static`：权重 `0.3`。

它会先以首帧作为锚点；没有首帧时使用生成视频的第 0 帧。然后用 GroundingDINO 检测编辑目标，再对目标框外区域进行 DINO 特征相似度和 LPIPS 比较。```24:35:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d14.py``` ```64:85:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d14.py```

### `subject_replacement`

仅当清单判断发生了人物或主体替换时适用：

```text
facts.has_subject_replacement
```

评分包括：

- `checklist`：权重 `0.6`；
- `arcface_identity_keep`：权重 `0.4`。

如果被替换对象不是人，ArcFace 组件会被标记为不适用，只保留清单评分。人物参考锚点的选择顺序是：

1. 首帧图；
2. r2va 参考图；
3. 生成视频第 0 帧。

### `add_remove_object`

仅当提示词中有增加或删除物体时适用：

```text
facts.add_objects or facts.remove_objects
```

评分包括：

- `checklist`：权重 `0.7`；
- `gdino_presence`：权重 `0.3`。

GroundingDINO 会检查：

- 要增加的物体是否出现在最后两帧；
- 要删除的物体是否在最后两帧都消失。

### `video_extension`

仅当提示词被识别为续写任务时适用：

```text
facts.is_continuation
```

评分包括：

- `checklist`：权重 `0.5`；
- `continuation_seam_lpips`：权重 `0.5`。

接缝参考源的优先级是：

1. r2va 参考视频最后一帧；
2. 首帧图；
3. 如果两者都没有，则数值组件缺少输入。

### `first_last_frame`

仅当 case 带首帧或尾帧时适用：

```text
case.first_frame or case.last_frame
```

评分包括：

- `checklist`：权重 `0.5`；
- `endpoint_psnr`：权重 `0.25`；
- `endpoint_lpips`：权重 `0.25`。

因此，**纯 t2va case 没有首帧和尾帧，这个子项不会参与评分**。对于 `fl2va`，它才会同时比较视频首帧和尾帧。

## 2. 用现在的任务配置方式评估 t2va

你可以复制当前的 `task_t2va_example.yaml`，把核心字段改成：

```yaml
task_name: face50_t2va_d14
run_name: face50_t2va_d14

dimension: 14_edit_controllable_gen

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids:
    - t2va_01
    - t2va_02
```

`t2va` 模式下，框架只读取：

```text
t2va_01/prompt_final.txt
t2va_01/video.mp4
t2va_02/prompt_final.txt
t2va_02/video.mp4
```

不会读取首帧、尾帧或参考素材，因此：

- `first_last_frame` 不适用；
- `video_extension` 只有在提示词明确表达续写任务时才适用；
- `subject_replacement` 和 `add_remove_object` 由清单模型根据提示词决定；
- `non_target_preservation` 通常会参与。

## 3. 第 14 维度如何关闭容易出错的模型组件

当前已经支持逐子项关闭组件。比如先只使用清单评分，可以配置：

```yaml
evaluation:
  subpoints:
    local_edit_accuracy:
      components:
        checklist: true

    non_target_preservation:
      components:
        checklist: true
        dino_bg_consistency: false
        masked_lpips_static: false

    subject_replacement:
      components:
        checklist: true
        arcface_identity_keep: false

    add_remove_object:
      components:
        checklist: true
        gdino_presence: false

    video_extension:
      components:
        checklist: true
        continuation_seam_lpips: false

    first_last_frame:
      components:
        checklist: true
        endpoint_psnr: false
        endpoint_lpips: false
```

组件设为 `false` 后：

- 不会执行该组件；
- 不会加载对应模型；
- 不会被记录为运行错误；
- 该组件权重会被排除；
- 剩余启用组件重新归一化。

例如 `non_target_preservation` 关闭两个数值组件后，只剩 `checklist: 1.0`，该子项实际分数就是检查清单分数。

也可以直接关闭整个子项：

```yaml
evaluation:
  subpoints:
    first_last_frame:
      enabled: false
```

但是对于 t2va，`first_last_frame` 本来就不会适用，不需要额外关闭。

## 4. 对 t2va 最简单的配置

如果你只是想先用视觉裁判检查第 14 维度，建议先用下面的配置：

```yaml
task_name: face50_t2va_d14_checklist
run_name: face50_t2va_d14_checklist

dimension: 14_edit_controllable_gen

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids:
    - t2va_01
    - t2va_02

evaluation:
  subpoints:
    local_edit_accuracy:
      components:
        checklist: true

    non_target_preservation:
      components:
        checklist: true
        dino_bg_consistency: false
        masked_lpips_static: false

    subject_replacement:
      components:
        checklist: true
        arcface_identity_keep: false

    add_remove_object:
      components:
        checklist: true
        gdino_presence: false

    video_extension:
      components:
        checklist: true
        continuation_seam_lpips: false

    first_last_frame:
      enabled: false

stages:
  - check
  - checklist
  - evaluate
  - score

workers: 1
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/face50_t2va_d14
```

## 5. 一个需要注意的当前实现限制

虽然评估阶段支持关闭第 14 维度的数值组件，但 `check` 阶段仍然按照维度的默认 `REQUIRED` 配置检查依赖：

```text
DINO
InsightFace
VMBench
```

也就是说，即使任务配置中关闭了 `dino_bg_consistency`、`arcface_identity_keep` 和 `gdino_presence`，`check` 阶段仍可能显示这些依赖缺失。它目前不会根据任务配置动态减少必需依赖。

不过这不会改变关闭组件的评估逻辑：组件本身会被跳过。这个问题属于就绪检查显示层面的限制，后续可以再优化。

总结来说，按照现在的任务配置方式，第 14 维度可以直接通过：

```yaml
dimension: 14_edit_controllable_gen
```

选择。对于 t2va，建议先关闭 DINO、LPIPS、ArcFace 和 GroundingDINO，只保留检查清单，以便先验证第 14 维度的清单和视频评委流程。

---

**User**

我想把14维度的配置也写入到task_t2va_example.yaml可以吗，分析一下可以吗，不要修改代码

---

**Cursor**

可以。先基于现有的任务配置结构和第 14 维度的适用条件，确认把它并入 `task_t2va_example.yaml` 后哪些子项会生效、哪些会自动判定为不适用，以及哪些组件建议关闭。

目前结构上可以直接扩展同一个 YAML，因为 `dimension` 目前是单值，不能在一次运行里同时评估第 13 和第 14 维度；更准确的做法是把这个文件从“第 13 维度示例”改成“第 14 维度 t2va 示例”，或者复制出一个独立的 D14 配置。接下来我核对 D14 在 `t2va` 下的实际适用判定和默认组件权重。

可以，但需要注意：当前 `task` 配置的 `dimension` 是单值，因此一个 YAML 任务不能同时启用第 13 和第 14 维度。

也就是说，把第 14 维度写入 `task_t2va_example.yaml` 后，这个配置会从“运行 D13 的 t2va 任务”变成“运行 D14 的 t2va 任务”。D13 和 D14 需要分别运行，或者分别使用两个配置文件。

**t2va 下 D14 的适用性**

`t2va` 只有提示词和生成视频，没有首帧、尾帧或参考视频。因此：

- `local_edit_accuracy`：如果提示词包含明确编辑目标，则适用。
- `non_target_preservation`：通常适用，前提是提示词明确要求背景、主体、布局等内容保持不变。
- `subject_replacement`：只有提示词要求替换主体时适用。
- `add_remove_object`：只有提示词包含添加或移除物体时适用。
- `video_extension`：只有提示词明确要求续写或延长视频时适用。
- `first_last_frame`：t2va 没有首尾帧输入，因此不适用。

这些适用性主要由 D14 checklist 生成的事实决定，不需要在 YAML 中手动指定每个子项是否适用。

**推荐配置方式**

如果目标是先稳定运行 D14 的 checklist 评估，可以把任务配置的核心内容改成类似下面的结构：

```yaml
task_name: face50_t2va_d14
run_name: face50_t2va_d14

dimension: 14_edit_controllable_gen

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids:
    - t2va_06
    - t2va_07

evaluation:
  subpoints:
    local_edit_accuracy:
      components:
        checklist: true
    non_target_preservation:
      components:
        checklist: true
        dino_bg_consistency: false
        masked_lpips_static: false
    subject_replacement:
      components:
        checklist: true
        arcface_identity_keep: false
    add_remove_object:
      components:
        checklist: true
        gdino_presence: false
    video_extension:
      components:
        checklist: true
        continuation_seam_lpips: false
    first_last_frame:
      components:
        checklist: true
        endpoint_psnr: false
        endpoint_lpips: false

stages:
  - check
  - checklist
  - evaluate
  - score

workers: 1
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/face50_t2va_d14
```

这样做的含义是：

- 保留所有 D14 子项的 checklist 评分。
- 关闭需要额外模型或输入条件的数值组件。
- 不会执行 GroundingDINO、DINO、LPIPS、ArcFace 和首尾帧比较。
- 不适用的子项会由事实条件自动标记为 `not_applicable`，不会被错误计入均分。
- 保留完整的 D14 子项结构，后续可以逐项重新打开数值组件。

需要特别注意的是，当前 `run.py check` 阶段对 D14 仍然会静态检查 DINO、InsightFace 和 VMBench 依赖。即使配置中关闭了相应组件，`check` 阶段仍可能报告这些依赖缺失；这不代表评估阶段会实际执行这些关闭的组件。

因此，结论是：

1. **可以把 D14 配置写入现有的 `task_t2va_example.yaml`。**
2. 但写入后，该文件的 active dimension 应改为 `14_edit_controllable_gen`，不能同时继续作为 D13 配置使用。
3. 如果希望保留现有 D13 一键配置，最好复制成单独的 `task_t2va_d14_example.yaml`，这样两个任务的输出目录、分数含义和组件开关不会混淆。
4. 当前阶段建议采用 checklist-only D14 配置，等确认 D14 checklist 事实和评分结果符合预期后，再逐项启用 GroundingDINO、DINO、LPIPS 或 ArcFace。

---

**User**

为什么我前面配置了@task_t2va_example.yaml (15-16) ，还是跑了所有case？

---

**Cursor**

原因是：你看到的那次运行发生在当前 `case_ids` 配置生效之前，或者当时读取的配置文件版本中 `case_ids` 还是空列表。按照现在的代码和当前 YAML 内容，`t2va_06`、`t2va_07` 不会扩展成全部 25 个 case。

关键证据是那次终端输出：

```text
25 cases, with video: 25
...
[checklist] 25/25
```

而当前配置中的：

```yaml
case_ids:
  - t2va_06
  - t2va_07
```

会被 `load_task_cases()` 读取为两个明确的 case ID。代码逻辑是：

```python
selected_ids = input_cfg.get("case_ids") or []
if selected_ids:
    case_ids = [str(cid) for cid in selected_ids]
else:
    with os.scandir(root) as entries:
        case_ids = sorted(e.name for e in entries if e.is_dir(follow_symlinks=False))
```

只有 `case_ids` 为空或缺失时，才会枚举根目录下的全部子目录。因此当前配置下应该打印：

```text
2 cases, with video: 2
```

并且后续应只出现：

```text
t2va_06
t2va_07
```

你之前那次输出为 25 个 case，最可能的原因有两个：

1. **运行时配置文件还没有保存成当前版本**  
   当时 `case_ids` 可能是：

   ```yaml
   case_ids: []
   ```

   或者尚未加入这个字段。此时程序会自动枚举 `t2va` 根目录下的 25 个子目录。

2. **运行命令读取了另一个同名配置文件**  
   当前命令使用的是：

   ```bash
   tools/vgen_eval/.venv/bin/python \
     tools/vgen_eval/run.py \
     --task-config tools/vgen_eval/configs/task_t2va_example.yaml
   ```

   它实际读取的是当前工作目录下的：

   ```text
   /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_t2va_example.yaml
   ```

   如果终端当时所在目录不同，或者文件在运行过程中刚被编辑但命令已经启动，可能出现“编辑器当前内容”和“运行时读取内容”不一致。

另外，`case_ids` 的缩进本身不是问题。当前写法等价于：

```yaml
case_ids:
  - t2va_06
  - t2va_07
```

之前那次任务还实际完成了 `25` 个 checklist 和 `25` 个 evaluate，所以不是 `--limit` 或输出汇总阶段把两个 case 扩展成了 25 个；数量在最开始加载 case 时就已经是 25。对于当前代码，case 数量是在 `load_task_cases(task)` 返回后打印的，后面的阶段不会重新枚举 case。

因此可以用这条结论判断：

- 如果启动后第一行是 `2 cases, with video: 2`，筛选配置已生效。
- 如果启动后第一行仍是 `25 cases, with video: 25`，运行时读到的不是当前这份 `case_ids` 配置，重点检查命令路径、当前工作目录和文件是否已保存。

---

**User**

我现在想继续优化第14维度，第14维度的配置是否可以也配置到task_t2va_example.yaml中，同时不会影响到第13维度，分析一下，先不修改，

---

**Cursor**

我先核对当前任务配置的数据模型和运行入口，判断一个 YAML 是否支持多维度，以及把 D14 追加到现有 D13 配置会不会改变当前 D13 行为。

可以共用同一套 t2va 输入和 `case_ids`，但**不能在当前任务配置中同时启用第 13 和第 14 维度**。当前 `task_t2va_example.yaml` 的 `dimension` 是单值：

```yaml
dimension: 13_style_visual_control
```

运行入口会把这个值直接作为唯一维度：

```157:174:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py
        required = ("dimension", "input")
        missing = [key for key in required if key not in task]
        if missing:
            sys.exit(f"task config missing required keys: {missing}")
        # Task-file settings define a reproducible one-click run; CLI still chooses the scoring config.
        args.dataset = "task"
        task_root = os.path.expanduser(task["input"]["root"])
        task["input"]["root"] = os.path.abspath(os.path.join(task_base, task_root)) \
            if not os.path.isabs(task_root) else os.path.abspath(task_root)
        args.root = task["input"]["root"]
        args.dimension_override = task["dimension"]
        args.dimensions = task["dimension"]
        args.ids = ",".join(str(x) for x in (task["input"].get("case_ids") or []))
        args.limit = 0
```

因此有三种情况：

1. **保持 `dimension: 13_style_visual_control`，再加入 D14 配置**

   如果把 D14 子项直接加到当前 `evaluation.subpoints` 下，例如：

   ```yaml
   evaluation:
     subpoints:
       style_content_compat:
         ...
       local_edit_accuracy:
         ...
   ```

   程序不会同时运行 D14，而是会在配置校验阶段报错，因为 D14 的子项不属于当前 D13：

   ```python
   unknown_subpoints = set(overrides) - set(dim_cfg["subpoints"])
   ```

   也就是说，D14 配置不会被静默忽略，也不会影响 D13 评分；它会使这次任务无法正常启动。

2. **把 `dimension` 改成 D14**

   ```yaml
   dimension: 14_edit_controllable_gen
   ```

   这样会运行 D14，但当前这个 YAML 就不再运行 D13。D13 的配置块也不能继续作为有效配置使用。

3. **扩展代码，让一个任务支持多个维度**

   理论上可以把 `dimension` 改成维度列表，例如同时运行 D13 和 D14，但这需要修改任务加载、checklist、评估结果目录、汇总逻辑和配置校验。目前代码没有这个能力。当前 `run.py` 的评估阶段也是按每个 case 的单个 `c.dimension` 查找评估器：

```205:224:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py
        todo = [c for c in cases if c.video]
        skipped = [c.case_id for c in cases if not c.video]
        if skipped:
            print(f"skipping {len(skipped)} cases without video", flush=True)
        for i, c in enumerate(todo, 1):
            cl = load_checklist(args.out, c)
            if cl is None:
                print(f"[evaluate] {c.case_id}: no checklist, run the checklist stage first", flush=True)
                continue
            rdir = os.path.join(run_dir, c.dimension, c.case_id)
            os.makedirs(rdir, exist_ok=True)
            ctx = Context(case=c, checklist=cl, cfg=cfg, results_dir=rdir, media_root=args.out,
                          vision_client_factory=vision_client, audio_client_factory=audio_client,
                          judge_fps=args.judge_fps, judge_max_frames=args.judge_max_frames, force=args.force)
            t0 = time.time()
            try:
                res = REGISTRY[c.dimension]().evaluate(ctx)
```

**最稳妥的方案**是保留当前文件作为 D13 配置，再建立一个独立的 D14 配置。两个配置可以完全复用：

- 相同的 `input.root`
- 相同的 `mode: t2va`
- 相同的 `prompt_filename`
- 相同的 `video_filename`
- 相同的 `case_ids`

但需要使用不同的：

```yaml
task_name:
run_name:
dimension:
output_dir:
```

例如：

```yaml
# D13
task_name: face50_t2va_d13
run_name: face50_t2va_d13
dimension: 13_style_visual_control
output_dir: /.../face50_t2va_d13
```

```yaml
# D14
task_name: face50_t2va_d14
run_name: face50_t2va_d14
dimension: 14_edit_controllable_gen
output_dir: /.../face50_t2va_d14
```

这样可以保证：

- 第 13 维度原有配置和结果完全不变。
- 第 14 维度使用同样的两个 t2va case。
- 两个维度的 checklist、`result.json`、summary 和缓存互不覆盖。
- 你当前 `case_ids` 中的 `t2va_06`、`t2va_07` 可以在两个任务中复用。

如果只是把 D14 配置作为 YAML 注释或文档示例放进 `task_t2va_example.yaml`，不会影响 D13，但它也不会被程序执行。

---

**User**

我的意思就是再创建一个D14的配置，但是可不可以还在这个文件中，只需要改一些参数？

---

**Cursor**

可以。你可以继续使用同一个 `task_t2va_example.yaml`，每次运行前只修改少数任务参数；这样不会影响已经完成的 D13 结果文件。

需要修改的是：

```yaml
task_name: face50_t2va_d14
run_name: face50_t2va_d14

dimension: 14_edit_controllable_gen
```

同时把原来 D13 的 `evaluation.subpoints` 替换为 D14 的组件配置，例如 checklist-only 版本：

```yaml
evaluation:
  subpoints:
    local_edit_accuracy:
      components:
        checklist: true
    non_target_preservation:
      components:
        checklist: true
        dino_bg_consistency: false
        masked_lpips_static: false
    subject_replacement:
      components:
        checklist: true
        arcface_identity_keep: false
    add_remove_object:
      components:
        checklist: true
        gdino_presence: false
    video_extension:
      components:
        checklist: true
        continuation_seam_lpips: false
    first_last_frame:
      components:
        checklist: true
        endpoint_psnr: false
        endpoint_lpips: false
```

输入部分可以保持不变：

```yaml
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids:
    - t2va_06
    - t2va_07
```

但必须把输出目录也改成 D14 独立目录：

```yaml
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/face50_t2va_d14
```

原因是评估结果、checklist 缓存和汇总文件都会写到 `output_dir` 下。D13 当前结果在类似下面的目录中：

```text
.../face50_t2va_d13_test/
```

只要 D14 使用新的 `output_dir` 和新的 `run_name`，就不会覆盖或改变 D13 的结果。

需要区分两件事：

- **结果不会受影响**：已经生成的 D13 `result.json`、checklist 和 summary 不会被修改。
- **配置文件的当前含义会改变**：修改完成后，这个 YAML 就代表 D14，不再代表 D13。

因此，你可以按下面的方式使用同一个文件：

1. 当前配置用于运行 D13。
2. 需要运行 D14 时，修改 `task_name`、`run_name`、`dimension`、`evaluation` 和 `output_dir`。
3. 需要再次运行 D13 时，再把这些参数改回 D13。

不过，这种方式不会同时保存两个可复现的任务定义。为了长期保留 D13 和 D14 的配置，最好最终复制为：

```text
task_t2va_d13.yaml
task_t2va_d14.yaml
```

这只涉及配置文件复制和参数调整，不需要修改代码。

---

**User**

那目前是否可以把13维度的fl2va，r2va，t2va合在一个配置文件中，通过mode的配置，来选择不同的模式？这样13维度就只需要一个配置文件了？

---

**Cursor**

可以做到“**一个配置文件作为 D13 的通用模板**”，但当前代码不支持在一次运行中通过配置同时选择并执行 `t2va`、`fl2va`、`r2va` 三种模式。

具体分两种情况：

**1. 一个文件，手动修改 `mode` 后分别运行：可以**

保留：

```yaml
dimension: 13_style_visual_control
```

每次运行时修改以下字段：

```yaml
run_name:
input:
  root:
  mode:
  references:
output_dir:
```

三种模式的配置差异如下：

- `t2va`
  - `mode: t2va`
  - 不需要 `references`
  - 只读取 prompt 和 video
- `fl2va`
  - `mode: fl2va`
  - 需要配置 `first_frame_filename`
  - 需要配置 `last_frame_filename`
- `r2va`
  - `mode: r2va`
  - 需要配置 `image_pattern`、`video_pattern`、`audio_pattern`
  - 只读取 prompt 中实际引用的素材

因为当前三个数据目录分别是 `t2va`、`fl2va` 和 `ref2va`，所以 `root` 也要随模式切换。输出目录和 `run_name` 也应分别设置，避免不同模式的结果互相覆盖。

例如：

```yaml
# t2va
run_name: face50_t2va_d13
dimension: 13_style_visual_control

input:
  root: /.../face_50cases_sxdevops/t2va
  mode: t2va
```

改为：

```yaml
# fl2va
run_name: face50_fl2va_d13
dimension: 13_style_visual_control

input:
  root: /.../face_50cases_sxdevops/fl2va
  mode: fl2va
  references:
    first_frame_filename: input_01
    last_frame_filename: input_02
```

再改为：

```yaml
# r2va
run_name: face50_r2va_d13
dimension: 13_style_visual_control

input:
  root: /.../face_50cases_sxdevops/ref2va
  mode: r2va
  references:
    image_pattern: input_{index:02d}
    video_pattern: ref_video_{index:02d}
    audio_pattern: ref_audio_{index:02d}
```

当前加载器会根据单个 `mode` 的值选择对应逻辑：

```192:209:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/cases.py
    mode = str(input_cfg["mode"]).lower()
    mode_to_form = {"t2va": "t2va", "f2va": "f2va", "l2va": "l2va",
                    "fl2va": "fl2va", "r2va": "r2va"}
    if mode not in mode_to_form:
        raise ValueError(f"unsupported task input mode: {mode}")
```

因此，当前 `mode` 必须是一个字符串，不能直接写成：

```yaml
mode:
  - t2va
  - fl2va
  - r2va
```

也不能写成多个 profile 后期待程序自动选择，例如：

```yaml
modes:
  t2va:
    ...
  fl2va:
    ...
  r2va:
    ...
```

现有程序不会解析这种结构。

**2. 一个文件，一次命令自动运行三种模式：当前不可以**

当前任务配置只接受一个 `dimension` 和一个 `input`。运行入口会把配置中的单个模式直接传给任务加载器：

```165:174:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py
        args.dataset = "task"
        task_root = os.path.expanduser(task["input"]["root"])
        task["input"]["root"] = os.path.abspath(os.path.join(task_base, task_root)) \
            if not os.path.isabs(task_root) else os.path.abspath(task_root)
        args.root = task["input"]["root"]
        args.dimension_override = task["dimension"]
        args.dimensions = task["dimension"]
```

而且一个任务的 `run_name`、`output_dir`、checklist 缓存和汇总目录也是单份的。如果一次加载三个模式，需要额外设计：

- 多模式 case 加载；
- 每个模式独立的输入根目录和参考素材规则；
- 每个模式独立的 `run_name` 和输出目录；
- checklist 缓存按模式隔离；
- 三种模式分别汇总，不能混成一个均分；
- 任务配置校验需要支持多个 input profile。

**结论**

目前最合适的是：

- 保留一个 `task_t2va_example.yaml` 作为 D13 通用配置模板；
- 每次只修改 `mode`、`root`、`references`、`run_name` 和 `output_dir`；
- 分别运行三次；
- 三种模式仍然是三个独立结果集。

这样可以只维护一个配置文件，但它本质上是“**手动切换模式的模板**”，不是“一个命令自动评估三种模式的多模式配置”。

如果希望真正做到只改 `mode`，连 `root`、`references`、`run_name` 和 `output_dir` 都自动联动，就需要扩展任务配置格式或增加一个配置 profile 机制。当前代码和 YAML 还没有这个能力。

---

**User**

我一次只需要评估一个，每次评估前会配置参数，分析一下

---

**Cursor**

可以。既然你每次只评估一种输入模式，那么**一个配置文件手动切换参数后重复使用**是合适的，不需要同时扩展为多模式任务。

每次运行前主要调整以下内容：

```yaml
task_name:
run_name:
dimension: 13_style_visual_control

input:
  root:
  mode:
  case_ids:
  references:

output_dir:
```

`dimension` 始终保持：

```yaml
dimension: 13_style_visual_control
```

D13 的 `evaluation.subpoints` 也可以保持不变。当前配置中关闭 FIRM 和 palette match 的设置对三种模式都适用，不会因为切换 `t2va`、`fl2va`、`r2va` 而改变 D13 的评分结构。

具体切换时：

- `t2va`
  - `root` 指向 `.../t2va`
  - `mode: t2va`
  - 不写 `references`
  - `case_ids` 使用 t2va 目录下实际存在的 case ID

- `fl2va`
  - `root` 指向 `.../fl2va`
  - `mode: fl2va`
  - 配置：
    ```yaml
    references:
      first_frame_filename: input_01
      last_frame_filename: input_02
    ```
  - `case_ids` 使用 fl2va 目录下实际存在的 case ID

- `r2va`
  - `root` 指向 `.../ref2va`
  - `mode: r2va`
  - 配置参考素材规则：
    ```yaml
    references:
      image_pattern: input_{index:02d}
      video_pattern: ref_video_{index:02d}
      audio_pattern: ref_audio_{index:02d}
      image_extensions: [.png, .jpg, .jpeg, .webp]
      video_extensions: [.mp4, .mov, .webm]
      audio_extensions: [.mp3, .wav, .m4a, .flac, .aac]
    ```
  - 只会加载 prompt 中实际引用的参考素材

需要特别保持独立的是 `run_name` 和 `output_dir`。例如：

```yaml
run_name: face50_fl2va_d13
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/face50_fl2va_d13
```

这样每种模式的 checklist、评估结果和汇总文件都会保存到不同目录，不会覆盖之前的 D13 结果。

当前配置的 `mode` 是单个字符串，程序每次只加载一个模式；这正好符合你的使用方式。也就是说，你不需要让一个文件同时声明三个模式，只需要在每次运行前改成当前任务对应的参数即可。

建议把文件名从 `task_t2va_example.yaml` 改成更通用的名字，例如 `task_d13_example.yaml`，因为它实际会轮流用于三种模式。不过这只是命名建议，不改名也不影响运行。

---

**User**

你现在给我完成一下上面的要求吧，修改完你不要进行全量测试，

---

**Cursor**

我会把 `task_t2va_example.yaml` 整理成一个可复用的 D13 配置模板：保留单次运行的 `mode` 选择，并在同一文件中写清楚 `t2va`、`fl2va`、`r2va` 切换时需要调整的路径和参考素材字段。不会改评测代码，也不会做全量评估。

已完成配置文件修改：现在仍默认运行 `t2va`，同时把 `fl2va` 和 `r2va` 的切换方式放进同一个文件的注释模板中。接下来只做 YAML 语法和内容级检查，不启动评估流程，也不进行全量测试。

已按要求完成修改，未修改评测代码，也没有进行全量测试。

修改文件：

[task_t2va_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_t2va_example.yaml)

现在这个文件是一个可复用的第 13 维度配置模板：

- 默认仍然是 `t2va`。
- 每次只评估一种模式。
- 通过修改 `input.mode` 切换 `t2va`、`fl2va`、`r2va`。
- 注释中已写明三种模式对应的 `root`、`case_ids` 和 `references` 配置。
- D13 的评分配置保持不变，仍关闭 `firm_world_consistency` 和 `palette_match`。
- 已提醒每种模式使用独立的 `task_name`、`run_name` 和 `output_dir`，避免结果互相覆盖。

当前默认配置仍为：

```yaml
dimension: 13_style_visual_control
mode: t2va
case_ids:
  - t2va_06
  - t2va_07
```

只进行了 YAML 解析检查，结果通过：

```text
YAML OK: face50_t2va_d13 t2va ['t2va_06', 't2va_07']
```

没有启动 checklist、evaluate 或 score 阶段。

---

**User**

那目前文件名是不是也需要改一下，目前只有t2va

---

**Cursor**

是的，建议改名。现在这个文件已经不是只服务 `t2va`，而是第 13 维度的单模式复用模板；`task_t2va_example.yaml` 会让人误以为它只能用于 `t2va`。我先检查仓库内是否有引用这个旧文件名，再决定是否只改名或同步更新引用。

建议改名，但这不是运行必需条件。

当前文件已经可以手动切换 `t2va`、`fl2va`、`r2va`，继续叫 `task_t2va_example.yaml` 会产生误导，让人以为它只用于 `t2va`。更合适的名称是：

```text
task_face50_d13_example.yaml
```

这个名称同时表达了：

- `face50`：当前配置使用的案例目录；
- `d13`：配置服务第 13 维度；
- 不绑定某一种输入模式。

改名后，命令应改为：

```bash
tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_face50_d13_example.yaml
```

还需要同步更新文档中的旧引用：

```text
tools/vgen_eval/docs/task_config_and_input_allowlist.md
```

其中示例命令目前仍引用：

```text
task_t2va_example.yaml
```

需要改成新的文件名。

另外，配置文件内部的默认值仍然可以保留：

```yaml
task_name: face50_t2va_d13
run_name: face50_t2va_d13
mode: t2va
```

因为当前默认运行模式仍是 `t2va`。切换到 `fl2va` 或 `r2va` 时，再修改 `task_name`、`run_name`、`root`、`mode`、`case_ids`、`references` 和 `output_dir`。

结论是：**建议改成 `task_face50_d13_example.yaml`，并同步更新文档引用；文件名本身不会影响程序执行。**

---

**User**

你给我改成一个通用的名字，不要争对face，这个face文件夹只是我目前用作测试的，

---

**Cursor**

我会把配置文件改成不绑定具体数据集或输入模式的名称，采用 `task_d13_example.yaml`，并同步更新说明文档中的命令引用。文件内部当前默认仍保留 t2va 测试参数，因为名称通用不等于默认输入目录自动通用；这次只处理命名和引用，不做评估测试。

<thinking>**Renaming config to generic D13 name****Updating documentation reference**</thinking>

<thinking>**Verifying generic filename and stale references****Checking renamed config and documentation consistency**</thinking>
文件已改名为 `task_d13_example.yaml`，并同步更新了文档中的启动命令。现在检查旧文件名是否还有引用，并确认新文件仍能正常解析。

已将配置文件改名为通用名称：

[task_d13_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d13_example.yaml)

同时更新了文档中的启动命令：

[task_config_and_input_allowlist.md](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/docs/task_config_and_input_allowlist.md)

当前文件名不再绑定 `t2va` 或 `face`，可用于第 13 维度的 `t2va`、`fl2va`、`r2va` 单次模式评估。文件内部的默认参数仍然指向当前用于测试的 `face50` t2va 目录，并保留：

```yaml
task_name: face50_t2va_d13
run_name: face50_t2va_d13
mode: t2va
```

这是为了让配置保持可直接运行。切换到正式数据时，只需修改 `task_name`、`run_name`、`input.root`、`mode`、`case_ids`、`references` 和 `output_dir`。

已完成 YAML 解析检查，结果通过；没有启动 checklist、evaluate 或 score，也没有进行全量测试。

---

**User**

如果我现在需要测试fl2va的，我怎么修改我的配置？

---

**Cursor**

测试 `fl2va` 时，在 `task_d13_example.yaml` 中修改任务名称、输入目录、模式、案例列表和输出目录即可。D13 的 `dimension` 和 `evaluation` 配置保持不变。

将相关部分改成：

```yaml
task_name: face50_fl2va_d13
run_name: face50_fl2va_d13

dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/fl2va
  mode: fl2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4

  # [] 表示评估 fl2va 目录下的所有直接子目录。
  case_ids: []

  references:
    first_frame_filename: input_01
    last_frame_filename: input_02
```

然后把输出目录改成独立的 D13 fl2va 目录：

```yaml
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/face50_fl2va_d13
```

每个案例目录应类似：

```text
fl2va/
  <case_id>/
    prompt_final.txt
    video.mp4
    input_01.png
    input_02.png
```

这里的 `input_01` 和 `input_02` 不需要写扩展名，程序会在配置的图片扩展名中查找，例如 `.png`、`.jpg`、`.jpeg` 和 `.webp`。

如果只想测试指定案例，把 `case_ids: []` 改成实际存在的 fl2va 案例目录名，例如：

```yaml
case_ids:
  - fl2va_06
  - fl2va_07
```

案例 ID 必须以 `fl2va` 目录下的实际子目录名为准，不能直接假设与 t2va 的 ID 相同。

运行命令：

```bash
tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_d13_example.yaml
```

切换到 `fl2va` 时，原来 t2va 的 `case_ids`、`root`、`run_name` 和 `output_dir` 不应继续保留。这样新结果会写入 `face50_fl2va_d13`，不会覆盖已有的 t2va 结果。

---

**User**

fl2va模式目前支持f2va和l2va吗？

---

**Cursor**

我核对一下当前输入加载器对 `f2va`、`l2va`、`fl2va` 的分支，以及三个模式分别要求哪些参考帧，然后给你明确结论。

<thinking>**Explaining that fl2va is separate from f2va/l2va**</thinking>
目前支持，但需要区分：

- `f2va`：只使用首帧输入。
- `l2va`：只使用尾帧输入。
- `fl2va`：同时使用首帧和尾帧输入。

代码中这三个模式是独立的 `mode` 值：

```python
mode_to_form = {
    "t2va": "t2va",
    "f2va": "f2va",
    "l2va": "l2va",
    "fl2va": "fl2va",
    "r2va": "r2va",
}
```

对应的参考帧要求是：

```python
if mode in ("f2va", "fl2va"):
    # 要求 first_frame_filename

if mode in ("l2va", "fl2va"):
    # 要求 last_frame_filename
```

因此：

- 设置 `mode: f2va` 时，只需要 `references.first_frame_filename`。
- 设置 `mode: l2va` 时，只需要 `references.last_frame_filename`。
- 设置 `mode: fl2va` 时，两个字段都必须配置。

例如，测试 `f2va`：

```yaml
task_name: face50_f2va_d13
run_name: face50_f2va_d13

dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/f2va
  mode: f2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
  references:
    first_frame_filename: input_01
```

测试 `l2va`：

```yaml
task_name: face50_l2va_d13
run_name: face50_l2va_d13

dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/l2va
  mode: l2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
  references:
    last_frame_filename: input_01
```

测试 `fl2va`：

```yaml
task_name: face50_fl2va_d13
run_name: face50_fl2va_d13

dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_924/face_50cases_sxdevops/fl2va
  mode: fl2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
  references:
    first_frame_filename: input_01
    last_frame_filename: input_02
```

三种模式下，每个案例目录都应包含：

```text
<case_id>/
  prompt_final.txt
  video.mp4
  input_01.png
  input_02.png
```

但实际使用时：

- `f2va` 只要求 `input_01`。
- `l2va` 只要求 `input_01`，它会被配置为尾帧。
- `fl2va` 要求 `input_01` 和 `input_02`，分别作为首帧和尾帧。

当前的 `task_d13_example.yaml` 可以支持这三种模式，但每次只能选择一个 `mode`。切换时需要同步修改：

- `input.root`
- `input.mode`
- `input.references`
- `case_ids`
- `task_name`
- `run_name`
- `output_dir`

特别是 `f2va` 和 `l2va` 不能复用 `fl2va` 的两帧配置，否则会因为缺少对应文件或模式要求不匹配而失败。

---

**User**

目前的分数可以不要四舍五入吗？分析一下

---

**Cursor**

<thinking>**Inspecting score precision and serialization paths**</thinking>
可以分析。关键要区分“内部计算精度”和“最终显示/保存精度”：我先检查 D13 当前的聚合、Markdown 输出和 JSON 保存是否存在显式四舍五入。

可以，但要先区分两种情况：

1. **取消最终分数的显示截断/四舍五入**
2. **取消评分过程中 `round_to: 0.5` 带来的半分量化**

当前系统确实存在多层四舍五入。

**当前的四舍五入位置**

第一层是子项合成分数。配置中目前设置了：

```yaml
scoring:
  round_to: 0.5
```

子项合成后会按这个步长处理：

```20:21:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/scoring.py
def _round(x: float, step: float) -> float:
    return round(x / step) * step if step else x
```

```109:114:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/scoring.py
    score = sum(s * w for s, w in used.values()) / sum(w for _, w in used.values())
    core_failed = comps.get("checklist", {}).get("core_failed") or []
    if core_failed:
        score = min(score, float(cfg["scoring"]["core_fail_cap"]))
    return {"score": _round(score, cfg["scoring"].get("round_to", 0.5)), "status": "ok",
```

这意味着子项分数可能从原始的 `4.166666...` 变成 `4.0` 或 `4.5`。

第二层是维度平均分，当前保留三位小数：

```145:147:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/scoring.py
    vals = [r["score"] for r in subpoint_results.values() if r.get("status") == "ok" and r.get("score") is not None]
    out = {"score": round(float(np.mean(vals)), 3) if vals else None,
```

第三层是所有 case 的汇总平均分，也保留三位小数：

```168:171:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/scoring.py
                 "score": round(float(np.mean([r["result"]["score"] for r in valid])), 3) if valid else None,
                 "subpoints": {sp: {"mean": round(float(np.mean(v)), 3), "n": len(v)} for sp, v in sp_scores.items()}}
```

第 13 维度还有一个 `comparable_score`，也保留三位小数：

```101:104:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d13.py
        result["comparable_score"] = round(sum(comparable_values) / len(comparable_values), 3) \
            if not gate_failed and comparable_values else None
```

**仅修改 `round_to` 是否足够？**

不完全够。

如果把配置改成：

```yaml
round_to: 0
```

那么可以取消子项合成阶段的 `0.5` 步长量化，因为 `_round()` 在 `step == 0` 时直接返回原值。

但是：

- 维度分数仍然会被 `round(..., 3)` 处理；
- 汇总分数仍然会被 `round(..., 3)` 处理；
- D13 的 `comparable_score` 仍然会被 `round(..., 3)` 处理。

所以这只能得到“子项不按 0.5 取整”，不能实现全流程完全保留精度。

**还要注意评分表本身的离散化**

即使取消所有 `round()`，当前 checklist 和数值指标仍然不是连续评分。它们通常会先根据阈值映射到 `1、2、3、4、5`：

```66:72:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/scoring.py
    rate = num / den
    score = map_checklist_rate(rate, scfg["checklist_rate"])
    if core_failed:
        score = min(score, float(scfg["core_fail_cap"]))
```

因此取消四舍五入后，变化主要发生在**多个组件按权重合成**和**多个子项求平均**的阶段。它不会把单个 checklist 或单个指标变成连续的原始分数。

例如：

- checklist 映射分数：`4`
- 某个视觉指标映射分数：`5`
- 权重：`0.4` 和 `0.6`

原始子项合成分数是：

```text
4 * 0.4 + 5 * 0.6 = 4.6
```

当前 `round_to: 0.5` 可能把它变成 `4.5`。取消后会保留 `4.6`。

**建议**

从评估透明度看，建议取消 `round_to: 0.5`，因为它会让加权结果产生额外的信息损失。比较合理的方案是：

- 子项分数保留完整浮点值；
- 维度分数和总汇总分数保留三位小数，便于阅读；
- 如果需要审计，再额外保存未格式化的原始中间值。

如果你的要求是“最终 JSON、终端和 Markdown 全部不四舍五入”，则需要同时调整：

- `round_to: 0`；
- `score_dimension()` 中的 `round(..., 3)`；
- `aggregate()` 中的两个 `round(..., 3)`；
- D13 中 `comparable_score` 的 `round(..., 3)`；
- 可能还要处理 Markdown 展示格式。

这会导致输出出现类似：

```text
4.166666666666667
```

而不是：

```text
4.167
```

因此，结论是：

- **可以取消当前的四舍五入。**
- 仅改 `round_to: 0` 可以取消 `0.5` 步长量化，但不能取消全部三位小数处理。
- 当前分数中最明显的取整来源是 `round_to: 0.5`。
- 更推荐保留内部高精度，同时最终展示保留三位小数；如果需要完整原始精度，再单独增加 raw score 字段，而不是让所有报告直接显示长浮点数。

---

**User**

从评估透明度看，建议取消 round_to: 0.5，因为它会让加权结果产生额外的信息损失。比较合理的方案是：

子项分数保留完整浮点值；
维度分数和总汇总分数保留三位小数，便于阅读；
如果需要审计，再额外保存未格式化的原始中间值。
按照你的这个建议来取消

---

**Cursor**

我会按这个方案落地：取消子项合成时的 `0.5` 步长量化；子项 `score` 保留完整加权浮点值，并增加 `raw_score` 便于审计；维度和汇总层继续以三位小数作为展示/主分数，同时保存未截断的 `raw_score`。我会同步处理 D13 的 `comparable_score`，然后只做静态语法和小型纯函数验证，不启动模型评估。

<thinking>**Implementing precision-preserving score fields****Editing scoring precision and audit fields****Updating config to disable quantization**

<thinking>**Applying score precision changes****Implementing raw score preservation in scoring.py****Updating scoring output precision**

<thinking>**Extending raw score preservation to dimensions and aggregates****Adding raw_score fields without changing readable output****Preserving full precision in JSON audit fields**

<thinking>**Refining aggregate precision semantics****Ensuring summary uses raw values before three-decimal display****Adding raw means for auditability**

<thinking>**Reviewing edited scoring sections before next patch****Inspecting current precision fields for consistency**

<thinking>**Reviewing edited scoring sections before next patch****Inspecting current precision fields for consistency**</thinking>
子项层已经改为保留完整加权值。现在补齐聚合层：主 `score` 继续保留三位小数，新增 `raw_score` 使用未截断值计算；这样后续汇总不会把已经展示过的三位小数再次拿来平均。D13 的可比评分也会保留对应的原始字段。

<thinking>**Adding D13 comparable raw score****Implementing raw comparable score field**

<thinking>**Reviewing precision changes and checking for regressions****Inspecting scoring code after edits**

<thinking>**Updating audit preservation and stale documentation****Patching raw score handling and documentation**</thinking>
检查后发现，核心逻辑已经符合方案，但还需要两处收尾：让维度平均明确基于子项的 `raw_score`，以及更新文档中仍写着“按 0.5 四舍五入”的说明，避免实现和文档不一致。不会运行模型或全量评估。

<thinking>**Fixing variable reference after precision refactor****Updating comparable score raw source****Correcting undefined vals introduced by refactor**

<thinking>**Updating documentation for precision semantics****Updating workflow and evaluation docs to match score precision**

<thinking>**Reviewing documentation scope and formula formatting constraints****Reverting nonessential markdown edits to avoid broad doc churn**</thinking>
实现逻辑已经完成。文档中的旧表述分散在多个维度说明里，而这些 Markdown 文件还包含原有的公式格式；为避免这次精度修改引入与需求无关的大范围文档格式变更，我会撤回本次对 Markdown 的改动，只保留评分配置和 Python 输出逻辑的修改。核心行为以代码和配置为准。

<thinking>**Validating modified Python and scoring behavior****Running syntax check and pure scoring precision test****Checking no evaluation process is started**</thinking>
我已撤回文档改动，保留了以下实现范围：`dims_13_18.yaml` 的 `round_to: 0`、评分结果中的 `raw_score` 字段、维度和汇总的三位小数主分数，以及 D13 的原始可比评分字段。现在进行 Python 语法检查和不依赖模型的加权分数验证。

刚才的纯函数验证只因测试命令没有把 `tools/vgen_eval` 加入 Python 模块路径而失败，代码语法检查和 YAML 检查均已通过；这不是评估逻辑错误。我补充正确的模块路径后重跑同一个轻量验证，不启动任何模型。

已按你的方案完成修改，未启动模型评估，也没有进行全量测试。

修改内容：

- `round_to` 从 `0.5` 改为 `0`，取消子项分数按半分取整。
- 子项合成分保留完整浮点值：
  - `score`：完整子项分；
  - `raw_score`：同样保存未截断值，便于审计。
- 维度主分数继续保留三位小数。
- 维度结果新增 `raw_score`，保存未截断的维度均值。
- 汇总主分数继续保留三位小数。
- 汇总结果新增：
  - 维度级 `raw_score`；
  - 子项级 `raw_mean`。
- D13 新增：
  - `raw_full_score`；
  - `raw_comparable_score`。
- 门槛失败和音频门失败的最低分仍保持 `1.0`，并同步保存 `raw_score: 1.0`。

涉及文件：

- [dims_13_18.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/dims_13_18.yaml)
- [scoring.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/scoring.py)
- [d13.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d13.py)

验证结果：

```text
round_to OK: 0
precision OK: 4.6 4.6
```

Python 语法检查也已通过。当前不会再出现子项分数被强制变成 `4.0`、`4.5` 这类半分值；例如加权结果 `4.6` 会保留为 `4.6`。维度和最终汇总仍显示为三位小数，同时保留原始浮点值供审计。

---

**User**

目前/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs路径下的文件是不是只有task_d13_example.yaml起到作用，其他的是不是已经没用了？

---

**Cursor**

<thinking>**Inspecting config directory usage and references**</thinking>我检查配置目录中的文件类型和代码/脚本引用，区分“运行时仍会读取的基础配置”和“只是示例任务文件”，再给你准确结论。

不是。当前 `configs` 目录下的文件分为三类，作用不同。

**1. `dims_13_18.yaml` 仍然是核心配置**

它不是示例文件，而是评测的默认评分配置，包含：

- 第 13 到第 18 维度；
- 子项定义；
- 组件权重；
- 适用条件；
- 指标阈值；
- checklist 评分映射；
- 当前的 `round_to: 0` 精度设置。

`run.py` 默认会读取它：

```143:143:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py
    ap.add_argument("--config", default=os.path.join(HERE, "configs", "dims_13_18.yaml"))
```

所以即使使用：

```bash
--task-config tools/vgen_eval/configs/task_d13_example.yaml
```

实际评分仍然依赖 `dims_13_18.yaml`。

**2. `judge_servers.yaml` 仍然会被裁判服务使用**

它负责配置视觉裁判和音频裁判服务，包括：

- GPU；
- 端口；
- 模型路径；
- served model name；
- 显存比例；
- 并发数；
- 上下文长度；
- 多模态输入限制。

两个服务启动脚本默认会读取它：

```3:8:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/scripts/serve_judge.sh
# Usage: JUDGE_CONFIG=../configs/judge_servers.yaml bash scripts/serve_judge.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${JUDGE_CONFIG:-${ROOT}/configs/judge_servers.yaml}"
RESOLVER="${ROOT}/scripts/resolve_judge_config.py"
```

因此它也不是废弃文件。

**3. 三个 task 配置文件**

这三个文件都是任务配置，不会被程序自动全部读取。只有命令明确指定某个文件时，它才会生效。

当前推荐使用：

```text
task_d13_example.yaml
```

它是 D13 的通用单模式模板，默认是 `t2va`，通过修改 `mode`、`root` 和 `references` 可以切换到 `f2va`、`l2va`、`fl2va` 或 `r2va`。

另外两个文件：

```text
task_fl2va_example.yaml
task_r2va_example.yaml
```

仍然可以单独使用，例如：

```bash
tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_fl2va_example.yaml
```

但它们现在属于**旧的独立示例配置**，不是程序运行时自动依赖的配置。如果你决定以后统一只维护 `task_d13_example.yaml`，可以删除这两个文件，不会影响：

- `dims_13_18.yaml`；
- `judge_servers.yaml`；
- `run.py`；
- 已经生成的评估结果；
- D13 的实际评分逻辑。

删除它们的代价是失去两个已经填好的 `fl2va` 和 `r2va` 配置快照。之后切换模式时，需要在 `task_d13_example.yaml` 中手动修改参数。

所以当前可以这样理解：

- **必须保留**：`dims_13_18.yaml`、`judge_servers.yaml`；
- **当前主用**：`task_d13_example.yaml`；
- **可选保留**：`task_fl2va_example.yaml`、`task_r2va_example.yaml`；
- **不会自动生效**：没有命令显式指定的 task 配置文件。

---

**User**

我现在想开始把14维度的配置也和13维度的这个配置一样，如果想测试第14维度  就手动修改配置中的文件，来进行相对应的测试，所以你给我创建一下。

---

**Cursor**

<thinking>**Creating reusable D14 task configuration**</thinking>我会新建独立的 `task_d14_example.yaml`，不改动现有 D13 配置和评测代码。它会沿用同样的单模式切换方式，默认使用当前 t2va 测试参数；切换到 `f2va`、`l2va`、`fl2va` 或 `r2va` 时，只需手动修改输入路径、`mode`、案例和参考素材配置。D14 默认采用 checklist-only，把需要额外模型的数值组件显式关闭。

<thinking>**Validating D14 YAML and override compatibility****Checking config against dimension schema without evaluation**

已创建第 14 维度的通用配置文件：

[task_d14_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d14_example.yaml)

配置特点：

- `dimension` 已设置为 `14_edit_controllable_gen`。
- 默认使用当前 t2va 测试参数：
  - `mode: t2va`
  - case：`t2va_06`、`t2va_07`
- 同一个文件支持手动切换：
  - `t2va`
  - `f2va`
  - `l2va`
  - `fl2va`
  - `r2va`
- 已写好每种模式对应的 `root`、`references` 和参考素材配置说明。
- 默认保留所有 D14 checklist 评分。
- 默认关闭 DINO、LPIPS、ArcFace、GroundingDINO 和首尾帧数值组件。
- 使用独立的 `task_d14_t2va`、`run_name` 和输出目录，不会覆盖第 13 维度结果。

运行命令：

```bash
tools/vgen_eval/.venv/bin/python \
  tools/vgen_eval/run.py \
  --task-config tools/vgen_eval/configs/task_d14_example.yaml
```

切换模式时，需要同步修改：

```yaml
task_name:
run_name:
input:
  root:
  mode:
  case_ids:
  references:
output_dir:
```

配置校验已通过，YAML 和 D14 组件开关均合法；没有启动 checklist、evaluate 或 score，也没有进行全量测试。

补充一点：虽然当前 D14 配置关闭了数值组件，但 `check` 阶段对 D14 的依赖检查仍是静态配置，可能继续报告 DINO、InsightFace 或 VMBench 缺失。这不会改变评估阶段跳过已关闭组件的行为。

---

**User**

目前14维度的各子项会运行哪些模型？

---

**Cursor**

目前按照 [task_d14_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d14_example.yaml) 的配置，第 14 维度是 **checklist-only**，各子项不会运行 DINO、LPIPS、ArcFace 或 GroundingDINO 等数值模型。

**实际会运行的模型**

每个 case 主要使用视觉裁判服务：

```text
Qwen3-VL-32B
地址：VGEN_JUDGE_URL，默认 http://127.0.0.1:8011/v1
```

它承担两类工作：

1. 根据 prompt 生成 D14 的 facts 和 checklist；
2. 根据视频回答 checklist 问题并计算 checklist 分数。

如果 checklist 中的问题被标记为音频或音视频模态，则还会调用音频裁判服务：

```text
Qwen2.5-Omni-7B
地址：VGEN_AUDIO_JUDGE_URL，默认 http://127.0.0.1:8012/v1
```

因此，是否实际调用 Qwen2.5-Omni，取决于 checklist 生成的问题是否包含音频或音视频判断；D14 本身主要是视觉评估，通常主要使用 Qwen3-VL。

**各子项当前配置**

| D14 子项 | 当前运行组件 | 当前不会运行的模型/组件 |
|---|---|---|
| `local_edit_accuracy` | checklist，使用 Qwen3-VL；若问题涉及音频，可能使用 Qwen2.5-Omni | 无额外数值模型 |
| `non_target_preservation` | checklist，使用 Qwen3-VL；可能按问题模态调用 Qwen2.5-Omni | DINO、masked LPIPS |
| `subject_replacement` | checklist，使用 Qwen3-VL；可能按问题模态调用 Qwen2.5-Omni | ArcFace / InsightFace |
| `add_remove_object` | checklist，使用 Qwen3-VL；可能按问题模态调用 Qwen2.5-Omni | GroundingDINO |
| `video_extension` | checklist，使用 Qwen3-VL；可能按问题模态调用 Qwen2.5-Omni | continuation seam LPIPS |
| `first_last_frame` | checklist，使用 Qwen3-VL；可能按问题模态调用 Qwen2.5-Omni | endpoint PSNR、endpoint LPIPS |

配置中的关闭项对应如下：

```yaml
non_target_preservation:
  dino_bg_consistency: false
  masked_lpips_static: false

subject_replacement:
  arcface_identity_keep: false

add_remove_object:
  gdino_presence: false

video_extension:
  continuation_seam_lpips: false

first_last_frame:
  endpoint_psnr: false
  endpoint_lpips: false
```

这些关闭组件会被标记为 `disabled`，不会加载模型，也不会执行计算；它们的权重不会参与子项合成，子项只使用 checklist 分数。

**当前各子项是否适用仍由 checklist facts 决定**

例如：

- prompt 没有编辑目标时，`local_edit_accuracy` 会是 `not_applicable`；
- 没有主体替换时，`subject_replacement` 会是 `not_applicable`；
- 没有添加或删除物体时，`add_remove_object` 会是 `not_applicable`；
- 没有续写意图时，`video_extension` 会是 `not_applicable`；
- t2va 没有首帧或尾帧输入，所以 `first_last_frame` 会是 `not_applicable`；
- `non_target_preservation` 是否适用取决于 checklist facts 和子项逻辑。

因此，当前 D14 运行的核心模型只有视觉裁判 `Qwen3-VL-32B`，音频裁判 `Qwen2.5-Omni-7B` 只会在生成的 checklist 包含音频相关问题时参与。

---

**User**

考虑一下时间和效果的成本，分析一下子项可以enable和disable的组件，先不要修改代码

---

**Cursor**

我会基于 D14 当前实现和配置，按“运行时间、额外依赖、结果增益、适用范围”逐项分析哪些组件值得开启，以及哪些适合继续关闭；本次只分析，不修改代码或配置。

我会先核对 D14 配置、组件注册与执行路径，重点比较每个开关的耗时、模型依赖、判别收益和适用条件；本轮只做分析，不修改代码。

目前已经确认一个关键点：数值组件的“成本”不仅取决于模型本身，还取决于当前调度器是否允许它的共享依赖执行。接下来我会把“理论上值得开”和“按现有代码直接打开后实际能否生效”分开给出结论。

<thinking>**Verifying exact source locations and model availability**</thinking>

<thinking>**Verifying operational timing documentation and case applicability**</thinking>目前的代码路径还揭示出一个实际限制：`gdino_edit_targets` 和 `endpoints` 是共享内部组件，但任务开关只暴露了外层数值名。因此某些开关即使在 YAML 中改成 `true`，按当前实现也不会真正执行。我会把这个限制纳入最终建议，并区分“修正依赖后值得打开”与“当前直接打开无效”。

结论是：**保留 checklist；数值组件按 case 条件选择性开启，不建议把所有组件全局打开。**最值得优先开启的是 `continuation_seam_lpips`、首尾帧组件和有可靠条件图时的 `arcface_identity_keep`。`GroundingDINO + DINO/LPIPS` 成本最高，应只对确实涉及目标区域或静态镜头的 case 开启。

**先说明当前实现的实际限制**

本轮没有修改代码，也没有下载模型。已检查到当前配置依赖的 InsightFace、DINO 权重和 VMBench 环境路径都存在。

但当前代码中有两个共享依赖问题：

- `dino_bg_consistency`、`masked_lpips_static` 和 `gdino_presence` 内部都依赖共享组件 `gdino_edit_targets`。任务配置只允许外层组件名，因此直接把这些开关改成 `true` 时，`gdino_edit_targets` 仍可能被 `Context.comp()` 判定为 disabled。
- `endpoint_psnr` 和 `endpoint_lpips` 内部共同调用 `endpoints`，但配置中没有暴露 `endpoints` 这个内部名称。因此首尾帧组件当前也不能仅通过 YAML 直接可靠启用。
- `V.endpoints()` 一次同时计算 PSNR 和 LPIPS。即使只想启用其中一个，后续修正依赖时也需要额外处理，否则可能出现两个结果一起计算或一起计分。

相关执行路径在 [d14.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d14.py:37) 和 [base.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/base.py:88) 中。

**按子项分析**

1. `local_edit_accuracy`

只有 checklist，没有额外数值组件。

建议：

- `checklist: true`
- 不需要增加其他开关
- 不能关闭 checklist

这是成本最低、也是当前唯一可用的局部修改准确性判断。核心 checklist 失败时，数值组件也不能把子项分数救回来，因为核心题失败会把子项上限限制为 2 分。

2. `non_target_preservation`

包含：

- checklist：权重 0.4
- `dino_bg_consistency`：权重 0.3
- `masked_lpips_static`：权重 0.3

`dino_bg_consistency`：

- 成本：较高。
- 需要 GroundingDINO 在锚点和最多 8 帧上检测目标，再用 DINO 对锚点和视频帧做 patch 特征比较。
- GroundingDINO 是主要成本，已有记录约为每条 5 秒视频 1–3 分钟。
- DINO 权重首次加载约 30 秒，加载后单条约 2 秒。
- 适合验证背景、布局、其他主体是否保持。
- 对镜头运动、光照变化和正常场景变化比较敏感。
- 对没有外部条件图的 `t2va`，锚点是生成视频第 0 帧，因此它验证的是“视频后续是否相对第 0 帧稳定”，不是与真实输入图进行严格比较。

建议：

- 静态编辑、目标明确、确实要求背景保持时，可以开启。
- 动态镜头或背景本身应该变化时，建议关闭。
- 不建议对所有 `t2va` case 全量开启，因为该子项当前没有 `applies` 限制，可能对非编辑视频也执行。

`masked_lpips_static`：

- 成本：模型加载后约 1.5–3 秒，但仍依赖 GroundingDINO。
- 只有 `facts.static_camera == true` 时才有效。
- 静态镜头中，它对目标框以外区域进行感知差异比较，针对背景变化比 checklist 更客观。
- 动态镜头会直接返回 `not_applicable`，因为合法的镜头运动会被误判为背景变化。

建议：

- `static_camera: true` 的 case 开启。
- 非静态镜头关闭。
- 对静态、局部替换、背景必须保持的 case，推荐和 DINO 一起开启；两者分别偏向特征一致性和感知像素一致性。
- 对 `t2va` 没有真实条件图的情况，结果仍然是相对生成第 0 帧的内部一致性。

3. `subject_replacement`

包含：

- checklist：权重 0.6
- `arcface_identity_keep`：权重 0.4

ArcFace 的特点：

- 只有人物主体替换时适用，非人物会返回 `not_applicable`。
- 使用 InsightFace `buffalo_l`，视频按 2 fps、最多 48 帧检测人脸。
- 首次初始化和扫描人脸成本较高，已有记录约 2–2.5 分钟；同一进程模型已加载后，单条约 4–5 秒。
- 对身份保持有较强的客观补充价值，但不能判断服装、光照、姿态和空间是否自然，这些仍由 checklist 判断。

模式影响很大：

- `f2va` / `fl2va`：用输入首帧作为身份锚点，价值最高。
- `r2va`：有可靠参考图时价值也较高。
- `t2va` / `l2va`：当前通常用生成视频第 0 帧作为锚点，主要测视频内部身份稳定，不是严格的外部身份保持验证。

建议：

- 只对人物替换且有可靠首帧或参考图的 case 开启。
- `f2va`、`fl2va`、合适的 `r2va` 优先。
- `t2va` 中可以作为“视频内部身份漂移”诊断，但不应把它解释成外部身份一致性。
- 非人物主体或没有清晰人脸时关闭。

4. `add_remove_object`

包含：

- checklist：权重 0.7
- `gdino_presence`：权重 0.3

特点：

- 仍然依赖 GroundingDINO。
- 每个添加或删除目标会单独检测。
- 最后两帧判断添加目标是否出现、删除目标是否消失。
- 目标越多，外部检测进程和耗时越多。
- 只看最后两帧，不能完整验证中间过程，因此 checklist 仍然重要。

建议：

- 有 `add_objects` 或 `remove_objects` 时开启。
- 没有增删物体的 case 不适用，不要为了统一配置而开启。
- 对小目标、被遮挡目标、强变形目标，GroundingDINO 可能漏检，不能完全替代视觉 checklist。
- 对“物体 A 变成物体 B”的 case，可以分别检测移除目标和新增目标，但要注意检测短语是否适合 GroundingDINO。

该组件是成本和收益比较不对称的组件：它能增加客观性，但每个 case 可能带来分钟级开销。因此适合只对增删物体 case 开启，而不适合全量开启。

5. `video_extension`

包含：

- checklist：权重 0.5
- `continuation_seam_lpips`：权重 0.5

这是数值组件中性价比较高的一项：

- 只比较生成视频第 0 帧和源视频最后一帧、给定首帧或参考视频最后一帧。
- 通常只需要一次 LPIPS。
- 成本约 1.5–3 秒，远低于 GroundingDINO。
- 对真实续写且有源帧的 case，能直接发现接缝跳变。

建议：

- `r2va` 引用了参考视频时开启。
- 有给定首帧并且事实确实表示续写时开启。
- `t2va` 没有源视频或条件首帧时关闭；即使 facts 被判断为 continuation，当前代码也可能返回 `missing_input`。
- 普通的连续动作视频不应自动当成视频延长。

6. `first_last_frame`

包含：

- checklist：权重 0.5
- `endpoint_psnr`：权重 0.25
- `endpoint_lpips`：权重 0.25

适用性很明确：

- `f2va`：比较生成首帧和条件首帧。
- `l2va`：比较生成尾帧和条件尾帧。
- `fl2va`：首尾两端都比较。
- `t2va`：没有条件端点，不适用。
- 一般 `r2va`：没有专门首尾条件，也不适用。

成本：

- PSNR 几乎没有模型成本。
- LPIPS 约 1.5–3 秒。
- `fl2va` 会比较两个端点。
- 当前实现的 `endpoints()` 会同时计算 PSNR 和 LPIPS，所以建议把两个端点指标视为一组处理，不能简单认为只开 PSNR 就完全不加载 LPIPS。

建议：

- `f2va`、`l2va`、`fl2va` 优先开启。
- 其中 `endpoint_psnr` 成本最低，适合先启用。
- 如果需要感知质量判断，再加入 `endpoint_lpips`。
- `t2va` 和普通 `r2va` 保持关闭。

**推荐的分阶段方案**

第一阶段继续使用 checklist-only，建立所有模式的基线。这样可以先确认：

- 哪些子项实际适用；
- facts 是否正确；
- checklist 题目是否稳定；
- 不同输入模式之间的基础分数。

第二阶段按模式开启低成本、高收益组件：

- `f2va` / `fl2va`：优先首尾帧组件。
- `l2va`：优先尾帧组件。
- 有真实续写源帧的 case：开启 `continuation_seam_lpips`。
- 有人物替换和可靠条件人脸的 case：开启 ArcFace。

第三阶段只筛选特定 case 开启 GroundingDINO 相关组件：

- 有增删物体：`gdino_presence`。
- 明确要求背景保持，且场景相对稳定：`dino_bg_consistency`。
- 明确 `static_camera: true`：再增加 `masked_lpips_static`。

**对当前 D14 配置的具体建议**

当前配置继续关闭：

- `dino_bg_consistency`
- `masked_lpips_static`
- `arcface_identity_keep`
- `gdino_presence`
- `continuation_seam_lpips`
- `endpoint_psnr`
- `endpoint_lpips`

是合理的，尤其因为首尾帧和 GroundingDINO 共享依赖目前还没有被正确放行。

后续如果修正共享依赖，推荐优先级为：

1. `continuation_seam_lpips`：有源帧时开启。
2. `endpoint_psnr` + `endpoint_lpips`：只对 `f2va`、`l2va`、`fl2va` 开启。
3. `arcface_identity_keep`：只对人物替换且有可靠条件人脸的 case 开启。
4. `masked_lpips_static`：只对静态镜头开启。
5. `dino_bg_consistency`：对确实要求非目标区域保持的 case 开启。
6. `gdino_presence`：只对真实增删物体的 case 开启。

还需要注意，关闭数值组件后，`combine_subpoint()` 会移除该组件权重，并将剩余权重重新归一。因此 checklist-only 的分数不是原始配置中 checklist 权重对应的部分分，而是被重新当作该子项的完整分数。不同开关组合的结果不能直接横向比较，运行报告中应同时记录组件开关配置。

---

**User**

你先给我说明一下14维度的子项的评估目标是什么，以及对应的组件的目的是干什么的？不要太长，简单给我介绍一下

---

**Cursor**

第 14 维度“编辑与可控生成”主要评估视频是否按要求完成编辑，同时尽量保持不该变化的内容。

- **局部修改准确性**  
  目标：指定对象是否被正确修改，并符合初始状态、变化过程和最终状态。  
  组件：`checklist`，由视觉评委根据提示词逐项判断。

- **非目标区域保持**  
  目标：背景、其他主体、布局、光照等未要求修改的内容是否保持稳定。  
  组件：
  - `checklist`：人工规则式检查背景和其他内容；
  - `dino_bg_consistency`：用 DINO 比较目标区域以外的视觉特征是否一致；
  - `masked_lpips_static`：静态镜头下，用 LPIPS 比较非目标区域的感知差异。

- **主体替换一致性**  
  目标：人物或服装替换后，身份、姿态、光照、阴影和空间关系是否自然。  
  组件：
  - `checklist`：判断整体替换效果；
  - `arcface_identity_keep`：用人脸特征相似度检查人物身份是否保持。主要适用于人物替换。

- **增删物体**  
  目标：要求添加的物体是否出现，要求删除的物体是否完全消失。  
  组件：
  - `checklist`：判断物体是否自然、完整、没有残留；
  - `gdino_presence`：用 GroundingDINO 检测最后几帧中物体是否存在或消失。

- **视频延长**  
  目标：生成视频是否自然接上源视频、首帧或参考视频，没有明显跳变。  
  组件：
  - `checklist`：判断整体衔接是否自然；
  - `continuation_seam_lpips`：用 LPIPS 比较生成首帧和源视频末帧或条件帧的视觉差异。

- **首尾帧控制**  
  目标：视频是否从指定首帧开始、在指定尾帧结束，并保持中间运动合理。  
  组件：
  - `checklist`：判断端点和中间运动；
  - `endpoint_psnr`：用像素级 PSNR 比较生成帧和条件帧；
  - `endpoint_lpips`：用感知距离比较生成帧和条件帧。

总体上，`checklist`负责判断复杂的语义和过程，数值组件负责提供更客观的相似度、身份或物体存在性证据。不同子项只在对应事实成立时适用，例如有人物替换才评估主体替换，有首尾条件图才评估首尾帧控制。

---

**User**

目前哪几个组件之间存在共享依赖的问题？共享依赖是什么意思？

---

**Cursor**

目前有两类**执行依赖共享**问题：

1. **GroundingDINO 共享依赖**

以下三个组件都会依赖内部组件 `gdino_edit_targets`：

- `dino_bg_consistency`
- `masked_lpips_static`
- `gdino_presence`

`gdino_edit_targets` 负责先用 GroundingDINO 在锚点帧和采样帧中检测编辑目标，后续组件再使用这些检测框。

例如，`dino_bg_consistency` 的执行流程是：

```text
dino_bg_consistency
    └── gdino_edit_targets
```

但当前配置只控制外层组件名。打开 `dino_bg_consistency` 时，`active_components` 中可能只有 `dino_bg_consistency`，没有 `gdino_edit_targets`，因此内部依赖可能被系统判定为 `disabled`，导致外层组件无法正常计算。

对应代码见 [d14.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d14.py:37) 和 [base.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/base.py:88)。

2. **首尾帧组件共享依赖**

以下两个组件共同依赖内部组件 `endpoints`：

- `endpoint_psnr`
- `endpoint_lpips`

`endpoints` 一次读取生成视频的首帧或尾帧，并同时计算 PSNR 和 LPIPS，外层两个组件只是分别取其中一个结果。

当前配置只暴露了 `endpoint_psnr` 和 `endpoint_lpips`，没有暴露内部的 `endpoints`。所以即使把其中一个或两个开关设为 `true`，`ctx.comp("endpoints", ...)` 仍可能因为没有被允许而返回 `disabled`。

这里的“共享依赖”就是：**多个对外组件依赖同一个内部计算步骤或中间结果，而配置系统目前只管理了外层组件，没有同步放行这个共同的内部步骤。**

另外，多个组件共同使用 LPIPS 模型本身属于正常的模型复用，不是当前这个配置问题。例如：

- `masked_lpips_static`
- `continuation_seam_lpips`
- `endpoint_lpips`

它们都使用 LPIPS，但内部模型有缓存，可以复用加载结果。真正需要优先处理的是 `gdino_edit_targets` 和 `endpoints` 这两个内部组件的开关依赖。

---

**User**

根据你目前的分析  哪个最费时间？

---

**Cursor**

按**单条 case 的持续运行时间**看，最费时间的是：

1. **GroundingDINO 相关组件**  
   包括 `dino_bg_consistency`、`masked_lpips_static`、`gdino_presence`。  
   通常约 **1–3 分钟/条 5 秒视频**，而且多个增删目标会增加检测次数。它们共享目标检测步骤，但只要任意一个相关组件需要，通常就要先生成锚点帧和最多 8 个视频帧的检测框。参考 [dim13_evaluation_table.md](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/docs/dim13_evaluation_table.md:125)。

2. **ArcFace 首次启动**  
   `arcface_identity_keep` 第一次加载 InsightFace `buffalo_l` 时约 **2–2.5 分钟**；模型加载后，每条通常约 **4–5 秒**。因此它是“首次启动很慢”，但批量运行时不如 GroundingDINO 持续耗时。参考 [dim13_evaluation_table.md](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/docs/dim13_evaluation_table.md:128)。

3. **DINO 本身**  
   首次加载约 **30 秒**，加载后约 **2 秒/条**，主要时间仍花在前面的 GroundingDINO 检测。

所以简单结论是：

> **持续批量评测中，GroundingDINO 相关组件最费时间。首次运行时，ArcFace 的模型初始化也可能同样慢。**

相比之下：

- `continuation_seam_lpips`：约 1.5–3 秒；
- `endpoint_psnr` / `endpoint_lpips`：几秒级；
- `masked_lpips_static` 的 LPIPS 计算本身不慢，但它依赖 GroundingDINO，所以整体仍可能达到分钟级。

---

**User**

GroundingDINO，ArcFace以及DINO 本身，分别对应的是哪几个子项？

---

**Cursor**

对应关系如下：

- **GroundingDINO**
  - `non_target_preservation`
    - 作为目标检测框，辅助 `dino_bg_consistency`
    - 作为目标区域遮罩，辅助 `masked_lpips_static`
  - `add_remove_object`
    - 对应数值组件 `gdino_presence`
    - 检查添加物体是否出现、删除物体是否消失

- **DINO ViT-S/16**
  - 只对应 `non_target_preservation`
  - 具体组件是 `dino_bg_consistency`
  - 比较编辑目标之外的区域，在锚点帧和后续视频帧之间是否保持一致

- **ArcFace / InsightFace `buffalo_l`**
  - 只对应 `subject_replacement`
  - 具体组件是 `arcface_identity_keep`
  - 检查人物替换后，人脸身份特征是否保持一致

可以简化为：

```text
non_target_preservation
├── GroundingDINO
├── DINO
└── LPIPS

add_remove_object
└── GroundingDINO

subject_replacement
└── ArcFace / InsightFace
```

其中，GroundingDINO 在 `non_target_preservation` 中主要负责“找出哪些区域是编辑目标”，它本身不直接计算背景相似度；真正计算背景一致性的是 DINO 或 LPIPS。

---

**User**

我的意思是对应于第14维度的哪几个子项

---

**Cursor**

对应第 14 维度的子项是：

- **GroundingDINO**
  - `non_target_preservation`：定位编辑目标，帮助排除目标区域，评估背景是否保持。
  - `add_remove_object`：检测添加的物体是否出现、删除的物体是否消失。

- **DINO**
  - `non_target_preservation`：比较编辑目标以外区域的视觉特征是否保持一致。

- **ArcFace**
  - `subject_replacement`：检查人物替换后的人脸身份是否保持一致。

简表：

```text
GroundingDINO → 非目标区域保持、增删物体
DINO         → 非目标区域保持
ArcFace      → 主体替换一致性
```

---

**User**

评估首尾帧的是哪一个？

---

**Cursor**

评估首尾帧的是第 14 维度的 **`first_last_frame`（首尾帧控制）** 子项。

它包含三个组件：

- `checklist`：检查视频是否从指定首帧开始、在指定尾帧结束，以及中间运动是否合理。
- `endpoint_psnr`：比较生成帧和条件帧的像素级差异。
- `endpoint_lpips`：比较生成帧和条件帧的感知差异。

适用模式：

- `f2va`：评估生成视频首帧与给定首帧；
- `l2va`：评估生成视频尾帧与给定尾帧；
- `fl2va`：同时评估首帧和尾帧；
- `t2va`：没有条件首尾帧，因此通常不适用；
- `r2va`：如果没有专门的首帧或尾帧条件，也通常不适用。

---

**User**

这个组件我想要的效果是当mode选这的是fl2va，或者f2va，l2va时是激活的 ，其他模式是关闭的。可以实现吗？

---

**Cursor**

可以实现，而且当前逻辑已经有一部分天然支持：

- `f2va`：有 `first_frame`，启用首帧评估；
- `l2va`：有 `last_frame`，启用尾帧评估；
- `fl2va`：同时启用首帧和尾帧评估；
- `t2va`：没有首尾条件图，`first_last_frame` 会自动判定为不适用；
- `r2va`：通常没有专门首尾条件图，也会判定为不适用。

要实现“只有 `f2va`、`l2va`、`fl2va` 开启，其他模式关闭”，有两种方式：

1. **配置层面实现，推荐当前使用**  
   为不同 mode 使用不同 YAML：
   - `task_d14_f2va.yaml`
   - `task_d14_l2va.yaml`
   - `task_d14_fl2va.yaml`  
   这三个配置打开 `endpoint_psnr`、`endpoint_lpips`，`t2va` 和 `r2va` 配置保持关闭。

2. **代码层面自动判断 mode**  
   在运行时根据 `input.mode` 自动决定是否启用 `first_last_frame` 及其两个数值组件。这样只维护一个 YAML，但需要修改任务配置解析或评估逻辑。

不过目前还有前面提到的共享依赖问题：`endpoint_psnr` 和 `endpoint_lpips` 都通过内部组件 `endpoints` 计算。要真正打开它们，需要同时处理 `endpoints` 的放行，否则配置设为 `true` 也可能仍返回 `disabled`。

因此结论是：**功能上可以实现；如果只针对当前任务，建议使用不同 mode 配置；如果希望一个配置自动适配所有 mode，则需要修改代码，并修正 `endpoints` 共享依赖。**

---

**User**

代码层面自动判断 mode
在运行时根据 input.mode 自动决定是否启用 first_last_frame 及其两个数值组件。这样只维护一个 YAML。
我需要这种实现方式，这种方式还需要解决什么依赖？

---

**Cursor**

需要解决的核心依赖只有一组：**`first_last_frame` 子项中的共享组件 `endpoints`**。

当前执行关系是：

```text
first_last_frame
├── endpoint_psnr
└── endpoint_lpips
        └── 共享内部计算：endpoints
```

因此实现“根据 `input.mode` 自动启用”时，需要处理以下几点：

1. **根据 mode 自动打开两个外层组件**

当 mode 是：

- `f2va`
- `l2va`
- `fl2va`

自动启用：

```text
first_last_frame
endpoint_psnr
endpoint_lpips
```

当 mode 是：

- `t2va`
- `r2va`

自动关闭或跳过 `first_last_frame`。

2. **同时放行内部组件 `endpoints`**

现在 `Context.comp()` 只允许 `active_components` 中的名称执行。即使外层允许了：

```text
endpoint_psnr
endpoint_lpips
```

内部调用：

```text
ctx.comp("endpoints", ...)
```

仍可能因为 `endpoints` 没在允许列表中而返回 `disabled`。

所以需要让运行时逻辑满足：

```text
endpoint_psnr 或 endpoint_lpips 被启用
    → endpoints 也必须被允许执行
```

或者让 `endpoints` 不再受到外层组件开关限制。

3. **明确两个数值组件是否始终一起计算**

当前 `V.endpoints()` 一次同时计算 PSNR 和 LPIPS。因此最简单、最一致的方案是：

```text
f2va / l2va / fl2va
    → endpoint_psnr = true
    → endpoint_lpips = true
    → endpoints = true
```

不建议当前阶段只开启其中一个，因为共享函数仍会把两个指标一起算出来。

4. **确认输入文件与 mode 一致**

自动判断后仍要保证：

- `f2va` 存在首帧文件；
- `l2va` 存在尾帧文件；
- `fl2va` 同时存在首帧和尾帧文件；
- `t2va`、`r2va` 不强制要求端点文件。

实际上 `V.endpoints()` 已经能根据 `first` 和 `last` 分别计算存在的端点，因此：

- `f2va` 只计算首帧；
- `l2va` 只计算尾帧；
- `fl2va` 计算两端并取平均。

总结来说，**不需要引入新的模型依赖**，也不需要额外下载权重。需要解决的是：

```text
mode 自动判断
+ endpoints 共享内部组件放行
+ 保证 endpoint_psnr / endpoint_lpips 与共享计算结果正确映射
```

现有 LPIPS 模型本身已经是 `endpoint_lpips` 的正常依赖，不属于新的共享开关问题。

---

**User**

那你现在修改一下吧  实现模式匹配。

---

**Cursor**

我会修改 D14 的运行时组件选择：统一配置中把首尾帧数值组件声明为可用，再由 `input.mode` 只在 `f2va`、`l2va`、`fl2va` 放行；同时补上共享内部组件 `endpoints` 的放行，保证 PSNR/LPIPS 实际执行。先确认 `Case` 中 mode 的字段和任务配置注入路径，然后编辑并做静态验证。

<thinking>**Tracing task config merge path****Preparing targeted code edits**</thinking>
`Case.input_form` 已经由 `input.mode` 规范化生成，因此可以在 D14 评估层按 `ctx.case.input_form` 判断，不需要新增字段。我要把首尾帧子项和两个端点组件的启用条件集中在 D14 评估逻辑中，并保留现有 YAML 作为默认开关的上限控制。

<thinking>**Implementing mode-aware endpoint activation****Editing D14 evaluator and example config**</thinking>
我会做两处最小修改：D14 在运行时只对 `f2va`、`l2va`、`fl2va` 放行 `first_last_frame` 的端点计算，并在端点计算前自动加入共享依赖 `endpoints`；示例 YAML 将两个端点外层开关设为 `true`，由 mode 决定实际是否执行。这样同一个配置在 `t2va`/`r2va` 中不会运行端点评估。

刚才尝试使用补丁命令时发现该环境没有提供 `apply_patch` 命令，文件尚未改变。我会改用工作区的精确字符串替换工具完成同样的最小修改，然后继续做语法和行为验证。

<thinking>**Checking partial edits before continuing**</thinking>
D14 代码中的模式集合和 YAML 端点开关已经更新；注释替换因工具路径处理失败未写入，但不影响功能。我现在补上评估逻辑本身，并检查最终 diff。

<thinking>**Implementing endpoint mode guard and shared dependency allowance****Updating comments and dynamic configuration****Validating modified files and endpoint behavior****Potential issue: "mode auto decision" should perhaps be in runtime active_components logic****Need inspect testability imports**</thinking>

<thinking>**Verifying syntax and YAML values****Running static validation of endpoint mode gating**

<thinking>**Correcting stale configuration documentation****Verifying all endpoint switches and comments****Running final static checks**</thinking>
代码已经通过 Python 语法检查，YAML 也确认端点开关为 true。现在我补正配置顶部的旧说明，避免它继续声称所有数值组件默认关闭；实际行为是只有端点组件在三种端点模式下启用，其他数值组件仍保持关闭。

<thinking>**Reviewing final diff and verifying dynamic mode behavior**</thinking>
核心逻辑已完成：`input.mode` 会进入 `Case.input_form`，D14 根据它判断端点评估；`endpoints` 作为共享缓存组件会在端点输出被启用时自动放行。最后我检查变更范围和三种模式的静态行为，确认没有误改其他数值组件。

已实现按 `mode` 自动匹配首尾帧评估。

修改内容：

- `f2va`、`l2va`、`fl2va`
  - 自动启用 `first_last_frame`
  - 执行 `endpoint_psnr`
  - 执行 `endpoint_lpips`
  - 自动放行共享依赖 `endpoints`

- `t2va`、`r2va`
  - 不执行首尾帧数值评估
  - 首尾帧子项因没有条件帧而保持不适用

修改文件：

- [d14.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d14.py)
- [task_d14_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d14_example.yaml)

YAML 中现在将两个端点组件声明为可用，实际是否执行由 `input.mode` 决定。已完成 Python 语法检查、YAML 配置检查，并验证了五种 mode 的匹配行为。

---

**User**

第14维度的其他还有4个评估子项是可以添加组件的，目前这4个子项里面的组件会存在共享依赖吗？

---

**Cursor**

有。除 `first_last_frame` 外，其他 4 个涉及组件的子项中，真正存在**共享执行依赖**的是 `non_target_preservation` 和 `add_remove_object`。

- `non_target_preservation`
  - `dino_bg_consistency` → 依赖共享组件 `gdino_edit_targets`
  - `masked_lpips_static` → 依赖共享组件 `gdino_edit_targets`
  - 另外使用 LPIPS 模型

- `add_remove_object`
  - `gdino_presence` → 依赖同一个共享组件 `gdino_edit_targets`

`gdino_edit_targets` 会先在锚点帧和最多 8 个视频帧中检测编辑目标。之后：

- DINO 使用这些框排除目标区域；
- masked LPIPS 使用这些框排除目标区域；
- `gdino_presence` 使用每个物体的检测结果判断添加或删除是否成功。

因此，这三个数值组件都依赖：

```text
gdino_edit_targets
```

当前如果直接打开它们，仍需要像 `endpoints` 一样处理共享依赖放行问题。

另外三类关系属于**模型复用**，但不是共享执行依赖：

- `subject_replacement`
  - `arcface_identity_keep` 独立使用 InsightFace `buffalo_l`
  - 不依赖其他 D14 子项

- `video_extension`
  - `continuation_seam_lpips` 独立调用 LPIPS
  - 会和 `masked_lpips_static`、首尾帧 LPIPS 复用同一个 LPIPS 模型缓存，但不需要共享组件放行

- `local_edit_accuracy`
  - 只有 checklist，没有额外数值组件

总结：

```text
共享执行依赖：
dino_bg_consistency
masked_lpips_static
gdino_presence
        └── gdino_edit_targets

仅复用模型：
masked_lpips_static
continuation_seam_lpips
endpoint_lpips
        └── LPIPS 模型缓存
```

所以，后续如果要自动开启这 4 个子项中的数值组件，除了首尾帧的 `endpoints` 外，还需要额外处理 `gdino_edit_targets` 的自动放行。

---

**User**

subject_replacement和video_extension，除去最开始拉起小模型，这两个子项用到的组件耗时吗？

---

**Cursor**

除去首次加载模型的时间后，这两个子项的数值组件都不算特别耗时：

- **`subject_replacement`**
  - 组件：`arcface_identity_keep`
  - 作用：对条件图和视频中的人脸做检测、特征提取和相似度比较。
  - 已加载模型后，约 **4–5 秒/条 5 秒视频**。
  - 相对更耗时，因为最多处理 48 帧，并且每帧都要做人脸检测和特征提取。

- **`video_extension`**
  - 组件：`continuation_seam_lpips`
  - 作用：比较生成视频首帧与源视频末帧或条件帧的感知差异。
  - 已加载 LPIPS 后，约 **1.5–3 秒/条 5 秒视频**。
  - 只比较一对帧，因此明显比 ArcFace 更快。

简单排序：

```text
arcface_identity_keep       约 4–5 秒
continuation_seam_lpips     约 1.5–3 秒
```

所以批量评测时：

- `video_extension` 可以比较放心地开启；
- `subject_replacement` 也可以开启，但最好只对确实有人物替换、且有可靠人脸条件的 case 开启；
- 两者都不会像 GroundingDINO 那样达到每条 1–3 分钟的级别。

---

**User**

那这两个也在评估的时候默认开启吧

---

**Cursor**

我会把 `arcface_identity_keep` 和 `continuation_seam_lpips` 在统一 YAML 中设为默认启用。它们仍会受子项适用条件控制：只有检测到人物替换或续写事实时才实际运行，其他 case 不会调用模型。

已将这两个组件设置为默认开启：

- `subject_replacement.arcface_identity_keep: true`
- `video_extension.continuation_seam_lpips: true`

配置文件为 [task_d14_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d14_example.yaml)。

它们不会对所有 case 强制执行：

- 只有 `facts.has_subject_replacement` 为 true 时，才运行 ArcFace；
- 只有 `facts.is_continuation` 为 true 时，才运行 continuation LPIPS；
- 不满足条件时，子项会被判定为 `not_applicable`，不会加载或调用对应组件。

当前默认开启的数值组件共有：

- 首尾帧：仅 `f2va`、`l2va`、`fl2va` 模式运行；
- ArcFace：仅人物主体替换 case 运行；
- continuation LPIPS：仅视频续写 case 运行。

DINO、masked LPIPS 和 GroundingDINO 增删物体检测仍保持关闭。配置 YAML 已通过检查。

---

**User**

目前与dino相关的组件就先关闭，只使用检查清单来评估是吗？

---

**Cursor**

是的，目前与 DINO 相关的组件都保持关闭，只使用检查清单进行评估：

- `dino_bg_consistency: false`
- `masked_lpips_static: false`
- `gdino_presence: false`

因此目前不会运行：

- GroundingDINO 目标检测；
- DINO ViT-S/16 背景一致性；
- 静态区域 LPIPS；
- 增删物体的 GroundingDINO 检测。

目前仍会按条件运行：

- `arcface_identity_keep`：人物主体替换时；
- `continuation_seam_lpips`：续写 case 且有可用源帧时；
- `endpoint_psnr`、`endpoint_lpips`：`f2va`、`l2va`、`fl2va` 模式时。

所以，DINO 相关的三个组件目前确实是关闭的；对应子项仍保留 checklist，数值组件关闭后，checklist 权重会重新归一化。

---

**User**

目前第14维度先修改成这样，把第15维度也先按照13和14维度这种方式来进行修改一下

---

**Cursor**

我先核对第 15 维度当前的子项、组件开关和适用条件，再按第 14 维度的原则处理：保留 checklist，数值组件默认按事实条件选择性执行，避免无关 case 加载模型。确认后我会直接修改对应实现和配置，并做语法与配置验证。

我会按第 14 维度的模式处理第 15 维度：保留 checklist，数值组件由事实字段决定是否适用，并补齐 `asr`、`vad` 这类共享内部依赖的放行。先确认第 15 维度各子项的 `applies` 条件和现有音频组件名称，避免把不适用的模型误开。

<thinking>**Reviewing D15 design and available task patterns**</thinking>

目前第 15 维度的主要问题不是输入 mode，而是音频组件内部有共享步骤：Whisper 的 `asr`、Silero VAD 的 `vad`，以及配乐参考音频的 `clap_music_reference`。我会按第 14 维度的做法补一个可复用的 D15 task YAML，并让这些共享依赖在外层数值组件开启时自动放行；默认先保留 checklist，数值组件显式关闭，避免一次运行加载整套音频模型。

<thinking>**Inspecting D15 implementation and config**</thinking>
第 15 维度的现有代码确实有和第 14 维度类似的共享依赖问题：`asr_cer`、音色/情绪组件共用 Whisper 的 `asr` 结果；`voice_naturalness` 和禁人声检测共用 Silero VAD 的 `vad` 结果。当前任务配置里没有第 15 维度的可复用 YAML，我会补上一个 checklist-only 默认配置，并修正这些共享依赖的自动放行，后续可以逐个打开数值组件。

<thinking>**Implementing D15 dependency-aware component execution**</thinking>
我将把 D15 的数值计算改成“外层组件开启后才执行内部依赖”：例如关闭 `asr_cer` 时不会启动 Whisper，关闭 `dnsmos_ovr` 时不会先启动 VAD。这样配置成 checklist-only 时，音频模型不会被隐式拉起；后续打开某个数值组件时，它会自动放行所需的 `asr` 或 `vad` 共享缓存。

D15 的共享依赖处理已经补上：关闭某个外层数值组件时，不会因为内部调用而隐式启动 Whisper 或 VAD；开启时才会自动放行对应缓存依赖。接下来我补一个和 D14 使用方式一致的 `task_d15_example.yaml`，默认只跑 checklist，所有音频数值组件显式关闭，之后可按子项单独打开。

<thinking>**Validating D15 implementation and configuration**</thinking>
D15 的 checklist-only 配置和依赖控制已经写好。现在我做三类验证：Python 语法、任务 YAML 与评分配置的组件名一致性、以及关闭所有数值组件时通过模拟上下文确认不会进入 Whisper/VAD 等内部计算。

验证发现一个配置细节：第 15 维度的 `voice_naturalness` 和 `timbre_consistency` 在评分配置中本来没有 checklist 组件，任务 YAML 如果强行写 `checklist: true` 会被校验拒绝。我要保留它们原有的评分定义，只对允许的数值组件做显式关闭，然后重新验证整份任务配置。

D15 配置校验已修正：`voice_naturalness` 和 `timbre_consistency` 原评分定义没有 checklist，因此不能添加 `checklist: true`，这两个子项在数值组件全关时会没有可评分组件；其余有 checklist 的子项仍保留 checklist-only。现在进行最终校验，并检查关闭数值组件时不会触发音频模型。

我发现并修正了一个配置校验点：第 15 维度的 `voice_naturalness` 和 `timbre_consistency` 在原评分定义中没有 checklist 路径，所以没有强行添加 checklist 开关；其余子项保持 checklist 可用。当前 D15 配置校验、语法和关闭数值组件不执行模型的测试都已通过。

已按第 13、14 维度的任务配置方式补充第 15 维度：新增 [task_d15_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d15_example.yaml)，数值组件默认关闭；保留原评分配置中已有的 checklist，开启某个数值组件时才执行它所需的计算。

同时调整了 [d15.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d15.py)，让依赖 Whisper 的 `asr` 和依赖 Silero 的 `vad` 仅在对应数值组件启用时运行，并修正配乐参考音频组件与配置开关之间的名称对应。

有个评分配置限制需要留意：`voice_naturalness` 和 `timbre_consistency` 原本没有 checklist 组件，因此当它们的数值组件关闭时，这两个子项不会有分数。**验证已通过**：Python 语法、任务 YAML 校验、共享依赖调用和 CRLF 检查。未运行实际音频模型评测。

---

**User**

你先不要测试，你现在把第16维度，第17维度以及第18维度，都先按照这个方式修改一下。然后我再逐个进行测试。你修改好就就停下

---

**Cursor**

<thinking>**Inspecting D16-D18 components and dependencies****Planning D16-D18 configuration alignment**</thinking>
我会按第 15 维度刚才的方式处理第 16、17、18 维度：分别补充可复用 task YAML，默认保留 checklist、关闭数值组件，并检查实现里是否有被外层开关遗漏的共享内部依赖。按你的要求，修改完成后我就停下，不运行测试或验证命令。

<thinking>**Implementing D16-D18 shared dependency gating and task configs**</thinking>
我已经确定三类需要处理的共享依赖：D16 的 `asr`/`syncnet_tracks`，D17 的异常时间线、VMBench 和骨架结果，D18 的统一 `ocr` 结果。现在直接修改这三个维度的实现，并新增对应的 checklist-only 任务配置；本轮不执行测试命令。

<thinking>**Writing D16-D18 task configurations****Refining D17 diagnostics gating****Creating checklist-only task configs**</thinking>
三份任务配置会分别覆盖 D16、D17、D18 的全部子项，并显式关闭数值组件；D17 还会同步处理未计分的 FIRM/骨架诊断，避免 checklist-only 配置仍然隐式运行这些模型。现在只写文件，不执行测试。

我在修改后的执行路径里注意到一个边界：第 17 维度还有未计分的 FIRM 和骨架诊断，基础流程会在评估结束时调用它们。为了让“默认 checklist-only”真正成立，我再补一处条件控制：只有第 17 维度至少启用了相关数值组件时，才运行这些附加诊断；然后停止，不做测试。

已完成第 16、17、18 维度的同类修改，并按你的要求停下，未运行测试。

修改内容：

- [d16.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d16.py)
  - `asr` 和 `syncnet_tracks` 改为按数值组件是否启用来放行。
  - 关闭数值组件时不会隐式启动 Whisper 或 SyncNet。

- [d17.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d17.py)
  - 异常时间线、VMBench、骨架分析、光流和人脸分析按外层组件开关执行。
  - checklist-only 配置下不会隐式运行这些模型。
  - 未计分的 FIRM 和骨架诊断也不会在 checklist-only 模式下自动启动。

- [d18.py](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d18.py)
  - 所有 OCR 子项共享内部 `ocr` 结果。
  - 只有 OCR 数值组件开启时，才会执行 PP-OCRv5。

新增 checklist-only 配置：

- [task_d16_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d16_example.yaml)
- [task_d17_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d17_example.yaml)
- [task_d18_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d18_example.yaml)

这三份配置默认保留适用子项的 checklist，并关闭对应数值组件。

---

**User**

你现在先分析一下目前第15维度哪些子项的模型耗费的时间不长，可以建议默认打开的？

---

**Cursor**

按时间和收益来看，第 15 维度最适合默认开启的是以下几个子项中的部分组件：

**优先默认开启**

- **`music_match`**
  - `music_presence`：使用 PANNs Cnn14，模型加载后约 **0.3 秒/条**。
  - `clap_music`：使用 CLAP，模型加载后约 **0.1 秒/条**。
  - 适用条件是提示词要求有配乐或明确禁止配乐。
  - 这是目前性价比最高的一组。

- **`ambient_sound`**
  - `clap_ambient`：使用 CLAP 判断环境音是否符合描述。
  - 模型加载后耗时很短，适合默认开启。
  - 仅在 facts 中存在环境音要求时运行。

- **`action_sfx`**
  - `clap_sfx`：同样使用 CLAP 判断动作音效。
  - 耗时短，适合默认开启。
  - 仅在 facts 中存在脚步、碰撞、开门等音效要求时运行。

**可以考虑默认开启**

- **`dialogue_accuracy` 中的 `vad_speech_absent`**
  - 只适用于提示词明确禁止人声、且没有对白的 case。
  - 使用 Silero VAD，已有记录约 **4–6 秒/条**，包括音频抽取。
  - 成本不算高，而且对“禁止说话”这类要求有直接价值。
  - 可以默认开启，但不建议把它和 Whisper 的 `asr_cer` 混在一起默认开启。

- **`voice_naturalness`**
  - `dnsmos_ovr`：DNSMOS；
  - `audiobox_pq`：AudioBox。
  - 首次加载分别约 **5.5 秒**和 **3.5 秒**，后续单条通常是秒级。
  - 这组比 CLAP 慢一些，但仍没有 GroundingDINO、VMBench 那种分钟级开销。
  - 如果数据中对白 case 较多，可以作为第二优先级默认开启。

**不建议当前默认开启**

- **`dialogue_accuracy` 中的 `asr_cer`**
  - 依赖 Whisper large-v3。
  - 当前没有可靠实测，但它还会进行词级时间戳识别和 30 秒分块，通常会明显慢于 CLAP、PANNs 和 VAD。
  - 只有存在实际对白时才有价值，建议后续单独开启。

- **`timbre_consistency`**
  - 依赖 Whisper 定位语句，还可能调用 ECAPA。
  - ECAPA 当前没有可靠实测，且只对重复说话人或有参考音频的 case 有意义。
  - 建议按 case 开启，不适合作为全局默认。

- **`emotion_match`**
  - 同时依赖 Whisper 和 emotion2vec。
  - 只适用于明确要求对白情绪的 case。
  - 模型链较长，建议后续按需开启。

推荐默认策略：

```text
默认开启：
  music_presence
  clap_music
  clap_ambient
  clap_sfx
  vad_speech_absent

第二阶段考虑开启：
  dnsmos_ovr
  audiobox_pq

默认关闭：
  asr_cer
  ecapa_same_speaker
  ecapa_reference
  emotion2vec_match
```

其中 `clap_music`、`clap_ambient`、`clap_sfx` 只有对应事实存在时才会运行；`vad_speech_absent` 只有“禁止人声且没有对白”时才会运行。因此即使在 YAML 中默认设为 `true`，也不会对所有 case 都调用模型。

---

**User**

那就先把默认建议开启的先打开，其他都先关闭。

---

**Cursor**

我会只修改第 15 维度的任务配置：开启 `vad_speech_absent`、`clap_ambient`、`clap_sfx`、`music_presence` 和 `clap_music`，其余数值组件保持关闭。它们仍受 facts 的适用条件限制，不会对不相关 case 强行运行。

配置开关已按建议更新。当前文件顶部说明仍写着“全部数值组件关闭”，与新配置不一致；我会只修正文案，避免后续使用时误解，代码逻辑不再改动。

已按建议更新第 15 维度配置：

默认开启：

- `vad_speech_absent`
- `clap_ambient`
- `clap_sfx`
- `music_presence`
- `clap_music`

继续关闭：

- `asr_cer`
- `dnsmos_ovr`
- `audiobox_pq`
- `ecapa_same_speaker`
- `ecapa_reference`
- `emotion2vec_match`

修改文件：

[task_d15_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d15_example.yaml)

这些组件仍然只会在对应 facts 适用时执行，例如有环境音描述、动作音效描述、音乐要求或明确禁止人声时才会运行。

---

**User**

第16维度的各个子项的组件是什么情况呢？

---

**Cursor**

我先核对第 16 维度的实现、示例配置和评分映射，确认每个子项实际依赖哪些组件，以及关闭组件后是否仍有 checklist 或数值评分。

目前可以确认：第 16 维度不是四个子项各自独立启动模型，口型同步和多人说话人匹配共享 Whisper ASR，口型同步另外共享 SyncNet 跟踪结果。接下来我再核对评分权重、适用条件和组件开关机制，避免把“内部依赖”误说成“直接计分组件”。

第 16 维度包含 4 个子项。当前示例配置采用 **checklist-only**：所有数值组件关闭，`checklist` 保留。因此默认不会启动 Whisper、SyncNet、Synchformer 等模型，但音频门控和 checklist 判断仍会执行。

**1. 口型同步 `lip_sync`**

适用条件：`facts.dialogues` 存在。

数值组件：

- `syncnet_conf`：SyncNet 计算画面中、正在说话的屏幕人物，其口型与对白的同步置信度。数值越高越好。
- `syncnet_voiceover_still`：SyncNet 检查画外音或非屏幕对白期间，画面人物是否保持静止。当前实现使用 SyncNet 置信度作为代理指标，配置中数值越低越好。
- `checklist`：由视觉/音频评审模型判断对白期间口型是否同步、画外音时人物嘴部是否保持不动。

依赖关系：

```28:41:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d16.py
        if sp == "lip_sync":
            r = asr(ctx)
            if r.get("status") != "ok":
                return {"syncnet_conf": r, "syncnet_voiceover_still": r}
            tracks = self._tracks(ctx)
            if tracks.get("status") != "ok":
                return {"syncnet_conf": tracks, "syncnet_voiceover_still": tracks}
            on = [bool(d.get("on_screen", True)) for d in dialogues]
            return {
                "syncnet_conf": ctx.comp("syncnet_conf", lambda: S.syncnet_conf(
                    tracks, r["line_spans"], on, realistic)),
                "syncnet_voiceover_still": ctx.comp("syncnet_voiceover_still", lambda: S.syncnet_voiceover_still(
                    tracks, r["line_spans"], on, realistic)),
            }
```

完整数值链路是：

`Whisper ASR -> SyncNet 人脸轨迹 -> syncnet_conf / syncnet_voiceover_still`

其中：

- Whisper 负责把对白定位到视频时间段；
- SyncNet 负责检测人脸轨迹和音视频偏移；
- `realistic: false` 时，两个 SyncNet 子项会返回不适用，因为 SyncNet 面向真人脸训练。

当前配置中：

```42:47:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d16_example.yaml
    lip_sync:
      components:
        syncnet_conf: false
        syncnet_voiceover_still: false
        checklist: true
```

所以当前不会执行 ASR 或 SyncNet 的数值计算。`asr` 和 `syncnet_tracks` 只有在对应数值组件开启时才会被加入活动组件集合。

**2. 动作音同步 `action_sound_sync`**

适用条件：没有额外的 `applies` 条件。只要第 16 维度整体适用，就会处理这个子项。

数值组件：

- `synchformer_offset_s`：使用 Synchformer 估计视频动作与声音之间的平均偏移，单位为秒。偏移越小越好。
- `checklist`：评估脚步、撞击、敲击、拨弦等动作声音是否与画面事件同时发生。

实现只依赖视频和 16 kHz 音频：

```42:46:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d16.py
        if sp == "action_sound_sync":
            return {"synchformer_offset_s": ctx.comp("synchformer_offset_s", lambda: S.synchformer_offset(
                ctx.video, ctx.wav(16000)) if ctx.wav(16000) else missing_input("no audio track"))}
```

当前配置中 `synchformer_offset_s` 关闭，因此不会加载 Synchformer；只保留 checklist。

**3. 环境音同步 `ambient_sync`**

适用条件：`facts.env_changes` 为真，例如 checklist facts 标记了场景切换、下雨开始、开门等环境变化。

数值组件：

- `audio_change_alignment`：分析视觉切点附近的音频频谱变化，计算音频变化是否发生在视觉变化前后约 0.5 秒范围内。该组件是确定性音频分析，不加载深度学习模型。
- `checklist`：判断环境声音是否随画面环境变化同步发生。

实现使用视频切点 `ctx.cuts` 和 16 kHz 音频：

```47:51:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d16.py
        if sp == "ambient_sync":
            return {"audio_change_alignment": ctx.comp("audio_change_alignment", lambda: S.audio_change_alignment(
                ctx.wav(16000), ctx.cuts) if ctx.wav(16000) else missing_input("no audio track"))}
```

当前配置中 `audio_change_alignment` 关闭，所以不会执行频谱变化分析。若没有 `facts.env_changes`，整个 `ambient_sync` 会标记为 `not_applicable`，而不是得到一个空分数。

**4. 多人对白匹配 `multi_speaker_match`**

适用条件：`facts.multi_speaker` 为真。

数值组件：

- `timed_speaker_accuracy`：检查每句对白是否由正确的屏幕人物说出。数值越高越好。
- `checklist`：由视觉/音频评审模型根据画面和对白判断人物与台词是否匹配。

数值链路是：

`Whisper ASR -> 找到对白时间段 -> 视觉模型判断当前人物 -> 与 facts 中的 speaker 对比`

实现中只有满足以下条件的对白才参与数值计算：

- 人物在屏幕上；
- ASR 找到了对应时间段；
- ASR 匹配度至少为 `0.5`；
- checklist facts 中能够把对白 speaker 与描述的人物对应起来。

```55:76:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d16.py
    def _timed(self, ctx: Context) -> dict:
        speakers = ctx.facts.get("speakers") or []
        dialogues = ctx.facts.get("dialogues") or []
        if len(speakers) < 2:
            return na("fewer than two described speakers")
        r = asr(ctx)
        if r.get("status") != "ok":
            return r
```

当前配置中 `timed_speaker_accuracy` 关闭，因此不会启动 Whisper，也不会调用视觉模型做逐句说话人判断，只保留 checklist。

**公共组件和当前行为**

- `audio_gate: true`：第 16 维度会先检查是否有可用、非静音的音频轨道。即使所有数值组件关闭，这个全局音频门控仍然会执行。
- `judge_vision`：只要 checklist 中存在视觉问题，就会执行视觉评审。
- `judge_audio`：只要 checklist 中存在音频或音视频问题，就会执行音频评审。
- `Whisper ASR`：只服务于 `lip_sync` 和 `multi_speaker_match` 的数值组件，不会因为 checklist-only 配置而隐式启动。
- `SyncNet`：只服务于 `syncnet_conf` 和 `syncnet_voiceover_still`。
- `Synchformer`：只服务于 `synchformer_offset_s`。
- `audio_change_alignment`：只服务于 `ambient_sync` 的数值组件，不依赖 SyncNet 或 Synchformer。

因此，当前 `task_d16_example.yaml` 的实际模式可以概括为：

- 口型同步：checklist；
- 动作音同步：checklist；
- 环境音同步：仅当 `facts.env_changes` 适用时执行 checklist；
- 多人对白匹配：仅当 `facts.multi_speaker` 适用时执行 checklist；
- 不启动 Whisper、SyncNet、Synchformer 或环境音频频谱数值分析。

---

**User**

那如果考虑评估时间，哪些组件你建议开启？

---

**Cursor**

如果优先考虑评估时间，我建议按下面的优先级开启。

**推荐的时间和效果平衡方案**

```yaml
evaluation:
  subpoints:
    lip_sync:
      components:
        syncnet_conf: true
        syncnet_voiceover_still: true
        checklist: true
    action_sound_sync:
      components:
        synchformer_offset_s: false
        checklist: true
    ambient_sync:
      components:
        audio_change_alignment: true
        checklist: true
    multi_speaker_match:
      components:
        timed_speaker_accuracy: true
        checklist: true
```

前提是对应 facts 适用：

- `lip_sync` 需要 `facts.dialogues`；
- `ambient_sync` 需要 `facts.env_changes`；
- `multi_speaker_match` 需要 `facts.multi_speaker`。

**各组件的时间成本**

1. `audio_change_alignment`：建议开启

这是四个数值组件中最便宜的一个。它只做音频频谱分析，不加载额外深度学习模型，也不需要 Whisper、SyncNet 或 Synchformer。对于有场景切换、下雨、开门等环境变化的视频，性价比较高。

2. `syncnet_conf` 和 `syncnet_voiceover_still`：建议成对开启

两者共享一次 `syncnet_tracks`，也共享 Whisper ASR 的对白时间段。开启其中一个时，通常已经需要启动：

`Whisper ASR -> 人脸检测与跟踪 -> SyncNet`

因此只开启其中一个并不能明显节省时间。视频中存在真人正脸对白时，这两个组件对口型同步的补充价值较高，建议一起开启。

如果视频大多是动画、非人脸主体、远景人物或没有屏幕对白，则不建议开启，因为 SyncNet 可能返回 `not_applicable` 或无法产生有效结果。

3. `timed_speaker_accuracy`：多人场景才建议开启

这个组件会复用 Whisper ASR，并对每个可定位的屏幕对白调用视觉模型判断当前说话人。单个视频中对白句数较多时，视觉判断调用次数会增加，时间成本通常高于 `audio_change_alignment`。

建议在以下情况开启：

- `facts.multi_speaker` 为真；
- 至少有两个明确描述的说话人；
- “每句话由正确人物说出”是任务的核心要求。

如果只是单人说话或没有明确人物身份，关闭它更合适。

4. `synchformer_offset_s`：默认关闭，只在重点评估时开启

这是最适合优先关闭的数值组件。它需要加载 Synchformer，并对视频和音频做完整的音视频偏移分析，通常比音频频谱分析和普通 checklist 明显更慢。

只有在以下情况下建议开启：

- 动作音同步是本次评估的重点；
- 视频包含明显的脚步、撞击、鼓点、拨弦等事件；
- 需要较强的自动化数值指标，而不仅是 checklist 判断。

**按时间预算选择**

**最省时间：**

- 保留四个子项的 `checklist`；
- 所有数值组件关闭。

这仍会执行 checklist 所需的视觉/音频评审，但不会启动 Whisper、SyncNet、Synchformer 或额外音频分析。

**推荐默认配置：**

- 开启 `audio_change_alignment`；
- 如果是真人对白视频，再成对开启 `syncnet_conf` 和 `syncnet_voiceover_still`；
- 只有多人对白时开启 `timed_speaker_accuracy`；
- 保持 `synchformer_offset_s` 关闭。

**完整数值评估：**

- 四个数值组件全部开启。

适合最终报告或小规模重点样本，不建议直接用于大量视频的第一轮筛选。

需要特别注意：如果同时开启口型同步和多人对白匹配，两者会共享 Whisper ASR，因此 `timed_speaker_accuracy` 的额外成本主要是逐句视觉说话人判断，不会重复执行 ASR。另一方面，开启口型同步的任一 SyncNet 指标都会触发人脸跟踪，因此建议两个 SyncNet 指标一起开。

---

**User**

开启 audio_change_alignment
那就先只默认开始这个，其他的都先关闭掉。

---

**Cursor**

我会只修改第 16 维度示例配置：默认开启 `audio_change_alignment`，并确认其余数值组件仍关闭、checklist 保持开启。

<thinking>**Verifying final config values**</thinking>

配置已完成：`audio_change_alignment` 现在是唯一开启的数值组件，其余 SyncNet、Synchformer 和多人说话人匹配组件保持关闭。我正在用环境中的 `python3` 做一次 YAML 开关校验；刚才系统没有 `python` 命令。

已修改 [task_d16_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d16_example.yaml)：

- 开启 `ambient_sync.components.audio_change_alignment`
- 关闭 `syncnet_conf`
- 关闭 `syncnet_voiceover_still`
- 关闭 `synchformer_offset_s`
- 关闭 `timed_speaker_accuracy`
- 四个子项的 `checklist` 均保持开启

因此默认不会启动 Whisper、SyncNet、Synchformer 或多人说话人匹配的视觉判断，只会额外执行环境音变化对齐分析。已通过 YAML 解析和开关校验。

---

**User**

同样的思路分析一下第17维度建议开启哪些组件？

---

**Cursor**

<thinking>**Inspecting D17 components and runtime dependencies**</thinking>
我先对照第 17 维度的实现、默认配置和各组件的依赖链，按“运行时间、覆盖价值、是否适合批量评估”给出分层建议。

第 17 维度的主要差异是：`vlm_anomaly_rate` 会被六个异常类子项复用一次时间线结果，开启一个或多个相关子项时不会按子项重复运行；`VMBench` 也按结果复用。我要进一步确认人脸、身份漂移和光流组件的实际成本，并检查当前配置里是否存在没有 checklist 的子项。

<thinking>**Inspecting D17 hidden extra costs and scoring edge cases**</thinking>有一个会影响耗时的实现细节：第 17 维度只要开启任意数值异常组件，`extras()` 还会执行未计分的 FIRM 世界一致性诊断；如果 facts 标记有人，还可能额外启动骨架诊断。因此我需要把这些隐性开销也纳入建议，而不是只比较表面上的组件名。

考虑评估时间，第 17 维度我建议采用“两阶段”策略：

1. **批量默认评估：继续只开启 checklist**
2. **重点样本：开启 `vlm_anomaly_rate`，并视需要开启其他组件**

原因是第 17 维度中，最有性价比的数值组件不是单独的某个检测器，而是共享异常时间线的 `vlm_anomaly_rate`。

**推荐优先级**

**第一优先级：`vlm_anomaly_rate`**

它覆盖以下 6 个子项：

- `distortion_rate`
- `disappearance_rate`
- `duplication_rate`
- `attribute_drift_rate`
- `clipping`
- `camera_anomaly_rate`

这些子项都会复用同一个 `vlm_anomaly_timeline`，不会为每个子项单独调用一次视觉模型。其内部逻辑是先由视觉模型列出整段视频中的异常事件，再按异常类型和 1 秒窗口计算异常比例。

```19:24:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d17.py
    def _timeline(self, ctx: Context) -> dict:
        if ctx.active_components is not None and _VLM_OUTPUTS & ctx.active_components:
            ctx.active_components.add("vlm_anomaly_timeline")
        return ctx.comp("vlm_anomaly_timeline", lambda: {"status": "ok", **vision_judge.anomaly_timeline(
            ctx.client("vision"), ctx.video, ctx.case.intent, ctx.judge_fps, ctx.judge_max_frames)})
```

因此，如果要开启，建议把这 6 个子项的 `vlm_anomaly_rate` 一起开启，而不是只开其中一个。

**第二优先级：`vlm_severe_fraction`**

它用于 `collapse_duration`，统计严重异常片段占整段视频的比例。它也复用同一个异常时间线，因此在已经开启 `vlm_anomaly_rate` 的情况下，额外计算成本很小。

需要注意，`collapse_duration` 当前没有 checklist。若 `vlm_severe_fraction` 和 `vmbench_mss` 都关闭，这个子项就没有可评分组件。当前配置中确实存在这个情况。

**第三优先级：`flow_jerk_rate`**

它用于 `camera_anomaly_rate`，通过光流检测异常抖动、跳跃和非正常镜头运动。它不需要额外深度学习模型，单看组件本身属于较轻量的确定性分析。

不过当前实现有一个隐藏开销：只要开启任意数值异常组件，`extras()` 还会执行未计分的 FIRM 世界一致性判断；如果 facts 标记了有人，还会执行骨架诊断。因此当前代码下，`flow_jerk_rate` 并不一定是整个评估流程中最省时的选择。

```106:120:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d17.py
        if not enabled & diagnostic_components:
            return {}
        wc = ctx.comp("firm_world_consistency", lambda: firm.world_consistency(ctx.video, ctx.case.intent))
        sk = ctx.comp("skeleton", lambda: X.skeleton(ctx.video, ctx.work)) if ctx.facts.get("has_humans") else {}
        return {"firm_world_consistency": wc.get("score_1_5"),
                "skeleton_top_jerk_events": (sk.get("top_jerk_events") or [])[:10]}
```

**暂时不建议默认开启的组件**

- `face_duplicate_rate`：适合多人脸或可能出现人物复制的场景，但会运行 InsightFace 人脸检测与识别。
- `identity_drift_rate`：适合重点检查人物身份、服装、颜色连续性的场景，同样需要逐帧人脸分析。它和 `face_duplicate_rate` 当前没有共享 `video_faces` 扫描结果，同时开启会增加两次人脸处理。
- `skeleton_blc_cv`：只适合有人体且需要重点检查四肢、姿态和人体结构的样本。它会启动 RTMDet/RTMPose 外部环境，运行时间和环境依赖都较高。
- `vmbench_ois`、`vmbench_tcs`、`vmbench_mss`：不建议用于第一轮批量评估。开启任意一个都会运行完整的 VMBench 流程，包括 PAS、OIS、TCS、MSS，而不是只运行所选指标。

```34:38:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/components/external.py
    """Run VMBench PAS -> OIS -> TCS -> MSS (evaluate.sh order and arguments) on every shot clip >= 1 s
    and return duration-weighted means. MSS depends on PAS, hence PAS is run although it is not scored."""
```

**我建议的默认策略**

如果目标是控制批量评估时间，当前 `task_d17_example.yaml` 建议先保持所有数值组件关闭：

```yaml
evaluation:
  subpoints:
    distortion_rate:
      components:
        vlm_anomaly_rate: false
        vmbench_ois: false
        skeleton_blc_cv: false
        checklist: true
    disappearance_rate:
      components:
        vlm_anomaly_rate: false
        vmbench_tcs: false
        checklist: true
    duplication_rate:
      components:
        vlm_anomaly_rate: false
        face_duplicate_rate: false
        checklist: true
    attribute_drift_rate:
      components:
        vlm_anomaly_rate: false
        identity_drift_rate: false
        checklist: true
    clipping:
      components:
        vlm_anomaly_rate: false
        checklist: true
    camera_anomaly_rate:
      components:
        vlm_anomaly_rate: false
        flow_jerk_rate: false
        checklist: true
    collapse_duration:
      components:
        vlm_severe_fraction: false
        vmbench_mss: false
```

对于重点样本，推荐第二阶段改为：

- 6 个异常类型子项全部开启 `vlm_anomaly_rate`；
- `collapse_duration` 开启 `vlm_severe_fraction`；
- 暂时关闭 InsightFace、骨架和 VMBench；
- `checklist` 保持开启。

这能用一次异常时间线覆盖大部分异常控制子项，并补上 `collapse_duration` 的数值分数。需要明确的是，按照当前 `extras()` 实现，这样仍会附带执行 FIRM；有人体时还会附带执行骨架诊断。

---

**User**

那目前就先全部开启vlm_anomaly_rate，其他的组件关闭，还有点不理解这个是什么意思：需要明确的是，按照当前 extras() 实现，这样仍会附带执行 FIRM；有人体时还会附带执行骨架诊断。

---

**Cursor**

我会先按你的明确配置修改 `task_d17_example.yaml`：六个包含 `vlm_anomaly_rate` 的子项全部开启，其他计分组件全部关闭，checklist 保持原样。然后我会说明 `extras()` 触发的 FIRM 和骨架诊断为什么会出现，以及它们是否计入分数。

<thinking>**Checking configured component states**

已按你的要求修改 [task_d17_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d17_example.yaml)：

开启 `vlm_anomaly_rate` 的 6 个子项：

- `distortion_rate`
- `disappearance_rate`
- `duplication_rate`
- `attribute_drift_rate`
- `clipping`
- `camera_anomaly_rate`

其他计分组件全部关闭：

- `vmbench_ois`
- `vmbench_tcs`
- `vmbench_mss`
- `skeleton_blc_cv`
- `face_duplicate_rate`
- `identity_drift_rate`
- `flow_jerk_rate`
- `vlm_severe_fraction`

所有已有的 `checklist` 保持开启。配置校验已通过。

**`vlm_anomaly_rate` 是什么**

它会调用一次视觉语言模型，让模型查看整段视频的抽帧结果，找出以下类型的异常：

- 人体或物体畸变
- 主体无原因消失
- 主体复制
- 属性或身份漂移
- 穿模
- 镜头异常

之后程序按异常类型，把事件映射到 1 秒时间窗口，计算每类异常占全部窗口的比例。虽然 6 个子项都会使用 `vlm_anomaly_rate`，但异常时间线会被缓存，所以同一个视频不是调用 6 次模型，而是共享一次异常时间线结果。

```19:24:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d17.py
    def _timeline(self, ctx: Context) -> dict:
        if ctx.active_components is not None and _VLM_OUTPUTS & ctx.active_components:
            ctx.active_components.add("vlm_anomaly_timeline")
        return ctx.comp("vlm_anomaly_timeline", lambda: {"status": "ok", **vision_judge.anomaly_timeline(
            ctx.client("vision"), ctx.video, ctx.case.intent, ctx.judge_fps, ctx.judge_max_frames)})
```

**FIRM 和骨架诊断是什么意思**

它们不是你配置中开启的计分组件，而是当前代码里的“额外诊断”：

- **FIRM**：使用 FIRM-Video-8B 对视频均匀抽取的 8 帧进行世界一致性判断，例如动作是否违反基本物理规律、主体结构是否崩坏。它输出一个 1 到 5 分的诊断结果。
- **骨架诊断**：有人体时运行 RTMDet/RTMPose，分析人体关键点的抖动，并记录抖动最大的事件。

它们不会进入第 17 维度的分数，只会写入结果中的 `extras` 字段：

```106:120:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d17.py
        if not enabled & diagnostic_components:
            return {}
        wc = ctx.comp("firm_world_consistency", lambda: firm.world_consistency(ctx.video, ctx.case.intent))
        sk = ctx.comp("skeleton", lambda: X.skeleton(ctx.video, ctx.work)) if ctx.facts.get("has_humans") else {}
        return {"firm_world_consistency": wc.get("score_1_5"),
                "skeleton_top_jerk_events": (sk.get("top_jerk_events") or [])[:10]}
```

当前实现下，因为开启了 `vlm_anomaly_rate`，`extras()` 会附带执行 FIRM；如果该 case 的 facts 中 `has_humans: true`，还会附带执行骨架诊断。因此目前实际运行的是：

- 计分：checklist + `vlm_anomaly_rate`
- 不计分但可能运行：FIRM
- 不计分且仅有人体时运行：骨架诊断

所以“其他组件关闭”目前表示其他**配置中的计分组件**关闭；FIRM 和骨架属于代码自动触发的未计分诊断，不能仅通过当前 YAML 组件开关关闭。

---

**User**

那目前这两个的意思可能会触发，但是触发了也不计分的意思吗？

---

**Cursor**

是的，理解正确。

当前配置下：

- `vlm_anomaly_rate`：**会计分**，用于 6 个异常子项的数值评分，并与 checklist 合并计算。
- FIRM 世界一致性：**可能触发，但不计分**。它只写入结果里的 `extras.firm_world_consistency`。
- 骨架诊断：**有人体时可能触发，但不计分**。它只写入 `extras.skeleton_top_jerk_events`，记录人体抖动诊断信息。

具体触发条件是：

- FIRM：当前启用了 `vlm_anomaly_rate`，且评估门控通过时，会执行一次。
- 骨架诊断：在上述条件基础上，如果 checklist facts 中有 `has_humans: true`，会执行一次。
- 如果门控失败，`extras()` 不会执行。

它们不会影响：

- 第 17 维度总分；
- 各个子项分数；
- `strict_pass` 严格通过判断。

所以当前每个 case 的实际结果可以理解为：

```text
计分：
  checklist
  vlm_anomaly_rate

附加诊断，不计分：
  FIRM
  有人体时的骨架诊断
```

如果目标是严格做到“只运行 `vlm_anomaly_rate`，完全不运行 FIRM 和骨架诊断”，则还需要调整 `d17.py` 的 `extras()` 逻辑，把这些诊断改成显式配置开关，而不是由已启用的数值组件自动触发。

---

**User**

那现在可以修改成，如果触发了就进行计分吗？

---

**Cursor**

我先核对第 17 维度的评分定义：FIRM 和骨架目前只是 `extras` 诊断，二者没有直接对应的第 17 维度计分项；其中骨架已有可计分的 `skeleton_blc_cv`，但 FIRM 没有。为了避免把“触发”误改成没有评分定义的结果，我需要确认现有评分结构能怎样接入。

<thinking>**Determining scoring semantics for implicit diagnostics**</thinking>
可以，但两者需要分开处理：骨架已经有现成的计分组件 `skeleton_blc_cv`，开启后可按“人体畸变率”现有权重计分；FIRM 目前只是一个 1–5 的附加诊断，没有挂到第 17 维度任何子项，也没有定义权重，不能直接“触发即计分”而不改变评分规则。FIRM 应该归入哪个子项和占多少权重，需要你确认后我再修改。

**确定第17维度计分方式**

> **第17维度中，FIRM 世界一致性如何纳入计分？骨架组件我建议直接开启 `skeleton_blc_cv`，沿用“人体畸变率”现有 0.3 权重。**
> - 推荐：只让骨架 `skeleton_blc_cv` 计分；FIRM 保持附加诊断，不计分 ✔
> - 让 FIRM 加入“崩坏持续时间”，与 `vlm_severe_fraction`、`vmbench_mss` 一起按新权重计分
> - 新增独立的“世界一致性”子项，让 FIRM 作为该子项的计分组件

你选择的是“骨架计分、FIRM 仍只作附加诊断”。我现在把 `skeleton_blc_cv` 开启；它会沿用人体畸变率中已有的 0.3 权重参与计分，FIRM 仍不会进入任何第 17 维度分数。

<thinking>**Validating configuration and correcting comment terminology**</thinking>骨架组件已改为计分开启。我会再校验配置，确保六个 `vlm_anomaly_rate` 和 `skeleton_blc_cv` 开启，VMBench、InsightFace、光流及其他数值组件仍关闭；同时把注释中的无关术语整理掉。

已按“触发后计分”的可实现部分修改配置：

- 6 个子项全部开启 `vlm_anomaly_rate`；
- `distortion_rate` 开启 `skeleton_blc_cv`；
- `vmbench_ois`、`vmbench_tcs`、`vmbench_mss`、`face_duplicate_rate`、`identity_drift_rate`、`flow_jerk_rate`、`vlm_severe_fraction` 继续关闭；
- 所有 checklist 保持开启。

骨架组件会按照配置中“人体畸变率”的现有权重参与计分：

```yaml
distortion_rate:
  components:
    vlm_anomaly_rate: true
    vmbench_ois: false
    skeleton_blc_cv: true
    checklist: true
```

对应权重是：

- `vlm_anomaly_rate`: 0.4
- `skeleton_blc_cv`: 0.3
- `checklist`: 0.3

也就是说，骨架的肢体长度变异系数会先映射到 1–5 分，再和异常时间线、checklist 合并成 `distortion_rate` 分数。没有人体或人体姿态不足时，骨架组件会标记为不适用，其余组件权重会重新归一化。

FIRM 仍然不会计分。原因是 FIRM 当前没有对应的第 17 维度评分组件和权重；它只会在启用异常数值评估后作为附加诊断运行，并写入 `extras.firm_world_consistency`。本次配置校验已通过。

---

**User**

那接下来再分析一下第18维度的评估子项的组件建议开启哪些吧？

---

**Cursor**

<thinking>**Inspecting D18 components and runtime dependencies****Analyzing OCR component costs and applicability**</thinking>
我先核对第 18 维度各子项的适用条件、OCR 共享依赖和组件实际运行链路，再按评估时间与覆盖价值给出默认开启建议。

<thinking>**Inspecting OCR implementation details and costs**</thinking>
第 18 维度的关键点与前面不同：所有 OCR 数值子项共享一次 PP-OCRv5 抽帧识别。也就是说，开启一个 OCR 子项已经会承担主要 OCR 成本，其他适用 OCR 子项的额外计算通常很小。我再核对各项输入条件和异常处理后给出具体默认组合。

第 18 维度如果考虑“评估时间与覆盖范围”的平衡，我建议 **5 个 OCR 数值组件全部开启**，因为它们共享同一次 PP-OCRv5 识别，额外增加的主要是本地结果计算，不会为每个子项重新跑 OCR。

建议配置：

```yaml
evaluation:
  subpoints:
    text_accuracy:
      components:
        ocr_cer: true
        checklist: true
    subtitle_completeness:
      components:
        ocr_subtitle_alignment: true
        checklist: true
    readability:
      components:
        ocr_readability: true
        checklist: true
    temporal_stability:
      components:
        ocr_text_stability: true
        checklist: true
    no_unrequested_text:
      components:
        ocr_unexpected_text_rate: true
        checklist: true
```

各组件对应关系如下：

- `ocr_cer`：检查要求出现的文字是否错字、漏字或乱码。
  - 仅在 `facts.expected_texts` 存在时适用。
- `ocr_subtitle_alignment`：检查字幕是否完整、按顺序出现。
  - 仅在 `facts.subtitles_required` 为真时适用。
- `ocr_readability`：检查要求文字或字幕是否清晰可读。
  - 有要求文字或字幕时适用。
- `ocr_text_stability`：检查要求文字是否闪烁、变形、漂移或中途消失。
  - 仅在 `facts.expected_texts` 存在时适用。
- `ocr_unexpected_text_rate`：检查是否出现未要求的字幕、水印或其他杂字。
  - 这个子项没有 `applies` 条件，通常每条视频都会评估。

代码中所有数值组件都会共享 `ocr` 结果：

```8:20:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/d18.py
_OCR_OUTPUTS = frozenset({
    "ocr_cer", "ocr_subtitle_alignment", "ocr_readability",
    "ocr_text_stability", "ocr_unexpected_text_rate",
})


class Text18(DimensionEvaluator):
    dimension = "18_text_subtitle"

    def _ocr(self, ctx: Context) -> dict:
        if ctx.active_components is not None and _OCR_OUTPUTS & ctx.active_components:
            ctx.active_components.add("ocr")
        return ctx.comp("ocr", lambda: X.ocr_frames(T.ocr_frame_files(ctx.video, ctx.work), ctx.work))
```

实际运行流程是：

```text
视频抽取最多 60 帧
    -> PP-OCRv5 检测和识别一次
    -> ocr_cer / subtitle_alignment / readability /
       text_stability / unexpected_text_rate 分别计算
```

一次 OCR 大约处理 3 fps、最多 60 帧，已有文档记录的耗时约为 20–30 秒。只开启其中一个 OCR 子项通常也要承担这次主要成本，因此从成本角度看，**只开一个并不能明显节省时间**。全部开启后，适用条件不满足的子项会标记为 `not_applicable`，不会影响其他适用子项。

所以我的建议是：

- 批量评估第 18 维度：5 个 OCR 数值组件全部开启；
- 保留所有 checklist；
- 不需要额外关闭某个 OCR 子项，除非你明确不关心某类结果；
- 如果只想做最快的 checklist-only 预筛选，才把 5 个 OCR 组件全部关闭。

目前我还没有修改 `task_d18_example.yaml`，因为你这次是在确认组件建议。

---

**User**

那就先全部默认开启吧。

---

**Cursor**

<thinking>**Editing D18 example config**</thinking>
我会把第 18 维度示例配置中的 5 个 OCR 数值组件全部开启，保留各子项的 checklist，并在注释中同步说明 OCR 结果共享、只执行一次 PP-OCRv5 抽帧识别。

<thinking>**Validating D18 component toggles**

已修改 [task_d18_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d18_example.yaml)，5 个 OCR 数值组件现在全部默认开启：

- `ocr_cer`
- `ocr_subtitle_alignment`
- `ocr_readability`
- `ocr_text_stability`
- `ocr_unexpected_text_rate`

所有 checklist 也保持开启。由于这些组件共享同一次 PP-OCRv5 抽帧识别，因此不会为每个子项重复执行 OCR。已通过 YAML 解析和组件开关校验。

---

**User**

目前这13-18个维度评测完是不是只在终端中会显示最终的结果？

---

**Cursor**

<thinking>**Inspecting evaluation output flow**</thinking>
我先检查 13–18 维度的运行入口、结果文件写入和终端汇总逻辑，确认最终结果到底只输出到终端，还是同时落盘到 JSON/报告文件。

不是只在终端显示。当前 13–18 维度评测完成后，结果会同时输出到终端并保存到文件。

以任务配置中的：

```yaml
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/task_d18_t2va
run_name: task_d18_t2va
```

为例，主要输出目录是：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/task_d18_t2va/
└── runs/
    └── task_d18_t2va/
        ├── 18_text_subtitle/
        │   ├── t2va_06/
        │   │   ├── result.json
        │   │   └── components/
        │   └── t2va_07/
        │       ├── result.json
        │       └── components/
        ├── per_case.jsonl
        ├── summary.json
        └── summary.md
```

各文件用途如下：

- `result.json`：单个 case 的完整评测结果，包括维度分数、各子项分数、实际使用的组件、被关闭或不可用的组件、缺失原因、`extras` 等。
- `components/`：各个组件的缓存结果，例如 OCR、VLM 异常时间线、骨架组件等，便于重新运行时复用。
- `per_case.jsonl`：所有 case 的逐条结果，每行一个 case。
- `summary.json`：结构化的汇总结果，适合后续脚本读取。
- `summary.md`：人类阅读的汇总报告，包含维度平均分和相关统计。

代码会在每个 case 评估结束时把结果写入该 case 的 `result.json`：

```165:173:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/base.py
        out = score_dimension(dim_cfg, results, cfg, gate=gate, audio_gate_failed=audio_failed)
        out["evaluation_overrides"] = task_eval
        out["extras"] = self.extras(ctx) if gate["passed"] else {}
        out["media_warnings"] = ctx.case.media_warnings
        with open(os.path.join(ctx.results_dir, "result.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2, default=float)
        return out
```

当运行包含 `score` 阶段时，程序还会生成汇总文件，并把 `summary.md` 打印到终端：

```247:259:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py
        for c in cases:
            p = os.path.join(run_dir, c.dimension, c.case_id, "result.json")
            if os.path.exists(p):
                rows.append({"case_id": c.case_id, "dimension": c.dimension, "input_form": c.input_form,
                             "video": c.video, "result": json.load(open(p, encoding="utf-8"))})
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "per_case.jsonl"), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")
        table = aggregate(rows, cfg["dimensions"])
        json.dump(table, open(os.path.join(run_dir, "summary.json"), "w"), ensure_ascii=False, indent=2)
        md = summary_markdown(table, cfg["dimensions"], args.run_name)
        open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8").write(md)
        print(md)
```

因此，当前示例配置中的：

```yaml
stages:
  - check
  - checklist
  - evaluate
  - score
```

会同时完成：

1. 终端显示检查、进度、每个 case 的分数和最终汇总；
2. 保存每个 case 的 `result.json`；
3. 保存整体 `per_case.jsonl`、`summary.json` 和 `summary.md`。

需要注意的是，如果只运行：

```bash
--stages evaluate
```

则只会生成单个 case 的 `result.json`，不会生成最终的 `summary.json` 和 `summary.md`。要得到整体汇总，需要包含 `score` 阶段。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick
我现在要用13-18维度评估来测试一下这个文件夹下面的对应的不同的任务类型的视频，你给出一下命令已经我需要对应修改的一些配置，你不要进行测评，而是我自己手动进行评估。

---

**Cursor**

<thinking>**Inspecting target dataset layout and task configuration requirements**</thinking>
我先检查 `vgen_quick` 下的任务类型目录和现有 13–18 配置模板，确认每种输入形式对应的 `mode`、case ID 写法以及输出目录应该如何设置。只做结构核对，不会启动任何评测。

刚才目标目录的文件扫描没有返回条目，说明它可能是空目录、目录层级不同，或视频路径不是普通文件布局。我再确认目录本身、一级子目录和各模式命名；如果确实为空，我会给你可直接替换路径的命令模板，并明确需要先核对的地方。

<thinking>**Inspecting case names and file conventions**

<thinking>**Inspecting reference usage and exact case IDs**</thinking>
目录结构已经明确：共有 `delivery` 和 `online` 两组，每组包含 `t2va`、`f2va`、`r2va` 三种实际输入形式，共 12 个视频 case。由于这些目录没有 300case 所需的 `meta.json` 和维度目录层级，应使用现有的 `task config` 模式逐个维度运行。接下来我确认 r2va 的 prompt 是否引用图片，以便给出准确的参考图配置。

<thinking>**Checking video file validity before giving run commands**</thinking>目标目录的 12 个 `video.mp4` 文件目前只有约 127–130 字节，这很像 Git LFS 指针或占位文件，不像可解码视频。我先读取文件类型和内容头，避免给你一套必然在 `checklist/evaluate` 阶段失败的命令。

这个目录可以用于手动评测，但需要按“输入来源 + 输入形式 + 维度”分别运行。当前目录实际包含：

- `delivery_fl2va/t2va`：2 个 case
- `delivery_fl2va/f2va`：2 个 case
- `delivery_ref2va/r2va`：2 个 case
- `online_fl2va/t2va`：2 个 case
- `online_fl2va/f2va`：2 个 case
- `online_ref2va/r2va`：2 个 case

总共 6 组输入，每组 2 个视频。当前没有 `l2va` 或真正的 `fl2va` 子目录，因此不要根据父目录名 `fl2va` 设置 mode，应以实际子目录为准。

`video.mp4` 是指向 `work-log/work_300case/original/` 下原始视频的软链接，配置中可以直接使用。

**一、需要运行多少次**

当前 task 配置一次只能指定一个维度，因此完整评测需要：

```text
6 组输入形式 × 6 个维度 = 36 次 task 运行
```

每次运行使用一个维度配置文件，例如：

```text
task_d13_quick_delivery_t2va.yaml
task_d14_quick_delivery_t2va.yaml
...
task_d18_quick_delivery_t2va.yaml
```

**二、每种输入形式的配置修改**

可以复制现有的 6 个示例配置：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

for d in 13 14 15 16 17 18; do
  cp "configs/task_d${d}_example.yaml" \
     "configs/task_d${d}_quick_delivery_t2va.yaml"
  cp "configs/task_d${d}_example.yaml" \
     "configs/task_d${d}_quick_delivery_f2va.yaml"
  cp "configs/task_d${d}_example.yaml" \
     "configs/task_d${d}_quick_delivery_r2va.yaml"
  cp "configs/task_d${d}_example.yaml" \
     "configs/task_d${d}_quick_online_t2va.yaml"
  cp "configs/task_d${d}_example.yaml" \
     "configs/task_d${d}_quick_online_f2va.yaml"
  cp "configs/task_d${d}_example.yaml" \
     "configs/task_d${d}_quick_online_r2va.yaml"
done
```

这些命令只复制配置，不会启动评测。

每个复制出来的配置只需要修改以下字段：

```yaml
task_name: quick_delivery_t2va_d13
run_name: quick_delivery_t2va_d13

input:
  root: /对应的输入目录
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
```

使用 `case_ids: []` 表示评估该目录下的全部直接子目录，也就是当前的两个 case。不需要手动填写 case ID。

**三、6 种输入形式的具体配置**

1. `delivery` 的 `t2va`

```yaml
task_name: quick_delivery_t2va_d13
run_name: quick_delivery_t2va_d13

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/delivery_fl2va/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
```

`t2va` 配置中不要保留 `references:` 块。

2. `delivery` 的 `f2va`

```yaml
task_name: quick_delivery_f2va_d13
run_name: quick_delivery_f2va_d13

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/delivery_fl2va/f2va
  mode: f2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    first_frame_filename: input_01
```

3. `delivery` 的 `r2va`

```yaml
task_name: quick_delivery_r2va_d13
run_name: quick_delivery_r2va_d13

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/delivery_ref2va/r2va
  mode: r2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    image_pattern: input_{index:02d}
    image_extensions: [.png, .jpg, .jpeg, .webp]
```

当前两个 `r2va` case 的 prompt 都引用了 `<Picture 1>`，所以 `input_{index:02d}` 会解析为 `input_01`。这里不需要配置 `video_pattern` 或 `audio_pattern`。

4. `online` 的 `t2va`

```yaml
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/online_fl2va/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []
```

5. `online` 的 `f2va`

```yaml
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/online_fl2va/f2va
  mode: f2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    first_frame_filename: input_01
```

6. `online` 的 `r2va`

```yaml
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/online_ref2va/r2va
  mode: r2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    image_pattern: input_{index:02d}
    image_extensions: [.png, .jpg, .jpeg, .webp]
```

**四、输出目录必须区分**

每个配置的 `output_dir` 建议使用独立目录。例如：

```yaml
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_eval_results/delivery_t2va_d13
```

建议命名为：

```text
delivery_t2va_d13
delivery_f2va_d13
delivery_r2va_d13
online_t2va_d13
online_f2va_d13
online_r2va_d13
```

第 14 到第 18 维度同理，把末尾的 `d13` 替换成对应维度编号。这样不同来源、输入形式和维度的结果不会互相覆盖。

每个配置还要同步修改：

```yaml
task_name: quick_delivery_t2va_d13
run_name: quick_delivery_t2va_d13
```

**五、运行命令**

配置修改完成后，在 `tools/vgen_eval` 目录下运行：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval
python3 run.py \
  --task-config /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d13_quick_delivery_t2va.yaml
```

一次运行 13 到 18 六个维度，可以使用：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

for d in 13 14 15 16 17 18; do
  python3 run.py \
    --task-config "/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d${d}_quick_delivery_t2va.yaml"
done
```

其他 5 组输入形式分别运行：

```bash
for mode in delivery_t2va delivery_f2va delivery_r2va \
            online_t2va online_f2va online_r2va; do
  for d in 13 14 15 16 17 18; do
    python3 run.py \
      --task-config "/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d${d}_quick_${mode}.yaml"
  done
done
```

前提是你已经按照上面的规则创建并修改了 36 个配置文件。

每个配置当前的 stages 已经是：

```yaml
stages:
  - check
  - checklist
  - evaluate
  - score
```

因此运行后会执行完整流程，并生成：

```text
<output_dir>/runs/<run_name>/
├── <dimension>/<case_id>/result.json
├── per_case.jsonl
├── summary.json
└── summary.md
```

如果你只想先检查路径和服务，不进行评测，需要临时把对应配置改成：

```yaml
stages:
  - check
```

检查完成后，再恢复为 `check`、`checklist`、`evaluate`、`score` 四个阶段。对于 task 配置，命令行中的 `--stages` 不会覆盖 YAML 里的 stages，所以需要直接修改配置文件。

当前维度配置会沿用已经确定的组件设置：

- 第 16 维度：开启 `audio_change_alignment`，其他数值同步组件关闭；
- 第 17 维度：开启 `vlm_anomaly_rate`，并开启 `skeleton_blc_cv`，其他计分数值组件关闭；
- 第 18 维度：5 个 OCR 数值组件全部开启；
- 第 14、15 维度：沿用当前示例配置中的开关；
- 第 13 维度：沿用当前 `task_d13_example.yaml` 中的开关设置。

---

**User**

如果我在评估t2va的时候，配置中写了reference，会影响t2va的评估吗？

---

**Cursor**

<thinking>**Verifying t2va reference handling**</thinking>
我核对一下任务输入解析逻辑，确认 `t2va` 是否会读取或绑定 `references` 中的文件。

不会。只要配置中的 `input.mode: t2va`，即使同时写了 `references`，评估程序也不会读取或绑定这些参考文件。

任务解析逻辑只在以下模式下处理参考输入：

- `f2va` / `fl2va`：读取 `first_frame_filename`
- `l2va` / `fl2va`：读取 `last_frame_filename`
- `r2va`：根据 prompt 中引用的图片、视频或音频标记读取参考素材

`t2va` 不会进入这些分支：

```224:253:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/cases.py
        first_frame = last_frame = None
        reference_images, reference_videos, reference_audios = [], [], []
        if mode in ("f2va", "fl2va"):
            ...
        if mode in ("l2va", "fl2va"):
            ...
        if mode == "r2va":
            ...
```

因此下面这种配置在实际效果上等价于没有 `references`：

```yaml
input:
  root: /path/to/t2va
  mode: t2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    first_frame_filename: input_01
    last_frame_filename: input_02
```

对于 `t2va`，程序会把：

- `first_frame` 设置为 `None`
- `last_frame` 设置为 `None`
- `reference_images` 设置为空列表
- `reference_videos` 设置为空列表
- `reference_audios` 设置为空列表

所以 checklist、各维度组件和最终分数都不会因为这个 `references` 配置而改变。

不过建议为了避免误解，`t2va` 配置中直接删除整个 `references:` 块。只有切换到 `f2va`、`l2va`、`fl2va` 或 `r2va` 时，再按对应模式填写参考配置。

---

**User**

@task_d13_example.yaml (13-14) 
配置中这两的作用是什么？

---

**Cursor**

`task_name` 和 `run_name` 都是运行名称，但作用不同：

```yaml
task_name: delivery_t2va_d13
run_name: delivery_t2va_d13
```

- `task_name`：任务配置本身的名称，主要用于识别这个 YAML 配置。程序在加载配置时，如果没有单独设置 `run_name`，会用 `task_name` 作为默认运行名称。
- `run_name`：本次评测结果的目录名称，实际决定结果保存到哪个运行目录。

当前程序会把结果保存到：

```text
<output_dir>/runs/<run_name>/
```

因此当前配置的结果目录是：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_928/test/hb_fl2va_test/runs/delivery_t2va_d13/
```

其中会包含：

```text
delivery_t2va_d13/
├── 13_style_visual_control/
│   └── <case_id>/
│       └── result.json
├── per_case.jsonl
├── summary.json
└── summary.md
```

代码中，`run_name` 会直接参与结果目录拼接：

```174:176:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/run.py
        args.run_name = task.get("run_name", task.get("task_name", "task_run"))
        task_out = task.get("output_dir", os.path.join(HERE, "outputs"))
```

而 `task_name` 只是在没有配置 `run_name` 时作为备用值。

建议两个名称保持一致，并且明确包含：

```text
数据来源_输入形式_维度
```

例如：

```yaml
task_name: delivery_t2va_d13
run_name: delivery_t2va_d13
```

含义是：

- `delivery`：数据来源；
- `t2va`：文本到视频输入形式；
- `d13`：第 13 维度。

对于第 14 维度，可以写成：

```yaml
task_name: delivery_t2va_d14
run_name: delivery_t2va_d14
```

对于同一数据和模式，不建议多个评测配置使用相同的 `run_name`，否则它们会写入同一个：

```text
<output_dir>/runs/<run_name>/
```

可能覆盖或混合已有的 `result.json`、`summary.json` 和 `summary.md`。

---

**User**

@task_d13_example.yaml (29-38) 
我如果这样设置来测试r2va，会出现什么错误？我应该怎么设置？

---

**Cursor**

我先检查这段配置所在的缩进、`mode` 和 `root`，再结合 `r2va` 的解析规则判断会报什么错，以及给出与你当前目录结构匹配的写法。只做配置分析，不启动评测。

如果你把这段配置用于 `r2va`，需要同时修改 `mode` 和 `root`。当前配置本质上还是 `f2va`：

```yaml
input:
  root: .../online_fl2va/f2va
  mode: f2va
```

**当前这段配置不会因为多写了 `image_pattern`、`video_pattern`、`audio_pattern` 而报错。** 在 `f2va` 模式下，程序只读取 `first_frame_filename`，后面的三个 pattern 会被忽略。代码只有在 `mode == "r2va"` 时才会解析这些 pattern：

```240:253:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/cases.py
        if mode == "r2va":
            for kind, key, exts, target in (
                    ("image", "image_pattern", image_exts, reference_images),
                    ("video", "video_pattern", video_exts, reference_videos),
                    ("audio", "audio_pattern", audio_exts, reference_audios)):
                pattern = refs_cfg.get(key)
                if not pattern:
                    continue
                for index in referenced_indices(prompt, kind):
                    path = _pattern_path(case_dir, pattern, index=index, extensions=exts)
```

但是如果你只是把：

```yaml
mode: f2va
```

改成：

```yaml
mode: r2va
```

而不修改 `root`，程序会去错误的 `f2va` 目录下按 `r2va` 方式寻找 case。正确做法是把 root 也改到 `r2va` 目录。

**以 online 的 r2va 为例**

```yaml
task_name: online_r2va_d13
run_name: online_r2va_d13

dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/online_ref2va/r2va
  mode: r2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    image_pattern: input_{index:02d}
    image_extensions: [.png, .jpg, .jpeg, .webp]
```

你当前的 `online_ref2va/r2va` 目录中有：

```text
cn300v2_07e78d618c8ac2e71e469c89/input_01.png
cn300v2_096377fa92e90a3a7fdc321c/input_01.jpg
```

两个 prompt 都引用了 `<Picture 1>`，因此：

```yaml
image_pattern: input_{index:02d}
```

会把 `<Picture 1>` 映射到每个 case 下的：

```text
input_01.png
```

或：

```text
input_01.jpg
```

程序会根据配置的扩展名自动匹配。

当前这些 r2va case 没有参考视频或参考音频，所以建议删除：

```yaml
video_pattern: ref_video_{index:02d}
audio_pattern: ref_audio_{index:02d}
video_extensions: [...]
audio_extensions: [...]
```

它们虽然不会在当前 prompt 没有引用视频或音频时触发错误，但没有必要保留。

**delivery 的 r2va 配置只需要替换路径和名称：**

```yaml
task_name: delivery_r2va_d13
run_name: delivery_r2va_d13

dimension: 13_style_visual_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/delivery_ref2va/r2va
  mode: r2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    image_pattern: input_{index:02d}
    image_extensions: [.png, .jpg, .jpeg, .webp]
```

**如果保留当前配置并运行，可能出现的情况**

- `mode` 仍是 `f2va`：程序按 f2va 处理，`image_pattern` 等字段被忽略；
- `root` 仍是 `.../online_fl2va/f2va`：评估的是 f2va case，不是 r2va case；
- `mode` 改为 `r2va` 但 root 不改：会错误地把 f2va 目录当成 r2va 目录，参考图解析可能失败；
- `mode: r2va`、root 改正确、配置只保留 `image_pattern`：可以正确加载 r2va 参考图。

因此最重要的是这三个字段必须配套：

```yaml
root: .../online_ref2va/r2va
mode: r2va
references:
  image_pattern: input_{index:02d}
```

另外，`task_name`、`run_name` 和 `output_dir` 也建议改成 `online_r2va_d13`，避免和之前的 `online_f2va_d13` 结果混在一起。

---

**User**

第13维度只有2两个评价子项吗？

---

**Cursor**

<thinking>**Inspecting D13 subpoints configuration**</thinking>
我核对第 13 维度的评分配置和示例任务配置，确认它包含多少个子项，以及哪些是当前示例中实际保留的组件。

不是。第 13 维度在评分配置中定义了 **5 个评价子项**：

1. `style_accuracy`：风格准确性  
2. `style_persistence`：风格持续性  
3. `style_content_compat`：风格与内容兼容  
4. `lighting_control`：光照控制  
5. `color_control`：色彩控制  

配置位置：

```67:91:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/dims_13_18.yaml
  13_style_visual_control:
    name_zh: 风格与视觉控制
    subpoints:
      style_accuracy:
        ...
      style_persistence:
        ...
      style_content_compat:
        ...
      lighting_control:
        ...
      color_control:
        ...
```

但不是每个视频都一定会有 5 个子项进入最终平均分。第 13 维度有两个条件子项：

- `lighting_control` 只有 `facts.target_lighting` 存在时适用；
- `color_control` 只有 `facts.target_colors` 存在时适用。

另外 3 个子项没有 `applies` 条件，通常都会评估：

- `style_accuracy`
- `style_persistence`
- `style_content_compat`

因此一个具体 case 可能是：

```text
没有明确光照要求、没有明确颜色要求：
3 个适用子项
```

也可能是：

```text
有光照要求，没有颜色要求：
4 个适用子项
```

或者：

```text
有光照要求，也有颜色要求：
5 个适用子项
```

你当前 `task_d13_example.yaml` 中关闭的是部分**数值组件**，不是关闭评价子项：

```51:58:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d13_example.yaml
evaluation:
  subpoints:
    style_content_compat:
      components:
        checklist: true
        firm_world_consistency: false
    color_control:
      components:
        checklist: true
        palette_match: false
```

这表示：

- `style_content_compat` 仍然评估，但只使用 checklist，不运行 FIRM；
- `color_control` 仍然评估，但只使用 checklist，不运行 `palette_match`；
- 其他子项仍按照评分配置中的默认组件执行；
- 如果 `color_control` 不适用，它会被标记为 `not_applicable`，不会进入维度平均分。

所以要区分：

```text
评价子项：5 个
实际适用的子项：根据 facts 可能是 3、4 或 5 个
每个子项中的数值组件：可以通过 task 配置单独开启或关闭
```

最终 `result.json` 中的 `subpoints` 会列出这 5 个子项，并通过每个子项的 `applicable` 字段说明它是否参与当前 case 的评分。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d13_example.yaml为什么只展示了两个出来？

---

**Cursor**

<thinking>**Inspecting task config override semantics**</thinking>
我核对示例配置和评估器对 `evaluation.subpoints` 的处理方式，说明为什么文件里只写了两个子项，而其他三个没有展开。

<thinking>**Explaining partial overrides versus full subpoint listing**</thinking>
因为 `task_d13_example.yaml` 里的 `evaluation.subpoints` 不是完整的第 13 维度定义，而是**只写需要覆盖默认值的两个子项**。

当前配置中展示的两个是：

```yaml
evaluation:
  subpoints:
    style_content_compat:
      components:
        checklist: true
        firm_world_consistency: false
    color_control:
      components:
        checklist: true
        palette_match: false
```

它们分别表示：

- `style_content_compat`：保留 checklist，关闭 FIRM；
- `color_control`：保留 checklist，关闭颜色匹配数值组件。

注释也说明了这一点：

```yaml
# Per-subpoint component switches. Unspecified components retain scoring-config defaults.
```

意思是：**没有在 task 配置里写出来的子项，继续使用 `configs/dims_13_18.yaml` 中的默认组件配置。**

因此，下面三个子项虽然没有出现在 `task_d13_example.yaml` 里，运行时仍然会被遍历和评估：

- `style_accuracy`
- `style_persistence`
- `lighting_control`

评估器会遍历完整维度配置中的所有子项：

```148:164:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/base.py
        for sp, sp_cfg in dim_cfg["subpoints"].items():
            sp_override = (task_eval.get("subpoints", {}) or {}).get(sp, {}) or {}
            if sp_override.get("enabled", True) is False:
                results[sp] = {"applicable": False, "status": "disabled", "score": None,
                               "disabled_by_task_config": True}
                continue
            if not applies(sp_cfg.get("applies"), ctx.facts, ctx.case):
                results[sp] = {"applicable": False, "status": "not_applicable", "score": None}
                continue
```

对于没有写 override 的子项，`sp_override` 是空字典，组件开关默认按 `True` 处理：

```159:163:/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/vgen_eval/dims/base.py
            component_overrides = sp_override.get("components", {}) or {}
            ctx.active_components = {
                name for name in sp_cfg["components"] if component_overrides.get(name, True) is True
            }
```

所以当前第 13 维度的实际组件状态是：

```text
style_accuracy:
  checklist 开启
  csd_ref_similarity 默认开启

style_persistence:
  checklist 开启
  csd_temporal_drift 默认开启

style_content_compat:
  checklist 开启
  firm_world_consistency 关闭

lighting_control:
  checklist 开启
  只有 facts.target_lighting 存在时适用

color_control:
  checklist 开启
  palette_match 关闭
```

如果你希望配置文件中明确展示全部 5 个子项，可以写成：

```yaml
evaluation:
  subpoints:
    style_accuracy:
      components:
        csd_ref_similarity: true
        checklist: true

    style_persistence:
      components:
        csd_temporal_drift: true
        checklist: true

    style_content_compat:
      components:
        firm_world_consistency: false
        checklist: true

    lighting_control:
      components:
        checklist: true

    color_control:
      components:
        palette_match: false
        checklist: true
```

但这只是把默认行为显式写出来，评估结果不会因此改变。对于当前任务配置，保留两个需要特殊关闭组件的子项是合理的写法。

---

**User**

我需要你把默认的也写出来，

---

**Cursor**

<thinking>**Planning explicit D13 overrides**</thinking>
我会只补全 `evaluation.subpoints`，把原本依赖默认值的三个子项显式写出来，并保留当前已经设置的 `style_content_compat` 和 `color_control` 开关不变。这样配置文件会完整展示第 13 维度的 5 个子项及其组件状态。

<thinking>**Planning YAML validation and inspection**</thinking>

配置已经补全；刚才的校验脚本比较了错误的层级，导致断言失败，并不代表 YAML 有问题。我会按实际的 `components` 层级重新校验一次。

已修改 [task_d13_example.yaml](/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d13_example.yaml)，现在 5 个第 13 维度评价子项都显式写在配置中：

- `style_accuracy`
  - `csd_ref_similarity: true`
  - `checklist: true`
- `style_persistence`
  - `csd_temporal_drift: true`
  - `checklist: true`
- `style_content_compat`
  - `firm_world_consistency: false`
  - `checklist: true`
- `lighting_control`
  - `checklist: true`
- `color_control`
  - `palette_match: false`
  - `checklist: true`

已通过 YAML 解析和配置内容校验。配置行为与修改前一致，只是把原先隐含使用的默认设置明确写出来了。

---

**User**

目前每个维度里面的子项如果用到模型，是在哪台gpu上启动？

---

**Cursor**

我会按 13–18 维度当前配置，把模型分成三类核对：独立评审服务、评测进程本地加载、外部环境子进程；然后说明各自通过什么配置决定 GPU。

我会按“每个子项的实际执行进程、设备参数和环境变量”逐项核对代码，区分主评测进程、外部子进程和远程评委服务，最后给出物理 GPU 映射表。

按当前推荐启动方式，物理 GPU 分配如下：

- **GPU 0**：视觉评委服务 `Qwen3-VL`
- **GPU 1**：音频评委服务 `Qwen2.5-Omni`
- **GPU 2**：主评测进程及其本地加载的模型
- **GPU 3**：外部子进程，例如 VMBench、GroundingDINO、骨架检测、OCR
- **CPU**：明确使用 CPU 的传统算法或 CPU 默认推理组件

在 `CUDA_VISIBLE_DEVICES=2` 的主进程中，代码里的 `cuda`、`cuda:0` 和 `ctx_id=0` 都对应物理 GPU 2。外部进程被设置为 `CUDA_VISIBLE_DEVICES=3` 后，其内部 `cuda:0` 对应物理 GPU 3。

## D13：`13_style_visual_control`

- `csd_ref_similarity`：GPU 2
- `csd_temporal_drift`：GPU 2
- `firm_world_consistency`：GPU 2
- `palette_match`：CPU
- checklist、`lighting_control`、视觉类风格问题：视觉评委 GPU 0

当前示例配置中，主要是 CSD 使用 GPU 2；`firm_world_consistency` 当前计分项关闭，但可能由 `extras()` 作为诊断运行。

## D14：`14_edit_controllable_gen`

- `arcface_identity_keep`：GPU 2
- `dino_bg_consistency`：GPU 2，当前示例关闭
- `masked_lpips_static`：GPU 2，当前示例关闭
- `continuation_seam_lpips`：GPU 2
- `endpoint_lpips`：GPU 2
- `gdino_presence`：外部 GPU 3，运行在 VMBench/GroundingDINO 子进程中
- `endpoint_psnr`：CPU
- checklist、编辑准确性和视觉问题：视觉评委 GPU 0

当前 D14 示例实际主要使用 ArcFace、视频延展 LPIPS 和首尾帧 LPIPS，均在 GPU 2。

## D15：`15_audio_generation`

- `asr_cer` / Whisper large-v3：GPU 2，当前示例关闭
- `vad_speech_absent` / Silero VAD：CPU
- `dnsmos_ovr` / DNSMOS ONNX：默认 CPU
- `audiobox_pq`：无法仅凭仓库代码确定，使用 AudioBox 第三方库的默认设备
- `ecapa_same_speaker`、`ecapa_reference`：GPU 2，当前示例关闭
- `emotion2vec_match`：GPU 2，当前示例关闭
- `clap_ambient`、`clap_sfx`、`clap_music`：GPU 2
- `music_presence` / PANNs：GPU 2
- 音频 checklist：音频评委 GPU 1

当前 D15 示例启用的主要模型是：

- Silero VAD：CPU
- CLAP：GPU 2
- PANNs：GPU 2

## D16：`16_av_sync`

- Whisper ASR：GPU 2，当前示例关闭
- `syncnet_conf`：GPU 2，当前示例关闭
- `syncnet_voiceover_still`：GPU 2，当前示例关闭
- `synchformer_offset_s`：GPU 2，当前示例关闭
- `audio_change_alignment`：CPU
- `timed_speaker_accuracy`：请求视觉评委，GPU 0
- 音频/音视频 checklist：音频评委 GPU 1；具体问题若被标为视觉 modality，则走视觉评委 GPU 0

当前 D16 示例只启用 `audio_change_alignment`，因此只使用 CPU，不加载 Whisper、SyncNet 或 Synchformer。

## D17：`17_failure_anomaly_control`

- `vlm_anomaly_rate`：视觉评委 GPU 0
- `vlm_severe_fraction`：视觉评委 GPU 0
- `vmbench_ois`、`vmbench_tcs`、`vmbench_mss`：外部 GPU 3
- `skeleton_blc_cv`：外部 GPU 3
- `face_duplicate_rate`：GPU 2
- `identity_drift_rate`：GPU 2
- `flow_jerk_rate`：CPU
- `firm_world_consistency`：GPU 2，可能由 `extras()` 额外运行
- checklist：视觉评委 GPU 0

因此 D17 可能同时占用 GPU 0、GPU 2 和 GPU 3。当前示例启用了 VLM 异常检测和 skeleton，分别对应 GPU 0 和 GPU 3；额外 FIRM 诊断可能占用 GPU 2。

## D18：`18_text_subtitle`

- PP-OCRv5 OCR：外部 GPU 3
- OCR 后处理：CPU
- 以下五个指标共享同一次 OCR 提取，因此共用外部 GPU 3：

  - `ocr_cer`
  - `ocr_subtitle_alignment`
  - `ocr_readability`
  - `ocr_text_stability`
  - `ocr_unexpected_text_rate`

- OCR checklist：通常走视觉评委 GPU 0

OCR 使用 `.venv-ocr/bin/python` 启动，并通过 `VGEN_EXTERNAL_GPU=3` 绑定到物理 GPU 3。

## checklist 和 `check` 阶段

- `vision` checklist：视觉评委 GPU 0
- `audio` checklist：音频评委 GPU 1
- `audio_visual` checklist：音频评委 GPU 1
- checklist 生成阶段：视觉评委 GPU 0
- `check` 阶段：只检查路径和服务，不加载模型，不占用模型推理 GPU

音频评委必须使用：

```bash
GPU=1 PORT=8012 bash scripts/serve_audio_judge.sh
```

否则脚本可能读取 `configs/judge_servers.yaml` 中默认的 GPU 3，从而与 VMBench、GroundingDINO、骨架检测和 OCR 冲突。

---

**User**

在什么配置文件中可以修改这些模型放在什么卡上？

---

**Cursor**

当前仓库没有一个统一的“所有模型 GPU 分配”配置文件，而是分为三处控制。

## 1. 视觉评委和音频评委

修改：

```text
tools/vgen_eval/configs/judge_servers.yaml
```

对应字段：

```yaml
vision:
  gpu: "0"

audio:
  gpu: "1"
```

当前文件里的 `audio.gpu` 默认仍是 `"3"`，如果希望音频评委使用物理 GPU 1，应改成：

```yaml
audio:
  gpu: "1"
```

视觉评委使用：

```yaml
vision:
  gpu: "0"
```

这两个配置会被以下脚本读取：

```text
tools/vgen_eval/scripts/serve_judge.sh
tools/vgen_eval/scripts/serve_audio_judge.sh
```

也可以通过环境变量临时覆盖 YAML，不修改配置文件：

```bash
GPU=0 PORT=8011 bash scripts/serve_judge.sh
GPU=1 PORT=8012 bash scripts/serve_audio_judge.sh
```

脚本中的 `GPU` 环境变量优先级高于 `judge_servers.yaml` 中的 `gpu` 字段。

如果使用多卡张量并行，可以在 YAML 中写：

```yaml
vision:
  gpu: "0,1"
  tensor_parallel_size: 2
```

但按照当前分配方案，视觉评委和音频评委各使用一张卡即可。

## 2. 主评测进程中的模型

主评测进程的 GPU 不是由 `task_d13_example.yaml`、`task_d14_example.yaml` 等任务配置控制的，而是由启动命令中的：

```bash
CUDA_VISIBLE_DEVICES=2
```

控制。

推荐启动方式：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
.venv/bin/python run.py --task-config /path/to/task.yaml
```

主进程中的这些模型都会使用当前进程可见的 GPU：

- CSD
- FIRM
- ArcFace / InsightFace
- DINO
- LPIPS
- Whisper
- ECAPA
- emotion2vec
- CLAP
- PANNs
- SyncNet
- Synchformer

由于进程只看到物理 GPU 2，所以代码中的：

```python
cuda
cuda:0
device=0
```

实际都指向物理 GPU 2。

也就是说，如果要把主评测模型整体换到物理 GPU 4，修改启动命令即可：

```bash
CUDA_VISIBLE_DEVICES=4 \
VGEN_EXTERNAL_GPU=3 \
.venv/bin/python run.py --task-config /path/to/task.yaml
```

任务 YAML 只控制哪些子项启用，不控制这些本地模型放在哪张 GPU。

## 3. 外部子进程模型

外部进程的 GPU 由启动命令中的：

```bash
VGEN_EXTERNAL_GPU=3
```

控制。

相关实现位于：

```text
tools/vgen_eval/vgen_eval/components/external.py
```

该变量会传递给外部子进程的 `CUDA_VISIBLE_DEVICES`，因此以下组件使用物理 GPU 3：

- VMBench
- GroundingDINO
- skeleton coherence
- PP-OCRv5 OCR

如果要把外部模型改到物理 GPU 5：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=5 \
.venv/bin/python run.py --task-config /path/to/task.yaml
```

外部进程内部使用的 `cuda:0` 此时对应物理 GPU 5。

## 4. 模型路径配置不是 GPU 配置

以下文件主要控制模型权重和环境路径，不控制 GPU：

```text
tools/vgen_eval/vgen_eval/paths.py
```

例如：

- `VGEN_MODEL_ROOT`：本地模型根目录
- `VGEN_WHISPER`：Whisper 权重路径
- `VGEN_ECAPA`：ECAPA 权重路径
- `VGEN_CLAP`：CLAP 权重路径
- `VGEN_DINO`：DINO 权重路径
- `VGEN_FIRM`：FIRM 权重路径
- `VGEN_VMBENCH_PYTHON`：VMBench Python 环境
- `VGEN_OCR_PYTHON`：OCR Python 环境

这些变量只改变“从哪里加载模型”，不会改变模型运行在哪张卡上。

## 当前推荐的修改位置

如果保持现在的四卡分配，建议设置：

```text
tools/vgen_eval/configs/judge_servers.yaml
  vision.gpu = "0"
  audio.gpu  = "1"
```

启动主评测时设置：

```bash
CUDA_VISIBLE_DEVICES=2
VGEN_EXTERNAL_GPU=3
```

最终对应关系是：

```text
judge_servers.yaml 的 vision.gpu → 视觉评委 GPU 0
judge_servers.yaml 的 audio.gpu  → 音频评委 GPU 1
启动命令的 CUDA_VISIBLE_DEVICES → 主评测本地模型 GPU 2
启动命令的 VGEN_EXTERNAL_GPU   → 外部模型 GPU 3
```

`check` 阶段只检查路径和服务状态，不加载这些模型。

---

**User**

目前1-5分是如何给出的？如何评价是给1分还是3分还是5分呢？

---

**Cursor**

目前的 1–5 分是一个**规则映射系统**，不是视觉评委或音频评委直接凭感觉输出最终分数。评测流程是：

1. 评委回答 checklist 问题；
2. 数值模型计算原始指标；
3. 原始指标按照阈值映射为 1–5 分；
4. 同一个子项的多个组件按权重合并；
5. 所有适用子项再求平均，得到维度分数。

主要规则都在：

```text
tools/vgen_eval/configs/dims_13_18.yaml
```

其中当前阈值被明确标记为临时阈值，后续应使用人工标注数据校准。

## 1. Checklist 如何得到 1–5 分

视觉评委和音频评委通常只回答：

- `yes` / `no`
- 或多选题中的某个选项

它们不会直接回答“这个视频是 3 分”。

系统把每个问题转换为：

```text
答对 = 1
答错 = 0
没有有效答案 = 不计入分母
```

然后计算加权通过率：

```text
通过率 = 答对问题的权重之和 / 已回答问题的权重之和
```

当前映射是：

- 通过率 `>= 1.00`：5 分
- 通过率 `>= 0.80` 且 `< 1.00`：4 分
- 通过率 `>= 0.60` 且 `< 0.80`：3 分
- 通过率 `>= 0.30` 且 `< 0.60`：2 分
- 通过率 `< 0.30`：1 分

例如：

```text
10 个问题全部答对       → 5 分
8 个问题答对             → 4 分
6～7 个问题答对          → 3 分
3～5 个问题答对          → 2 分
0～2 个问题答对          → 1 分
```

实际计算还会考虑问题权重。

### 核心问题失败的限制

Checklist 中标记为 `core: true` 的核心问题，只要有一个答错，该子项最高只能得到 2 分。

因此，即使普通问题大部分答对，只要核心要求失败，结果仍可能是：

```text
子项分数 <= 2
```

### Gate 失败

每个视频还可能有可评估性 gate，例如主体是否出现、视频是否能正常观看等。

如果 gate 失败：

```text
该视频相关维度的适用子项统一记为 1 分
```

D15 和 D16 还有音频 gate。如果没有音轨或音频基本静音，适用的音频相关子项会被记为 1 分。

## 2. 数值模型如何得到 1–5 分

数值模型先产生原始指标，然后根据指标方向和阈值映射。

指标有两种方向：

- `higher`：越高越好，例如相似度、存在率、同步准确率
- `lower`：越低越好，例如 CER、LPIPS、漂移率、异常率

### 示例一：相似度越高越好

`csd_ref_similarity` 当前配置是：

```text
>= 0.80       → 5 分
>= 0.65       → 4 分
>= 0.50       → 3 分
>= 0.35       → 2 分
< 0.35        → 1 分
```

所以：

```text
0.82 → 5 分
0.56 → 3 分
0.20 → 1 分
```

### 示例二：LPIPS 越低越好

`endpoint_lpips` 当前配置是：

```text
<= 0.08       → 5 分
<= 0.15       → 4 分
<= 0.25       → 3 分
<= 0.40       → 2 分
> 0.40        → 1 分
```

所以：

```text
0.06 → 5 分
0.20 → 3 分
0.55 → 1 分
```

### 示例三：ASR 错误率越低越好

`asr_cer` 当前配置是：

```text
<= 0.05       → 5 分
<= 0.15       → 4 分
<= 0.30       → 3 分
<= 0.50       → 2 分
> 0.50        → 1 分
```

所以：

```text
CER = 0.03 → 5 分
CER = 0.22 → 3 分
CER = 0.70 → 1 分
```

### 示例四：异常率越低越好

D17 的异常类指标使用统一异常率规则：

```text
异常率 <= 0.00       → 5 分
异常率 <= 0.05       → 4 分
异常率 <= 0.15       → 3 分
异常率 <= 0.35       → 2 分
异常率 > 0.35        → 1 分
```

因此异常率为 `0.10` 时是 3 分，异常率为 `0.40` 时是 1 分。

## 3. FIRM 的评分方式不同

`firm_world_consistency` 是例外。

FIRM 会直接让模型输出一个 `1–5` 的整数，并要求模型给出理由。它不是先计算连续指标再查阈值。

因此：

- FIRM：模型直接输出 1、2、3、4 或 5
- 视觉评委 checklist：回答问题后由通过率映射
- 音频评委 checklist：回答问题后由通过率映射
- VLM 异常检测：先检测异常事件，再计算异常率并映射

## 4. 多个组件如何合并成一个子项分数

以 D14 的 `subject_replacement` 为例：

```yaml
components:
  checklist: 0.6
  arcface_identity_keep: 0.4
```

假设：

```text
checklist                 → 5 分
arcface_identity_keep     → 3 分
```

子项原始分数为：

```text
5 × 0.6 + 3 × 0.4 = 4.2
```

当前配置不会把这个子项强制取整，保留浮点数。

如果某个组件关闭、不适用或不可用，系统会移除该组件，并对剩余组件重新归一化权重。例如只剩 checklist：

```text
checklist = 5 分
子项最终分数 = 5 分
```

如果 checklist 和所有其他组件都不可用，该子项不会伪造一个分数，而是标记为没有可用组件。

## 5. 一个维度的最终分数如何得到

维度分数是所有适用子项原始分数的平均值。

例如一个维度有三个适用子项：

```text
子项 A = 4.2
子项 B = 3.0
子项 C = 5.0
```

维度分数为：

```text
(4.2 + 3.0 + 5.0) / 3 = 4.067
```

最终报告通常保留三位小数。

D17 还有一个额外的 `strict_pass`：

```text
所有适用子项都 >= 4 分
并且没有核心 checklist 失败
```

只有同时满足这两个条件，D17 才算严格通过。`strict_pass` 是额外的通过标志，不会替代数值分数。

## 目前 1、3、5 分的实际含义

当前系统中可以概括为：

- **1 分**：核心要求基本未满足、视频不可评估、音频缺失，或指标明显低于最低阈值
- **3 分**：达到中间阈值，功能部分实现，但仍有明显问题
- **5 分**：Checklist 全部通过，或指标达到最高阈值，且没有核心失败

需要注意，当前代码还没有一个独立的自然语言等级定义，例如“1 分=差、3 分=一般、5 分=优秀”的人工评分手册。现在主要依靠 `dims_13_18.yaml` 中的数值阈值和 checklist 通过率。文件顶部已经说明这些阈值是 **PROVISIONAL**，也就是尚未经过人工标注集校准的临时配置。

---

**User**

你把今天目前到目前对搭建视频评估工作流写一个简短的日报，
格式类似如下，不要参考内容：
23.进行DSH company-codex-like + gpt-5.6-luna · xhigh · k=2的测试，成功率为3.5%（09/28）
24.本地部署qwen38_27b，将被测模型换为qwen38_27b，agent换为mini-swe-agent 2.4.6,通过冒烟测试（09/28）

---

**Cursor**

25.梳理视频评估工作流 D13-D18 各维度子项的模型调用链路与 GPU 分配，明确视觉评委、音频评委、主评测进程和外部评测进程的设备映射（09/29）

26.核对视频评估工作流中的 GPU 配置入口，确认评委服务在 `judge_servers.yaml` 中配置，主评测和外部模型分别通过 `CUDA_VISIBLE_DEVICES`、`VGEN_EXTERNAL_GPU` 指定运行卡（09/29）

27.梳理视频评估工作流的 1-5 分评分机制，明确 checklist 通过率、模型指标阈值、组件权重、核心问题封顶和音视频 gate 对最终分数的影响（09/29）

---

**User**

你这只是最基础的，你需要把今天所有的工作内容都写出来。

---

**Cursor**

下面是今天完整的工作日报版本，不再只保留三条概括性描述。

## 2026 年 9 月 29 日工作日报

### 一、梳理 D13-D18 视频评估整体流程

围绕视频评估工作流中的 D13-D18 六个维度，逐项核对了维度配置、子项定义、模型组件、评委调用、数值指标、门控逻辑和最终分数计算方式，明确了从输入视频到维度得分的完整调用链路。

核对范围包括：

- `tools/vgen_eval/configs/dims_13_18.yaml`
- D13-D18 各维度的任务示例配置
- 维度基类和具体维度实现
- 视觉评委和音频评委调用逻辑
- FIRM 直接评分逻辑
- 外部模型子进程启动逻辑
- 评估结果汇总和 1-5 分映射逻辑

确认评估过程不是单一模型直接给分，而是由以下几类结果共同组成：

1. 输入视频和任务描述经过任务级检查。
2. 视觉或音频评委生成 checklist。
3. checklist 通过率转换为 1-5 分。
4. 本地模型或外部模型计算数值指标。
5. 数值指标根据 `metric_thresholds` 转换为 1-5 分。
6. 同一子项的多个组件按照 YAML 中的权重加权。
7. 不可用或不适用的组件从分母中剔除并重新归一化。
8. 所有适用子项的得分平均得到维度分数。
9. 如果 gate 失败，则相关子项或维度按照规则记为 1 分。

---

### 二、明确 D13-D18 各维度的模型组成和运行设备

按照当前约定，四张物理 GPU 的用途已经明确：

- 物理 GPU 0：视觉评委 Qwen3-VL
- 物理 GPU 1：音频评委 Qwen2.5-Omni
- 物理 GPU 2：主评测进程中的本地模型
- 物理 GPU 3：外部子进程，例如 VMBench、GroundingDINO、skeleton 和 OCR

逐个维度确认如下。

#### D13：风格与视觉控制

- CSD：主评测进程，物理 GPU 2。
- FIRM：主评测进程，物理 GPU 2；FIRM 直接输出 1-5 分整数。
- palette：CPU。
- 视觉 checklist：调用 Qwen3-VL，物理 GPU 0。

#### D14：编辑与可控生成

- ArcFace：主评测进程，物理 GPU 2。
- DINO：主评测进程，物理 GPU 2。
- LPIPS：主评测进程，物理 GPU 2。
- PSNR：CPU。
- GroundingDINO：外部子进程，物理 GPU 3。
- 视觉 checklist：调用 Qwen3-VL，物理 GPU 0。

同时通过实际运行日志确认 LPIPS 能够正常加载 Alex 权重并完成评估。

#### D15：音频生成能力

- Whisper：主评测进程，物理 GPU 2。
- ECAPA：主评测进程，物理 GPU 2。
- emotion2vec：主评测进程，物理 GPU 2。
- CLAP：主评测进程，物理 GPU 2。
- PANNs：主评测进程，物理 GPU 2。
- Silero VAD：CPU。
- DNSMOS：默认 CPU。
- AudioBox：实际设备依赖第三方库的默认行为，目前仅凭仓库代码无法完全确认。
- 音频 checklist：调用 Qwen2.5-Omni，物理 GPU 1。

#### D16：音视频同步与时间对齐

- Whisper：主评测进程，物理 GPU 2。
- SyncNet：主评测进程，物理 GPU 2。
- Synchformer：主评测进程，物理 GPU 2。
- `audio_change_alignment`：CPU。
- timed speaker 相关请求：发送到视觉评委 Qwen3-VL，物理 GPU 0。
- 音频类 checklist：通常发送到音频评委 Qwen2.5-Omni，物理 GPU 1。

#### D17：人物动作和运动质量

- VLM anomaly：调用视觉评委 Qwen3-VL，物理 GPU 0。
- VMBench：外部子进程，物理 GPU 3。
- skeleton：外部子进程，物理 GPU 3。
- InsightFace：主评测进程，物理 GPU 2。
- FIRM：主评测进程，物理 GPU 2。
- 光流相关计算：CPU。
- 额外计算 `strict_pass`，要求所有适用子项都不低于 4 分，并且不能有核心 checklist 失败。

#### D18：文字和 OCR 能力

- PP-OCRv5 检测和识别：外部子进程，物理 GPU 3。
- OCR 结果后处理：CPU。
- OCR checklist：通常调用视觉评委 Qwen3-VL，物理 GPU 0。

---

### 三、核对四张 GPU 的环境变量映射规则

确认了主进程和外部子进程之间的设备编号不能混用。

当前推荐启动方式为：

```bash
GPU=0 PORT=8011 bash scripts/serve_judge.sh
GPU=1 PORT=8012 bash scripts/serve_audio_judge.sh

CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
.venv/bin/python run.py --task-config /path/to/task.yaml
```

设备映射规则已经确认：

- 主进程设置 `CUDA_VISIBLE_DEVICES=2` 后：
  - `cuda`
  - `cuda:0`
  - `device=0`
  - `ctx_id=0`

  实际都指向物理 GPU 2。

- 外部进程继承 `VGEN_EXTERNAL_GPU=3` 后：
  - 外部进程的 `CUDA_VISIBLE_DEVICES` 为 3。
  - 外部进程内部的 `cuda:0` 实际指向物理 GPU 3。

因此，主进程内部使用 `cuda:0` 并不会占用物理 GPU 0，而是占用被环境变量重新映射后的物理 GPU 2。

同时确认：

- `check` 阶段只检查输入路径、任务配置和评委服务状态。
- `check` 阶段不会加载主评测模型。
- 外部模型的 GPU 设置由 `VGEN_EXTERNAL_GPU` 控制。
- 评委服务的 GPU 设置由启动脚本中的 `GPU` 环境变量控制。

---

### 四、核对评委服务启动脚本和配置入口

检查了以下文件：

- `tools/vgen_eval/configs/judge_servers.yaml`
- `tools/vgen_eval/scripts/serve_judge.sh`
- `tools/vgen_eval/scripts/serve_audio_judge.sh`
- `tools/vgen_eval/scripts/resolve_judge_config.py`

确认服务配置流程如下：

1. 启动脚本调用 `resolve_judge_config.py` 读取 YAML。
2. YAML 中定义模型路径、服务端口、GPU、显存利用率和并行参数。
3. 同名环境变量优先级高于 YAML 配置。
4. 脚本最终导出 `CUDA_VISIBLE_DEVICES="${GPU}"`。
5. 服务分别通过 HTTP API 提供视觉和音频评委能力。

当前配置确认结果：

- `vision.gpu` 为 `"0"`，与当前设备规划一致。
- `audio.gpu` 在 YAML 中仍然是 `"3"`。
- 如果直接按推荐的四卡分工使用，需要把音频评委改成物理 GPU 1，或者启动时使用 `GPU=1` 覆盖 YAML。
- 当前尚未直接修改 `judge_servers.yaml`。
- 已经通过环境变量覆盖方式确认音频评委可以按 GPU 1 的规划启动。

---

### 五、启动并检查视觉、音频评委服务

确认两个评委服务均可用：

- 视觉评委：
  - 模型：Qwen3-VL-32B
  - 地址：`http://127.0.0.1:8011/v1`
  - 物理 GPU：GPU 0

- 音频评委：
  - 模型：Qwen2.5-Omni-7B
  - 地址：`http://127.0.0.1:8012/v1`
  - 物理 GPU：GPU 1

从服务日志中确认：

- `/v1/models` 请求正常返回。
- `/v1/chat/completions` 请求正常返回。
- 视觉评委已实际处理 checklist 请求。
- 音频评委已实际处理音频评估请求。
- 两个服务的推理进程处于正常运行状态。
- GPU 0 上运行视觉评委模型，GPU 1 上运行音频评委模型，没有把两个评委服务混到同一张卡上。

---

### 六、实际运行 D14 评估任务

使用 `task_d14_example.yaml` 对多个生成结果进行了实际评测。

#### `online_t2va_d14`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：5.0、4.0。
- D14 最终得分：4.5。
- 有效样本数：2/2。
- 非目标区域保持子项平均分：4.5。

#### `online_f2va_d14`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：2.45、4.75。
- D14 最终得分：3.6。
- 有效样本数：2/2。
- 局部修改准确性：1.0。
- 非目标区域保持：3.0。
- 主体替换一致性：1.0。
- 视频延长：4.5。
- 首尾帧控制：4.75。

该次运行还验证了 LPIPS 模型能够正常加载：

- 使用 Alex 主干。
- 成功读取 LPIPS Alex 权重。
- 完成感知相似度计算。
- torchvision 给出了 `pretrained` 参数弃用警告，但不影响本次评测。

#### `online_r2va_d14`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：5.0、4.0。
- D14 最终得分：4.5。
- 有效样本数：2/2。
- 局部修改准确性：5.0。
- 非目标区域保持：4.0。

D14 的多组运行已经验证了：

- 任务配置能够正确读取。
- 视频路径检查正常。
- 视觉 checklist 服务调用正常。
- 数值指标组件能够被按子项启用。
- 子项没有对应样本时会显示为 `-`，不会错误地参与均值。
- 最终维度分数能够按照有效子项正确汇总。

---

### 七、实际运行 D15 音频生成评估任务

使用 `task_d15_example.yaml` 对多组结果进行了实际评测。

#### `online_r2va_d15`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：4.0、5.0。
- D15 最终得分：4.5。
- 对白内容正确性：5.0。
- 环境音：3.5。
- 动作音效：5.0。
- 配乐符合度：5.0。

#### `online_f2va_d15`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：5.0、2.333。
- D15 最终得分：3.667。
- 环境音：3.0。
- 动作音效：1.0。
- 配乐符合度：5.0。

#### `online_t2va_d15`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：2.333、3.667。
- D15 最终得分：3.0。
- 环境音：1.0。
- 动作音效：3.0。
- 配乐符合度：5.0。

#### `delivery_t2va_d15`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- D15 最终得分：3.0。
- 环境音：1.0。
- 动作音效：3.0。
- 配乐符合度：5.0。

#### `delivery_f2va_d15`

- 评测样本：2 个。
- 视频有效样本：2/2。
- checklist：2/2 成功，失败数为 0。
- 单样本得分：5.0、2.333。
- D15 最终得分：3.667。
- 对白内容正确性：5.0。
- 环境音：3.0。
- 动作音效：3.0。
- 配乐符合度：5.0。

D15 的运行验证了：

- 音频评委服务可以正常参与任务。
- 音频 checklist 失败数为 0。
- 对白、环境音、动作音效和配乐等不同子项可以独立启用。
- 没有有效结果的音色、自然度和情绪子项会被剔除，不会将空值按 0 分处理。
- 音频 gate 和静音逻辑会影响可用子项及最终分数。
- 不同生成方式之间的音频质量差异能够反映到最终 D15 分数中。

---

### 八、核对当前 1-5 分评分机制

当前评分机制已经从配置和代码两方面完成核对。

#### Checklist 评分

- checklist 问题由视觉评委或音频评委回答。
- 对于 yes/no 问题，回答正确记 1，错误记 0。
- 对于 choice 问题，选择正确记 1，错误记 0。
- 无效回答、未回答或无法判断的项目不计入分母。
- 按问题权重计算 checklist 通过率。

通过率到 1-5 分的映射为：

- 通过率大于等于 1.00：5 分。
- 通过率大于等于 0.80：4 分。
- 通过率大于等于 0.60：3 分。
- 通过率大于等于 0.30：2 分。
- 通过率低于 0.30：1 分。

如果核心 checklist 项失败，相关子项最高只能得到 2 分。

#### 数值指标评分

- 每个指标在 `metric_thresholds` 中配置阈值。
- 根据指标是 `higher` 还是 `lower` 类型采用不同方向判断。
- 指标值根据阈值转换成 1-5 分。
- 数值模型、checklist 和其他组件再按照子项权重加权。

#### 缺失组件处理

- 组件不可用时不会默认按 0 分处理。
- 组件不适用时会被剔除。
- 剩余有效组件重新归一化。
- 如果整个子项没有有效组件，则该子项显示为 `-`，并且不进入维度均值。

#### Gate 处理

- gate 失败的样本记为 1 分，并纳入均值。
- 无法读取的视频不进入正常评分流程。
- D15、D16 如果没有音频或检测到静音，相关音频子项会受到 gate 规则影响。
- D17 额外输出 `strict_pass`。
- `strict_pass` 要求所有适用子项至少为 4 分，并且不能存在核心 checklist 失败。

#### 特殊评分

- FIRM 不经过普通数值指标映射，直接输出 1-5 分整数。
- 当前阈值均标记为 provisional，仍然需要人工标注数据进行 calibration，不能把当前阈值视为最终标准。

---

### 九、确认的代码和配置入口

今天重点定位并核对了以下文件：

- `tools/vgen_eval/configs/judge_servers.yaml`
  - 评委模型、端口、GPU 和并行参数配置。

- `tools/vgen_eval/scripts/serve_judge.sh`
  - 视觉评委服务启动脚本。

- `tools/vgen_eval/scripts/serve_audio_judge.sh`
  - 音频评委服务启动脚本。

- `tools/vgen_eval/scripts/resolve_judge_config.py`
  - YAML 配置和环境变量解析逻辑。

- `tools/vgen_eval/vgen_eval/components/external.py`
  - 外部子进程环境变量及 GPU 设置。

- `tools/vgen_eval/vgen_eval/paths.py`
  - 模型路径和环境路径控制，不负责 GPU 分配。

- `tools/vgen_eval/configs/dims_13_18.yaml`
  - D13-D18 维度、子项、权重、组件和阈值配置。

- `tools/vgen_eval/vgen_eval/scoring.py`
  - 指标映射、权重合并、维度汇总和最终分数逻辑。

- `tools/vgen_eval/vgen_eval/dims/base.py`
  - 维度通用评估流程和 gate 处理。

- `tools/vgen_eval/vgen_eval/judges/vision.py`
  - 视觉 checklist 和视觉评委请求逻辑。

- `tools/vgen_eval/vgen_eval/judges/audio.py`
  - 音频 checklist 和音频评委请求逻辑。

- `tools/vgen_eval/vgen_eval/judges/firm.py`
  - FIRM 直接输出整数分数的逻辑。

- D13-D18 对应的任务示例配置：
  - `task_d13_example.yaml`
  - `task_d14_example.yaml`
  - `task_d15_example.yaml`
  - D16-D18 对应示例配置

---

### 十、当前未完成和待确认事项

1. `judge_servers.yaml` 中的 `audio.gpu` 仍默认为 `"3"`，尚未直接修改为 `"1"`。
2. 目前可以通过 `GPU=1` 临时覆盖音频评委 GPU 配置。
3. AudioBox 的实际运行设备仍需通过第三方库默认配置或运行日志进一步确认。
4. `dims_13_18.yaml` 中的分数阈值仍是 provisional。
5. 当前尚未使用人工标注集完成阈值 calibration。
6. D13、D16、D17、D18 还需要继续运行更完整的正式样本，验证所有外部模型和对应子项。
7. 当前 D14、D15 的运行主要用于验证链路和配置，不能替代正式数据集上的最终评测结果。

---

### 今日工作总结

今天完成的核心工作是：把 D13-D18 从“知道有哪些指标”进一步梳理成了可执行的完整评估链路，明确了每个子项调用哪个模型、运行在哪张 GPU、如何经过 checklist 和数值指标得到 1-5 分，并通过 D14、D15 多组真实任务运行验证了评委服务、主评测进程、音频评估流程、LPIPS 组件和分数汇总逻辑均能正常工作。

当前最重要的后续工作是：

- 固化音频评委使用物理 GPU 1 的配置。
- 继续完成 D16-D18 的实际运行验证。
- 通过人工标注集校准 `dims_13_18.yaml` 中的 provisional 阈值。
- 进一步确认 AudioBox 的设备行为。
- 在正式数据集上检查各子项的有效样本覆盖率和最终分数稳定性。

---

**User**

25.梳理视频评估工作流 D13-D18 各维度子项的模型调用链路与 GPU 分配，明确视觉评委、音频评委、主评测进程和外部评测进程的设备映射（09/29）

26.核对视频评估工作流中的 GPU 配置入口，确认评委服务在 judge_servers.yaml 中配置，主评测和外部模型分别通过 CUDA_VISIBLE_DEVICES、VGEN_EXTERNAL_GPU 指定运行卡（09/29）

27.梳理视频评估工作流的 1-5 分评分机制，明确 checklist 通过率、模型指标阈值、组件权重、核心问题封顶和音视频 gate 对最终分数的影响（09/29）
还是要按照这个格式写，但是不要表现的在做之前重复的事情，

---

**Cursor**

下面内容可直接接在原来的 25-27 后面，避免重复已经完成的 GPU 分配和评分机制梳理：

28. 启动并联调视觉评委 Qwen3-VL 与音频评委 Qwen2.5-Omni 服务，验证 `8011`、`8012` 端口的模型查询和 `/v1/chat/completions` 请求均可正常返回（09/29）

29. 使用 `task_d14_example.yaml` 完成 `online_t2va`、`online_f2va`、`online_r2va` 三组 D14 实际评测，确认 2/2 视频均可处理、checklist 请求全部成功，维度得分分别为 4.5、3.6、4.5（09/29）

30. 在 D14 实际评测中验证 LPIPS 感知指标能够正常加载 Alex 权重并参与计算，同时确认局部编辑、非目标区域保持、主体替换、视频延长和首尾帧控制等子项可以按有效样本分别汇总（09/29）

31. 使用 `task_d15_example.yaml` 完成 `online_r2va`、`online_f2va`、`online_t2va`、`delivery_t2va`、`delivery_f2va` 五组 D15 音频评测，确认 2/2 视频均可处理、音频 checklist 请求全部成功，维度得分分别为 4.5、3.667、3.0、3.0、3.667（09/29）

32. 对比 D15 多组评测结果，核验对白准确性、环境音、动作音效和配乐符合度等音频子项的实际输出，确认没有有效结果的音色、自然度和情绪子项会被剔除而不是按 0 分计入（09/29）

33. 检查 D14、D15 评测日志和结果汇总，确认任务路径检查、视频有效性检查、checklist 生成、数值指标计算、单样本评分和维度均值汇总均已完整执行（09/29）

34. 核对视觉评委和音频评委的运行日志，确认两个服务均已收到真实评测请求并正常返回结果，未出现模型服务不可用、接口请求失败或评测进程异常退出（09/29）

35. 检查当前评测配置中的遗留问题，确认 `judge_servers.yaml` 的 `audio.gpu` 仍默认为 `"3"`，目前通过 `GPU=1` 环境变量覆盖使用；同时记录 AudioBox 实际运行设备仍需结合第三方库行为或运行日志进一步确认（09/29）

36. 整理 D13-D18 评测链路的代码和配置入口，完成从任务配置、评委服务、外部模型进程、数值指标组件到最终结果汇总文件的定位，为后续正式数据集批量评测和阈值 calibration 做准备（09/29）

---

**User**

再继续写一下，正在做的和未完成的，也要是以上的格式

---

**Cursor**

37. 正在补充 D16-D18 的实际样本评测，重点验证音视频同步、人物动作质量、运动一致性和 OCR 文字识别等子项是否能够按预期完成端到端调用（09/29）

38. 正在核验 D16 的 Whisper、SyncNet、Synchformer、音频变化对齐和 timed speaker 请求链路，确认音频分析、视觉评委请求与最终子项汇总之间的数据传递关系（09/29）

39. 正在核验 D17 的 VMBench、skeleton、InsightFace、FIRM 和光流组件，重点检查外部子进程结果、主进程指标和 `strict_pass` 是否能够共同写入最终评测结果（09/29）

40. 正在核验 D18 的 PP-OCRv5 外部推理、OCR 后处理和视觉 checklist 流程，检查检测结果、识别结果及文字一致性评分能否正确汇总到维度分数（09/29）

41. 待将 `judge_servers.yaml` 中的 `audio.gpu` 默认值由 `"3"` 调整为 `"1"`，使配置文件默认值与当前音频评委物理 GPU 1 的分配方案保持一致（09/29）

42. 待进一步确认 AudioBox 的实际运行设备，计划结合第三方库默认配置、进程启动参数和运行日志判断其是否进入主评测进程 GPU 2（09/29）

43. 待使用人工标注集对 `dims_13_18.yaml` 中当前 provisional 的数值阈值进行 calibration，重新核定 1-5 分映射区间和不同指标方向的判定边界（09/29）

44. 待检查人工标注集与自动评测结果在 checklist、数值指标、核心问题封顶和 gate 失败样本上的一致性，定位自动评分与人工评分之间的偏差来源（09/29）

45. 待在正式数据集上开展 D13-D18 批量评测，统计各维度、各子项的有效样本数、不可用组件数量、gate 失败数量和最终分数分布（09/29）

46. 待补充不同生成类型和不同输入条件下的评测覆盖，确认当前 D14、D15 中出现的空子项是否由任务配置未启用、输入数据缺失或组件尚未接入导致（09/29）

47. 待对 D14、D15 的多组试运行结果进行结果文件归档和横向对比，进一步检查单样本分数、子项均值、维度均值与最终报告之间是否保持一致（09/29）

48. 待完成 D16-D18 的服务、主进程和外部进程联合运行验证，确认物理 GPU 0、1、2、3 在完整评测过程中不会发生模型错卡、资源冲突或外部进程继承错误（09/29）

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/configs/task_d17_example.yaml
第17维度的评估为什么没有fl2va模式的参考图的配置？

---

**Cursor**

原因是 `task_d17_example.yaml` 当前并不是 `fl2va` 配置，而是一个没有配置完整的 `f2va` 配置。具体表现为：

- `task_name` 和 `run_name` 都是 `online_f2va_d17`。
- `input.root` 指向 `.../online_fl2va/f2va`。
- `input.mode` 设置为 `f2va`。

```8:15:tools/vgen_eval/configs/task_d17_example.yaml
task_name: online_f2va_d17
run_name: online_f2va_d17

dimension: 17_failure_anomaly_control
input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/online_fl2va/f2va
  # Select exactly one mode: t2va, f2va, l2va, fl2va, or r2va.
  mode: f2va
```

当前 `references` 块配置的是：

```22:29:tools/vgen_eval/configs/task_d17_example.yaml
  # r2va:
  references:
    image_pattern: input_{index:02d}
    video_pattern: ref_video_{index:02d}
    audio_pattern: ref_audio_{index:02d}
    image_extensions: [.png, .jpg, .jpeg, .webp]
    video_extensions: [.mp4, .mov, .webm]
    audio_extensions: [.mp3, .wav, .m4a, .flac, .aac]
```

这组 `image_pattern`、`video_pattern`、`audio_pattern` 是 **r2va 的参考素材配置**，不是 `fl2va` 的首尾帧配置。代码只有在 `mode == "r2va"` 时才会读取这些字段；因此当前配置中的这些字段对 `f2va` 和 `fl2va` 都不会起作用。

正确的 `fl2va` 配置应该使用：

```yaml
task_name: online_fl2va_d17
run_name: online_fl2va_d17

dimension: 17_failure_anomaly_control

input:
  root: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick/online_fl2va/fl2va
  mode: fl2va
  prompt_filename: prompt_final.txt
  video_filename: video.mp4
  case_ids: []

  references:
    first_frame_filename: input_01
    last_frame_filename: input_02
    image_extensions: [.png, .jpg, .jpeg, .webp]
```

`fl2va` 模式要求同时提供首帧和尾帧。加载器会分别检查这两个字段：

```226:239:tools/vgen_eval/vgen_eval/cases.py
        if mode in ("f2va", "fl2va"):
            name = refs_cfg.get("first_frame_filename")
            if not name:
                raise ValueError(f"mode {mode} requires references.first_frame_filename")
            first_frame = _pattern_path(case_dir, name, extensions=image_exts)
            if not first_frame:
                raise FileNotFoundError(f"configured first frame is missing for case {cid}: {name}")
        if mode in ("l2va", "fl2va"):
            name = refs_cfg.get("last_frame_filename")
            if not name:
                raise ValueError(f"mode {mode} requires references.last_frame_filename")
            last_frame = _pattern_path(case_dir, name, extensions=image_exts)
            if not last_frame:
                raise FileNotFoundError(f"configured last frame is missing for case {cid}: {name}")
```

所以当前文件存在两个问题：

1. 它没有真正配置 `fl2va`。
2. 即使按照当前的 `f2va` 模式运行，也缺少 `references.first_frame_filename`，正常情况下会报：

```text
mode f2va requires references.first_frame_filename
```

第 17 维度本身是支持 `fl2va` 的。参考首尾图只会附给视觉评委，用于 checklist 判断；VLM 异常时间线、VMBench、骨架、InsightFace 和光流仍然只分析生成视频，不会拿首尾参考图计算异常数值。文档也明确规定了 `fl2va` 要挂上首帧和尾帧，且条件图只用于第二次视觉评委答题。

因此，这不是 D17 设计上不支持 `fl2va`，而是 `task_d17_example.yaml` 目前被写成了一个不完整的 `f2va` 示例，应该补成上面的 `fl2va` 配置。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/docs/dim13_evaluation_table.md
这个是之前初步的方案设计，我需要你按照这个文档的格式，再新建一个目前13-18维度的评估规则和方案。

---

**Cursor**

已新建当前版本的 D13-D18 评估规则文档：

`tools/vgen_eval/docs/dims_13_18_current_evaluation_plan.md`

文档沿用了 `dim13_evaluation_table.md` 的组织方式，包含：

- 五种输入形式：`t2va`、`f2va`、`l2va`、`fl2va`、`r2va`
- 统一的任务读取、视觉评委、音频评委和 checklist 流程
- D13-D18 每个维度的二级评测项
- 每个子项的适用条件
- checklist、数值模型和组件权重
- 组件不可用时的重新归一化规则
- D15、D16 的音频 gate
- D17 的异常时间线和 `strict_pass`
- D18 的 PP-OCRv5 独立抽帧流程
- 当前 GPU 分配和外部进程设备规划
- 当前已接入模型、运行位置和待确认事项
- 当前 provisional 阈值及人工标注 calibration 要求

另外特别修正并写清了 D17 的输入配置区别：

- `f2va`、`l2va`、`fl2va` 使用 `first_frame_filename` / `last_frame_filename`。
- 只有 `r2va` 使用 `image_pattern`、`video_pattern` 和 `audio_pattern`。
- `fl2va` 必须显式配置首帧和尾帧，不能只保留 r2va 的参考素材配置。

文档已检查，没有使用不兼容的 `\(...\)` 或 `\[...\]` 公式定界符，且当前没有诊断错误。

---

**User**

我还想知道目前是如何触发数值组件的？

---

**Cursor**

目前数值组件不是“启动评测就全部运行”，而是经过 **配置开关、子项适用条件、依赖扩展、gate 判断和缓存** 五层触发。

## 1. 先由任务配置决定哪些组件允许运行

每个子项在 `dims_13_18.yaml` 中定义默认组件和权重，例如 D14：

```yaml
non_target_preservation:
  components:
    checklist: 0.4
    dino_bg_consistency: 0.3
    masked_lpips_static: 0.3
```

任务 YAML 可以通过 `evaluation.subpoints.<subpoint>.components` 覆盖默认开关：

```yaml
evaluation:
  subpoints:
    non_target_preservation:
      components:
        dino_bg_consistency: false
        masked_lpips_static: false
        checklist: true
```

含义是：

- 未写出的组件默认启用。
- 写成 `false` 的数值组件不运行。
- 关闭后，该组件的权重不会保留在分母中。
- 剩余已运行组件会重新归一化。
- `checklist` 不能关闭。

任务启动时，`run.py` 会先校验：

- 子项名称是否合法。
- 组件名称是否属于该子项。
- 开关是否为布尔值。
- 是否错误关闭 checklist。

对应入口是 `run.py` 中的 `_validate_task_evaluation()`。

---

## 2. 再由 `applies` 判断子项是否适用

每个子项可以在维度配置中声明适用条件。例如：

```yaml
subject_replacement:
  applies: facts.has_subject_replacement
```

实际执行时，系统会读取第一次评委生成的 `facts`，判断这个子项是否适用：

```python
if not applies(sp_cfg.get("applies"), ctx.facts, ctx.case):
    results[sp] = {
        "applicable": False,
        "status": "not_applicable",
        "score": None,
    }
    continue
```

因此：

- D14 没有编辑目标时，不触发 `local_edit_accuracy`。
- D14 没有主体替换时，不触发 `subject_replacement`。
- D15 没有对白时，不触发 `voice_naturalness`。
- D15 没有环境音要求时，不触发 `ambient_sound`。
- D16 没有多人说话人事实时，不触发 `multi_speaker_match`。
- D18 没有目标文字时，不触发 `text_accuracy`。
- D18 的 `no_unrequested_text` 没有 `applies`，因此默认每条都评。

这里的 `facts` 不是人工在任务 YAML 中填写的，而是 checklist 阶段由视觉评委从 prompt 中抽取。

---

## 3. 通过 gate 后，才真正进入数值组件

每个 case 在 `DimensionEvaluator.evaluate()` 中先执行：

1. 加载或生成 checklist。
2. 调用视觉/音频评委回答 gate 和 checklist。
3. 判断普通 gate 是否通过。
4. 对 D15、D16 判断音频 gate。
5. 只有 gate 通过后才调用数值组件。

核心逻辑是：

```python
ctx.active_components = {
    name for name in sp_cfg["components"]
    if component_overrides.get(name, True) is True
}

comps = {} if (audio_failed or not gate["passed"]) else dict(
    self.components(ctx, sp)
)
```

所以：

- 普通 checklist gate 失败：数值组件不运行。
- D15/D16 音频 gate 失败：数值组件不运行，适用子项最后按 1 分计入。
- gate 通过：才进入当前子项的 `components()` 方法。

需要注意，checklist 本身不是这里的数值组件。它是在数值组件流程之后单独加入的：

```python
comps["checklist"] = checklist_component(
    ctx.checklist,
    answers,
    sp,
    cfg["scoring"],
)
```

---

## 4. `active_components` 决定单个组件是否真正执行

每个维度的 `components(ctx, sp)` 会根据子项名称调用对应模型或算法。

例如 D18：

```python
if sp == "text_accuracy":
    return {
        "ocr_cer": ctx.comp(
            "ocr_cer",
            lambda: T.ocr_cer(ocr, expected),
        )
    }
```

但 `ctx.comp()` 会先检查当前组件是否在 `active_components` 中：

```python
def comp(self, name, fn):
    if (
        self.active_components is not None
        and name not in self.active_components
    ):
        return {
            "status": "disabled",
            "reason": "disabled by task configuration",
        }
    return run_cached(...)
```

因此，一个数值组件只有同时满足以下条件才会执行：

- 子项适用。
- 普通 gate 通过。
- 音频 gate 通过，或者该维度没有音频 gate。
- 任务配置没有将它关闭。
- 该组件在当前子项中被实现并被调用。
- 组件依赖存在且输入有效。

---

## 5. 共享模型会通过依赖扩展被触发

有些组件不是单独启动，而是多个输出共享一次模型推理。

### D15：Whisper 和 VAD

D15 中多个组件依赖 Whisper，例如：

- `asr_cer`
- `ecapa_same_speaker`
- `ecapa_reference`
- `emotion2vec_match`

D15 会根据当前启用的输出组件，把共享依赖加入 `active_components`：

```python
if (
    ctx.active_components is not None
    and _ASR_DEPENDENTS & ctx.active_components
):
    ctx.active_components.add("asr")
```

因此：

- 只开启 `asr_cer`，会触发共享的 `asr`。
- 关闭所有依赖 ASR 的组件，则不会启动 Whisper。
- 禁止人声检测相关组件启用时，会触发 `vad`。
- VAD 也用于后续 DNSMOS 的语音段切分。

### D16：SyncNet 轨迹

D16 中以下组件依赖共享的 SyncNet 轨迹：

- `syncnet_conf`
- `syncnet_voiceover_still`

只要其中任意一个启用，D16 会额外加入：

```text
syncnet_tracks
```

然后模型轨迹只计算一次，两个输出复用结果。

### D17：异常时间线、VMBench 和 skeleton

D17 有类似依赖扩展：

- 启用 `vlm_anomaly_rate` 或 `vlm_severe_fraction`：
  - 触发 `vlm_anomaly_timeline`。
- 启用任意 `vmbench_ois`、`vmbench_tcs` 或 `vmbench_mss`：
  - 触发共享的 `vmbench`。
- 启用 `skeleton_blc_cv`：
  - 触发共享的 `skeleton`。

所以 D17 的 VMBench 不是每个子项单独完整跑一遍，而是先运行一次共享 VMBench，再提取 OIS、TCS 或 MSS 对应结果。

### D18：OCR

D18 中这些组件共享一次 OCR 提取：

- `ocr_cer`
- `ocr_subtitle_alignment`
- `ocr_readability`
- `ocr_text_stability`
- `ocr_unexpected_text_rate`

只要当前子项中有任意一个 OCR 输出被启用，就会触发：

```text
ocr
```

先用 PP-OCRv5 对视频抽帧做一次统一提取，再由不同的后处理函数计算具体指标。

---

## 6. `ctx.comp()` 负责缓存和实际执行

组件真正执行的入口是：

```python
return run_cached(
    os.path.join(self.results_dir, "components"),
    name,
    fn,
    force=self.force,
)
```

每个组件会写到当前 case 的：

```text
<results_dir>/components/<component_name>.json
```

运行规则：

- 文件存在，且状态不是 `error`：直接读取缓存。
- 文件不存在：执行组件。
- 上次状态是 `error`：下一次会重试。
- 使用 `--force`：忽略已有缓存，重新计算。

因此，第二次重复执行同一个任务时，通常不会重新加载或重新运行已经成功完成的数值组件。

---

## 7. 以 D14 为例

假设 D14 的 facts 是：

```json
{
  "edit_targets": ["the red car"],
  "has_subject_replacement": false,
  "add_objects": [],
  "remove_objects": [],
  "is_continuation": false,
  "has_static_camera": true
}
```

则适用子项大致为：

- `local_edit_accuracy`：运行 checklist。
- `non_target_preservation`：
  - checklist
  - DINO
  - 静止镜头 LPIPS
  - GroundingDINO 作为编辑区域依赖
- `subject_replacement`：不适用。
- `add_remove_object`：不适用。
- `video_extension`：不适用。
- `first_last_frame`：根据输入模式决定是否适用。

如果任务 YAML 又关闭了 DINO：

```yaml
non_target_preservation:
  components:
    dino_bg_consistency: false
```

则实际只运行：

- checklist
- GroundingDINO 相关区域提取
- LPIPS

最终非目标保持子项的权重会从：

```text
0.4 + 0.3 + 0.3
```

变成有效组件：

```text
0.4 + 0.3
```

然后重新归一化，而不是把 DINO 当作 0 分。

---

## 8. 以 D15 为例

如果 prompt 中有对白、环境音和动作音效，但没有情绪描述：

会触发：

- Whisper：对白识别和时间定位。
- DNSMOS：声音自然度。
- AudioBox：音质。
- ECAPA：如果有重复说话人或 voice 参考。
- CLAP：环境音。
- CLAP：动作音效。
- 不触发 emotion2vec，或者该情绪组件被判定为不适用。
- 可能触发 VAD，具体取决于当前启用组件和语音段处理需求。

如果视频没有音轨：

1. D15 的音频 gate 失败。
2. 数值音频组件不再执行。
3. 所有适用音频子项被改为 1 分。
4. 这些 1 分仍然进入 D15 维度均值。

---

## 9. 以 D17 为例

默认任务配置中，D17 的 VLM 异常时间线和 skeleton 可以被启用，而 VMBench、InsightFace、光流可以通过任务 YAML 关闭。

例如当前示例配置中：

```yaml
distortion_rate:
  components:
    vlm_anomaly_rate: true
    vmbench_ois: false
    skeleton_blc_cv: true
    checklist: true
```

实际过程是：

- `vlm_anomaly_rate: true`
  - 触发 VLM anomaly timeline。
  - 根据异常事件计算 1 秒窗口异常比例。
- `vmbench_ois: false`
  - 不触发 VMBench OIS。
- `skeleton_blc_cv: true`
  - 触发 skeleton。
- `checklist: true`
  - 使用视觉评委 checklist 分数。

如果 D17 所有依赖数值组件都关闭，只留下 checklist，D17 不会因为 `extras()` 中存在 FIRM 或 skeleton 诊断逻辑而偷偷启动这些模型。代码专门检查了是否有启用的 diagnostic component，避免 checklist-only 任务隐式运行重模型。

---

## 10. 最终结果里如何体现触发情况

每个 case 的 `result.json` 会记录：

- 每个子项是否适用。
- 每个组件的状态。
- 组件最终分数和权重。
- 缺失组件。
- 被任务配置关闭的组件。
- checklist 是否核心失败。
- gate 是否失败。
- 维度最终分数。

典型状态包括：

```text
ok
disabled
not_applicable
missing_input
error
```

其中：

- `ok`：组件实际成功运行并参与评分。
- `disabled`：被任务 YAML 显式关闭。
- `not_applicable`：根据 facts 或输入形式不适用。
- `missing_input`：缺少音轨、参考图或其他必要输入。
- `error`：组件执行异常，当前结果不会作为有效数值分参与加权。

## 一句话总结

当前数值组件的触发链路是：

```text
任务配置开关
→ facts 判断子项是否适用
→ checklist gate
→ 音频 gate（D15/D16）
→ active_components 过滤
→ 共享依赖扩展
→ ctx.comp()
→ 成功缓存读取或实际模型运行
→ 组件阈值映射
→ 子项加权
→ 维度平均
```

其中 `check` 阶段只检查路径和服务，不触发数值模型；`checklist` 阶段只生成 facts 和题目；真正的数值组件是在 `evaluate` 阶段，并且只有满足上述条件后才会运行。

---

**User**

目前第二步视觉评委出题是依据什么，他的提示词是什么？

---

**Cursor**

目前第二步“视觉评委出题”实际上是 **checklist 阶段的第一次 Qwen3-VL 调用**。它不是看视频后出题，而是只根据当前 case 的原始需求和维度规则，预先生成事实、门槛题和评分问题。

## 一、第二步出题依据什么

出题时主要依据四部分信息：

### 1. 当前维度

从任务配置的：

```yaml
dimension: 17_failure_anomaly_control
```

确定当前是 D13、D14、D15、D16、D17 还是 D18。

随后读取：

```text
tools/vgen_eval/configs/dims_13_18.yaml
```

得到该维度的：

- 子项名称。
- 子项中文名称。
- `focus` 评测重点。
- `applies` 适用条件。
- 组件名称。
- checklist 和数值组件权重。

例如 D17 的子项 focus 包括：

- 人体畸变率。
- 主体消失率。
- 主体复制率。
- 属性漂移率。
- 穿模问题。
- 镜头异常率。
- 崩坏持续时间。

这些内容会作为出题范围传给 Qwen3-VL，而不是让模型自由发挥。

### 2. 原始用户需求

出题使用：

```text
intent_en.txt
```

或者任务配置指定的：

```yaml
prompt_filename: prompt_final.txt
```

在 checklist 生成流程里，代码使用的是：

```python
case.intent.strip()
```

并且对于 300case，会删除末尾由数据管线追加的 prompt-enhancement boilerplate：

```text
Write the entire enhanced prompt in English.
```

这部分不会作为用户真实需求参与出题。

### 3. 当前输入形式和参考素材信息

出题时会告诉模型当前 case 的输入形式和素材数量，例如：

```json
{
  "input_form": "fl2va",
  "duration_s": null,
  "has_first_frame_image": true,
  "has_last_frame_image": true,
  "num_reference_images": 0,
  "num_reference_audios": 0,
  "num_reference_videos": 0
}
```

这些信息用于让模型知道：

- 当前是否有首帧。
- 当前是否有尾帧。
- 当前是否存在 r2va 参考图。
- 当前是否存在参考音频。
- 当前是否存在参考视频。
- 当前输入属于 t2va、f2va、l2va、fl2va 还是 r2va。

需要注意，出题阶段不把生成视频传给模型，也不把音频传给模型。

### 4. 当前维度的通用出题规则

规则来自配置中的：

```yaml
common_checklist_rules:
```

并由 `run.py` 传入：

```python
generate_checklist(
    c,
    cfg["dimensions"][c.dimension],
    cfg["common_checklist_rules"],
    client,
    args.out,
)
```

因此，第二步的提示词不是只由 Python 文件中的固定字符串组成，而是：

```text
固定 system prompt
+ 当前维度子项及 focus
+ common_checklist_rules
+ D13 专属规则（如果是 D13）
+ 输入形式和参考素材信息
+ 原始用户需求
+ JSON 输出格式要求
```

---

## 二、当前实际使用的 system prompt

代码中的固定 system prompt 是：

```text
You turn a video-generation request into (1) structured facts and (2) atomic verification questions for judging the generated video. Requests may be in Chinese or English and may contain negative prompts. Only use information stated or directly implied by the request. Output only JSON.
```

中文含义是：

> 你需要把视频生成需求转换成两部分内容：  
> 1. 结构化事实；  
> 2. 用于评估生成视频的原子化验证问题。  
> 输入需求可能是中文或英文，也可能包含 negative prompt。只能使用需求中明确写出或可以直接推导出的信息。只输出 JSON。

这部分定义了模型的基本行为：

- 不能根据生成视频主观猜测需求。
- 不能凭空增加用户没有要求的目标。
- 不能把最终维度分数直接交给模型。
- 必须输出结构化 JSON。
- 必须把复杂需求拆成可以单独判断的 checklist 问题。

代码位置是 `vgen_eval/checklist.py` 中的 `SYSTEM`。

---

## 三、实际发送给模型的 user prompt 结构

实际 user prompt 大致是下面的结构：

```text
Target dimension: <dimension> (<name_zh>)

Sub-points of this dimension (use these ids in "subpoint"):
- <subpoint_id> (<name_zh>): <focus>
- <subpoint_id> (<name_zh>): <focus>
...

Rules:
<common_checklist_rules>

<dimension-specific-rules>

- modality: "vision" = answerable from frames; "audio" = needs listening only; "audio_visual" = needs both
  (e.g. lip sync, a sound coinciding with an action).
- For kind="yes_no" set expect and leave options=[] and answer_index=null.
- For kind="choice" set options (3-4) and answer_index (0-based), and expect=null.
- weight: 1.0 normal, 2.0 central requirement, 0.5 minor detail. ids: gates g1.., items q1..
- Cover every sub-point that the request gives something to check; skip sub-points the request does not touch.
- Facts: fill every field; use empty lists / false / null when the request says nothing.

Generation inputs: <input metadata JSON>

User request (original):
<<<
<original intent>
>>>

Return JSON {"facts": {...}, "gates": [...], "items": [...]}
```

其中最重要的约束是：

```text
Cover every sub-point that the request gives something to check;
skip sub-points the request does not touch.
```

这意味着模型不应该无条件为所有子项生成问题，而是根据当前需求决定哪些子项真正适用。

例如：

- prompt 没有对白，就不应为对白准确性生成有效评测事实。
- prompt 没有环境音要求，就不应把环境音质量当成用户明确要求。
- prompt 没有首尾帧条件，D14 的首尾帧控制不应适用。
- D17 的异常子项通常会保持评估，因为 D17 本身就是通用异常控制维度。

---

## 四、模型必须输出什么

输出顶层结构固定为：

```json
{
  "facts": {},
  "gates": [],
  "items": []
}
```

### 1. `facts`

`facts` 用来决定后续哪些子项和数值组件会被触发。

不同维度有不同的 facts schema。

#### D13 facts

主要包括：

```text
target_style
realistic
target_lighting
target_colors
main_subject_noun
style_spec
reference_image_roles
```

其中：

- `target_lighting` 决定是否触发光照控制。
- `target_colors` 决定是否触发色彩控制。
- `style_spec` 提供风格、媒介、渲染、纹理、时代、色板和负向风格约束。
- `reference_image_roles` 决定 r2va 参考图是风格图、内容图、端点图、混合图还是未知图。

D13 还有专门的规则，要求：

```text
Do not classify first_frame or last_frame as style references:
they are endpoint constraints.
```

也就是说，首帧和尾帧不会被自动当成风格参考图。

#### D14 facts

主要包括：

```text
edit_targets
preserved
has_subject_replacement
add_objects
remove_objects
is_continuation
static_camera
main_subject_noun
subject_is_person
```

这些字段直接控制：

- 局部修改准确性。
- 非目标区域保持。
- 主体替换一致性。
- 增删物体。
- 视频延长。
- 静止镜头 LPIPS。
- GroundingDINO 的检测对象。

#### D15 facts

主要包括：

```text
dialogues
voice_forbidden
has_repeated_speaker
dialogue_emotions
ambient
sfx
music_required
music_forbidden
music_description
reference_audio_role
```

这些字段决定：

- 是否触发 Whisper。
- 是否触发 VAD。
- 是否评估声音自然度。
- 是否评估音色一致性。
- 是否评估情绪。
- 是否评估环境音。
- 是否评估动作音效。
- 是否评估配乐。

#### D16 facts

主要包括：

```text
dialogues
speakers
multi_speaker
av_events
env_changes
realistic
```

这些字段决定：

- 是否触发口型同步。
- 是否触发环境音同步。
- 是否触发多人对白匹配。
- 是否将输入判断为写实人物，从而使用 SyncNet。

#### D17 facts

主要包括：

```text
subjects
main_subject_noun
has_humans
requested_camera_motion
```

这些字段决定：

- 是否有可供 VMBench 检测的主体名词。
- 是否有人体。
- 是否启用人体关键点和 OIS 相关数值组件。
- 用户要求的运镜是什么，从而避免把正常运镜算成异常。

#### D18 facts

主要包括：

```text
expected_texts
allowed_texts
subtitles_required
subtitle_lines
text_forbidden
```

这些字段决定：

- 是否评文字准确性。
- 是否评字幕完整性。
- 是否评可读性。
- 是否评文字时序稳定性。
- 允许哪些文本。
- 是否禁止额外文字。

---

## 五、`gates` 和 `items` 有什么区别

### `gates`

`gates` 是可评估性门槛，不是质量评分问题。

例如：

- 主体是否在视频中清晰可见？
- 视频是否包含足够的有效内容？
- 目标区域是否完全不可见？
- 音频是否存在并且可以判断？

最多生成 2 个 gate：

```json
"gates": [
  {
    "id": "g1",
    "subpoint": null,
    "question": "...",
    "kind": "yes_no",
    "expect": "yes",
    "options": [],
    "answer_index": null,
    "modality": "vision",
    "time_hint": null,
    "weight": 1.0,
    "core": true
  }
]
```

如果 gate 题已作答且答案错误，整个 case 会进入 gate-failed 流程：

- 数值组件不运行。
- 当前维度最终分数记为 1。
- 该样本仍然进入整体均值。

### `items`

`items` 是具体质量评估问题，必须绑定到一个子项：

```json
{
  "id": "q1",
  "subpoint": "distortion_rate",
  "question": "...",
  "kind": "yes_no",
  "expect": "yes",
  "options": [],
  "answer_index": null,
  "modality": "vision",
  "time_hint": "...",
  "weight": 2.0,
  "core": true
}
```

每个问题必须包含：

- `subpoint`：属于哪个二级评测项。
- `question`：实际判断问题。
- `kind`：`yes_no` 或 `choice`。
- `expect`：yes/no 题的标准答案。
- `options`：choice 题的选项。
- `answer_index`：choice 题的正确选项。
- `modality`：视觉、音频或音视频。
- `time_hint`：如有时间要求，提供时间范围。
- `weight`：普通、核心或次要问题权重。
- `core`：是否核心问题。

---

## 六、出题阶段如何决定问题的正确答案

模型在第一次出题时，同时生成标准答案。

### yes/no 问题

例如需求是：

```text
The video must not contain any subtitles.
```

模型应生成类似：

```json
{
  "kind": "yes_no",
  "expect": "no",
  "question": "Are there any subtitles visible in the generated video?"
}
```

这里的 `expect: "no"` 很重要，因为问题本身问的是“是否有字幕”，而需求要求“不能有字幕”。

### choice 问题

例如需求要求：

```text
The scene should use warm orange lighting.
```

模型可以生成：

```json
{
  "kind": "choice",
  "options": [
    "warm orange lighting",
    "cool blue lighting",
    "neutral daylight"
  ],
  "answer_index": 0
}
```

评估阶段 Qwen3-VL 只需要选择选项，程序再将选项索引与 `answer_index` 对比。

---

## 七、当前第二步并不是直接使用 D13-D18 评估表中的所有文字

需要区分两类提示词：

### A. 出题提示词

由 `checklist.py` 生成，负责：

- 从 prompt 提取 facts。
- 生成 gate。
- 生成 checklist 问题。
- 为每个问题绑定子项和标准答案。

### B. 评委答题提示词

由 `judges/vision.py` 和 `judges/audio.py` 生成，负责：

- 将生成视频抽帧或提供音频。
- 把已经生成的问题发给视觉/音频评委。
- 让评委回答 yes/no 或 choice。
- 要求输出证据和时间戳。

视觉答题使用的固定 system prompt 是：

```text
You are a strict evaluator of AI-generated videos. You get timestamped frames of a generated video, optionally the reference images given to the generator, and questions. Answer only from what is visible. If something is not visible or not clearly true, answer "no" (or the option that best matches what is actually shown). Never assume the request was followed. Evidence: <= 20 words, cite timestamps. Output only JSON.
```

所以：

- 第一次调用：只看需求，生成问题。
- 第二次调用：看成片，回答问题。
- 第一次调用的 `expect` 和 `answer_index` 是参考答案。
- 第二次调用只输出模型答案，不重新制定评分标准。

---

## 八、出题结果会被缓存

出题结果保存在：

```text
<out>/checklists/<dataset>/<case_id>.json
```

系统会根据以下内容计算 checklist cache key：

- 原始 intent。
- 当前维度。
- 当前维度的子项配置。
- checklist 版本号。

如果缓存存在，并且版本和 key 没有变化，后续评估会直接复用原有 checklist，不重新调用 Qwen3-VL。

只有以下情况会重新生成：

- 执行 `--regen-checklist`。
- checklist 版本变化。
- prompt 内容变化。
- 当前维度子项配置变化。
- 缓存不存在。
- 上次缓存未通过有效性检查。

因此，如果修改了出题规则但没有提升版本号或使用 `--regen-checklist`，旧 checklist 可能继续被使用。

---

## 九、当前流程的关键限制

目前第二步出题是“规则引导下的 LLM 结构化出题”，不是完全固定模板，也不是人工逐题配置。它有以下特点：

1. 子项和 `focus` 由 YAML 固定。
2. 具体问题文本由 Qwen3-VL 根据 prompt 生成。
3. 适用性由 `facts` 控制。
4. 标准答案也由出题模型生成。
5. 后续视觉/音频评委只负责回答已生成问题。
6. 题目结果会缓存并复用。
7. 如果出题模型误读 prompt，后续数值组件可能被错误触发或跳过。
8. 当前尚未加入人工审核后强制阻止自动重生成的完整工作流，虽然缓存 metadata 支持 `reviewed` 字段保护已审核结果。

最简化地说，当前第二步的提示词逻辑是：

```text
当前维度的子项和评测重点
+ 通用出题规则
+ 维度专属事实字段
+ 当前输入模式与参考素材信息
+ 原始生成需求
→ facts + gates + checklist items
```

而不是：

```text
视频内容
→ 视觉模型自由打分
```

也就是说，视觉评委出题阶段依据的是 **prompt 和配置规则**；生成视频只在下一次“回答 checklist”阶段才被送给视觉评委。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem13_test/delivery_r2va_d13/runs
你使用这个里面实际评估的一个案例给我讲解一下

---

**Cursor**

下面我用这个目录里实际跑过的一个案例来完整说明：

```text
work-log/work_929/dem13_test/delivery_r2va_d13/runs/
└── delivery_r2va_d13/
    └── 13_style_visual_control/
        └── cn300v2_096377fa92e90a3a7fdc321c/
```

这个案例是：

- 维度：D13 风格与视觉控制
- 输入形式：`r2va`
- Case ID：`cn300v2_096377fa92e90a3a7fdc321c`
- 最终得分：**4.8**
- gate：通过
- 输出文件：`result.json`

---

## 一、这个案例的输入是什么

这个 case 使用了一张参考图：

```text
input_01.jpg
```

从结果中的 `style_reference_policy` 可以看出，原始需求主要描述了：

- 写实真人风格。
- 电影感、柔和光照。
- 暖色调。
- 室内环境。
- 手机屏幕中的人物。
- 人物从屏幕中伸手出来。
- 屏幕出现蜘蛛网状裂纹。
- 不要对白。
- 不要字幕。
- 不要画面文字。

模型从需求中抽取出的风格信息包括：

```json
{
  "medium": ["live-action"],
  "rendering": ["photorealistic"],
  "texture": [
    "glass shatters into fine radial spiderweb cracks",
    "soft skin texture",
    "realistic fabric of hoodie and shorts"
  ],
  "palette": [
    "warm tones",
    "soft cinematic color grading"
  ],
  "lighting": [
    "cinematic soft light",
    "soft window light",
    "screen glow softly illuminating fingers",
    "soft light flare tracing crack edges"
  ],
  "mood": [
    "intimate",
    "slightly surreal"
  ],
  "realism": "photorealistic"
}
```

参考图虽然被加载并提供给评估流程，但模型判断它的角色为：

```json
{
  "asset": "input_01.jpg",
  "role": "unknown",
  "confidence": 1.0,
  "used_by_csd": false
}
```

这里很关键：这张参考图没有被识别为“纯风格参考图”，所以没有进入 CSD 风格相似度计算。

因此，虽然任务是 `r2va`，但这个案例的 CSD 参考图数量实际上是：

```json
"csd_reference_count": 0
```

也就是说，这个案例的风格准确性没有使用参考图相似度，而是只使用视觉 checklist。

---

## 二、第一步：视觉评委先从需求中出题

这个阶段没有把生成视频送给模型，只给了需求和 D13 的评测规则。

模型生成了两个 gate：

```text
g1：主体是否在视频中清晰可见？
g2：视频是否始终保持一致的写实真人风格？
```

实际回答结果是：

```json
{
  "g1": true,
  "g2": true
}
```

视觉评委给出的证据是：

- `g1`：手机屏幕中的人物从 0.25 秒到 7.75 秒都可见。
- `g2`：视频从 0.25 秒到 7.75 秒始终保持一致的 photorealistic live-action 风格。

因此：

```text
gate passed = true
```

如果 gate 失败，这个 case 的维度会直接按最低分 1 分处理，数值组件也不会继续计算。

---

## 三、第二步：视觉评委回答 checklist

这个案例生成了 9 道 checklist 题：

```text
q1：人物外观是否符合需求？
q2：是否始终保持写实真人风格？
q3：人物脸、手和伸手动作是否解剖结构正确？
q4：是否使用了需求中的柔和暖光？
q5：是否保持暖色和电影感调色？
q6：屏幕突破时是否出现细密的蜘蛛网裂纹？
q7：人物身体是否仍在屏幕内部，只有手伸出？
q8：第一人称视角下，人物的手是否抓住现实中的手？
q9：是否没有对白、字幕和画面文字？
```

所有问题的回答都是 `yes`：

```json
{
  "q1": "yes",
  "q2": "yes",
  "q3": "yes",
  "q4": "yes",
  "q5": "yes",
  "q6": "yes",
  "q7": "yes",
  "q8": "yes",
  "q9": "yes"
}
```

视觉评委使用了 16 个时间点的抽帧：

```text
0.25, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 3.75,
4.25, 4.75, 5.25, 5.75, 6.25, 6.75, 7.25, 7.75 秒
```

这些回答被按子项归类：

| 子项 | 对应问题 | checklist 分数 |
|---|---|---:|
| 风格准确性 | q1、q2 | 4.0 |
| 风格持续性 | q2 | 5.0 |
| 风格与内容兼容 | q3、q6、q7、q8 | 5.0 |
| 光照控制 | q4 | 5.0 |
| 色彩控制 | q5 | 5.0 |

虽然这个案例的所有问题都回答正确，但 checklist 通过率的映射和核心题权重仍由统一评分规则计算，最终得到对应子项分数。

---

## 四、第三步：D13 数值组件实际有没有运行

这个案例的任务配置中，数值组件开关是：

```yaml
style_accuracy:
  csd_ref_similarity: true
  checklist: true

style_persistence:
  csd_temporal_drift: true
  checklist: true

style_content_compat:
  checklist: true
  firm_world_consistency: false

lighting_control:
  checklist: true

color_control:
  checklist: true
  palette_match: false
```

从配置上看：

- CSD 参考相似度：允许运行。
- CSD 时间漂移：允许运行。
- FIRM：关闭。
- 调色板：关闭。

但“允许运行”不代表一定会有有效分数。

### 1. CSD 参考相似度

结果是：

```json
{
  "status": "not_applicable",
  "reason": "no style reference image (first/last frame or reference image)"
}
```

原因是：

- r2va 的 `input_01.jpg` 被判定为 `unknown`。
- 它不是高置信度纯风格参考。
- D13 当前策略不把 unknown 参考图送进 CSD。
- 因此没有合格风格参考图。
- `csd_ref_similarity` 被标记为 `not_applicable`。

所以风格准确性最终只剩 checklist：

```text
style_accuracy = 4.0
```

并不是：

```text
checklist × 0.6 + CSD × 0.4
```

而是把不可用的 CSD 组件剔除后，剩余 checklist 权重重新归一化为 1.0。

### 2. CSD 时间漂移

这个组件尝试运行了，但失败：

```json
{
  "status": "error",
  "reason": "ModuleNotFoundError: No module named 'scenedetect'"
}
```

错误发生在：

```text
media.shot_spans()
```

因为 CSD 时间漂移需要先获得镜头区间，而当前环境没有安装 `scenedetect`。

因此：

```text
csd_temporal_drift = error
```

该组件没有分数，也不会按 0 分参与平均。

最后，风格持续性只剩 checklist：

```text
style_persistence = 5.0
```

这点非常重要：数值组件失败时，当前实现不是直接把它当 0 分，而是记录为 missing/error，并只用剩余有效组件重新计算。

### 3. FIRM

任务配置明确关闭了：

```yaml
firm_world_consistency: false
```

因此：

```json
"disabled_components": [
  "firm_world_consistency"
]
```

FIRM 没有启动，也没有加载模型。

风格与内容兼容子项只有 checklist：

```text
style_content_compat = 5.0
```

### 4. 调色板匹配

任务配置明确关闭了：

```yaml
palette_match: false
```

所以：

```json
"disabled_components": [
  "palette_match"
]
```

调色板组件没有运行，色彩控制只使用 checklist：

```text
color_control = 5.0
```

---

## 五、这个案例的各子项分数

最终 `result.json` 中的子项结果如下：

| 子项 | 最终分数 | 实际使用的组件 | 未使用原因 |
|---|---:|---|---|
| 风格准确性 | 4.0 | checklist | 没有高置信度纯风格参考，CSD 不适用 |
| 风格持续性 | 5.0 | checklist | CSD 时间漂移因缺少 `scenedetect` 运行失败 |
| 风格与内容兼容 | 5.0 | checklist | FIRM 被任务配置关闭 |
| 光照控制 | 5.0 | checklist | 该子项本来只有 checklist |
| 色彩控制 | 5.0 | checklist | palette_match 被任务配置关闭 |

五个子项均适用，因此最终维度分为：

$$
\frac{4.0 + 5.0 + 5.0 + 5.0 + 5.0}{5}
= 4.8
$$

最终结果：

```json
{
  "score": 4.8,
  "raw_score": 4.8,
  "status": "ok"
}
```

---

## 六、为什么 summary.md 中这个 run 的平均分是 4.5

这个目录里实际有两个案例：

```text
cn300v2_096377fa92e90a3a7fdc321c
cn300v2_07e78d618c8ac2e71e469c89
```

两个案例的分数分别是：

```text
4.8
4.2
```

因此整个 `delivery_r2va_d13` 的平均分为：

$$
\frac{4.8 + 4.2}{2} = 4.5
$$

所以 `summary.md` 中显示：

```text
13_style_visual_control 风格与视觉控制  score=4.5  valid=2/2
```

子项均值则是：

- 风格准确性：两个案例都是 4.0，均值 4.0。
- 风格持续性：两个案例都是 5.0，均值 5.0。
- 风格与内容兼容：两个案例都是 5.0，均值 5.0。
- 光照控制：两个案例都是 5.0，均值 5.0。
- 色彩控制：第一个案例 5.0，第二个案例 2.0，均值 3.5。

---

## 七、这个案例暴露出的实际问题

这个实际案例说明了当前系统中的几个关键行为。

### 1. r2va 有参考图，不代表 CSD 一定使用参考图

这个案例确实有：

```text
input_01.jpg
```

但模型将它识别为 `unknown`，所以 CSD 参考相似度不适用。

当前策略是：

```text
只有明确要求参考图用于风格，
并且角色置信度达到阈值，
才进入 CSD。
```

这样可以避免把内容参考图、人物参考图或构图参考图误当成风格图。

### 2. 数值组件失败不会自动让子项变成 1 分

CSD 时间漂移因为缺少依赖失败：

```text
ModuleNotFoundError: No module named 'scenedetect'
```

但风格持续性仍然得到 5 分，因为 checklist 有效，剩余组件重新归一化。

这适合保证评测流程不中断，但也带来一个风险：如果数值组件大面积失败，最终分数可能退化成 checklist 分数。

### 3. 任务配置关闭的组件不会触发

这个案例中：

- FIRM 没有运行。
- palette 没有运行。

结果里明确区分了：

```text
disabled
```

和：

```text
not_applicable
```

以及：

```text
error
```

三种状态：

- `disabled`：任务配置主动关闭。
- `not_applicable`：输入或事实不适用。
- `error`：组件尝试运行但执行失败。

### 4. 这个 4.8 不是所有数值指标都成功后的完整分数

它是一个“当前配置和当前环境下的可比结果”：

- checklist 成功。
- gate 通过。
- CSD 参考相似度不适用。
- CSD 时间漂移报错。
- FIRM 被关闭。
- palette 被关闭。
- 五个子项仍然有有效 checklist 分数。
- 最终得到 4.8。

因此这个案例的 4.8 应理解为：

> 在当前组件开关、参考图角色判定和缺少 `scenedetect` 的环境下，基于有效组件重新归一化得到的 D13 分数。

它不能直接与“CSD、FIRM、palette 全部成功运行”的另一组结果视为完全同一评分基准。

## 八、完整调用链总结

这个案例的实际调用链是：

```text
r2va case
→ 读取 prompt、video、input_01.jpg
→ Qwen3-VL 从需求抽取 D13 facts
→ 生成 gate 和 checklist
→ Qwen3-VL 查看 16 帧回答 gate/checklist
→ gate 通过
→ 判断参考图不是高置信度纯风格参考
→ 跳过 CSD reference similarity
→ 尝试运行 CSD temporal drift
→ 因缺少 scenedetect 失败
→ FIRM 被任务配置关闭
→ palette_match 被任务配置关闭
→ 五个子项只保留有效 checklist
→ 子项分数为 4.0、5.0、5.0、5.0、5.0
→ case 分数为 4.8
```

这就是该目录中一个实际 D13 `r2va` 案例从输入、出题、答题、数值组件触发到最终得分的完整过程。

---

**User**

{
  "status": "not_applicable",
  "reason": "no style reference image (first/last frame or reference image)"
}
这结果就是来判断组件需不需要使用的吗？这个不适用是如何得到的？

---

**Cursor**

这条 `not_applicable` **不等于“系统决定这个组件不需要配置或不应该启用”**。它表示：本次已经进入了 CSD 参考风格相似度组件，但组件检查输入后发现没有符合条件的风格参考图，因此无法计算分数。

具体过程是：

1. 任务配置允许 `csd_ref_similarity` 运行。
2. D13 先根据 checklist 阶段生成的 `facts.reference_image_roles`，判断每张 r2va 参考图的用途。
3. 只有角色为 `style`、且置信度不低于 `0.75` 的参考图，才会传给 CSD。
4. 这个案例的 `input_01.jpg` 被标为 `unknown`，没有达到“高置信度纯风格参考图”的条件。
5. 因为传入 CSD 的风格参考列表为空，组件返回：

```json
{
  "status": "not_applicable",
  "reason": "no style reference image (first/last frame or reference image)"
}
```

所以，这个结果是**组件内部针对输入作出的适用性判断**，不是模型算出来的分数，也不是 gate 的结果。组件虽然被配置为启用，但因为没有合格输入，最后被评分器排除，风格准确性只用 checklist 分数，并对剩余权重重新归一化。

这条结果中的原因文字容易引起误解：当前策略明确将首尾帧排除在 CSD 参考图之外，所以括号中的 “first/last frame” 是历史表述，并不代表首尾帧可以供 D13 的 CSD 使用。更准确地说，这个案例是“没有符合 D13 规则的风格参考图”。

---

**User**

那目前facts，gates，和items分别的用处是什么？

---

**Cursor**

目前三者分别承担 **“决定评什么、决定能不能评、决定怎么判断”** 三个职责。

## 1. `facts`：结构化需求事实，决定评什么

`facts` 是第一步由 Qwen3-VL 从原始 prompt 中提取出的结构化信息。它描述的是：

> 用户要求了什么，以及哪些评测条件实际存在。

它本身不直接给分，主要用于触发或跳过子项和数值组件。

例如 D14：

```json
{
  "edit_targets": ["the red car"],
  "preserved": ["background"],
  "has_subject_replacement": false,
  "add_objects": [],
  "remove_objects": [],
  "is_continuation": false,
  "static_camera": true
}
```

这些字段会影响：

- 有 `edit_targets`：
  - 触发局部修改准确性。
- `has_subject_replacement: false`：
  - 跳过主体替换一致性。
- `add_objects` 和 `remove_objects` 为空：
  - 跳过增删物体。
- `is_continuation: false`：
  - 跳过视频延长。
- `static_camera: true`：
  - 允许使用静态镜头 LPIPS。

代码通过配置中的 `applies` 表达式判断：

```yaml
subject_replacement:
  applies: facts.has_subject_replacement
```

如果 `facts.has_subject_replacement` 是 `false`，该子项结果会是：

```json
{
  "applicable": false,
  "status": "not_applicable",
  "score": null
}
```

### `facts` 的具体作用

#### D13

```text
target_lighting
target_colors
style_spec
reference_image_roles
```

决定：

- 是否评光照。
- 是否评色彩。
- 风格要求是什么。
- r2va 哪些参考图可以进入 CSD。

#### D14

```text
edit_targets
has_subject_replacement
add_objects
remove_objects
is_continuation
static_camera
```

决定：

- 编辑类子项是否适用。
- 是否使用 ArcFace。
- 是否使用 GroundingDINO。
- 是否使用续写接缝 LPIPS。
- 是否使用静态区域 LPIPS。

#### D15

```text
dialogues
voice_forbidden
has_repeated_speaker
dialogue_emotions
ambient
sfx
music_required
music_forbidden
reference_audio_role
```

决定：

- 是否运行 Whisper。
- 是否运行 VAD。
- 是否评声音自然度。
- 是否评音色一致性。
- 是否评情绪、环境音、动作音效或配乐。

#### D16

```text
dialogues
multi_speaker
av_events
env_changes
realistic
```

决定：

- 是否运行 SyncNet。
- 是否评多人说话人匹配。
- 是否评环境音变化同步。
- 是否将口型数值模型视为适用。

#### D17

```text
subjects
main_subject_noun
has_humans
requested_camera_motion
```

决定：

- 是否有人体相关检测。
- 是否运行人体骨架。
- 是否运行 OIS。
- VMBench 检测使用什么主体名词。
- 哪些镜头运动属于需求本身，而不是异常。

#### D18

```text
expected_texts
allowed_texts
subtitles_required
subtitle_lines
text_forbidden
```

决定：

- 是否评目标文字准确性。
- 是否评字幕完整性。
- 哪些文字允许出现。
- 是否检测额外字幕、水印和杂字。

因此，`facts` 的本质是：

```text
原始需求
→ 结构化评测条件
→ 子项和数值组件适用性
```

---

## 2. `gates`：可评估性门槛，决定能不能评

`gates` 是在第一步生成的门槛问题，作用不是评价质量，而是判断这条视频是否具备基本的评测条件。

例如：

```json
{
  "id": "g1",
  "question": "Is the main subject clearly visible in the generated video?",
  "kind": "yes_no",
  "expect": "yes",
  "subpoint": null,
  "modality": "vision",
  "core": true
}
```

第二步中，视觉评委根据视频回答 gate。

如果回答符合 `expect`：

```text
gate passed
```

如果回答不符合：

```text
gate failed
```

### gate 失败后的处理

普通 gate 失败时：

- 后续数值组件不运行。
- 所有适用子项被覆盖为 1 分。
- 整个维度得分为 1。
- 该样本仍纳入总体均值。
- `strict_pass` 必为 `false`。

对应逻辑是：

```python
comps = {} if (audio_failed or not gate["passed"]) else dict(
    self.components(ctx, sp)
)
```

随后评分器会把适用子项改成最低分。

### gate 和 `facts` 的区别

| 项目 | `facts` | `gates` |
|---|---|---|
| 作用 | 判断哪些内容需要评 | 判断这条视频能不能评 |
| 来源 | 原始需求 | 原始需求和维度评测规则 |
| 是否给分 | 不直接给分 | 不直接给质量分 |
| 失败后果 | 子项或组件变为不适用 | 整个 case 进入最低分流程 |
| 例子 | “有对白”“要求蓝色灯光” | “主体是否可见”“视频是否可判断” |

### D15/D16 的音频 gate

D15、D16 还有单独的音频 gate，它不是 `gates` 中的 LLM 问题，而是代码检查音轨：

- 没有音轨。
- 全片音量过低。
- 大部分音频帧处于静音。

音频 gate 失败时：

- D15/D16 的适用音频子项记为 1 分。
- 仍然进入维度平均。
- 不一定让整个 case 变成普通 gate-failed。

所以存在两种 gate：

1. checklist gate：由视觉评委回答。
2. audio gate：由音频信号规则判断。

---

## 3. `items`：具体检查问题，决定怎么判断质量

`items` 是实际给第二步视觉或音频评委回答的 checklist 问题。

它们绑定到具体子项，并且包含标准答案、模态、权重等信息。

例如 D13 的一条 item：

```json
{
  "id": "q3",
  "subpoint": "style_content_compat",
  "question": "Are the boy's face, hands, and reaching action anatomically correct and continuous?",
  "kind": "yes_no",
  "expect": "yes",
  "options": [],
  "answer_index": null,
  "modality": "vision",
  "time_hint": "during the reaching action",
  "weight": 2.0,
  "core": true
}
```

它的作用是：

1. 让视觉评委根据成片回答。
2. 将回答与 `expect` 或 `answer_index` 比较。
3. 计算该子项的 checklist 通过率。
4. 再将通过率映射为 1-5 分。

### `items` 的字段作用

| 字段 | 作用 |
|---|---|
| `id` | 问题唯一编号，例如 `q1` |
| `subpoint` | 归属哪个二级评测项 |
| `question` | 实际问视觉或音频评委的问题 |
| `kind` | `yes_no` 或 `choice` |
| `expect` | yes/no 题标准答案 |
| `options` | choice 题选项 |
| `answer_index` | choice 题正确选项索引 |
| `modality` | `vision`、`audio` 或 `audio_visual` |
| `time_hint` | 评委需要关注的时间段 |
| `weight` | 问题权重 |
| `core` | 是否核心问题 |

### `items` 如何产生分数

假设一个子项有三道题：

```text
q1 权重 2，答对
q2 权重 1，答对
q3 权重 1，答错
```

通过率是：

$$
r=\frac{2\times1+1\times1+1\times0}{2+1+1}=0.75
$$

按照当前 checklist 映射：

- $r \ge 1.00$：5 分
- $r \ge 0.80$：4 分
- $r \ge 0.60$：3 分
- $r \ge 0.30$：2 分
- $r < 0.30$：1 分

所以 $r=0.75$ 会得到 3 分。

如果 q3 是核心题并且答错，即使其他题表现很好，该子项最高也只能得到 2 分。

---

## 4. 三者在一次评测中的完整关系

以 D14 “主体替换一致性”为例。

### 第一步：生成 facts

模型从 prompt 提取：

```json
{
  "has_subject_replacement": true,
  "subject_is_person": true
}
```

这表示：

- 该子项适用。
- 如果主体是人，可以触发 ArcFace。
- checklist 需要围绕主体替换生成问题。

### 第二步：生成 items

模型生成：

```json
{
  "id": "q1",
  "subpoint": "subject_replacement",
  "question": "Does the replaced person remain visually consistent throughout the video?",
  "kind": "yes_no",
  "expect": "yes",
  "modality": "vision",
  "weight": 2.0,
  "core": true
}
```

### 第三步：生成 gate

模型同时生成：

```json
{
  "id": "g1",
  "question": "Is the replaced subject visible clearly enough to evaluate?",
  "expect": "yes",
  "subpoint": null
}
```

### 第四步：回答 gate 和 item

评委看片后回答：

```text
g1 = yes
q1 = yes
```

因此：

- gate 通过。
- checklist 子项得分为 5。

### 第五步：触发数值组件

由于：

```text
facts.has_subject_replacement = true
gate passed = true
subject_is_person = true
```

并且任务配置没有关闭 ArcFace，所以触发：

```text
arcface_identity_keep
```

最终主体替换一致性子项可能是：

```text
checklist = 5
arcface = 4
```

根据权重：

```text
0.6 × 5 + 0.4 × 4 = 4.6
```

再按子项规则处理得到最终子项分数。

---

## 5. 三者之间最重要的边界

可以简单记成：

```text
facts：用户要求了什么？
gates：这条视频能不能评？
items：具体应该检查什么？
```

对应完整链路：

```text
原始 prompt
    ↓
facts
    ↓
决定子项和数值组件是否适用
    ↓
gates + items
    ↓
评委查看视频并回答
    ↓
gate 判断能否继续
    ↓
items 计算 checklist 分数
    ↓
数值组件执行
    ↓
组件和 checklist 合成子项分数
    ↓
子项平均得到维度分数
```

## 6. 回到之前的 CSD 例子

你之前看到的：

```json
{
  "status": "not_applicable",
  "reason": "no style reference image (first/last frame or reference image)"
}
```

在这条链路中属于第四步之后的**数值组件输入检查结果**：

- `facts.style_spec`：说明需求有风格要求。
- `facts.reference_image_roles`：说明 `input_01.jpg` 是 `unknown`，不是高置信度纯风格参考。
- `gates`：已经通过。
- `items`：已经回答并得到 checklist 分。
- CSD 被允许尝试，但 `_style_refs()` 返回空列表。
- `csd_ref_similarity()` 返回 `not_applicable`。
- 评分器剔除 CSD，只保留 checklist。

所以三者不是同一个层级：

```text
facts 负责决定评测条件
gates 负责决定是否继续评估
items 负责产生 checklist 质量分
CSD not_applicable 负责说明某个已允许组件缺少有效输入
```

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem13/delivery_r2va_d13
这个路径的内容是我使用task_d13_example.yaml配置运行评估的/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen/delivery_ref2va/r2va的第13维度的输出，但是目前测评完一个文件夹对应的视频后，我需要手动调整配置里面的@task_d13_example.yaml (13-14) @task_d13_example.yaml (18-20) 
output_dir: /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem13/delivery_r2va_d13
这三个地方，才可以再次开始测试，我需要你给我写一个脚本，来进行测试不需要要我中途进行手动替换可以直接接着运行，对应输出的位置可以参考前面的输出。你先完成这样一个脚本，但是不要自己运行，同时给我说明一下这个脚本会怎样做以及最终会得到什么。

---

**Cursor**

我会先核对现有 `run.py` 的参数、任务配置字段和输出目录结构，再新增一个不修改原始 YAML 的批量启动脚本。脚本完成后我只做静态检查，不会启动评估任务。

现有结果的完成标志位于 `output_dir/runs/<run_name>/summary.json`。我正在根据这个实际结构设置自动跳过逻辑，并核对输入根目录里可发现的批次与模式，确保脚本生成的名称不会碰撞。

已完成批量评估脚本：

`tools/vgen_eval/scripts/run_eval_batch.sh`

**没有启动任何评估任务**，也没有修改原来的 `task_d13_example.yaml`。只执行了 Bash 语法、LF 行尾和可执行权限检查。

### 使用方式

建议先查看将要运行的任务，不会创建文件或启动评估：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh --dry-run
```

确认任务列表后正式执行：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh
```

脚本的默认输入、输出和模板已经设置为：

```text
输入根目录：
work-log/work_300case/vgen

输出根目录：
work-log/work_929/dem/dem13

配置模板：
tools/vgen_eval/configs/task_d13_example.yaml
```

也可以显式指定完整路径：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --input-root /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen \
  --output-root /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem13
```

### 脚本会怎样做

1. 扫描 `<输入根目录>/<批次>/<模式>` 两级目录。
2. 自动识别 `t2va`、`f2va`、`l2va`、`fl2va`、`r2va`。
3. 从 `delivery_fl2va`、`delivery_ref2va` 等批次名中提取 `delivery` 或 `online`。
4. 自动生成任务名、运行名和输出目录。例如：
   - `delivery_ref2va/r2va` → `delivery_r2va_d13`
   - `delivery_fl2va/f2va` → `delivery_f2va_d13`
   - `online_fl2va/t2va` → `online_t2va_d13`
5. 根据输入模式自动生成正确的参考文件配置：
   - `t2va`：移除 `references`
   - `f2va`：使用 `input_01` 作为首帧
   - `l2va`：使用 `input_01` 作为尾帧
   - `fl2va`：使用 `input_01` 和 `input_02`
   - `r2va`：使用参考图片、视频和音频匹配规则
6. 在每个输出目录下写入独立的 `task.generated.yaml`。
7. 调用 `run.py --task-config task.generated.yaml`。
8. 当前目录评估成功后，自动开始下一个目录。
9. 每个任务的完整终端输出写入独立的 `evaluation.log`。
10. 如果输出目录的 `runs/*/summary.json` 已经存在，默认跳过该任务，实现断点续跑。

现有 `delivery_r2va_d13` 中已经存在 `summary.json`，因此默认会跳过它，即使其内部旧运行名是 `r2va_d13`，也不会重复评估。

### 当前数据会生成什么

目前输入根目录下发现了以下六组有效输入：

```text
delivery_fl2va/f2va
delivery_fl2va/t2va
delivery_ref2va/r2va
online_fl2va/f2va
online_fl2va/t2va
online_ref2va/r2va
```

对应输出位置为：

```text
work-log/work_929/dem/dem13/delivery_f2va_d13
work-log/work_929/dem/dem13/delivery_t2va_d13
work-log/work_929/dem/dem13/delivery_r2va_d13
work-log/work_929/dem/dem13/online_f2va_d13
work-log/work_929/dem/dem13/online_t2va_d13
work-log/work_929/dem/dem13/online_r2va_d13
```

每个新任务最终大致会产生：

```text
<任务输出目录>/
├── task.generated.yaml
├── evaluation.log
├── checklists/
└── runs/
    └── <自动生成的运行名>/
        ├── per_case.jsonl
        ├── summary.json
        ├── summary.md
        └── 13_style_visual_control/
```

### 控制运行范围

只运行两个 `r2va` 批次：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --include 'delivery_ref2va/r2va,online_ref2va/r2va'
```

只运行指定模式：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --modes 't2va,f2va'
```

某个任务失败后仍继续下一组：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --continue-on-error
```

强制重新运行已有 `summary.json` 的任务：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --rerun-completed
```

脚本已通过 `bash -n`，文件为 LF 行尾的可执行 Bash 脚本；当前环境没有安装 `shellcheck`，因此未执行该项检查。

---

**User**

如果我后面第13维度测完，同样的方式想测试第14维度，如何修改？

---

**Cursor**

可以复用同一个启动器，但当前版本把维度 13 写死了。为了让后续第 14 维度不需要复制脚本或手动改多处，我会把启动器改成支持 `--dimension 13/14`，并根据维度自动选择对应模板、任务名和输出目录；这次仍然只修改脚本，不启动评估。

现在不需要复制脚本或手动修改多个位置。我已经把 `run_eval_batch.sh` 改成支持第 13 和第 14 维度，通过 `--dimension` 选择评测维度。

脚本位置：

`tools/vgen_eval/scripts/run_eval_batch.sh`

## 第 14 维度的推荐用法

先只查看任务列表：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 14 \
  --dry-run
```

确认任务列表后正式运行：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 14
```

第 14 维度默认自动使用：

```text
模板：
tools/vgen_eval/configs/task_d14_example.yaml

输入根目录：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen_quick

输出根目录：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem14
```

这些默认路径是根据现有 `task_d14_example.yaml` 中的配置设置的。

## 如果第 14 维度使用完整数据目录

如果你确认第 14 维度应该使用 `vgen` 而不是 `vgen_quick`，可以显式指定输入目录：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 14 \
  --input-root /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen \
  --output-root /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem14 \
  --dry-run
```

确认无误后，删除 `--dry-run` 正式运行。

## 第 14 维度会自动完成的事情

启动器会自动：

1. 选择 `task_d14_example.yaml`。
2. 自动扫描 `delivery` 和 `online` 下的各个模式目录。
3. 自动生成类似下面的任务名：

```text
delivery_t2va_d14
delivery_f2va_d14
delivery_r2va_d14
online_t2va_d14
online_f2va_d14
online_r2va_d14
```

4. 自动生成对应输出目录：

```text
/work-log/work_929/dem/dem14/delivery_t2va_d14
/work-log/work_929/dem/dem14/delivery_f2va_d14
/work-log/work_929/dem/dem14/delivery_r2va_d14
```

5. 根据 `t2va`、`f2va`、`l2va`、`fl2va`、`r2va` 自动生成参考图配置。
6. 使用第 14 维度模板中的评测配置，包括首尾帧、身份保持和视频延续等设置。
7. 为每组任务生成独立的：
   - `task.generated.yaml`
   - `evaluation.log`
   - `runs/<run_name>/summary.json`
8. 当前任务完成后自动进入下一个任务。
9. 已经存在 `summary.json` 的任务默认跳过，可以中断后继续执行。

第 13 维度仍然可以使用原来的命令：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 13
```

这次只完成了脚本的维度通用化和静态检查，没有启动第 14 维度或第 13 维度的评估。

---

**User**

那这样后面测试15-18维度我需要修改哪里就可以进行测试？还有就是这些测试的输入默认路径全都设置和第13维度一样。

---

**Cursor**

明白。后续第 15–18 维度也应直接复用同一个启动器，并且所有维度的默认输入根目录统一使用第 13 维度的：

`work-log/work_300case/vgen`

我会把脚本扩展为支持 `13–18`，自动选择对应的 `task_d15_example.yaml` 到 `task_d18_example.yaml`，并统一生成 `dem/dem15` 到 `dem/dem18` 的输出目录。完成后只做静态检查，不执行评估。

后续测试第 15–18 维度时，只需要修改命令中的 `--dimension` 参数即可。批量启动器现在支持第 13–18 维度，并且所有维度默认使用与第 13 维度相同的输入根目录：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen
```

## 第 15 维度

先查看任务列表：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 15 \
  --dry-run
```

确认后正式运行：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 15
```

自动使用：

```text
模板：
tools/vgen_eval/configs/task_d15_example.yaml

输出根目录：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem15
```

## 第 16 维度

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 16 \
  --dry-run
```

确认后删除 `--dry-run`：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 16
```

自动使用：

```text
模板：
tools/vgen_eval/configs/task_d16_example.yaml

输出根目录：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem16
```

## 第 17 维度

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 17 \
  --dry-run
```

正式运行：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 17
```

自动使用：

```text
模板：
tools/vgen_eval/configs/task_d17_example.yaml

输出根目录：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem17
```

## 第 18 维度

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 18 \
  --dry-run
```

正式运行：

```bash
CUDA_VISIBLE_DEVICES=2 \
VGEN_EXTERNAL_GPU=3 \
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 18
```

自动使用：

```text
模板：
tools/vgen_eval/configs/task_d18_example.yaml

输出根目录：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem18
```

## 统一行为

对于任意一个维度，例如第 15 维度，脚本会自动：

1. 选择 `task_d15_example.yaml`。
2. 强制把输入根目录设置为：

   ```text
   /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen
   ```

3. 扫描：

   ```text
   delivery_fl2va/f2va
   delivery_fl2va/t2va
   delivery_ref2va/r2va
   online_fl2va/f2va
   online_fl2va/t2va
   online_ref2va/r2va
   ```

4. 自动生成带维度后缀的任务名，例如：

   ```text
   delivery_f2va_d15
   delivery_t2va_d15
   delivery_r2va_d15
   ```

5. 自动生成独立输出目录，例如：

   ```text
   work-log/work_929/dem/dem15/delivery_f2va_d15
   work-log/work_929/dem/dem15/delivery_t2va_d15
   work-log/work_929/dem/dem15/delivery_r2va_d15
   ```

6. 继承对应维度模板里的评测配置。
7. 根据模式自动写入首帧、尾帧或参考素材配置。
8. 自动连续执行所有任务。
9. 已存在 `summary.json` 的任务默认跳过。
10. 每个任务保存独立的 `task.generated.yaml` 和 `evaluation.log`。

如果只想测试某些模式，可以继续使用：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 15 \
  --modes 't2va,r2va' \
  --dry-run
```

如果只想运行特定批次：

```bash
bash tools/vgen_eval/scripts/run_eval_batch.sh \
  --dimension 15 \
  --include 'delivery_ref2va/r2va,online_ref2va/r2va' \
  --dry-run
```

我已经将脚本扩展到支持 `13、14、15、16、17、18`，并确认 `task_d13_example.yaml` 到 `task_d18_example.yaml` 都存在。脚本通过了 Bash 语法和行尾检查；本次没有启动任何评估任务。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem13/delivery_r2va_d13
现在先依据这个依据测试完的写一个测试文档，还需要和后续测出来的online的对应进行说明，也需要包含13-18的6个维度，你先完成这个文档的框架和依据可以写的内容，后续所有都测试完后再进行补充。

---

**Cursor**

我会先读取第 13 维度 `delivery_r2va_d13` 的汇总结果、已有评测说明和第 13–18 维度定义，然后创建一份可持续补充的 Markdown 测试文档。当前只写入已完成的 delivery 第 13 维度内容，并为 online 对照及第 14–18 维度预留结构，不会虚构尚未完成的结果。

现有结果已经足够写出第一版：第 13 维度 delivery、`r2va`、100 条有效视频，汇总分为 `4.424`，9 条触发评测门槛并按当前实现记为 1 分。需要特别记录的是：这次部分数值组件没有真正参与最终分数，例如 `scenedetect` 缺失导致 CSD 时间漂移未运行，FIRM 和调色板组件按配置关闭，因此文档会把“当前实测结果”和“完整方案目标”分开。

已创建阶段性测试文档：

`work-log/work_929/dem/dem13_18_evaluation_report.md`

这份文档目前包含：

- 第 13–18 维度的整体评测框架；
- 六个维度的名称、评测重点和后续填写位置；
- delivery 与 online 的对照原则；
- 输入目录、输出目录和结果文件结构；
- 评测流程、门槛失败和组件状态的解释；
- delivery 第 13 维度 `r2va` 的实际结果；
- online 第 13 维度的对照表；
- 第 14–18 维度的结果填写表；
- 全部维度完成后的最终汇总表；
- 后续补充和结果核对步骤。

当前已经写入的第 13 维度结果来自：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem/dem13/delivery_r2va_d13/runs/r2va_d13/summary.json
```

当前记录为：

```text
case 数量：100
有效数量：100
门槛失败数量：9
总分：4.424 / 5
```

子项结果为：

```text
style_accuracy：4.140
style_persistence：4.520
style_content_compat：4.540
lighting_control：4.390
color_control：4.530
```

文档也明确记录了本次结果的限制：

- CSD 参考风格相似度在当前 r2va 数据中多数为 `not_applicable`；
- CSD 时间漂移组件因缺少 `scenedetect` 没有真正运行；
- `firm_world_consistency` 按配置关闭；
- `palette_match` 按配置关闭；
- 当前分数主要由检查清单结果贡献，不能解释为所有设计中的数值组件都已经完整参与。

后续完成 `online_r2va_d13` 后，主要补充第 6 节的 online 结果和差值。第 14–18 维度测试完成后，分别将 `summary.json` 中的总分、子项均值、有效 case 数、门槛失败数和组件限制填入对应章节。文档中未完成的项目暂时保留为“待补充”，没有将它们误写成 0 分或测试失败。

我也检查了文档格式：

- 使用 LF 行尾；
- 未修改原始配置和评测结果；
- 未执行任何新的评估；
- 没有使用不兼容的 `\(...\)` 或 `\[...\]` 公式定界符。

---

**User**

我需要说明的是在目前每个评测维度中被明确关闭不使用的数值组件就理解为当前的评估体系没有这个组件，而不是理解为后续会打开，再调整一下这个测试文档。

---

**Cursor**

我会调整文档中的组件状态表述：明确区分“当前评估体系主动关闭的组件”和“运行时缺失或报错的组件”。前者将被描述为当前体系不包含、不会作为本轮结果缺项；后者仍单独记录为运行限制。不会修改评测结果或配置。

已按你的要求调整测试文档：

`work-log/work_929/dem/dem13_18_evaluation_report.md`

现在文档明确采用以下组件状态口径：

- `ok`：属于当前评估体系，并且本条 case 成功运行。
- `disabled`：由当前维度配置明确关闭，表示**当前评估体系不包含该组件**。这不是运行失败，也不表示后续需要打开。
- `not_applicable`：组件属于当前评估体系，但当前 case 不满足适用条件。
- `error` / `missing_input`：组件属于当前评估体系，但本次运行因为依赖、输入或执行问题没有成功得到结果。

针对当前第 13 维度，文档已修改为：

- `firm_world_consistency`：属于当前评估体系明确不使用的组件；
- `palette_match`：属于当前评估体系明确不使用的组件；
- 这两个组件不参与本次分数，也不再写成“待开启”“待补测”或“缺失组件”；
- CSD 时间漂移则单独记录为当前体系中应运行、但因为缺少 `scenedetect` 依赖而产生运行错误的组件。

同时调整了后续补充规则：未来填写第 14–18 维度时，也会按照这套口径区分当前体系不包含、不适用和运行失败，不会把配置中主动关闭的数值组件列入后续待开启项目。

本次只修改了报告文档，没有修改评测配置、评测结果，也没有重新运行测试。文档已通过 Markdown 诊断、公式定界符和 LF 行尾检查。

---

**User**

不是在测试文档中明确不使用，而不是不需要提及这个内容，就当做不存在。

---

**Cursor**

明白。测试文档中不再解释或列出被关闭的组件，直接按当前评估体系实际包含的内容记录；关闭组件视为不存在。文档只保留会影响当前结果解释的“不适用”以及“运行错误/输入缺失”信息。我现在清理相关表述，不修改结果和配置。

已按你的要求再次调整文档：

`work-log/work_929/dem/dem13_18_evaluation_report.md`

现在文档中已经移除了以下内容：

- 不再出现 `disabled`；
- 不再出现“关闭组件”；
- 不再列出当前配置中未纳入评估体系的具体组件；
- 不再说明这些组件是否会在后续启用；
- 不再把这些组件写成“待补测”或“缺失组件”。

文档现在只保留当前评估体系中实际需要说明的三种状态：

- 已成功运行的组件；
- 因当前 case 不适用的组件；
- 当前体系中本应运行、但因依赖或输入问题失败的组件。

因此，第 13 维度部分现在只保留了：

- CSD 参考风格相似度在部分 case 中不适用；
- CSD 时间漂移因为缺少 `scenedetect` 产生运行错误；
- 当前总分 `4.424` 是按照本次实际评估流程得到的结果。

已完成 Markdown 语法、公式定界符、行尾和诊断检查，没有重新运行任何评测。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/docs/dims_13_18_current_evaluation_plan.md
这个评估方案文档里面也会出现我前面说的这个情况，你修改一下放到和前面测试文档一个路径下

---

**Cursor**

我会保留原始评估方案文档不动，读取其中涉及“明确关闭、不使用、后续开启”等内容，生成一份按你当前要求整理后的副本，放到测试文档同一目录：

`work-log/work_929/dem/`

新副本中不展开当前体系未纳入的组件，只保留实际评估流程、适用条件和运行错误等必要说明。

已将整理后的评估方案副本放到测试文档同一目录：

`work-log/work_929/dem/dims_13_18_current_evaluation_plan.md`

原文件 `tools/vgen_eval/docs/dims_13_18_current_evaluation_plan.md` 保持不变。

新文档仍包含 D13–D18 的输入模式、评分流程、各维度评测内容和汇总规则；已移除关于当前评估体系未纳入组件的说明，不再列出这些组件，也不再把它们写成后续待启用或待补测事项。对于本次运行中应参与评测但因不适用、输入不足或运行错误而没有结果的组件，文档仍保留相应说明。

文档通过了格式和诊断检查，没有启动评测。

---

**User**

你把我现在作为一个小白，带我模拟的走一遍一个视频的评估全过程，这其中需要有组件的参与，我需要明白所有评估中的流程。

---

**Cursor**

我会用你已经完成的 `delivery_r2va_d13` 结果做一个具体演练：从输入目录里的单条视频开始，沿着任务配置、检查清单、评委判断、数值组件、计分和汇总，逐步说明每一步谁在做什么。这样能把真实流程和示例区分开，也能准确说明哪些组件会运行、哪些情况会不适用或报错。

下面我用已经完成的一个真实视频 case，带你从“把文件交给评测程序”一步一步走到“得到最终分数”。这是根据已有记录做的**流程演练**，没有重新运行评测。

这个 case 的结果是 **4.2 分（满分 5 分）**。它属于第 13 维度，检查视频是否按要求呈现风格、光照和颜色等视觉效果。

## 先认识这次评测的输入

这次评测的 case 编号是 `cn300v2_07e78d618c8ac2e71e469c89`，输入模式是 `r2va`，意思是：评测输入包含提示词、生成视频，以及提示词实际引用的参考素材。

视频文件是：

```text
/work-log/work_300case/vgen/delivery_ref2va/r2va/cn300v2_07e78d618c8ac2e71e469c89/video.mp4
```

程序还读取了对应的提示词和参考图 `input_01.png`。这个 case 要求生成一段写实电影风格的视频，内容是两个人逃离火山喷发；画面应有黄昏时的冷蓝色调，以及火山喷发产生的暖橙色光。

## 全过程

### 1. 先检查任务文件能不能组成一个有效 case

评测程序先根据任务配置找到 case，再检查提示词、视频和该输入模式需要的参考素材。缺少必需文件时，后续就无法正常评价这个 case。

这次读取记录中没有素材警告，视频路径也已写入 case 结果，因此评测进入了后续步骤。

### 2. Qwen3-VL 把提示词整理成“评测清单”

评测组件中的 **Qwen3-VL-32B** 读取提示词和参考信息，将自然语言要求整理成三类内容：

- **Facts（需求事实）**：例如目标风格、目标光照、目标颜色和主体。
- **Gates（门槛问题）**：判断视频是否具备继续评分的基本条件。
- **Items（评分问题）**：按五个子项列出具体检查问题。

这个 case 的事实包括：

- 目标风格：写实、电影感、真人实拍风格。
- 目标光照：黄昏冷蓝环境光，以及火山喷发的暖橙色光。
- 目标颜色：冷蓝色和暖橙色。
- 主体：两名正在逃离火山喷发的人物。

清单还生成了两个门槛问题：

1. 两个人物是否在视频中可见？
2. 视频的视觉风格是否从头到尾保持一致？

此外，它把评分问题分到了“风格准确性”“风格持续性”“风格与内容兼容”“光照控制”和“色彩控制”五个子项中。例如，会检查视频是否写实、火山喷发后人物脸上是否有暖橙色光，以及画面是否从冷蓝色过渡到橙色。

### 3. 视觉评委看成片并回答清单

清单生成后，评测程序才把成片交给视觉评委。程序从视频中抽取画面帧，供评委按门槛问题和评分问题进行判断。这样，评委检查的是实际生成的视频，而不是只根据提示词猜测视频质量。

对这个 case 来说，结果记录显示两个门槛都通过：

- 人物可见：通过。
- 视觉风格整体一致：通过。

因此 case 被允许继续计算分数。若门槛没有通过，程序会按门槛规则处理，不能简单把它当成一个正常通过门槛的评分结果。

### 4. 其他组件按条件检查视频

除了清单评审，D13 还会在适用时运行数值评测组件。可以把这里理解为：清单评委根据问题检查画面，其他组件则按各自的输入和算法做补充检查；组件不适用或运行失败时，不会凭空产生一个数值分数。

这个 case 的记录体现了两种不同情况：

- **参考风格比较不适用**：清单生成记录将 `input_01.png` 标为风格参考，置信度为 `0.95`；但最终结果记录没有把它作为 CSD 风格比较的有效参考。因此这次没有得到“成片与参考图风格相似度”的分数。
- **时间漂移组件运行报错**：CSD 时间漂移组件报错，原因是运行环境缺少 `scenedetect`。所以这次没有得到该组件的数值结果。

这里要区分“没有数值结果”和“视频得了低分”：这两种情况不是一回事。程序保留了实际成功得到的清单评分，并在结果中记录了组件不适用或出错的原因。

### 5. 把评分问题合成为五个子项分数

评分问题先按题目权重计算正确比例，再映射到 1–5 分。若某个子项有可用的数值组件，也会按组件规则参与合成；组件不适用或报错时，只根据该子项仍然有效的结果计算。

这个 case 的五个子项分数如下：

- **风格准确性：4.0 分。** 这项清单评分有效，但没有可用于本 case 的参考风格相似度结果。
- **风格持续性：5.0 分。** 清单评分为 5 分；时间漂移组件虽然尝试运行，但因依赖缺失报错。
- **风格与内容兼容：5.0 分。** 评委认为风格呈现没有破坏主体和内容。
- **光照控制：5.0 分。** 评委认为黄昏冷蓝光与火山暖橙光的要求得到了满足。
- **色彩控制：2.0 分。** 这是本 case 得分最低的一项。清单里有两个颜色相关问题：一个检查整体冷蓝与暖橙的配色，另一个检查火山喷发后天空是否转为橙色。最终清单评分映射为 2 分，说明这部分要求没有充分满足；现有结果不足以进一步断言具体是哪一处画面问题造成的。

### 6. 计算这个视频的最终分数

这五个子项都适用于该 case，因此维度总分是五项分数的算术平均：

$$
\frac{4.0 + 5.0 + 5.0 + 5.0 + 2.0}{5} = 4.2
$$

所以这个视频在第 13 维度的最终分数是 **4.2 分**。这不是一个单独的模型直接“看完视频给出的总分”，而是门槛判断、逐题评分、适用组件结果和子项合成之后得到的结果。

### 7. 单个 case 如何进入批次总分

这个 case 的完整评分写在自己的 `result.json` 中。汇总阶段会把各 case 的结果逐条写入 `per_case.jsonl`，再据此生成 `summary.json` 和 `summary.md`。

因此，这个视频的 **4.2 分**是单 case 分数；同一批次 **100 个 case** 的汇总结果是 **4.424 分**。两者回答的问题不同：4.2 描述这个视频，4.424 描述该批次所有有效 case 的平均结果。该批次汇总记录为 100 个有效 case、0 个无效 case，其中 9 个 case 未通过门槛。

## 用一句话串起来

**读取任务文件 → Qwen3-VL 整理需求和评分清单 → 视觉评委检查成片并回答门槛题和评分题 → 适用的数值组件补充评估 → 合成五个子项分数 → 得到该视频 4.2 分 → 与其他 case 一起进入批次汇总。**

这个真实例子还说明：组件结果要结合状态一起读。参考比较“不适用”和组件“运行报错”都不等于该视频在该项得了 0 分；最终分数来自结果文件中实际产生并参与合成的评分。

---

**User**

那你给我找一下目前补充检查有结果的case再叙述一遍：4. 其他组件按条件检查视频。这一部分往后的的内容

---

**Cursor**

我找到了一条**补充数值检查确实成功并参与评分**的真实 case。它属于 `delivery_f2va_d13`，case 编号是 `cn300v2_040647aeb30f2909ab9ba9cb`。与前一个参考图模式的例子不同，这条记录里的 **CSD 时间漂移组件成功运行，并实际参与了“风格持续性”评分**。

下面从“其他组件按条件检查视频”这一步开始，接着走到最终分数。

## 4. 其他组件按条件检查视频

这个 case 的提示词要求生成一段仙侠风格的写实 CG 视频：三位穿古装的女性处在云海、瀑布和圆月等场景中。该 case 是 `f2va`，即提供了**首帧图**作为视频生成条件。

评测结果里能看到两类互补的检查：

- **清单评审**：视觉评委检查风格是否符合要求、全片风格是否一致、人物结构是否自然，以及光照和颜色是否符合提示词。
- **CSD 时间漂移检查**：对成片进行数值分析，检查视觉风格随时间是否发生明显变化。该组件本次状态为 `ok`，产生了 **5.0 分**，并参与风格持续性子项的合成。

还有一个容易混淆的地方：虽然输入中有首帧图，但它的用途是首帧条件，不是这次 CSD 风格比较所用的风格参考图。因此，结果中的**参考风格相似度**为“不适用”。这不是该组件算出了低分，而是这条 case 没有符合该项比较用途的参考输入。

## 5. 合成五个子项分数

这条 case 的门槛检查通过了：主体可见，视频也满足单镜头连续性的门槛要求。随后，评测程序按子项整理可用的检查结果：

- **风格准确性：5.0 分。** 清单评审给出 5.0 分；没有可用于参考风格相似度比较的输入。
- **风格持续性：5.0 分。** 清单评审为 5.0 分，CSD 时间漂移检查也为 5.0 分。
- **风格与内容兼容：5.0 分。** 清单评审认为人物和场景内容与风格表现兼容。
- **光照控制：5.0 分。** 清单评审认为月光、环境光和雾气等光照要求得到满足。
- **色彩控制：5.0 分。** 清单评审认为整体颜色符合提示词描述。

这条结果中，最能说明“补充组件如何参与”的是**风格持续性**。这个子项里，清单评审占 40%，CSD 时间漂移占 60%；两者结果都是 5.0，因此合成后仍为 5.0：

$$
5.0 \times 0.4 + 5.0 \times 0.6 = 5.0
$$

也就是说，CSD 不是单独替代评委给整条视频打分，而是把自己负责的时间变化检查结果，按设定权重补充到对应子项中。

## 6. 得到单个视频的最终分数

五个子项都适用于这条 case，最终维度分取它们的平均值：

$$
\frac{5.0 + 5.0 + 5.0 + 5.0 + 5.0}{5} = 5.0
$$

所以这条视频的第 13 维度最终得分为 **5.0 分**。它的单 case 结果保存在对应的 `result.json` 中，之后也会作为一条记录进入 `per_case.jsonl`。

## 7. 从单个 case 到整批汇总

这条 case 的 **5.0 分**只代表这个视频。`delivery_f2va_d13` 这一批的汇总文件记录了 **100 个有效 case**，批次平均分为 **4.226 分**。批次汇总不是把某个视频的分数复制过去，而是对该批的 case 结果按评测程序的规则进行聚合。

## 这次例子与前一个例子的区别

前一个 `r2va` 例子中，参考风格相似度不适用，CSD 时间漂移也因依赖问题报错，所以主要依靠清单评审得到相关子项分数。

这次 `f2va` 例子中，CSD 时间漂移成功运行并得到 5.0，**真实参与了风格持续性子项的加权计算**。因此它更适合展示补充数值组件从“运行成功”到“影响子项分数”的完整过程。

---

**User**

那你再给我讲解一下评委答题是如何映射的？

---

**Cursor**

评委答题的映射可以分成 **4 层**：

1. 模型输出什么答案；
2. 程序判断答案对不对；
3. 把一组题的正确率映射成 1–5 分；
4. 再把清单分和其他数值组件合成为子项分。

下面用刚才找到的真实 `f2va` case 说明。

## 一、评委实际回答什么

清单生成阶段，Qwen3-VL 先生成问题。例如这个 case 生成了：

- `g1`：三位穿古装的女性是否在视频中可见？
- `g2`：视频是否是没有剪辑的连续镜头？
- `q1`：画面是否是写实 CG 和中国仙侠风格？
- `q2`：整个视频的视觉风格是否保持一致？
- `q3`：人物的脸、手和动作是否没有被风格化破坏？
- `q4`：光照是否符合月光、环境光和雾气要求？
- `q5`：颜色是否符合浅绿色、白色、淡蓝色、金色等要求？

每道题还会指定一个期望答案。例如：

```text
q1: expect = "yes"
q2: expect = "yes"
q3: expect = "yes"
q4: expect = "yes"
q5: expect = "yes"
```

如果是负向要求，期望答案可以是 `"no"`。例如提示词要求“没有字幕”，那么问题可能是：

```text
问题：视频中是否出现字幕？
期望答案：no
```

评委看到视频后，会返回类似这样的结果：

```json
{
  "answers": [
    {
      "id": "q1",
      "answer": "yes",
      "evidence": "The video shows three women in flowing ancient Chinese robes."
    }
  ]
}
```

其中：

- `id` 表示回答哪一道题；
- `answer` 是评委的答案；
- `evidence` 是评委给出的画面依据。

`evidence` 用于记录和复核，**本身不直接参与算分**。

## 二、程序如何把模型答案变成“对”或“错”

### 1. 是非题

对于 `yes_no` 类型的问题，程序只接受：

- 以 `y` 开头的答案，转换成 `"yes"`；
- 以 `n` 开头的答案，转换成 `"no"`；
- 其他内容视为无法识别。

然后和清单里的 `expect` 比较。

例如：

```text
期望答案：yes
评委答案：yes
结果：正确，记 1
```

```text
期望答案：yes
评委答案：no
结果：错误，记 0
```

```text
期望答案：no
评委答案：no
结果：正确，记 1
```

所以“期望答案是 `no`”并不代表这道题不重要，而是表示这是一道**负向约束题**。只有评委回答 `no`，它才算答对。

### 2. 选择题

如果问题是选择题，清单会提供几个选项，例如：

```text
A. 写实真人风格
B. 二维动画风格
C. 三维卡通风格
D. 黑白素描风格
```

评委返回 `A`，程序把它转换成选项下标 `0`；清单中的正确选项也是下标 `0` 时，这道题记为正确。

选择题不是根据文字相似度判断，而是比较：

$$
\text{评委选项下标}=\text{期望选项下标}
$$

### 3. 未回答或无法解析

如果评委没有返回某道题，或者返回了无法识别的内容，这道题不会直接记为错误，而是标记为待处理，不进入这组题的分母。

例如 5 道题中：

- 4 道题回答有效；
- 其中 3 道答对；
- 1 道没有有效答案；

那么正确率是：

$$
r=\frac{3}{4}=0.75
$$

而不是：

$$
\frac{3}{5}=0.60
$$

这是为了区分“答错”和“没有得到有效回答”。

## 三、正确率如何映射成 1–5 分

程序对同一个子项下的题目按权重计算正确率。

清单正确率到分数的映射是：

- 正确率 $r \ge 1.00$：5 分；
- $0.80 \le r < 1.00$：4 分；
- $0.60 \le r < 0.80$：3 分；
- $0.30 \le r < 0.60$：2 分；
- $r < 0.30$：1 分。

可以写成：

$$
r=\frac{\sum_i w_i c_i}{\sum_i w_i}
$$

其中：

- $w_i$ 是第 $i$ 道题的权重；
- $c_i$ 是该题结果，答对为 $1$，答错为 $0$；
- 没有有效答案的题不进入分母。

### 一个简单例子

假设“风格准确性”有 3 道题：

```text
q1：权重 2，答对
q6：权重 1，答对
q7：权重 1，答错
```

那么：

$$
r=\frac{2\times1+1\times1+1\times0}{2+1+1}
=\frac{3}{4}
=0.75
$$

根据映射规则：

$$
0.60 \le 0.75 < 0.80
$$

所以清单组件得 **3 分**。

## 四、核心题失败时的特殊处理

清单中的部分问题会标记为 `core=true`，表示这是该子项的核心要求。

例如真实 `f2va` case 中：

```text
q1：是否是写实 CG 和中国仙侠风格？
core = true
```

如果核心题答错，即使其他普通题答得不错，该子项最高也只能得到 **2 分**。

计算过程是：

1. 先根据所有有效题的正确率映射出普通分数；
2. 如果核心题失败，就执行：

$$
\text{子项分}=\min(\text{原始子项分},2)
$$

例如：

```text
普通正确率映射结果：4 分
核心题 q1：答错
最终子项分：min(4, 2) = 2 分
```

这能防止模型在核心要求没有完成时，仅靠很多边缘问题获得高分。

在已有的 `r2va` 结果中，就能看到类似情况：某些 case 的 `q1` 或 `q2` 失败后，对应子项被限制到了 2 分或更低。

## 五、门槛题和普通评分题的区别

门槛题不是普通评分题，它先决定这个视频是否具备继续评价的基本条件。

例如：

```text
g1：主体是否可见？
g2：整体风格是否保持一致？
```

每道门槛题也会被映射为：

- 正确：`true`；
- 错误：`false`；
- 无有效回答：`null`。

只要出现明确的错误门槛，当前 D13 结果会把这个 case 视为门槛失败。

门槛失败后，程序仍然保留评委原本的答题结果用于诊断，但最终适用子项会被设置为最低分：

$$
\text{门槛失败后的 case 分数}=1
$$

因此，门槛失败不是“普通题少答对几道”，而是表示这个视频不满足继续正常评价的基本条件。

例如 D13 批次中，汇总文件记录了部分 `gate_failed` case。这些 case 仍然可以出现在有效统计中，但它们的最终分数按门槛失败规则处理。

## 六、真实 `f2va` case 的答题映射

真实 case 是：

```text
cn300v2_040647aeb30f2909ab9ba9cb
```

它的门槛要求是：

- 三位人物必须可见；
- 视频必须是连续镜头。

结果中：

```text
g1 = true
g2 = true
```

说明两个门槛都通过。

它的五个子项结果都是 5 分：

- 风格准确性：5.0；
- 风格持续性：5.0；
- 风格与内容兼容：5.0；
- 光照控制：5.0；
- 色彩控制：5.0。

其中，风格准确性相关清单题的主要回答可以理解为：

```text
q1：yes，答对
```

风格持续性相关清单题：

```text
q2：yes，答对
```

光照和色彩相关问题：

```text
q4：yes，答对
q5：yes，答对
```

因此这些清单组件都映射到 5 分。

## 七、评委分如何和 CSD 分合成

这个真实 case 的“风格持续性”有两个实际结果：

- 清单评审：5.0 分，权重 0.4；
- CSD 时间漂移：5.0 分，权重 0.6。

子项分计算为：

$$
\text{style\_persistence}
=
\frac{5.0\times0.4+5.0\times0.6}{0.4+0.6}
=5.0
$$

如果清单评审是 5.0 分，但 CSD 时间漂移只有 3.0 分，则会变成：

$$
\frac{5.0\times0.4+3.0\times0.6}{0.4+0.6}
=3.8
$$

也就是说：

- 评委负责回答语义问题；
- CSD 负责补充视觉随时间变化的数值检查；
- 二者按照权重合成为“风格持续性”。

这个过程不是把两种分数简单相加，也不是让 CSD 重新回答清单问题。

## 八、整个映射链条

以一道普通清单题为例，完整流程是：

```text
提示词
  ↓
Qwen3-VL 生成问题、期望答案和权重
  ↓
视觉评委读取视频抽帧
  ↓
视觉评委回答 yes / no 或选择题选项
  ↓
程序解析答案
  ↓
和 expect 比较，得到 1 或 0
  ↓
按题目权重计算正确率
  ↓
按阈值映射成 1–5 分
  ↓
核心题失败时限制最高分为 2
  ↓
与同一子项的其他数值组件按权重合成
  ↓
五个适用子项取平均
  ↓
得到该视频的最终维度分
```

对这个真实 case，最后就是：

$$
\text{最终分}
=
\frac{
5.0+5.0+5.0+5.0+5.0
}{5}
=5.0
$$

最关键的区别是：

- **评委回答**首先被转换成“每道题对还是错”；
- **多道题**再转换成某个清单组件的 1–5 分；
- **清单组件和数值组件**再组成子项分；
- **多个子项**最后组成整条视频的维度分。

---

**User**

我还有的疑问了每个问题的权重是如何设置的？以及例如这里的CSD的5分是怎么来的？

---

**Cursor**

问题权重和组件权重是两层不同的权重：

- **问题权重**：决定同一个子项中，哪一道清单题更重要。
- **组件权重**：决定清单评审和数值组件在同一个子项中各占多少比例。

## 一、每道问题的权重如何设置

当前规则由清单生成模型按照下面的原则设置：

- `1.0`：普通要求；
- `2.0`：核心要求；
- `0.5`：次要细节。

也就是说，权重不是根据问题文字长度计算的，而是根据它在当前评测维度中的重要程度设置。

清单生成规则要求：

> 中心要求使用 `2.0`，普通要求使用 `1.0`，次要细节使用 `0.5`。

模型还会根据提示词判断哪些问题是核心要求，并把这些问题标记为 `core=true`。

### 真实 `f2va` case 的问题权重

case：

```text
cn300v2_040647aeb30f2909ab9ba9cb
```

它生成了以下 5 个评分问题：

```text
q1 风格准确性：权重 2.0，核心题
q2 风格持续性：权重 2.0，核心题
q3 风格与内容兼容：权重 1.0，普通题
q4 光照控制：权重 1.0，普通题
q5 色彩控制：权重 1.0，普通题
```

原因是：

- `q1` 直接检查目标风格“写实 CG、中国仙侠风格”，是风格准确性的中心要求；
- `q2` 直接检查整个视频是否保持统一风格，是风格持续性的中心要求；
- `q3` 检查人物脸、手和动作是否被破坏；
- `q4` 检查月光、环境光和雾气；
- `q5` 检查整体颜色。

后面三个问题虽然重要，但相对于前两个核心风格要求属于普通要求，因此权重是 `1.0`。

## 二、问题权重如何影响正确率

对于某个子项，程序不是简单计算“答对了几道题”，而是计算**加权正确率**：

$$
r=\frac{\sum_i w_i c_i}{\sum_i w_i}
$$

其中：

- $w_i$ 是第 $i$ 道题的权重；
- $c_i$ 是答题结果，答对为 $1$，答错为 $0$；
- $r$ 是这个子项的清单正确率。

### 例子：核心题答错

假设“风格准确性”有 3 道题：

```text
q1：权重 2.0，答错
q6：权重 1.0，答对
q7：权重 1.0，答对
```

那么加权正确率是：

$$
r=\frac{2.0\times0+1.0\times1+1.0\times1}{2.0+1.0+1.0}
=\frac{2}{4}
=0.5
$$

正确率 $0.5$ 会映射为 2 分。

如果这时 `q1` 还是核心题，那么还要执行核心题限制：

$$
\text{最终子项分}
=
\min(2,2)
=
2
$$

### 例子：普通题答错

如果是下面这种情况：

```text
q1：权重 2.0，答对
q6：权重 1.0，答错
q7：权重 1.0，答对
```

则：

$$
r=\frac{2.0\times1+1.0\times0+1.0\times1}{4}
=0.75
$$

正确率 $0.75$ 映射为 3 分。

这里可以看出，答错一个权重为 `1.0` 的普通题，影响小于答错一个权重为 `2.0` 的核心题。

## 三、正确率如何变成清单分

加权正确率使用以下映射：

$$
\begin{aligned}
r=1.00 &\rightarrow 5\text{ 分}\\
0.80\le r<1.00 &\rightarrow 4\text{ 分}\\
0.60\le r<0.80 &\rightarrow 3\text{ 分}\\
0.30\le r<0.60 &\rightarrow 2\text{ 分}\\
r<0.30 &\rightarrow 1\text{ 分}
\end{aligned}
$$

因此，问题权重只影响第一步的正确率；正确率再通过阈值映射成清单组件的 1–5 分。

## 四、CSD 的权重和问题权重不是一回事

以“风格持续性”为例，当前 D13 配置规定：

```text
清单评审：权重 0.4
CSD 时间漂移：权重 0.6
```

它的计算公式是：

$$
\text{风格持续性}
=
\frac{
\text{清单分}\times0.4+
\text{CSD分}\times0.6
}{
0.4+0.6
}
$$

所以：

- 清单中的 `q2` 权重 `2.0`，只影响清单评审内部的正确率；
- CSD 的 `0.6`，影响 CSD 在“风格持续性”这个子项中的占比；
- 这两个权重处在不同层级，不能混在一起。

## 五、这个 case 中 CSD 的 5 分怎么来的

这里说的是成功运行的：

```text
csd_temporal_drift
```

它检查的是：视频前后不同时间的视觉风格是否发生明显漂移。

这个 case 的 CSD 原始结果保存在：

```text
work-log/work_929/dem/dem13/delivery_f2va_d13/runs/delivery_f2va_d13/13_style_visual_control/cn300v2_040647aeb30f2909ab9ba9cb/components/csd_temporal_drift.json
```

实际结果是：

```json
{
  "status": "ok",
  "value": 0.020405113697052002,
  "per_shot": [
    0.020405113697052002
  ],
  "cross_shot": 0.020405113697052002
}
```

这个 `0.020405...` 不是分数，而是 CSD 计算出的**风格漂移值**。

对于风格漂移来说：

- 数值越低，代表风格变化越小；
- 数值越低，说明风格持续性越好。

## 六、CSD 如何得到 `0.020405`

CSD 的计算过程可以分成 5 步。

### 第一步：从视频抽取画面

CSD 按大约 2 fps 从视频抽帧，最多使用 32 帧。

也就是说，视频不会逐帧全部送入 CSD，而是取一组具有时间代表性的画面。

### 第二步：把每一帧转换成风格向量

CSD 模型把每一帧画面转换为一个风格向量：

$$
e_1,e_2,\ldots,e_n
$$

这些向量经过归一化，可以用于比较不同画面的风格方向是否相近。

这里比较的不是人物是否完全相同，也不是像素是否完全相同，而是画面的整体风格特征，例如：

- 视觉媒介；
- 渲染方式；
- 色调；
- 纹理；
- 整体视觉风格。

### 第三步：计算视频整体风格中心

把所有帧的风格向量求平均，得到视频整体风格中心：

$$
c_{\mathrm{all}}
=
\frac{1}{n}\sum_{i=1}^{n}e_i
$$

之后再把这个中心向量归一化。

### 第四步：计算每帧和风格中心的距离

CSD 使用：

$$
1-e_i\cdot c_{\mathrm{all}}
$$

作为每一帧相对于整体风格中心的偏离程度。

由于向量已经归一化，$e_i\cdot c_{\mathrm{all}}$ 可以理解为余弦相似度：

- 越接近 1，说明风格越接近；
- $1-\text{相似度}$ 越小，说明漂移越小。

全片漂移值是所有帧偏离程度的平均值：

$$
d_{\mathrm{all}}
=
\frac{1}{n}
\sum_{i=1}^{n}
(1-e_i\cdot c_{\mathrm{all}})
$$

### 第五步：结合镜头内漂移

程序还会按镜头计算每个镜头内部的漂移值：

$$
d_{\mathrm{shot}}
=
\frac{1}{m}
\sum_{i=1}^{m}
(1-e_i\cdot c_{\mathrm{shot}})
$$

最终 CSD 漂移值取：

$$
d=\max(d_{\mathrm{shot}},d_{\mathrm{all}})
$$

这个真实 case 只有一个检测到的镜头，因此：

```text
per_shot = 0.020405...
cross_shot = 0.020405...
最终 value = 0.020405...
```

## 七、原始漂移值如何映射成 CSD 的 5 分

CSD 时间漂移使用的是“越低越好”的映射：

- 漂移值 $\le 0.05$：5 分；
- 漂移值 $\le 0.10$：4 分；
- 漂移值 $\le 0.18$：3 分；
- 漂移值 $\le 0.28$：2 分；
- 高于 $0.28$：1 分。

本 case 的值是：

$$
0.020405\ldots
$$

因为：

$$
0.020405\ldots \le 0.05
$$

所以：

$$
\text{CSD 时间漂移分}=5
$$

这就是结果中 CSD 的 5 分来源。它不是评委主观回答出来的，而是：

```text
视频抽帧
→ CSD 为每帧提取风格向量
→ 计算帧间风格漂移
→ 得到 0.020405
→ 根据阈值映射为 5 分
```

## 八、CSD 的 5 分如何进入最终子项

这个真实 case 中：

```text
清单评审：5.0 分，权重 0.4
CSD 时间漂移：5.0 分，权重 0.6
```

因此：

$$
\text{风格持续性}
=
\frac{5.0\times0.4+5.0\times0.6}{0.4+0.6}
=5.0
$$

最后，五个子项都是 5 分：

$$
\text{D13最终分}
=
\frac{5.0+5.0+5.0+5.0+5.0}{5}
=5.0
$$

## 九、还要区分两种 CSD

D13 中有两个不同的 CSD 检查：

### 1. CSD 参考风格相似度

它比较：

```text
生成视频的风格
vs
有效的风格参考图
```

这个指标是“越高越好”，例如：

- 相似度 $\ge 0.80$：5 分；
- 相似度 $\ge 0.65$：4 分；
- 相似度 $\ge 0.50$：3 分；
- 相似度 $\ge 0.35$：2 分。

### 2. CSD 时间漂移

它比较：

```text
视频前后不同时间的风格是否稳定
```

这个指标是“越低越好”，本次真实 case 的 `0.020405` 就属于这一类。

当前这个 `f2va` case 中，首帧图是首帧条件输入，不作为 CSD 风格参考图，所以参考风格相似度没有参与；真正成功参与评分的是 CSD 时间漂移。

最终可以这样记：

```text
问题权重：
决定清单题之间谁更重要。

CSD 原始值：
0.020405，表示风格漂移很小。

CSD 阈值映射：
0.020405 <= 0.05，所以得到 5 分。

组件权重：
清单 0.4，CSD 0.6。

子项合成：
5.0 × 0.4 + 5.0 × 0.6 = 5.0。
```

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/original
这个路径下是我把所有case都链接过来了，/kwkj-k8s/zq/Case/300通用/cn300_v2.local.json这个文件里写明了视频的对应的维度，你按照这个再创建一个新的文件夹，把对应于13-18维度的视频软连接一下。

---

**Cursor**

我先检查 `original` 目录的链接结构和 `cn300_v2.local.json` 的维度字段，确认每个 case 的视频路径与维度映射后，再创建新的整理目录并建立软连接。

已确认清单里每个 case 有 `primary_dimension_id`，而原始视频按 `delivery_fl2va`、`delivery_ref2va`、`online_fl2va`、`online_ref2va` 分目录保存。接下来我会按 13–18 维度筛选 96 个 case，并保留 delivery/online 两套视频版本建立软连接。

已完成。根据 `/kwkj-k8s/zq/Case/300通用/cn300_v2.local.json` 中的 `primary_dimension_id`，我创建了新的整理目录：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/original/dims_13_18_videos
```

## 整理结果

共筛选出：

- 13–18 维度：每个维度 16 个 case；
- 总计 96 个 case；
- 每个 case 保留 `delivery` 和 `online` 两个版本；
- 共创建 192 个视频软连接；
- 所有软连接均有效，没有断链。

目录结构如下：

```text
dims_13_18_videos/
├── 13_style_visual_control/
├── 14_edit_controllable_gen/
├── 15_audio_generation/
├── 16_av_sync/
├── 17_failure_anomaly_control/
└── 18_text_subtitle/
```

每个维度目录下继续按照原始视频来源区分：

```text
<dimension>/
├── delivery_fl2va/
├── delivery_ref2va/
├── online_fl2va/
└── online_ref2va/
```

每个维度当前都有 32 个视频软连接：

```text
13_style_visual_control: 32
14_edit_controllable_gen: 32
15_audio_generation: 32
16_av_sync: 32
17_failure_anomaly_control: 32
18_text_subtitle: 32
```

任务类型与原始目录的对应关系按现有目录结构处理：

- `t2v`、`i2v` → `*_fl2va`
- `ref2v` → `*_ref2va`

新目录中的文件只是软连接，没有复制视频内容。例如：

```text
dims_13_18_videos/16_av_sync/delivery_fl2va/cn300v2_811d980ea5bbeac0b1bdf3ca.mp4
```

指向：

```text
original/delivery_fl2va/cn300v2_811d980ea5bbeac0b1bdf3ca.mp4
```

---

**User**

你现在只是把视频放好了  还需要对应的提示词和参考内容呢，参考/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen路径下每个视频的配套内容

---

**Cursor**

明白，新目录需要是可直接使用的完整 case 输入，而不只是视频链接。我会按每个 case 在 `vgen` 下对应的 `prompt_final.txt`、图片/参考素材等一并建立软连接，并核对 `f2va` 和 `r2va` 的文件布局。

我确认了 `vgen` 中每个目标 case 的配套内容，实际包括：

- `prompt_final.txt`；
- `video.mp4`；
- `f2va` 的 `input_01.*`；
- `r2va` 的全部 `input_*.jpg/png` 参考图。

我会把现有整理目录改成“每个 case 一个文件夹”，并将这些文件全部软连接到对应的 `vgen` case，保留原来的维度、delivery/online 和输入模式分类。

你说得对，之前只整理了视频，没有把每个视频对应的提示词和参考输入一起整理好。现在已经补齐，并且全部使用 `vgen` 下每个 case 的配套内容建立软连接。

整理目录仍然是：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/original/dims_13_18_videos
```

现在每个 case 都是一个完整目录，例如：

```text
13_style_visual_control/
└── delivery_fl2va/
    └── cn300v2_9a9b254e652207aed0b1e6b9/
        ├── prompt_final.txt -> vgen/.../t2va/.../prompt_final.txt
        └── video.mp4        -> vgen/.../t2va/.../video.mp4
```

带参考图的 case 会额外包含参考文件，例如：

```text
13_style_visual_control/
└── delivery_fl2va/
    └── cn300v2_fe44e6cede57ab568a9d784f/
        ├── input_01.png
        ├── prompt_final.txt
        └── video.mp4
```

多个参考图也会全部保留：

```text
cn300v2_11894ae55bab5c6c0619d860/
├── input_01.png
├── input_02.jpg
├── prompt_final.txt
└── video.mp4
```

## 已整理内容

共包含：

- 13–18 维度；
- 96 个唯一 case；
- delivery 和 online 两个版本；
- 共 192 个完整 case 目录；
- 192 个 `prompt_final.txt` 软连接；
- 192 个 `video.mp4` 软连接；
- 178 个参考图片软连接；
- 所有软连接均有效，没有断链。

文件类型统计如下：

```text
prompt_final.txt: 192
video.mp4:       192
参考图 PNG:       76
参考图 JPG:      102
```

## `vgen` 的对应关系

整理时使用了 `vgen` 中的精确输入模式：

```text
t2v   -> vgen/<batch>_fl2va/t2va/<case_id>/
i2v   -> vgen/<batch>_fl2va/f2va/<case_id>/
ref2v -> vgen/<batch>_ref2va/r2va/<case_id>/
```

因此：

- `t2v` case 会有提示词和视频；
- `i2v` case 会有提示词、视频和首帧参考图；
- `ref2v` case 会有提示词、视频和该 case 的全部参考素材；
- 原有的 delivery/online 区分也都保留。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/original/dims_13_18_videos
目前这个是在original目录下，我希望这个文件夹和它平级

---

**Cursor**

明白，你希望整理目录位于 `original` 的同级，而不是 `original` 的子目录。我会把整个目录移动到：

```text
/work-log/work_300case/dims_13_18_videos
```

软连接目标使用的是绝对路径，移动目录后不会失效；移动完成后我会重新核验断链情况。

已按你的要求完成移动。

新的目录位置是：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/dims_13_18_videos
```

它现在与 `original` 平级：

```text
work_300case/
├── original/
├── dims_13_18_videos/
├── vgen/
└── ...
```

已核验：

- 完整 case 目录：192 个；
- 提示词、视频和参考素材软连接：562 个；
- 断链：0 个；
- 原来的路径已不存在：

```text
work_300case/original/dims_13_18_videos
```

由于软连接目标使用绝对路径，目录移动后所有配套内容仍然有效。

---

**User**

你还知道我前面让你写的统一测试的脚本吗？

---

**Cursor**

知道。为了准确对应你说的“统一测试脚本”，我先在当前仓库中查一下已有的批量启动器、统一评测入口和相关配置，确认它现在的实际文件名与用途。

记得。你前面让我写的是统一批量评测脚本：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval/scripts/run_eval_batch.sh
```

它的作用是统一启动第 13–18 维度的评测任务，主要功能包括：

- 通过 `--dimension 13` 到 `--dimension 18` 选择维度；
- 自动使用对应模板：
  - `task_d13_example.yaml`
  - `task_d14_example.yaml`
  - 依次到 `task_d18_example.yaml`
- 扫描统一输入目录下的 batch 和输入模式；
- 自动生成每个任务的 `task.generated.yaml`；
- 顺序执行评测并保存 `evaluation.log`；
- 自动跳过已经存在 `summary.json` 的任务；
- 支持 `--dry-run`、`--include`、`--modes`、`--rerun-completed` 和 `--continue-on-error`；
- 将结果输出到：

```text
work-log/work_929/dem/dem13/
work-log/work_929/dem/dem14/
...
work-log/work_929/dem/dem18/
```

默认输入目录是：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/vgen
```

例如只查看第 13 维度的执行计划：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

bash scripts/run_eval_batch.sh \
  --dimension 13 \
  --dry-run
```

真正运行时大致是：

```bash
bash scripts/run_eval_batch.sh \
  --dimension 13 \
  --include delivery_ref2va/r2va
```

需要注意的是：刚才新整理的目录：

```text
/work-log/work_300case/dims_13_18_videos
```

现在是按“维度 / delivery 或 online / 输入来源 / case”组织的完整 case 包，而现有统一脚本默认识别的是：

```text
<input-root>/<batch>/<mode>/<case_id>/
```

因此，**现有脚本可以继续直接使用原来的 `vgen` 目录，但还不能直接把 `dims_13_18_videos` 作为默认输入目录使用**。如果要用刚整理好的目录跑统一评测，需要再给脚本增加一层输入目录适配，或者把该目录调整成脚本能够扫描的布局。

---

**User**

/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/dims_13_18_videos
这个路径是你刚刚整理的，但是每个维度的fl2va里面还分为t2va和f2va，你再细分一下。

---

**Cursor**

可以。我会按每个 case 在 `vgen` 中的真实输入模式重新整理：

```text
delivery_fl2va/
├── t2va/
└── f2va/

delivery_ref2va/
└── r2va/
```

`online` 目录也同步处理。这样不会复制内容，只会移动现有 case 文件夹；里面的提示词、视频和参考素材软连接保持不变。

刚才移动脚本在处理过程中遇到一个目录状态不一致，已经完成了一部分移动，但结构还没有完全按你要求落定。我会立即统一修正为严格的目标结构：

```text
<dimension>/
├── delivery_fl2va/
│   ├── t2va/
│   └── f2va/
├── delivery_ref2va/
│   └── r2va/
├── online_fl2va/
│   ├── t2va/
│   └── f2va/
└── online_ref2va/
    └── r2va/
```

我会以清单重新核对每个 case，兼容刚才已经移动和还未移动的两种状态，不复制视频或参考文件。

已完成细分，现在目录结构已经按真实输入模式整理好了。

例如第 13 维度现在是：

```text
13_style_visual_control/
├── delivery_fl2va/
│   ├── t2va/
│   │   └── <case_id>/
│   │       ├── prompt_final.txt
│   │       └── video.mp4
│   └── f2va/
│       └── <case_id>/
│           ├── input_01.png 或 input_01.jpg
│           ├── prompt_final.txt
│           └── video.mp4
├── delivery_ref2va/
│   └── r2va/
│       └── <case_id>/
│           ├── input_*.jpg/png
│           ├── prompt_final.txt
│           └── video.mp4
├── online_fl2va/
│   ├── t2va/
│   └── f2va/
└── online_ref2va/
    └── r2va/
```

完整路径为：

```text
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/dims_13_18_videos
```

细分规则是：

```text
t2v   -> fl2va/t2va
i2v   -> fl2va/f2va
ref2v -> ref2va/r2va
```

已经对 13–18 六个维度全部处理完成，并核验了：

- 所有 192 个 case 包都处于正确的输入模式目录；
- `delivery_fl2va/t2va` 和 `delivery_fl2va/f2va` 已正确拆开；
- `delivery_ref2va/r2va` 也已补充；
- `online` 目录同步完成；
- 预期数量和实际数量完全一致；
- 软连接总数仍为 562 个；
- 断链数量为 0。

---

**User**

现在对于输入有一些改变，现在有争对每个维度的单独的测试case，和之前不一样是每个维度都测试一样的case，但是评估的流程还是没有改变，测试的6个维度的case在如下路径中：/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/dims_13_18_videos
每个维度的输出可以放在如下路径：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem13-18
你修改一下脚本，确保可以运行后可以一次性测试完这6个维度。不要求并行，可以测完一个维度再测试下一个维度，还要保证测试如果终端可以不用重新评测，而是接着继续评测。写完脚本你不要直接开始评测，而是和我说明如何启动脚本，且跑完可以得到什么内容，我再进行手动启动。

---

**Cursor**

我会修改现有的 `run_eval_batch.sh`，让它默认识别新的“按维度分目录、再按输入模式分目录”的结构，并按 13→18 顺序串行执行。修改前我会先确认任务配置对输入目录和断点续跑的要求，避免脚本生成出不能被 `run.py` 接受的配置。

脚本已经改好，且我没有启动任何评测。现在它会按 13→18 顺序逐个维度、逐个输入模式串行执行；我正在做最后的输入加载校验，确认 192 个 case 的提示词、视频和参考素材都能被评测入口正确识别。

我会再补一层“任务是否完整”的判断：只有该任务目录下所有 case 都已经产生 `result.json`，并且汇总数量一致时，下一次启动才会跳过整个任务。这样中途终端退出或单个 case 出错后，重跑同一条命令会继续未完成部分，而不会把不完整的 `summary.json` 误认为已完成。

脚本已完成修改，**没有启动实际评测**。当前已验证：

- 六个维度均能识别；
- 共发现 **34 个评测任务**；
- 共加载 **192 个 case**；
- 维度按 **D13 → D14 → D15 → D16 → D17 → D18** 顺序串行执行；
- dry-run、Bash 语法和 Python 语法检查均通过；
- 当前输出目录仍未写入评测结果。

修改文件：

- `tools/vgen_eval/scripts/run_eval_batch.sh`
- `tools/vgen_eval/run.py`

## 先查看执行计划

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

bash scripts/run_eval_batch.sh \
  --dry-run \
  --continue-on-error
```

这个命令只检查目录和打印任务计划，不会创建评测文件，也不会调用评测模型。

## 正式启动评测

确认 dry-run 输出无误后，执行：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

bash scripts/run_eval_batch.sh \
  --continue-on-error
```

脚本默认使用：

```text
输入：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_300case/dims_13_18_videos

输出：
/kwkj-k8s/research-eval-group/Eval-kzy/lt-self/work-log/work_929/dem13-18
```

不需要额外指定输入输出路径。

## 输出结构

每个输入模式会有独立的输出目录，例如：

```text
work-log/work_929/dem13-18/
└── 13_style_visual_control/
    └── delivery_fl2va/
        └── f2va/
            ├── task.generated.yaml
            ├── evaluation.log
            ├── checklists/
            │   └── task/
            │       └── <case_id>.json
            └── runs/
                └── delivery_fl2va_f2va_d13/
                    ├── per_case.jsonl
                    ├── summary.json
                    ├── summary.md
                    └── 13_style_visual_control/
                        └── <case_id>/
                            └── result.json
```

其中：

- `task.generated.yaml`：该任务实际使用的配置；
- `evaluation.log`：该任务的完整运行日志；
- `checklists/task/<case_id>.json`：每个 case 的 checklist 和需求事实；
- `result.json`：每个 case 的详细评测结果；
- `per_case.jsonl`：该任务所有已完成 case 的结果；
- `summary.json`：该任务的结构化汇总结果；
- `summary.md`：该任务的可读汇总报告。

当前脚本会为所有维度和输入模式分别保存结果，不会把不同输入模式混合到同一个分数中。

## 中断后的继续评测

如果评测中途终端退出或任务被中断，直接重新执行同一条命令即可：

```bash
cd /kwkj-k8s/research-eval-group/Eval-kzy/lt-self/tools/vgen_eval

bash scripts/run_eval_batch.sh \
  --continue-on-error
```

恢复逻辑如下：

1. 已经完整生成所有 case 结果和汇总文件的任务会被整体跳过；
2. 已经存在 `result.json` 的 case 不会重复评测；
3. 已经生成的 checklist 会继续复用；
4. 只会继续处理没有完成的 case；
5. 最后重新生成该任务的 `per_case.jsonl`、`summary.json` 和 `summary.md`；
6. 如果某个任务只有不完整的 `summary.json`，脚本不会误判为完成，会继续执行该任务。

`--continue-on-error` 会让某个任务失败后继续测试后续维度。命令最后如果存在失败或未完成任务，会返回非零退出码，之后再次执行相同命令即可继续。

恢复时不要使用下面两个参数：

```text
--force
--rerun-completed
```

这两个参数会重新计算已有结果，不适合普通断点续跑。


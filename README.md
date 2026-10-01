# D13-D18 本地评测框架

本目录恢复了一套可在没有远端服务器时运行的本地评测框架。它覆盖第 13 至第 18 维度，并保留了此前会话确定的核心工作流：

```text
case 输入
  -> facts：从 prompt 提取结构化需求事实
  -> checklist：生成 gates 和 items
  -> judge：视觉/音频评委回答 gates 和 items
  -> 数值组件：仅在子项适用、gate 通过且组件开启时执行
  -> result.json：单 case 结果
  -> summary.json / summary.md：批次汇总
```

## 当前本地实现边界

- 默认不依赖远端服务器，使用 `offline` 评委模式生成可复核的占位回答。
- 视觉裁判和音频裁判支持分别配置：`V_EVAL_VISION_JUDGE_URL` 对应 Qwen3-VL-32B-Instruct，`V_EVAL_AUDIO_JUDGE_URL` 对应 Qwen2.5-Omni-7B。
- 当前框架也兼容旧的 `V_EVAL_JUDGE_URL` 和 `V_EVAL_JUDGE_MODEL`，但新部署建议使用按模态拆分的变量。
- 配置 OpenAI 兼容服务后，框架会向对应服务的 `/chat/completions` 接口发送请求。
- 本地没有安装的视觉、音频和 OCR 模型不会被伪装成成功结果，会在组件结果中写明 `not_configured` 或 `not_applicable`。
- 当前先按此前约定把进入评测流程的视频视为可读取；缺少 `video.mp4` 的 case 会标记为 `skipped_missing_video`，不计分。
- 可读取视频的普通 gate 明确失败时，总分记为最低分 `1.0`，并计入汇总的 `gate_failed`。

## 目录

- `run.py`：命令行入口。
- `v_eval/core.py`：输入解析、清单、评委、组件和计分逻辑。
- `configs/dims_13_18.yaml`：六个维度的 facts、gates、subpoints、组件权重。
- `configs/task_d13_example.yaml` 至 `task_d18_example.yaml`：六个可复制的任务模板。
- `docs/dimensions_13_18.md`：六个维度的定义与评分流程。
- `outputs/`：默认结果目录。

## 输入布局

每个任务的 `input.root` 下直接放 case 目录。默认读取：

```text
<input.root>/
  case_001/
    prompt_final.txt
    video.mp4
```

模式可以是 `t2va`、`f2va`、`l2va`、`fl2va` 或 `r2va`。

`f2va` 读取 `input_01` 作为首帧，`l2va` 读取 `input_02` 作为尾帧，`fl2va` 同时读取两者。`r2va` 按 prompt 中的引用编号读取 `input_01`、`input_02` 等图片，并可按配置读取 `ref_video_01` 和 `ref_audio_01`。

## 手动运行

在 `D:\git\kwkj-lt\v_eval` 中执行：

```powershell
python .\run.py --task-config .\configs\task_d13_example.yaml
```

只评估两个 case 时，在任务 YAML 中填写：

```yaml
case_ids:
  - case_001
  - case_002
```

只运行某个阶段时，例如只检查输入：

```powershell
python .\run.py --task-config .\configs\task_d13_example.yaml --stages check
```

强制忽略已有结果缓存：

```powershell
python .\run.py --task-config .\configs\task_d13_example.yaml --force
```

## 结果结构

```text
outputs/d13/runs/local_d13/
  13_style_visual_control/case_001/
    facts.json
    checklist.json
    answers.json
    result.json
  per_case.jsonl
  summary.json
  summary.md
```

`facts.json` 保存需求事实，`checklist.json` 保存冻结的 `gates` 和 `items`，`answers.json` 保存评委回答，`result.json` 保存子项与总分。重复执行时会复用成功的 `result.json`，使用 `--force` 才会重算。

## 计分规则

每个 checklist 子项按有效回答的加权正确率映射到 1–5 分：

- 1.00：5 分
- 0.80–<1.00：4 分
- 0.60–<0.80：3 分
- 0.30–<0.60：2 分
- <0.30：1 分

未回答默认不进入分母。核心题失败时，子项最高为 2 分。适用子项的分数取平均作为维度分数。组件缺失、错误或不适用时，不会直接按 0 分压低结果；只有成功得到分数的启用组件参与该子项的权重归一化。

普通 gate 不是质量题，而是可评估性门槛。明确失败时，所有适用子项记为 `1.0`，case 状态为 `gate_failed`，但仍进入均值。缺视频的 case 是 `skipped_missing_video`，不进入均值。

## 组件触发顺序

一个数值组件需要同时满足：

1. 所属子项的 `applies` 条件成立。
2. 普通 gate 通过。
3. 任务配置没有把它设为 `false`。
4. 组件输入存在，且实现依赖可用。
5. 组件没有可复用的成功缓存，或本次使用 `--force`。

D14 的 ArcFace、续写 LPIPS 和首尾帧端点组件按条件纳入评估；D15–D18 的组件按照耗时策略和需求事实分别配置为全局开启或关闭，并由程序逐条 case 自动判断是否适用。关闭组件不会进入子项权重分母。

## 远端评委接口

默认是离线模式。若已有 OpenAI 兼容裁判服务，可在 PowerShell 中设置：

```powershell
$env:V_EVAL_VISION_JUDGE_URL = 'http://127.0.0.1:8011/v1'
$env:V_EVAL_VISION_JUDGE_MODEL = 'Qwen3-VL-32B-Instruct'
$env:V_EVAL_AUDIO_JUDGE_URL = 'http://127.0.0.1:8012/v1'
$env:V_EVAL_AUDIO_JUDGE_MODEL = 'Qwen2.5-Omni-7B'
python .\run.py --task-config .\configs\task_d13_example.yaml
```

维度对应关系：

- 视觉裁判：D13、D14、D17、D18。
- 音频裁判：D15、D16。

当前本机只有 2GB 显存，因此这两个裁判模型应在具备足够显存的本地机器或局域网机器上启动；本评测程序只负责通过 HTTP 调用它们。

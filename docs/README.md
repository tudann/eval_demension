# D13–D18 本地评测框架

本项目覆盖第 13 至第 18 维度。现在每个维度只需要一份任务配置；同一配置可依次加载 `t2va`、`f2va`、`l2va`、`fl2va` 和 `r2va` 五种输入，五种模式共用该维度的评测、计分和汇总流程。

```text
五类 case 输入
  -> facts：从 prompt 提取结构化需求事实
  -> checklist：生成 gates 和 items
  -> judge：视觉/音频评委回答 gates 和 items
  -> 数值组件：满足适用条件且已启用时执行
  -> result.json：单 case 结果
  -> summary.json / summary.md：总体及分模式汇总
```

## 当前本地实现边界

- 默认使用 `offline` 评委模式生成可复核的占位回答。
- 视觉与音频裁判可分别通过 `V_EVAL_VISION_JUDGE_URL` 和 `V_EVAL_AUDIO_JUDGE_URL` 接入 OpenAI 兼容服务。
- 未安装或未实现的数值模型不会伪装为成功，会记录为 `not_configured`、`not_applicable` 或 `missing_input`。
- 缺少待评视频的 case 标记为 `skipped_missing_video`，不计分。
- 可读取视频的普通 gate 明确失败时，总分记为最低分 `1.0`，并计入均值和 `gate_failed` 数量。

任务配置按维度维护，一份配置可以列出五种 `mode`。某个模式当前没有 case 时，可以保留该输入块并设置 `allow_missing_root: true`，缺失目录会被跳过；case 文件夹准备好后无需新增配置文件。当前六份示例任务配置已统一使用 `data/feishu_video_cases/<mode>` 作为输入根目录，后续也可以将这些 `root` 改成其他数据集目录。


- `configs/task_d13_example.yaml`：第 13 维度，五种输入模式。
- `configs/task_d14_example.yaml`：第 14 维度，五种输入模式。
- `configs/task_d15_example.yaml`：第 15 维度，五种输入模式。
- `configs/task_d16_example.yaml`：第 16 维度，五种输入模式。
- `configs/task_d17_example.yaml`：第 17 维度，五种输入模式。
- `configs/task_d18_example.yaml`：第 18 维度，五种输入模式。
- `configs/dims_13_18.yaml`：六个维度固定的子项、适用条件、组件权重和评分规则。

任务文件中的 `inputs` 是输入任务列表。每项必须有唯一 `id`，结果会按该 `id` 隔离，避免不同模式中同名 case 相互覆盖：

```yaml
dimension: 13_style_visual_control
inputs:
  - id: t2va
    root: ./data/feishu_video_cases/t2va
    mode: t2va
    allow_missing_root: true
    prompt_filename: prompt_final.txt
    video_filename: video.mp4
    case_ids: []

  - id: fl2va
    root: ./data/feishu_video_cases/fl2va
    mode: fl2va
    allow_missing_root: true
    prompt_filename: prompt_final.txt
    video_filename: video.mp4
    case_ids: []
    references:
      first_frame_filename: input_01
      last_frame_filename: input_02
```

`case_ids: []` 表示读取该模式根目录下的全部直接子目录。只测试指定 case 时填写：

```yaml
case_ids:
  - case_001
  - case_002
```

旧版单输入配置 `input:` 仍然兼容，但新任务应使用 `inputs:`，从而在一份维度配置中覆盖五种模式。

## 五种输入模式

每个 `root` 下的直接子目录是一条 case，至少包含配置指定的提示词和待评视频：

```text
<root>/
  case_001/
    prompt_final.txt
    video.mp4
```

不同模式额外读取的内容如下：

- `t2va`：只读取提示词与待评视频。
- `f2va`：另读取首帧，模板默认名为 `input_01`。
- `l2va`：另读取尾帧，模板默认名为 `input_01`。
- `fl2va`：另读取首帧 `input_01` 和尾帧 `input_02`。
- `r2va`：按模板读取 `input_01`、`ref_video_01`、`ref_audio_01` 等编号参考素材。

参考图片可使用 `.png`、`.jpg`、`.jpeg`、`.webp`；参考视频和音频支持代码中声明的常见格式。文件名和编号模式都可以在每个 `inputs[].references` 中修改。

加载器不会打开 case 目录中的 `metadata.json`、其他提示词或未配置的普通文件。它只检查配置指定的提示词、视频和该模式允许的参考素材路径。

## 运行

首次运行先创建虚拟环境并安装基础依赖：

```bash
cd /home/ubuntu/lt-self/V-eval/eval_demension
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

在项目目录执行某一个维度的任务。例如运行第 13 维度的五种模式：

```bash
cd /home/ubuntu/lt-self/V-eval/eval_demension
.venv/bin/python run.py --task-config configs/task_d13_example.yaml
```

其他维度只需替换任务文件名：

```bash
.venv/bin/python run.py --task-config configs/task_d14_example.yaml
.venv/bin/python run.py --task-config configs/task_d15_example.yaml
```

只检查配置和输入发现，不进行评估：

```bash
.venv/bin/python run.py --task-config configs/task_d13_example.yaml --stages check
```

忽略已有结果缓存并重新计算：

```bash
.venv/bin/python run.py --task-config configs/task_d13_example.yaml --force
```

## 结果结构

多模式任务会在维度目录下增加输入 `id` 这一层：

```text
outputs/d13/runs/local_d13/
  13_style_visual_control/
    t2va/
      case_001/
        facts.json
        checklist.json
        answers.json
        result.json
    f2va/
      case_001/
        ...
    l2va/
      ...
    fl2va/
      ...
    r2va/
      ...
  per_case.jsonl
  summary.json
  summary.md
```

`summary.json` 包含整体统计和 `per_mode` 分模式统计。`summary.md` 同时展示总体均分与各模式均分。

## 裁判服务

视觉裁判负责 D13、D14、D17、D18；音频裁判负责 D15、D16。服务可以是本地部署，也可以是 OpenAI 兼容的外部 API。API 密钥只通过环境变量传入，不要写入 YAML、代码或 Git：

```bash
export V_EVAL_VISION_JUDGE_URL=http://127.0.0.1:8011/v1
export V_EVAL_VISION_JUDGE_MODEL=Qwen3-VL-32B-Instruct
export V_EVAL_VISION_JUDGE_API_KEY="$YOUR_API_KEY"
export V_EVAL_AUDIO_JUDGE_URL=http://127.0.0.1:8012/v1
export V_EVAL_AUDIO_JUDGE_MODEL=Qwen2.5-Omni-7B
export V_EVAL_AUDIO_JUDGE_API_KEY="$YOUR_API_KEY"
.venv/bin/python run.py --task-config configs/task_d13_example.yaml
```

也可以把两个 URL 和模型变量都指向同一个外部服务；当前 `JudgeClient` 会为每个请求发送 `Authorization: Bearer <key>`。支持的密钥变量优先级为模态专用的 `V_EVAL_VISION_JUDGE_API_KEY` / `V_EVAL_AUDIO_JUDGE_API_KEY`，其次是 `V_EVAL_JUDGE_API_KEY`、`V_EVAL_API_KEY` 和 `OPENAI_API_KEY`。

当前评测框架只把提示词、case 元数据和本地文件路径发送给评委服务，不会自动上传本地视频或图片。外部模型因此可以先验证 checklist JSON 和调用链；要得到真实的视频质量判断，还需要后续增加视频/图片的多模态上传或可访问 URL 适配。

任务配置只负责选择输入和启停数值组件。裁判模型服务需要单独部署或提供外部 API。

# 模型与裁判服务状态

## 裁判模型

当前评测程序已经支持两个独立的 OpenAI 兼容裁判服务：

|服务|模型|负责维度|建议地址变量|
|---|---|---|---|
|视觉裁判|Qwen3-VL-32B-Instruct|D13、D14、D17、D18|`V_EVAL_VISION_JUDGE_URL`|
|音频裁判|Qwen2.5-Omni-7B|D15、D16|`V_EVAL_AUDIO_JUDGE_URL`|

对应模型变量：

```powershell
$env:V_EVAL_VISION_JUDGE_MODEL = 'Qwen3-VL-32B-Instruct'
$env:V_EVAL_AUDIO_JUDGE_MODEL = 'Qwen2.5-Omni-7B'
```

对应服务地址示例：

```powershell
$env:V_EVAL_VISION_JUDGE_URL = 'http://127.0.0.1:8011/v1'
$env:V_EVAL_AUDIO_JUDGE_URL = 'http://127.0.0.1:8012/v1'
```

当前本机检测到的显卡是 NVIDIA GeForce MX350，显存约 2GB。这个硬件不适合直接运行 32B 或 7B 量级的裁判模型，因此本项目只负责调用服务，不在当前电脑上启动这两个裁判模型。

## 当前本机运行环境

目前系统 Python 为 3.11。项目运行需要的基础 YAML 和 Pillow 已可用；以下模型运行依赖目前未安装：

- PyTorch
- Transformers
- Hugging Face Hub 主运行环境
- librosa / soundfile
- ONNX Runtime
- InsightFace
- OpenCV
- LPIPS
- PySceneDetect

模型下载工具已单独放在：

```text
D:\git\kwkj-lt\v_eval\.runtime
```

它用于查询或下载模型，不代表模型推理依赖已经安装。

## 可下载验证的轻量模型

在 D 盘约 32GB 可用空间、当前显卡只有 2GB 的条件下，优先考虑以下模型：

|模型|可覆盖组件|建议|
|---|---|---|
|`openai/clip-vit-base-patch32`|风格或图像相似度代理|可以下载验证，但不能等同原方案的 CLIP ViT-L/14|
|`laion/clap-htsat-unfused`|D15 环境音、动作音效、配乐相似度|可以下载验证，推理可能需要 CPU|
|`MIT/ast-finetuned-audioset-10-10-0.4593`|音频事件/音乐存在性代理|可以下载验证|
|`speechbrain/spkrec-ecapa-voxceleb`|D15 音色一致性|可以下载验证，但还需要 SpeechBrain 和音频依赖|
|`PaddlePaddle/PP-OCRv5_server_rec`|D18 OCR 识别|可以下载验证，但还需要 Paddle 推理运行时和检测模型|

这些模型不能直接替代原方案中的所有模型：

- CLIP Base 不能等同 CSD 使用的 ViT-L/14 风格模型。
- AST 不能等同 PANNs Cnn14，只能作为音频事件分类替代或预验证。
- PP-OCRv5 识别模型还需要配套检测模型。
- ECAPA 只提供说话人特征能力，不负责完整的 VAD、分段和评分流程。

## 暂不建议在当前电脑下载或运行

- Qwen3-VL-32B-Instruct。
- Qwen2.5-Omni-7B。
- GroundingDINO Swin-B。
- VMBench 相关模型。
- RTMDet + RTMPose 全套权重。
- FIRM-Video-8B。
- Whisper large-v3。

原因是显存不足、模型或依赖体积较大，或者当前 D 盘空间不适合连续下载多套权重。裁判模型应该部署在另一台有足够显存的本地机器或局域网机器上。

## 结论

当前已经完成：

1. 视觉和音频两个裁判服务的独立配置接口。
2. 两个裁判模型与 D13–D18 维度的服务映射。
3. 轻量模型仓库的可访问性验证。
4. 模型下载和运行依赖边界说明。

后续可以在 D 盘建立单独模型目录，逐个下载并验证轻量组件；不要把裁判大模型下载到这台 MX350 电脑上。
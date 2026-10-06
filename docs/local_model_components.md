# 已接入的本地数值组件

`v_eval/model_components.py` 提供 D13-D18 的懒加载适配层。模型目录默认是：

```text
/home/ubuntu/lt-self/V-eval/eval_demension/models
```

也可以通过环境变量覆盖：

```bash
export V_EVAL_MODEL_DIR=/path/to/models
```

当前接入关系：

- D13：CLIP ViT-L/14 -> `csd_ref_similarity`、`csd_temporal_drift`
- D14：PSNR -> `endpoint_psnr`；LPIPS -> `endpoint_lpips`、`continuation_seam_lpips`；InsightFace buffalo_l -> `arcface_identity_keep`
- D15：DNSMOS -> `dnsmos_ovr`；ECAPA -> `ecapa_same_speaker`；emotion2vec+ large -> `emotion2vec_match`；CLAP -> `clap_ambient`、`clap_sfx`、`clap_music`；PANNs -> `music_presence`
- D16：Silero VAD + InsightFace 预筛窗口 -> 外部真实 SyncNet v2 适配器 -> `syncnet_conf`；未配置时安全回退 checklist
- D17：`vlm_anomaly_rate` 仍属于视觉评委服务，不在本地模型适配层重复加载
- D18：PP-OCRv5 检测和识别 -> `ocr_cer`、`ocr_subtitle_alignment`、`ocr_readability`、`ocr_text_stability`

安装本地模型运行依赖：

```bash
cd /home/ubuntu/lt-self/V-eval/eval_demension
.venv/bin/python -m pip install -r requirements-models.txt
```

PaddlePaddle 需要根据主机 CPU/CUDA 版本按官方安装命令单独选择。模型适配层不会在导入评估框架时加载重量模型；只有某个 case 的对应子项适用且开关为真时才加载，并在同一进程内复用缓存。

每个组件都会写入明确状态：

- `ok`：模型推理或公式计算成功并产生 1–5 分；
- `not_applicable`：该 case 不满足子项适用条件；
- `missing_input`：所需视频、音频、参考素材或帧不可用；
- `not_configured`：模型运行依赖或模型目录未准备好；
- `error`：加载或推理发生异常。

缺失模型不会被当作满分，也不会伪造数值结果。

## D16 SyncNet v2 适配器协议

评测器本身不捆绑来源和许可证尚未确认的 SyncNet 代码或权重。配置真实本地实现时，将 `V_EVAL_SYNCNET_COMMAND` 设置为适配器命令，并可用 `V_EVAL_SYNCNET_WEIGHTS` 指定权重：

```bash
export V_EVAL_SYNCNET_COMMAND='python3 /path/to/syncnet_adapter.py'
export V_EVAL_SYNCNET_WEIGHTS='/path/to/syncnet_v2.model'
```

评测器通过标准输入发送一个 JSON 对象，其中包含 `protocol_version`、原视频路径、16 kHz 音轨路径、经过 Silero VAD 与 InsightFace 筛选的 `windows`，以及可选的权重路径。适配器必须在标准输出只返回一个 JSON 对象，例如：

```json
{
  "status": "ok",
  "confidence": 6.3,
  "offset_ms": -40,
  "windows": [
    {"start": 1.2, "end": 3.2, "confidence": 6.1, "offset_ms": -40}
  ]
}
```

也可以只在 `windows` 中返回每窗结果，评测器会对有限值取平均。置信度按 7.0、5.5、4.0、2.5 映射为 5–1 分，偏移量保留为诊断数据。适配器没有配置时组件状态为 `not_configured`，口型子项只保留 checklist 分数。

资源边界可通过 `V_EVAL_SYNCNET_MAX_WINDOWS`、`V_EVAL_SYNCNET_MAX_TOTAL_SECONDS`、`V_EVAL_SYNCNET_WINDOW_SECONDS` 和 `V_EVAL_SYNCNET_TIMEOUT` 调整。默认最多 4 窗、总计 12 秒、每窗 2 秒。

## LPIPS 和 InsightFace 的额外说明

LPIPS 需要两部分：`models/lpips/alex.pth` 校准文件，以及 Torchvision AlexNet 主干权重。下载脚本已增加后者，路径为 `models/hub/checkpoints/alexnet-owt-7be5be79.pth`。

InsightFace 官方压缩包中的 ONNX 文件直接位于压缩包根目录。下载脚本的新版本会整理到 `models/insightface/buffalo_l/`；旧下载结果仍可由运行时适配层从 `buffalo_l.zip` 自动整理。

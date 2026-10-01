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
- D16：当前没有打开的独立数值模型，继续使用 checklist
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

## LPIPS 和 InsightFace 的额外说明

LPIPS 需要两部分：`models/lpips/alex.pth` 校准文件，以及 Torchvision AlexNet 主干权重。下载脚本已增加后者，路径为 `models/hub/checkpoints/alexnet-owt-7be5be79.pth`。

InsightFace 官方压缩包中的 ONNX 文件直接位于压缩包根目录。下载脚本的新版本会整理到 `models/insightface/buffalo_l/`；旧下载结果仍可由运行时适配层从 `buffalo_l.zip` 自动整理。

# 本地出题与裁判服务

- 出题及视觉裁判：已有 Qwen3-VL-32B-Instruct-FP8 权重，服务 127.0.0.1:8011，GPU 3。
- 音频及音视频裁判：Qwen2.5-Omni-7B，下载到本目录 models/，服务 127.0.0.1:8012，默认也在 GPU 3。
- 使用项目自己的 `.runtime/serving-venv` 运行 vLLM-Omni 0.30.0；不依赖 `/opt/sglang`。
- 端口仅监听本机。内存配额分别为 0.55 与 0.35；长视频或高并发需再做压力测试。

准备：

    bash serving/download_omni.sh
    bash serving/install_runtime.sh

启动（前台运行便于观察日志；用两个终端分别执行）：

    bash serving/start_vision.sh
    bash serving/start_omni.sh

后台启动与状态：

    bash serving/start_services.sh
    bash serving/status.sh

如仅需出题和视觉，可只启动 `start_vision.sh`。如果 GPU 3 显存不足，先调整 `config.env` 中的显存配额、上下文长度或将 Omni 指向空闲 GPU。不要停止其他人的服务。

项目 `.env` 使用 `V_EVAL_CHECKLIST_*` 指向 8011、`V_EVAL_VISION_JUDGE_*` 指向 8011，`V_EVAL_AUDIO_JUDGE_*` 指向 8012。音频消息设置 `V_EVAL_AUDIO_CONTENT_FORMAT=audio_url`，与 vLLM-Omni 示例一致。运行评测前以实际短音频和音视频案例验证模型返回的 JSON 清单与评分。

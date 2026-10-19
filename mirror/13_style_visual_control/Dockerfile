# Dimension 13 evaluator. The vision judge stays outside this image.
# Build context is the staged directory produced by stage_context.sh.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    V_EVAL_MODEL_DIR=/opt/d13-eval/models \
    V_EVAL_CLIP_DEVICE=cuda:0 \
    V_EVAL_CHECKLIST_MODEL=Qwen3-VL-32B-Instruct-FP8 \
    V_EVAL_VISION_JUDGE_MODEL=Qwen3-VL-32B-Instruct-FP8

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-d13.txt /tmp/requirements-d13.txt
RUN python3 -m venv /opt/d13-eval/.venv \
    && /opt/d13-eval/.venv/bin/pip install --no-cache-dir -r /tmp/requirements-d13.txt \
    && /opt/d13-eval/.venv/bin/pip install --no-cache-dir torch==2.14.1 torchvision==0.29.1 \
        --index-url https://download.pytorch.org/whl/cu130 \
    && rm -rf /root/.cache/pip

WORKDIR /opt/d13-eval
COPY run.py /opt/d13-eval/run.py
COPY v_eval /opt/d13-eval/v_eval
COPY configs /opt/d13-eval/configs
COPY models /opt/d13-eval/models
COPY entrypoint.sh /opt/d13-eval/entrypoint.sh
RUN chmod +x /opt/d13-eval/entrypoint.sh

ENTRYPOINT ["/opt/d13-eval/entrypoint.sh"]
CMD ["--task-config", "/opt/d13-eval/configs/task_d13_container.yaml"]

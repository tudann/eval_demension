#!/usr/bin/env python3
"""下载 D13-D18 当前启用的辅助模型权重。

本脚本只下载并保存模型文件，不安装 Python 依赖，也不执行模型加载、推理或评估。
适合在 tmux 中长时间运行。Hugging Face 模型使用 huggingface_hub 下载；
DNSMOS、LPIPS、PANNs 和 InsightFace 使用官方或项目公开的权重地址下载。

示例：
    python download_aux_models.py
    python download_aux_models.py --output-dir /data/v-eval-models
    python download_aux_models.py --only clap,dnsmos
    python download_aux_models.py --list

如需访问受限的 Hugging Face 仓库，请预先设置 HF_TOKEN，或使用 huggingface-cli
登录。不要把 token 写入本文件或命令行历史。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "models"
MANIFEST_NAME = "download_manifest.json"


@dataclass(frozen=True)
class HuggingFaceModel:
    key: str
    label: str
    repo_id: str
    directory: str
    allow_patterns: tuple[str, ...]
    purpose: str


@dataclass(frozen=True)
class DirectFile:
    key: str
    label: str
    url: str
    relative_path: str
    purpose: str
    md5: str | None = None
    sha256: str | None = None


# 这里只列当前任务配置中打开、且排除了两个评委模型后的模型。
# PSNR 是公式计算，不需要下载权重；LPIPS 只下载 AlexNet 权重。
HF_MODELS: tuple[HuggingFaceModel, ...] = (
    HuggingFaceModel(
        key="clip_vit_large_patch14",
        label="CLIP ViT-L/14（CSD 骨干候选）",
        repo_id="openai/clip-vit-large-patch14",
        directory="clip-vit-large-patch14",
        allow_patterns=(
            "*.json",
            "*.txt",
            "*.model",
            "*.safetensors",
            "*.bin",
            "*.py",
        ),
        purpose="D13 CSD 风格相似度和时序漂移的图像编码骨干；仍需后续实现 CSD 适配。",
    ),
    HuggingFaceModel(
        key="clap",
        label="CLAP htsat-unfused",
        repo_id="laion/clap-htsat-unfused",
        directory="clap-htsat-unfused",
        allow_patterns=(
            "*.json",
            "*.txt",
            "*.yaml",
            "*.yml",
            "*.pt",
            "*.bin",
            "*.safetensors",
            "*.py",
        ),
        purpose="D15 环境音、动作音效和配乐文本-音频匹配。",
    ),
    HuggingFaceModel(
        key="ecapa",
        label="SpeechBrain ECAPA-TDNN VoxCeleb",
        repo_id="speechbrain/spkrec-ecapa-voxceleb",
        directory="spkrec-ecapa-voxceleb",
        allow_patterns=(
            "*.json",
            "*.txt",
            "*.yaml",
            "*.yml",
            "*.ckpt",
            "*.pth",
            "*.pt",
            "*.bin",
            "*.py",
        ),
        purpose="D15 音色和说话人一致性。",
    ),
    HuggingFaceModel(
        key="emotion2vec",
        label="emotion2vec+ large",
        repo_id="emotion2vec/emotion2vec_plus_large",
        directory="emotion2vec_plus_large",
        allow_patterns=(
            "*.json",
            "*.txt",
            "*.yaml",
            "*.yml",
            "*.pt",
            "*.pth",
            "*.bin",
            "*.safetensors",
            "*.py",
        ),
        purpose="D15 对白情绪匹配；后续需要 FunASR/emotion2vec 适配。",
    ),
    HuggingFaceModel(
        key="ppocr_det",
        label="PP-OCRv5 server detection",
        repo_id="PaddlePaddle/PP-OCRv5_server_det",
        directory="PP-OCRv5_server_det",
        allow_patterns=(
            "*.json",
            "*.txt",
            "*.yml",
            "*.yaml",
            "*.pdmodel",
            "*.pdiparams",
            "*.pdiparams.info",
            "*.py",
        ),
        purpose="D18 画面文字检测；需要 PaddleOCR/PaddlePaddle 运行时才能调用。",
    ),
    HuggingFaceModel(
        key="ppocr_rec",
        label="PP-OCRv5 server recognition",
        repo_id="PaddlePaddle/PP-OCRv5_server_rec",
        directory="PP-OCRv5_server_rec",
        allow_patterns=(
            "*.json",
            "*.txt",
            "*.yml",
            "*.yaml",
            "*.pdmodel",
            "*.pdiparams",
            "*.pdiparams.info",
            "*.py",
        ),
        purpose="D18 画面文字识别；需要和检测模型配套使用。",
    ),
)

DIRECT_FILES: tuple[DirectFile, ...] = (
    DirectFile(
        key="lpips",
        label="LPIPS AlexNet 权重",
        url=(
            "https://raw.githubusercontent.com/richzhang/PerceptualSimilarity/"
            "master/lpips/weights/v0.1/alex.pth"
        ),
        relative_path="lpips/alex.pth",
        purpose="D14 续写接缝和首尾帧感知差异。",
    ),
    DirectFile(
        key="lpips",
        label="Torchvision AlexNet backbone 权重",
        url="https://download.pytorch.org/models/alexnet-owt-7be5be79.pth",
        relative_path="hub/checkpoints/alexnet-owt-7be5be79.pth",
        purpose="LPIPS AlexNet 的主干权重；与 lpips/alex.pth 校准权重配套。",
    ),
    DirectFile(
        key="dnsmos",
        label="DNSMOS model_v8",
        url=(
            "https://raw.githubusercontent.com/microsoft/DNS-Challenge/"
            "master/DNSMOS/DNSMOS/model_v8.onnx"
        ),
        relative_path="dnsmos/model_v8.onnx",
        purpose="D15 语音自然度 OVRL。",
    ),
    DirectFile(
        key="dnsmos",
        label="DNSMOS sig_bak_ovr",
        url=(
            "https://raw.githubusercontent.com/microsoft/DNS-Challenge/"
            "master/DNSMOS/DNSMOS/sig_bak_ovr.onnx"
        ),
        relative_path="dnsmos/sig_bak_ovr.onnx",
        purpose="D15 DNSMOS 的配套信号质量模型。",
    ),
    DirectFile(
        key="panns",
        label="PANNs Cnn14",
        url="https://zenodo.org/records/3987831/files/Cnn14_mAP=0.431.pth?download=1",
        relative_path="panns/Cnn14_mAP=0.431.pth",
        purpose="D15 配乐存在性；使用官方 Zenodo 权重。",
        md5="541141fa2ee191a88f24a3219fff024e",
    ),
    DirectFile(
        key="insightface",
        label="InsightFace buffalo_l",
        url="https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        relative_path="insightface/buffalo_l.zip",
        purpose="D14 主体替换身份一致性；下载后会自动解压到同目录。",
    ),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"模型保存目录，默认：{DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--only",
        help="只下载指定组件，逗号分隔，例如：clap,dnsmos；默认下载全部。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="忽略已有目标文件并重新下载；默认会复用已有文件。",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="某个组件失败后继续下载其他组件；默认遇到错误立即退出。",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="只列出下载清单，不连接网络。",
    )
    return parser.parse_args()


def all_keys() -> list[str]:
    return [model.key for model in HF_MODELS] + sorted({item.key for item in DIRECT_FILES})


def selected_keys(value: str | None) -> set[str]:
    if not value:
        return set(all_keys())
    requested = {part.strip() for part in value.split(",") if part.strip()}
    known = set(all_keys())
    unknown = sorted(requested - known)
    if unknown:
        raise SystemExit(f"未知组件：{', '.join(unknown)}；可选值：{', '.join(sorted(known))}")
    return requested


def print_catalog() -> None:
    print("当前下载清单：")
    for model in HF_MODELS:
        print(f"  {model.key:22s} Hugging Face  {model.repo_id}  — {model.purpose}")
    for item in DIRECT_FILES:
        print(f"  {item.key:22s} 直链          {item.relative_path}  — {item.purpose}")
    print("\n不会下载：PSNR 权重、FIRM、关闭的 SyncNet/Synchformer、VMBench、DINO、")
    print("GroundingDINO、Whisper、RTMDet/RTMPose，以及两个评委模型。")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, item: DirectFile) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if item.md5 and md5_file(path) != item.md5:
        return False
    if item.sha256 and sha256_file(path) != item.sha256:
        return False
    return True


def download_url(item: DirectFile, destination: Path, force: bool) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not force and verify_file(destination, item):
        print(f"[跳过] {item.label}：文件已存在且校验通过 -> {destination}")
        return "skipped"

    part = destination.with_name(destination.name + ".part")
    for attempt in range(1, 4):
        resume_from = part.stat().st_size if part.exists() else 0
        headers = {"User-Agent": "lt-self-model-downloader/1.0", "Accept-Encoding": "identity"}
        if resume_from:
            headers["Range"] = f"bytes={resume_from}-"
        request = urllib.request.Request(item.url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                status = getattr(response, "status", response.getcode())
                if resume_from and status != 206:
                    resume_from = 0
                    part.unlink(missing_ok=True)
                mode = "ab" if resume_from else "wb"
                content_length = response.headers.get("Content-Length")
                total = (int(content_length) + resume_from) if content_length else None
                downloaded = resume_from
                last_report = 0.0
                print(f"[下载] {item.label} -> {destination}")
                with part.open(mode) as stream:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        stream.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if now - last_report >= 2.0:
                            if total:
                                percent = downloaded * 100 / total
                                print(f"         {downloaded / 1024**2:.1f}/{total / 1024**2:.1f} MiB ({percent:.1f}%)")
                            else:
                                print(f"         {downloaded / 1024**2:.1f} MiB")
                            last_report = now
                if not verify_file(part, item):
                    part.unlink(missing_ok=True)
                    raise RuntimeError(f"下载完成但校验失败：{part}")
                os.replace(part, destination)
                print(f"[完成] {item.label} ({destination.stat().st_size / 1024**2:.1f} MiB)")
                return "downloaded"
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            print(f"[重试 {attempt}/3] {item.label}：{exc}", file=sys.stderr)
            if attempt == 3:
                raise
            time.sleep(2 * attempt)
    raise AssertionError("unreachable")


def download_huggingface(model: HuggingFaceModel, output_dir: Path, force: bool) -> str:
    endpoint = os.environ.get("HF_ENDPOINT")
    if endpoint:
        # huggingface_hub 通过 HF_ENDPOINT 读取镜像设置；这里保留环境变量，
        # 不把任何站点或 token 写死在脚本中。
        os.environ["HF_ENDPOINT"] = endpoint
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "缺少 huggingface_hub。请先在运行下载的环境中安装："
            "python -m pip install -U huggingface_hub"
        ) from exc

    target = output_dir / model.directory
    marker = target / ".download_complete"
    if marker.exists() and not force:
        print(f"[跳过] {model.label}：已存在完成标记 -> {target}")
        return "skipped"

    target.mkdir(parents=True, exist_ok=True)
    token = os.environ.get("HF_TOKEN") or None
    endpoint = os.environ.get("HF_ENDPOINT")
    kwargs = {
        "repo_id": model.repo_id,
        "revision": "main",
        "local_dir": str(target),
        "allow_patterns": list(model.allow_patterns),
        "token": token,
    }
    if endpoint:
        # huggingface_hub 通过 HF_ENDPOINT 读取镜像设置；这里保留环境变量，
        # 不把任何站点或 token 写死在脚本中。
        os.environ["HF_ENDPOINT"] = endpoint
    print(f"[下载] {model.label}：{model.repo_id} -> {target}")
    snapshot_download(**kwargs)
    marker.write_text(f"completed_at={utc_now()}\nrepo={model.repo_id}\n", encoding="utf-8")
    print(f"[完成] {model.label} -> {target}")
    return "downloaded"


def extract_insightface_zip(output_dir: Path, force: bool) -> None:
    archive = output_dir / "insightface" / "buffalo_l.zip"
    extracted = output_dir / "insightface" / "buffalo_l"
    if not archive.exists():
        return
    if extracted.exists() and not force:
        return
    print(f"[解压] InsightFace buffalo_l -> {extracted}")
    extracted.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extracted)
    # 官方压缩包文件直接位于根目录，统一整理为 buffalo_l/ 模型包目录。
    if not any(extracted.glob("*.onnx")):
        raise RuntimeError(f"InsightFace 压缩包已下载，但未找到 ONNX 权重：{extracted}")


def write_manifest(output_dir: Path, selected: Iterable[str], statuses: dict[str, str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": utc_now(),
        "script": str(Path(__file__).resolve()),
        "download_only": True,
        "selected": sorted(selected),
        "statuses": statuses,
        "hf_models": [model.__dict__ for model in HF_MODELS if model.key in selected],
        "direct_files": [item.__dict__ for item in DIRECT_FILES if item.key in selected],
    }
    (output_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.list:
        print_catalog()
        return 0

    selected = selected_keys(args.only)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    statuses: dict[str, str] = {}
    failures: list[str] = []

    print(f"模型保存目录：{output_dir}")
    print("本次仅下载文件，不安装依赖、不加载模型、不执行推理或评估。")
    print("如果网络中断，重新执行同一命令会复用已完成文件，并尝试续传 .part 文件。\n")

    for model in HF_MODELS:
        if model.key not in selected:
            continue
        try:
            statuses[model.key] = download_huggingface(model, output_dir, args.force)
        except Exception as exc:  # noqa: BLE001 - 下载器需要把组件错误报告给用户
            statuses[model.key] = "failed"
            failures.append(f"{model.key}: {exc}")
            print(f"[失败] {model.label}：{exc}", file=sys.stderr)
            if not args.continue_on_error:
                write_manifest(output_dir, selected, statuses)
                return 1

    for item in DIRECT_FILES:
        if item.key not in selected:
            continue
        try:
            statuses[item.key] = download_url(item, output_dir / item.relative_path, args.force)
            if item.key == "insightface":
                extract_insightface_zip(output_dir, args.force)
        except Exception as exc:  # noqa: BLE001 - 下载器需要把组件错误报告给用户
            statuses[item.key] = "failed"
            failures.append(f"{item.key} ({item.label}): {exc}")
            print(f"[失败] {item.label}：{exc}", file=sys.stderr)
            if not args.continue_on_error:
                write_manifest(output_dir, selected, statuses)
                return 1

    write_manifest(output_dir, selected, statuses)
    if failures:
        print("\n下载结束，但有组件失败：", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(f"已写入清单：{output_dir / MANIFEST_NAME}", file=sys.stderr)
        return 1

    print(f"\n全部选定组件已处理。下载清单：{output_dir / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

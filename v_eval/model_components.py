from __future__ import annotations

"""Local adapters for the enabled D13-D18 numeric components.

The adapters are deliberately lazy and optional: importing the evaluator does not
require every heavyweight runtime. Each component returns a structured result with
status ``ok``, ``not_configured``, ``not_applicable``, ``missing_input`` or
``error``. Models are loaded once per evaluator process and reused across cases.
"""

import difflib
import json
import math
import os
import re
import shlex
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = ROOT / "models"


_CACHE: dict[str, Any] = {}


def model_dir() -> Path:
    return Path(os.getenv("V_EVAL_MODEL_DIR", str(DEFAULT_MODEL_DIR))).expanduser().resolve()


def _result(component: str, status: str, score: float | None = None, **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"component": component, "status": status, "score": score}
    value.update(extra)
    return value


def _optional_import(module: str, package: str | None = None) -> tuple[Any | None, str | None]:
    try:
        return __import__(module, fromlist=["*"]), None
    except ImportError as exc:
        return None, f"missing dependency: {package or module} ({exc})"


def _safe_float(value: Any) -> float | None:
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _clip_score(value: float, thresholds: tuple[float, float, float, float], higher: bool = True) -> float:
    if higher:
        return 5.0 if value >= thresholds[0] else 4.0 if value >= thresholds[1] else 3.0 if value >= thresholds[2] else 2.0 if value >= thresholds[3] else 1.0
    return 5.0 if value <= thresholds[0] else 4.0 if value <= thresholds[1] else 3.0 if value <= thresholds[2] else 2.0 if value <= thresholds[3] else 1.0


def _ffprobe_duration(path: Path) -> float | None:
    try:
        output = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            stderr=subprocess.STDOUT,
            text=True,
        )
        return _safe_float(output.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def extract_frame(video: Path | None, seconds: float = 0.0) -> Path | None:
    if not video or not video.is_file():
        return None
    cache_key = f"frame:{video}:{seconds:.4f}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    temp = Path(tempfile.mkdtemp(prefix="v_eval_frame_")) / "frame.png"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, seconds):.4f}", "-i", str(video), "-frames:v", "1", str(temp)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    if not temp.is_file() or temp.stat().st_size == 0:
        return None
    _CACHE[cache_key] = temp
    return temp


def video_frames(video: Path | None, count: int = 16) -> list[Path]:
    if not video or not video.is_file():
        return []
    duration = _ffprobe_duration(video)
    if duration is None or duration <= 0:
        frame = extract_frame(video)
        return [frame] if frame else []
    timestamps = [0.0] if count <= 1 else [duration * i / (count - 1) for i in range(count)]
    return [frame for timestamp in timestamps if (frame := extract_frame(video, timestamp)) is not None]


def extract_audio(video: Path | None, sample_rate: int = 16000) -> Path | None:
    if not video or not video.is_file():
        return None
    cache_key = f"audio:{video}:{sample_rate}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    temp = Path(tempfile.mkdtemp(prefix="v_eval_audio_")) / "audio.wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(sample_rate), str(temp)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    if not temp.is_file() or temp.stat().st_size == 0:
        return None
    _CACHE[cache_key] = temp
    return temp


def _load_clip() -> tuple[Any | None, Any | None, str | None]:
    if "clip" in _CACHE:
        return (*_CACHE["clip"], None)
    transformers, error = _optional_import("transformers", "transformers")
    if error:
        return None, None, error
    local = model_dir() / "clip-vit-large-patch14"
    if not local.is_dir():
        return None, None, f"model directory not found: {local}"
    try:
        processor = transformers.CLIPProcessor.from_pretrained(str(local), local_files_only=True)
        model = transformers.CLIPModel.from_pretrained(str(local), local_files_only=True)
        model.eval()
        _CACHE["clip"] = (processor, model)
        return processor, model, None
    except Exception as exc:  # noqa: BLE001
        return None, None, f"CLIP load failed: {exc}"


def csd_component(component: str, case: Any) -> dict[str, Any]:
    processor, model, error = _load_clip()
    if error:
        return _result(component, "not_configured", reason=error)
    frames = video_frames(case.video_path, 16)
    if not frames:
        return _result(component, "missing_input", reason="cannot extract video frames")
    references = list(case.reference_images)
    if component == "csd_ref_similarity" and not references:
        return _result(component, "not_applicable", reason="no reference image")
    if component == "csd_temporal_drift":
        references = []
    try:
        import torch
        images = [Image.open(path).convert("RGB") for path in frames]
        with torch.no_grad():
            frame_inputs = processor(images=images, return_tensors="pt")
            frame_features = model.get_image_features(**frame_inputs)
            frame_features = frame_features / frame_features.norm(dim=-1, keepdim=True)
            if references:
                ref_images = [Image.open(path).convert("RGB") for path in references]
                ref_inputs = processor(images=ref_images, return_tensors="pt")
                ref_features = model.get_image_features(**ref_inputs)
                ref_features = ref_features / ref_features.norm(dim=-1, keepdim=True)
                similarities = (frame_features @ ref_features.T).max(dim=1).values.cpu().tolist()
                value = sum(similarities) / len(similarities)
                return _result(component, "ok", _clip_score(value, (0.80, 0.65, 0.50, 0.35)), value=round(value, 6), method="clip_vit_large_patch14")
            mean = frame_features.mean(dim=0, keepdim=True)
            mean = mean / mean.norm(dim=-1, keepdim=True)
            drift = float((1.0 - (frame_features @ mean.T).squeeze(-1)).mean().item())
            return _result(component, "ok", _clip_score(drift, (0.05, 0.10, 0.18, 0.28), higher=False), value=round(drift, 6), method="clip_vit_large_patch14")
    except Exception as exc:  # noqa: BLE001
        return _result(component, "error", reason=f"CSD inference failed: {exc}")


def _load_lpips() -> tuple[Any | None, str | None]:
    if "lpips" in _CACHE:
        return _CACHE["lpips"], None
    module, error = _optional_import("lpips", "lpips")
    if error:
        return None, error
    backbone = model_dir() / "hub" / "checkpoints" / "alexnet-owt-7be5be79.pth"
    if not backbone.is_file():
        return None, f"AlexNet backbone checkpoint not found: {backbone}"
    os.environ.setdefault("TORCH_HOME", str(model_dir()))
    try:
        metric = module.LPIPS(net="alex")
        metric.eval()
        _CACHE["lpips"] = metric
        return metric, None
    except Exception as exc:  # noqa: BLE001
        return None, f"LPIPS load failed: {exc}"


def _image_tensor(path: Path) -> Any:
    import torch
    from torchvision import transforms
    image = Image.open(path).convert("RGB")
    return transforms.ToTensor()(image).unsqueeze(0) * 2.0 - 1.0


def _endpoint_pairs(case: Any) -> list[tuple[Path, Path]]:
    if not case.video_path:
        return []
    pairs: list[tuple[Path, Path]] = []
    if case.first_frame:
        generated = extract_frame(case.video_path, 0.0)
        if generated:
            pairs.append((case.first_frame, generated))
    if case.last_frame:
        duration = _ffprobe_duration(case.video_path) or 0.05
        generated = extract_frame(case.video_path, max(0.0, duration - 0.05))
        if generated:
            pairs.append((case.last_frame, generated))
    return pairs


def _endpoint_paths(case: Any, component: str) -> tuple[Path | None, Path | None]:
    if component == "continuation_seam_lpips" and case.reference_videos:
        duration = _ffprobe_duration(case.reference_videos[0]) or 0.0
        reference = extract_frame(case.reference_videos[0], max(0.0, duration - 0.05))
        target = extract_frame(case.video_path, 0.0)
        return reference, target
    pairs = _endpoint_pairs(case)
    if pairs:
        return pairs[0]
    return None, None


def lpips_component(component: str, case: Any) -> dict[str, Any]:
    metric, error = _load_lpips()
    if error:
        return _result(component, "not_configured", reason=error)
    if component == "continuation_seam_lpips":
        pairs = [_endpoint_paths(case, component)]
    else:
        pairs = _endpoint_pairs(case)
    pairs = [(reference, target) for reference, target in pairs if reference and target]
    if not pairs:
        return _result(component, "missing_input", reason="reference or generated endpoint frame unavailable")
    try:
        import torch
        with torch.no_grad():
            values = [float(metric(_image_tensor(reference), _image_tensor(target)).item()) for reference, target in pairs]
        value = sum(values) / len(values)
        return _result(component, "ok", _clip_score(value, (0.08, 0.15, 0.25, 0.40), higher=False), value=round(value, 6), pairs=len(values), method="lpips_alex")
    except Exception as exc:  # noqa: BLE001
        return _result(component, "error", reason=f"LPIPS inference failed: {exc}")


def psnr_component(case: Any) -> dict[str, Any]:
    pairs = _endpoint_pairs(case)
    if not pairs:
        return _result("endpoint_psnr", "missing_input", reason="reference or generated endpoint frame unavailable")
    try:
        import numpy as np
        values = []
        for reference, target in pairs:
            with Image.open(reference) as ref, Image.open(target) as dst:
                a = np.asarray(ref.convert("RGB").resize((256, 256)), dtype=np.float32)
                b = np.asarray(dst.convert("RGB").resize((256, 256)), dtype=np.float32)
            mse = float(np.mean((a - b) ** 2))
            values.append(99.0 if mse == 0 else 10.0 * math.log10((255.0 ** 2) / mse))
        value = sum(values) / len(values)
        return _result("endpoint_psnr", "ok", _clip_score(value, (30.0, 26.0, 22.0, 18.0)), value=round(value, 6), pairs=len(values), method="psnr")
    except Exception as exc:  # noqa: BLE001
        return _result("endpoint_psnr", "error", reason=f"PSNR calculation failed: {exc}")


def _load_insightface() -> tuple[Any | None, str | None]:
    if "insightface" in _CACHE:
        return _CACHE["insightface"], None
    module, error = _optional_import("insightface", "insightface")
    if error:
        return None, error
    flat = model_dir() / "insightface"
    pack = model_dir() / "insightface" / "buffalo_l"
    if not pack.is_dir() and (flat / "buffalo_l.zip").is_file():
        try:
            pack.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(flat / "buffalo_l.zip") as bundle:
                bundle.extractall(pack)
        except (OSError, zipfile.BadZipFile) as exc:
            return None, f"InsightFace model-pack extraction failed: {exc}"
    if not pack.is_dir():
        # The downloader currently extracts the official archive directly into
        # insightface/. FaceAnalysis can still be configured from that directory
        # after the standard model-pack directory is created by the caller.
        return None, f"InsightFace model pack directory not found: {pack}; downloaded files are in {flat}"
    try:
        app = module.app.FaceAnalysis(name="buffalo_l", root=str(model_dir()))
        ctx_id = int(os.getenv("V_EVAL_INSIGHTFACE_CTX_ID", "-1"))
        app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        _CACHE["insightface"] = app
        return app, None
    except Exception as exc:  # noqa: BLE001
        return None, f"InsightFace load failed: {exc}"


def arcface_component(case: Any) -> dict[str, Any]:
    app, error = _load_insightface()
    if error:
        return _result("arcface_identity_keep", "not_configured", reason=error)
    anchor = case.reference_images[0] if case.reference_images else case.first_frame
    frames = video_frames(case.video_path, 24)
    if not anchor or not frames:
        return _result("arcface_identity_keep", "missing_input", reason="face anchor or video frames unavailable")
    try:
        import numpy as np
        import cv2
        anchor_image = cv2.imread(str(anchor))
        anchor_faces = app.get(anchor_image) if anchor_image is not None else []
        if not anchor_faces:
            return _result("arcface_identity_keep", "not_applicable", reason="no face in anchor")
        anchor_embedding = anchor_faces[0].normed_embedding
        similarities = []
        for frame in frames:
            image = cv2.imread(str(frame))
            if image is None:
                continue
            faces = app.get(image)
            if faces:
                similarities.append(float(np.dot(anchor_embedding, faces[0].normed_embedding)))
        if not similarities:
            return _result("arcface_identity_keep", "ok", 1.0, value=0.0, reason="no face in generated video")
        similarities.sort()
        selected = similarities[len(similarities) // 2 :]
        value = sum(selected) / len(selected)
        return _result("arcface_identity_keep", "ok", _clip_score(value, (0.65, 0.55, 0.45, 0.35)), value=round(value, 6), frames=len(similarities), method="insightface_buffalo_l")
    except Exception as exc:  # noqa: BLE001
        return _result("arcface_identity_keep", "error", reason=f"ArcFace inference failed: {exc}")


def _load_clap() -> tuple[Any | None, Any | None, str | None]:
    if "clap" in _CACHE:
        return (*_CACHE["clap"], None)
    transformers, error = _optional_import("transformers", "transformers")
    if error:
        return None, None, error
    local = model_dir() / "clap-htsat-unfused"
    try:
        model = transformers.ClapModel.from_pretrained(str(local), local_files_only=True)
        processor = transformers.ClapProcessor.from_pretrained(str(local), local_files_only=True)
        model.eval()
        _CACHE["clap"] = (processor, model)
        return processor, model, None
    except Exception as exc:  # noqa: BLE001
        return None, None, f"CLAP load failed: {exc}"


def clap_component(component: str, case: Any, facts: dict[str, Any]) -> dict[str, Any]:
    processor, model, error = _load_clap()
    if error:
        return _result(component, "not_configured", reason=error)
    audio = extract_audio(case.video_path, 48000)
    if not audio:
        return _result(component, "missing_input", reason="video audio track unavailable")
    descriptions: list[str] = []
    if component == "clap_ambient" and facts.get("ambient"):
        descriptions.append(str(facts.get("ambient_description") or "the described ambient sound"))
    elif component == "clap_sfx" and facts.get("sfx"):
        descriptions.append(str(facts.get("sfx_description") or "the described action sound effect"))
    elif component == "clap_music" and facts.get("music_required"):
        descriptions.append(str(facts.get("music_description") or "the requested background music"))
    if not descriptions:
        return _result(component, "not_applicable", reason="no applicable audio description")
    try:
        import librosa
        import torch
        waveform, _ = librosa.load(str(audio), sr=48000, mono=True)
        inputs = processor(text=descriptions, audios=waveform, sampling_rate=48000, return_tensors="pt", padding=True)
        with torch.no_grad():
            audio_features = model.get_audio_features(input_features=inputs.get("input_features"), is_longer=inputs.get("is_longer"))
            text_features = model.get_text_features(input_ids=inputs.get("input_ids"), attention_mask=inputs.get("attention_mask"))
            audio_features = audio_features / audio_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            value = float((audio_features @ text_features.T).mean().item())
        return _result(component, "ok", _clip_score(value, (0.45, 0.35, 0.25, 0.15)), value=round(value, 6), method="clap_htsat_unfused")
    except Exception as exc:  # noqa: BLE001
        return _result(component, "error", reason=f"CLAP inference failed: {exc}")


def dnsmos_component(case: Any) -> dict[str, Any]:
    onnxruntime, error = _optional_import("onnxruntime", "onnxruntime")
    if error:
        return _result("dnsmos_ovr", "not_configured", reason=error)
    audio = extract_audio(case.video_path, 16000)
    model_path = model_dir() / "dnsmos" / "model_v8.onnx"
    if not audio or not model_path.is_file():
        return _result("dnsmos_ovr", "missing_input", reason="audio or DNSMOS model unavailable")
    try:
        import librosa
        import numpy as np
        signal, _ = librosa.load(str(audio), sr=16000, mono=True)
        if len(signal) < 16000:
            return _result("dnsmos_ovr", "not_applicable", reason="audio shorter than one second")
        session = _CACHE.get("dnsmos") or onnxruntime.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        _CACHE["dnsmos"] = session
        input_name = session.get_inputs()[0].name
        result = session.run(None, {input_name: signal.astype(np.float32)[None, :]})
        values = [float(item) for item in np.asarray(result[0]).reshape(-1) if math.isfinite(float(item))]
        value = sum(values) / len(values) if values else None
        if value is None:
            return _result("dnsmos_ovr", "error", reason="DNSMOS returned no numeric output")
        return _result("dnsmos_ovr", "ok", _clip_score(value, (3.6, 3.2, 2.8, 2.3)), value=round(value, 6), method="dnsmos_model_v8")
    except Exception as exc:  # noqa: BLE001
        return _result("dnsmos_ovr", "error", reason=f"DNSMOS inference failed: {exc}")


def _load_ecapa() -> tuple[Any | None, str | None]:
    if "ecapa" in _CACHE:
        return _CACHE["ecapa"], None
    speechbrain, error = _optional_import("speechbrain", "speechbrain")
    if error:
        return None, error
    local = model_dir() / "spkrec-ecapa-voxceleb"
    try:
        encoder = speechbrain.inference.EncoderClassifier.from_hparams(source=str(local), savedir=str(local), run_opts={"device": "cpu"})
        _CACHE["ecapa"] = encoder
        return encoder, None
    except Exception as exc:  # noqa: BLE001
        return None, f"ECAPA load failed: {exc}"


def ecapa_component(case: Any) -> dict[str, Any]:
    encoder, error = _load_ecapa()
    if error:
        return _result("ecapa_same_speaker", "not_configured", reason=error)
    audio = extract_audio(case.video_path, 16000)
    if not audio:
        return _result("ecapa_same_speaker", "missing_input", reason="audio track unavailable")
    try:
        import numpy as np
        import soundfile as sf
        import torch
        waveform, _ = sf.read(str(audio), dtype="float32")
        if waveform.ndim > 1:
            waveform = waveform.mean(axis=1)
        candidates = [waveform]
        if case.reference_audios:
            reference, _ = sf.read(str(case.reference_audios[0]), dtype="float32")
            if reference.ndim > 1:
                reference = reference.mean(axis=1)
            candidates = [waveform, reference]
        elif len(waveform) >= 32000:
            midpoint = len(waveform) // 2
            candidates = [waveform[:midpoint], waveform[midpoint:]]
        embeddings = []
        for segment in candidates:
            if len(segment) < 12800:
                continue
            tensor = torch.from_numpy(np.asarray(segment, dtype=np.float32)).unsqueeze(0)
            embeddings.append(encoder.encode_batch(tensor).squeeze().detach())
        if len(embeddings) < 2:
            return _result("ecapa_same_speaker", "not_applicable", reason="fewer than two usable speech/reference segments")
        similarities = [float(torch.nn.functional.cosine_similarity(embeddings[i], embeddings[j], dim=0).item()) for i in range(len(embeddings)) for j in range(i + 1, len(embeddings))]
        value = sum(similarities) / len(similarities)
        return _result("ecapa_same_speaker", "ok", _clip_score(value, (0.75, 0.65, 0.55, 0.45)), value=round(value, 6), method="speechbrain_ecapa")
    except Exception as exc:  # noqa: BLE001
        return _result("ecapa_same_speaker", "error", reason=f"ECAPA inference failed: {exc}")


def emotion_component(case: Any, facts: dict[str, Any]) -> dict[str, Any]:
    funasr, error = _optional_import("funasr", "funasr")
    if error:
        return _result("emotion2vec_match", "not_configured", reason=error)
    audio = extract_audio(case.video_path, 16000)
    if not audio or not facts.get("dialogue_emotions"):
        return _result("emotion2vec_match", "not_applicable", reason="no applicable dialogue emotion")
    try:
        model = _CACHE.get("emotion2vec")
        if model is None:
            model = funasr.AutoModel(model=str(model_dir() / "emotion2vec_plus_large"), device="cpu")
            _CACHE["emotion2vec"] = model
        output = model.generate(str(audio), granularity="utterance", extract_embedding=False)
        labels = str(output).lower()
        target = str(facts.get("target_emotion") or "").lower()
        matched = bool(target and target in labels)
        return _result("emotion2vec_match", "ok", 5.0 if matched else 1.0, value=1.0 if matched else 0.0, output=output, method="emotion2vec_plus_large")
    except Exception as exc:  # noqa: BLE001
        return _result("emotion2vec_match", "error", reason=f"emotion2vec inference failed: {exc}")


def music_component(case: Any, facts: dict[str, Any]) -> dict[str, Any]:
    panns, error = _optional_import("panns_inference", "panns-inference")
    if error:
        return _result("music_presence", "not_configured", reason=error)
    audio = extract_audio(case.video_path, 32000)
    checkpoint = model_dir() / "panns" / "Cnn14_mAP=0.431.pth"
    if not audio or not checkpoint.is_file():
        return _result("music_presence", "missing_input", reason="audio or PANNs checkpoint unavailable")
    try:
        import librosa
        import numpy as np
        waveform, _ = librosa.load(str(audio), sr=32000, mono=True)
        if len(waveform) < 32000 * 2:
            return _result("music_presence", "not_applicable", reason="audio shorter than two seconds")
        tagger = _CACHE.get("panns")
        if tagger is None:
            tagger = panns.AudioTagging(checkpoint_path=str(checkpoint), device="cpu")
            _CACHE["panns"] = tagger
        prediction, _ = tagger.inference(waveform[None, :].astype(np.float32))
        prediction = np.asarray(prediction)
        if prediction.ndim == 1:
            prediction = prediction[None, :]
        labels = getattr(panns, "labels", None)
        if labels is None:
            try:
                from panns_inference.config import labels
            except ImportError:
                labels = None
        music_index = labels.index("Music") if labels and "Music" in labels else 137
        probabilities = prediction[..., music_index].reshape(-1)
        value = float(np.max(probabilities))
        if facts.get("music_forbidden") and not facts.get("music_required"):
            score = 5.0 if value < 0.2 else 3.0 if float(np.mean(probabilities >= 0.3)) < 0.2 else 1.0
        else:
            ratio = float(np.mean(probabilities >= 0.3))
            score = 5.0 if ratio >= 0.5 else 3.0 if ratio > 0.0 else 1.0
        return _result("music_presence", "ok", score, value=round(value, 6), method="panns_cnn14")
    except Exception as exc:  # noqa: BLE001
        return _result("music_presence", "error", reason=f"PANNs inference failed: {exc}")


def _load_ocr() -> tuple[Any | None, str | None]:
    if "ocr" in _CACHE:
        return _CACHE["ocr"], None
    paddleocr, error = _optional_import("paddleocr", "paddleocr")
    if error:
        return None, error
    det = model_dir() / "PP-OCRv5_server_det"
    rec = model_dir() / "PP-OCRv5_server_rec"
    if not det.is_dir() or not rec.is_dir():
        return None, "PP-OCRv5 model directories not found"
    try:
        ocr = paddleocr.PaddleOCR(
            text_detection_model_dir=str(det),
            text_recognition_model_dir=str(rec),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device=os.getenv("V_EVAL_OCR_DEVICE", "cpu"),
        )
        _CACHE["ocr"] = ocr
        return ocr, None
    except Exception as exc:  # noqa: BLE001
        return None, f"PP-OCRv5 load failed: {exc}"


def _ocr_texts(case: Any) -> tuple[list[str], str | None]:
    ocr, error = _load_ocr()
    if error:
        return [], error
    frames = video_frames(case.video_path, 8)
    texts: list[str] = []
    try:
        for frame in frames:
            results = ocr.predict(str(frame))
            for result in results:
                data = result.get("rec_texts", []) if hasattr(result, "get") else []
                texts.extend(str(item) for item in data if str(item).strip())
        return texts, None
    except Exception as exc:  # noqa: BLE001
        return [], f"OCR inference failed: {exc}"


def ocr_component(component: str, case: Any, facts: dict[str, Any]) -> dict[str, Any]:
    texts, error = _ocr_texts(case)
    if error:
        return _result(component, "not_configured", reason=error)
    expected = [str(item) for item in facts.get("expected_texts", []) if str(item).strip()]
    if component == "ocr_cer" and not expected:
        return _result(component, "not_applicable", reason="no expected text")
    if component == "ocr_subtitle_alignment" and not facts.get("subtitles_required"):
        return _result(component, "not_applicable", reason="subtitles not required")
    joined = " ".join(texts)
    if component in {"ocr_cer", "ocr_subtitle_alignment"}:
        target = " ".join(expected) or str(facts.get("subtitle_lines") or "")
        ratio = difflib.SequenceMatcher(None, target, joined).ratio() if target else 0.0
        cer = 1.0 - ratio
        return _result(component, "ok", _clip_score(cer, (0.05, 0.15, 0.30, 0.50), higher=False), value=round(cer, 6), recognized=texts, method="ppocrv5")
    if component == "ocr_readability":
        ratio = min(1.0, len(texts) / max(1, len(expected))) if expected else min(1.0, len(texts) / 3.0)
        return _result(component, "ok", _clip_score(ratio, (1.0, 0.8, 0.6, 0.3)), value=round(ratio, 6), recognized=texts, method="ppocrv5")
    if component == "ocr_text_stability":
        frames = max(1, len(video_frames(case.video_path, 8)))
        ratio = min(1.0, len(texts) / frames)
        return _result(component, "ok", _clip_score(ratio, (0.9, 0.75, 0.5, 0.25)), value=round(ratio, 6), recognized=texts, method="ppocrv5")
    return _result(component, "not_applicable", reason="unsupported OCR component")


def _silero_speech_intervals(audio: Path) -> tuple[list[tuple[float, float]], str | None]:
    module, error = _optional_import("silero_vad", "silero-vad")
    if error:
        return [], error
    try:
        vad = _CACHE.get("silero_vad")
        if vad is None:
            try:
                vad = module.load_silero_vad(onnx=True)
            except TypeError:
                vad = module.load_silero_vad()
            _CACHE["silero_vad"] = vad
        waveform = module.read_audio(str(audio), sampling_rate=16000)
        timestamps = module.get_speech_timestamps(
            waveform, vad, sampling_rate=16000, return_seconds=True,
        )
        intervals = []
        for row in timestamps:
            if not isinstance(row, dict):
                continue
            start = _safe_float(row.get("start"))
            end = _safe_float(row.get("end"))
            if start is not None and end is not None and end > start:
                intervals.append((max(0.0, start), end))
        return intervals, None
    except Exception as exc:  # noqa: BLE001
        return [], f"Silero VAD failed: {exc}"


def _bounded_speech_windows(intervals: list[tuple[float, float]], duration: float) -> list[dict[str, float]]:
    try:
        max_windows = max(1, int(os.getenv("V_EVAL_SYNCNET_MAX_WINDOWS", "4")))
        max_total = max(1.0, float(os.getenv("V_EVAL_SYNCNET_MAX_TOTAL_SECONDS", "12")))
        window_seconds = max(1.0, float(os.getenv("V_EVAL_SYNCNET_WINDOW_SECONDS", "2")))
        if not all(math.isfinite(value) and value > 0 for value in (max_total, window_seconds)):
            raise ValueError("invalid SyncNet window limits")
    except (TypeError, ValueError, OverflowError):
        max_windows, max_total, window_seconds = 4, 12.0, 2.0
    usable_length = min(window_seconds, max_total / max_windows, duration)
    candidates: list[dict[str, float]] = []
    for speech_start, speech_end in intervals:
        center = (speech_start + speech_end) / 2.0
        start = min(max(0.0, center - usable_length / 2.0), max(0.0, duration - usable_length))
        end = min(duration, start + usable_length)
        if end > start:
            candidates.append({"start": round(start, 6), "end": round(end, 6)})
    if len(candidates) <= max_windows:
        return candidates
    if max_windows == 1:
        return [candidates[len(candidates) // 2]]
    indices = {round(index * (len(candidates) - 1) / (max_windows - 1)) for index in range(max_windows)}
    return [candidates[index] for index in sorted(indices)]


def _visible_face_windows(windows: list[dict[str, float]], case: Any) -> tuple[list[dict[str, float]], str | None]:
    app, error = _load_insightface()
    if error:
        return [], error
    try:
        import cv2
        visible: list[dict[str, float]] = []
        for window in windows:
            timestamp = (window["start"] + window["end"]) / 2.0
            frame = extract_frame(case.video_path, timestamp)
            image = cv2.imread(str(frame)) if frame else None
            faces = app.get(image) if image is not None else []
            has_visible_face = False
            for face in faces:
                bbox = getattr(face, "bbox", None)
                if bbox is None or len(bbox) < 4:
                    continue
                if float(bbox[2] - bbox[0]) >= 40.0 and float(bbox[3] - bbox[1]) >= 40.0:
                    has_visible_face = True
                    break
            if has_visible_face:
                visible.append(window)
        return visible, None
    except Exception as exc:  # noqa: BLE001
        return [], f"InsightFace window filtering failed: {exc}"


def _syncnet_adapter_response(command: str, request: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        completed = subprocess.run(
            shlex.split(command), input=json.dumps(request, ensure_ascii=False),
            capture_output=True, text=True, check=False,
            timeout=max(1, int(os.getenv("V_EVAL_SYNCNET_TIMEOUT", "180"))),
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return None, f"SyncNet adapter execution failed: {exc}"
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        return None, f"SyncNet adapter failed: {detail[:2000]}"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"SyncNet adapter returned invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "SyncNet adapter response must be a JSON object"
    return payload, None


def syncnet_component(case: Any, facts: dict[str, Any]) -> dict[str, Any]:
    """Run a configured real SyncNet adapter; never substitute an energy-correlation proxy."""
    component = "syncnet_conf"
    command = os.getenv("V_EVAL_SYNCNET_COMMAND", "").strip()
    if not command:
        return _result(component, "not_configured", reason="V_EVAL_SYNCNET_COMMAND is not configured")
    if not facts.get("dialogues"):
        return _result(component, "not_applicable", reason="no requested dialogue")
    if not case.video_path or not case.video_path.is_file():
        return _result(component, "missing_input", reason="target video is unavailable")
    weights = os.getenv("V_EVAL_SYNCNET_WEIGHTS", "").strip()
    if weights and not Path(weights).expanduser().is_file():
        return _result(component, "not_configured", reason=f"SyncNet weights not found: {weights}")
    duration = _ffprobe_duration(case.video_path)
    audio = extract_audio(case.video_path, 16000)
    if duration is None or duration <= 0 or audio is None:
        return _result(component, "missing_input", reason="video duration or 16 kHz audio is unavailable")
    intervals, vad_error = _silero_speech_intervals(audio)
    if vad_error:
        return _result(component, "not_configured", reason=vad_error)
    if not intervals:
        return _result(component, "not_applicable", reason="Silero VAD found no speech")
    windows = _bounded_speech_windows(intervals, duration)
    windows, face_error = _visible_face_windows(windows, case)
    if face_error:
        return _result(component, "not_configured", reason=face_error)
    if not windows:
        return _result(component, "not_applicable", reason="no speech window contains a visible face of at least 40 px")

    request: dict[str, Any] = {
        "protocol_version": 1,
        "component": component,
        "video_path": str(case.video_path.resolve()),
        "audio_path": str(audio.resolve()),
        "windows": windows,
        "expected_output": {"confidence": "number", "offset_ms": "number", "windows": "optional array"},
    }
    if weights:
        request["weights_path"] = str(Path(weights).expanduser().resolve())
    response, adapter_error = _syncnet_adapter_response(command, request)
    if adapter_error:
        return _result(component, "error", reason=adapter_error, windows=windows)
    assert response is not None
    response_status = str(response.get("status", "ok"))
    if response_status == "not_configured":
        return _result(component, "not_configured", reason=str(response.get("reason") or "adapter is not configured"))
    if response_status != "ok":
        return _result(component, "error", reason=str(response.get("reason") or f"adapter status: {response_status}"))

    confidence = _safe_float(response.get("confidence"))
    returned_windows = response.get("windows")
    window_confidences: list[float] = []
    window_offsets: list[float] = []
    if isinstance(returned_windows, list):
        for row in returned_windows:
            if not isinstance(row, dict):
                continue
            current_confidence = _safe_float(row.get("confidence"))
            current_offset = _safe_float(row.get("offset_ms"))
            if current_confidence is not None:
                window_confidences.append(current_confidence)
            if current_offset is not None:
                window_offsets.append(current_offset)
    if confidence is None and window_confidences:
        confidence = sum(window_confidences) / len(window_confidences)
    if confidence is None:
        return _result(component, "error", reason="SyncNet adapter response has no finite confidence", windows=windows)
    offset_ms = _safe_float(response.get("offset_ms"))
    if offset_ms is None and window_offsets:
        offset_ms = sum(window_offsets) / len(window_offsets)
    return _result(
        component, "ok", _clip_score(confidence, (7.0, 5.5, 4.0, 2.5)),
        confidence=round(confidence, 6), offset_ms=round(offset_ms, 3) if offset_ms is not None else None,
        windows=windows, adapter_windows=returned_windows if isinstance(returned_windows, list) else None,
        method="syncnet_v2_external_adapter",
    )


def run_local_component(name: str, case: Any, facts: dict[str, Any]) -> dict[str, Any] | None:
    if name in {"csd_ref_similarity", "csd_temporal_drift"}:
        return csd_component(name, case)
    if name == "endpoint_psnr":
        return psnr_component(case)
    if name in {"endpoint_lpips", "continuation_seam_lpips"}:
        return lpips_component(name, case)
    if name == "arcface_identity_keep":
        return arcface_component(case)
    if name == "dnsmos_ovr":
        return dnsmos_component(case)
    if name == "ecapa_same_speaker":
        return ecapa_component(case)
    if name == "emotion2vec_match":
        return emotion_component(case, facts)
    if name in {"clap_ambient", "clap_sfx", "clap_music"}:
        return clap_component(name, case, facts)
    if name == "music_presence":
        return music_component(case, facts)
    if name == "syncnet_conf":
        return syncnet_component(case, facts)
    if name in {"ocr_cer", "ocr_subtitle_alignment", "ocr_readability", "ocr_text_stability"}:
        return ocr_component(name, case, facts)
    return None

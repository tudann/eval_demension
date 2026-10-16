"""Prepare an isolated D13 test bundle from the source CSV, without running judges."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "d13_test"
MODES = {"text": "t2va", "first_frame": "f2va", "reference": "r2va"}


def write_text_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Refusing to overwrite modified file: {path.relative_to(ROOT)}")
    else:
        path.write_text(content, encoding="utf-8")


def video_info(path: Path) -> dict:
    probe = ROOT / ".runtime" / "ffmpeg" / "bin" / "ffprobe.exe"
    executable = str(probe) if probe.is_file() else shutil.which("ffprobe")
    if not executable:
        raise ValueError("ffprobe is required to validate videos")
    result = subprocess.run([executable, "-v", "error", "-show_entries",
                             "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
                            check=True, capture_output=True, text=True, timeout=30)
    info = json.loads(result.stdout)
    if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
        raise ValueError("No video stream")
    if float(info.get("format", {}).get("duration", 0)) <= 0:
        raise ValueError("Invalid duration")
    return info


def fetch(job: tuple[str, Path, str, str], download: bool) -> dict:
    case_id, destination, url, kind = job
    record = {"case_id": case_id, "file": str(destination.relative_to(BUNDLE)), "kind": kind}
    if kind == "image":
        existing = next((p for p in sorted(destination.parent.glob(destination.stem + ".*"))
                         if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}), None)
    else:
        existing = destination if destination.is_file() else None
    temporary = destination.with_suffix(".download")
    try:
        if existing is None:
            if not download:
                return {**record, "status": "missing", "error": "not downloaded"}
            request = urllib.request.Request(url, headers={"User-Agent": "v-eval-case-preparation/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as handle:
                shutil.copyfileobj(response, handle)
            existing = temporary
        if kind == "image":
            with Image.open(existing) as image:
                image.verify()
                extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image.format)
            if not extension:
                raise ValueError("Unsupported image format")
            final = destination.with_suffix(extension)
        else:
            record["probe"] = video_info(existing)
            final = destination
        if existing == temporary:
            if final.exists():
                raise ValueError("Destination already exists")
            temporary.rename(final)
        else:
            final = existing
        return {**record, "file": str(final.relative_to(BUNDLE)), "status": "ready", "bytes": final.stat().st_size}
    except urllib.error.HTTPError as exc:
        return {**record, "status": "missing", "error": f"HTTP {exc.code}"}
    except Exception as exc:
        # Never include a signed source URL in console output or error reports.
        return {**record, "status": "missing", "error": type(exc).__name__}
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="Fetch missing source media")
    args = parser.parse_args()
    with (ROOT / "data" / "d13_d20_cases.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = [(n, row) for n, row in enumerate(csv.DictReader(handle), 2)
                if row["一级维度"].startswith("13.")]
    if len(rows) != 15 or len({row["case_id"] for _, row in rows}) != 15:
        raise ValueError("Expected 15 unique D13 cases")
    jobs = []
    cases = []
    dimension_cfg = yaml.safe_load((ROOT / "configs" / "dims_13_18.yaml").read_text(encoding="utf-8"))
    subpoints = dimension_cfg["dimensions"]["13_style_visual_control"]["subpoints"]
    names = {cfg["name_zh"]: key for key, cfg in subpoints.items()}
    for row_number, row in rows:
        case_id, mode = row["case_id"], MODES[row["mode"]]
        directory = BUNDLE / "cases" / mode / case_id
        original = row["prompt_input"].rstrip("\r\n") + "\n"
        prompt = original
        media = [("images", "input", "image"), ("input_videos", "ref_video", "video"),
                 ("audios", "ref_audio", "audio")]
        markers = []
        for column, stem, kind in media:
            for index, url in enumerate(json.loads(row[column]), 1):
                extension = ".png" if kind == "image" else ".mp4" if kind == "video" else ".wav"
                jobs.append((case_id, directory / f"{stem}_{index:02d}{extension}", url, kind))
                if mode == "r2va":
                    markers.append(f"Reference {kind.title()} {index} = {stem}_{index:02d}")
        if markers:
            prompt = "参考素材编号（按 CSV 原顺序；第一张/第二张对应图1/图2）：\n" + "\n".join(markers) + "\n\n" + original
        write_text_once(directory / "prompt_original.txt", original)
        write_text_once(directory / "prompt_final.txt", prompt)
        source = {"csv": "data/d13_d20_cases.csv", "csv_row": row_number, **row,
                  "evaluation_dimension": "13_style_visual_control", "evaluation_mode": mode,
                  "expected_subpoint": names[row["二级维度"]],
                  "prompt_adaptation": "reference index legend added" if markers else "none"}
        write_text_once(directory / "source.json", json.dumps(source, ensure_ascii=False, indent=2) + "\n")
        jobs.append((case_id, directory / "video.mp4", row["output_url"], "video"))
        cases.append({"case_id": case_id, "mode": mode, "subpoint": row["二级维度"],
                      "expected_subpoint": names[row["二级维度"]]})
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda job: fetch(job, args.download), jobs))
    for case in cases:
        case["media"] = [r for r in results if r["case_id"] == case["case_id"]]
        case["ready"] = all(r["status"] == "ready" for r in case["media"])
        directory = BUNDLE / "cases" / case["mode"] / case["case_id"]
        (directory / "readiness.json").write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    task = yaml.safe_load((ROOT / "configs" / "task_d13_local.yaml").read_text(encoding="utf-8"))
    task.update(task_name="csv_d13_test", run_name="csv_d13_test", output_dir="../outputs/d13_csv_test")
    task["inputs"] = []
    for mode in MODES.values():
        source = next(i for i in yaml.safe_load((ROOT / "configs" / "task_d13_local.yaml").read_text(encoding="utf-8"))["inputs"] if i["mode"] == mode)
        source.update(root=f"./d13_test/cases/{mode}", allow_missing_root=False,
                      case_ids=[c["case_id"] for c in cases if c["mode"] == mode])
        task["inputs"].append(source)
    (BUNDLE / "task_all.yaml").write_text(yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8")
    ready_task = {**task, "run_name": "csv_d13_ready", "inputs": []}
    for item in task["inputs"]:
        ready_ids = [c["case_id"] for c in cases if c["mode"] == item["mode"] and c["ready"]]
        if ready_ids:
            ready_task["inputs"].append({**item, "case_ids": ready_ids})
    if ready_task["inputs"]:
        (BUNDLE / "task_ready.yaml").write_text(yaml.safe_dump(ready_task, allow_unicode=True, sort_keys=False), encoding="utf-8")
    report = {"source": "data/d13_d20_cases.csv", "total": len(cases),
              "ready": sum(c["ready"] for c in cases), "cases": cases}
    (BUNDLE / "readiness.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"D13: {len(cases)} cases; ready {report['ready']}; media {sum(r['status']=='ready' for r in results)}/{len(results)}")
    for case in cases:
        missing = [m["file"] + " (" + m["error"] + ")" for m in case["media"] if m["status"] != "ready"]
        print(case["case_id"], "ready" if case["ready"] else "missing: " + ", ".join(missing))


if __name__ == "__main__":
    main()

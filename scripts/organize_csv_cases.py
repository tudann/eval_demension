"""Stage CSV case prompts and media links without downloading or overwriting media."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "d13_d20_cases.csv"
DEFAULT_OUTPUT = ROOT / "data" / "d13_d20_cases"

DIMENSIONS = {
    "13": ("13_style_visual_control", True),
    "14": ("14_edit_controllable_gen", True),
    "15": ("15_audio_quality_control", True),
    "16": ("16_audio_visual_sync", True),
    "17": ("17_failure_anomaly_control", True),
    "18": ("18_text_visual_consistency", True),
    "20": ("20_performance_emotion", True),
}
MODES = {
    "text": "t2va",
    "first_frame": "f2va",
    "first_and_last_frame": "fl2va",
    "reference": "r2va",
}
REQUIRED_COLUMNS = {
    "case_id", "一级维度", "二级维度", "mode", "ratio", "seconds", "size",
    "prompt_input", "images", "audios", "input_videos", "output_url",
}


def parse_links(value: str, case_id: str, column: str) -> list[str]:
    try:
        links = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{case_id}: invalid JSON in {column}") from exc
    if not isinstance(links, list) or any(not isinstance(link, str) or not link for link in links):
        raise ValueError(f"{case_id}: {column} must be a JSON array of URLs")
    return links


def labeled_links(links: list[str], stem: str) -> list[dict[str, str]]:
    return [{"filename_stem": f"{stem}_{index:02d}", "url": url}
            for index, url in enumerate(links, 1)]


def build_files(csv_path: Path, output: Path) -> tuple[dict[Path, str], Counter[str]]:
    files: dict[Path, str] = {}
    counts: Counter[str] = Counter()
    seen_ids: set[str] = set()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV missing columns: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, 2):
            case_id = row["case_id"].strip()
            if not re.fullmatch(r"[0-9]+", case_id) or case_id in seen_ids:
                raise ValueError(f"row {row_number}: invalid or duplicate case_id: {case_id!r}")
            seen_ids.add(case_id)
            match = re.match(r"^(\d+)\.", row["一级维度"].strip())
            dimension_number = match.group(1) if match else ""
            # D19 is source data but not part of the seven-dimension evaluator.
            if dimension_number == "19":
                continue
            if dimension_number not in DIMENSIONS or not case_id.startswith(dimension_number):
                raise ValueError(f"row {row_number}: dimension does not match case_id {case_id}")
            source_mode = row["mode"].strip()
            if source_mode not in MODES:
                raise ValueError(f"row {row_number}: unsupported mode: {source_mode!r}")
            dimension, compatible = DIMENSIONS[dimension_number]
            mode = MODES[source_mode]
            images = parse_links(row["images"], case_id, "images")
            audios = parse_links(row["audios"], case_id, "audios")
            input_videos = parse_links(row["input_videos"], case_id, "input_videos")
            expected_images = {"text": 0, "first_frame": 1, "first_and_last_frame": 2}
            if source_mode in expected_images and len(images) != expected_images[source_mode]:
                raise ValueError(f"{case_id}: {source_mode} expects {expected_images[source_mode]} image(s)")
            if source_mode != "reference" and (audios or input_videos):
                raise ValueError(f"{case_id}: unexpected reference audio/video in {source_mode}")
            prompt = row["prompt_input"]
            if not prompt.strip():
                raise ValueError(f"{case_id}: empty prompt_input")
            case_dir = output / dimension / mode / case_id
            files[case_dir / "prompt_final.txt"] = prompt.rstrip("\r\n") + "\n"
            source = {
                "case_id": case_id,
                "csv_row": row_number,
                "source_dimension": row["一级维度"],
                "source_subdimension": row["二级维度"],
                "source_mode": source_mode,
                "evaluation_dimension": dimension if compatible else None,
                "evaluation_mode": mode,
                "ratio": row["ratio"],
                "seconds": row["seconds"],
                "size": row["size"],
                "target_video": {"filename": "video.mp4", "url": row["output_url"].strip() or None},
                "reference_images": labeled_links(images, "input"),
                "reference_audios": labeled_links(audios, "ref_audio"),
                "reference_videos": labeled_links(input_videos, "ref_video"),
            }
            files[case_dir / "source.json"] = json.dumps(source, ensure_ascii=False, indent=2) + "\n"
            counts[dimension] += 1
    return files, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    files, counts = build_files(args.csv, args.output)
    conflicts = [path for path, content in files.items()
                 if path.exists() and path.read_text(encoding="utf-8") != content]
    if conflicts:
        raise ValueError(f"existing case files differ; refusing to overwrite: {conflicts[0]}")
    new_files = [path for path in files if not path.exists()]
    for path in new_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(files[path], encoding="utf-8")
    print(f"organized {sum(counts.values())} cases into {args.output}; wrote {len(new_files)} files")
    for dimension, count in sorted(counts.items()):
        print(f"  {dimension}: {count}")


if __name__ == "__main__":
    main()

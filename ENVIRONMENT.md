# Windows Setup and Evaluation

## Code layout

`run.py` is the command-line entry point. The evaluation implementation lives in `v_eval/`:

- `cases.py`: case discovery, paths, prompts, and applicability checks.
- `judge_client.py`: external judge configuration and response parsing.
- `checklists.py`: dimension-specific checklist generation and judge answers.
- `judge_media.py`: video, image, and audio preparation for the judge.
- `scoring.py`: checklist, gate, numeric-component, and dimension scoring.
- `model_components.py`: optional local numeric model adapters.
- `workflow.py`: per-case preparation, evaluation, caching, and result files.

`core.py` remains as a compatibility import path; new code should import from the module that owns the function. Shared dimension definitions and weights remain in `configs/dims_13_18.yaml`.

## Prepare once

Install `uv` if it is not already available, then run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_environment.ps1 -InstallFfmpeg
```

This installs Python 3.11 under `.runtime/python`, creates `.venv`, installs the lightweight evaluator dependencies and case/output folders, and installs `ffmpeg` plus `ffprobe` locally under `.runtime/ffmpeg`. The run script adds that location to PATH automatically. The explicit `-ExecutionPolicy Bypass` applies only to this PowerShell process and does not change the machine policy.

When npm is available, setup downloads the Windows FFmpeg/ffprobe binary packages through the configured npm registry; otherwise it uses the Gyan FFmpeg essentials archive. An existing system installation also works.

## Configure judge services

The checklist author and answer judge are external OpenAI-compatible chat completion services. Copy `.env.example` to `.env` and replace the example URL, model, and key values. D13, D14, D17, and D18 need a vision-capable judge; D15, D16, and D20 need an audio or audio-visual judge. Checklist generation can use `V_EVAL_CHECKLIST_URL`; when unset, the applicable vision/audio judge endpoint is used.

## Add cases and run

See [data/cases/README.md](data/cases/README.md) for the case layout. Verify a dimension before making API calls:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_dimension.ps1 -Dimension 13 -CheckOnly
```

Evaluate and score all discovered cases for one dimension:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_dimension.ps1 -Dimension 13
```

The same command accepts dimensions `14`, `15`, `16`, `17`, `18`, and `20`. Results and summaries are written under the matching `outputs/dNN/runs/local_dNN/` folder. Pass `-Force` to ignore saved result/checklist caches.

Every case needs a nonempty `prompt_final.txt` and `video.mp4`; frame-conditioned modes also need their endpoint images. The run stops before any judge calls if a discovered case is incomplete. If you replace a prompt, video, or reference after a run, use `-Force` to refresh the cached checklist and result.
Cases that fail because of a temporary judge or media error are retried automatically on the next run; successful cached scores are reused unless `-Force` is supplied.

The seven local task files enable checklist-based scoring and explicitly disable optional local numeric components. Those components need separate heavyweight dependencies and model weights; see [docs/local_model_components.md](docs/local_model_components.md). Enable a component in its task file only after installing and validating it. D17's anomaly rates and breakdown duration are currently judged on a 1–5 rubric, not reported as measured percentages or seconds; the `vlm_anomaly_rate` adapter is not implemented.

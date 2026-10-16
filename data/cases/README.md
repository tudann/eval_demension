# Case Input Folders

Place evaluation cases under the dimension and input-mode folders. Each direct child folder is one case.

```text
data/cases/<dimension>/<mode>/<case_id>/
  prompt_final.txt
  video.mp4
  input_01.png       # f2va/l2va, or an explicitly referenced r2va image
  input_02.png       # required last-frame image for fl2va
  ref_video_01.mp4   # r2va, only when referenced by the prompt
  ref_audio_01.wav   # r2va, only when referenced by the prompt
```

Supported dimensions are `13_style_visual_control`, `14_edit_controllable_gen`, `15_audio_quality_control`, `16_audio_visual_sync`, `17_failure_anomaly_control`, `18_text_visual_consistency`, and `20_performance_emotion`. D19 is outside this evaluation framework.

Supported modes are `t2va`, `f2va`, `l2va`, `fl2va`, and `r2va`. Endpoint image names are configurable in each task file. The standard names above match the supplied local configurations. In `r2va`, reference media is attached only when the prompt explicitly identifies its one-based index, for example `Reference Image 1`, `Reference Video 1`, or `Reference Audio 1`.

For audio or video references, use common formats such as MP4, MOV, MP3, WAV, or FLAC. Keep one generated target video named `video.mp4` in each case directory. Case IDs should be unique within a mode.
For D15, D16, and D20, the target `video.mp4` must contain an audio stream; otherwise media preparation returns an unscored `media_error`.

Run `scripts/setup_environment.ps1` once to create the five mode folders for all seven dimensions. Run `scripts/run_dimension.ps1 -Dimension 13 -CheckOnly` to verify discovery and case completeness, then run it without `-CheckOnly` to evaluate. If PowerShell blocks `.ps1` files, use the `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` commands in [ENVIRONMENT.md](../../ENVIRONMENT.md).

# CSV cases awaiting media

These folders are organized from `../d13_d20_cases.csv`. The source CSV is unchanged.
Each case has a `prompt_final.txt` and a `source.json` containing the original row number,
dimension/mode labels, media URLs, and the local filename stems to use. No video or
reference media has been downloaded, and no placeholder media has been created.

```text
<dimension>/<mode>/<case_id>/
  prompt_final.txt
  source.json
  video.mp4                 # add the actual generated video
  input_01.<image format>   # when source.json lists a first/reference image
  input_02.<image format>   # when source.json lists a second image
  ref_video_01.<format>     # when source.json lists a reference video
```

CSV modes map to evaluator modes as `text → t2va`, `first_frame → f2va`,
`first_and_last_frame → fl2va`, and `reference → r2va`. Determine the true image or
video extension after obtaining the media; do not rename non-MP4 data to `.mp4`.
The Feishu auth-code URLs in the source may expire.

This is a staging folder, separate from `data/cases/` used by the local task configs.
After adding the real media, place ready cases in the corresponding
`data/cases/<evaluation_dimension>/<mode>/<case_id>/` folders. The evaluator now uses
the CSV's seven dimensions, including D17 “失败与异常控制”. D19 is outside the
evaluation framework. Its three previously staged source rows are retained here
for provenance but are ignored on future imports and must not be scored. Two source
rows have no target-video URL; they require a video supplied separately.

To refresh the staging tree after adding CSV rows, run
`.venv/Scripts/python.exe scripts/organize_csv_cases.py`. The importer rejects conflicting existing
files, so manually edited prompts and metadata are not overwritten.

# 中文三任务 300 条中的第 13–18 维

来源是同目录上一级的 `中文三任务300条基准集 V2.csv`。这里只保留 `benchmark_level1_id` 为 13–18 的 96 条，并按当前评测框架的输入方式放好。

每条 case 是模式目录下的一个子目录，评测器读取 `prompt_final.txt` 和 `video.mp4`。`metadata.json`、`index.csv` 只作整理记录，评测器不读取。

## 输入模式

| 原任务 | 评测模式 | 本批条数 | 条件文件 |
|---|---|---|---|
| `t2v` | `t2va` | 29 | 无 |
| `i2v`（素材角色为首帧） | `f2va` | 36 | `input_01.png` 或 `input_01.jpg` |
| `ref2v`（素材角色为参考图） | `r2va` | 31 | `input_01` 起按原序号编号 |

这批数据没有尾帧任务，也没有同时给首帧和尾帧的任务，所以没有 `l2va`、`fl2va` 目录。

参考图已从 CSV 里的地址下载到对应 case 目录，共 89 张。CSV 里没有成片，因此目前都没有 `video.mp4`。打分前把成片放到该 case 目录并命名为 `video.mp4`；缺视频时该条记为 `skipped_missing_video`，不计分。

`r2va` 只把提示词里写明编号的参考图送进评测，例如 `参考图1`、`[Reference Image 1]`。本批 31 条里只有 2 条写了这种编号，其余参考图已保存在目录中，当前加载器不会附上。`f2va` 的首帧按文件名读取，不依赖提示词编号。

## 目录

```text
d13_d18/
  index.csv
  13_style_visual_control/{t2va,f2va,r2va}/<case_id>/
  14_edit_controllable_gen/{f2va,r2va}/<case_id>/
  15_audio_quality_control/{t2va,f2va,r2va}/<case_id>/
  16_audio_visual_sync/{t2va,f2va,r2va}/<case_id>/
  17_motion_temporal_consistency/{t2va,f2va,r2va}/<case_id>/
  18_text_visual_consistency/{t2va,f2va,r2va}/<case_id>/
```

第 14 维原表没有 `t2v`。各维条数：13 为 16，14 为 16，15 为 16，16 为 16，17 为 16，18 为 16。

## 运行

任务配置在 `configs/task_d13_cn300.yaml` 至 `configs/task_d18_cn300.yaml`。只检查能否发现 case：

```bash
.venv/bin/python run.py --task-config configs/task_d13_cn300.yaml --stages check
```

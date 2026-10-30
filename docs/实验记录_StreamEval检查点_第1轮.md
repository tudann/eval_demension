# 实验记录：StreamEval 检查点第 1 轮

> 日期：2026-10-28  
> 状态：D14 已用同一批片子完成优化前、优化后对照。结论见 `实验报告_D14_StreamEval检查点对照.md`。还没有人工对齐。D16、D20 还没有重跑。  
> 对照目录：旧清单留在 `outputs/d14_regression`，以及已经落盘的 `outputs/compare/<视频>/<提示词>/d14`。新结果仍用 `configs/compare_run.yaml` 加 `bash scripts/run_compare.sh`。同一提示词和视频再跑时，把 `output_tag` 设成新名字，写到旁边的新目录。  
> 本轮只借鉴 StreamEval。分数合成、子项权重、ArcFace / LPIPS / PSNR / SyncNet 都没有改。

## 1. 要验证的问题

短 clip 上，把检查题改成 StreamEval 的检查点之后，裁判会不会少给「闪一下就算改对 / 看错对象也给高分 / 声音和画面不在同一段仍给高分」。

对照协议：

| 维度 | 借的指标 | 短 clip 上的问法 |
|------|----------|------------------|
| D14 局部修改 | Edit Success | 期望状态是否在成片后段连续稳定 |
| D14 非目标保持 | Preservation | 同一时段里，保护列表是否未改 |
| D14 主体替换 | Reference + Identity | 对照参考图，身份和外观属性是否同时成立 |
| D16 口型 / 动作音 / 环境音 | A–V Sync | 声音和可见事件是否在同一时间窗，且没有明显超前或滞后 |
| D20 表演 | Following | 写明的情绪、视线、表情变化、反应、动作是否做到；只闪一下不算充分达成 |

D13、D15、D17、D18 本轮没有改。

## 2. 改了哪些文件

| 文件 | 改动 |
|------|------|
| `configs/dims_13_18.yaml` | D14 事实增加 `edit_expected_state`、`reference_attributes`。D20 事实增加 `performance_controls`。子项名称、权重、适用条件没变 |
| `v_eval/checklists.py` | 出题策略、事实别名、题面改写、作答附加口径。通过校验的 D14 / D16 / D20 清单带 `checkpoint_protocol: streameval_v1` |
| `tests/test_checklist_facts.py` | 覆盖 D14 成对检查点、参考替换、D16 时间窗、D20 指定动作 |
| `docs/D13-D20优先优化表.md` | 指向本记录 |

## 3. 行为前后

### D14

改前：`local_edit_accuracy` 只要求 `edit_targets` 非空，题面由裁判自由写，可以是「衣服有没有改好」。`preserved` 有字段，但没有强制写进非目标题。

改后：出题结果里

- `edit_expected_state` 抄自期望状态（没有单独写时，用 `edit_targets`）
- 局部修改题固定为：期望状态是否在**成片后段稳定段**成立；闪现、改错对象、旧状态回来，都不能算充分达成
- 非目标题固定为：在**同一时段**，`preserved` 列出的内容是否未改
- 主体替换且带参考图或外观属性时，题面要求身份和属性同时成立

作答附加口径：上述失败情况最高 3 分；5 分只给后段稳定成立。人脸分和像素分不代替这两道题。

### D16

改前：口型题可以只写「嘴部开合是否对应这句话」。动作音 / 环境音题写「是否同时发生」，没有偏移窗。

改后：有对白、动作声或环境声时，题面改成「是否落在同一时间窗内，且没有明显超前或滞后」，并带上具体对白或声音事实。作答时，明显超前或滞后最高 3 分。没有换掉 SyncNet，也没有接入别的同步模型。

### D20

改前：情绪、视线、反应题可以是「对不对」「是否及时」。

改后：

- 有 `target_emotion` / `character_situation`、`emotion_change`、`gaze_target`、`reaction_event` 时，题面改成「是否做到了」加上失败条款（没做到、做错对象、只闪一下）
- `performance_controls` 里的指定动作追加到第一条表演题上，不覆盖眨眼、呼吸那道微动作题
- 语音情绪仍不进 D20

## 4. 明确没改的部分

- 维度分仍是 1–5，不是 StreamEval 的 0–100
- D14 的 ArcFace 0.4、续写 LPIPS 0.5、首尾帧 PSNR/LPIPS 权重不变
- D16 的 SyncNet 0.3 权重不变
- 不跑 StreamEval 的 WebSocket 会话，也不做 15/30/60/120/300 秒等权聚合
- 已落盘的 checklist 缓存不会自动更新

## 5. 建议的实验跑法

在 `eval_dem_13_20` 下改 `configs/compare_run.yaml`，然后执行 `bash scripts/run_compare.sh`。`force` 保持 `false`。

和旧回归同一批片子时：`dimensions: [14]`，`prompt_filename: prompt_final.txt`，`video_filename: video.mp4`，`output_tag` 留空。新结果写到 `outputs/compare/video/prompt_final/d14`。旧结果留在 `outputs/d14_regression`。

沿用已经出过题的 `prompt_enhanced.txt` 加 `video-group-new.mp4` 或 `agnes-2.5-flash.mp4` 时：同样只改 `dimensions: [14]`，并把 `output_tag` 设为 `streameval_v1`。新题写到 `outputs/compare/<视频>/prompt_enhanced/streameval_v1/d14`。改代码前的清单仍在 `outputs/compare/<视频>/prompt_enhanced/d14`。

需要在线视觉裁判。D16、D20 仍要等音频裁判。

看每条结果里的：

1. `checklist.json`（或等价清单）是否带 `checkpoint_protocol = streameval_v1`
2. D14 是否同时有期望状态题和保护内容题，两题是否指向同一时段
3. D16 同步题是否写了时间窗
4. D20 是否把 prompt 里写明的视线 / 动作写进题面
5. 同一条片子上，新题分数和旧题分数差多少；闪现、改错对象、声画错位的样本是否从 4–5 落到 3 及以下

人工对照先做小样本。同向之后再考虑改权重。本轮不要把新题分数直接换成对外维度分的最终口径，先作为对照。

## 6. 单测

`tests/test_checklist_facts.py` 里新增 `StreamEvalCheckpointTests`，并收紧了 D16 口型题、D20 已有情绪事实的题面断言。不调用在线裁判。

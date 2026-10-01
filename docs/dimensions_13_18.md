# 第 13–18 维度说明

## 第 13 维度：风格与视觉控制

核心问题是视频是否按照提示词稳定呈现目标风格、内容关系、光照和颜色。子项为：

- `style_accuracy`：风格准确性。
- `style_persistence`：风格随时间的持续性。
- `style_content_compat`：风格与主体、动作、世界状态的兼容性。
- `lighting_control`：是否符合目标光照要求；没有光照要求时不适用。
- `color_control`：是否符合目标颜色要求；没有颜色要求时不适用。

## 第 14 维度：编辑与可控生成

核心问题是编辑目标是否被正确修改，以及未要求修改的内容是否保持。子项为：

- `local_edit_accuracy`：局部修改是否命中目标。
- `non_target_preservation`：非目标区域是否保持。
- `subject_replacement`：主体替换后的一致性；需要主体替换事实。
- `add_remove_object`：添加或删除物体是否成功。
- `video_extension`：续写视频的接缝与连续性；需要续写事实。
- `first_last_frame`：首帧和尾帧控制；需要相应输入帧。

## 第 15 维度：音频质量与控制

核心问题是对白、声音质量、音色、情绪和环境声音是否符合提示词。子项为：

- `dialogue_accuracy`：对白内容准确性。
- `voice_naturalness`：语音自然度。
- `timbre_consistency`：重复说话人或参考音色的一致性。
- `emotion_control`：对白情绪是否符合要求。
- `ambient_sound`：环境声音是否匹配。
- `action_sfx`：动作音效是否匹配。
- `music_match`：配乐存在性或禁止配乐要求。

## 第 16 维度：音画同步

核心问题是语音、口型、多人说话、音频变化和画面事件的时间对应关系。子项为：

- `lip_sync`：口型与对白同步；需要对白事实。
- `multi_speaker_match`：多人说话人和画面主体匹配。
- `audio_change_alignment`：音频变化与画面事件同步。
- `realism`：音画关系的自然和真实程度。

## 第 17 维度：运动与时序一致性

核心问题是运动、镜头、主体身份、时间连续性和人体动作是否稳定。子项为：

- `motion_consistency`：动作与运动轨迹连续。
- `camera_motion`：镜头运动是否符合要求；没有镜头运动要求时不适用。
- `subject_consistency`：主体在时间上的身份与结构一致。
- `temporal_continuity`：前后帧的时间连续性。
- `human_motion`：有人体时检查人体运动；无人体时不适用。

## 第 18 维度：文本与视觉一致性

核心问题是目标文字、字幕、可读性、稳定性和额外文字控制。子项为：

- `text_accuracy`：目标文字内容准确。
- `subtitle_alignment`：字幕是否完整并与内容对齐。
- `text_readability`：文字是否清晰可读。
- `text_stability`：文字在连续帧中是否稳定。
- `no_unrequested_text`：是否出现未要求的文字、水印或杂字。

## 三类清单对象

`facts` 是从 prompt 提取的结构化事实，决定子项是否适用以及需要检查的对象。`gates` 是评估门槛，决定视频是否进入正常组件评分。`items` 是绑定到子项的具体问题，由评委回答并映射到 1–5 分。

三者关系为：

```text
prompt -> facts -> applies 判断
prompt + dimension rules -> gates/items
video + gates/items -> answers
answers + numeric components -> subpoint scores -> dimension score
```

## 当前本地框架的可追溯性

每个 case 都保存这三类中间结果：

- `facts.json`：结构化事实。
- `checklist.json`：冻结清单，包括 `gates` 和 `items`。
- `answers.json`：评委回答与证据。

这样可以区分“需求事实识别错误”“门槛没有通过”“具体评分题没有通过”和“数值组件没有输入或没有安装”这几类问题。

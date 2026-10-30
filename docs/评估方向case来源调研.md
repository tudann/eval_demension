# 评估方向 case 来源调研

> 更新日期：2026-10-29  
> 依据：各项目 GitHub README 与 Hugging Face 数据集卡片、文件列表（当日抓取）。  
> 用法：回答两件事。一是公开项目怎么证明自己的评估方法可行；二是哪些项目放出了能直接拿来用的 case，尤其是带人工标签的 case。

## 1. 公开项目怎么证明方法可行

几乎所有项目走同一条路：先按维度写一套提示词，用若干个生成模型各出一批视频，请人对这些视频打分，再看自动方法的分数和人工分数是否一致。差别主要在人工怎么打、一致性怎么算。

| 做法 | 人工怎么打 | 一致性怎么算 | 代表项目 |
|---|---|---|---|
| 成对偏好 | 同一提示下两个模型的视频，人选哪个更好 | 自动分给出的胜负与人工选择的一致率，或按模型胜率算相关 | VBench（16 个维度各一份成对标注） |
| 分档打分 | 每条视频按 1–5 分打一个或几个维度 | Spearman、PLCC、Kendall，或二次加权 Kappa | VideoPhy-2、VideoFeedback2、FIRM-Video-Bench、MoChaBench、VE-Bench、DEVIL（Pearson 超过 0.9） |
| 规则逐条核对 | 人对每条视频逐项判「遵守 / 违反 / 无法判断」 | 自动裁判逐项判定的准确率 | VideoPhy-2 的物理规则、VTR-Bench 的 20 道检查题 |
| 专家标签 | 专业人员给类别标签（运镜类型、景别、崩坏区域） | 分类准确率、AP、分割重叠 | CameraBench、CineTechBench、BrokenVideos |
| 模型级排序 | 人给每个模型一个总体排名或均分 | 自动榜和人工榜的模型级相关 | PhyGenBench（表中带 Human 列）、WBench、DramaChain Bench（PLCC 0.918） |

两点值得注意。第一，模型级相关容易做高，单条视频级相关更能说明方法可用；我们要做的是「随机输入一条就评」，应该看单条级。第二，公开 case 几乎都是英文提示词、5 秒左右的单镜头，和本地中文、多镜头、带音频的业务样本分布差得远。

## 2. 各方向可用的公开 case

「人工标签」列说明能不能直接拿来验证方法：有标签的可以算我们的方法和人工的一致性；只有提示词或视频的只能用来出题或试跑。

### 2.1 内容与逻辑

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [FIRM-Video-Bench](https://huggingface.co/datasets/VisionXLab/FIRM-Video-Bench) | 250 条生成视频，附提示词和多家裁判模型的打分结果 | 有：指令遵循、画质、世界常识各 1–5 分 | 直接验证 D1 清单打分与人工的一致性 |
| [VideoFeedback2](https://huggingface.co/datasets/TIGER-Lab/VideoFeedback2) | 2933 条提示、22 个模型、27168 条视频 | 有：画质、文本对齐、物理常识三维人工分 | 取文本对齐一维做大样本验证 |
| [VBench 人工标注](https://huggingface.co/datasets/Vchitect/VBench_human_annotation) | 物体、多物体、颜色、空间关系、场景、整体一致等维度各一份 | 有：成对偏好（需登录同意） | 验证各子项的胜负判定 |
| [T2V-CompBench](https://github.com/KaiyueSun98/T2V-CompBench) | 700 条提示，七类组合题各 100 条，附多个模型的生成视频 | 论文做过人工相关，标签未见公开 | 出题，补 D1 清单漏掉的绑定和数量题 |
| [TiViBench](https://github.com/EnVision-Research/TiViBench) | 四类推理题的提示和首帧图 | 无 | 只在需要推理题时出题 |

### 2.2 画面观感

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| VideoFeedback2 | 同上 | 有：画质一维 | 验证 DOVER、Q-Align 与人工的单条级相关 |
| FIRM-Video-Bench | 同上 | 有：画质 1–5 分 | 小样本复核 |
| VBench 人工标注 | 美学、成像质量两份 | 有：成对偏好 | 验证胜负判定 |
| [EvalCrafter](https://github.com/evalcrafter/EvalCrafter) | 700 条提示、约 1 万条视频 | 有：8.6k 条人工反馈，覆盖 5 个方面 | 补充验证 |

### 2.3 时序与运动

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| VBench 人工标注 | 闪烁、运动平滑、动态度、主体和背景一致几份 | 有：成对偏好 | 验证防静帧和平滑指标 |
| [VMBench](https://github.com/AMAP-ML/VMBench) | 1050 条按六类运动写的提示 | 论文做过人工偏好对齐，标签未见公开 | 出运动题 |
| [DEVIL](https://github.com/MingXiangL/DEVIL) | 按动态强度分档的提示 | 论文报告与人工 Pearson 超过 0.9，标签未见公开 | 出不同动态强度的题 |

### 2.4 物理与空间

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [VideoPhy-2 测试集](https://huggingface.co/datasets/videophysics/videophy2_test) | 生成视频链接、提示、动作类别、难题子集 | 有：语义遵循和物理常识各 1–5 分，加逐条物理规则的遵守、违反、无法判断 | 最适合验证 D7：既能算分数相关，也能逐条核对违例判定 |
| VideoFeedback2 | 同上 | 有：物理常识一维 | 补充验证 |
| [WorldModelBench](https://huggingface.co/datasets/Efficient-Large-Model/worldmodelbench) | 350 条首帧图加指令，7 个领域 | 公开的是测试题；训练裁判用的人工标签未在此数据集里 | 出首帧生视频的物理题 |
| [PhyGenBench](https://github.com/OpenGVLab/PhyGenBench) | 160 条提示，27 条物理定律 | 只有模型级人工分 | 出题 |
| [Physics-IQ](https://github.com/google-deepmind/physics-IQ-benchmark) | 396 条实拍物理过程 | 有真实后半段作对照，不需要人工分 | 只用于续写类任务 |

### 2.5 主体一致

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [OpenS2V-Eval](https://huggingface.co/datasets/BestWishYsh/OpenS2V-Eval) | 180 条主体加文本（80 条真实、100 条合成），带参考图，附多个模型的生成视频 | 论文做过人工对齐，标签未见公开 | 直接拿来测参考图主体是否留住 |
| ConsisID-Bench（同仓库） | 150 张人脸参考图、90 条提示 | 无 | 测人脸身份保持 |
| VBench 人工标注 | 主体一致一份 | 有：成对偏好 | 验证无参考图时前后一致的判定 |

### 2.6 摄影与镜头

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [CameraBench 测试集](https://huggingface.co/datasets/syCen/CameraBench) | 1000 多条视频 | 有：专家运镜标签和描述 | 验证运镜判别准确率，重点看变焦和推镜头；视频来自网络，和生成视频分布不同 |
| [CineTechBench](https://github.com/PRIS-CV/CineTechBench) | 景别、角度、构图、运镜等专家标注 | 有，但只给原片链接，需自行下载 | 验证景别和构图判别 |
| [FilmOps](https://github.com/Neo-yk/FilmOps) | 只放出判别模型 | 无 | 作为判别器，不作 case 来源 |

### 2.7 条件与编辑

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [VE-Bench](https://github.com/littlespray/VE-Bench) 数据库 | 真实、AIGC、CG 三类源视频，多类编辑指令，8 种编辑方法的结果 | 有：每条编辑结果的人工分 | 验证编辑完成度和保留度的打分 |
| [IVEBench](https://huggingface.co/datasets/Coraxor/IVEBench) | 600 条源视频，8 大类 35 小类编辑指令 | 无 | 出编辑题 |
| [StreamEval](https://huggingface.co/datasets/StreamEval/StreamEval) | 编辑类 case 带期望结果（oracles） | 有期望终态，不是人工打分 | 借期望结果的写法 |

### 2.8 音频表现

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [AVGen-Bench](https://huggingface.co/datasets/microsoft/AVGen-Bench) | 11 类场景提示（广告、新闻、预告片、ASMR、乐器教学等），附多个模型的 3000 余条有声生成视频 | 未见人工标签 | 直接拿生成视频试跑音质、台词和同步指标 |
| [JavisBench](https://huggingface.co/datasets/JavisVerse/JavisBench) | 10140 条有声视频描述，19 类场景 | 无 | 出音画对齐题 |
| [seed-tts-eval](https://github.com/BytedanceSpeech/seed-tts-eval) | 中英文参考音频加目标文本 | 无，用转写和音色比对客观评 | 校准中文台词转写错误率和音色相似度 |
| [AV-DPO](https://huggingface.co/datasets/JavisVerse/AV-DPO) | 音画偏好对 | 有：偏好对 | 可验证音画质量和同步的偏好判定 |

### 2.9 文字信息

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [VTR-Bench](https://github.com/hardenyu21/VTR-Bench) | 300 条提示（广告、科学、界面、文化、日常各 60 条），1202 段指定文字，6000 道检查题，附多个模型的生成视频 | 有逐字参考文本和检查题 | 最适合本方向：可直接测逐字正确率和场景遵循；广告类贴近商用 |

### 2.10 表演与情绪

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [MoChaBench](https://github.com/congwei1230/MoChaBench) | 220 条对白提示加语音，覆盖独白、多人轮流说、情绪、动作、特写、竖屏等；附 MoCha 生成结果和首帧 | 有：人工多数票评分，仓库带一致性脚本 | 验证口型同步和表演判定，也是短剧对白场景的现成题 |

### 2.11 异常与可用性

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [BrokenVideos](https://huggingface.co/datasets/Chengming2/brokenvideo) | 约 3254 条 AI 生成视频 | 有：逐像素崩坏掩码（需申请） | 验证崩坏能否检出、定位是否准确 |
| [VBench-2.0 人体异常集](https://huggingface.co/datasets/Vchitect/VBench-2.0_human_anomaly) | 真实和 AIGC 视频 | 有：人体结构异常标注 | 验证手、脸、肢体类崩坏检测 |
| VideoPhy-2 测试集 | 同上 | 有：人写的额外违例 | 补充穿模、形变类样本 |

### 2.12 短剧大类

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| MoChaBench 多人轮流说、竖屏 | 见表演与情绪 | 有 | 短剧对白镜头的现成题 |
| [MovieBench](https://huggingface.co/datasets/weijiawu/MovieBench) | 基于 LSMDC 电影的分镜描述和角色库 | 无，描述由 GPT-4 生成 | 借角色库和分镜描述的结构，原片需自行获取 |
| DramaChain Bench | 5569 道三人标注的短剧全链路题 | 有 | 尚未开源，开源后是唯一现成的短剧人工标签 |
| MuSS | 多镜头叙事 | 无 | 数据和评测代码均未放出 |

### 2.13 长时与世界

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [WBench](https://huggingface.co/datasets/meituan-longcat/WBench) | 289 条多轮交互 case，另有现成生成视频样例 | 论文称 22 项自动指标经人工判断验证，标签未见公开 | 借多轮长视频的 case 写法 |
| StreamEval | 15–300 秒会话，case 带输入时间线和期望结果 | 有期望结果 | 借分段期望的写法 |
| [WorldScore](https://github.com/haoyi-duan/WorldScore) | 场景图加相机路径 | 无 | 只用于世界生成类 |

### 2.14 商用风险

| 数据 | 内容 | 人工标签 | 用法 |
|---|---|---|---|
| [SafeWatch-Bench](https://huggingface.co/datasets/Virtue-AI-HUB/SafeWatch-Bench) | 生成视频按风险大类和子类分组，每组含正常样本 | 有：风险类别标签（需申请） | 验证违规内容判定的准确率和误报 |
| [T2VSafetyBench](https://github.com/yibo-miao/T2VSafetyBench) | 14 类风险提示，含越狱改写 | 无 | 出风险题 |
| [GenVidBench](https://huggingface.co/datasets/jian-0/GenVidBench) | 678 万条真实与生成视频 | 有真伪标签 | 只用于 AI 生成检测 |
| 品牌、肖像授权、广告文案 | 无公开 case | 无 | 需自建 |

## 3. 本地已有的 case

| 数据 | 内容 | 人工标签 |
|---|---|---|
| `data/300case/中文三任务300条基准集 V2.csv` | 300 条真实中文提示，分文生、首帧生、参考生三种任务 | 无 |
| `docs/第1-18维度case表.md` | 从上面 300 条里按维度挑出的 case：第 1–12 维各 17 条，第 13–18 维各 16 条 | 无 |
| `data/固定回归case/` | 第 13–20 维的回归 case，约 230 条本地视频，`case_video_results.csv` 384 行带视频地址 | 无 |
| `data/d13_d20_cases.csv` | 第 13–20 维 case 的输入参数和输出地址 | 无 |

本地 case 的长处是贴业务：中文、多镜头、带音频、有参考图。缺的是人工标签，所以只能证明方法「能跑」，不能证明方法「判得对」。

## 4. 结论：case 分三层来建

| 层 | 来源 | 作用 |
|---|---|---|
| 验证层 | 带人工标签的公开数据：VideoPhy-2、VideoFeedback2、FIRM-Video-Bench、VBench 人工标注、MoChaBench、VE-Bench、CameraBench、BrokenVideos、VBench-2.0 人体异常集、SafeWatch-Bench、VTR-Bench | 算我们的方法和人工的单条级一致性，回答「方法判得对不对」 |
| 出题层 | 只有提示词或参考数据的公开数据：T2V-CompBench、VMBench、DEVIL、PhyGenBench、WorldModelBench、OpenS2V-Eval、IVEBench、AVGen-Bench、JavisBench、T2VSafetyBench | 补齐本地样本缺的题型，用我们的模型出视频后试跑 |
| 业务层 | 本地 300 条中文提示和第 13–20 维回归 case | 抽一小批（每个方向约 30 条）做人工标注，确认方法在中文、多镜头、有声样本上仍然成立 |

现在没有带人工标签公开数据的方向有三个：短剧大类（等 DramaChain Bench 开源）、表演与情绪中脸上情绪这一块、商用风险中品牌、肖像和广告文案这一块。这三处只能靠业务层自建标注。

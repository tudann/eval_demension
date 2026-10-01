# 飞书视频案例

- 来源文档：[视频评测维度及case 副本](https://my.feishu.cn/wiki/UsBewLzp8if1zaktL7JcYHY5nnf)
- 选择范围：T2VA 2 条、R2VA 2 条；文档未提供可确认的 FL2VA 原始首尾帧条件，因此 FL2VA 保持为空。
- 视频统一选择文档中的 Agnes 2.5flash 生成结果。
- `metadata.json` 只记录来源和整理信息；评估框架实际读取每个 case 的 `prompt_final.txt`、`video.mp4`，以及对应模式允许的参考文件。

## 目录

```text
feishu_video_cases/
├── t2va/
│   ├── feishu_ad_perfume_ripple/
│   └── feishu_ad_perfume_packshot/
├── fl2va/              # 空：没有确认的原始首尾帧案例
└── r2va/
    ├── feishu_product_multiview_perfume/
    └── feishu_product_foldable_phone/
```

# 视频生产线 — 全自动视频制作流水线

一站式视频生产技能。输入素材 + 灵感文字 → 自动分析风格 → 学习对标博主 → 智能剪辑 → 字幕 → 成品。

## 快速开始

```bash
# 完整流程
python scripts/pipeline.py \
  --project-name "AI入门第一课" \
  --images E:/素材/*.png \
  --videos E:/素材/*.mp4 \
  --inspiration "今天教大家用AI写周报..."

# 干跑模式 (仅规划不生成)
python scripts/pipeline.py \
  --images E:/素材/*.png \
  --inspiration "AI工具对比" \
  --dry-run
```

## 架构

```
输入 (图片/视频/文字/参考链接)
  → ① 素材采集 → ② 内容分析 → ③ 风格学习(参考博主)
    → ④ 时间线规划 + 缺口检测
      → ⑤ AI视频生成(填补缺口)
    → ⑥ BGM匹配
  → ⑦ 剪辑引擎(FFmpeg合成)
  → ⑧ auto-caption(字幕)
  → E:/ 成品 + 自动打开剪映
```

## 依赖

- Python 3.10+
- FFmpeg
- Whisper (openai-whisper)
- yt-dlp, scenedetect, opencv-python, librosa
- 剪映专业版 (可选)

```bash
pip install yt-dlp "scenedetect[opencv]" librosa Pillow
```

## 配置

编辑 `config.json`：
- `pipeline.output_drive` — 默认输出盘符
- `ai_video` — AI视频生成API配置
- `bgm` — BGM库路径和匹配策略
- `editing` — 剪辑参数

## 内置风格

- `bilibili_ai_tutorial` — B站AI教程 (快节奏+高密度)
- `douyin_short` — 抖音短视频 (超快+竖屏)
- `documentary` — 纪录片风格 (慢节奏+电影感)
- `review` — 产品测评 (适中+干净)

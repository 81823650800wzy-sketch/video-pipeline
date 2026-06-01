# 视频生产线 — 全自动视频制作流水线

一站式视频生产技能。输入素材 + 灵感文字 → 自动分析风格 → 学习对标博主 → 智能剪辑 → 字幕 → 成品。

## 适用场景

- AI 教程/知识类视频批量生产
- 有素材积累，想快速出片
- 想模仿特定博主的剪辑风格
- 从灵感到成品的一键式视频制作

## 核心能力

| 阶段 | 功能 | 说明 |
|------|------|------|
| ① 素材采集 | 多模态输入 | 图片、视频、灵感文字、参考链接 |
| ② 内容分析 | 风格分类 | 自动判断 tutorial/vlog/documentary/review |
| ③ 风格学习 | 对标博主 | yt-dlp下载 + PySceneDetect分析 + 量化风格 |
| ④ 时间线 | 缺口检测 | 智能分配素材到时间线，检测缺失画面 |
| ⑤ AI补全 | 视频生成 | 缺口处自动生成AI视频(需API Key) |
| ⑥ BGM | 智能匹配 | 本地库/Pixabay/静音降级 |
| ⑦ 剪辑 | FFmpeg合成 | 转场 + Ken Burns + 调色 + 音轨混合 |
| ⑧ 字幕 | auto-caption | 复用现有字幕技能，输出SRT+成品 |

## 快速使用

```bash
# 完整流程
python ~/.claude/skills/video-pipeline/scripts/pipeline.py \
  --project-name "AI入门第一课" \
  --images E:/素材/*.png \
  --videos E:/素材/*.mp4 \
  --inspiration "今天教大家用AI写周报..."

# 干跑模式 (仅规划不生成)
python ~/.claude/skills/video-pipeline/scripts/pipeline.py \
  --images E:/素材/*.png \
  --inspiration "AI工具对比" \
  --dry-run

# 指定风格 + 参考博主
python ~/.claude/skills/video-pipeline/scripts/pipeline.py \
  --videos E:/素材/*.mp4 \
  --style bilibili_ai_tutorial \
  --reference "https://www.bilibili.com/video/BV..."
```

## 配置

编辑 `~/.claude/skills/video-pipeline/config.json`：
- `pipeline.output_drive` — 默认输出盘符
- `ai_video` — AI视频生成API配置
- `bgm` — BGM库路径和匹配策略
- `editing` — 剪辑参数（转场/调速/调色）
- `auto_caption` — 字幕模型和样式

## 内置风格预设

| 预设 | 适用 | 平台 | 节奏 |
|------|------|------|------|
| `bilibili_ai_tutorial` | AI教程 | B站 | 快节奏+高密度 |
| `douyin_short` | 短视频 | 抖音 | 超快+竖屏 |
| `documentary` | 深度内容 | 全平台 | 慢节奏+电影感 |
| `review` | 测评类 | B站 | 适中+干净 |

## 依赖

- Python 3.10+ + FFmpeg + Whisper
- yt-dlp + scenedetect + opencv-python + librosa (自动安装)
- 剪映专业版 (可选)

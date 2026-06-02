# ⚠️ 已迁移

此仓库已迁移到新地址：**[video-studio](https://github.com/81823650800wzy-sketch/video-studio)**

## 迁移说明

`video-pipeline` 和 `auto-caption` 已合并为统一的 `video-studio` skill。

新仓库提供两种模式：
- **caption** — 快速字幕处理
- **pipeline** — 完整视频生产线

## 使用新版本

```bash
# 字幕模式
python ~/.claude/skills/video-studio/scripts/video_studio.py caption video.mp4

# 生产线模式
python ~/.claude/skills/video-studio/scripts/video_studio.py pipeline \
  --project-name "项目名" --images ... --inspiration "..."
```

## 更新

```bash
cd ~/.claude/skills/video-studio
git pull
```

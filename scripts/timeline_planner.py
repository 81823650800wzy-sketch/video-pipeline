"""
时间线规划模块 — 构建逐镜头时间线 + 缺口检测
============================================
输入: manifest + content_analysis + style_profile
输出: timeline.json (每个镜头的精确时间、素材、效果)
"""

import json
from pathlib import Path

from utils import section, step, ok, warn, ensure_dir


def build_timeline(manifest, content, style_profile, project_dir, config):
    """构建完整的时间线"""
    section("Stage 4: 时间线规划")

    output_dir = ensure_dir(Path(project_dir) / "timeline")
    editing_cfg = config.get("editing", {})

    images = manifest.get("images", [])
    videos = manifest.get("videos", [])
    outline = content.get("outline", [])
    total_source_duration = sum(v.get("duration", 0) for v in videos)
    target_duration = content.get("target_duration", 60)

    style_editing = style_profile.get("editing", {})
    intro_dur = style_editing.get("intro_duration", editing_cfg.get("intro_duration", 3))
    outro_dur = style_editing.get("outro_duration", editing_cfg.get("outro_duration", 4))
    avg_shot = style_editing.get("avg_shot_duration", 5)
    trans_dist = style_editing.get("transition_distribution", {"cut": 0.8, "dissolve": 0.2})

    segments = []
    time_cursor = 0.0
    gap_index = 0

    # ----------------------------------------------------------
    # 1. 开场卡
    # ----------------------------------------------------------
    segments.append({
        "id": "intro",
        "type": "title_card",
        "start": 0.0,
        "end": intro_dur,
        "duration": intro_dur,
        "text": content.get("outline", [{}])[0].get("title", "开场") if outline else "开场",
        "transition_out": "dissolve",
    })
    time_cursor = intro_dur
    step(f"开场卡: 0.0s → {intro_dur:.1f}s")

    # ----------------------------------------------------------
    # 2. 内容段 — 分配素材到各章节
    # ----------------------------------------------------------
    content_sections = [o for o in outline if o.get("type") in ("content", "section")]
    available_videos = list(videos)
    available_images = list(images)

    for i, sec in enumerate(content_sections):
        sec_dur = sec.get("duration") or avg_shot
        title = sec.get("title", f"第{i+1}部分")

        # 尝试用视频
        if available_videos:
            vid = available_videos.pop(0)
            vid_dur = vid.get("duration", avg_shot)
            seg_dur = min(vid_dur, max(sec_dur, 3))
            segments.append({
                "id": f"seg_{i}",
                "type": "video",
                "asset_path": vid.get("dest_path") or vid.get("path"),
                "start": time_cursor,
                "end": time_cursor + seg_dur,
                "duration": seg_dur,
                "title": title,
                "transition_in": "dissolve" if i == 0 else "cut",
                "transition_out": "cut",
                "effects": [],
            })
            time_cursor += seg_dur
            step(f"[视频] {title[:30]} | {time_cursor-seg_dur:.1f}s → {time_cursor:.1f}s ({seg_dur:.1f}s)")
            continue

        # 尝试用图片 (Ken Burns)
        if available_images:
            img = available_images.pop(0)
            seg_dur = min(sec_dur, 6.0)
            segments.append({
                "id": f"seg_{i}",
                "type": "image_ken_burns",
                "asset_path": img.get("dest_path") or img.get("path"),
                "start": time_cursor,
                "end": time_cursor + seg_dur,
                "duration": seg_dur,
                "title": title,
                "transition_in": "dissolve",
                "transition_out": "dissolve",
                "effects": ["ken_burns"],
            })
            time_cursor += seg_dur
            step(f"[图片] {title[:30]} | {time_cursor-seg_dur:.1f}s → {time_cursor:.1f}s ({seg_dur:.1f}s)")
            continue

        # 缺口 — 没有匹配的素材
        gap_dur = min(sec_dur, 10.0)
        segments.append({
            "id": f"gap_{gap_index}",
            "type": "gap",
            "asset_path": None,
            "start": time_cursor,
            "end": time_cursor + gap_dur,
            "duration": gap_dur,
            "title": title,
            "description": f"需要展示: {title}",
            "suggested_prompt": _generate_gap_prompt(title, style_profile),
            "transition_in": "dissolve",
            "transition_out": "dissolve",
            "effects": [],
        })
        gap_index += 1
        time_cursor += gap_dur
        step(f"[缺口] {title[:30]} | {time_cursor-gap_dur:.1f}s → {time_cursor:.1f}s ({gap_dur:.1f}s)")

    # ----------------------------------------------------------
    # 3. 结尾卡
    # ----------------------------------------------------------
    segments.append({
        "id": "outro",
        "type": "title_card",
        "start": time_cursor,
        "end": time_cursor + outro_dur,
        "duration": outro_dur,
        "text": "感谢观看",
        "transition_in": "dissolve",
        "transition_out": "fade",
    })
    step(f"结尾卡: {time_cursor:.1f}s → {time_cursor + outro_dur:.1f}s")
    time_cursor += outro_dur

    # ----------------------------------------------------------
    # 4. 构建完整 Timeline
    # ----------------------------------------------------------
    gaps = [s for s in segments if s["type"] == "gap"]

    timeline = {
        "target_duration": time_cursor,
        "total_segments": len(segments),
        "gap_count": len(gaps),
        "segments": segments,
        "gaps": gaps,
        "source_duration_used": total_source_duration,
        "transitions": trans_dist,
        "global_style": style_profile.get("style_type", "tutorial"),
    }

    # 保存
    tl_path = output_dir / "timeline.json"
    with open(tl_path, "w", encoding="utf-8") as f:
        # 简化序列化
        json.dump(timeline, f, ensure_ascii=False, indent=2, default=str)
    ok(f"时间线: {len(segments)} 段, {len(gaps)} 缺口, {time_cursor:.0f}s 总长 → {tl_path}")

    return timeline


def _generate_gap_prompt(title, style_profile):
    """为缺口生成AI视频提示词"""
    style_name = style_profile.get("name", "")
    visual = style_profile.get("visual", {})
    palette = visual.get("color_palette", [])[:3]

    base = f"生成一段关于 '{title}' 的教学演示画面。"
    if "tutorial" in style_profile.get("style_type", ""):
        base += "干净简洁的界面操作演示，清晰的步骤展示。"
    elif "documentary" in style_profile.get("style_type", ""):
        base += "电影感画面，缓慢运镜，深邃色调。"
    else:
        base += "动态画面，明亮色调，适合短视频平台。"

    base += " 无水印，无文字叠加，画面流畅。"

    if palette:
        base += f" 色调参考: {'/'.join(palette)}"

    return base.strip()


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="时间线规划模块")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--output", default="E:/_test_timeline")
    args = parser.parse_args()

    if args.manifest:
        with open(args.manifest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {"images": [], "videos": [], "inspiration": "test"}

    content = {
        "style_key": "bilibili_ai_tutorial",
        "outline": [
            {"type": "intro", "title": "开场", "duration": 3},
            {"type": "content", "title": "核心教学", "duration": 20},
            {"type": "outro", "title": "总结", "duration": 4},
        ],
        "target_duration": 27,
    }
    style = {
        "editing": {"intro_duration": 3, "outro_duration": 4, "avg_shot_duration": 5,
                     "transition_distribution": {"cut": 0.8, "dissolve": 0.2}},
        "style_type": "tutorial",
    }
    config = {"editing": {"intro_duration": 3, "outro_duration": 4}}

    timeline = build_timeline(manifest, content, style, args.output, config)
    print(f"\nGenerated {len(timeline['segments'])} segments, {timeline['gap_count']} gaps")

"""
素材采集模块 — 多模态输入验证、元数据提取、项目目录构建
========================================================
接受: 图片列表 / 视频列表 / 灵感文字 / 参考链接
输出: input_manifest.json (所有素材的结构化目录)
"""

import json
import shutil
from pathlib import Path

from utils import (
    section, step, ok, warn, fail,
    ensure_dir, copy_to, get_video_info, get_image_info, sanitize_filename
)


def collect_inputs(
    images=None,
    videos=None,
    inspiration=None,
    inspiration_file=None,
    reference_urls=None,
    project_dir=None,
):
    """采集和验证所有输入素材，复制到项目目录，返回 manifest"""
    section("Stage 1: 素材采集")

    images = images or []
    videos = videos or []
    reference_urls = reference_urls or []
    inspiration = inspiration or ""

    # 读取灵感文字文件
    if inspiration_file:
        insp_path = Path(inspiration_file)
        if insp_path.exists():
            inspiration = insp_path.read_text(encoding="utf-8") + "\n" + inspiration
            step(f"读取灵感文件: {insp_path.name}")

    # 确保项目目录存在
    project_dir = ensure_dir(project_dir)
    assets_dir = ensure_dir(project_dir / "assets")
    images_dir = ensure_dir(assets_dir / "images")
    videos_dir = ensure_dir(assets_dir / "videos")

    # ========== 验证和收集图片 ==========
    step(f"图片: 收到 {len(images)} 个路径")
    collected_images = []
    for img_path in images:
        p = Path(img_path)
        if not p.exists():
            warn(f"图片不存在，跳过: {img_path}")
            continue
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
            warn(f"不支持的图片格式，跳过: {p.name}")
            continue
        info = get_image_info(p)
        if info["width"] > 0:
            dest = copy_to(p, images_dir)
            info["dest_path"] = str(dest)
            collected_images.append(info)
            step(f"  {p.name} ({info['width']}x{info['height']})")
        else:
            warn(f"无法读取图片: {p.name}")

    ok(f"有效图片: {len(collected_images)}")

    # ========== 验证和收集视频 ==========
    step(f"视频: 收到 {len(videos)} 个路径")
    collected_videos = []
    for vid_path in videos:
        p = Path(vid_path)
        if not p.exists():
            warn(f"视频不存在，跳过: {vid_path}")
            continue
        if p.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv"):
            warn(f"不支持的视频格式，跳过: {p.name}")
            continue
        info = get_video_info(p)
        if info["duration"] > 0:
            dest = copy_to(p, videos_dir)
            info["dest_path"] = str(dest)
            collected_videos.append(info)
            step(f"  {p.name} ({info['duration']:.1f}s, {info['width']}x{info['height']})")
        else:
            warn(f"无法读取视频: {p.name}")

    ok(f"有效视频: {len(collected_videos)}")

    # ========== 灵感文字 ==========
    if inspiration:
        step(f"灵感文字: {len(inspiration)} 字符")
        # 保存灵感文字到项目目录
        insp_dest = project_dir / "inspiration.txt"
        insp_dest.write_text(inspiration, encoding="utf-8")
        ok(f"灵感文字已保存: {insp_dest}")
    else:
        warn("未提供灵感文字")

    # ========== 参考链接 ==========
    if reference_urls:
        step(f"参考链接: {len(reference_urls)} 个")
        for url in reference_urls:
            step(f"  {url[:80]}...")

    # ========== 构建 manifest ==========
    total_duration = sum(v["duration"] for v in collected_videos)
    total_images = len(collected_images)

    if total_duration == 0 and total_images == 0:
        warn("没有任何有效的图片或视频素材！将只能生成纯文字内容")

    manifest = {
        "project_dir": str(project_dir),
        "assets_dir": str(assets_dir),
        "images": collected_images,
        "videos": collected_videos,
        "inspiration": inspiration,
        "inspiration_length_chars": len(inspiration),
        "reference_urls": reference_urls,
        "summary": {
            "image_count": total_images,
            "video_count": len(collected_videos),
            "total_video_duration": total_duration,
            "has_inspiration": bool(inspiration),
            "has_reference": bool(reference_urls),
        },
    }

    # 保存 manifest
    manifest_path = project_dir / "input_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    ok(f"素材清单: {manifest_path}")

    return manifest


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="素材采集模块")
    parser.add_argument("--images", nargs="*", default=[])
    parser.add_argument("--videos", nargs="*", default=[])
    parser.add_argument("--inspiration", default="")
    parser.add_argument("--output", default="E:/_test_project")
    args = parser.parse_args()
    manifest = collect_inputs(
        images=args.images,
        videos=args.videos,
        inspiration=args.inspiration,
        project_dir=args.output,
    )
    print("\nManifest summary:", json.dumps(manifest["summary"], indent=2))

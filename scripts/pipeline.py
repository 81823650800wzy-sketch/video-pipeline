#!/usr/bin/env python3
"""
视频生产线 — 全自动视频制作流水线
================================
输入: 图片 + 视频 + 灵感文字 + (可选)参考博主链接
输出: E盘成品视频 + SRT字幕 + 自动打开剪映

用法:
  python pipeline.py --project-name "AI入门第一课" \
    --images E:/素材/*.png --videos E:/素材/*.mp4 \
    --inspiration "今天教大家..." \
    --reference "https://www.bilibili.com/video/BV..."
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# 确保能找到同目录下的模块
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from config_manager import load_config, resolve_paths, validate_config, merge_with_cli
from utils import section, step, ok, warn, fail, ensure_dir, sanitize_filename, get_video_info, get_image_info


# ============================================================
#   CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="视频生产线 — 全自动视频制作流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整流程
  %(prog)s --project-name "AI入门第一课" \\
    --images E:/素材/1.png E:/素材/2.png \\
    --videos E:/素材/demo.mp4 \\
    --inspiration "今天教大家用AI写周报..."

  # 快速模式 (仅图片+文字)
  %(prog)s --images E:/素材/*.png --inspiration "AI工具介绍"

  # 带参考博主
  %(prog)s --videos E:/素材/*.mp4 \\
    --reference "https://www.bilibili.com/video/BV..."
        """,
    )
    parser.add_argument("--project-name", default=None,
                        help="项目名称 (默认自动生成)")
    parser.add_argument("--images", nargs="*", default=[],
                        help="输入图片路径列表")
    parser.add_argument("--videos", nargs="*", default=[],
                        help="输入视频路径列表")
    parser.add_argument("--inspiration", default=None,
                        help="灵感文字 (直接输入字符串)")
    parser.add_argument("--inspiration-file", default=None,
                        help="灵感文字文件路径 (.txt/.md)")
    parser.add_argument("--reference", nargs="*", default=[],
                        help="参考博主视频链接 (B站/抖音)")
    parser.add_argument("--style", default="auto",
                        choices=["auto", "bilibili_ai_tutorial", "douyin_short",
                                 "documentary", "review"],
                        help="视频风格 (默认: auto 自动检测)")
    parser.add_argument("--output", default=None,
                        help="输出目录 (默认: E:/成品/)")
    parser.add_argument("--no-open", action="store_true",
                        help="不自动打开剪映")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅分析和规划，不实际生成视频")
    return parser.parse_args()


# ============================================================
#  Stage 函数 — 导入真实模块
# ============================================================

def stage1_collect_inputs(images, videos, inspiration, inspiration_file, config):
    """Stage 1: 多模态素材采集"""
    from input_collector import collect_inputs as ci
    project_dir = ensure_dir(
        Path(config["pipeline"]["output_drive"]) / config.get("_project_name", "project"))
    return ci(
        images=images, videos=videos,
        inspiration=inspiration, inspiration_file=inspiration_file,
        project_dir=project_dir,
    )


def stage2_analyze_content(manifest, config):
    """Stage 2: 内容分析 + 风格分类"""
    from content_analyzer import analyze_content
    return analyze_content(manifest, config.get("_explicit_style", "auto"))


def stage3_learn_reference(reference_urls, content_style_key, project_dir, config):
    """Stage 3: 参考博主风格学习"""
    from reference_learner import learn_from_references
    return learn_from_references(reference_urls, content_style_key, project_dir, config)


def stage4_plan_timeline(manifest, content, reference, project_dir, config):
    """Stage 4: 时间线规划 + 缺口检测"""
    from timeline_planner import build_timeline
    return build_timeline(manifest, content, reference, project_dir, config)


def stage5_generate_ai_video(timeline, config):
    """Stage 5: AI视频补全缺口 (后续实现)"""
    gaps = timeline.get("gaps", [])
    if not gaps:
        step("无缺口，跳过AI视频生成")
        return timeline
    ai_cfg = config.get("ai_video", {})
    if not ai_cfg.get("enabled"):
        step("AI视频未启用，缺口将用文字卡片填充")
        return timeline
    return timeline


def stage6_select_bgm(style_profile, timeline, project_dir, config):
    """Stage 6: BGM匹配"""
    from bgm_manager import select_bgm
    return select_bgm(style_profile, timeline["target_duration"], project_dir, config)


def stage7_assemble(timeline, bgm, project_dir, config):
    """Stage 7: FFmpeg剪辑合成"""
    from editing_engine import assemble_timeline
    return assemble_timeline(timeline, bgm, project_dir, config)


def stage8_add_caption(video_path, config):
    """Stage 8: 字幕 + 剪映 (调用现有auto-caption skill)"""
    section("Stage 8: 字幕生成")
    import importlib.util

    ac_cfg = config.get("auto_caption", {})
    ac_path = Path(ac_cfg.get("skill_path",
        str(Path.home() / ".claude/skills/auto-caption"))).expanduser()
    ac_script = ac_path / "scripts" / "auto_caption.py"

    if not ac_script.exists():
        fail("auto-caption skill 未找到: {}" .format(ac_script))
        return video_path

    step("调用 auto-caption...")
    spec = importlib.util.spec_from_file_location("auto_caption", ac_script)
    auto_cap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auto_cap)

    result = auto_cap.process_video(
        video_path=video_path,
        model=ac_cfg.get("whisper_model", "small"),
        language=ac_cfg.get("language", "zh"),
        burn=ac_cfg.get("burn_subtitles", True),
        output_dir=video_path.parent,
        open_jianying=config.get("jianying", {}).get("auto_open", True)
    )
    captioned = result.get("captioned") or result.get("srt")
    ok("字幕完成: {}" .format(captioned))
    return Path(captioned) if captioned else video_path


# ============================================================
#  Main
# ============================================================

def main():
    args = parse_args()

    # 加载配置
    config = load_config()
    config = resolve_paths(config)
    config = merge_with_cli(config, vars(args))
    warnings = validate_config(config)
    for w in warnings:
        warn(w)

    # 项目名
    project_name = (args.project_name
                    or sanitize_filename(
                        args.inspiration[:30] if args.inspiration
                        else datetime.now().strftime("%Y%m%d_%H%M%S")))
    project_dir = ensure_dir(
        Path(config["pipeline"]["output_drive"]) / project_name)

    print(f"\n{'='*60}")
    print(f"  视频生产线 — 全自动视频制作流水线")
    print(f"{'='*60}")
    print(f"  项目: {project_name}")
    print(f"  输出: {project_dir}")
    print(f"  风格: {args.style}")
    print(f"  干跑: {'是' if args.dry_run else '否'}")
    print(f"{'='*60}")

    if args.dry_run:
        step("干跑模式 - 仅规划不生成")

    # ===== 流水线执行 =====
    manifest = stage1_collect_inputs(
        args.images, args.videos, args.inspiration, args.inspiration_file, config)
    content = stage2_analyze_content(manifest, config)
    reference = stage3_learn_reference(
        args.reference, content.get("style_key", "bilibili_ai_tutorial"),
        str(project_dir), config)
    # 使用参考学习的风格(如有)覆盖内容分析的风格
    style_profile = reference if reference else content.get("style_profile")
    timeline = stage4_plan_timeline(manifest, content, style_profile, str(project_dir), config)
    timeline = stage5_generate_ai_video(timeline, config)
    bgm = stage6_select_bgm(style_profile, timeline, str(project_dir), config)

    if not args.dry_run:
        assembly = stage7_assemble(timeline, bgm, project_dir, config)
        final = stage8_add_caption(assembly, config)

        print(f"\n{'='*60}")
        print(f"  生产完成!")
        print(f"{'='*60}")
        print(f"  成品: {final}")
        print(f"  项目: {project_dir}")
        print(f"{'='*60}\n")

        # 保存项目报告
        report = {
            "project_name": project_name,
            "timestamp": datetime.now().isoformat(),
            "style": content.get("style_profile", {}).get("name", ""),
            "output": str(final) if final else "",
            "config": config,
        }
        report_path = project_dir / "project_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        ok("项目报告: {}" .format(report_path))
    else:
        print(f"\n{'='*60}")
        print(f"  干跑完成 - 未生成视频")
        print(f"{'='*60}\n")

        # 保存timeline供检查
        tl_path = project_dir / "timeline_plan.json"
        with open(tl_path, "w", encoding="utf-8") as f:
            json.dump({"manifest": manifest, "content": content,
                        "timeline": timeline}, f, ensure_ascii=False, indent=2)
        ok("规划结果: {}" .format(tl_path))


if __name__ == "__main__":
    main()

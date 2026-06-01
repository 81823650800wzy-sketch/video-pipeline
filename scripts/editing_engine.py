"""
剪辑引擎模块 — FFmpeg 合成完整视频
=================================
执行时间线: 转场 + Ken Burns + 音轨混合 + 卡片生成
输出: assembly.mp4 (无字幕，后续由 auto-caption 处理)
"""

import tempfile
from pathlib import Path

from utils import section, step, ok, warn, fail, run_ffmpeg, ffprobe_get, ensure_dir


def _escape_filter_path(path_str):
    """转义FFmpeg滤镜路径中的冒号 (Windows C:/ → C\\:/)"""
    return str(path_str).replace("\\", "/").replace(":", "\\:")


def assemble_timeline(timeline, bgm, project_dir, config):
    """执行时间线，输出合成视频"""
    section("Stage 7: 剪辑合成")

    output_dir = ensure_dir(Path(project_dir) / "output")
    assembly_path = output_dir / "assembly.mp4"

    segments = timeline.get("segments", [])
    if not segments:
        fail("时间线为空")
        return None

    # 策略: 逐个处理片段 → concat 合成
    temp_dir = ensure_dir(Path(project_dir) / "temp" / "segments")
    processed = []

    for i, seg in enumerate(segments):
        seg_id = seg.get("id", f"seg_{i}")
        seg_path = temp_dir / f"{seg_id}.mp4"
        seg_dur = seg.get("duration", 5)

        if seg["type"] == "title_card":
            _render_title_card(seg, seg_path, config)
        elif seg["type"] in ("video",):
            _render_video_segment(seg, seg_path)
        elif seg["type"] in ("image_ken_burns",):
            _render_ken_burns(seg, seg_path)
        elif seg["type"] == "gap":
            _render_gap_card(seg, seg_path, config)
        else:
            warn(f"未知片段类型: {seg['type']}")

        if seg_path.exists() and seg_path.stat().st_size > 0:
            processed.append({
                "path": seg_path,
                "transition_out": seg.get("transition_out", "cut"),
                "duration": seg.get("duration", 0),
            })
        else:
            warn(f"片段 {seg_id} 渲染失败，跳过")

    if not processed:
        fail("所有片段渲染失败")
        return None

    # ===== concat 所有片段 =====
    step(f"合成 {len(processed)} 个片段...")

    # 使用系统临时目录避免中文路径编码问题
    import tempfile as tmpmod
    concat_tmp = Path(tmpmod.mkdtemp(prefix="vp_concat_"))
    concat_list = concat_tmp / "concat_list.txt"

    with open(concat_list, "w", encoding="utf-8") as f:
        for p in processed:
            # 复制片段到临时目录，用简单文件名
            safe_name = p['path'].name
            safe_dest = concat_tmp / safe_name
            import shutil as sh
            sh.copy(p['path'], safe_dest)
            f.write(f"file '{safe_dest.as_posix()}'\n")

    concat_video = concat_tmp / "concat_video.mp4"
    if not run_ffmpeg([
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(concat_video),
    ], "concat 视频片段", cwd=str(concat_tmp))[0]:
        fail("视频拼接失败")
        return None

    # 复制结果回项目目录
    import shutil as sh
    sh.copy(concat_video, temp_dir / "concat_video.mp4")
    concat_video = temp_dir / "concat_video.mp4"

    # ===== 添加 BGM =====
    if bgm and bgm.get("path") and Path(bgm["path"]).exists():
        bgm_path = Path(bgm["path"])
        mix_video = temp_dir / "mixed.mp4"
        duration_str = ffprobe_get(concat_video, "format=duration")
        total_dur = float(duration_str) if duration_str else timeline["target_duration"]

        step(f"混音: BGM + 人声 (闪避={bgm.get('ducking',{}).get('enabled',True)})")

        # 简单混合: BGM 降到背景音量
        bgm_volume = 0.2  # BGM 20% 音量

        run_ffmpeg([
            "-i", str(concat_video),
            "-stream_loop", "-1", "-i", str(bgm_path),
            "-t", str(total_dur),
            "-filter_complex",
            f"[1:a]volume={bgm_volume},afade=t=in:d={bgm.get('fade_in',1)},afade=t=out:st={total_dur-bgm.get('fade_out',2)}:d={bgm.get('fade_out',2)}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=0.5[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", config["pipeline"]["audio_bitrate"],
            str(mix_video),
        ], "混合BGM")
        final_path = mix_video
    else:
        final_path = concat_video

    # 复制到输出位置
    import shutil
    shutil.copy(final_path, assembly_path)
    ok(f"成品(无字幕): {assembly_path}")

    return assembly_path


def _render_title_card(seg, output_path, config):
    """生成标题卡片 (带静音音轨)"""
    text = seg.get("text", "标题")
    dur = seg.get("duration", 3)
    resolution = config["pipeline"]["resolution"]
    w, h = resolution["width"], resolution["height"]
    font_file = config.get("editing", {}).get("title_font",
        "C:/Windows/Fonts/msyh.ttc")

    # drawtext + 静音音轨
    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=0x1A1A2E:s={w}x{h}:d={dur}:r={config['pipeline']['fps']}",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(dur),
        "-vf", (
            f"drawtext=fontfile='{_escape_filter_path(font_file)}':"
            f"text='{text}':"
            f"fontsize=48:fontcolor=white:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:"
            f"shadowx=2:shadowy=2:shadowcolor=black@0.5"
        ),
        "-c:v", config["pipeline"]["video_codec"],
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-preset", config["pipeline"]["preset"],
        "-crf", str(config["pipeline"]["crf"]),
        "-pix_fmt", "yuv420p",
        str(output_path),
    ], f"标题卡: {text}")


def _render_video_segment(seg, output_path):
    """处理视频片段(裁剪+缩放)"""
    src = seg.get("asset_path", "")
    dur = seg.get("duration", 0)
    if not src or not Path(src).exists():
        _render_blank_segment(dur, output_path)
        return

    run_ffmpeg([
        "-i", str(src),
        "-t", str(dur),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ], f"视频片段: {Path(src).name}")


def _render_ken_burns(seg, output_path):
    """图片 Ken Burns 效果 (缓慢缩放)"""
    src = seg.get("asset_path", "")
    dur = seg.get("duration", 5)
    fps = 30

    if not src or not Path(src).exists():
        _render_blank_segment(dur, output_path)
        return

    run_ffmpeg([
        "-loop", "1", "-i", str(src),
        "-t", str(dur),
        "-vf", (
            f"scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='min(zoom+0.0008,1.1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps={fps}"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ], f"Ken Burns: {Path(src).name}")


def _render_gap_card(seg, output_path, config):
    """缺口 — 文字提示卡片"""
    title = seg.get("title", "概念讲解")
    dur = seg.get("duration", 8)
    font_file = config.get("editing", {}).get("title_font",
        "C:/Windows/Fonts/msyh.ttc")
    w, h = config["pipeline"]["resolution"]["width"], config["pipeline"]["resolution"]["height"]

    escaped_font = _escape_filter_path(font_file)
    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=0x16213E:s={w}x{h}:d={dur}:r=30",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(dur),
        "-vf", (
            f"drawtext=fontfile='{escaped_font}':"
            f"text='{title}':fontsize=42:fontcolor=#4ECDC4:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-30,"
            f"drawtext=fontfile='{escaped_font}':"
            f"text='(AI生成画面)':fontsize=24:fontcolor=#888888:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+40"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ], f"缺口卡: {title}")


def _render_blank_segment(duration, output_path):
    """黑色占位片段 (带静音)"""
    run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=black:s=1920x1080:d={duration}:r=30",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ], f"占位: {duration:.1f}s")


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="剪辑引擎模块")
    parser.add_argument("--timeline", default=None)
    parser.add_argument("--output", default="E:/_test_edit")
    args = parser.parse_args()

    if args.timeline:
        with open(args.timeline, "r", encoding="utf-8") as f:
            timeline = json.load(f)
    else:
        print("请提供 --timeline 参数")
        exit(1)

    bgm = {"path": None, "mode": "silent"}
    config = {
        "pipeline": {"resolution": {"width": 1920, "height": 1080}, "fps": 30,
                      "video_codec": "libx264", "audio_codec": "aac",
                      "audio_bitrate": "192k", "crf": 23, "preset": "medium"},
        "editing": {"intro_duration": 3, "outro_duration": 4,
                     "title_font": "C:/Windows/Fonts/msyh.ttc"},
    }

    result = assemble_timeline(timeline, bgm, args.output, config)
    if result:
        print(f"\nDone: {result}")
    else:
        print("\nFailed!")

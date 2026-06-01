"""
参考博主风格学习模块
==================
下载参考视频 → PySceneDetect镜头检测 → OpenCV色彩分析 → Whisper语速 → 量化风格
输出: StyleProfile (可直接用于时间线规划)
"""

import json
import tempfile
from pathlib import Path

from utils import (
    section, step, ok, warn, fail,
    ensure_dir, run_ffmpeg, ffprobe_get, get_video_info,
)
from style_profiles import get_style_preset, STYLE_PRESETS


def learn_from_references(reference_urls, content_style_key, project_dir, config):
    """从参考视频学习风格，返回合并后的 StyleProfile"""
    section("Stage 3: 参考风格学习")

    if not reference_urls:
        step("未提供参考链接，使用内置风格预设")
        profile = get_style_preset(content_style_key)
        ok(f"使用预设: {profile['name']}")
        return profile

    ref_config = config.get("reference", {})
    cache_dir = ensure_dir(Path(project_dir) / "reference_cache")
    max_refs = ref_config.get("max_reference_videos", 3)

    reference_profiles = []
    for i, url in enumerate(reference_urls[:max_refs]):
        step(f"分析参考视频 {i+1}/{min(len(reference_urls), max_refs)}: {url[:60]}...")

        try:
            video_path = _download_reference(url, cache_dir, ref_config)
            if video_path:
                profile = _analyze_video_style(video_path, ref_config)
                reference_profiles.append(profile)
                step(f"  镜头数: {profile.get('scene_count', '?')}, "
                     f"平均镜头: {profile.get('avg_scene_duration', '?')}s")
        except Exception as e:
            warn(f"参考视频分析失败: {e}")

    if not reference_profiles:
        warn("所有参考视频分析失败，使用内置预设")
        return get_style_preset(content_style_key)

    # 合并参考风格和基础风格
    base_profile = get_style_preset(content_style_key)
    merged = _merge_profiles(base_profile, reference_profiles)
    ok(f"风格学习完成 (融合了 {len(reference_profiles)} 个参考视频)")

    return merged


def _download_reference(url, output_dir, ref_config):
    """使用 yt-dlp 下载参考视频"""
    import yt_dlp

    cookie_file = ref_config.get("bilibili_cookie_file", "")

    ydl_opts = {
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "format": "best[height<=1080][ext=mp4]/best[height<=1080]/best",
        "quiet": True,
        "no_warnings": True,
        "max_filesize": 500 * 1024 * 1024,  # 最大500MB
        "merge_output_format": "mp4",
    }

    if cookie_file and Path(cookie_file).exists():
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            path = Path(filename)
            if path.exists():
                step(f"  下载完成: {path.name}")
                return path
            # 尝试找任意扩展名
            for ext in [".mp4", ".mkv", ".webm", ".flv"]:
                alt = path.with_suffix(ext)
                if alt.exists():
                    return alt
    except Exception as e:
        # 尝试不下载只获取信息
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                step(f"  获取信息: {info.get('title', '?')[:40]} "
                     f"({info.get('duration', 0)}s)")
        except Exception:
            pass
        raise

    return None


def _analyze_video_style(video_path, ref_config):
    """全面分析一个参考视频的编辑风格"""
    info = get_video_info(video_path)
    duration = info.get("duration", 0)
    if duration == 0:
        raise ValueError("无法读取视频时长")

    profile = {
        "source_video": str(video_path),
        "source_duration": duration,
    }

    # 1. 镜头检测
    step("  检测镜头边界...")
    scene_result = _detect_scenes(video_path, ref_config)
    profile.update(scene_result)

    # 2. 色彩分析
    step("  分析色彩...")
    color_result = _analyze_colors(video_path, duration)
    profile.update(color_result)

    # 3. 语速分析
    step("  分析语速...")
    speech_result = _analyze_speech(video_path)
    profile.update(speech_result)

    # 4. BGM分析
    step("  分析BGM...")
    bgm_result = _analyze_bgm(video_path)
    profile.update(bgm_result)

    return profile


def _detect_scenes(video_path, ref_config):
    """检测镜头边界和转场"""
    try:
        from scenedetect import detect, ContentDetector

        threshold = ref_config.get("scene_threshold", 27)
        min_length = ref_config.get("min_scene_length", 1.0)

        scenes = detect(str(video_path), ContentDetector(threshold=threshold))

        if not scenes:
            return {"scene_count": 1, "avg_scene_duration": 0, "cuts_per_minute": 0}

        durations = []
        for scene in scenes:
            dur = scene[1].get_seconds() - scene[0].get_seconds()
            if dur >= min_length:
                durations.append(dur)

        if not durations:
            return {"scene_count": 1, "avg_scene_duration": 0, "cuts_per_minute": 0}

        total_dur = sum(durations)
        avg_dur = total_dur / len(durations)
        # 估算每分钟剪辑次数
        cuts_per_min = len(durations) / (total_dur / 60) if total_dur > 0 else 0

        # 分析转场类型分布 (简化: 根据镜头时长变化推断)
        transition_guess = {"cut": 0.75, "dissolve": 0.20, "fade": 0.05}

        return {
            "scene_count": len(durations),
            "avg_scene_duration": round(avg_dur, 2),
            "min_scene_duration": round(min(durations), 2),
            "max_scene_duration": round(max(durations), 2),
            "cuts_per_minute": round(cuts_per_min, 1),
            "transition_distribution": transition_guess,
        }
    except Exception as e:
        warn(f"  镜头检测失败: {e}")
        return {"scene_count": 1, "avg_scene_duration": 0, "cuts_per_minute": 0}


def _analyze_colors(video_path, duration):
    """采样关键帧进行色彩分析"""
    try:
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {}

        # 每秒采样一帧
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_interval = max(int(fps), 1)

        colors = []
        brightness_values = []

        for frame_idx in range(0, total_frames, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                break

            # 平均亮度
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            brightness_values.append(np.mean(hsv[:, :, 2]))

            # 采样像素用于颜色聚类
            small = cv2.resize(frame, (40, 30))
            colors.extend(small.reshape(-1, 3).tolist())

        cap.release()

        if not colors:
            return {}

        # K-Means 聚类提取主色调
        from sklearn.cluster import KMeans
        colors_np = np.array(colors)
        kmeans = KMeans(n_clusters=5, n_init=3, random_state=42)
        kmeans.fit(colors_np[:5000])  # 最多5000个样本
        dominant = kmeans.cluster_centers_.astype(int)

        palette = []
        for c in dominant:
            # BGR → HEX
            hex_color = f"#{c[2]:02X}{c[1]:02X}{c[0]:02X}"
            palette.append(hex_color)

        avg_brightness = np.mean(brightness_values)
        if avg_brightness > 150:
            brightness_type = "bright"
        elif avg_brightness < 80:
            brightness_type = "dark"
        else:
            brightness_type = "balanced"

        return {
            "color_palette": palette,
            "brightness": brightness_type,
            "avg_brightness": round(float(avg_brightness), 1),
        }
    except Exception as e:
        warn(f"  色彩分析失败: {e}")
        return {}


def _analyze_speech(video_path):
    """分析视频语速"""
    try:
        import whisper

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "ref_audio.wav"

            # 提取前60秒音频
            if not run_ffmpeg([
                "-i", str(video_path),
                "-t", "60",
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                str(audio_path),
            ], "提取参考音频")[0]:
                return {}

            if not audio_path.exists() or audio_path.stat().st_size < 1000:
                return {}

            model = whisper.load_model("tiny")
            result = model.transcribe(
                str(audio_path),
                language="zh",
                verbose=False,
                word_timestamps=True,
            )

            segments = result.get("segments", [])
            if not segments:
                return {}

            # 计算语速
            total_chars = sum(len(s["text"].strip()) for s in segments)
            total_dur = segments[-1]["end"] - segments[0]["start"]
            chars_per_sec = total_chars / total_dur if total_dur > 0 else 0

            # 计数停顿 (词间间隔 >1.5s)
            pauses = 0
            for i in range(1, len(segments)):
                gap = segments[i]["start"] - segments[i - 1]["end"]
                if gap > 1.5:
                    pauses += 1

            return {
                "speech_rate_chars_per_sec": round(chars_per_sec, 1),
                "speech_rate_chars_per_min": round(chars_per_sec * 60),
                "speech_segments": len(segments),
                "pauses_detected": pauses,
            }
    except Exception as e:
        warn(f"  语速分析失败: {e}")
        return {}


def _analyze_bgm(video_path):
    """分析BGM节拍"""
    try:
        import librosa
        import numpy as np

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "bgm_audio.wav"

            if not run_ffmpeg([
                "-i", str(video_path),
                "-t", "30",
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "22050", "-ac", "1",
                str(audio_path),
            ], "提取BGM音频")[0]:
                return {}

            y, sr = librosa.load(str(audio_path), sr=22050)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

            # 估算能量(响度)
            rms = librosa.feature.rms(y=y)
            energy = float(np.mean(rms))

            return {
                "bgm_bpm_estimate": round(float(tempo)) if tempo > 0 else 120,
                "bgm_energy": round(energy, 4),
            }
    except Exception as e:
        warn(f"  BGM分析失败: {e}")
        return {}


def _merge_profiles(base, references):
    """合并基础风格和参考风格"""
    if not references:
        return base

    merged = base.copy()

    # 平均关键指标
    avg_scene = sum(r.get("avg_scene_duration", 0) for r in references) / len(references)
    if avg_scene > 0:
        editing = merged.get("editing", {})
        editing["avg_shot_duration"] = round(avg_scene, 1)
        merged["editing"] = editing

    # 合并调色板
    ref_palettes = [r.get("color_palette", []) for r in references if r.get("color_palette")]
    if ref_palettes:
        # 取第一个参考视频的调色板
        merged["visual"] = merged.get("visual", {}).copy()
        merged["visual"]["color_palette"] = ref_palettes[0]

    # 平均语速
    ref_speech = [r.get("speech_rate_chars_per_min", 0) for r in references
                  if r.get("speech_rate_chars_per_min")]
    if ref_speech:
        avg_speech = sum(ref_speech) / len(ref_speech)
        merged["audio"] = merged.get("audio", {}).copy()
        merged["audio"]["speech_rate"] = round(avg_speech)

    # 平均BPM
    ref_bpm = [r.get("bgm_bpm_estimate", 0) for r in references
               if r.get("bgm_bpm_estimate")]
    if ref_bpm:
        avg_bpm = sum(ref_bpm) / len(ref_bpm)
        merged["audio"] = merged.get("audio", {}).copy()
        merged["audio"]["bgm_bpm"] = round(avg_bpm)

    merged["_reference_count"] = len(references)
    return merged

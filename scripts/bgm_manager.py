"""
BGM管理模块 — 智能匹配/选择背景音乐
==================================
策略: 本地库优先 → Pixabay API → 静音降级
"""

import json
import random
from pathlib import Path

from utils import section, step, ok, warn, ensure_dir


def select_bgm(style_profile, target_duration, project_dir, config):
    """为视频匹配合适的BGM"""
    section("Stage 6: BGM匹配")

    bgm_cfg = config.get("bgm", {})
    audio_style = style_profile.get("audio", {})
    target_bpm = audio_style.get("bgm_bpm", bgm_cfg.get("default_bpm", 120))
    target_mood = audio_style.get("bgm_mood", bgm_cfg.get("default_mood", "upbeat_tech"))
    mode = bgm_cfg.get("mode", "local_first")

    step(f"目标: BPM≈{target_bpm}, 氛围={target_mood}, 时长={target_duration:.0f}s")

    result = {
        "path": None,
        "bpm": target_bpm,
        "mood": target_mood,
        "duration": target_duration,
        "mode": "silent",
        "ducking": bgm_cfg.get("ducking", {"enabled": True}),
        "fade_in": bgm_cfg.get("fade", {}).get("in_seconds", 1.5),
        "fade_out": bgm_cfg.get("fade", {}).get("out_seconds", 2.0),
        "volume_db": -12,
    }

    # 1. 尝试本地库
    if mode in ("local_first", "local_only"):
        local_dir = Path(bgm_cfg.get("local_library_dir",
            str(Path.home() / ".claude/skills/video-pipeline/bgm_library"))).expanduser()
        local_dir = ensure_dir(local_dir)

        local_tracks = _scan_local_library(local_dir)
        if local_tracks:
            step(f"本地库: {len(local_tracks)} 首曲目")
            match = _best_match(local_tracks, target_bpm, target_mood, target_duration)
            if match:
                result["path"] = match["path"]
                result["bpm"] = match.get("bpm", target_bpm)
                result["mode"] = "local"
                result["source_name"] = match.get("filename", "")
                step(f"  匹配: {match.get('filename', '?')} (BPM={match.get('bpm','?')}, "
                     f"氛围={match.get('mood','?')})")
                ok(f"BGM已选: {result['source_name']}")
                return result
            step("  本地库无匹配曲目")

    # 2. 尝试 Pixabay API
    pixabay_key = bgm_cfg.get("pixabay_api_key", "")
    if mode not in ("local_only",) and pixabay_key:
        step("搜索 Pixabay 音乐库...")
        pix_track = _search_pixabay(target_mood, target_bpm, target_duration, pixabay_key)
        if pix_track:
            result.update(pix_track)
            result["mode"] = "pixabay"
            ok(f"BGM已选(Pixabay): {result.get('source_name', '?')}")
            return result

    # 3. 静音降级
    warn("无可用BGM，使用静音模式")
    ok("BGM: 静音 (语音独白)")
    return result


def _scan_local_library(lib_dir):
    """扫描本地BGM库"""
    catalog_path = Path(lib_dir) / "catalog.json"
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
            # 添加完整路径
            for name, info in catalog.items():
                info["path"] = str(Path(lib_dir) / name)
                info["filename"] = name
            return list(catalog.values())
        except Exception:
            pass

    # 无catalog，直接扫描音频文件
    tracks = []
    for ext in (".mp3", ".wav", ".ogg", ".m4a", ".flac"):
        for f in lib_dir.glob(f"*{ext}"):
            tracks.append({
                "path": str(f),
                "filename": f.name,
                "bpm": 120,  # 默认
                "mood": "general",
                "duration": 180,
            })
    return tracks


def _best_match(tracks, target_bpm, target_mood, target_duration):
    """找到最佳匹配曲目"""
    if not tracks:
        return None

    scored = []
    for t in tracks:
        score = 0

        # BPM匹配 (越近越好)
        track_bpm = t.get("bpm", 120)
        bpm_diff = abs(track_bpm - target_bpm)
        if bpm_diff < 10:
            score += 3
        elif bpm_diff < 30:
            score += 1

        # 氛围匹配
        track_mood = t.get("mood", "general")
        if track_mood == target_mood:
            score += 3
        elif target_mood in track_mood or track_mood in target_mood:
            score += 1

        # 时长匹配 (曲目至少是目标时长的60%)
        track_dur = t.get("duration", 180)
        if track_dur >= target_duration * 0.6:
            score += 2

        scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_track = scored[0]

    if best_score >= 2:
        return best_track
    # 分数太低但至少有一首
    if scored:
        return scored[0][1]
    return None


def _search_pixabay(mood, bpm, duration, api_key):
    """搜索 Pixabay 音乐库"""
    try:
        import requests
        mood_map = {
            "upbeat_tech": "upbeat",
            "energetic": "upbeat",
            "calm": "ambient",
            "cinematic": "cinematic",
            "neutral_tech": "corporate",
        }
        q = mood_map.get(mood, "upbeat")
        url = f"https://pixabay.com/api/music/?key={api_key}&q={q}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        hits = data.get("hits", [])
        if hits:
            track = hits[0]
            return {
                "path": track.get("previewURL", ""),
                "bpm": bpm,
                "source_name": track.get("title", "Pixabay Track"),
                "download_url": track.get("previewURL", ""),
            }
    except Exception as e:
        warn(f"  Pixabay搜索失败: {e}")
    return None


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BGM管理模块")
    parser.add_argument("--duration", type=float, default=60, help="视频时长(秒)")
    args = parser.parse_args()

    style = {"audio": {"bgm_bpm": 120, "bgm_mood": "upbeat_tech"}}
    config = {"bgm": {"mode": "local_first", "default_bpm": 120, "default_mood": "upbeat_tech",
                       "local_library_dir": "~/.claude/skills/video-pipeline/bgm_library",
                       "ducking": {"enabled": True}, "fade": {"in_seconds": 1.5, "out_seconds": 2.0}}}

    result = select_bgm(style, args.duration, "E:/_test", config)
    print(f"\nSelected: mode={result['mode']}, path={result.get('path', 'silent')}")

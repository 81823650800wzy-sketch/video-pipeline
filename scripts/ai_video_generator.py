"""
AI视频生成模块 — 缺口自动补全 (占位模块，待API Key启用)
=====================================================
当素材不够时，自动生成AI视频填充时间线缺口。
提供商: DashScope Wan 2.7 > Kling 3.0 > Seedance 2.0

启用方法:
  1. 获取API Key (dashscope.aliyun.com 或 klingai.com)
  2. 填入 ~/.claude/skills/video-pipeline/config.json 的 ai_video 部分
  3. 设置 ai_video.enabled = true
"""

import json
import time
from pathlib import Path

from utils import section, step, ok, warn, fail, ensure_dir


def generate_gap_clips(gaps, style_profile, project_dir, config):
    """为缺口生成AI视频片段"""
    section("Stage 5: AI视频补全")

    ai_cfg = config.get("ai_video", {})
    if not ai_cfg.get("enabled"):
        step("AI视频未启用，缺口将用文字卡片填充")
        return {}

    providers = ai_cfg.get("provider_priority", ["dashscope", "kling", "seedance"])
    output_dir = ensure_dir(Path(project_dir) / "ai_generated")

    results = {}
    for gap in gaps:
        gap_id = gap.get("id", "gap_0")
        prompt = gap.get("suggested_prompt", gap.get("description", ""))

        step(f"生成缺口 {gap_id}: {gap.get('title', '')[:30]}...")
        step(f"  Prompt: {prompt[:80]}...")

        clip = None
        for provider in providers:
            step(f"  尝试 {provider}...")
            clip = _try_generate(provider, prompt, gap.get("duration", 5), output_dir, ai_cfg)
            if clip:
                results[gap_id] = clip
                ok(f"  生成成功: {clip}")
                break
            warn(f"  {provider} 调用失败")

        if not clip:
            warn(f"  缺口 {gap_id} 无法填充，将使用文字卡片")

    ok(f"AI视频生成: {len(results)}/{len(gaps)} 个缺口已填充")
    return results


def _try_generate(provider, prompt, duration, output_dir, ai_cfg):
    """尝试调用某个AI视频API"""
    if provider == "dashscope":
        return _call_dashscope(prompt, duration, output_dir, ai_cfg.get("dashscope", {}))
    elif provider == "kling":
        return _call_kling(prompt, duration, output_dir, ai_cfg.get("kling", {}))
    elif provider == "seedance":
        return _call_seedance(prompt, duration, output_dir, ai_cfg.get("seedance", {}))
    return None


def _call_dashscope(prompt, duration, output_dir, cfg):
    """调用阿里云 DashScope Wan 2.7 API"""
    api_key = cfg.get("api_key", "")
    if not api_key:
        return None

    try:
        import requests

        endpoint = cfg.get("endpoint",
            "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis")

        body = {
            "model": cfg.get("model", "wan2.7-t2v"),
            "input": {
                "prompt": prompt,
                "negative_prompt": "blurry, distorted, watermark, text",
            },
            "parameters": {
                "duration": min(duration, 10),
                "resolution": "1080p",
            },
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 提交任务
        resp = requests.post(endpoint, json=body, headers=headers, timeout=30)
        data = resp.json()

        task_id = data.get("output", {}).get("task_id", "")
        if not task_id:
            return None

        # 轮询结果
        poll_interval = cfg.get("poll_interval", 5)
        max_attempts = cfg.get("max_poll_attempts", 60)

        for _ in range(max_attempts):
            time.sleep(poll_interval)
            status_resp = requests.get(
                f"{endpoint}/tasks/{task_id}",
                headers=headers,
                timeout=30,
            )
            status = status_resp.json()
            task_status = status.get("output", {}).get("task_status", "")

            if task_status == "SUCCEEDED":
                video_url = status.get("output", {}).get("video_url", "")
                if video_url:
                    return _download_video(video_url, output_dir, f"gap_dashscope_{task_id[:8]}.mp4")
            elif task_status == "FAILED":
                return None

    except Exception:
        pass

    return None


def _call_kling(prompt, duration, output_dir, cfg):
    """调用快手可灵 Kling 3.0 API"""
    api_key = cfg.get("api_key", "")
    if not api_key:
        return None

    try:
        import requests

        endpoint = cfg.get("endpoint", "https://api.klingai.com/v1/videos/text2video")

        body = {
            "model_name": cfg.get("model", "kling-v1-5"),
            "prompt": prompt,
            "duration": min(duration, 10),
            "mode": "std",
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(endpoint, json=body, headers=headers, timeout=30)
        data = resp.json()
        task_id = data.get("data", {}).get("task_id", "")

        if not task_id:
            return None

        # 轮询
        for _ in range(60):
            time.sleep(5)
            status_resp = requests.get(
                f"{endpoint}/{task_id}",
                headers=headers,
                timeout=30,
            )
            status = status_resp.json()
            state = status.get("data", {}).get("task_status", "")

            if state == "succeed":
                video_url = status.get("data", {}).get("task_result", {}).get("videos", [{}])[0].get("url", "")
                if video_url:
                    return _download_video(video_url, output_dir, f"gap_kling_{task_id[:8]}.mp4")
            elif state == "failed":
                return None

    except Exception:
        pass

    return None


def _call_seedance(prompt, duration, output_dir, cfg):
    """调用字节跳动 Seedance 2.0 API (火山引擎)"""
    ak = cfg.get("access_key", "")
    sk = cfg.get("secret_key", "")
    if not ak or not sk:
        return None

    try:
        import requests
        # 火山引擎需要 AK/SK 签名，较复杂
        # 此处留接口，待后续实现完整签名逻辑
        step("  Seedance 签名逻辑待实现")
    except Exception:
        pass

    return None


def _download_video(url, output_dir, filename):
    """下载生成的视频"""
    try:
        import requests
        resp = requests.get(url, timeout=120)
        if resp.status_code == 200:
            output_path = Path(output_dir) / filename
            with open(output_path, "wb") as f:
                f.write(resp.content)
            if output_path.stat().st_size > 10000:  # 至少10KB
                return str(output_path)
    except Exception:
        pass
    return None

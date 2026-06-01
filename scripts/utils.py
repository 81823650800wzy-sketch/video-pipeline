"""
video-pipeline 公共工具模块
====================
FFmpeg 封装 / 路径处理 / 进度报告 / 日志
"""

import shutil
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

# Windows GBK 终端兼容
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# FFmpeg / FFprobe 路径检测
# ============================================================

def find_ffmpeg():
    """查找 FFmpeg 路径，优先 PATH，再搜索 winget 安装位置"""
    for name in ["ffmpeg", "ffprobe"]:
        if shutil.which(name):
            continue
        winget_base = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        if winget_base.exists():
            for candidate in winget_base.rglob(f"{name}.exe"):
                os.environ["PATH"] = str(candidate.parent) + os.pathsep + os.environ.get("PATH", "")
                break


find_ffmpeg()


def run_ffmpeg(args, desc="", cwd=None):
    """运行 FFmpeg 命令，返回 (success, stderr)"""
    # 使用完整路径，不依赖 PATH
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "warning"] + args
    if desc:
        print(f"  [ffmpeg] {desc}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    except FileNotFoundError:
        print(f"  ! ffmpeg not found: {ffmpeg_bin}")
        return False, "ffmpeg not found"
    stderr_out = result.stderr or ""
    if result.returncode != 0:
        print(f"  ! ffmpeg RC={result.returncode}: {stderr_out[:300]}")
    return result.returncode == 0, stderr_out


def ffprobe_get(path, key="format=duration"):
    """用 ffprobe 获取视频元数据"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", key,
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def get_video_info(path):
    """获取视频的综合信息"""
    path = Path(path)
    if not path.exists():
        return None
    duration_str = ffprobe_get(path, "format=duration")
    width_str = ffprobe_get(path, "stream=width")
    height_str = ffprobe_get(path, "stream=height")
    fps_str = ffprobe_get(path, "stream=r_frame_rate")
    # 安全解析帧率 (如 "25/1" → 25.0, "0/0" → 0)
    try:
        if fps_str and "/" in fps_str:
            a, b = fps_str.split("/", 1)
            fps = float(a) / float(b) if float(b) != 0 else 0
        else:
            fps = float(fps_str) if fps_str else 0
    except (ValueError, ZeroDivisionError):
        fps = 0

    return {
        "path": str(path),
        "filename": path.name,
        "duration": float(duration_str) if duration_str else 0,
        "width": int(width_str) if width_str else 0,
        "height": int(height_str) if height_str else 0,
        "fps": fps,
    }


def get_image_info(path):
    """获取图片尺寸"""
    from PIL import Image
    try:
        img = Image.open(path)
        w, h = img.size
        return {"path": str(path), "filename": Path(path).name, "width": w, "height": h}
    except Exception:
        return {"path": str(path), "filename": Path(path).name, "width": 0, "height": 0}


# ============================================================
# 路径和文件工具
# ============================================================

def ensure_dir(path):
    """确保目录存在"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)


def copy_to(src, dst_dir):
    """复制文件到目标目录，返回新路径"""
    import shutil as sh
    dst_dir = ensure_dir(dst_dir)
    dst = dst_dir / Path(src).name
    sh.copy2(src, dst)
    return dst


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    # 去掉非法字符，限制长度，去掉首尾空格和点(Windows不允许末尾点)
    cleaned = "".join(c for c in name if c not in r'<>:"/\|?*').strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned[:100] if cleaned else "untitled"


# ============================================================
# 进度和日志
# ============================================================

def section(title):
    """打印阶段标题"""
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


def step(msg):
    """打印步骤"""
    print(f"  → {msg}")


def ok(msg):
    """打印成功"""
    print(f"  ✓ {msg}")


def warn(msg):
    """打印警告"""
    print(f"  ! {msg}")


def fail(msg):
    """打印错误"""
    print(f"  ✗ {msg}")

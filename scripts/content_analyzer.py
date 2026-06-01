"""
内容分析模块 — 风格分类、大纲提取、复杂度评估
============================================
输入: input_manifest (含视频、图片、灵感文字)
输出: ContentAnalysis (风格类型、难度、大纲、关键主题)
"""

import json
import re
import tempfile
from pathlib import Path
from collections import Counter

from utils import section, step, ok, warn, run_ffmpeg
from style_profiles import STYLE_PRESETS, get_best_style_for


def analyze_content(manifest, style_hint="auto"):
    """分析素材内容，返回风格和结构信息"""
    section("Stage 2: 内容分析")

    inspiration = manifest.get("inspiration", "")
    videos = manifest.get("videos", [])
    images = manifest.get("images", [])

    # 1. 提取所有文字内容
    all_text = inspiration

    # 如果有视频，转写第一个视频的前30秒作为分析样本
    video_transcript = ""
    if videos:
        step("分析视频语音样本...")
        video_transcript = _sample_transcribe(videos[0]["dest_path"], max_duration=30)

    all_text += "\n" + video_transcript

    # 2. 风格分类
    style_key, style_profile = _classify_style(all_text, videos, images, style_hint)
    step(f"检测风格: {style_profile['name']}")

    # 3. 难度评估
    level = _assess_level(all_text)
    step(f"内容难度: {level}")

    # 4. 提取大纲
    outline = _extract_outline(inspiration, video_transcript, style_profile)
    step(f"提取大纲: {len(outline)} 个章节")
    for item in outline:
        if "title" in item:
            step(f"  [{item.get('type','')}] {item['title'][:50]}")

    # 5. 关键主题
    topics = _extract_topics(all_text)
    step(f"关键主题: {', '.join(topics[:8])}")

    # 6. 估算目标时长
    target_duration = _estimate_duration(inspiration, videos, images, outline, style_profile)
    step(f"预估成品时长: {target_duration:.0f}s ({target_duration/60:.1f}分钟)")

    result = {
        "style_key": style_key,
        "style_profile": style_profile,
        "level": level,
        "outline": outline,
        "topics": topics,
        "target_duration": target_duration,
        "has_video_transcript": bool(video_transcript),
        "total_source_duration": sum(v.get("duration", 0) for v in videos),
    }

    ok(f"内容分析完成 → {style_profile['name']} / {level} / {target_duration:.0f}s")

    return result


def _sample_transcribe(video_path, max_duration=30):
    """转写视频的前 N 秒作为分析样本"""
    try:
        import whisper
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "sample.wav"

            # 提取前 max_duration 秒音频
            run_ffmpeg([
                "-i", str(video_path),
                "-t", str(max_duration),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                str(audio_path),
            ], "采样音频")

            if not audio_path.exists() or audio_path.stat().st_size < 1000:
                return ""

            model = whisper.load_model("tiny")  # 用tiny模型快速分析
            result = model.transcribe(str(audio_path), language="zh", verbose=False, word_timestamps=False)
            return result.get("text", "") or ""

    except Exception as e:
        warn(f"语音采样失败: {e}")
        return ""


def _classify_style(text, videos, images, style_hint):
    """根据内容特征判断最合适的视频风格"""
    if style_hint and style_hint != "auto":
        return style_hint, STYLE_PRESETS.get(style_hint, STYLE_PRESETS["bilibili_ai_tutorial"])

    # 特征计数
    tutorial_signals = [
        "第一步", "第二步", "接下来", "我们来看", "首先", "然后",
        "教程", "教学", "学习", "入门", "新手", "小白",
        "打开", "点击", "选择", "设置", "配置", "输入",
        "代码", "命令", "安装", "运行", "执行", "参数",
    ]
    vlog_signals = [
        "我", "今天", "大家好", "欢迎", "这期",
        "日常", "生活", "体验", "感觉", "觉得",
    ]
    doc_signals = [
        "历史", "原理", "深度", "解析", "背后", "真相",
        "故事", "发展", "演变", "趋势", "未来", "影响",
    ]
    review_signals = [
        "评测", "测评", "对比", "优缺点", "性价比",
        "推荐", "不推荐", "值得", "表现", "性能",
    ]

    text_lower = text.lower()

    scores = {
        "bilibili_ai_tutorial": _count_signals(text_lower, tutorial_signals),
        "douyin_short": _count_signals(text_lower, tutorial_signals + vlog_signals) * 0.8,
        "documentary": _count_signals(text_lower, doc_signals),
        "review": _count_signals(text_lower, review_signals),
    }

    # 有视频素材 → 偏向 tutorial
    if videos:
        scores["bilibili_ai_tutorial"] *= 1.3
    # 只有图片 → 偏向 documentary 或 tutorial
    if images and not videos:
        scores["documentary"] *= 1.2

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "bilibili_ai_tutorial"  # 默认

    return best, STYLE_PRESETS[best]


def _count_signals(text, signals):
    """统计信号词出现次数"""
    return sum(1 for s in signals if s in text)


def _assess_level(text):
    """评估内容难度"""
    beginner_signals = ["小白", "零基础", "入门", "新手", "第一次", "基础", "简单"]
    advanced_signals = ["高级", "进阶", "原理", "源码", "底层", "架构", "优化", "深入"]

    beginner_count = _count_signals(text, beginner_signals)
    advanced_count = _count_signals(text, advanced_signals)

    if beginner_count > advanced_count + 2:
        return "beginner"
    elif advanced_count > beginner_count + 2:
        return "advanced"
    else:
        return "intermediate"


def _extract_outline(inspiration, transcript, style_profile):
    """从灵感文字和视频转写中提取内容大纲"""
    text = inspiration + "\n" + transcript
    if not text.strip():
        # 默认结构
        return [
            {"type": "intro", "title": "开场引入", "duration": style_profile["editing"]["intro_duration"]},
            {"type": "content", "title": "核心内容", "duration": 30},
            {"type": "outro", "title": "结尾总结", "duration": style_profile["editing"]["outro_duration"]},
        ]

    # 按段落和标点分句
    paragraphs = [p.strip() for p in text.replace("\r", "").split("\n") if p.strip()]

    # 尝试识别标题行（短句、以数字开头、包含冒号等）
    outline = []
    for para in paragraphs:
        if len(para) < 60 and (para[0].isdigit() or "：" in para or ":" in para or "。" not in para):
            outline.append({
                "type": "section",
                "title": para[:80],
                "duration": None,
            })
        elif len(para) > 20:
            outline.append({
                "type": "content",
                "title": para[:40] + "..." if len(para) > 40 else para,
                "duration": None,
            })

    # 确保有开头和结尾
    if not outline or outline[0].get("type") != "intro":
        outline.insert(0, {"type": "intro", "title": "开场", "duration": style_profile["editing"]["intro_duration"]})

    if outline[-1].get("type") != "outro":
        outline.append({"type": "outro", "title": "结尾", "duration": style_profile["editing"]["outro_duration"]})

    # 限制最大章节数
    if len(outline) > 15:
        outline = outline[:7] + outline[-3:]

    return outline


def _extract_topics(text):
    """提取关键主题词"""
    # 中文常见停用词
    stopwords = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
                 "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
                 "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "怎么", "如何", "可以",
                 "这个", "那个", "就是", "然后", "所以", "因为", "但是", "而且", "如果", "虽然",
                 "我们", "他们", "已经", "还是", "或者", "应该", "不过", "还是", "比较", "今天"}

    # 简单分词：提取2-4字词组
    words = []
    # 按标点切分
    segments = re.split(r'[，。！？；、\s,\.!\?;\n]+', text)
    for seg in segments:
        seg = seg.strip()
        if len(seg) >= 2 and seg not in stopwords:
            # 尝试提取2-4字的关键词组
            if len(seg) <= 6:
                words.append(seg)
            else:
                # 滑窗提取2-4字词组
                for i in range(len(seg) - 1):
                    for wlen in [2, 3, 4]:
                        w = seg[i:i+wlen]
                        if w not in stopwords and len(w) >= 2:
                            words.append(w)

    # 取频率最高的
    counter = Counter(words)
    return [w for w, _ in counter.most_common(15)]


def _estimate_duration(inspiration, videos, images, outline, style_profile):
    """估算目标视频时长"""
    # 基础: 按大纲章节估算
    section_count = len([o for o in outline if o.get("type") == "content"])
    base_duration = section_count * 15  # 每节约15秒

    # 灵感文字长度影响
    insp_chars = len(inspiration)
    if insp_chars > 100:
        # 中文语速约250字/分钟
        base_duration += insp_chars / 250 * 60

    # 素材时长影响
    video_dur = sum(v.get("duration", 0) for v in videos)
    if video_dur > 0:
        base_duration = max(base_duration, video_dur * 0.8)  # 至少用80%素材

    # 图片数量影响
    img_count = len(images)
    if img_count > 0:
        base_duration = max(base_duration, img_count * 5)  # 每张图5秒

    # 限制范围
    base_duration = max(15, min(base_duration, 1800))  # 15秒 ~ 30分钟

    return round(base_duration)


# ============================================================
# CLI 测试入口
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="内容分析模块")
    parser.add_argument("--manifest", default=None, help="input_manifest.json 路径")
    parser.add_argument("--inspiration", default="", help="灵感文字")
    args = parser.parse_args()

    if args.manifest:
        with open(args.manifest, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {
            "videos": [],
            "images": [],
            "inspiration": args.inspiration,
        }

    result = analyze_content(manifest)
    print("\n=== 分析结果 ===")
    print(json.dumps({
        "style": result["style_key"],
        "level": result["level"],
        "duration": result["target_duration"],
        "topics": result["topics"],
        "outline": result["outline"],
    }, ensure_ascii=False, indent=2))

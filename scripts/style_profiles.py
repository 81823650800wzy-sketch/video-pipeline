"""
视频风格预设 — 当用户未提供参考视频时的内置风格模板
"""

STYLE_PRESETS = {
    # ============================================================
    # B站 AI教程 通用风格
    # ============================================================
    "bilibili_ai_tutorial": {
        "name": "B站AI教程通用风格",
        "platform": "bilibili",
        "style_type": "tutorial",
        "description": "适用于B站知识区AI教学视频，快节奏+高信息密度+清晰字幕",

        "editing": {
            "avg_shot_duration": 5.0,       # 平均镜头时长(秒)
            "min_shot_duration": 2.0,
            "max_shot_duration": 12.0,
            "transition_distribution": {
                "cut": 0.75,                # 硬切占75%
                "dissolve": 0.20,           # 叠化20%
                "fade": 0.05,               # 淡入淡出5%
            },
            "dissolve_duration": 0.4,       # 叠化时长(秒)
            "intro_duration": 3.0,          # 片头时长
            "outro_duration": 4.0,          # 片尾时长
        },

        "visual": {
            "color_palette": ["#1A1A2E", "#16213E", "#0F3460", "#E94560", "#FFFFFF"],
            "brightness": "balanced",       # bright / dark / balanced
            "saturation_boost": 1.1,        # 饱和度增强倍数
            "resolution": [1920, 1080],
            "ken_burns_on_images": True,    # 图片自动加Ken Burns效果
        },

        "subtitle": {
            "font_size": 22,
            "font_color": "&H00FFFFFF",     # 白色文字
            "outline_color": "&H00000000",  # 黑色描边
            "back_color": "&H80000000",     # 半透明黑底
            "position": "bottom",           # bottom / top / center
            "max_chars_per_line": 18,
            "highlight_keywords": True,     # 关键词高亮
        },

        "audio": {
            "speech_rate": 280,             # 目标语速(字/分钟)
            "bgm_bpm": 120,                 # BGM BPM
            "bgm_mood": "upbeat_tech",      # 氛围
            "bgm_volume_ratio": 0.2,        # BGM音量相对于人声
            "ducking_enabled": True,        # 人声时自动降BGM
        },

        "structure": [
            {"type": "intro", "duration": 3, "desc": "片头标题卡"},
            {"type": "hook", "duration": 5, "desc": "痛点/反常识引入"},
            {"type": "content", "duration": None, "desc": "干货讲解(可变长度)"},
            {"type": "demo", "duration": None, "desc": "实操演示"},
            {"type": "summary", "duration": 5, "desc": "总结要点"},
            {"type": "outro", "duration": 4, "desc": "引导关注+片尾"},
        ],
    },

    # ============================================================
    # 抖音短视频风格
    # ============================================================
    "douyin_short": {
        "name": "抖音短视频风格",
        "platform": "douyin",
        "style_type": "vlog",

        "editing": {
            "avg_shot_duration": 2.5,
            "min_shot_duration": 1.0,
            "max_shot_duration": 5.0,
            "transition_distribution": {"cut": 0.85, "dissolve": 0.10, "zoom": 0.05},
            "dissolve_duration": 0.2,
            "intro_duration": 1.5,
            "outro_duration": 2.0,
        },

        "visual": {
            "color_palette": ["#FF6B6B", "#FFE66D", "#4ECDC4", "#FFFFFF", "#2C3E50"],
            "brightness": "bright",
            "saturation_boost": 1.2,
            "resolution": [1080, 1920],     # 竖屏
            "ken_burns_on_images": True,
        },

        "subtitle": {
            "font_size": 26,
            "font_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "position": "center",
            "max_chars_per_line": 12,
            "highlight_keywords": True,
        },

        "audio": {
            "speech_rate": 320,
            "bgm_bpm": 130,
            "bgm_mood": "energetic",
            "bgm_volume_ratio": 0.3,
            "ducking_enabled": True,
        },

        "structure": [
            {"type": "hook", "duration": 3, "desc": "前3秒抓眼球"},
            {"type": "content", "duration": None, "desc": "快节奏干货"},
            {"type": "outro", "duration": 2, "desc": "引导互动"},
        ],
    },

    # ============================================================
    # 纪录片/深度风格
    # ============================================================
    "documentary": {
        "name": "纪录片深度风格",
        "platform": "bilibili",
        "style_type": "documentary",

        "editing": {
            "avg_shot_duration": 8.0,
            "min_shot_duration": 4.0,
            "max_shot_duration": 20.0,
            "transition_distribution": {"dissolve": 0.50, "fade": 0.30, "cut": 0.20},
            "dissolve_duration": 1.0,
            "intro_duration": 5.0,
            "outro_duration": 6.0,
        },

        "visual": {
            "color_palette": ["#2C3E50", "#34495E", "#7F8C8D", "#BDC3C7", "#ECF0F1"],
            "brightness": "dark",
            "saturation_boost": 0.9,
            "resolution": [1920, 1080],
            "ken_burns_on_images": True,
        },

        "subtitle": {
            "font_size": 18,
            "font_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "position": "bottom",
            "max_chars_per_line": 22,
            "highlight_keywords": False,
        },

        "audio": {
            "speech_rate": 220,
            "bgm_bpm": 80,
            "bgm_mood": "cinematic",
            "bgm_volume_ratio": 0.35,
            "ducking_enabled": True,
        },

        "structure": [
            {"type": "intro", "duration": 5, "desc": "氛围开场"},
            {"type": "background", "duration": None, "desc": "背景铺垫"},
            {"type": "deep_dive", "duration": None, "desc": "深度展开"},
            {"type": "reflection", "duration": None, "desc": "观点总结"},
            {"type": "outro", "duration": 6, "desc": "余韵结尾"},
        ],
    },

    # ============================================================
    # 产品测评风格
    # ============================================================
    "review": {
        "name": "产品测评风格",
        "platform": "bilibili",
        "style_type": "review",

        "editing": {
            "avg_shot_duration": 4.0,
            "min_shot_duration": 2.0,
            "max_shot_duration": 10.0,
            "transition_distribution": {"cut": 0.70, "dissolve": 0.20, "slide": 0.10},
            "dissolve_duration": 0.3,
            "intro_duration": 3.0,
            "outro_duration": 3.0,
        },

        "visual": {
            "color_palette": ["#FFFFFF", "#F5F5F5", "#2196F3", "#FF5722", "#4CAF50"],
            "brightness": "bright",
            "saturation_boost": 1.0,
            "resolution": [1920, 1080],
            "ken_burns_on_images": False,
        },

        "subtitle": {
            "font_size": 20,
            "font_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color": "&H80000000",
            "position": "bottom",
            "max_chars_per_line": 20,
            "highlight_keywords": True,
        },

        "audio": {
            "speech_rate": 260,
            "bgm_bpm": 110,
            "bgm_mood": "neutral_tech",
            "bgm_volume_ratio": 0.2,
            "ducking_enabled": True,
        },

        "structure": [
            {"type": "intro", "duration": 3, "desc": "产品亮相"},
            {"type": "features", "duration": None, "desc": "特性逐一讲解"},
            {"type": "pros_cons", "duration": None, "desc": "优缺点"},
            {"type": "verdict", "duration": 5, "desc": "购买建议"},
            {"type": "outro", "duration": 3, "desc": "互动引导"},
        ],
    },
}


def get_style_preset(style_key="bilibili_ai_tutorial"):
    """获取风格预设"""
    return STYLE_PRESETS.get(style_key, STYLE_PRESETS["bilibili_ai_tutorial"])


def list_styles():
    """列出所有可用的风格预设"""
    return [(k, v["name"], v["platform"]) for k, v in STYLE_PRESETS.items()]


def get_best_style_for(style_type, platform="bilibili"):
    """根据内容和平台推荐最佳风格"""
    # 精确匹配
    for key, preset in STYLE_PRESETS.items():
        if preset["style_type"] == style_type and preset["platform"] == platform:
            return key, preset
    # 仅匹配类型
    for key, preset in STYLE_PRESETS.items():
        if preset["style_type"] == style_type:
            return key, preset
    # 默认
    return "bilibili_ai_tutorial", STYLE_PRESETS["bilibili_ai_tutorial"]

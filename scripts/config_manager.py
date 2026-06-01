"""
配置管理 — 加载/合并/校验 pipeline 配置
"""

import json
from pathlib import Path


CONFIG_DIR = Path.home() / ".claude" / "skills" / "video-pipeline"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config():
    """加载 pipeline 配置"""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Config not found: {CONFIG_FILE}")
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    """保存配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def merge_with_cli(config, cli_args):
    """CLI 参数覆盖配置文件"""
    if cli_args.get("output_dir"):
        config.setdefault("pipeline", {})["output_drive"] = cli_args["output_dir"]
    if cli_args.get("project_name"):
        config["_project_name"] = cli_args["project_name"]
    return config


def resolve_paths(config):
    """展开配置中的路径 (~/ 等)"""
    p = config.get("pipeline", {})
    for key in ["output_drive", "project_base_dir", "temp_dir"]:
        if key in p:
            p[key] = str(Path(p[key]).expanduser())
    ac = config.get("auto_caption", {})
    if "skill_path" in ac:
        ac["skill_path"] = str(Path(ac["skill_path"]).expanduser())
    bgm = config.get("bgm", {})
    if "local_library_dir" in bgm:
        bgm["local_library_dir"] = str(Path(bgm["local_library_dir"]).expanduser())
    return config


def validate_config(config):
    """校验配置，返回警告列表"""
    warnings = []

    # 检查输出盘符
    out = config.get("pipeline", {}).get("output_drive", "")
    out_path = Path(out)
    if not out_path.exists():
        warnings.append(f"输出目录不存在: {out}，将自动创建")

    # 检查剪映路径
    jy = config.get("jianying", {}).get("exe_path", "")
    if jy and not Path(jy).exists():
        warnings.append(f"剪映路径不存在: {jy}")

    # 检查AI视频配置
    ai = config.get("ai_video", {})
    if ai.get("enabled"):
        providers = ai.get("provider_priority", [])
        has_key = False
        for p in providers:
            pcfg = ai.get(p, {})
            if pcfg.get("api_key") or pcfg.get("access_key"):
                has_key = True
                break
        if not has_key:
            warnings.append("AI视频已启用但无API Key，将自动禁用")
            ai["enabled"] = False

    return warnings

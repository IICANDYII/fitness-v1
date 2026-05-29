"""
Prompt loader — 从 prompts/ 目录读取 YAML prompt 文件。

用法:
    from prompts.prompt_loader import load_prompt
    system, user = load_prompt("workout_plan_generator", gender="female", age=24, ...)
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Any

import yaml

PROMPTS_DIR = Path(__file__).parent


def _latest_version(files: list[Path]) -> Path:
    """
    若同一 prompt 存在多个版本文件（如 foo_v1.0.0.yaml, foo_v1.1.0.yaml），
    返回语义版本最高的文件；否则直接返回唯一匹配。
    版本号从文件内 `version` 字段读取，文件名本身不需要带版本号。
    """
    if len(files) == 1:
        return files[0]

    def _ver_tuple(p: Path) -> tuple[int, ...]:
        try:
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            ver = str(data.get("version", "0.0.0"))
            return tuple(int(x) for x in ver.split("."))
        except Exception:
            return (0, 0, 0)

    return max(files, key=_ver_tuple)


def load_prompt(name: str, **kwargs: Any) -> tuple[str, str]:
    """
    按名称加载 prompt YAML，返回 (system, user) 两段已渲染的字符串。

    Args:
        name:    YAML 文件名（不含扩展名），支持通配如 "workout_plan_generator"
        **kwargs: 模板变量，用于替换 YAML 中的 {placeholder}

    Returns:
        (system_prompt, user_prompt)

    Raises:
        FileNotFoundError: 找不到匹配的 prompt 文件
        KeyError:          模板变量缺失
    """
    pattern = str(PROMPTS_DIR / f"{name}*.yaml")
    matched = [Path(p) for p in glob.glob(pattern)]
    if not matched:
        raise FileNotFoundError(f"No prompt file matching '{pattern}'")

    target = _latest_version(matched)

    with open(target, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    version = data.get("version", "?")
    system_tmpl: str = data.get("system", "")
    user_tmpl:   str = data.get("user", "")

    # str.format_map 允许模板中保留未提供的 {key}（不抛 KeyError）
    # 但我们希望明确检查，用 SafeMapper 报告缺失变量
    class _SafeMap(dict):
        def __missing__(self, key: str) -> str:
            raise KeyError(
                f"Prompt '{name}' (v{version}) requires variable '{{{key}}}' "
                f"but it was not provided to load_prompt()."
            )

    mapping = _SafeMap(**kwargs)
    system = system_tmpl.format_map(mapping)
    user   = user_tmpl.format_map(mapping)

    return system, user


def prompt_meta(name: str) -> dict:
    """返回 prompt 文件的元数据（version, description 等）。"""
    pattern = str(PROMPTS_DIR / f"{name}*.yaml")
    matched = [Path(p) for p in glob.glob(pattern)]
    if not matched:
        raise FileNotFoundError(f"No prompt file matching '{pattern}'")
    target = _latest_version(matched)
    with open(target, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {k: v for k, v in data.items() if k not in ("system", "user")}

"""
yaml_loader.py - 加载 Phase1 / Phase2 的 prompt 配置

扫描指定目录下的所有 .yaml 文件：
  - 文件名含 "phase1" → Phase 1 prompt
  - 文件名含 "phase2" → Phase 2 prompt

若存在多个同类文件，取 yaml 内 version 字段最大的那个。

返回 PromptConfig(system, user, version, name)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class PromptConfig:
    system: str
    user: str
    version: str
    name: str
    source_file: str


def _version_key(v: str) -> tuple:
    """将 "3.0" / "v3" / "4" 等格式统一转为可比较的元组。"""
    v = v.lstrip("v").lstrip("V")
    try:
        parts = [int(x) for x in v.split(".")]
        return tuple(parts)
    except ValueError:
        return (0,)


def load_prompt(yaml_path: str | Path) -> PromptConfig:
    """加载单个 yaml 文件，返回 PromptConfig。"""
    yaml_path = Path(yaml_path)
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    system = data.get("system", "").strip()
    user = data.get("user", "").strip()
    version = str(data.get("version", "0"))
    name = data.get("name", yaml_path.stem)

    if not system:
        raise ValueError(f"yaml 文件 {yaml_path} 缺少 system 字段")

    return PromptConfig(
        system=system,
        user=user,
        version=version,
        name=name,
        source_file=str(yaml_path),
    )


def load_prompts(prompts_dir: str | Path) -> tuple[PromptConfig, PromptConfig]:
    """
    扫描目录，返回 (phase1_prompt, phase2_prompt)。

    规则：
      - 文件名含 "phase1"（大小写不敏感）→ Phase 1 候选
      - 文件名含 "phase2" → Phase 2 候选
      - 多个候选取 version 最大的

    Raises:
        FileNotFoundError: 找不到 phase1 或 phase2 yaml
    """
    prompts_dir = Path(prompts_dir)
    phase1_candidates: list[PromptConfig] = []
    phase2_candidates: list[PromptConfig] = []

    for yaml_file in sorted(prompts_dir.glob("*.yaml")):
        name_lower = yaml_file.name.lower()
        try:
            cfg = load_prompt(yaml_file)
        except Exception as e:
            print(f"[yaml_loader] 跳过 {yaml_file.name}：{e}")
            continue

        if "phase1" in name_lower:
            phase1_candidates.append(cfg)
        elif "phase2" in name_lower:
            phase2_candidates.append(cfg)

    if not phase1_candidates:
        raise FileNotFoundError(f"在 {prompts_dir} 下找不到 phase1 yaml 文件")
    if not phase2_candidates:
        raise FileNotFoundError(f"在 {prompts_dir} 下找不到 phase2 yaml 文件")

    phase1 = max(phase1_candidates, key=lambda c: _version_key(c.version))
    phase2 = max(phase2_candidates, key=lambda c: _version_key(c.version))

    print(f"[yaml_loader] Phase1 prompt: {phase1.name}  v{phase1.version}  ({Path(phase1.source_file).name})")
    print(f"[yaml_loader] Phase2 prompt: {phase2.name}  v{phase2.version}  ({Path(phase2.source_file).name})")

    return phase1, phase2

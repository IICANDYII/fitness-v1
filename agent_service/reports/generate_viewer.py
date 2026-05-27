"""
生成 muscle_viewer.html
- 正面 + 背面 SVG 并排展示
- 默认颜色 rgb(184, 188, 204)
- 高亮颜色 rgb(240, 64, 52)
- highlight(['abdominals','hands']) 可高亮指定肌群
"""
import re
from pathlib import Path

_HERE  = Path(__file__).parent
INPUT  = _HERE / "muscle_input.html"
OUTPUT = _HERE / "muscle_viewer.html"

raw = INPUT.read_text(encoding="utf-8")

# 提取两段 <svg ...>...</svg>
svg_blocks = re.findall(r'(<svg\b[^>]*>[\s\S]*?</svg>)', raw, re.IGNORECASE)
assert len(svg_blocks) >= 2, f"Expected 2 SVGs, found {len(svg_blocks)}"

front_svg = svg_blocks[0]
back_svg  = svg_blocks[1]

# 给两个 SVG 分别加 data-view 属性以便区分
front_svg = front_svg.replace('<svg ', '<svg data-view="front" ', 1)
back_svg  = back_svg.replace('<svg ', '<svg data-view="back" ', 1)

# 收集所有 bodymap id（用于显示标签 / 调试）
ids = sorted(set(re.findall(r'id="([^"]+)"', front_svg + back_svg)))

HTML = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>肌群图谱</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: #eef0f5;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    padding: 28px 20px 40px;
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif;
  }}

  h1 {{
    font-size: 20px;
    font-weight: 600;
    color: #2b2d42;
    margin-bottom: 22px;
    letter-spacing: .04em;
  }}

  /* ── 控制栏 ── */
  .controls {{
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 28px;
    flex-wrap: wrap;
    justify-content: center;
  }}
  .controls input {{
    padding: 9px 14px;
    border: 1.5px solid #c8cad8;
    border-radius: 8px;
    font-size: 14px;
    width: 340px;
    outline: none;
    background: #fff;
    color: #2b2d42;
    transition: border-color .2s;
  }}
  .controls input:focus {{ border-color: rgb(240, 64, 52); }}
  .controls button {{
    padding: 9px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
    transition: opacity .15s;
  }}
  .controls button:hover {{ opacity: .85; }}
  .btn-highlight {{ background: rgb(240, 64, 52); color: #fff; }}
  .btn-reset     {{ background: #6b6f8a; color: #fff; }}

  /* ── SVG 容器 ── */
  .svg-container {{
    display: flex;
    gap: 48px;
    justify-content: center;
    flex-wrap: wrap;
  }}
  .view-wrapper {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }}
  .view-label {{
    font-size: 13px;
    font-weight: 600;
    color: #6b6f8a;
    letter-spacing: .08em;
    text-transform: uppercase;
  }}
  .view-wrapper svg {{
    height: min(72vh, 640px);
    width: auto;
    display: block;
  }}

  /* ── 肌群颜色 ── */
  /* 所有 bodymap 路径默认灰色 */
  .bodymap path, .bodymap circle, .bodymap ellipse, .bodymap polygon, .bodymap rect {{
    fill: rgb(184, 188, 204);
    transition: fill .25s ease;
  }}
  /* 高亮 */
  .bodymap.active path, .bodymap.active circle,
  .bodymap.active ellipse, .bodymap.active polygon, .bodymap.active rect {{
    fill: rgb(240, 64, 52);
  }}
  /* 结构轮廓 body 组不受影响 */
  .body-map__model {{
    pointer-events: none;
  }}
  /* 隐藏 hidden 类元素（关节占位符等） */
  .hidden {{
    display: none !important;
  }}

  /* ── 提示标签 ── */
  .hint {{
    margin-top: 18px;
    font-size: 12px;
    color: #9499b2;
    text-align: center;
    line-height: 1.8;
  }}
  .hint code {{
    background: #e8eaf2;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 11px;
  }}
</style>
</head>
<body>

<h1>肌群图谱 · 正 / 背面</h1>

<div class="controls">
  <input
    type="text"
    id="muscle-input"
    placeholder="输入肌群 ID，逗号分隔，如 abdominals,chest,lats"
  />
  <button class="btn-highlight" onclick="applyHighlight()">高亮</button>
  <button class="btn-reset"     onclick="resetHighlight()">重置</button>
</div>

<div class="svg-container">
  <div class="view-wrapper" id="front-view">
    <span class="view-label">正面</span>
    {front_svg}
  </div>
  <div class="view-wrapper" id="back-view">
    <span class="view-label">背面</span>
    {back_svg}
  </div>
</div>

<p class="hint">
  可用肌群 ID：
  {' '.join(f'<code>{i}</code>' for i in ids)}
  <br>
  在 JS 中调用 <code>highlight(['abdominals','lats'])</code> 可直接高亮
</p>

<script>
/**
 * highlight(muscles)
 * @param {{string[]}} muscles - 肌群 ID 数组，如 ['abdominals', 'chest']
 *
 * 规则：
 *   - 正面 SVG 中 <g id="calves"> 与 背面 SVG 中 <g id="calves"> 使用相同 ID
 *   - querySelectorAll('[id="x"]') 会同时找到两个，均高亮
 *   - 无需区分 front/back —— 传入名称即可，两面同步
 */
function highlight(muscles) {{
  // 重置
  document.querySelectorAll('.bodymap').forEach(el => {{
    el.classList.remove('active');
  }});

  if (!muscles || muscles.length === 0) return;

  muscles.forEach(name => {{
    const id = name.trim();
    if (!id) return;
    // 用属性选择器，支持同名 ID 同时出现在两个 SVG 中
    document.querySelectorAll(`[id="${{id}}"]`).forEach(el => {{
      if (el.classList.contains('bodymap')) {{
        el.classList.add('active');
      }}
    }});
  }});
}}

function applyHighlight() {{
  const val = document.getElementById('muscle-input').value;
  const muscles = val.split(',').map(s => s.trim()).filter(Boolean);
  highlight(muscles);
}}

function resetHighlight() {{
  document.getElementById('muscle-input').value = '';
  highlight([]);
}}

// 回车触发
document.getElementById('muscle-input').addEventListener('keydown', e => {{
  if (e.key === 'Enter') applyHighlight();
}});
</script>
</body>
</html>
"""

OUTPUT.write_text(HTML, encoding="utf-8")
print(f"Generated: {OUTPUT}")
print(f"SVG IDs found: {len(ids)}")
for i in ids:
    print(f"  {i}")

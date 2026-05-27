import re
from pathlib import Path

_HERE = Path(__file__).parent

# ── Load and process SVGs ────────────────────────────────────────────
front_svg = (_HERE / 'front_body.svg').read_text(encoding='utf-8')
back_svg  = (_HERE / 'back_body.svg').read_text(encoding='utf-8')

front_svg = re.sub(r'<\?xml[^?]*\?>', '', front_svg).strip()
back_svg  = re.sub(r'<\?xml[^?]*\?>', '', back_svg).strip()

# Strip Tailwind classes from SVG root element
front_svg = re.sub(r'(<svg[^>]*) class="[^"]*"', r'\1', front_svg, count=1)
back_svg  = re.sub(r'(<svg[^>]*) class="[^"]*"', r'\1', back_svg,  count=1)

# Prefix ALL back SVG IDs with "b-" to avoid DOM conflicts with front SVG
ids_back = re.findall(r'\bid="([^"]+)"', back_svg)
for id_val in sorted(ids_back, key=len, reverse=True):
    back_svg = back_svg.replace(f'id="{id_val}"',    f'id="b-{id_val}"')
    back_svg = back_svg.replace(f'url(#{id_val})',   f'url(#b-{id_val})')
    back_svg = back_svg.replace(f'href="#{id_val}"', f'href="#b-{id_val}"')

# ── HTML Template ────────────────────────────────────────────────────
HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>训练分析仪表板</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #eef0f8;
  font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
  padding: 24px 20px;
  min-height: 100vh;
}
.dashboard {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  max-width: 1440px;
  margin: 0 auto;
}
.card {
  background: #fff;
  border-radius: 18px;
  padding: 20px 18px 18px;
  box-shadow: 0 2px 14px rgba(80,100,160,0.07);
  display: flex;
  flex-direction: column;
}
.card-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e2340;
  text-align: center;
  margin-bottom: 14px;
  letter-spacing: .02em;
}

/* ════════════════════════════
   CARD 1 — 当日分析
   ════════════════════════════ */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin-bottom: 14px;
}
.stat-box {
  background: #f4f6fc;
  border-radius: 10px;
  padding: 8px 4px;
  text-align: center;
}
.stat-lbl  { font-size: 10px; color: #8b92b0; white-space: nowrap; margin-bottom: 3px; }
.stat-val  { font-size: 18px; font-weight: 800; color: #1e2340; line-height: 1; }
.stat-unit { font-size: 10px; font-weight: 500; color: #8b92b0; }

.section-label { font-size: 12px; font-weight: 600; color: #374151; margin-bottom: 10px; }

/* Colored horizontal bar list */
.bar-list { display: flex; flex-direction: column; gap: 10px; flex: 1; }
.bar-item { display: flex; align-items: center; gap: 8px; }
.bar-name {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
  width: 22px;
  flex-shrink: 0;
}
.bar-track {
  flex: 1;
  height: 10px;
  background: #e9ecf5;
  border-radius: 5px;
  overflow: hidden;
}
.bar-fill  { height: 100%; border-radius: 5px; transition: width .6s ease; }
.bar-pct {
  font-size: 13px;
  font-weight: 700;
  color: #374151;
  width: 42px;
  text-align: right;
  flex-shrink: 0;
}

/* ════════════════════════════
   CARD 2 — 训练部位可视化
   ════════════════════════════ */
.viz-body {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
}
.viz-svgwrap svg { display: block; height: 260px; width: auto; }
.viz-legend {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-self: center;
  flex-shrink: 0;
}
.legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #374151;
  font-weight: 600;
}
.legend-dot { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }

/* ════════════════════════════
   CARD 3 — 每周分析
   ════════════════════════════ */
.weekly-nums {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}
.w-num-lbl { font-size: 10px; color: #8b92b0; margin-bottom: 3px; white-space: nowrap; }
.w-num-val {
  font-size: 22px;
  font-weight: 800;
  color: #1e2340;
  display: flex;
  align-items: baseline;
  gap: 5px;
}
.trend-up   { font-size: 11px; font-weight: 600; color: #10b981; }
.trend-down { font-size: 11px; font-weight: 600; color: #ef4444; }
.trend-flat { font-size: 11px; font-weight: 600; color: #9ca3af; }
.chart-wrap { flex: 1; min-height: 140px; position: relative; }
.chart-wrap canvas { display: block; }
.chart-xlabels {
  display: flex;
  justify-content: space-between;
  padding: 0 4px;
  margin-top: 2px;
}
.chart-xlabels span { font-size: 10px; color: #9ca3af; }

/* ════════════════════════════
   CARD 4 — 月历视图
   ════════════════════════════ */
.cal-month { text-align: center; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px; }
.cal-grid  { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; text-align: center; }
.cal-wd    { font-size: 10px; color: #9ca3af; padding: 2px 0 5px; font-weight: 600; }
.cal-day {
  font-size: 11px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  color: #374151;
  font-weight: 500;
}
.cal-day.partial { border: 2px solid #10b981; color: #10b981; font-weight: 700; }
.cal-day.full    { background: #10b981; color: #fff; font-weight: 700; }
.cal-day.today   { background: #3b82f6; color: #fff; font-weight: 700; }
.cal-day.empty   { visibility: hidden; }

/* ════════════════════════════
   SVG Bodymap
   ════════════════════════════ */
.bodymap path, .bodymap circle, .bodymap ellipse, .bodymap polygon, .bodymap rect {
  fill: rgb(184,188,204);
  transition: fill .35s ease;
}
/* joint marker groups stay invisible */
.hidden { display: none !important; }
</style>
</head>
<body>
<div class="dashboard">

  <!-- ══ Card 1: 当日分析 ══ -->
  <div class="card">
    <div class="card-title">当日分析</div>
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-lbl">训练时长</div>
        <div class="stat-val" id="s-duration">--<span class="stat-unit"> min</span></div>
      </div>
      <div class="stat-box">
        <div class="stat-lbl">消耗热量</div>
        <div class="stat-val" id="s-calories">--<span class="stat-unit">kcal</span></div>
      </div>
      <div class="stat-box">
        <div class="stat-lbl">平均心率</div>
        <div class="stat-val" id="s-hr">--<span class="stat-unit">bpm</span></div>
      </div>
      <div class="stat-box">
        <div class="stat-lbl">完成率</div>
        <div class="stat-val" id="s-rate">--<span class="stat-unit">%</span></div>
      </div>
    </div>
    <div class="section-label">训练部位分布</div>
    <div class="bar-list" id="muscle-bars">
      <!-- filled by JS -->
    </div>
  </div>

  <!-- ══ Card 2: 训练部位可视化 ══ -->
  <div class="card">
    <div class="card-title">训练部位可视化</div>
    <div class="viz-body">
      <div class="viz-svgwrap" id="viz-front">FRONT_SVG_PLACEHOLDER</div>
      <div class="viz-svgwrap" id="viz-back">BACK_SVG_PLACEHOLDER</div>
      <div class="viz-legend">
        <div class="legend-row"><div class="legend-dot" style="background:#F04034"></div>高</div>
        <div class="legend-row"><div class="legend-dot" style="background:#52C41A"></div>中</div>
        <div class="legend-row"><div class="legend-dot" style="background:#9FC6FF"></div>低</div>
      </div>
    </div>
  </div>

  <!-- ══ Card 3: 每周分析 ══ -->
  <div class="card">
    <div class="card-title">每周分析</div>
    <div class="weekly-nums">
      <div>
        <div class="w-num-lbl">总训练量（组数）</div>
        <div class="w-num-val" id="w-sets">-- <span class="trend-flat">--</span></div>
      </div>
      <div>
        <div class="w-num-lbl">总消耗（kcal）</div>
        <div class="w-num-val" id="w-kcal">-- <span class="trend-flat">--</span></div>
      </div>
    </div>
    <div class="chart-wrap">
      <canvas id="weeklyChart"></canvas>
    </div>
    <div class="chart-xlabels" id="chart-labels">
      <span>周一</span><span>周二</span><span>周三</span><span>周四</span><span>周五</span><span>周六</span><span>周日</span>
    </div>
  </div>

  <!-- ══ Card 4: 月历视图 ══ -->
  <div class="card">
    <div class="card-title">月历视图</div>
    <div class="cal-month" id="cal-month">-- 年 -- 月</div>
    <div class="cal-grid" id="calGrid"></div>
  </div>

</div>

<script>
var API = 'http://localhost:8002/api';

var HEAT_COLORS = { high: '#F04034', medium: '#52C41A', low: '#9FC6FF', none: 'rgb(184,188,204)' };

// Each muscle group gets a fixed palette color (index order)
var BAR_PALETTE = ['#F786A9', '#52C41A', '#E6A23C', '#409EFF', '#722ED1', '#13C2C2'];

/* ── Heatmap ─────────────────────────────────────────────────────────
   Uses querySelectorAll('[id="..."]') instead of getElementById so that
   both front SVG (id="chest") and back SVG (id="b-lats") are both colored.
   ------------------------------------------------------------------- */
function applyHeatmap(muscleData) {
  Object.entries(muscleData).forEach(function(entry) {
    var muscleId = entry[0], level = entry[1];
    var color = HEAT_COLORS[level] || HEAT_COLORS.none;
    document.querySelectorAll('[id="' + muscleId + '"]').forEach(function(el) {
      el.querySelectorAll('path, circle, ellipse, polygon, rect').forEach(function(p) {
        p.style.fill = color;
      });
    });
  });
}

/* ── Weekly line chart ─────────────────────────────────────────────── */
function drawChart(data, labels) {
  var canvas = document.getElementById('weeklyChart');
  var wrap = canvas.parentElement;
  var dpr = window.devicePixelRatio || 1;
  var W = wrap.clientWidth || 260, H = 150;
  canvas.width = W * dpr; canvas.height = H * dpr;
  canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  var ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  var pL = 26, pR = 6, pT = 10, pB = 4;
  var cW = W - pL - pR, cH = H - pT - pB;
  var maxV = Math.max.apply(null, data.concat([1]));
  var roundedMax = Math.ceil(maxV / 5) * 5 || 5;
  var xStep = cW / (data.length - 1);

  // Y gridlines + labels
  ctx.strokeStyle = '#edf0f7'; ctx.lineWidth = 1;
  ctx.fillStyle = '#9ca3af'; ctx.font = '9px sans-serif'; ctx.textAlign = 'right';
  [0, Math.round(roundedMax * 0.33), Math.round(roundedMax * 0.67), roundedMax].forEach(function(v) {
    var y = pT + cH - (v / roundedMax) * cH;
    ctx.beginPath(); ctx.moveTo(pL, y); ctx.lineTo(W - pR, y); ctx.stroke();
    ctx.fillText(v, pL - 2, y + 3);
  });

  // X labels
  document.getElementById('chart-labels').innerHTML =
    labels.map(function(l) { return '<span>' + l + '</span>'; }).join('');

  var pts = data.map(function(v, i) {
    return { x: pL + i * xStep, y: pT + cH - (v / roundedMax) * cH };
  });

  // Gradient fill under curve
  ctx.beginPath();
  ctx.moveTo(pts[0].x, pT + cH);
  pts.forEach(function(p) { ctx.lineTo(p.x, p.y); });
  ctx.lineTo(pts[pts.length - 1].x, pT + cH);
  ctx.closePath();
  var grad = ctx.createLinearGradient(0, pT, 0, pT + cH);
  grad.addColorStop(0, 'rgba(59,130,246,0.18)');
  grad.addColorStop(1, 'rgba(59,130,246,0)');
  ctx.fillStyle = grad; ctx.fill();

  // Smooth bezier curve
  ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y);
  for (var j = 1; j < pts.length; j++) {
    var mx = (pts[j - 1].x + pts[j].x) / 2;
    ctx.bezierCurveTo(mx, pts[j - 1].y, mx, pts[j].y, pts[j].x, pts[j].y);
  }
  ctx.strokeStyle = '#3b82f6'; ctx.lineWidth = 2.2; ctx.lineJoin = 'round'; ctx.stroke();

  // Dots
  pts.forEach(function(p) {
    ctx.beginPath(); ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#3b82f6'; ctx.fill();
    ctx.beginPath(); ctx.arc(p.x, p.y, 1.8, 0, Math.PI * 2);
    ctx.fillStyle = '#fff'; ctx.fill();
  });
}

/* ── Calendar ─────────────────────────────────────────────────────── */
function renderCalendar(year, month, workoutDays) {
  var CN_MONTHS = ['一','二','三','四','五','六','七','八','九','十','十一','十二'];
  document.getElementById('cal-month').textContent = year + '年 ' + CN_MONTHS[month - 1] + '月';
  var grid = document.getElementById('calGrid');
  grid.innerHTML = '';

  ['一','二','三','四','五','六','日'].forEach(function(d) {
    var el = document.createElement('div');
    el.className = 'cal-wd'; el.textContent = d; grid.appendChild(el);
  });

  var offset = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  for (var i = 0; i < offset; i++) {
    var el = document.createElement('div');
    el.className = 'cal-day empty'; grid.appendChild(el);
  }

  var today = new Date();
  var daysInMonth = new Date(year, month, 0).getDate();
  for (var d = 1; d <= daysInMonth; d++) {
    var cell = document.createElement('div');
    var ds = year + '-' + String(month).padStart(2, '0') + '-' + String(d).padStart(2, '0');
    var isToday = (today.getFullYear() === year && (today.getMonth() + 1) === month && today.getDate() === d);
    var status = workoutDays[ds];
    if (isToday)                cell.className = 'cal-day today';
    else if (status === 'full') cell.className = 'cal-day full';
    else if (status === 'partial') cell.className = 'cal-day partial';
    else                        cell.className = 'cal-day';
    cell.textContent = d;
    grid.appendChild(cell);
  }
}

/* ── Muscle bar list (Card 1) ─────────────────────────────────────── */
function renderMuscleBars(dist) {
  var list = document.getElementById('muscle-bars');
  list.innerHTML = '';
  Object.entries(dist).forEach(function(entry, idx) {
    var name = entry[0], pct = entry[1];
    var color = BAR_PALETTE[idx % BAR_PALETTE.length];
    var item = document.createElement('div');
    item.className = 'bar-item';
    item.innerHTML =
      '<span class="bar-name">' + name + '</span>' +
      '<div class="bar-track">' +
        '<div class="bar-fill" style="width:' + pct + '%;background:' + color + '"></div>' +
      '</div>' +
      '<span class="bar-pct">' + pct + '%</span>';
    list.appendChild(item);
  });
}

/* ── Trend badge HTML ─────────────────────────────────────────────── */
function trendHtml(pct) {
  if (pct > 0) return '<span class="trend-up">&#8679;' + pct + '%</span>';
  if (pct < 0) return '<span class="trend-down">&#8681;' + Math.abs(pct) + '%</span>';
  return '<span class="trend-flat">--</span>';
}

/* ── Main init (parallel API fetch) ─────────────────────────────── */
async function init() {
  try {
    var [daily, weekly, musclesData, calendar] = await Promise.all([
      fetch(API + '/daily').then(function(r)   { return r.json(); }),
      fetch(API + '/weekly').then(function(r)  { return r.json(); }),
      fetch(API + '/muscles').then(function(r) { return r.json(); }),
      fetch(API + '/calendar').then(function(r){ return r.json(); }),
    ]);

    // Card 1: stats
    document.getElementById('s-duration').innerHTML = daily.duration_min + '<span class="stat-unit"> min</span>';
    document.getElementById('s-calories').innerHTML = daily.calories + '<span class="stat-unit">kcal</span>';
    document.getElementById('s-hr').innerHTML = (daily.avg_hr || '--') + '<span class="stat-unit">bpm</span>';
    document.getElementById('s-rate').innerHTML = daily.completion_rate + '<span class="stat-unit">%</span>';
    renderMuscleBars(daily.muscle_distribution || {});

    // Card 2: muscle heatmap (front + back)
    applyHeatmap(musclesData);

    // Card 3: weekly KPIs + chart
    document.getElementById('w-sets').innerHTML = weekly.total_sets + ' ' + trendHtml(weekly.sets_trend_pct);
    document.getElementById('w-kcal').innerHTML = weekly.total_calories + ' ' + trendHtml(weekly.calories_trend_pct);
    drawChart(weekly.daily_sets, weekly.day_labels);

    // Card 4: calendar
    renderCalendar(calendar.year, calendar.month, calendar.days || {});

  } catch (err) {
    console.error('API error:', err);
    drawChart([0, 0, 0, 0, 0, 0, 0], ['周一','周二','周三','周四','周五','周六','周日']);
    document.getElementById('cal-month').textContent = '⚠ 后端未启动 (port 8002)';
  }
}

init();
</script>
</body>
</html>'''

html = HTML_TEMPLATE \
    .replace('FRONT_SVG_PLACEHOLDER', front_svg) \
    .replace('BACK_SVG_PLACEHOLDER',  back_svg)

with open(_HERE / 'training_dashboard.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Done!', round(len(html) / 1024, 1), 'KB')

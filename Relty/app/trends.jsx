// trends.jsx — Activity & Fitness trend reports + shared chart primitives

// ── Chart primitives ─────────────────────────────────────────

// Vertical bar chart (div-based). data: [{label, value, state:'past'|'today'|'future'}]
function VBars({ data, color, height = 116, avg, unit = '', topLabel }) {
  const T = useTheme();
  const max = Math.max(...data.map((d) => d.value), avg || 0) * 1.18 || 1;
  return (
    <div>
      <div style={{ position: 'relative', height, display: 'flex', alignItems: 'flex-end', gap: 7 }}>
        {avg != null && (
          <div style={{ position: 'absolute', left: 0, right: 0, bottom: `${(avg / max) * 100}%`, borderTop: `1px dashed ${T.faint}`, opacity: 0.6, pointerEvents: 'none' }}>
            <span style={{ position: 'absolute', right: 0, top: -13, fontSize: 9, fontWeight: 600, color: T.faint }}>avg {avg}{unit}</span>
          </div>
        )}
        {data.map((d, i) => {
          const isToday = d.state === 'today';
          const future = d.state === 'future';
          const bg = future ? 'rgba(255,255,255,0.05)'
            : isToday ? color
            : `color-mix(in srgb, ${color} 42%, transparent)`;
          return (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', height: '100%' }}>
              {topLabel && isToday && d.value > 0 && (
                <span style={{ fontSize: 10.5, fontWeight: 700, color: T.text, marginBottom: 4, fontVariantNumeric: 'tabular-nums' }}>{d.value}{unit}</span>
              )}
              <div style={{
                width: '100%', maxWidth: 26, height: future ? '6%' : `${(d.value / max) * 100}%`,
                minHeight: future ? 6 : 5, background: bg, borderRadius: 6,
                boxShadow: isToday && T.glow ? `0 0 12px -2px ${color}` : 'none',
                transition: 'height 0.6s cubic-bezier(.22,1,.36,1)',
              }}></div>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: 7, marginTop: 8 }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 10, fontWeight: d.state === 'today' ? 700 : 500, color: d.state === 'today' ? T.text : T.faint }}>{d.label}</div>
        ))}
      </div>
    </div>
  );
}

// Stacked bars. days: [{label, state, parts:{key:value}}], keys: [{key,color,label}]
function StackedBars({ days, keys, height = 124, unit = 'm' }) {
  const T = useTheme();
  const totals = days.map((d) => keys.reduce((a, k) => a + (d.parts[k.key] || 0), 0));
  const max = Math.max(...totals) * 1.12 || 1;
  return (
    <div>
      <div style={{ height, display: 'flex', alignItems: 'flex-end', gap: 8 }}>
        {days.map((d, i) => {
          const total = totals[i];
          return (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'center', height: '100%' }}>
              <div style={{ width: '100%', maxWidth: 28, height: `${(total / max) * 100}%`, display: 'flex', flexDirection: 'column', borderRadius: 6, overflow: 'hidden', minHeight: total ? 6 : 0 }}>
                {keys.map((k, ki) => {
                  const v = d.parts[k.key] || 0;
                  if (!v) return null;
                  return <div key={k.key} style={{ height: `${(v / total) * 100}%`, background: k.color, opacity: d.state === 'today' ? 1 : 0.55 }}></div>;
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        {days.map((d, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 10, fontWeight: d.state === 'today' ? 700 : 500, color: d.state === 'today' ? T.text : T.faint }}>{d.label}</div>
        ))}
      </div>
    </div>
  );
}

// Line + area chart. data: [{label, value}]
function LineArea({ data, color, height = 110, unit = '', avg }) {
  const T = useTheme();
  const gid = React.useRef('la' + Math.random().toString(36).slice(2, 7));
  const W = 320, padT = 14, padB = 4;
  const max = Math.max(...data.map((d) => d.value)) * 1.12 || 1;
  const min = Math.min(...data.map((d) => d.value)) * 0.85;
  const span = max - min || 1;
  const n = data.length;
  const pts = data.map((d, i) => {
    const x = n === 1 ? W / 2 : (i / (n - 1)) * W;
    const y = padT + (1 - (d.value - min) / span) * (height - padT - padB);
    return [x, y];
  });
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const area = `${line} L${W} ${height} L0 ${height} Z`;
  return (
    <div>
      <div style={{ position: 'relative', height }}>
        <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" width="100%" height={height} style={{ display: 'block', overflow: 'visible' }}>
          <defs>
            <linearGradient id={gid.current} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.32" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d={area} fill={`url(#${gid.current})`} />
          <path d={line} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
        {/* dots — absolutely positioned so they stay round */}
        {pts.map((p, i) => {
          const last = i === n - 1;
          return (
            <div key={i} style={{
              position: 'absolute', left: `${(p[0] / W) * 100}%`, top: p[1],
              width: last ? 9 : 6, height: last ? 9 : 6, borderRadius: 99,
              background: last ? color : T.card, border: `2px solid ${color}`,
              transform: 'translate(-50%,-50%)',
              boxShadow: last && T.glow ? `0 0 9px ${color}` : 'none',
            }}></div>
          );
        })}
      </div>
      <div style={{ display: 'flex', marginTop: 8 }}>
        {data.map((d, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 10, fontWeight: i === n - 1 ? 700 : 500, color: i === n - 1 ? T.text : T.faint }}>{d.label}</div>
        ))}
      </div>
    </div>
  );
}

// Consistency dot grid. days: [{ hit: bool|null }]
function ConsistencyGrid({ days, color }) {
  const T = useTheme();
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6 }}>
      {days.map((d, i) => (
        <div key={i} title={d.label} style={{
          aspectRatio: '1', borderRadius: 6,
          background: d.hit === true ? color : d.hit === false ? 'rgba(255,255,255,0.05)' : 'transparent',
          border: d.hit === null ? `1px dashed ${T.line}` : d.hit ? 'none' : `1px solid ${T.line}`,
          opacity: d.hit === true ? (d.dim || 1) : 1,
        }}></div>
      ))}
    </div>
  );
}

function TrendStat({ label, value, unit, delta, deltaGood }) {
  const T = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <span style={{ fontSize: 10.5, color: T.faint, fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: 19, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em', lineHeight: 1 }}>
        {value}{unit && <span style={{ fontSize: 11, fontWeight: 500, color: T.sub, marginLeft: 2 }}>{unit}</span>}
      </span>
      {delta && (
        <span style={{ fontSize: 10.5, fontWeight: 600, color: deltaGood ? T.green : T.faint }}>{delta}</span>
      )}
    </div>
  );
}

// Compact entry card for home screens
function TrendEntry({ accent, subtitle, data, onClick }) {
  const T = useTheme();
  const max = Math.max(...data) || 1;
  return (
    <Card pad={16} onClick={onClick}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, flexShrink: 0,
          background: `color-mix(in srgb, ${accent} 14%, transparent)`,
          border: `1px solid color-mix(in srgb, ${accent} 28%, transparent)`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Ic name="trends" size={19} color={accent} sw={2.2} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14.5, fontWeight: 700, color: T.text }}>Trend Report</div>
          <div style={{ fontSize: 11.5, color: T.faint }}>{subtitle}</div>
        </div>
        {/* mini sparkbars */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2.5, height: 24 }}>
          {data.map((v, i) => (
            <div key={i} style={{ width: 4, height: `${(v / max) * 100}%`, minHeight: 4, borderRadius: 2, background: i === data.length - 1 ? accent : `color-mix(in srgb, ${accent} 40%, transparent)` }}></div>
          ))}
        </div>
        <Ic name="chevR" size={14} color={T.faint} sw={2.2} />
      </div>
    </Card>
  );
}

// ── Data ─────────────────────────────────────────────────────
const A_WEEKLY = [
  { label: 'M', value: 412, state: 'past' },
  { label: 'T', value: 455, state: 'past' },
  { label: 'W', value: 280, state: 'past' },
  { label: 'T', value: 470, state: 'past' },
  { label: 'F', value: 430, state: 'today' },
  { label: 'S', value: 0, state: 'future' },
  { label: 'S', value: 0, state: 'future' },
];

const A_TYPE_DAYS = [
  { label: 'M', state: 'past', parts: { walk: 180, outdoor: 60, gym: 0 } },
  { label: 'T', state: 'past', parts: { walk: 150, outdoor: 90, gym: 60 } },
  { label: 'W', state: 'past', parts: { walk: 120, outdoor: 0, gym: 0 } },
  { label: 'T', state: 'past', parts: { walk: 160, outdoor: 110, gym: 50 } },
  { label: 'F', state: 'today', parts: { walk: 182, outdoor: 105, gym: 70 } },
  { label: 'S', state: 'future', parts: {} },
  { label: 'S', state: 'future', parts: {} },
];

const A_SEDENTARY = [
  { label: 'Mon', value: 6.2 },
  { label: 'Tue', value: 5.8 },
  { label: 'Wed', value: 7.4 },
  { label: 'Thu', value: 5.1 },
  { label: 'Fri', value: 5.5 },
];

const REGULARITY_DAYS = [
  { hit: true, dim: 0.55 }, { hit: false }, { hit: true, dim: 0.7 }, { hit: true, dim: 0.85 }, { hit: true }, { hit: false }, { hit: true, dim: 0.6 },
  { hit: true, dim: 0.8 }, { hit: true }, { hit: false }, { hit: true }, { hit: true }, { hit: null }, { hit: null },
];

// ─────────────────────────────────────────────────────────────
// Activity Trends
// ─────────────────────────────────────────────────────────────
function ActivityTrends({ nav }) {
  const T = useTheme();
  const typeKeys = [
    { key: 'walk', color: mixColor(T, 'walk'), label: 'Walk' },
    { key: 'outdoor', color: mixColor(T, 'outdoor'), label: 'Outdoor' },
    { key: 'gym', color: mixColor(T, 'gym'), label: 'Gym' },
  ];
  return (
    <div data-screen-label="Activity · Trends">
      <ScreenHeader title="Activity Trends" kicker="Jun 8 – 14 · This week" accent={T.green} onBack={() => nav.pop('activity-home')} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {/* Weekly activity trend */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
            <SectionLabel>Weekly Activity</SectionLabel>
            <Tag color={T.green}>+8% vs last wk</Tag>
          </div>
          <div style={{ display: 'flex', gap: 18, marginBottom: 18 }}>
            <TrendStat label="Daily active avg" value="409" unit="min" />
            <TrendStat label="Best day" value="Thu" />
            <TrendStat label="Goal days" value="4 / 5" />
          </div>
          <VBars data={A_WEEKLY} color={T.green} avg={409} unit="" topLabel />
        </Card>

        {/* Activity type trend */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 16 }}>Activity Type Trend</SectionLabel>
          <StackedBars days={A_TYPE_DAYS} keys={typeKeys} />
          <div style={{ display: 'flex', gap: 16, marginTop: 16, flexWrap: 'wrap' }}>
            {typeKeys.map((k) => (
              <div key={k.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: k.color }}></span>
                <span style={{ fontSize: 11.5, color: T.sub }}>{k.label}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Sedentary trend */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
            <SectionLabel>Sedentary Trend</SectionLabel>
            <Tag color={T.green}>↓ 0.7h vs last wk</Tag>
          </div>
          <div style={{ display: 'flex', gap: 18, marginBottom: 16 }}>
            <TrendStat label="Daily still avg" value="6.0" unit="h" />
            <TrendStat label="Longest block" value="96" unit="min" />
          </div>
          <LineArea data={A_SEDENTARY} color="#E0B45A" />
        </Card>

        {/* Activity regularity score — NO ring, by design */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 14 }}>Activity Regularity</SectionLabel>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 6 }}>
            <span style={{ fontSize: 44, fontWeight: 800, color: T.text, letterSpacing: '-0.03em', lineHeight: 0.9, fontVariantNumeric: 'tabular-nums' }}>82</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: T.faint, marginBottom: 6 }}>/ 100</span>
            <div style={{ marginLeft: 'auto', marginBottom: 4 }}><Tag color={T.green}>Consistent</Tag></div>
          </div>
          <HBar value={82} color={T.green} h={6} style={{ marginBottom: 18 }} />
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.faint, marginBottom: 9 }}>Last 14 days</div>
          <ConsistencyGrid days={REGULARITY_DAYS} color={T.green} />
          <div style={{ fontSize: 12.5, color: T.sub, lineHeight: 1.5, marginTop: 14, textWrap: 'pretty' }}>
            You hit your move goal 10 of the last 12 days. Mornings are your most reliable window; weekends dip most.
          </div>
        </Card>

        <AICard accent={T.green}>
          Your activity is trending up this week, led by a strong midweek ride and steadier daily walking. Sedentary time is down — keep the morning movement habit going to protect your regularity score.
        </AICard>
      </div>
    </div>
  );
}

// ── Fitness trend data ───────────────────────────────────────
const F_LOAD = [
  { label: 'M', value: 13.1, state: 'past' },
  { label: 'T', value: 11.8, state: 'past' },
  { label: 'W', value: 0, state: 'past' },
  { label: 'T', value: 12.0, state: 'past' },
  { label: 'F', value: 14.2, state: 'today' },
  { label: 'S', value: 0, state: 'future' },
  { label: 'S', value: 0, state: 'future' },
];

const F_MUSCLES = [
  { name: 'Shoulders', sets: 13 },
  { name: 'Chest', sets: 11 },
  { name: 'Arms', sets: 10 },
  { name: 'Back', sets: 9 },
  { name: 'Legs', sets: 8 },
  { name: 'Core', sets: 4 },
];
const MUSCLE_TARGET = 10;

const F_WEEK_STATUS = [
  { d: 'M', s: 'done' }, { d: 'T', s: 'done' }, { d: 'W', s: 'rest' },
  { d: 'T', s: 'done' }, { d: 'F', s: 'done' }, { d: 'S', s: 'planned' }, { d: 'S', s: 'rest' },
];

const F_ADHERENCE = [
  { label: 'W21', value: 83, state: 'past' },
  { label: 'W22', value: 100, state: 'past' },
  { label: 'W23', value: 67, state: 'past' },
  { label: 'W24', value: 80, state: 'today' },
];

// ─────────────────────────────────────────────────────────────
// Fitness Trends
// ─────────────────────────────────────────────────────────────
function FitnessTrends({ nav }) {
  const T = useTheme();
  const muscleMax = Math.max(...F_MUSCLES.map((m) => m.sets));
  return (
    <div data-screen-label="Fitness · Trends">
      <ScreenHeader title="Fitness Trends" kicker="Week 24 · Hypertrophy Block" accent={T.blue} onBack={() => nav.pop('fitness-report')} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {/* This week training overview */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
            <SectionLabel>This Week</SectionLabel>
            <Tag color={T.blue} filled>4 / 6 done</Tag>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', rowGap: 18, columnGap: 10, marginBottom: 18 }}>
            <TrendStat label="Volume" value="38.2k" unit="kg" />
            <TrendStat label="Gym time" value="4h 35m" />
            <TrendStat label="Avg score" value="88" />
            <TrendStat label="Total sets" value="84" />
            <TrendStat label="Reps" value="612" />
            <TrendStat label="Streak" value="3" unit="wk" />
          </div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.faint, marginBottom: 12 }}>Daily training load</div>
          <VBars data={F_LOAD} color={T.blue} height={96} topLabel unit="" />
        </Card>

        {/* Muscle coverage analysis */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
            <SectionLabel>Muscle Coverage</SectionLabel>
            <span style={{ fontSize: 10.5, color: T.faint }}>weekly sets</span>
          </div>
          <div style={{ fontSize: 11.5, color: T.sub, marginBottom: 16 }}>Target {MUSCLE_TARGET}+ sets per group</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
            {F_MUSCLES.map((m) => {
              const under = m.sets < MUSCLE_TARGET;
              const c = under ? '#E0B45A' : T.blue;
              return (
                <div key={m.name}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                    <span style={{ flex: 1, fontSize: 12.5, color: T.sub }}>{m.name}</span>
                    {under && <Tag color="#E0B45A">Under</Tag>}
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums', minWidth: 18, textAlign: 'right' }}>{m.sets}</span>
                  </div>
                  <div style={{ position: 'relative' }}>
                    <HBar value={(m.sets / muscleMax) * 100} color={c} h={6} />
                    {/* target marker */}
                    <div style={{ position: 'absolute', top: -2, bottom: -2, left: `${(MUSCLE_TARGET / muscleMax) * 100}%`, width: 1.5, background: 'rgba(255,255,255,0.3)' }}></div>
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 12.5, color: T.sub, lineHeight: 1.5, marginTop: 16, textWrap: 'pretty' }}>
            Push volume is well covered. <strong style={{ color: T.text, fontWeight: 600 }}>Legs and core are under target</strong> — your Saturday session is a good place to balance.
          </div>
        </Card>

        {/* Plan execution */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
            <SectionLabel>Plan Execution</SectionLabel>
            <Tag color={T.blue}>On track</Tag>
          </div>
          {/* this week status row */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 18 }}>
            {F_WEEK_STATUS.map((w, i) => {
              const done = w.s === 'done';
              const planned = w.s === 'planned';
              return (
                <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: T.faint }}>{w.d}</span>
                  <span style={{
                    width: 26, height: 26, borderRadius: 8,
                    background: done ? `color-mix(in srgb, ${T.blue} 18%, transparent)` : 'transparent',
                    border: done ? `1px solid color-mix(in srgb, ${T.blue} 38%, transparent)` : `1px solid ${T.line}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {done && <Ic name="check" size={13} color={T.blue} sw={2.8} />}
                    {planned && <span style={{ width: 6, height: 6, borderRadius: 99, border: `1.5px solid ${T.blue}` }}></span>}
                    {w.s === 'rest' && <span style={{ width: 7, height: 2, borderRadius: 2, background: 'rgba(255,255,255,0.18)' }}></span>}
                  </span>
                </div>
              );
            })}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <span style={{ fontSize: 13, color: T.sub, flex: 1 }}>Weekly completion</span>
            <span style={{ fontSize: 16, fontWeight: 800, color: T.text, fontVariantNumeric: 'tabular-nums' }}>67%</span>
            <span style={{ fontSize: 11.5, color: T.faint }}>4 of 6</span>
          </div>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.faint, marginBottom: 12 }}>4-week adherence</div>
          <VBars data={F_ADHERENCE} color={T.blue} height={84} avg={83} unit="%" />
        </Card>

        <AICard title="Coach Insight" accent={T.blue}>
          You've held a 3-week training streak with strong push volume. To round out the block, prioritize legs and core next — adding one lower-body session would lift your weekly balance without raising overall fatigue.
        </AICard>
      </div>
    </div>
  );
}

Object.assign(window, { ActivityTrends, FitnessTrends, TrendEntry, TrendStat, VBars, StackedBars, LineArea, ConsistencyGrid });

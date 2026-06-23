// fitness.jsx — shared fitness UI + Screen 1 (Report / home)

// ─────────────────────────────────────────────────────────────
// Muscle coverage bars (no rings, by design)
// ─────────────────────────────────────────────────────────────
function MuscleBars({ rows, gap = 13 }) {
  const T = useTheme();
  const meta = levelMeta(T);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap }}>
      {rows.map((r) => {
        const m = meta[r.level];
        return (
          <div key={r.name}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span style={{ flex: 1, fontSize: 12.5, color: T.sub }}>{r.name}</span>
              <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.04em', color: m.text }}>{m.label}</span>
            </div>
            <HBar value={r.pct} color={m.color} h={5} />
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Top tabs — Report / Insights (Plan is a secondary entry on Report)
// ─────────────────────────────────────────────────────────────
function FitnessTabs({ active, nav }) {
  const T = useTheme();
  const tabs = [
    { id: 'Report', go: 'fitness-report' },
    { id: 'Insights', go: 'fitness-insights' },
  ];
  return (
    <div style={{ padding: '0 16px 6px' }}>
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 3,
        background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
        borderRadius: 12, padding: 3,
      }}>
        {tabs.map((tb) => {
          const on = tb.id === active;
          return (
            <button key={tb.id} className="press"
              onClick={on ? undefined : () => nav.tab(tb.go)}
              style={{
                border: 'none', borderRadius: 9, padding: '8px 0', cursor: on ? 'default' : 'pointer',
                fontSize: 13, fontWeight: 700, letterSpacing: '0.01em', fontFamily: 'inherit',
                color: on ? '#081019' : T.faint,
                background: on ? T.blue : 'transparent',
                boxShadow: on && T.glow ? `0 4px 14px -4px color-mix(in srgb, ${T.blue} 70%, transparent)` : 'none',
                transition: 'color 0.2s',
              }}>{tb.id}</button>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Selectable week strip — drives the selected workout
// ─────────────────────────────────────────────────────────────
function WeekStrip({ nav }) {
  const T = useTheme();
  const store = useFit();
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 6 }}>
      {WEEK.map((w) => {
        const has = !!w.wid;
        const sel = has && store.selected === w.wid;
        return (
          <button
            key={w.n}
            className={has ? 'press' : undefined}
            onClick={has ? () => { loadDailyWorkout(w.wid).then(() => { store.set({ selected: w.wid }); }); } : undefined}
            style={{
              border: sel ? `1px solid color-mix(in srgb, ${T.blue} 45%, transparent)` : '1px solid transparent',
              background: sel ? `color-mix(in srgb, ${T.blue} 16%, transparent)` : 'transparent',
              borderRadius: 13, padding: '9px 0 8px', cursor: has ? 'pointer' : 'default',
              fontFamily: 'inherit',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7,
            }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: sel ? T.blue : T.faint }}>{w.d}</span>
            <span style={{ fontSize: 14, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: sel || w.today ? T.text : T.sub }}>{w.n}</span>
            <span style={{ width: 14, height: 14, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {has
                ? <span style={{
                    width: 7, height: 7, borderRadius: 99,
                    background: sel ? T.blue : `color-mix(in srgb, ${T.blue} 55%, transparent)`,
                    boxShadow: sel && T.glow ? `0 0 7px color-mix(in srgb, ${T.blue} 75%, transparent)` : 'none',
                  }}></span>
                : w.today
                  ? <span style={{ width: 7, height: 7, borderRadius: 99, border: `1.5px solid ${T.blue}` }}></span>
                  : <span style={{ width: 6, height: 2, borderRadius: 2, background: 'rgba(255,255,255,0.16)' }}></span>}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Month calendar — reachable from the week card's calendar toggle.
// Lets you jump to any past day (incl. last week) and open its report.
// ─────────────────────────────────────────────────────────────
function MonthCalendar({ nav }) {
  const T = useTheme();
  const store = useFit();
  const dows = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth(); // 0-based
  const todayDate = now.getDate();
  const firstDow = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDow; i++) cells.push(null);
  for (let d = 1; d <= days; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginBottom: 8 }}>
        {dows.map((d, i) => (
          <div key={i} style={{ textAlign: 'center', fontSize: 9.5, fontWeight: 700, letterSpacing: '0.04em', color: T.faint }}>{d}</div>
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4 }}>
        {cells.map((cell, i) => {
          if (cell === null) return <div key={i}></div>;
          const wid = WORKOUT_DAYS[cell];
          const has = !!wid;
          const isToday = cell === todayDate;
          const sel = has && store.selected === wid;
          return (
            <button
              key={i}
              className={has ? 'press' : undefined}
              onClick={has ? () => {
                loadDailyWorkout(wid).then(() => { store.set({ selected: wid }); });
              } : undefined}
              style={{
                aspectRatio: '1', borderRadius: 10, cursor: has ? 'pointer' : 'default',
                fontFamily: 'inherit', position: 'relative',
                border: isToday ? `1px solid color-mix(in srgb, ${T.blue} 55%, transparent)` : '1px solid transparent',
                background: sel ? `color-mix(in srgb, ${T.blue} 18%, transparent)`
                  : has ? 'rgba(255,255,255,0.04)' : 'transparent',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3,
              }}>
              <span style={{ fontSize: 12.5, fontWeight: isToday || has ? 700 : 500, fontVariantNumeric: 'tabular-nums', color: isToday || sel ? T.text : has ? T.sub : T.faint }}>{cell}</span>
              <span style={{
                width: 5, height: 5, borderRadius: 99,
                background: has ? (sel ? T.blue : `color-mix(in srgb, ${T.blue} 60%, transparent)`) : 'transparent',
              }}></span>
            </button>
          );
        })}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 12, paddingTop: 12, borderTop: `1px solid ${T.line}` }}>
        <span style={{ width: 6, height: 6, borderRadius: 99, background: T.blue }}></span>
        <span style={{ fontSize: 11, color: T.faint }}>Workout logged — tap to open its report</span>
      </div>
    </div>
  );
}

// Week card with a calendar toggle (top-right)
function WeekCalendarCard({ nav }) {
  const T = useTheme();
  const [mode, setMode] = React.useState('week');
  const isWeek = mode === 'week';
  return (
    <Card pad={16}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <SectionLabel>{isWeek ? 'This Week' : new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</SectionLabel>
        <button className="press" onClick={() => setMode(isWeek ? 'month' : 'week')} style={{
          display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontFamily: 'inherit',
          padding: '5px 10px', borderRadius: 999,
          border: `1px solid ${isWeek ? T.line : `color-mix(in srgb, ${T.blue} 40%, transparent)`}`,
          background: isWeek ? 'rgba(255,255,255,0.04)' : `color-mix(in srgb, ${T.blue} 13%, transparent)`,
          fontSize: 11.5, fontWeight: 700, color: isWeek ? T.sub : T.blue,
        }}>
          <Ic name={isWeek ? 'cal' : 'chevL'} size={13} color={isWeek ? T.sub : T.blue} sw={2} />
          {isWeek ? 'Calendar' : 'Week'}
        </button>
      </div>
      {isWeek ? <WeekStrip nav={nav} /> : <MonthCalendar nav={nav} />}
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────
// Vertical timeline (session phases) — no per-row timestamps
// ─────────────────────────────────────────────────────────────
function Timeline({ items }) {
  const T = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {items.map((it, i) => {
        const last = i === items.length - 1;
        const strong = it.strong;
        return (
          <div key={i} style={{ display: 'flex', gap: 13 }}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 12, flexShrink: 0 }}>
              <span style={{
                width: strong ? 11 : 8, height: strong ? 11 : 8, borderRadius: 99, marginTop: 3,
                background: strong ? T.blue : 'transparent',
                border: strong ? 'none' : `1.6px solid color-mix(in srgb, ${T.blue} 55%, transparent)`,
                boxShadow: strong && T.glow ? `0 0 8px color-mix(in srgb, ${T.blue} 70%, transparent)` : 'none',
              }}></span>
              {!last && <span style={{ flex: 1, width: 1.5, background: T.line, marginTop: 3, minHeight: 16 }}></span>}
            </div>
            <div style={{ paddingBottom: last ? 0 : 14, flex: 1, minWidth: 0, display: 'flex', alignItems: 'baseline', gap: 8, marginTop: -1 }}>
              <span style={{ flex: 1, fontSize: 13.5, fontWeight: strong ? 700 : 600, color: strong ? T.text : T.sub }}>{it.label}</span>
              {it.detail && <span style={{ fontSize: 11.5, color: T.faint, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{it.detail}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Zone → SVG muscle group ID mappings (front and back)
// ─────────────────────────────────────────────────────────────
const FRONT_ZONE_IDS = {
  chest:     ['chest'],
  shoulders: ['front-shoulders'],
  biceps:    ['biceps', 'forearms'],
  core:      ['abdominals', 'obliques'],
  legs:      ['quads', 'calves'],
};
const BACK_ZONE_IDS = {
  upperBack: ['b-lats', 'b-traps', 'b-traps-middle'],
  lowerBack: ['b-lowerback'],
  shoulders: ['b-rear-shoulders'],
  triceps:   ['b-triceps'],
  legs:      ['b-hamstrings', 'b-glutes'],
};

// ─────────────────────────────────────────────────────────────
// Inline SVG body figure — plan_viewer color palette
// ─────────────────────────────────────────────────────────────
const HEAT_NONE      = 'rgba(255,255,255,0.10)';
const HEAT_NONE_BACK = 'rgba(255,255,255,0.22)';
const HEAT_PRIMARY   = 'rgb(238,122,90)';
const HEAT_SECONDARY = 'rgba(238,122,90,0.38)';
const HEAT_TERTIARY  = 'rgba(238,122,90,0.15)';

// Build a colored SVG HTML string from raw SVG text + zone activation map.
// Returns null if svgText is not yet available (shows <img> fallback).
function applyZoneColors(svgText, zones, isBack) {
  if (!svgText) return null;
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgText, 'image/svg+xml');
  const svg = doc.querySelector('svg');
  if (!svg) return null;

  // Normalize b- prefixes on SVG element IDs (female_back_body.svg uses them)
  svg.querySelectorAll('[id^="b-"]').forEach(el => { el.id = el.id.slice(2); });

  // Hide joint overlays / hover targets
  svg.querySelectorAll(
    '#shoulders, #elbow, #wrist, #hips, #knees, #ankles, ' +
    '#upper-spine, #lower-spine, #scapula, [id^="hover"]'
  ).forEach(el => { el.style.display = 'none'; });

  // Body skeleton — thicker stroke, no fill
  svg.querySelectorAll('#body path, #body line, #body-head path').forEach(el => {
    el.style.stroke        = 'rgba(255,255,255,0.70)';
    el.style.strokeWidth   = '12';
    el.style.fill          = 'none';
    el.style.strokeOpacity = '1';
  });

  // Base fill for all bodymap shapes
  const base = isBack ? HEAT_NONE_BACK : HEAT_NONE;
  svg.querySelectorAll('.bodymap path, .bodymap circle, .bodymap ellipse').forEach(p => {
    p.style.fill = base;
    if (isBack) {
      p.style.stroke        = 'rgba(255,255,255,0.45)';
      p.style.strokeWidth   = '2';
      p.style.paintOrder    = 'stroke fill';
      p.style.strokeLinejoin = 'round';
    }
  });

  // Collect primary / secondary / tertiary SVG IDs from zone levels
  const zoneMap = isBack ? BACK_ZONE_IDS : FRONT_ZONE_IDS;
  const primIds = [], secIds = [], terIds = [];
  Object.entries(zones || {}).forEach(([zone, lvl]) => {
    const ids = zoneMap[zone];
    if (!ids) return;
    if (lvl === 'high')      primIds.push(...ids);
    else if (lvl === 'med')  secIds.push(...ids);
    else if (lvl === 'low')  terIds.push(...ids);
  });

  // SVG IDs are already normalized (no b-), but BACK_ZONE_IDS still carries b- prefixes
  const normId = id => id.startsWith('b-') ? id.slice(2) : id;
  const setFill = (rawIds, color, skipSets) => {
    rawIds.forEach(rawId => {
      const id = normId(rawId);
      if (skipSets && skipSets.some(s => s.map(normId).includes(id))) return;
      svg.querySelectorAll(
        `[id="${id}"] path, [id="${id}"] ellipse, [id="${id}"] circle`
      ).forEach(p => { p.style.fill = color; });
    });
  };
  setFill(primIds, HEAT_PRIMARY);
  setFill(secIds,  HEAT_SECONDARY, [primIds]);
  setFill(terIds,  HEAT_TERTIARY,  [primIds, secIds]);

  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.style.cssText = 'width:100%;height:100%;display:block;';

  return svg.outerHTML;
}

// Body figure component — uses inline SVG with orange heat palette.
// Falls back to <img> while SVG text is loading.
function BodyFigure({ view, zones }) {
  const T = useTheme();
  const store = useFit();
  const gender = store.gender || 'male';
  const isBack = view === 'back';
  const label  = isBack ? 'BACK' : 'FRONT';

  const svgText = isBack ? _svgCache.back : _svgCache.front;
  const zonesKey = JSON.stringify(zones);
  const svgHtml = React.useMemo(
    () => applyZoneColors(svgText, zones, isBack),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [svgText, zonesKey, isBack]
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      {svgHtml ? (
        <div
          style={{
            width: 84, height: 164, flexShrink: 0,
            background: 'rgb(26,29,39)',
            border: '1.5px solid rgba(255,255,255,0.08)',
            borderRadius: 10, overflow: 'hidden',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
          dangerouslySetInnerHTML={{ __html: svgHtml }}
        />
      ) : (
        <img
          src={`${API_BASE}/fitness/body-svg/${view}?gender=${gender}`}
          width={84} height={164}
          style={{ display: 'block', objectFit: 'contain', borderRadius: 10 }}
        />
      )}
      <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.14em', color: T.faint }}>{label}</span>
    </div>
  );
}

// Combined muscle coverage — body figures (front + back) + level bars.
// Used everywhere a "Muscle Coverage" block appears.
function MuscleCoverage({ rows, front, back, gap = 13 }) {
  return (
    <div style={{ display: 'flex', gap: 14 }}>
      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
        <BodyFigure view="front" zones={front || {}} />
        <BodyFigure view="back" zones={back || {}} />
      </div>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <MuscleBars rows={rows} gap={gap} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Action button
// ─────────────────────────────────────────────────────────────
function GhostBtn({ icon, children, onClick, primary }) {
  const T = useTheme();
  return (
    <button className="press" onClick={onClick} style={{
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
      padding: '13px 0', borderRadius: 12, cursor: 'pointer', fontFamily: 'inherit',
      fontSize: 14, fontWeight: 700, letterSpacing: '0.01em',
      border: primary ? 'none' : `1px solid ${T.line}`,
      background: primary ? T.blue : 'rgba(255,255,255,0.04)',
      color: primary ? '#081019' : T.sub,
      boxShadow: primary && T.glow ? `0 8px 24px -10px color-mix(in srgb, ${T.blue} 70%, transparent)` : 'none',
    }}>
      {icon && <Ic name={icon} size={15} color={primary ? '#081019' : T.sub} sw={2.1} />}
      {children}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
// Training Suggestions — shown inline; tap to pick among plans
// (same selection pattern as the movement editor)
// ─────────────────────────────────────────────────────────────
function TrainingSuggestions({ nav }) {
  const T = useTheme();
  const store = useFit();
  const [picking, setPicking] = React.useState(false);
  const plan = getPlan(store.plan);

  return (
    <Card pad={18} glowColor={picking ? undefined : T.blue}>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <Ic name="spark" size={15} color={T.blue} />
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.blue }}>Training Suggestions</span>
      </div>
      <div style={{ fontSize: 12, color: T.faint, lineHeight: 1.5, marginBottom: 16 }}>
        A light reference from your records — not a fixed plan. Swap or adjust anytime.
      </div>

      {picking ? (
        /* ── plan picker (3–4 options, radio rows) ── */
        <React.Fragment>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <SectionLabel>Choose a plan</SectionLabel>
            <button className="press" onClick={() => setPicking(false)} style={{
              border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
              fontSize: 12.5, fontWeight: 700, color: T.faint,
            }}>Done</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {PLANS.map((p) => {
              const on = p.id === store.plan;
              return (
                <button key={p.id} className="press"
                  onClick={() => { store.set({ plan: p.id }); setPicking(false); }}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 11, width: '100%', textAlign: 'left',
                    padding: '13px 13px', borderRadius: 13, cursor: 'pointer', fontFamily: 'inherit',
                    border: on ? `1px solid color-mix(in srgb, ${T.blue} 45%, transparent)` : `1px solid ${T.line}`,
                    background: on ? `color-mix(in srgb, ${T.blue} 11%, transparent)` : 'rgba(255,255,255,0.03)',
                  }}>
                  <span style={{
                    width: 18, height: 18, borderRadius: 99, flexShrink: 0,
                    border: on ? 'none' : `1.5px solid ${T.line}`, background: on ? T.blue : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>{on && <Ic name="check" size={11} color="#081019" sw={3} />}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 700, color: on ? T.text : T.sub }}>{p.name}</div>
                    <div style={{ fontSize: 11, color: T.faint, marginTop: 2 }}>{p.why} · {p.moves.length} moves</div>
                  </div>
                  <span style={{ fontSize: 11, color: T.faint, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{p.mins}</span>
                </button>
              );
            })}
          </div>
        </React.Fragment>
      ) : (
        /* ── selected plan, shown directly ── */
        <React.Fragment>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 12 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 17, fontWeight: 800, color: T.text, letterSpacing: '-0.01em' }}>{plan.name}</div>
              <div style={{ fontSize: 12, color: T.faint, marginTop: 3 }}>{plan.why}</div>
            </div>
            <button className="press" onClick={() => setPicking(true)} style={{
              display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0, cursor: 'pointer', fontFamily: 'inherit',
              padding: '7px 12px', borderRadius: 999, border: `1px solid color-mix(in srgb, ${T.blue} 38%, transparent)`,
              background: `color-mix(in srgb, ${T.blue} 12%, transparent)`,
              fontSize: 12, fontWeight: 700, color: T.blue,
            }}>Switch <Ic name="chevR" size={11} color={T.blue} sw={2.6} /></button>
          </div>

          <button className="press" onClick={() => nav && nav.push('plan-edit')} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, width: '100%',
            marginBottom: 14, padding: '10px 0', borderRadius: 11, cursor: 'pointer', fontFamily: 'inherit',
            border: `1px solid ${T.line}`, background: 'rgba(255,255,255,0.04)',
            fontSize: 13, fontWeight: 700, color: T.sub,
          }}>
            <Ic name="edit" size={14} color={T.sub} sw={1.9} />Edit this plan
          </button>

          <div style={{ display: 'flex', gap: 14, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Ic name="clock" size={13} color={T.faint} sw={2} />
              <span style={{ fontSize: 12, color: T.sub, fontWeight: 600 }}>{plan.mins}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Ic name="dumbbell" size={13} color={T.faint} sw={1.9} />
              <span style={{ fontSize: 12, color: T.sub, fontWeight: 600 }}>{plan.moves.length} movements</span>
            </div>
          </div>

          {/* movement list with sets */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
            {plan.moves.map((mv, i) => (
              <div key={mv.name + i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{
                  width: 24, height: 24, borderRadius: 8, flexShrink: 0,
                  background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700, color: T.faint, fontVariantNumeric: 'tabular-nums',
                }}>{i + 1}</span>
                <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: T.text }}>{mv.name}</span>
                <span style={{ fontSize: 12, color: T.sub, fontWeight: 600, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{mv.sets}</span>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 16 }}>
            {plan.tags.map((t) => <Tag key={t} color={T.blue}>{t}</Tag>)}
          </div>
        </React.Fragment>
      )}
    </Card>
  );
}

// ─────────────────────────────────────────────────────────────
// User selector — tap the avatar to switch between users
// ─────────────────────────────────────────────────────────────
function UserSelector() {
  const T = useTheme();
  const store = useFit();
  const [open, setOpen] = React.useState(false);
  const users = store.users || [];
  const current = users.find(u => u.user_id === store.currentUid);
  const label = current ? current.label : 'Loading…';

  return (
    <div style={{ position: 'relative' }}>
      <button className="press" onClick={() => setOpen(!open)} style={{
        display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', fontFamily: 'inherit',
        padding: '6px 11px', borderRadius: 999,
        border: `1px solid ${open ? `color-mix(in srgb, ${T.blue} 40%, transparent)` : T.line}`,
        background: open ? `color-mix(in srgb, ${T.blue} 13%, transparent)` : 'rgba(255,255,255,0.04)',
        fontSize: 11.5, fontWeight: 700, color: open ? T.blue : T.sub,
      }}>
        <Ic name="user" size={13} color={open ? T.blue : T.sub} sw={2} />
        <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
        <Ic name={open ? 'chevL' : 'chevR'} size={11} color={open ? T.blue : T.faint} sw={2.4} style={open ? { transform: 'rotate(-90deg)' } : { transform: 'rotate(90deg)' }} />
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', right: 0, marginTop: 6, zIndex: 50,
          width: 260, maxHeight: 320, overflowY: 'auto',
          background: T.card, border: `1px solid ${T.line}`, borderRadius: 14,
          boxShadow: '0 16px 48px rgba(0,0,0,0.55)',
          padding: 6,
        }} className="scroll-hidden">
          {users.map(u => {
            const on = u.user_id === store.currentUid;
            return (
              <button key={u.user_id} className="press" onClick={() => {
                if (!on) switchUser(u.user_id);
                setOpen(false);
              }} style={{
                display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left',
                padding: '10px 10px', borderRadius: 10, cursor: 'pointer', fontFamily: 'inherit',
                border: on ? `1px solid color-mix(in srgb, ${T.blue} 40%, transparent)` : '1px solid transparent',
                background: on ? `color-mix(in srgb, ${T.blue} 11%, transparent)` : 'transparent',
              }}>
                <span style={{
                  width: 16, height: 16, borderRadius: 99, flexShrink: 0,
                  border: on ? 'none' : `1.5px solid ${T.line}`, background: on ? T.blue : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>{on && <Ic name="check" size={10} color="#081019" sw={3} />}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 600, color: on ? T.text : T.sub, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.label}</div>
                  <div style={{ fontSize: 10, color: T.faint, marginTop: 2 }}>{u.session_count} sessions{u.last_workout ? ` · last ${u.last_workout}` : ''}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SCREEN 1 — Fitness Report (default home)
// ─────────────────────────────────────────────────────────────
// Today's Plan — compact tile (taps through to the editable plan)
function TodayPlanCard({ nav }) {
  const T = useTheme();
  const store = useFit();
  const plan = getPlan(store.plan);
  return (
    <button className="press" onClick={() => nav.push('plan-detail')} style={{
      display: 'flex', alignItems: 'center', gap: 13, width: '100%', textAlign: 'left',
      padding: 13, borderRadius: T.radius, cursor: 'pointer', fontFamily: 'inherit',
      border: `1px solid color-mix(in srgb, ${T.blue} 30%, transparent)`,
      background: `linear-gradient(135deg, color-mix(in srgb, ${T.blue} 15%, ${T.card}), ${T.card} 72%)`,
      boxShadow: T.glow ? `0 10px 28px rgba(0,0,0,0.32), 0 0 60px -30px ${T.blue}` : '0 10px 28px rgba(0,0,0,0.32)',
    }}>
      <div style={{
        width: 46, height: 46, borderRadius: 13, flexShrink: 0,
        background: `color-mix(in srgb, ${T.blue} 20%, transparent)`,
        border: `1px solid color-mix(in srgb, ${T.blue} 34%, transparent)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}><Ic name="dumbbell" size={22} color={T.blue} sw={1.9} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.11em', textTransform: 'uppercase', color: T.blue, marginBottom: 3 }}>Today's Plan · Mon</div>
        <div style={{ fontSize: 16, fontWeight: 800, color: T.text, letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{plan.name}</div>
        <div style={{ fontSize: 11.5, color: T.faint, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>{plan.mins} · {plan.moves.length} movements</div>
      </div>
      <Ic name="chevR" size={16} color={T.blue} sw={2.3} />
    </button>
  );
}

function FitnessReport({ nav }) {
  const T = useTheme();
  const store = useFit();
  const w = getWorkout(store.selected);
  const isLatest = WORKOUTS.length > 0 && w.id === WORKOUTS[WORKOUTS.length - 1].id;

  if (store.loading) {
    return (
      <div data-screen-label="Fitness · Report">
        <ScreenHeader kicker="Training log & review" title="Fitness" accent={T.blue} right={<UserSelector />} />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '80px 0', color: T.faint, fontSize: 13, fontWeight: 600 }}>
          Loading workout data…
        </div>
      </div>
    );
  }

  return (
    <div data-screen-label="Fitness · Report">
      <ScreenHeader kicker="Training log & review" title="Fitness" accent={T.blue} right={<UserSelector />} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 16px 0' }}>

        {/* Selectable week timeline (with calendar toggle) */}
        <WeekCalendarCard nav={nav} />

        {/* Video + timelines + comparison */}
        <WorkoutVideo videoFile={w.videoFile} dateStr={w.id} />

        {/* Selected workout — focal card with the one ring */}
        <Card pad={20} glowColor={T.blue}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <SectionLabel>{isLatest ? 'Last Workout' : 'Workout'}</SectionLabel>
            <Tag color={T.blue}>{w.intensity}</Tag>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <Ring key={w.id} size={132} stroke={10} value={w.score} color={T.blue}>
              {(n) => (
                <React.Fragment>
                  <span style={{ fontSize: 36, fontWeight: 800, color: T.text, letterSpacing: '-0.03em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{n}</span>
                  <span style={{ fontSize: 10.5, fontWeight: 600, color: T.faint, letterSpacing: '0.06em' }}>/ 100</span>
                </React.Fragment>
              )}
            </Ring>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 19, fontWeight: 800, color: T.text, letterSpacing: '-0.01em', lineHeight: 1.15 }}>{w.type}</div>
              <div style={{ fontSize: 12, color: T.faint, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>{w.when} · {w.time}</div>
              <div style={{ display: 'flex', gap: 20, marginTop: 16 }}>
                <div>
                  <div style={{ fontSize: 10.5, color: T.faint, marginBottom: 3 }}>Duration</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{w.dur}<span style={{ fontSize: 11, color: T.sub, marginLeft: 2 }}>min</span></div>
                </div>
                <div>
                  <div style={{ fontSize: 10.5, color: T.faint, marginBottom: 3 }}>Calories</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{w.kcal}<span style={{ fontSize: 11, color: T.sub, marginLeft: 2 }}>kcal</span></div>
                </div>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', margin: '18px 0 4px' }}>
            <span style={{ fontSize: 11, color: T.faint, marginRight: 2, alignSelf: 'center' }}>Primary</span>
            {w.primary.map((m) => <Tag key={m} color={T.blue}>{m}</Tag>)}
          </div>
        </Card>

        {/* Today's plan — compact tile */}
        <TodayPlanCard nav={nav} />

        {/* AI session recap */}
        <AICard title="Session Recap" accent={T.blue}>{w.recap}</AICard>

        {/* Single action */}
        <GhostBtn icon="chevR" primary onClick={() => nav.push('workout-report')}>View Full Report</GhostBtn>

        {/* This week status */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
            <SectionLabel>Last 7 Days</SectionLabel>
            <Tag color={T.blue}>More stable than last wk</Tag>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>
            <StatTile label="Sessions" value={String(WEEKLY_STATS.sessions)} />
            <StatTile label="Total time" value={String(WEEKLY_STATS.totalMin)} unit="min" />
            <StatTile label="Avg score" value={WEEKLY_STATS.avgScore} />
          </div>
        </Card>

        {/* Muscle coverage preview — last 7 days */}
        <Card pad={18} onClick={() => nav.push('fitness-insights')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
            <SectionLabel>Muscle Coverage · 7 days</SectionLabel>
            <Ic name="chevR" size={14} color={T.faint} sw={2.2} />
          </div>
          <MuscleCoverage rows={COVERAGE_7D} front={COVERAGE_7D_FRONT} back={COVERAGE_7D_BACK} />
        </Card>

        {/* Next session reminder — lightweight tone */}
        <AICard title="Next Time" accent={T.blue}>
          You've leaned into upper body this week, so next session could be a good moment to add legs or core. If you'd rather keep training upper body, consider easing back on shoulder volume to avoid stacking strain.
        </AICard>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Dual-timeline bar — ground truth vs recognition
// ─────────────────────────────────────────────────────────────
const TL_COLORS = {
  exercise:   'rgb(238,122,90)',
  transition: 'rgba(255,255,255,0.10)',
  rest:       'rgba(255,255,255,0.06)',
};

function fmtSec(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, '0')}`;
}

function TimelineBar({ segments, totalSec, label, color }) {
  const T = useTheme();
  if (!segments || !segments.length || !totalSec) return null;
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: color || T.faint, marginBottom: 5 }}>{label}</div>
      <div style={{ position: 'relative', height: 22, borderRadius: 5, overflow: 'hidden', background: 'rgba(255,255,255,0.04)', border: `1px solid ${T.line}` }}>
        {segments.map((seg, i) => {
          const start = seg.start ?? seg.start_sec ?? 0;
          const end   = seg.end   ?? seg.end_sec   ?? start;
          const type  = seg.type  ?? (seg.state === 'EXERCISE' ? 'exercise' : 'transition');
          const left  = (start / totalSec) * 100;
          const width = ((end - start) / totalSec) * 100;
          const isEx  = type === 'exercise';
          const name  = seg.label || seg.exercise_name || (seg.segmentId ? '' : '');
          return (
            <div key={i} title={`${name || type} ${fmtSec(start)}–${fmtSec(end)}`} style={{
              position: 'absolute', top: 0, bottom: 0,
              left: `${left}%`, width: `${Math.max(width, 0.3)}%`,
              background: isEx ? TL_COLORS.exercise : TL_COLORS[type] || TL_COLORS.transition,
              borderRight: '0.5px solid rgba(0,0,0,0.3)',
            }}>
              {isEx && width > 5 && (
                <span style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', fontSize: 8, fontWeight: 700, color: '#fff', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden', maxWidth: '90%' }}>{name}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function recSegToUnified(seg) {
  const isEx = (seg.state === 'EXERCISE');
  return {
    start: seg.start_sec ?? 0,
    end:   seg.end_sec ?? 0,
    type:  isEx ? 'exercise' : 'transition',
    label: isEx ? (seg.exercise_name || seg.segmentId || '') : '',
  };
}

// ─────────────────────────────────────────────────────────────
// Video + dual timeline + comparison table
// ─────────────────────────────────────────────────────────────
function WorkoutVideo({ videoFile, dateStr }) {
  const T = useTheme();
  const [gt, setGt] = React.useState(null);
  const [rec, setRec] = React.useState(null);
  const [versions, setVersions] = React.useState([]);
  const [ver, setVer] = React.useState('');
  const [recExercises, setRecExercises] = React.useState([]);
  const videoRef = React.useRef(null);

  React.useEffect(() => {
    if (!videoFile) { setGt(null); setRec(null); setVersions([]); return; }
    fetch(`${API_BASE}/ground-truth?date=${dateStr}`).then(r => r.json()).then(d => {
      setGt(d.found ? d : null);
    }).catch(() => setGt(null));
    fetch(`${API_BASE}/recognition-versions?date=${dateStr}`).then(r => r.json()).then(v => {
      setVersions(v || []);
      if (v && v.length > 0) setVer(prev => (v.includes(prev) ? prev : v[v.length - 1]));
    }).catch(() => setVersions([]));
  }, [videoFile, dateStr]);

  React.useEffect(() => {
    if (!ver || !videoFile) { setRec(null); setRecExercises([]); return; }
    fetch(`${API_BASE}/recognition-result?version=${ver}&date=${dateStr}`).then(r => r.json()).then(d => {
      if (d.found) {
        setRec(d.timeline || []);
        setRecExercises(d.exercises || []);
      } else {
        setRec(null);
        setRecExercises([]);
      }
    }).catch(() => { setRec(null); setRecExercises([]); });
  }, [ver, videoFile, dateStr]);

  if (!videoFile) return null;

  const src = `${API_BASE.replace('/api', '')}/video/${encodeURIComponent(videoFile)}`;
  const gtSegs = gt ? gt.data : [];
  const recSegs = rec ? rec.map(recSegToUnified) : [];
  const totalSec = Math.max(
    ...gtSegs.map(s => s.end ?? s.end_sec ?? 0),
    ...recSegs.map(s => s.end ?? 0),
    1
  );

  const gtExercises = gtSegs.filter(s => s.type === 'exercise');
  const recExList = recExercises.map(ex => {
    const totalReps = (ex.result?.sets || []).reduce((sum, s) => sum + (s.reps || 0), 0);
    return {
      name: ex.result?.exercise || ex.segmentId || '?',
      sets: (ex.result?.sets || []).length,
      reps: totalReps,
      startSec: ex.startTime ?? 0,
      endSec: ex.endTime ?? 0,
    };
  });

  const seekTo = (sec) => {
    if (videoRef.current) { videoRef.current.currentTime = sec; videoRef.current.play(); }
  };

  return (
    <React.Fragment>
      {/* Video + timelines side by side */}
      <Card pad={12}>
        <div style={{ display: 'flex', gap: 10 }}>
          {/* Timeline bars */}
          <div style={{ width: 120, flexShrink: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <TimelineBar segments={gtSegs} totalSec={totalSec} label="Ground Truth" color="#4CAF50" />
            <TimelineBar segments={recSegs} totalSec={totalSec} label={`Rec ${ver}`} color={T.blue} />
            {/* Time axis */}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: T.faint, fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>
              <span>0:00</span>
              <span>{fmtSec(totalSec)}</span>
            </div>
          </div>

          {/* Video */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <video
              ref={videoRef}
              key={videoFile}
              controls
              playsInline
              preload="metadata"
              style={{ width: '100%', display: 'block', borderRadius: 10 }}
              src={src}
            />
          </div>
        </div>

        {/* Version selector */}
        {versions.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: T.faint, letterSpacing: '0.06em' }}>VER</span>
            {versions.map(v => (
              <button key={v} className="press" onClick={() => setVer(v)} style={{
                padding: '3px 9px', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 11, fontWeight: 700,
                border: v === ver ? `1px solid ${T.blue}` : `1px solid ${T.line}`,
                background: v === ver ? `color-mix(in srgb, ${T.blue} 18%, transparent)` : 'transparent',
                color: v === ver ? T.blue : T.faint,
              }}>{v}</button>
            ))}
          </div>
        )}
      </Card>

      {/* Comparison table */}
      {(gtExercises.length > 0 || recExList.length > 0) && (
        <Card pad={14}>
          <SectionLabel style={{ marginBottom: 12 }}>Exercise Comparison</SectionLabel>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${T.line}` }}>
                  <th style={{ textAlign: 'left', padding: '6px 6px', color: T.faint, fontWeight: 700, fontSize: 10 }}>#</th>
                  <th style={{ textAlign: 'left', padding: '6px 6px', color: '#4CAF50', fontWeight: 700, fontSize: 10 }}>Ground Truth</th>
                  <th style={{ textAlign: 'center', padding: '6px 4px', color: '#4CAF50', fontWeight: 700, fontSize: 10 }}>Sets</th>
                  <th style={{ textAlign: 'center', padding: '6px 4px', color: '#4CAF50', fontWeight: 700, fontSize: 10 }}>Reps</th>
                  <th style={{ textAlign: 'left', padding: '6px 6px', color: T.blue, fontWeight: 700, fontSize: 10 }}>Recognition</th>
                  <th style={{ textAlign: 'center', padding: '6px 4px', color: T.blue, fontWeight: 700, fontSize: 10 }}>Sets</th>
                  <th style={{ textAlign: 'center', padding: '6px 4px', color: T.blue, fontWeight: 700, fontSize: 10 }}>Reps</th>
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: Math.max(gtExercises.length, recExList.length) }).map((_, i) => {
                  const g = gtExercises[i];
                  const r = recExList[i];
                  const parseGtReps = (repsStr) => {
                    if (!repsStr) return { sets: 1, reps: 0 };
                    const parts = String(repsStr).trim().split(/\s+/);
                    const total = parts.reduce((s, p) => s + (parseInt(p, 10) || 0), 0);
                    return { sets: parts.length, reps: total };
                  };
                  const gParsed = g ? parseGtReps(g.reps) : null;
                  return (
                    <tr key={i} style={{ borderBottom: `1px solid ${T.line}`, cursor: 'pointer' }} className="press"
                      onClick={() => seekTo(g ? g.start : (r ? r.startSec : 0))}>
                      <td style={{ padding: '8px 6px', color: T.faint, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{i + 1}</td>
                      <td style={{ padding: '8px 6px', color: g ? T.text : T.faint, fontWeight: 600 }}>{g ? g.label : '—'}</td>
                      <td style={{ padding: '8px 4px', textAlign: 'center', color: T.sub, fontVariantNumeric: 'tabular-nums' }}>{gParsed ? gParsed.sets : '—'}</td>
                      <td style={{ padding: '8px 4px', textAlign: 'center', color: T.sub, fontVariantNumeric: 'tabular-nums' }}>{gParsed ? gParsed.reps : '—'}</td>
                      <td style={{ padding: '8px 6px', color: r ? T.text : T.faint, fontWeight: 600 }}>{r ? r.name : '—'}</td>
                      <td style={{ padding: '8px 4px', textAlign: 'center', color: T.sub, fontVariantNumeric: 'tabular-nums' }}>{r ? r.sets : '—'}</td>
                      <td style={{ padding: '8px 4px', textAlign: 'center', color: T.sub, fontVariantNumeric: 'tabular-nums' }}>{r ? r.reps : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </React.Fragment>
  );
}

Object.assign(window, {
  FitnessReport, BodyFigure, MuscleCoverage,
  FitnessTabs, MuscleBars, Timeline, GhostBtn, WeekStrip, WeekCalendarCard, MonthCalendar, TrainingSuggestions,
  UserSelector, WorkoutVideo,
});

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
            onClick={has ? () => { loadDailyWorkout(w.wid).then(() => { store.set({ selected: w.wid }); nav.push('workout-report'); }); } : undefined}
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
                loadDailyWorkout(wid).then(() => { store.set({ selected: wid }); nav.push('workout-report'); });
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
// Body figure — colors driven by the SAME level map as the bars
// ─────────────────────────────────────────────────────────────
function BodyFigure({ view, zones }) {
  const T = useTheme();
  const meta = levelMeta(T);
  const base = 'rgba(255,255,255,0.05)';
  const stroke = 'rgba(255,255,255,0.09)';
  const fill = (lvl) => (lvl && meta[lvl]) ? meta[lvl].color : base;
  const front = view === 'front';
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <svg width="84" height="164" viewBox="0 0 100 196">
        <circle cx="50" cy="14" r="9.5" fill={base} stroke={stroke} />
        <rect x="44.5" y="24" width="11" height="7" rx="3.5" fill={base} stroke={stroke} />
        <circle cx="30" cy="38" r="8.5" fill={fill(zones.shoulders)} stroke={stroke} />
        <circle cx="70" cy="38" r="8.5" fill={fill(zones.shoulders)} stroke={stroke} />
        <rect x="33" y="31" width="34" height={front ? 17 : 21} rx="7.5" fill={front ? fill(zones.chest) : fill(zones.upperBack)} stroke={stroke} />
        <rect x="36" y={front ? 50 : 54} width="28" height={front ? 24 : 18} rx="8" fill={front ? fill(zones.core) : fill(zones.lowerBack)} stroke={stroke} />
        <rect x="18" y="35" width="9" height="28" rx="4.5" fill={front ? fill(zones.biceps) : fill(zones.triceps)} stroke={stroke} />
        <rect x="73" y="35" width="9" height="28" rx="4.5" fill={front ? fill(zones.biceps) : fill(zones.triceps)} stroke={stroke} />
        <rect x="16.5" y="66" width="8" height="24" rx="4" fill={base} stroke={stroke} />
        <rect x="75.5" y="66" width="8" height="24" rx="4" fill={base} stroke={stroke} />
        <rect x="36.5" y="77" width="27" height="13" rx="6.5" fill={base} stroke={stroke} />
        <rect x="36.5" y="92" width="11.5" height="44" rx="5.75" fill={fill(zones.legs)} stroke={stroke} />
        <rect x="52" y="92" width="11.5" height="44" rx="5.75" fill={fill(zones.legs)} stroke={stroke} />
        <rect x="38" y="139" width="9.5" height="34" rx="4.75" fill={base} stroke={stroke} />
        <rect x="52.5" y="139" width="9.5" height="34" rx="4.75" fill={base} stroke={stroke} />
        <rect x="36.5" y="176" width="12" height="6" rx="3" fill={base} stroke={stroke} />
        <rect x="51.5" y="176" width="12" height="6" rx="3" fill={base} stroke={stroke} />
      </svg>
      <span style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: '0.14em', color: T.faint }}>{front ? 'FRONT' : 'BACK'}</span>
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
  return (
    <div data-screen-label="Fitness · Report">
      <ScreenHeader kicker="Training log & review" title="Fitness" accent={T.blue} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 16px 0' }}>

        {/* Selectable week timeline (with calendar toggle) */}
        <WeekCalendarCard nav={nav} />

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

Object.assign(window, {
  FitnessReport, BodyFigure, MuscleCoverage,
  FitnessTabs, MuscleBars, Timeline, GhostBtn, WeekStrip, WeekCalendarCard, MonthCalendar, TrainingSuggestions,
});

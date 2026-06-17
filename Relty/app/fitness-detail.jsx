// fitness-detail.jsx — Workout Report + Movement Edit + Insights + Plan

// ─────────────────────────────────────────────────────────────
// Small pieces
// ─────────────────────────────────────────────────────────────
function ConfTag({ conf }) {
  const T = useTheme();
  const c = conf === 'High' ? T.blue : conf === 'Medium' ? '#E0B45A' : T.faint;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span style={{ display: 'flex', gap: 2 }}>
        {[0, 1, 2].map((i) => {
          const lit = conf === 'High' ? i < 3 : conf === 'Medium' ? i < 2 : i < 1;
          return <span key={i} style={{ width: 4, height: 9, borderRadius: 1.5, background: lit ? c : 'rgba(255,255,255,0.12)' }}></span>;
        })}
      </span>
      <span style={{ fontSize: 11, fontWeight: 700, color: c }}>{conf}</span>
    </span>
  );
}

function MiniMetric({ label, value, tag, tagColor }) {
  const T = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 10.5, color: T.faint, fontWeight: 500 }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ fontSize: 15.5, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        {tag && <Tag color={tagColor}>{tag}</Tag>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SCREEN 2 — Workout Report (reflects the selected day)
// ─────────────────────────────────────────────────────────────
function WorkoutReport({ nav }) {
  const T = useTheme();
  const store = useFit();
  const w = getWorkout(store.selected);
  const openEdit = (m, i) => {
    store.set({ movement: { ...m, wid: w.id, idx: i } });
    nav.push('movement-edit');
  };
  return (
    <div data-screen-label="Fitness · Workout Report">
      <ScreenHeader
        kicker={`${w.when} · ${w.time}`}
        title="Workout Report"
        accent={T.blue}
        onBack={() => {
          const latest = WORKOUTS.length > 0 ? WORKOUTS[WORKOUTS.length - 1].id : null;
          if (latest) store.set({ selected: latest });
          nav.pop('fitness-report');
        }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {/* Type line */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '0 2px' }}>
          <Ic name="dumbbell" size={17} color={T.blue} sw={1.9} />
          <span style={{ fontSize: 15, fontWeight: 700, color: T.text }}>{w.type}</span>
          <Tag color={T.blue}>Strength</Tag>
        </div>

        {/* Score — the one ring on this screen */}
        <Card pad={20} glowColor={T.blue}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <Ring key={w.id} size={140} stroke={11} value={w.score} color={T.blue}>
              {(n) => (
                <React.Fragment>
                  <span style={{ fontSize: 38, fontWeight: 800, color: T.text, letterSpacing: '-0.03em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{n}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: T.faint, letterSpacing: '0.06em' }}>/ 100</span>
                </React.Fragment>
              )}
            </Ring>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 13, minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <SectionLabel>Workout Score</SectionLabel>
                <div><Tag color={T.blue} filled>{w.intensity}</Tag></div>
              </div>
              <MiniMetric label="Total time" value={`${w.dur} min`} />
              <MiniMetric label="Active burn" value={`${w.kcal} kcal`} />
              <MiniMetric label="Training load" value={w.load} tag="Est." tagColor={T.faint} />
            </div>
          </div>
        </Card>

        {/* Session timeline — vertical, no timestamps */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 16 }}>Session Timeline · {w.dur} min</SectionLabel>
          <Timeline items={w.timeline} />
        </Card>

        {/* Movement review — tap a row to correct it */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
            <SectionLabel>Movement Review</SectionLabel>
            <span style={{ fontSize: 10.5, color: T.faint }}>est. reps · confidence</span>
          </div>
          <div style={{ fontSize: 11.5, color: T.faint, marginBottom: 16, lineHeight: 1.5 }}>
            Detected from motion patterns — tap any movement to correct it.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {w.movements.map((ex, i) => (
              <div key={ex.name + i} className="press" onClick={() => openEdit(ex, i)} style={{
                background: 'rgba(255,255,255,0.03)', border: `1px solid ${T.line}`,
                borderRadius: 14, padding: 14, cursor: 'pointer',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                  <span style={{ flex: 1, fontSize: 13.5, fontWeight: 700, color: T.text }}>{ex.name}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: T.faint }}>Edit</span>
                  <Ic name="chevR" size={13} color={T.faint} sw={2.2} />
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 10.5, color: T.faint, marginBottom: 3 }}>{ex.reps.length} sets · est. reps</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: T.sub, fontVariantNumeric: 'tabular-nums', letterSpacing: '0.02em' }}>{ex.reps.join(' · ')}</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 10.5, color: T.faint, marginBottom: 3 }}>Stability</div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: T.sub }}>{ex.stability}</div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
                    <span style={{ fontSize: 10.5, color: T.faint }}>Confidence</span>
                    <ConfTag conf={ex.conf} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Muscle coverage — figure + bars share the same level colors */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 16 }}>Muscle Coverage</SectionLabel>
          <MuscleCoverage rows={w.coverage} front={w.figureFront} back={w.figureBack} gap={14} />
        </Card>

        {/* Training load note */}
        <AICard title="Training Load" accent={T.blue}>
          This session's load reads as <strong style={{ color: T.text, fontWeight: 600 }}>{w.load.toLowerCase()}</strong>, based on duration, strength set count, rest intervals and movement continuity. Stable heart-rate data isn't connected yet, so recovery is shown for reference only.
        </AICard>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Movement Edit — correction screen (reached by tapping a movement)
// ─────────────────────────────────────────────────────────────
function Stepper({ value, onChange, min = 0, max = 30 }) {
  const T = useTheme();
  const btn = (label, fn, dis) => (
    <button className={dis ? undefined : 'press'} onClick={dis ? undefined : fn} style={{
      width: 32, height: 32, borderRadius: 9, flexShrink: 0, cursor: dis ? 'default' : 'pointer',
      border: `1px solid ${T.line}`, background: 'rgba(255,255,255,0.05)', fontFamily: 'inherit',
      color: dis ? 'rgba(255,255,255,0.2)' : T.text, fontSize: 18, fontWeight: 600, lineHeight: 1,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{label}</button>
  );
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      {btn('−', () => onChange(value - 1), value <= min)}
      <span style={{ minWidth: 26, textAlign: 'center', fontSize: 16, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      {btn('+', () => onChange(value + 1), value >= max)}
    </div>
  );
}

function MovementEdit({ nav }) {
  const T = useTheme();
  const store = useFit();
  const m = store.movement || { name: '', reps: [10], stability: 'Steady', conf: 'High' };
  const [name, setName] = React.useState(m.name);
  const [reps, setReps] = React.useState(m.reps.slice());
  const alts = MOVEMENT_ALTS[m.name] || [m.name];

  const setRep = (i, v) => setReps((r) => r.map((x, j) => (j === i ? Math.max(1, Math.min(30, v)) : x)));
  const addSet = () => setReps((r) => [...r, r[r.length - 1] || 10]);
  const removeSet = (i) => setReps((r) => (r.length > 1 ? r.filter((_, j) => j !== i) : r));

  return (
    <div data-screen-label="Fitness · Edit Movement">
      <ScreenHeader
        kicker="Correct recognition"
        title="Edit Movement"
        accent={T.blue}
        onBack={() => nav.pop('workout-report')}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {/* Detected banner */}
        <Card pad={16} style={{ background: `linear-gradient(140deg, color-mix(in srgb, ${T.blue} 7%, ${T.card}), ${T.card} 62%)` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{
              width: 34, height: 34, borderRadius: 10, flexShrink: 0,
              background: `color-mix(in srgb, ${T.blue} 15%, transparent)`,
              border: `1px solid color-mix(in srgb, ${T.blue} 30%, transparent)`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}><Ic name="dumbbell" size={17} color={T.blue} sw={1.9} /></span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 11, color: T.faint }}>Detected as</div>
              <div style={{ fontSize: 14.5, fontWeight: 700, color: T.text }}>{m.name}</div>
            </div>
            <ConfTag conf={m.conf} />
          </div>
        </Card>

        {/* Rename / pick correct movement */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 14 }}>Movement</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {alts.map((a) => {
              const on = a === name;
              return (
                <button key={a} className="press" onClick={() => setName(a)} style={{
                  display: 'flex', alignItems: 'center', gap: 11, width: '100%', textAlign: 'left',
                  padding: '12px 13px', borderRadius: 12, cursor: 'pointer', fontFamily: 'inherit',
                  border: on ? `1px solid color-mix(in srgb, ${T.blue} 45%, transparent)` : `1px solid ${T.line}`,
                  background: on ? `color-mix(in srgb, ${T.blue} 11%, transparent)` : 'rgba(255,255,255,0.03)',
                }}>
                  <span style={{
                    width: 18, height: 18, borderRadius: 99, flexShrink: 0,
                    border: on ? 'none' : `1.5px solid ${T.line}`, background: on ? T.blue : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>{on && <Ic name="check" size={11} color="#081019" sw={3} />}</span>
                  <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: on ? T.text : T.sub }}>{a}</span>
                </button>
              );
            })}
          </div>
        </Card>

        {/* Sets & reps */}
        <Card pad={18}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <SectionLabel>Sets &amp; Reps</SectionLabel>
            <span style={{ fontSize: 11.5, color: T.faint, fontVariantNumeric: 'tabular-nums' }}>{reps.length} sets</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {reps.map((r, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{
                  width: 26, height: 26, borderRadius: 8, flexShrink: 0,
                  background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700, color: T.faint, fontVariantNumeric: 'tabular-nums',
                }}>{i + 1}</span>
                <span style={{ flex: 1, fontSize: 13, color: T.sub }}>reps</span>
                <Stepper value={r} onChange={(v) => setRep(i, v)} min={1} />
                {reps.length > 1 && (
                  <button className="press" onClick={() => removeSet(i)} style={{
                    width: 30, height: 30, borderRadius: 8, flexShrink: 0, cursor: 'pointer',
                    border: `1px solid ${T.line}`, background: 'transparent', fontFamily: 'inherit',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}><Ic name="trash" size={14} color={T.faint} sw={1.9} /></button>
                )}
              </div>
            ))}
          </div>
          <button className="press" onClick={addSet} style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, width: '100%',
            marginTop: 14, padding: '11px 0', borderRadius: 11, cursor: 'pointer', fontFamily: 'inherit',
            border: `1px dashed ${T.line}`, background: 'transparent',
            fontSize: 13, fontWeight: 600, color: T.sub,
          }}>
            <Ic name="plus" size={14} color={T.sub} sw={2.2} />Add set
          </button>
        </Card>

        {/* Segment-level corrections (moved here from Fix Recognition) */}
        <Card pad={16}>
          <SectionLabel style={{ marginBottom: 12 }}>Segment</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            {[
              { icon: 'merge', label: 'Merge with previous movement' },
              { icon: 'trash', label: 'Remove this segment', danger: true },
            ].map((a) => (
              <button key={a.label} className="press" onClick={() => nav.pop('workout-report')} style={{
                display: 'flex', alignItems: 'center', gap: 12, width: '100%',
                padding: '12px 13px', borderRadius: 12, cursor: 'pointer', fontFamily: 'inherit',
                border: `1px solid ${a.danger ? 'color-mix(in srgb, #E0655A 32%, transparent)' : T.line}`,
                background: 'rgba(255,255,255,0.03)', textAlign: 'left',
              }}>
                <span style={{
                  width: 30, height: 30, borderRadius: 9, flexShrink: 0,
                  background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}><Ic name={a.icon} size={15} color={a.danger ? '#E0655A' : T.sub} sw={1.9} /></span>
                <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: a.danger ? '#E0655A' : T.text }}>{a.label}</span>
                <Ic name="chevR" size={14} color={T.faint} sw={2.1} />
              </button>
            ))}
          </div>
        </Card>

        {/* Save / cancel */}
        <div style={{ display: 'flex', gap: 10, paddingBottom: 4 }}>
          <GhostBtn onClick={() => nav.pop('workout-report')}>Cancel</GhostBtn>
          <GhostBtn icon="check" primary onClick={() => nav.pop('workout-report')}>Save Changes</GhostBtn>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// SCREEN 3 — Insights (suggestions entry moved to Report)
// ─────────────────────────────────────────────────────────────
function FitnessInsights({ nav }) {
  const T = useTheme();
  const [range, setRange] = React.useState('Week');
  const isWeek = range === 'Week';

  const weekLoad = WEEKLY_INSIGHTS.weekLoad.length > 0
    ? WEEKLY_INSIGHTS.weekLoad
    : [{ label: '-', value: 0, state: 'today' }];

  return (
    <div data-screen-label="Fitness · Insights">
      <ScreenHeader kicker="Trends from your real records" title="Insights" accent={T.blue} onBack={() => nav.pop('fitness-report')} />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 16px 0' }}>

        {/* Range toggle */}
        <SegControl options={['Week', 'Month']} value={range} onChange={setRange} />

        {isWeek ? (
          <React.Fragment>
            {/* Last 7 days overview */}
            <Card pad={18}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
                <SectionLabel>Last 7 Days</SectionLabel>
                <Tag color={T.blue}>Stable</Tag>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', rowGap: 18, columnGap: 10, marginBottom: 18 }}>
                <TrendStat label="Sessions" value={String(WEEKLY_INSIGHTS.sessions)} />
                <TrendStat label="Total time" value={WEEKLY_INSIGHTS.totalTime} unit="min" />
                <TrendStat label="Avg score" value={WEEKLY_INSIGHTS.avgScore} />
                <TrendStat label="Main type" value={WEEKLY_INSIGHTS.mainType} />
                <TrendStat label="Consistency" value={WEEKLY_INSIGHTS.consistency} />
                <TrendStat label="Streak" value={WEEKLY_INSIGHTS.streak} unit="wk" />
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.faint, marginBottom: 12 }}>Daily training load</div>
              <VBars data={weekLoad} color={T.blue} height={84} topLabel unit="" />
            </Card>

            {/* Muscle coverage trend */}
            <Card pad={18}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
                <SectionLabel>Muscle Coverage</SectionLabel>
                <span style={{ fontSize: 10.5, color: T.faint }}>last 7 days</span>
              </div>
              <MuscleCoverage rows={COVERAGE_7D} front={COVERAGE_7D_FRONT} back={COVERAGE_7D_BACK} />
            </Card>

            {/* Imbalance reminder */}
            <AICard title="Balance" accent={T.blue}>
              Over the last 7 days your training has leaned upper body, with <strong style={{ color: T.text, fontWeight: 600 }}>legs and core running light</strong>. If you train next, you could consider adding a lower-body or core block — no rush.
            </AICard>

            {/* Activity-linked insight */}
            <Card pad={16} style={{ background: `linear-gradient(140deg, color-mix(in srgb, ${T.green} 6%, ${T.card}), ${T.card} 62%)` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
                <Ic name="pulse" size={15} color={T.green} sw={2} />
                <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.green }}>From Activity</span>
              </div>
              <div style={{ fontSize: 13.5, lineHeight: 1.55, color: T.sub, textWrap: 'pretty' }}>
                You had a long sedentary stretch yesterday afternoon, and warm-up before your evening session ran short. Next time, 5 minutes of dynamic warm-up could help.
              </div>
            </Card>
          </React.Fragment>
        ) : (
          <React.Fragment>
            {/* Last 30 days overview */}
            <Card pad={18}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 18 }}>
                <SectionLabel>Last 30 Days</SectionLabel>
                <Tag color={T.blue}>Building</Tag>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', rowGap: 18, columnGap: 10, marginBottom: 18 }}>
                <TrendStat label="Sessions" value={String(MONTHLY_INSIGHTS.sessions)} />
                <TrendStat label="Total time" value={MONTHLY_INSIGHTS.totalTime} />
                <TrendStat label="Avg score" value={MONTHLY_INSIGHTS.avgScore} />
                <TrendStat label="Per week" value={MONTHLY_INSIGHTS.perWeek} />
                <TrendStat label="Main type" value={MONTHLY_INSIGHTS.mainType} />
                <TrendStat label="Streak" value={MONTHLY_INSIGHTS.streak} unit="wk" />
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: T.faint, marginBottom: 12 }}>Weekly training load</div>
              <VBars data={MONTH_LOAD} color={T.blue} height={84} topLabel unit="" />
            </Card>

            {/* Muscle coverage trend — month */}
            <Card pad={18}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 16 }}>
                <SectionLabel>Muscle Coverage</SectionLabel>
                <span style={{ fontSize: 10.5, color: T.faint }}>last 30 days</span>
              </div>
              <MuscleCoverage rows={COVERAGE_30D} front={COVERAGE_30D_FRONT} back={COVERAGE_30D_BACK} />
            </Card>

            {/* Monthly balance reminder */}
            <AICard title="Monthly Balance" accent={T.blue}>
              Across the month, push and pull volume are well established and your <strong style={{ color: T.text, fontWeight: 600 }}>streak held for 3 weeks</strong>. Legs have improved but still trail the upper body — a steady lower-body day each week would even things out.
            </AICard>
          </React.Fragment>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Plan Detail — read view of today's plan (resembles Training
// Suggestions). Switch plans here, or step into the editor.
// ─────────────────────────────────────────────────────────────
function PlanDetail({ nav }) {
  const T = useTheme();
  const store = useFit();
  const [picking, setPicking] = React.useState(false);
  const plan = getPlan(store.plan);

  return (
    <div data-screen-label="Fitness · Today's Plan">
      <ScreenHeader
        kicker="Today · Mon, Jun 15"
        title="Today's Plan"
        accent={T.blue}
        onBack={() => nav.pop('fitness-report')}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {picking ? (
          /* ── choose a plan ── */
          <Card pad={18}>
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
                const pv = getPlan(p.id);
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
                      <div style={{ fontSize: 13.5, fontWeight: 700, color: on ? T.text : T.sub }}>{pv.name}</div>
                      <div style={{ fontSize: 11, color: T.faint, marginTop: 2 }}>{pv.why} · {pv.moves.length} moves</div>
                    </div>
                    <span style={{ fontSize: 11, color: T.faint, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{pv.mins}</span>
                  </button>
                );
              })}
            </div>
          </Card>
        ) : (
          <React.Fragment>
            {/* Plan summary card */}
            <Card pad={20} glowColor={T.blue}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: T.text, letterSpacing: '-0.02em', lineHeight: 1.1 }}>{plan.name}</div>
                  <div style={{ fontSize: 12.5, color: T.faint, marginTop: 4 }}>{plan.why}</div>
                </div>
                <button className="press" onClick={() => setPicking(true)} style={{
                  display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0, cursor: 'pointer', fontFamily: 'inherit',
                  padding: '7px 12px', borderRadius: 999, border: `1px solid color-mix(in srgb, ${T.blue} 38%, transparent)`,
                  background: `color-mix(in srgb, ${T.blue} 12%, transparent)`,
                  fontSize: 12, fontWeight: 700, color: T.blue,
                }}>Switch <Ic name="chevR" size={11} color={T.blue} sw={2.6} /></button>
              </div>

              <div style={{ display: 'flex', gap: 16, marginBottom: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Ic name="clock" size={14} color={T.faint} sw={2} />
                  <span style={{ fontSize: 12.5, color: T.sub, fontWeight: 600 }}>{plan.mins}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Ic name="dumbbell" size={14} color={T.faint} sw={1.9} />
                  <span style={{ fontSize: 12.5, color: T.sub, fontWeight: 600 }}>{plan.moves.length} movements</span>
                </div>
              </div>

              {/* movement list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
                {plan.moves.map((mv, i) => (
                  <div key={(mv.name || '') + i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{
                      width: 24, height: 24, borderRadius: 8, flexShrink: 0,
                      background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, fontWeight: 700, color: T.faint, fontVariantNumeric: 'tabular-nums',
                    }}>{i + 1}</span>
                    <span style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: T.text }}>{mv.name || 'Untitled'}</span>
                    <span style={{ fontSize: 12, color: T.sub, fontWeight: 600, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{mv.sets}</span>
                  </div>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 18 }}>
                {plan.tags.map((t) => <Tag key={t} color={T.blue}>{t}</Tag>)}
              </div>
            </Card>

            {/* AI note */}
            <AICard title="Why this plan" accent={T.blue}>
              {plan.why}. It's a light reference drawn from your recent records — adjust the movements, sets or duration anytime.
            </AICard>

            {/* Actions */}
            <div style={{ display: 'flex', gap: 10, paddingBottom: 4 }}>
              <GhostBtn icon="edit" onClick={() => nav.push('plan-edit')}>Edit Plan</GhostBtn>
              <GhostBtn icon="check" primary onClick={() => nav.pop('fitness-report')}>Looks Good</GhostBtn>
            </div>
          </React.Fragment>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Plan Edit — view & modify today's plan (reached from Today's Plan tile)
// ─────────────────────────────────────────────────────────────
function PlanField({ value, onChange, placeholder, style }) {
  const T = useTheme();
  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      style={{
        width: '100%', boxSizing: 'border-box', fontFamily: 'inherit',
        background: 'rgba(255,255,255,0.04)', border: `1px solid ${T.line}`,
        borderRadius: 10, padding: '10px 12px', color: T.text,
        fontSize: 14, fontWeight: 600, outline: 'none', ...style,
      }}
    />
  );
}

function PlanEdit({ nav }) {
  const T = useTheme();
  const store = useFit();
  const [picking, setPicking] = React.useState(false);

  const base = getPlan(store.plan);
  const [name, setName] = React.useState(base.name);
  const [mins, setMins] = React.useState(base.mins);
  const [moves, setMoves] = React.useState(base.moves.map((m) => ({ ...m })));

  // re-seed local fields when the user switches which plan is today's
  React.useEffect(() => {
    const p = getPlan(store.plan);
    setName(p.name); setMins(p.mins); setMoves(p.moves.map((m) => ({ ...m })));
  }, [store.plan]);

  const setMove = (i, patch) => setMoves((ms) => ms.map((m, j) => (j === i ? { ...m, ...patch } : m)));
  const removeMove = (i) => setMoves((ms) => (ms.length > 1 ? ms.filter((_, j) => j !== i) : ms));
  const addMove = () => setMoves((ms) => [...ms, { name: '', sets: '3 × 10' }]);

  const save = () => {
    store.set({ planEdits: { ...store.planEdits, [store.plan]: { name, mins, moves } } });
    nav.pop('fitness-report');
  };

  return (
    <div data-screen-label="Fitness · Today's Plan">
      <ScreenHeader
        kicker="Today · Mon, Jun 15"
        title="Today's Plan"
        accent={T.blue}
        onBack={() => nav.pop('fitness-report')}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {picking ? (
          /* ── pick which plan is today's ── */
          <Card pad={18}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <SectionLabel>Choose today's plan</SectionLabel>
              <button className="press" onClick={() => setPicking(false)} style={{
                border: 'none', background: 'transparent', cursor: 'pointer', fontFamily: 'inherit',
                fontSize: 12.5, fontWeight: 700, color: T.faint,
              }}>Done</button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {PLANS.map((p) => {
                const on = p.id === store.plan;
                const pv = getPlan(p.id);
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
                      <div style={{ fontSize: 13.5, fontWeight: 700, color: on ? T.text : T.sub }}>{pv.name}</div>
                      <div style={{ fontSize: 11, color: T.faint, marginTop: 2 }}>{pv.mins} · {pv.moves.length} moves</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </Card>
        ) : (
          <React.Fragment>
            {/* Plan name + duration */}
            <Card pad={18}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <SectionLabel>Plan</SectionLabel>
                <button className="press" onClick={() => setPicking(true)} style={{
                  display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer', fontFamily: 'inherit',
                  padding: '6px 11px', borderRadius: 999, border: `1px solid color-mix(in srgb, ${T.blue} 38%, transparent)`,
                  background: `color-mix(in srgb, ${T.blue} 12%, transparent)`,
                  fontSize: 12, fontWeight: 700, color: T.blue,
                }}>Switch <Ic name="chevR" size={11} color={T.blue} sw={2.6} /></button>
              </div>
              <PlanField value={name} onChange={setName} placeholder="Plan name" style={{ fontSize: 15.5, fontWeight: 700, marginBottom: 9 }} />
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Ic name="clock" size={15} color={T.faint} sw={2} />
                <PlanField value={mins} onChange={setMins} placeholder="Duration" style={{ flex: 1 }} />
              </div>
            </Card>

            {/* Movements */}
            <Card pad={18}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <SectionLabel>Movements</SectionLabel>
                <span style={{ fontSize: 11.5, color: T.faint, fontVariantNumeric: 'tabular-nums' }}>{moves.length} total</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {moves.map((mv, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{
                      width: 24, height: 24, borderRadius: 8, flexShrink: 0,
                      background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, fontWeight: 700, color: T.faint, fontVariantNumeric: 'tabular-nums',
                    }}>{i + 1}</span>
                    <PlanField value={mv.name} onChange={(v) => setMove(i, { name: v })} placeholder="Movement" style={{ flex: 1, minWidth: 0 }} />
                    <PlanField value={mv.sets} onChange={(v) => setMove(i, { sets: v })} placeholder="3 × 10"
                      style={{ width: 78, flexShrink: 0, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }} />
                    <button className="press" onClick={() => removeMove(i)} style={{
                      width: 32, height: 32, borderRadius: 8, flexShrink: 0, cursor: 'pointer',
                      border: `1px solid ${T.line}`, background: 'transparent', fontFamily: 'inherit',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}><Ic name="trash" size={14} color={T.faint} sw={1.9} /></button>
                  </div>
                ))}
              </div>
              <button className="press" onClick={addMove} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, width: '100%',
                marginTop: 14, padding: '11px 0', borderRadius: 11, cursor: 'pointer', fontFamily: 'inherit',
                border: `1px dashed ${T.line}`, background: 'transparent',
                fontSize: 13, fontWeight: 600, color: T.sub,
              }}>
                <Ic name="plus" size={14} color={T.sub} sw={2.2} />Add movement
              </button>
            </Card>

            {/* Save / cancel */}
            <div style={{ display: 'flex', gap: 10, paddingBottom: 4 }}>
              <GhostBtn onClick={() => nav.pop('fitness-report')}>Cancel</GhostBtn>
              <GhostBtn icon="check" primary onClick={save}>Save Plan</GhostBtn>
            </div>
          </React.Fragment>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { WorkoutReport, MovementEdit, FitnessInsights, PlanDetail, PlanEdit });

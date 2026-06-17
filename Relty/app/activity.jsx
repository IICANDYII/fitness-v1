// activity.jsx — Activity module: Today Overview + Activity Detail (timeline)

// Shared day data
const DAY_MIX = [
  { id: 'walk', label: 'Walking / Commute', dur: '3h 02m', min: 182 },
  { id: 'outdoor', label: 'Outdoor activity', dur: '1h 45m', min: 105 },
  { id: 'gym', label: 'Gym training', dur: '1h 10m', min: 70 },
  { id: 'idle', label: 'Sedentary / Still', dur: '1h 13m', min: 73 },
];

// Day band segments, 07:00 → 23:00 (16h = 960 min)
const DAY_BAND = [
  { t: 'idle', from: 420, to: 490 },    // 7:00–8:10
  { t: 'walk', from: 490, to: 522 },    // 8:10 walk
  { t: 'idle', from: 522, to: 630 },
  { t: 'outdoor', from: 630, to: 678 }, // 10:30 ride
  { t: 'idle', from: 678, to: 750 },
  { t: 'gym', from: 750, to: 795 },     // 12:30 gym
  { t: 'idle', from: 795, to: 885 },    // 14:45 sedentary (long)
  { t: 'walk', from: 885, to: 950 },
  { t: 'idle', from: 950, to: 1100 },
  { t: 'walk', from: 1100, to: 1150 },
  { t: 'idle', from: 1150, to: 1380 },
];

function mixColor(T, id) {
  if (id === 'walk') return T.green;
  if (id === 'outdoor') return `color-mix(in oklab, ${T.green} 45%, #3FC8E0)`;
  if (id === 'gym') return T.blue;
  return 'rgba(255,255,255,0.14)';
}

// Horizontal day band (07:00–23:00)
function DayBand({ h = 26 }) {
  const T = useTheme();
  const start = 420, span = 960;
  return (
    <div>
      <div style={{ display: 'flex', gap: 2, height: h, borderRadius: 7, overflow: 'hidden' }}>
        {DAY_BAND.map((s, i) => (
          <div key={i} style={{
            width: `${((s.to - s.from) / span) * 100}%`,
            background: s.t === 'idle' ? 'rgba(255,255,255,0.06)' : mixColor(T, s.t),
            borderRadius: 3,
          }}></div>
        ))}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 7, padding: '0 1px' }}>
        {['7 AM', '11 AM', '3 PM', '7 PM', '11 PM'].map((l) => (
          <span key={l} style={{ fontSize: 9.5, color: T.faint, fontVariantNumeric: 'tabular-nums' }}>{l}</span>
        ))}
      </div>
    </div>
  );
}

function MixLegendDot({ color }) {
  return <span style={{ width: 8, height: 8, borderRadius: 99, background: color, flexShrink: 0 }}></span>;
}

// ─────────────────────────────────────────────────────────────
// Screen 1 — Activity Home / Today Overview
// ─────────────────────────────────────────────────────────────
function ActivityHome({ nav }) {
  const T = useTheme();
  const totalMin = DAY_MIX.reduce((a, m) => a + m.min, 0);
  return (
    <div data-screen-label="Activity · Today Overview">
      <ScreenHeader
        kicker="Today · Fri, Jun 12"
        title="Activity"
        accent={T.green}
        right={<HeaderIconBtn icon="spark" color={T.green} />}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>

        {/* Activity Score — the one ring on this screen */}
        <Card pad={20} glowColor={T.green} onClick={() => nav.push('activity-detail')}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <Ring size={150} stroke={11} value={86} color={T.green}>
              {(n) => (
                <React.Fragment>
                  <span style={{ fontSize: 42, fontWeight: 800, color: T.text, letterSpacing: '-0.03em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{n}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: T.faint, letterSpacing: '0.06em' }}>/ 100</span>
                </React.Fragment>
              )}
            </Ring>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>
              <SectionLabel>Activity Score</SectionLabel>
              <div><Tag color={T.green}>Good</Tag></div>
              <div style={{ fontSize: 13, color: T.sub, lineHeight: 1.5, textWrap: 'pretty' }}>Steady activity rhythm today.</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 12, fontWeight: 600, color: T.green }}>
                Day detail <Ic name="chevR" size={12} color={T.green} sw={2.4} />
              </div>
            </div>
          </div>
        </Card>

        {/* Active stats */}
        <Card pad={18}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 1fr', rowGap: 18, columnGap: 10 }}>
            <StatTile icon="clock" label="Active time" value="7h 10m" />
            <StatTile icon="bolt" label="Active burn" value="612" unit="kcal" />
            <StatTile icon="shoe" label="Steps" value="9,842" />
            <StatTile icon="pin" label="Distance" value="7.3" unit="km" />
            <div style={{ gridColumn: '2 / 4', display: 'flex', flexDirection: 'column', gap: 7 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <span style={{ fontSize: 11.5, color: T.faint, fontWeight: 500 }}>Daily goal</span>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: T.green, fontVariantNumeric: 'tabular-nums' }}>72%</span>
              </div>
              <HBar value={72} color={T.green} h={6} />
            </div>
          </div>
        </Card>

        {/* Activity mix */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 13 }}>Activity Mix</SectionLabel>
          <div style={{ display: 'flex', gap: 2, height: 10, borderRadius: 6, overflow: 'hidden', marginBottom: 14 }}>
            {DAY_MIX.map((m) => (
              <div key={m.id} style={{ width: `${(m.min / totalMin) * 100}%`, background: mixColor(T, m.id), borderRadius: 3 }}></div>
            ))}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
            {DAY_MIX.map((m) => (
              <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                <MixLegendDot color={mixColor(T, m.id)} />
                <span style={{ flex: 1, fontSize: 13, color: T.sub }}>{m.label}</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{m.dur}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Day timeline preview */}
        <Card pad={18} onClick={() => nav.push('activity-detail')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <SectionLabel>Today's Timeline</SectionLabel>
            <Ic name="chevR" size={13} color={T.faint} sw={2.2} />
          </div>
          <DayBand />
        </Card>

        {/* Sedentary watch */}
        <Card pad={16}>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 11, flexShrink: 0,
              background: 'rgba(224,180,90,0.12)', border: '1px solid rgba(224,180,90,0.25)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Ic name="pause" size={16} color="#E0B45A" sw={2.2} />
            </div>
            <div style={{ minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: T.text }}>Longest still period</span>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#E0B45A', fontVariantNumeric: 'tabular-nums' }}>96 min</span>
              </div>
              <div style={{ fontSize: 12.5, color: T.sub, lineHeight: 1.5, textWrap: 'pretty' }}>
                Try 5 minutes of shoulder mobility or a short walk before bed.
              </div>
            </div>
          </div>
        </Card>

        {/* Trend report entry */}
        <TrendEntry
          accent={T.green}
          subtitle="Weekly patterns, sedentary &amp; regularity"
          data={[412, 455, 280, 470, 430]}
          onClick={() => nav.push('activity-trends')}
        />

        {/* AI agent summary */}
        <AICard accent={T.green}>
          Moderate activity overall today. You logged walking blocks in the morning and early afternoon, and finished a gym session at midday. One long still stretch after lunch — light stretching tonight will help recovery.
        </AICard>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Screen 2 — Activity Detail / Full-day timeline
// ─────────────────────────────────────────────────────────────
const EVENTS = [
  {
    time: '08:10', icon: 'shoe', type: 'walk', title: 'Walk · Commute',
    stats: [['Duration', '32 min'], ['Distance', '2.6 km'], ['Burn', '156 kcal']],
    tag: 'Light',
  },
  {
    time: '10:30', icon: 'bike', type: 'outdoor', title: 'Outdoor · Ride',
    stats: [['Duration', '48 min'], ['Distance', '18.6 km'], ['Burn', '316 kcal']],
    tag: 'Moderate',
  },
  {
    time: '12:30', icon: 'dumbbell', type: 'gym', title: 'Gym Workout',
    stats: [['Duration', '45 min'], ['Burn', '512 kcal'], ['Type', 'Strength']],
    cta: true,
  },
  {
    time: '14:45', icon: 'pause', type: 'idle', title: 'Sedentary',
    stats: [['Duration', '96 min']],
    note: 'Long still period — consider standing up to move.',
  },
];

function TimelineEvent({ ev, isLast, nav }) {
  const T = useTheme();
  const c = ev.type === 'idle' ? '#E0B45A' : mixColor(T, ev.type);
  return (
    <div style={{ display: 'flex', gap: 13 }}>
      {/* rail */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 38, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: T.faint, fontVariantNumeric: 'tabular-nums', marginBottom: 6 }}>{ev.time}</span>
        <span style={{
          width: 10, height: 10, borderRadius: 99, background: c, flexShrink: 0,
          boxShadow: T.glow ? `0 0 8px color-mix(in srgb, ${c} 60%, transparent)` : 'none',
        }}></span>
        {!isLast && <div style={{ width: 1.5, flex: 1, background: 'rgba(255,255,255,0.08)', marginTop: 6, minHeight: 24 }}></div>}
      </div>
      {/* card */}
      <Card pad={14} style={{ flex: 1, marginBottom: isLast ? 0 : 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 10 }}>
          <Ic name={ev.icon} size={15} color={c} sw={2} />
          <span style={{ fontSize: 14, fontWeight: 700, color: T.text, flex: 1 }}>{ev.title}</span>
          {ev.tag && <Tag color={c}>{ev.tag}</Tag>}
        </div>
        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {ev.stats.map(([l, v]) => (
            <div key={l} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: 10.5, color: T.faint }}>{l}</span>
              <span style={{ fontSize: 13.5, fontWeight: 600, color: T.sub, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
            </div>
          ))}
        </div>
        {ev.note && <div style={{ fontSize: 12, color: T.sub, marginTop: 10, lineHeight: 1.5 }}>{ev.note}</div>}
        {ev.cta && (
          <button className="press" onClick={() => nav.push('workout-report')} style={{
            marginTop: 12, width: '100%', padding: '10px 0', borderRadius: 11,
            border: `1px solid color-mix(in srgb, ${T.blue} 35%, transparent)`,
            background: `color-mix(in srgb, ${T.blue} 13%, transparent)`,
            color: T.blue, fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'inherit',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
          }}>
            View Workout Report <Ic name="chevR" size={12} color={T.blue} sw={2.5} />
          </button>
        )}
      </Card>
    </div>
  );
}

function ActivityDetail({ nav }) {
  const T = useTheme();
  const [tab, setTab] = React.useState('Timeline');
  const totalMin = DAY_MIX.reduce((a, m) => a + m.min, 0);
  return (
    <div data-screen-label="Activity · Day Detail">
      <ScreenHeader title="Activity Detail" kicker="Fri, Jun 12" accent={T.green} onBack={() => nav.pop('activity-home')} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '4px 16px 0' }}>
        <SegControl options={['Timeline', 'Breakdown', 'Insights']} value={tab} onChange={setTab} />

        {tab === 'Timeline' && (
          <div style={{ paddingTop: 4 }}>
            {EVENTS.map((ev, i) => (
              <TimelineEvent key={ev.time} ev={ev} isLast={i === EVENTS.length - 1} nav={nav} />
            ))}
          </div>
        )}

        {tab === 'Breakdown' && (
          <Card pad={18}>
            <SectionLabel style={{ marginBottom: 13 }}>Time by Type</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 15 }}>
              {DAY_MIX.map((m) => (
                <div key={m.id}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, color: T.sub }}>{m.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontVariantNumeric: 'tabular-nums' }}>{m.dur}</span>
                  </div>
                  <HBar value={(m.min / totalMin) * 100} color={mixColor(T, m.id)} h={5} />
                </div>
              ))}
            </div>
          </Card>
        )}

        {tab === 'Insights' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <Card pad={16}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>Most active window</div>
              <div style={{ fontSize: 12.5, color: T.sub, lineHeight: 1.5 }}>10:30 – 11:18 AM, during your outdoor ride — 316 kcal in 48 minutes.</div>
            </Card>
            <Card pad={16}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>Sedentary trend</div>
              <div style={{ fontSize: 12.5, color: T.sub, lineHeight: 1.5 }}>Still time is 22% above your 7-day average, concentrated after lunch.</div>
            </Card>
            <Card pad={16}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 4 }}>Weekly pace</div>
              <div style={{ fontSize: 12.5, color: T.sub, lineHeight: 1.5 }}>Active burn is on pace to clear your weekly goal one day early.</div>
            </Card>
          </div>
        )}

        {/* Day totals */}
        <Card pad={18}>
          <SectionLabel style={{ marginBottom: 14 }}>Day Totals</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', rowGap: 18, columnGap: 12 }}>
            <StatTile icon="shoe" label="Steps" value="9,842" />
            <StatTile icon="pin" label="Distance" value="7.3" unit="km" />
            <StatTile icon="bolt" label="Active burn" value="1,136" unit="kcal" />
            <StatTile icon="clock" label="Active time" value="7h 48m" />
          </div>
        </Card>

        {/* Score recap — deliberately NO ring here */}
        <Card pad={16}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Ic name="pulse" size={16} color={T.green} sw={2.2} />
            <span style={{ flex: 1, fontSize: 13, color: T.sub }}>Activity Score</span>
            <span style={{ fontSize: 16, fontWeight: 800, color: T.text, fontVariantNumeric: 'tabular-nums' }}>86<span style={{ fontSize: 12, fontWeight: 600, color: T.faint }}> / 100</span></span>
            <Tag color={T.green}>Good</Tag>
          </div>
        </Card>
      </div>
    </div>
  );
}

Object.assign(window, { ActivityHome, ActivityDetail, mixColor, DayBand });

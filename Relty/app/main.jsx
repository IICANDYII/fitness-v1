// main.jsx — app shell: theme, navigation, device frame, tweaks

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "activityAccent": "#3FD17E",
  "fitnessAccent": "#4D9FFF",
  "cardRadius": 20,
  "ringGlow": true
}/*EDITMODE-END*/;

const SCREENS = {
  'activity-home': { comp: (p) => <ActivityHome {...p} />, tab: 'activity' },
  'activity-detail': { comp: (p) => <ActivityDetail {...p} />, tab: 'activity' },
  'activity-trends': { comp: (p) => <ActivityTrends {...p} />, tab: 'activity' },
  'fitness-report': { comp: (p) => <FitnessReport {...p} />, tab: 'fitness' },
  'workout-report': { comp: (p) => <WorkoutReport {...p} />, tab: 'fitness' },
  'movement-edit': { comp: (p) => <MovementEdit {...p} />, tab: 'fitness' },
  'fitness-insights': { comp: (p) => <FitnessInsights {...p} />, tab: 'fitness' },
  'plan-detail': { comp: (p) => <PlanDetail {...p} />, tab: 'fitness' },
  'plan-edit': { comp: (p) => <PlanEdit {...p} />, tab: 'fitness' },
};

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  const theme = React.useMemo(() => ({
    bg: '#0A0B0D',
    card: '#15171C',
    line: 'rgba(255,255,255,0.07)',
    text: '#F2F4F7',
    sub: 'rgba(230,235,243,0.62)',
    faint: 'rgba(230,235,243,0.38)',
    green: t.activityAccent,
    blue: t.fitnessAccent,
    radius: t.cardRadius,
    glow: t.ringGlow,
  }), [t]);

  // ── navigation: keep at most 2 scenes (under-layer + animating top)
  const keyRef = React.useRef(1);
  const [scenes, setScenes] = React.useState(() => {
    const saved = localStorage.getItem('relty-screen');
    const name = SCREENS[saved] ? saved : 'activity-home';
    return [{ name, key: 0, anim: 'none' }];
  });
  const current = scenes[scenes.length - 1];

  React.useEffect(() => {
    localStorage.setItem('relty-screen', current.name);
  }, [current.name]);

  React.useEffect(() => {
    if (scenes.length > 1) {
      const id = setTimeout(() => setScenes((s) => s.slice(-1)), 400);
      return () => clearTimeout(id);
    }
  }, [scenes]);

  const go = (name, anim) => {
    setScenes((s) => {
      const top = s[s.length - 1];
      if (top.name === name) return s;
      return [top, { name, key: keyRef.current++, anim }];
    });
  };
  const nav = {
    push: (n) => go(n, 'push'),
    pop: (n) => go(n, 'pop'),
    tab: (n) => go(n, 'tab'),
  };

  return (
    <ThemeCtx.Provider value={theme}>
      <FitStage>
        <IOSDevice dark width={390} height={844}>
          <div style={{
            height: '100%', position: 'relative', background: theme.bg,
            fontFamily: "-apple-system, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', Helvetica, sans-serif",
            color: theme.text, overflow: 'hidden',
          }}>
            {/* scenes */}
            {scenes.map((sc, i) => {
              const def = SCREENS[sc.name];
              const isTop = i === scenes.length - 1;
              const animClass = isTop && sc.anim !== 'none'
                ? (sc.anim === 'push' ? 'scene-push' : sc.anim === 'pop' ? 'scene-pop' : 'scene-tab')
                : '';
              return (
                <div key={sc.key} className={`scroll-hidden ${animClass}`} style={{
                  position: 'absolute', inset: 0, overflowY: 'auto',
                  background: theme.bg, paddingBottom: 116,
                  pointerEvents: isTop ? 'auto' : 'none',
                  zIndex: isTop ? 2 : 1,
                }}>
                  {def.comp({ nav })}
                </div>
              );
            })}

            {/* status bar scrim */}
            <div style={{
              position: 'absolute', top: 0, left: 0, right: 0, height: 70, zIndex: 8,
              background: 'linear-gradient(to bottom, rgba(10,11,13,0.92) 35%, transparent)',
              pointerEvents: 'none',
            }}></div>

            <BottomNav active={SCREENS[current.name].tab} onTab={nav.tab} />
          </div>
        </IOSDevice>
      </FitStage>

      <TweaksPanel>
        <TweakSection label="Module Accents" />
        <TweakColor label="Activity" value={t.activityAccent}
          options={['#3FD17E', '#2FCBA4', '#9BD14A']}
          onChange={(v) => setTweak('activityAccent', v)} />
        <TweakColor label="Fitness" value={t.fitnessAccent}
          options={['#4D9FFF', '#5E7BFF', '#38BDF8']}
          onChange={(v) => setTweak('fitnessAccent', v)} />
        <TweakSection label="Surface" />
        <TweakSlider label="Card radius" value={t.cardRadius} min={12} max={28} step={1} unit="px"
          onChange={(v) => setTweak('cardRadius', v)} />
        <TweakToggle label="Ring glow" value={t.ringGlow}
          onChange={(v) => setTweak('ringGlow', v)} />
      </TweaksPanel>
    </ThemeCtx.Provider>
  );
}

// Scales the 390×844 device to fit the viewport
function FitStage({ children }) {
  const [s, setS] = React.useState(1);
  React.useEffect(() => {
    const f = () => setS(Math.min(1, (window.innerHeight - 36) / 854, (window.innerWidth - 36) / 400));
    f();
    window.addEventListener('resize', f);
    return () => window.removeEventListener('resize', f);
  }, []);
  return (
    <div style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ transform: `scale(${s})` }}>{children}</div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

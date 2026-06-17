// shared.jsx — design tokens, icons, and shared UI primitives for the Relty wearable app
// Exports to window at the bottom.

const ThemeCtx = React.createContext(null);
const useTheme = () => React.useContext(ThemeCtx);

// ── Icons ────────────────────────────────────────────────────
const ICON_PATHS = {
  home: 'M4 11.5L12 4.5l8 7V20a1 1 0 01-1 1h-4.6v-5.6h-4.8V21H5a1 1 0 01-1-1z',
  pulse: 'M3 12.5h3.5L9.5 6l4.5 12 2.5-5.5H21',
  dumbbell: 'M7 8.5v7M10.5 6.5v11M13.5 6.5v11M17 8.5v7M10.5 12h3M3.5 12H7M17 12h3.5',
  trends: 'M4 17l5-6 4 3 7-8.5',
  chevR: 'M9.5 5.5l6.5 6.5-6.5 6.5',
  chevL: 'M14.5 5.5L8 12l6.5 6.5',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  pause: 'M9 6.5v11M15 6.5v11',
  edit: 'M4 20.2h4.1L19 9.3l-4.1-4.1L4 16.1zM13.6 6.1l4.1 4.1',
  search: 'M10.8 4.5a6.3 6.3 0 100 12.6 6.3 6.3 0 000-12.6zM19.5 19.5l-4.2-4.2',
  filter: 'M4 5.5h16l-6.3 7.4v5.1l-3.4 1.8v-6.9z',
  plus: 'M12 5v14M5 12h14',
  trash: 'M4.5 7h15M9 7V4.8h6V7M6.5 7l1 12.2h9l1-12.2',
  merge: 'M6 4.5v3.8a5.2 5.2 0 005.2 5.2H18M14.4 9.6L18.2 13.5 14.4 17.4',
  flame: 'M12 3.5c3.4 3 4.8 5.8 4.8 8.6a4.8 4.8 0 11-9.6 0c0-1.6.7-3 1.8-4.2.3 1.4 1 2.1 1.9 2.4-.3-2.4.4-4.7 1.1-6.8z',
};

function Ic({ name, size = 20, color = 'currentColor', sw = 1.8, style }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', style: { display: 'block', flexShrink: 0, ...style } };
  if (name === 'spark') {
    return (
      <svg {...common}>
        <path d="M12 3.2l1.8 5 5 1.8-5 1.8-1.8 5-1.8-5-5-1.8 5-1.8z" fill={color} />
        <circle cx="19" cy="4.6" r="1.4" fill={color} opacity="0.7" />
      </svg>
    );
  }
  if (name === 'bolt') {
    return <svg {...common}><path d="M13.2 2.5L5.5 13.2H11l-1.2 8.3 7.7-10.7H12z" fill={color} /></svg>;
  }
  if (name === 'user') {
    return (
      <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="8.2" r="3.4" />
        <path d="M5 20c1.2-3.4 3.9-5.1 7-5.1s5.8 1.7 7 5.1" />
      </svg>
    );
  }
  if (name === 'clock') {
    return (
      <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="8.2" />
        <path d="M12 7.5V12l3.2 2" />
      </svg>
    );
  }
  if (name === 'pin') {
    return (
      <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 21c-4-3.7-6.2-7-6.2-9.9a6.2 6.2 0 0112.4 0C18.2 14 16 17.3 12 21z" />
        <circle cx="12" cy="11" r="2.2" />
      </svg>
    );
  }
  if (name === 'cal') {
    return (
      <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <rect x="4" y="5.5" width="16" height="15" rx="3" />
        <path d="M4 10h16M8.5 3.5v3.5M15.5 3.5v3.5" />
      </svg>
    );
  }
  if (name === 'bike') {
    return (
      <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="16.5" r="3.4" />
        <circle cx="18" cy="16.5" r="3.4" />
        <path d="M6 16.5l3.5-6.5h5.5l3 6.5M9.5 10l2.8 6.5M14 7.5h2.5" />
      </svg>
    );
  }
  if (name === 'shoe') {
    return (
      <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
        <path d="M3.5 16.5c0-1.2.8-2.3 2-2.6l3-.9 2-4.5 2.5 2.5h3.5c2.2 0 4 1.8 4 4v1.5h-17z" />
        <path d="M3.5 18.5h17" />
      </svg>
    );
  }
  const d = ICON_PATHS[name] || ICON_PATHS.pulse;
  return (
    <svg {...common} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}

// ── Primitives ───────────────────────────────────────────────
function Card({ children, onClick, style, pad = 16, glowColor }) {
  const T = useTheme();
  return (
    <div
      className={onClick ? 'press' : undefined}
      onClick={onClick}
      style={{
        background: T.card,
        border: `1px solid ${T.line}`,
        borderRadius: T.radius,
        padding: pad,
        boxShadow: glowColor && T.glow
          ? `0 14px 36px rgba(0,0,0,0.4), 0 0 80px -28px ${glowColor}`
          : '0 10px 28px rgba(0,0,0,0.32)',
        position: 'relative',
        cursor: onClick ? 'pointer' : 'default',
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function SectionLabel({ children, style }) {
  const T = useTheme();
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase',
      color: T.faint, padding: '0 2px', ...style,
    }}>{children}</div>
  );
}

function Tag({ children, color, filled }) {
  const T = useTheme();
  const c = color || T.sub;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: '0.04em',
      color: filled ? '#0B0C0E' : c,
      background: filled ? c : `color-mix(in srgb, ${c} 14%, transparent)`,
      border: filled ? 'none' : `1px solid color-mix(in srgb, ${c} 26%, transparent)`,
      borderRadius: 999, padding: '3px 9px', whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function HBar({ value, color, h = 5, track, style }) {
  const T = useTheme();
  return (
    <div style={{ height: h, borderRadius: 99, background: track || 'rgba(255,255,255,0.08)', overflow: 'hidden', ...style }}>
      <div style={{
        width: `${Math.min(100, Math.max(0, value))}%`, height: '100%', borderRadius: 99,
        background: color, transition: 'width 0.6s cubic-bezier(.22,1,.36,1)',
      }}></div>
    </div>
  );
}

// Ring gauge — used ONLY for Activity Score and Workout Score.
// Apple-Fitness-style: sweeps up from 0 on an ease-out, glowing cap rides the
// arc tip, and `children` may be a function that receives the live animated value
// so the number can count up in sync.
function Ring({ size = 156, stroke = 11, value, max = 100, color, duration = 1250, children }) {
  const T = useTheme();
  const idRef = React.useRef('g' + Math.random().toString(36).slice(2, 8));
  const r = (size - stroke) / 2;
  const C = 2 * Math.PI * r;
  const target = Math.min(1, value / max);

  const reduce = typeof window !== 'undefined'
    && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const [prog, setProg] = React.useState(reduce ? target : 0);

  React.useEffect(() => {
    if (reduce) { setProg(target); return; }
    // ease-out-cubic — fast initial sweep that settles, like Fitness rings.
    // Timer-driven (not rAF) so it animates even in throttled/offscreen contexts.
    const ease = (x) => 1 - Math.pow(1 - x, 3);
    const start = performance.now();
    const hold = 90;
    let timer = setInterval(() => {
      const k = Math.min(1, (performance.now() - start - hold) / duration);
      if (k <= 0) return;
      setProg(target * ease(k));
      if (k >= 1) { clearInterval(timer); timer = null; }
    }, 16);
    return () => { if (timer) clearInterval(timer); };
  }, [target, duration, reduce]);

  // cap position — arc starts at 12 o'clock (svg is rotated -90°)
  const ang = -Math.PI / 2 + prog * 2 * Math.PI;
  const cx = size / 2 + r * Math.cos(ang);
  const cy = size / 2 + r * Math.sin(ang);
  const showCap = prog > 0.012 && prog < 0.999;

  return (
    <div style={{ width: size, height: size, position: 'relative', flexShrink: 0 }}>
      <svg width={size} height={size} style={{ display: 'block' }}>
        <defs>
          <linearGradient id={idRef.current} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.5" />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
        </defs>
        <g style={{ transform: 'rotate(-90deg)', transformOrigin: 'center' }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={stroke} />
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none"
            stroke={`url(#${idRef.current})`} strokeWidth={stroke} strokeLinecap="round"
            strokeDasharray={`${C * prog} ${C}`}
            style={{ filter: T.glow ? `drop-shadow(0 0 9px color-mix(in srgb, ${color} 48%, transparent))` : 'none' }}
          />
        </g>
        {/* glowing cap riding the tip */}
        {showCap && (
          <circle cx={cx} cy={cy} r={stroke / 2} fill={color}
            style={{ filter: T.glow ? `drop-shadow(0 0 7px color-mix(in srgb, ${color} 75%, transparent))` : 'none' }} />
        )}
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 1,
      }}>{typeof children === 'function' ? children(Math.round(prog * max)) : children}</div>
    </div>
  );
}

function StatTile({ icon, label, value, unit, accent }) {
  const T = useTheme();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {icon && <Ic name={icon} size={14} color={accent || T.faint} sw={2} />}
        <span style={{ fontSize: 11.5, color: T.faint, fontWeight: 500, letterSpacing: '0.02em', whiteSpace: 'nowrap' }}>{label}</span>
      </div>
      <div style={{ fontSize: 21, fontWeight: 700, color: T.text, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em', lineHeight: 1 }}>
        {value}{unit && <span style={{ fontSize: 12.5, fontWeight: 500, color: T.sub, marginLeft: 3 }}>{unit}</span>}
      </div>
    </div>
  );
}

// ── Screen header ────────────────────────────────────────────
function HeaderIconBtn({ icon, color, onClick }) {
  const T = useTheme();
  return (
    <button className="press" onClick={onClick} style={{
      width: 36, height: 36, borderRadius: 99, border: `1px solid ${T.line}`,
      background: T.card, display: 'flex', alignItems: 'center', justifyContent: 'center',
      cursor: 'pointer', padding: 0,
    }}>
      <Ic name={icon} size={17} color={color || T.sub} sw={2} />
    </button>
  );
}

function ScreenHeader({ kicker, title, onBack, right, accent }) {
  const T = useTheme();
  return (
    <div style={{ padding: '64px 20px 14px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        {onBack && <HeaderIconBtn icon="chevL" onClick={onBack} />}
        <div style={{ minWidth: 0 }}>
          {kicker && <div style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: accent || T.faint, marginBottom: 3 }}>{kicker}</div>}
          <div style={{ fontSize: onBack ? 21 : 27, fontWeight: 700, color: T.text, letterSpacing: '-0.02em', lineHeight: 1.1, whiteSpace: 'nowrap' }}>{title}</div>
        </div>
      </div>
      {right && <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>{right}</div>}
    </div>
  );
}

// ── Segmented control ────────────────────────────────────────
function SegControl({ options, value, onChange }) {
  const T = useTheme();
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: `repeat(${options.length}, 1fr)`, gap: 3,
      background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.line}`,
      borderRadius: 11, padding: 3,
    }}>
      {options.map((o) => (
        <button key={o} onClick={() => onChange(o)} className="press" style={{
          border: 'none', borderRadius: 8, padding: '7px 0', cursor: 'pointer',
          fontSize: 12.5, fontWeight: 600, letterSpacing: '0.01em',
          fontFamily: 'inherit',
          color: value === o ? T.text : T.faint,
          background: value === o ? 'rgba(255,255,255,0.1)' : 'transparent',
          boxShadow: value === o ? '0 2px 8px rgba(0,0,0,0.3)' : 'none',
          transition: 'background 0.2s, color 0.2s',
        }}>{o}</button>
      ))}
    </div>
  );
}

// ── AI insight card ──────────────────────────────────────────
function AICard({ title = 'AI Summary', accent, children }) {
  const T = useTheme();
  const c = accent || T.green;
  return (
    <Card pad={16} style={{ background: `linear-gradient(140deg, color-mix(in srgb, ${c} 7%, ${T.card}), ${T.card} 62%)` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
        <Ic name="spark" size={15} color={c} />
        <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: c }}>{title}</span>
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.55, color: T.sub, textWrap: 'pretty' }}>{children}</div>
    </Card>
  );
}

// ── Bottom navigation ────────────────────────────────────────
function BottomNav({ active, onTab }) {
  const T = useTheme();
  const items = [
    { id: 'home', label: 'Home', icon: 'home' },
    { id: 'activity', label: 'Activity', icon: 'pulse', go: 'activity-home', color: T.green },
    { id: 'fitness', label: 'Fitness', icon: 'dumbbell', go: 'fitness-report', color: T.blue },
    { id: 'trends', label: 'Trends', icon: 'trends' },
    { id: 'profile', label: 'Profile', icon: 'user' },
  ];
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 30,
      background: 'rgba(10,11,13,0.82)',
      backdropFilter: 'blur(18px) saturate(160%)', WebkitBackdropFilter: 'blur(18px) saturate(160%)',
      borderTop: `1px solid ${T.line}`,
      padding: '9px 10px 26px',
      display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 2,
    }}>
      {items.map((it) => {
        const isActive = active === it.id;
        const enabled = !!it.go;
        const color = isActive ? it.color : enabled ? T.sub : 'rgba(232,236,244,0.24)';
        return (
          <button
            key={it.id}
            className={enabled ? 'press' : undefined}
            onClick={enabled ? () => onTab(it.go) : undefined}
            style={{
              background: 'none', border: 'none', cursor: enabled ? 'pointer' : 'default',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              padding: '4px 0', fontFamily: 'inherit',
            }}
          >
            <Ic name={it.icon} size={21} color={color} sw={isActive ? 2.1 : 1.7} />
            <span style={{ fontSize: 10, fontWeight: isActive ? 700 : 500, color, letterSpacing: '0.02em' }}>{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}

Object.assign(window, {
  ThemeCtx, useTheme, Ic, Card, SectionLabel, Tag, HBar, Ring, StatTile,
  ScreenHeader, HeaderIconBtn, SegControl, AICard, BottomNav,
});

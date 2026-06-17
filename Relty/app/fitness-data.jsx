// fitness-data.jsx — API-connected fitness dataset + selection store
// Loaded BEFORE fitness.jsx / fitness-detail.jsx.

const API_BASE = 'http://localhost:8000/api';
const DEFAULT_UID = '00000000-0000-0000-0000-000000025803';

// ── Level → color mapping (shared by bars AND the body figure) ──
function levelMeta(T) {
  return {
    high: { label: 'High', color: T.blue, text: T.blue },
    med: { label: 'Med', color: `color-mix(in srgb, ${T.blue} 58%, rgba(255,255,255,0.06))`, text: T.sub },
    low: { label: 'Low', color: '#E0B45A', text: '#E0B45A' },
  };
}

// ── Backend → Frontend data transformers ──

// Map backend muscle group CN names to EN names used by the Relty UI
const MUSCLE_CN_TO_EN = {
  '胸': 'Chest', '肩': 'Shoulders', '臂': 'Arms', '背': 'Back',
  '腿': 'Legs', '臀': 'Glutes', '腹': 'Core',
};

// Percentage → level
function pctToLevel(pct) {
  if (pct >= 65) return 'high';
  if (pct >= 30) return 'med';
  return 'low';
}

// Convert backend muscle_distribution {肌群: pct} → coverage array
function toCoverage(dist) {
  if (!dist || !Object.keys(dist).length) return [];
  return Object.entries(dist)
    .map(([cn, pct]) => ({
      name: MUSCLE_CN_TO_EN[cn] || cn,
      level: pctToLevel(pct),
      pct: Math.round(pct),
    }))
    .sort((a, b) => b.pct - a.pct);
}

// Convert backend muscle_heatmap → front/back body figure zone objects
function toBodyFigures(heatmap) {
  if (!heatmap) return { front: {}, back: {} };
  const zoneMap = {
    chest: 'chest', shoulders: 'shoulders', 'front-shoulders': 'shoulders',
    'rear-shoulders': 'shoulders', triceps: 'triceps', biceps: 'biceps',
    abdominals: 'core', obliques: 'core',
    quads: 'legs', hamstrings: 'legs', calves: 'legs',
    glutes: 'legs', hips: 'legs',
    lats: 'upperBack', traps: 'upperBack', scapula: 'upperBack',
    lowerback: 'lowerBack',
  };
  const front = {}, back = {};
  Object.entries(heatmap).forEach(([id, pct]) => {
    if (pct <= 0) return;
    const isBack = id.startsWith('b-');
    const bare = isBack ? id.slice(2) : id;
    const zone = zoneMap[bare];
    if (!zone) return;
    const lvl = pctToLevel(pct);
    const target = isBack ? back : front;
    const prev = target[zone];
    if (!prev || lvlRank(lvl) > lvlRank(prev)) target[zone] = lvl;
  });
  return { front, back };
}

function lvlRank(lvl) { return lvl === 'high' ? 3 : lvl === 'med' ? 2 : 1; }

// Convert backend exercises → timeline items
function toTimeline(exercises, categoryDuration) {
  const items = [];
  if (categoryDuration && categoryDuration['有氧'] > 0) {
    items.push({ label: 'Cardio warm-up', detail: `${Math.round(categoryDuration['有氧'] / 60)} min` });
  }
  (exercises || []).forEach(ex => {
    if (['跑步机', '跑步', '慢跑'].some(k => (ex.name || '').includes(k))) return;
    items.push({ label: ex.name_en || ex.name, detail: `${ex.sets} sets`, strong: true });
  });
  items.push({ label: 'Stretch & cooldown', detail: '3 min' });
  return items;
}

// Convert backend exercises → movements for review screen
function toMovements(exercises) {
  return (exercises || []).filter(ex => {
    return !['跑步机', '跑步', '慢跑'].some(k => (ex.name || '').includes(k));
  }).map(ex => ({
    name: ex.name_en || ex.name,
    reps: Array.from({ length: ex.sets || 1 }, () => ex.reps || 0),
    stability: 'Steady',
    conf: 'Medium',
  }));
}

// Workout type from primary muscles
function inferType(summary) {
  if (!summary) return 'Strength Training';
  const p = (summary.primary || []).map(g => MUSCLE_CN_TO_EN[g] || g);
  if (p.some(m => ['Legs', 'Glutes'].includes(m))) return 'Lower Body';
  if (p.some(m => m === 'Back')) return 'Back + Arms';
  if (p.some(m => m === 'Chest')) return 'Chest + Shoulders';
  return 'Strength Training';
}

// Format date to display string
function fmtDate(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${days[d.getDay()]} · ${months[d.getMonth()]} ${d.getDate()}`;
}

function fmtWhen(dateStr) {
  const d = new Date(dateStr + 'T12:00:00');
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const diff = Math.round((today - d) / 86400000);
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  return ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][d.getDay()];
}

// Convert a full /api/daily response → a WORKOUTS-compatible object
function dailyToWorkout(daily, dateStr) {
  const fb = daily.fitness_balance || {};
  const ms = daily.muscle_summary || {};
  const figures = toBodyFigures(daily.muscle_heatmap);
  const primary = (ms.primary || []).map(g => MUSCLE_CN_TO_EN[g] || g);
  return {
    id: dateStr,
    when: fmtWhen(dateStr),
    date: fmtDate(dateStr),
    type: inferType(ms),
    time: '',
    dur: daily.duration_min || 0,
    score: fb.score || 0,
    kcal: daily.calories || 0,
    intensity: fb.score >= 75 ? 'Moderate–High intensity' : fb.score >= 50 ? 'Moderate intensity' : 'Light intensity',
    load: fb.score >= 75 ? 'Moderate–High' : fb.score >= 50 ? 'Moderate' : 'Light',
    primary,
    recap: `Balance score ${fb.score || 0}/100 (G:${fb.G || 0} S:${fb.S || 0} E:${fb.E || 0} C:${fb.C || 0}). ${(ms.missing || []).length > 0 ? 'Missing: ' + (ms.missing || []).map(g => MUSCLE_CN_TO_EN[g] || g).join(', ') + '.' : 'All muscle groups covered.'}`,
    timeline: toTimeline(daily.exercises, daily.category_duration),
    movements: toMovements(daily.exercises),
    coverage: toCoverage(daily.muscle_distribution),
    figureFront: figures.front,
    figureBack: figures.back,
  };
}

// ── API fetch helpers ──

async function apiFetch(path, uid) {
  const id = uid || fitStore.currentUid || DEFAULT_UID;
  const sep = path.includes('?') ? '&' : '?';
  const url = `${API_BASE}${path}${sep}user_id=${encodeURIComponent(id)}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json();
}

// ── Mutable data arrays (replaced by API data on load) ──

let COVERAGE_7D = [];
let COVERAGE_7D_FRONT = {};
let COVERAGE_7D_BACK = {};
let COVERAGE_30D = [];
let COVERAGE_30D_FRONT = {};
let COVERAGE_30D_BACK = {};
let MONTH_LOAD = [];
let WEEK = [];
let WORKOUTS = [];
let WORKOUT_DAYS = {};
const WEEKLY_STATS = { sessions: 0, totalMin: 0, avgScore: '--' };
const WEEKLY_INSIGHTS = {
  sessions: 0, totalTime: '0', avgScore: '--', mainType: 'Strength',
  consistency: '--', streak: '--', weekLoad: [],
};
const MONTHLY_INSIGHTS = {
  sessions: 0, totalTime: '0', avgScore: '--', perWeek: '0',
  mainType: 'Strength', streak: '--',
};

const MOVEMENT_ALTS = {
  'Machine Chest Press': ['Machine Chest Press', 'Incline Chest Press', 'Pec Deck'],
  'Seated Shoulder Press': ['Seated Shoulder Press', 'Machine Shoulder Press', 'Lateral Raise'],
  'Cable Pushdown': ['Cable Pushdown', 'Triceps Pushdown', 'Overhead Extension'],
  'Leg Press': ['Leg Press', 'Hack Squat', 'Smith Squat'],
  'Goblet Squat': ['Goblet Squat', 'Front Squat', 'Box Squat'],
  'Hamstring Curl': ['Hamstring Curl', 'Romanian Deadlift', 'Glute Bridge'],
  'Lat Pulldown': ['Lat Pulldown', 'Assisted Pull-up', 'Straight-arm Pulldown'],
  'Seated Cable Row': ['Seated Cable Row', 'Chest-supported Row', 'Single-arm Row'],
  'Dumbbell Curl': ['Dumbbell Curl', 'Hammer Curl', 'Cable Curl'],
};

const PLANS = [
  {
    id: 'lower', name: 'Lower-body focus', mins: '30–35 min',
    why: 'Balances a light leg week', tags: ['Legs', 'Glutes', 'Core'],
    moves: [
      { name: 'Goblet Squat', sets: '3 × 12' },
      { name: 'Leg Press', sets: '3 × 12' },
      { name: 'Romanian Deadlift', sets: '3 × 10' },
      { name: 'Walking Lunge', sets: '2 × 12' },
      { name: 'Plank', sets: '3 × 40s' },
    ],
  },
  {
    id: 'core', name: 'Core + mobility', mins: '20 min',
    why: 'Core ran low recently', tags: ['Core', 'Mobility'],
    moves: [
      { name: 'Dead Bug', sets: '3 × 10' },
      { name: 'Cable Woodchop', sets: '3 × 12' },
      { name: 'Hanging Knee Raise', sets: '3 × 12' },
      { name: 'Side Plank', sets: '2 × 30s' },
      { name: 'Hip Mobility Flow', sets: '5 min' },
    ],
  },
  {
    id: 'full', name: 'Full-body light', mins: '25 min',
    why: 'Even coverage, low strain', tags: ['Full body'],
    moves: [
      { name: 'Incline Chest Press', sets: '3 × 10' },
      { name: 'Lat Pulldown', sets: '3 × 10' },
      { name: 'Goblet Squat', sets: '3 × 10' },
      { name: 'Shoulder Press', sets: '2 × 12' },
      { name: 'Plank', sets: '2 × 40s' },
    ],
  },
  {
    id: 'push', name: 'Upper push (lighter)', mins: '28 min',
    why: 'Keeps shoulder volume moderate', tags: ['Chest', 'Shoulders', 'Triceps'],
    moves: [
      { name: 'Machine Chest Press', sets: '3 × 10' },
      { name: 'Seated Shoulder Press', sets: '2 × 12' },
      { name: 'Cable Pushdown', sets: '2 × 12' },
      { name: 'Lateral Raise', sets: '2 × 15' },
    ],
  },
];

function getWorkout(id) {
  return WORKOUTS.find((w) => w.id === id) || WORKOUTS[WORKOUTS.length - 1] || {
    id: 'empty', when: 'Today', date: '--', type: 'Rest Day', time: '',
    dur: 0, score: 0, kcal: 0, intensity: '--', load: '--', primary: [],
    recap: 'No workout data available for this day.', timeline: [], movements: [],
    coverage: [], figureFront: {}, figureBack: {},
  };
}

function getPlan(id) {
  const base = PLANS.find((p) => p.id === id) || PLANS[0];
  const e = fitStore.planEdits[base.id];
  return e ? { ...base, ...e } : base;
}

// ── Tiny external store for cross-screen selection ──
const fitStore = {
  selected: null,
  movement: null,
  plan: 'lower',
  planEdits: {},
  loading: true,
  currentUid: DEFAULT_UID,
  users: [],
  _l: new Set(),
  set(patch) { Object.assign(fitStore, patch); fitStore._l.forEach((f) => f()); },
};

function useFit() {
  const [, bump] = React.useState(0);
  React.useEffect(() => {
    const f = () => bump((x) => x + 1);
    fitStore._l.add(f);
    return () => fitStore._l.delete(f);
  }, []);
  return fitStore;
}

// ── Build week strip from calendar data ──
function buildWeek(calendarDays, refYear, refMonth) {
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const todayDate = today.getDate();
  const todayMonth = today.getMonth() + 1;
  const todayYear = today.getFullYear();

  // Build a 7-day strip: today in the middle-ish, or Sunday-first of the current week
  const todayObj = new Date(todayYear, todayMonth - 1, todayDate);
  const dow = todayObj.getDay(); // 0=Sun
  const sunDate = new Date(todayObj);
  sunDate.setDate(todayDate - dow);

  const dayLetters = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const week = [];
  const wkDays = {};

  for (let i = 0; i < 7; i++) {
    const d = new Date(sunDate);
    d.setDate(sunDate.getDate() + i);
    const n = d.getDate();
    const m = d.getMonth() + 1;
    const y = d.getFullYear();
    const ds = `${y}-${String(m).padStart(2, '0')}-${String(n).padStart(2, '0')}`;
    const hasWorkout = calendarDays[ds] === 'full' || calendarDays[ds] === 'partial';
    const isToday = n === todayDate && m === todayMonth && y === todayYear;

    const entry = { d: dayLetters[i], n, today: isToday };
    if (hasWorkout) {
      entry.wid = ds;
      wkDays[n] = ds;
    } else {
      entry.rest = true;
    }
    week.push(entry);
  }
  return { week, wkDays };
}

// ── Load daily data for a specific date (on-demand) ──
async function loadDailyWorkout(dateStr) {
  const existing = WORKOUTS.find(w => w.id === dateStr);
  if (existing) return existing;
  try {
    const daily = await apiFetch(`/daily?date=${dateStr}`);
    if (!daily.date && !daily.duration_min) {
      const w = dailyToWorkout({ fitness_balance: daily.fitness_balance || {}, exercises: [], muscle_distribution: {}, muscle_heatmap: {}, muscle_summary: {} }, dateStr);
      WORKOUTS.push(w);
      return w;
    }
    const w = dailyToWorkout(daily, dateStr);
    const idx = WORKOUTS.findIndex(x => x.id === dateStr);
    if (idx >= 0) WORKOUTS[idx] = w; else WORKOUTS.push(w);
    return w;
  } catch (e) {
    console.warn('loadDailyWorkout failed:', e);
    return null;
  }
}

// ── Load user list ──
async function loadUsers() {
  try {
    const r = await fetch(`${API_BASE}/users`);
    if (!r.ok) return;
    const users = await r.json();
    fitStore.set({ users });
  } catch (e) {
    console.warn('loadUsers failed:', e);
  }
}

// ── Switch to a different user and reload all data ──
async function switchUser(uid) {
  fitStore.set({ currentUid: uid, loading: true, selected: null });
  WORKOUTS.length = 0;
  WEEK.length = 0;
  Object.keys(WORKOUT_DAYS).forEach(k => delete WORKOUT_DAYS[k]);
  await initFitnessData();
}

// ── Initial data load from backend ──
async function initFitnessData() {
  try {
    const [calendar, weekly] = await Promise.all([
      apiFetch('/calendar'),
      apiFetch('/weekly'),
    ]);

    // Build calendar mapping
    const calDays = calendar.days || {};
    WORKOUT_DAYS = {};
    Object.keys(calDays).forEach(ds => {
      const day = parseInt(ds.split('-')[2], 10);
      WORKOUT_DAYS[day] = ds;
    });

    // Build week strip
    const { week, wkDays } = buildWeek(calDays, calendar.year, calendar.month);
    WEEK = week;

    // Load workout data for ALL training dates from the calendar
    const allTrainingDates = Object.keys(calDays).sort();
    const dailyResults = await Promise.all(
      allTrainingDates.map(ds => apiFetch(`/daily?date=${ds}`).catch(() => null))
    );

    WORKOUTS = [];
    dailyResults.forEach((daily, i) => {
      if (!daily || (!daily.date && !daily.duration_min)) return;
      WORKOUTS.push(dailyToWorkout(daily, allTrainingDates[i]));
    });

    // Weekly stats from the API response (mutate, don't reassign)
    WEEKLY_STATS.sessions = weekly.training_frequency || 0;
    WEEKLY_STATS.totalMin = weekly.total_duration || 0;
    WEEKLY_STATS.avgScore = WORKOUTS.length
      ? String(Math.round(WORKOUTS.reduce((s, x) => s + (x.score || 0), 0) / WORKOUTS.length))
      : '--';

    // Insights data
    WEEKLY_INSIGHTS.sessions = weekly.training_frequency || 0;
    WEEKLY_INSIGHTS.totalTime = String(weekly.total_duration || 0);
    WEEKLY_INSIGHTS.avgScore = WEEKLY_STATS.avgScore;
    WEEKLY_INSIGHTS.mainType = 'Strength';
    const dayLabels = weekly.day_labels || [];
    const dayDur = weekly.daily_duration || [];
    const maxDur = Math.max(...dayDur, 1);
    const cnToEn = { '日': 'S', '一': 'M', '二': 'T', '三': 'W', '四': 'T', '五': 'F', '六': 'S' };
    WEEKLY_INSIGHTS.weekLoad = dayLabels.map((label, i) => ({
      label: cnToEn[label.replace('周', '')] || label.replace('周', ''),
      value: dayDur[i] ? Math.round(dayDur[i] / maxDur * 10 * 10) / 10 : 0,
      state: i === dayLabels.length - 1 ? 'today' : 'past',
    }));

    // Monthly insights — compute from all WORKOUTS (w.id is "YYYY-MM-DD")
    const now = new Date();
    const d30ago = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 30);
    const monthWorkouts = WORKOUTS.filter(w => new Date(w.id) >= d30ago);
    MONTHLY_INSIGHTS.sessions = monthWorkouts.length;
    // Estimate total duration: weekly API gives 7-day total; scale by ratio
    const weeklyTotal = weekly.total_duration || 0;
    const estMonthMin = monthWorkouts.length > 0 && WEEKLY_STATS.sessions > 0
      ? Math.round(weeklyTotal * monthWorkouts.length / WEEKLY_STATS.sessions)
      : 0;
    const hrs = Math.floor(estMonthMin / 60);
    const mins = estMonthMin % 60;
    MONTHLY_INSIGHTS.totalTime = hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m`;
    MONTHLY_INSIGHTS.avgScore = monthWorkouts.length
      ? String(Math.round(monthWorkouts.reduce((s, w) => s + (w.score || 0), 0) / monthWorkouts.length))
      : '--';
    MONTHLY_INSIGHTS.perWeek = monthWorkouts.length > 0
      ? (monthWorkouts.length / 4.3).toFixed(1) : '0';
    MONTHLY_INSIGHTS.mainType = 'Strength';

    // Weekly muscle coverage → COVERAGE_7D
    if (weekly.muscle_coverage && weekly.muscle_coverage.length > 0) {
      COVERAGE_7D = weekly.muscle_coverage.map(item => ({
        name: MUSCLE_CN_TO_EN[item.group] || item.group,
        level: pctToLevel(item.pct),
        pct: item.pct,
      }));
      // Build body figures from coverage
      const covFront = {}, covBack = {};
      const frontZones = { 'Chest': 'chest', 'Shoulders': 'shoulders', 'Arms': 'biceps', 'Core': 'core', 'Legs': 'legs' };
      const backZones = { 'Back': 'upperBack', 'Shoulders': 'shoulders', 'Arms': 'triceps', 'Legs': 'legs', 'Glutes': 'lowerBack' };
      COVERAGE_7D.forEach(item => {
        const fz = frontZones[item.name];
        if (fz) covFront[fz] = item.level;
        const bz = backZones[item.name];
        if (bz) covBack[bz] = item.level;
      });
      COVERAGE_7D_FRONT = covFront;
      COVERAGE_7D_BACK = covBack;
    }

    // Use same data for 30D for now (backend doesn't have separate 30-day endpoint)
    COVERAGE_30D = COVERAGE_7D.map(c => ({ ...c }));
    COVERAGE_30D_FRONT = { ...COVERAGE_7D_FRONT };
    COVERAGE_30D_BACK = { ...COVERAGE_7D_BACK };

    // Weekly training load for the month view
    MONTH_LOAD = (weekly.daily_duration || []).map((dur, i) => ({
      label: (weekly.day_labels || [])[i] || `D${i + 1}`,
      value: dur || 0,
      state: i === (weekly.daily_duration || []).length - 1 ? 'today' : 'past',
    }));

    // Select the most recent workout
    const latest = WORKOUTS.length > 0 ? WORKOUTS[WORKOUTS.length - 1].id : null;
    fitStore.set({ selected: latest, loading: false });

  } catch (e) {
    console.error('initFitnessData failed:', e);
    fitStore.set({ loading: false });
  }
}

// Kick off data loading
loadUsers();
initFitnessData();

Object.assign(window, {
  levelMeta, COVERAGE_7D, COVERAGE_7D_FRONT, COVERAGE_7D_BACK,
  COVERAGE_30D, COVERAGE_30D_FRONT, COVERAGE_30D_BACK, MONTH_LOAD, WORKOUT_DAYS,
  WEEK, WORKOUTS, WEEKLY_STATS, WEEKLY_INSIGHTS, MONTHLY_INSIGHTS, getWorkout, getPlan, MOVEMENT_ALTS, PLANS, fitStore, useFit,
  loadDailyWorkout, apiFetch, MUSCLE_CN_TO_EN, toCoverage, toBodyFigures,
  switchUser, loadUsers,
});

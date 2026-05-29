-- ============================================================
-- Exercise library table  (fitness DB)
-- ============================================================
CREATE TABLE IF NOT EXISTS exercises (
    id                   SERIAL PRIMARY KEY,
    exercise_id          VARCHAR(120)  UNIQUE NOT NULL,
    name                 VARCHAR(200)  NOT NULL,          -- English name
    name_cn              VARCHAR(200),                    -- Chinese name
    primary_muscles      JSONB         NOT NULL DEFAULT '[]',
    secondary_muscles    JSONB         NOT NULL DEFAULT '[]',
    movement_pattern     VARCHAR(50),                     -- push/pull/hold/squat/hinge
    equipment            JSONB         NOT NULL DEFAULT '[]',
    difficulty           VARCHAR(20),                     -- beginner/intermediate/advanced
    training_goals       JSONB         NOT NULL DEFAULT '[]',
    exercise_type        VARCHAR(20),                     -- compound/isolation
    recommended_rep_range JSONB        NOT NULL DEFAULT '{}',
    risk_level           VARCHAR(20),                     -- low/medium/high
    common_mistakes      JSONB         NOT NULL DEFAULT '[]',
    safety_tips          JSONB         NOT NULL DEFAULT '[]',
    estimated_mets       FLOAT,
    fatigue_score        JSONB         NOT NULL DEFAULT '{}',
    contraindications    JSONB         NOT NULL DEFAULT '[]',
    source_data          JSONB,                           -- raw basic_info + muscles for traceability
    created_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_exercises_movement  ON exercises (movement_pattern);
CREATE INDEX IF NOT EXISTS idx_exercises_difficulty ON exercises (difficulty);
CREATE INDEX IF NOT EXISTS idx_exercises_type       ON exercises (exercise_type);
CREATE INDEX IF NOT EXISTS idx_exercises_muscles    ON exercises USING gin (primary_muscles);
CREATE INDEX IF NOT EXISTS idx_exercises_goals      ON exercises USING gin (training_goals);
CREATE INDEX IF NOT EXISTS idx_exercises_equipment  ON exercises USING gin (equipment);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;
DROP TRIGGER IF EXISTS trg_exercises_updated_at ON exercises;
CREATE TRIGGER trg_exercises_updated_at
    BEFORE UPDATE ON exercises
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE exercises IS '动作库：包含肌群、难度、训练目标、MET值、风险等结构化数据';

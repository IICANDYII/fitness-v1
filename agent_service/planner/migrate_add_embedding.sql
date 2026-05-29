-- ============================================================
-- 为 exercises 表添加 pgvector embedding 列
-- 依赖: CREATE EXTENSION IF NOT EXISTS vector;
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE exercises
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- HNSW 索引: 近似最近邻, cosine 距离
-- m=16 ef_construction=64 为默认推荐值, 可根据数据量调整
CREATE INDEX IF NOT EXISTS idx_exercises_embedding_hnsw
    ON exercises
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON COLUMN exercises.embedding IS
    'text-embedding-3-small 1536维向量, 由 embed_exercises.py 生成';

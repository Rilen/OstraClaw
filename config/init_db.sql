-- ============================================================
--  OstraClaw — Inicialização do Banco de Dados PostgreSQL
-- ============================================================

-- Tabela de hashes oficiais conhecidos
CREATE TABLE IF NOT EXISTS official_hashes (
    id          SERIAL PRIMARY KEY,
    sha256      VARCHAR(64) UNIQUE NOT NULL,
    filename    VARCHAR(255),
    edition     VARCHAR(100),       -- Ex: "Ano XIV - Nº 1234"
    date_issued DATE,
    registered_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela de logs de auditoria
CREATE TABLE IF NOT EXISTS audit_log (
    id                  SERIAL PRIMARY KEY,
    filename            VARCHAR(255) NOT NULL,
    timestamp           TIMESTAMPTZ DEFAULT NOW(),
    aggregate_score     NUMERIC(5,4),
    preliminary_verdict VARCHAR(20),
    final_verdict       VARCHAR(20) NOT NULL,
    confidence          NUMERIC(5,4),
    main_reason         TEXT,
    skill_results       JSONB,
    duration_seconds    NUMERIC(8,3)
);

CREATE INDEX IF NOT EXISTS idx_audit_verdict ON audit_log(final_verdict);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);

-- Hashes de exemplo (substituir pelos reais)
-- INSERT INTO official_hashes (sha256, filename, edition) VALUES
--   ('abc123...', 'jornal_2024_001.pdf', 'Ano XIV - Nº 001');

-- View de resumo de conformidade
CREATE OR REPLACE VIEW conformidade_summary AS
SELECT
    DATE_TRUNC('day', timestamp) AS dia,
    COUNT(*) AS total_auditados,
    COUNT(*) FILTER (WHERE final_verdict = 'AUTHENTIC') AS autênticos,
    COUNT(*) FILTER (WHERE final_verdict = 'SUSPECT') AS suspeitos,
    COUNT(*) FILTER (WHERE final_verdict = 'FRAUD') AS fraudes,
    ROUND(AVG(aggregate_score)::numeric, 3) AS score_medio
FROM audit_log
GROUP BY 1
ORDER BY 1 DESC;

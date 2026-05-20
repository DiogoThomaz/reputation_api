CREATE TABLE logs_acesso (
    id SERIAL PRIMARY KEY,
    ip INET NOT NULL,
    user_agent TEXT,
    metodo VARCHAR(10) NOT NULL,
    rota TEXT NOT NULL,
    payload JSONB,
    status_http SMALLINT,
    tempo_resposta_ms DOUBLE PRECISION, -- em milissegundos
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
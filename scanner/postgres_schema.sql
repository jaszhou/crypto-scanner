CREATE TABLE IF NOT EXISTS crypto_signals (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    surge FLOAT,
    rsi FLOAT,
    macd FLOAT,
    macd_signal FLOAT,
    golden_cross BOOLEAN,
    signals TEXT,
    close_price FLOAT,
    llm_summary TEXT,
    llm_risk TEXT,
    future_6h FLOAT,
    future_24h FLOAT,
    return_6h FLOAT,
    return_24h FLOAT
);

CREATE INDEX IF NOT EXISTS idx_symbol_time ON crypto_signals(symbol, timestamp);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    side VARCHAR(4),          -- buy or sell
    entry_price FLOAT,
    last_price FLOAT,
    amount FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(10) DEFAULT 'open'
);

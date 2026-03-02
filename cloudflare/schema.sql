-- Lamatita - Cloudflare D1 Schema (SQLite)

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    created_by INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL REFERENCES groups(id),
    user_id INTEGER NOT NULL REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS game_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    player_name TEXT NOT NULL,
    game TEXT NOT NULL DEFAULT 'solitaire',
    time_seconds INTEGER NOT NULL,
    timer_mode TEXT NOT NULL DEFAULT 'CHRONO',
    hint_mode INTEGER NOT NULL DEFAULT 0,
    konami INTEGER NOT NULL DEFAULT 0,
    anonymous INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scores_time ON game_scores(time_seconds ASC);
CREATE INDEX IF NOT EXISTS idx_scores_user ON game_scores(user_id);
CREATE INDEX IF NOT EXISTS idx_scores_anonymous ON game_scores(anonymous);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

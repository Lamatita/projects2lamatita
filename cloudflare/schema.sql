-- ============================================
-- Lamatita - Schéma de base de données
-- (Référence uniquement - les scores sont
--  stockés dans localStorage du navigateur)
-- ============================================

-- Table des joueurs
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Table des scores du Solitaire
CREATE TABLE IF NOT EXISTS game_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    time_seconds INTEGER NOT NULL,
    timer_mode TEXT NOT NULL CHECK (timer_mode IN ('CHRONO', 'FLEMME')),
    hint_mode BOOLEAN NOT NULL DEFAULT 0,
    played_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id)
);

-- Index pour les classements
CREATE INDEX IF NOT EXISTS idx_scores_score ON game_scores(score DESC);
CREATE INDEX IF NOT EXISTS idx_scores_time ON game_scores(time_seconds ASC);
CREATE INDEX IF NOT EXISTS idx_scores_player ON game_scores(player_id);

-- ============================================
-- Format localStorage utilisé (clé: lamatita_scores)
-- ============================================
-- [
--   {
--     "player": "NomDuJoueur",
--     "score": 520,
--     "time": 185,
--     "timerMode": "CHRONO",
--     "hintMode": false,
--     "date": "2026-03-02T14:30:00.000Z"
--   }
-- ]
-- ============================================

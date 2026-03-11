async function ensureTablesExist(db) {
  await db.exec(`
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
  `);
}

function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers }
  });
}

function getSessionCookie(request) {
  const cookie = request.headers.get('Cookie') || '';
  const match = cookie.match(/lamatita_session=([^;]+)/);
  return match ? match[1] : null;
}

function setSessionCookie(sessionId) {
  return `lamatita_session=${sessionId}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${30 * 24 * 3600}`;
}

function clearSessionCookie() {
  return 'lamatita_session=; Path=/; HttpOnly; Max-Age=0';
}

function generateId() {
  return crypto.randomUUID();
}

async function hashPassword(password) {
  const encoder = new TextEncoder();
  const salt = crypto.randomUUID();
  const data = encoder.encode(password + salt);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hash + '.' + salt;
}

async function comparePassword(supplied, stored) {
  const [hash, salt] = stored.split('.');
  const encoder = new TextEncoder();
  const data = encoder.encode(supplied + salt);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const suppliedHash = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return suppliedHash === hash;
}

function generateGroupCode() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let code = '';
  for (let i = 0; i < 6; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

async function getSessionUser(request, db) {
  const sessionId = getSessionCookie(request);
  if (!sessionId) return null;

  const session = await db.prepare(
    "SELECT user_id FROM sessions WHERE id = ? AND expires_at > datetime('now')"
  ).bind(sessionId).first();
  if (!session) return null;

  const user = await db.prepare('SELECT id, username FROM users WHERE id = ?').bind(session.user_id).first();
  return user;
}

function bestPerPlayer(scores) {
  const best = {};
  for (const s of scores) {
    if (!best[s.player_name] || s.time_seconds < best[s.player_name].time_seconds) {
      best[s.player_name] = s;
    }
  }
  const result = Object.values(best);
  result.sort((a, b) => a.time_seconds - b.time_seconds);
  return result;
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const path = url.pathname;
  const method = request.method;
  const db = env.DB;

  if (method === 'OPTIONS') {
    return new Response(null, { status: 204 });
  }

  if (!db) {
    return jsonResponse({ message: 'Base de donnees non configuree. Veuillez lier une base D1 au projet Cloudflare Pages.' }, 503);
  }

  try {
    await ensureTablesExist(db);
    if (path === '/api/auth/register' && method === 'POST') {
      const body = await request.json();
      const { username, password } = body;
      if (!username || !password) return jsonResponse({ message: 'Donnees invalides' }, 400);

      const existing = await db.prepare('SELECT id FROM users WHERE username = ?').bind(username).first();
      if (existing) return jsonResponse({ message: "Ce nom d'utilisateur est deja pris" }, 409);

      const hashed = await hashPassword(password);
      const result = await db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').bind(username, hashed).run();
      const userId = result.meta.last_row_id;

      const sessionId = generateId();
      const expires = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString();
      await db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)').bind(sessionId, userId, expires).run();

      return jsonResponse({ id: userId, username }, 200, { 'Set-Cookie': setSessionCookie(sessionId) });
    }

    if (path === '/api/auth/login' && method === 'POST') {
      const body = await request.json();
      const { username, password } = body;
      if (!username || !password) return jsonResponse({ message: 'Donnees requises' }, 400);

      const user = await db.prepare('SELECT id, username, password FROM users WHERE username = ?').bind(username).first();
      if (!user) return jsonResponse({ message: 'Nom d\'utilisateur ou mot de passe incorrect' }, 401);

      const valid = await comparePassword(password, user.password);
      if (!valid) return jsonResponse({ message: 'Nom d\'utilisateur ou mot de passe incorrect' }, 401);

      const sessionId = generateId();
      const expires = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString();
      await db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)').bind(sessionId, user.id, expires).run();

      return jsonResponse({ id: user.id, username: user.username }, 200, { 'Set-Cookie': setSessionCookie(sessionId) });
    }

    if (path === '/api/auth/logout' && method === 'POST') {
      const sessionId = getSessionCookie(request);
      if (sessionId) {
        await db.prepare('DELETE FROM sessions WHERE id = ?').bind(sessionId).run();
      }
      return jsonResponse({ message: 'Deconnecte' }, 200, { 'Set-Cookie': clearSessionCookie() });
    }

    if (path === '/api/auth/me' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);
      return jsonResponse({ id: user.id, username: user.username });
    }

    if (path === '/api/groups' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const memberships = await db.prepare('SELECT group_id FROM group_members WHERE user_id = ?').bind(user.id).all();
      const groups = [];
      for (const m of memberships.results) {
        const g = await db.prepare('SELECT * FROM groups WHERE id = ?').bind(m.group_id).first();
        if (g) {
          const members = await db.prepare(
            'SELECT u.username FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?'
          ).bind(g.id).all();
          groups.push({ ...g, members: members.results.map(r => ({ username: r.username })) });
        }
      }
      return jsonResponse(groups);
    }

    if (path === '/api/groups' && method === 'POST') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const body = await request.json();
      if (!body.name) return jsonResponse({ message: 'Nom requis' }, 400);

      let code;
      let existing;
      do {
        code = generateGroupCode();
        existing = await db.prepare('SELECT id FROM groups WHERE code = ?').bind(code).first();
      } while (existing);

      const result = await db.prepare('INSERT INTO groups (name, code, created_by) VALUES (?, ?, ?)').bind(body.name, code, user.id).run();
      const groupId = result.meta.last_row_id;
      await db.prepare('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)').bind(groupId, user.id).run();

      return jsonResponse({ id: groupId, name: body.name, code });
    }

    if (path === '/api/groups/join' && method === 'POST') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const body = await request.json();
      if (!body.code) return jsonResponse({ message: 'Code requis' }, 400);

      const group = await db.prepare('SELECT * FROM groups WHERE code = ?').bind(body.code.toUpperCase()).first();
      if (!group) return jsonResponse({ message: 'Groupe non trouve' }, 404);

      const already = await db.prepare('SELECT id FROM group_members WHERE group_id = ? AND user_id = ?').bind(group.id, user.id).first();
      if (already) return jsonResponse({ message: 'Vous etes deja membre' }, 409);

      await db.prepare('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)').bind(group.id, user.id).run();
      return jsonResponse({ id: group.id, name: group.name, code: group.code });
    }

    if (path === '/api/scores' && method === 'POST') {
      const body = await request.json();
      const { timeSeconds, timerMode, hintMode, konami } = body;
      if (typeof timeSeconds !== 'number' || !timerMode) return jsonResponse({ message: 'Donnees invalides' }, 400);

      const user = await getSessionUser(request, db);
      let userId = null;
      let playerName = '';
      let anonymous = 0;

      if (user) {
        userId = user.id;
        playerName = user.username;
      } else {
        anonymous = 1;
        const countResult = await db.prepare('SELECT COUNT(*) as cnt FROM game_scores WHERE anonymous = 1').first();
        const anonCount = countResult ? countResult.cnt : 0;
        playerName = 'Petit Random Malicieux ' + anonCount;
      }

      await db.prepare(
        'INSERT INTO game_scores (user_id, player_name, game, time_seconds, timer_mode, hint_mode, konami, anonymous) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
      ).bind(userId, playerName, 'solitaire', timeSeconds, timerMode, hintMode ? 1 : 0, konami ? 1 : 0, anonymous).run();

      return jsonResponse({ ok: true });
    }

    if (path === '/api/scores/general' && method === 'GET') {
      const allScores = await db.prepare('SELECT * FROM game_scores ORDER BY time_seconds ASC').all();

      const allGroups = await db.prepare('SELECT * FROM groups').all();
      const groupsWithMembers = [];
      for (const g of allGroups.results) {
        const members = await db.prepare(
          'SELECT u.username FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?'
        ).bind(g.id).all();
        groupsWithMembers.push({ ...g, members: members.results.map(r => r.username) });
      }

      const anonScores = allScores.results.filter(s => s.anonymous);
      const anonBest = bestPerPlayer(anonScores);

      const addedPlayers = {};
      for (const group of groupsWithMembers) {
        const memberScores = allScores.results.filter(s => !s.anonymous && group.members.includes(s.player_name));
        if (memberScores.length === 0) continue;
        const best = bestPerPlayer(memberScores);
        if (best.length > 0) {
          const leader = best[0];
          if (!addedPlayers[leader.player_name] || leader.time_seconds < addedPlayers[leader.player_name].time) {
            addedPlayers[leader.player_name] = {
              player: leader.player_name,
              time: leader.time_seconds,
              timerMode: leader.timer_mode,
              hintMode: !!leader.hint_mode,
              konami: !!leader.konami,
              anonymous: false,
              date: leader.created_at,
              groupName: group.name
            };
          }
        }
      }

      const anonFormatted = anonBest.map(s => ({
        player: s.player_name,
        time: s.time_seconds,
        timerMode: s.timer_mode,
        hintMode: !!s.hint_mode,
        konami: !!s.konami,
        anonymous: true,
        date: s.created_at
      }));

      const combined = [...anonFormatted, ...Object.values(addedPlayers)];
      combined.sort((a, b) => a.time - b.time);

      return jsonResponse(combined);
    }

    if (path === '/api/scores/personal' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const scores = await db.prepare('SELECT * FROM game_scores WHERE user_id = ? ORDER BY time_seconds ASC').bind(user.id).all();
      const formatted = scores.results.map(s => ({
        player: s.player_name,
        time: s.time_seconds,
        timerMode: s.timer_mode,
        hintMode: !!s.hint_mode,
        konami: !!s.konami,
        anonymous: !!s.anonymous,
        date: s.created_at
      }));
      return jsonResponse(formatted);
    }

    const groupScoreMatch = path.match(/^\/api\/scores\/group\/(\d+)$/);
    if (groupScoreMatch && method === 'GET') {
      const groupId = parseInt(groupScoreMatch[1]);
      const members = await db.prepare('SELECT user_id FROM group_members WHERE group_id = ?').bind(groupId).all();
      if (members.results.length === 0) return jsonResponse([]);

      const userIds = members.results.map(m => m.user_id);
      const allScores = [];
      for (const uid of userIds) {
        const scores = await db.prepare('SELECT * FROM game_scores WHERE user_id = ?').bind(uid).all();
        allScores.push(...scores.results);
      }

      const best = bestPerPlayer(allScores);
      const formatted = best.map(s => ({
        player: s.player_name,
        time: s.time_seconds,
        timerMode: s.timer_mode,
        hintMode: !!s.hint_mode,
        konami: !!s.konami,
        anonymous: !!s.anonymous,
        date: s.created_at
      }));
      return jsonResponse(formatted);
    }

    const membersMatch = path.match(/^\/api\/groups\/(\d+)\/members$/);
    if (membersMatch && method === 'GET') {
      const groupId = parseInt(membersMatch[1]);
      const members = await db.prepare(
        'SELECT u.username FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?'
      ).bind(groupId).all();
      return jsonResponse(members.results);
    }

    return jsonResponse({ message: 'Not found' }, 404);
  } catch (err) {
    return jsonResponse({ message: 'Erreur serveur: ' + err.message }, 500);
  }
}

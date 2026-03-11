async function ensureTablesExist(db) {
  const usersTable = await db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").first();
  if (usersTable && usersTable.sql.includes('SERIAL')) {
    await db.batch([
      db.prepare("CREATE TABLE users_new (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL)"),
      db.prepare("INSERT INTO users_new (username, password) SELECT username, password FROM users"),
      db.prepare("DROP TABLE users"),
      db.prepare("ALTER TABLE users_new RENAME TO users"),
    ]);
  }

  const groupsTable = await db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name='groups'").first();
  if (groupsTable && groupsTable.sql.includes('SERIAL')) {
    await db.batch([
      db.prepare("CREATE TABLE groups_new (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, created_by INTEGER NOT NULL)"),
      db.prepare("INSERT INTO groups_new (name, code, created_by) SELECT name, code, created_by FROM groups"),
      db.prepare("DROP TABLE groups"),
      db.prepare("ALTER TABLE groups_new RENAME TO groups"),
    ]);
  }

  const gmTable = await db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name='group_members'").first();
  if (gmTable && gmTable.sql.includes('SERIAL')) {
    await db.batch([
      db.prepare("CREATE TABLE group_members_new (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, user_id INTEGER NOT NULL)"),
      db.prepare("INSERT INTO group_members_new (group_id, user_id) SELECT group_id, user_id FROM group_members"),
      db.prepare("DROP TABLE group_members"),
      db.prepare("ALTER TABLE group_members_new RENAME TO group_members"),
    ]);
  }

  const scoresTable = await db.prepare("SELECT sql FROM sqlite_master WHERE type='table' AND name='game_scores'").first();
  if (scoresTable && scoresTable.sql.includes('SERIAL')) {
    await db.batch([
      db.prepare("CREATE TABLE game_scores_new (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, player_name TEXT NOT NULL, game TEXT NOT NULL DEFAULT 'solitaire', time_seconds INTEGER NOT NULL DEFAULT 0, timer_mode TEXT NOT NULL DEFAULT 'CHRONO', hint_mode INTEGER NOT NULL DEFAULT 0, konami INTEGER NOT NULL DEFAULT 0, anonymous INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, difficulty TEXT NOT NULL DEFAULT '', rounds INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')))"),
      db.prepare("INSERT INTO game_scores_new (user_id, player_name, game, time_seconds, timer_mode, hint_mode, konami, anonymous, created_at) SELECT user_id, player_name, game, time_seconds, timer_mode, CASE WHEN hint_mode THEN 1 ELSE 0 END, CASE WHEN konami THEN 1 ELSE 0 END, CASE WHEN anonymous THEN 1 ELSE 0 END, created_at FROM game_scores"),
      db.prepare("DROP TABLE game_scores"),
      db.prepare("ALTER TABLE game_scores_new RENAME TO game_scores"),
    ]);
  }

  if (scoresTable && !scoresTable.sql.includes('SERIAL') && !scoresTable.sql.includes('score ')) {
    try {
      await db.prepare("ALTER TABLE game_scores ADD COLUMN score INTEGER NOT NULL DEFAULT 0").run();
    } catch(e) {}
    try {
      await db.prepare("ALTER TABLE game_scores ADD COLUMN difficulty TEXT NOT NULL DEFAULT ''").run();
    } catch(e) {}
    try {
      await db.prepare("ALTER TABLE game_scores ADD COLUMN rounds INTEGER NOT NULL DEFAULT 0").run();
    } catch(e) {}
  }

  await db.batch([
    db.prepare("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL)"),
    db.prepare("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), expires_at TEXT NOT NULL)"),
    db.prepare("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, created_by INTEGER NOT NULL)"),
    db.prepare("CREATE TABLE IF NOT EXISTS group_members (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, user_id INTEGER NOT NULL)"),
    db.prepare("CREATE TABLE IF NOT EXISTS game_scores (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, player_name TEXT NOT NULL, game TEXT NOT NULL DEFAULT 'solitaire', time_seconds INTEGER NOT NULL DEFAULT 0, timer_mode TEXT NOT NULL DEFAULT 'CHRONO', hint_mode INTEGER NOT NULL DEFAULT 0, konami INTEGER NOT NULL DEFAULT 0, anonymous INTEGER NOT NULL DEFAULT 0, score INTEGER NOT NULL DEFAULT 0, difficulty TEXT NOT NULL DEFAULT '', rounds INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')))"),
    db.prepare("CREATE TABLE IF NOT EXISTS morpion_rooms (code TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT '{}', player_x TEXT, player_o TEXT, updated_at TEXT NOT NULL DEFAULT (datetime('now')), created_at TEXT NOT NULL DEFAULT (datetime('now')))"),
    db.prepare("CREATE TABLE IF NOT EXISTS user_presence (user_id INTEGER PRIMARY KEY, last_seen TEXT NOT NULL DEFAULT (datetime('now')))"),
    db.prepare("CREATE TABLE IF NOT EXISTS morpion_invites (id INTEGER PRIMARY KEY AUTOINCREMENT, from_user_id INTEGER NOT NULL, from_username TEXT NOT NULL, to_user_id INTEGER NOT NULL, to_username TEXT NOT NULL, room_code TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT (datetime('now')))"),
  ]);

  try {
    await db.prepare("DELETE FROM morpion_rooms WHERE created_at < datetime('now', '-24 hours')").run();
    await db.prepare("DELETE FROM morpion_invites WHERE created_at < datetime('now', '-1 hour')").run();
    await db.prepare("DELETE FROM user_presence WHERE last_seen < datetime('now', '-5 minutes')").run();
  } catch(e) {}
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

function bestPerPlayer(scores, game) {
  const best = {};
  for (const s of scores) {
    const key = s.player_name;
    if (!best[key]) {
      best[key] = s;
    } else if (game === 'solitaire') {
      if (s.time_seconds < best[key].time_seconds) best[key] = s;
    } else {
      if ((s.score || 0) > (best[key].score || 0)) best[key] = s;
    }
  }
  const result = Object.values(best);
  if (game === 'solitaire') {
    result.sort((a, b) => a.time_seconds - b.time_seconds);
  } else {
    result.sort((a, b) => (b.score || 0) - (a.score || 0));
  }
  return result;
}

function formatScore(s) {
  return {
    player: s.player_name,
    time: s.time_seconds,
    timerMode: s.timer_mode,
    hintMode: !!s.hint_mode,
    konami: !!s.konami,
    anonymous: !!s.anonymous,
    date: s.created_at,
    game: s.game || 'solitaire',
    score: s.score || 0,
    difficulty: s.difficulty || '',
    rounds: s.rounds || 0
  };
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

      const hashed = await hashPassword(password);
      const sessionId = generateId();
      const expires = new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString();

      const existing = await db.prepare('SELECT id FROM users WHERE username = ?').bind(username).first();
      if (existing) {
        await db.batch([
          db.prepare('UPDATE users SET password = ? WHERE id = ?').bind(hashed, existing.id),
          db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)').bind(sessionId, existing.id, expires),
        ]);
        return jsonResponse({ id: existing.id, username }, 200, { 'Set-Cookie': setSessionCookie(sessionId) });
      }

      const results = await db.batch([
        db.prepare('INSERT INTO users (username, password) VALUES (?, ?)').bind(username, hashed),
        db.prepare('SELECT id FROM users WHERE username = ?').bind(username),
        db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, (SELECT id FROM users WHERE username = ?), ?)').bind(sessionId, username, expires),
      ]);

      const userId = results[1].results.length > 0 ? results[1].results[0].id : 0;
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
      await db.batch([
        db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)').bind(sessionId, user.id, expires),
      ]);

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

      const groupBatch = await db.batch([
        db.prepare('INSERT INTO groups (name, code, created_by) VALUES (?, ?, ?)').bind(body.name, code, user.id),
        db.prepare('SELECT last_insert_rowid() as id'),
      ]);
      const groupId = groupBatch[1].results[0].id;
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
      const game = body.game || 'solitaire';
      const timeSeconds = body.timeSeconds || 0;
      const timerMode = body.timerMode || '';
      const hintMode = body.hintMode || false;
      const konami = body.konami || false;
      const score = body.score || 0;
      const difficulty = body.difficulty || '';
      const rounds = body.rounds || 0;

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
        'INSERT INTO game_scores (user_id, player_name, game, time_seconds, timer_mode, hint_mode, konami, anonymous, score, difficulty, rounds) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
      ).bind(userId, playerName, game, timeSeconds, timerMode, hintMode ? 1 : 0, konami ? 1 : 0, anonymous, score, difficulty, rounds).run();

      return jsonResponse({ ok: true });
    }

    if (path === '/api/scores/general' && method === 'GET') {
      const gameFilter = url.searchParams.get('game') || 'solitaire';
      const allScores = await db.prepare('SELECT * FROM game_scores WHERE game = ?').bind(gameFilter).all();

      const allGroups = await db.prepare('SELECT * FROM groups').all();
      const groupsWithMembers = [];
      for (const g of allGroups.results) {
        const members = await db.prepare(
          'SELECT u.username FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?'
        ).bind(g.id).all();
        groupsWithMembers.push({ ...g, members: members.results.map(r => r.username) });
      }

      const anonScores = allScores.results.filter(s => s.anonymous);
      const anonBest = bestPerPlayer(anonScores, gameFilter);

      const addedPlayers = {};
      for (const group of groupsWithMembers) {
        const memberScores = allScores.results.filter(s => !s.anonymous && group.members.includes(s.player_name));
        if (memberScores.length === 0) continue;
        const best = bestPerPlayer(memberScores, gameFilter);
        if (best.length > 0) {
          const leader = best[0];
          const formatted = formatScore(leader);
          formatted.groupName = group.name;
          formatted.anonymous = false;
          if (!addedPlayers[leader.player_name]) {
            addedPlayers[leader.player_name] = formatted;
          } else if (gameFilter === 'solitaire') {
            if (leader.time_seconds < addedPlayers[leader.player_name].time) addedPlayers[leader.player_name] = formatted;
          } else {
            if ((leader.score || 0) > (addedPlayers[leader.player_name].score || 0)) addedPlayers[leader.player_name] = formatted;
          }
        }
      }

      const anonFormatted = anonBest.map(s => formatScore(s));

      const combined = [...anonFormatted, ...Object.values(addedPlayers)];
      if (gameFilter === 'solitaire') {
        combined.sort((a, b) => a.time - b.time);
      } else {
        combined.sort((a, b) => (b.score || 0) - (a.score || 0));
      }

      return jsonResponse(combined);
    }

    if (path === '/api/scores/personal' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);
      const gameFilter = url.searchParams.get('game') || 'solitaire';

      const orderBy = gameFilter === 'solitaire' ? 'time_seconds ASC' : 'score DESC';
      const scores = await db.prepare('SELECT * FROM game_scores WHERE user_id = ? AND game = ? ORDER BY ' + orderBy).bind(user.id, gameFilter).all();
      const formatted = scores.results.map(s => formatScore(s));
      return jsonResponse(formatted);
    }

    const groupScoreMatch = path.match(/^\/api\/scores\/group\/(\d+)$/);
    if (groupScoreMatch && method === 'GET') {
      const groupId = parseInt(groupScoreMatch[1]);
      const gameFilter = url.searchParams.get('game') || 'solitaire';
      const members = await db.prepare('SELECT user_id FROM group_members WHERE group_id = ?').bind(groupId).all();
      if (members.results.length === 0) return jsonResponse([]);

      const userIds = members.results.map(m => m.user_id);
      const allScores = [];
      for (const uid of userIds) {
        const scores = await db.prepare('SELECT * FROM game_scores WHERE user_id = ? AND game = ?').bind(uid, gameFilter).all();
        allScores.push(...scores.results);
      }

      const best = bestPerPlayer(allScores, gameFilter);
      const formatted = best.map(s => formatScore(s));
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

    if (path === '/api/presence/ping' && method === 'POST') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);
      const existing = await db.prepare('SELECT user_id FROM user_presence WHERE user_id = ?').bind(user.id).first();
      if (existing) {
        await db.prepare("UPDATE user_presence SET last_seen = datetime('now') WHERE user_id = ?").bind(user.id).run();
      } else {
        await db.prepare("INSERT INTO user_presence (user_id, last_seen) VALUES (?, datetime('now'))").bind(user.id).run();
      }
      return jsonResponse({ ok: true });
    }

    if (path === '/api/presence/online' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const memberships = await db.prepare('SELECT group_id FROM group_members WHERE user_id = ?').bind(user.id).all();
      if (memberships.results.length === 0) return jsonResponse([]);

      const groupMateIds = new Set();
      for (const m of memberships.results) {
        const gm = await db.prepare('SELECT user_id FROM group_members WHERE group_id = ?').bind(m.group_id).all();
        gm.results.forEach(r => { if (r.user_id !== user.id) groupMateIds.add(r.user_id); });
      }
      if (groupMateIds.size === 0) return jsonResponse([]);

      const onlineUsers = [];
      for (const uid of groupMateIds) {
        const p = await db.prepare("SELECT user_id FROM user_presence WHERE user_id = ? AND last_seen > datetime('now', '-2 minutes')").bind(uid).first();
        if (p) onlineUsers.push(uid);
      }
      return jsonResponse(onlineUsers);
    }

    if (path === '/api/groups/members' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const memberships = await db.prepare('SELECT group_id FROM group_members WHERE user_id = ?').bind(user.id).all();
      const memberMap = {};
      const groupNames = {};
      for (const m of memberships.results) {
        const g = await db.prepare('SELECT name FROM groups WHERE id = ?').bind(m.group_id).first();
        if (g) groupNames[m.group_id] = g.name;
        const gm = await db.prepare('SELECT gm.user_id, u.username FROM group_members gm JOIN users u ON gm.user_id = u.id WHERE gm.group_id = ?').bind(m.group_id).all();
        for (const r of gm.results) {
          if (r.user_id !== user.id) {
            if (!memberMap[r.user_id]) memberMap[r.user_id] = { id: r.user_id, username: r.username, groups: [] };
            memberMap[r.user_id].groups.push({ id: m.group_id, name: groupNames[m.group_id] || '' });
          }
        }
      }
      return jsonResponse(Object.values(memberMap));
    }

    if (path === '/api/morpion/invite' && method === 'POST') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);
      const body = await request.json();
      const toUserId = body.toUserId;
      const roomCode = body.roomCode;
      if (!toUserId || !roomCode) return jsonResponse({ message: 'Donnees manquantes' }, 400);

      const toUser = await db.prepare('SELECT id, username FROM users WHERE id = ?').bind(toUserId).first();
      if (!toUser) return jsonResponse({ message: 'Utilisateur introuvable' }, 404);

      await db.prepare("DELETE FROM morpion_invites WHERE from_user_id = ? AND to_user_id = ? AND status = 'pending'").bind(user.id, toUserId).run();

      await db.prepare(
        'INSERT INTO morpion_invites (from_user_id, from_username, to_user_id, to_username, room_code) VALUES (?, ?, ?, ?, ?)'
      ).bind(user.id, user.username, toUserId, toUser.username, roomCode).run();

      return jsonResponse({ ok: true });
    }

    if (path === '/api/morpion/invitations' && method === 'GET') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);

      const invites = await db.prepare(
        "SELECT * FROM morpion_invites WHERE to_user_id = ? AND status = 'pending' AND created_at > datetime('now', '-5 minutes') ORDER BY created_at DESC"
      ).bind(user.id).all();

      return jsonResponse(invites.results.map(i => ({
        id: i.id,
        fromUsername: i.from_username,
        fromUserId: i.from_user_id,
        roomCode: i.room_code,
        createdAt: i.created_at
      })));
    }

    const inviteActionMatch = path.match(/^\/api\/morpion\/invite\/(\d+)\/(accept|decline)$/);
    if (inviteActionMatch && method === 'POST') {
      const user = await getSessionUser(request, db);
      if (!user) return jsonResponse({ message: 'Non connecte' }, 401);
      const inviteId = parseInt(inviteActionMatch[1]);
      const action = inviteActionMatch[2];

      const invite = await db.prepare("SELECT * FROM morpion_invites WHERE id = ? AND to_user_id = ? AND status = 'pending'").bind(inviteId, user.id).first();
      if (!invite) return jsonResponse({ message: 'Invitation introuvable ou déjà traitée' }, 404);

      const newStatus = action === 'accept' ? 'accepted' : 'declined';
      await db.prepare('UPDATE morpion_invites SET status = ? WHERE id = ?').bind(newStatus, inviteId).run();

      if (action === 'accept') {
        return jsonResponse({ ok: true, roomCode: invite.room_code, fromUsername: invite.from_username });
      }
      return jsonResponse({ ok: true });
    }

    if (path === '/api/morpion/create' && method === 'POST') {
      const body = await request.json();
      const code = body.code;
      if (!code || code.length < 6) return jsonResponse({ message: 'Code invalide' }, 400);

      const existing = await db.prepare('SELECT code FROM morpion_rooms WHERE code = ?').bind(code).first();
      if (existing) {
        await db.prepare("UPDATE morpion_rooms SET state = '{}', player_o = NULL, updated_at = datetime('now') WHERE code = ?").bind(code).run();
      } else {
        await db.prepare("INSERT INTO morpion_rooms (code, state, player_x) VALUES (?, '{}', ?)").bind(code, body.playerName || 'Joueur X').run();
      }
      return jsonResponse({ ok: true, code });
    }

    if (path === '/api/morpion/join' && method === 'POST') {
      const body = await request.json();
      const code = (body.code || '').toUpperCase().trim();
      if (!code) return jsonResponse({ message: 'Code requis' }, 400);

      const room = await db.prepare('SELECT * FROM morpion_rooms WHERE code = ?').bind(code).first();
      if (!room) return jsonResponse({ message: 'Partie introuvable' }, 404);

      await db.prepare("UPDATE morpion_rooms SET player_o = ?, updated_at = datetime('now') WHERE code = ?").bind(body.playerName || 'Joueur O', code).run();
      const state = room.state ? JSON.parse(room.state) : {};
      return jsonResponse({ ok: true, code, state, playerX: room.player_x, playerO: body.playerName || 'Joueur O' });
    }

    const morpionStateMatch = path.match(/^\/api\/morpion\/state\/([A-Za-z0-9]+)$/);
    if (morpionStateMatch && method === 'GET') {
      const code = morpionStateMatch[1].toUpperCase();
      const since = url.searchParams.get('since') || '0';
      const room = await db.prepare('SELECT * FROM morpion_rooms WHERE code = ?').bind(code).first();
      if (!room) return jsonResponse({ message: 'Partie introuvable' }, 404);

      const state = room.state ? JSON.parse(room.state) : {};
      if (state.ts && String(state.ts) === since) {
        return jsonResponse({ changed: false });
      }
      return jsonResponse({ changed: true, state, playerX: room.player_x, playerO: room.player_o, updatedAt: room.updated_at });
    }

    if (path === '/api/morpion/move' && method === 'POST') {
      const body = await request.json();
      const code = (body.code || '').toUpperCase().trim();
      if (!code) return jsonResponse({ message: 'Code requis' }, 400);

      const room = await db.prepare('SELECT code FROM morpion_rooms WHERE code = ?').bind(code).first();
      if (!room) return jsonResponse({ message: 'Partie introuvable' }, 404);

      const stateJson = JSON.stringify(body.state || {});
      await db.prepare("UPDATE morpion_rooms SET state = ?, updated_at = datetime('now') WHERE code = ?").bind(stateJson, code).run();
      return jsonResponse({ ok: true });
    }

    return jsonResponse({ message: 'Not found' }, 404);
  } catch (err) {
    return jsonResponse({ message: 'Erreur serveur: ' + err.message }, 500);
  }
}

/**
 * ⚽ 足彩泊松分析 — 预测页
 */
const CONFIG = {
    ODDS_API_KEY: 'efc0bf96ed9d8255c706f2185a15e42e',
    DATA_PATH: 'data',
    CACHE_TTL: 6 * 60 * 60 * 1000,
};

const LEAGUE_META = {
    2021: { code: 'PL', name: '英格兰超级联赛', abbr: '英超' },
    2002: { code: 'BL1', name: '德国超级联赛', abbr: '德甲' },
    2014: { code: 'PD', name: '西班牙超级联赛', abbr: '西甲' },
    2019: { code: 'SA', name: '意大利超级联赛', abbr: '意甲' },
    2015: { code: 'FL1', name: '法国超级联赛', abbr: '法甲' },
    2022: { code: 'CN1', name: '中国超级联赛', abbr: '中超' },
    2023: { code: 'WCQ', name: '世界杯预选赛', abbr: '世预赛' },
    2024: { code: 'WC2014', name: '2014世界杯', abbr: '2014世界杯' },
    2025: { code: 'WC2018', name: '2018世界杯', abbr: '2018世界杯' },
    2026: { code: 'WC2022', name: '2022世界杯', abbr: '2022世界杯' },
};

const LEAGUE_PARAMS = {
    2021: { eloHomeAdv: 80, dixonColesRho: 0.18, poissonWeight: 0.55 },
    2002: { eloHomeAdv: 115, dixonColesRho: 0.14, poissonWeight: 0.60 },
    2014: { eloHomeAdv: 115, dixonColesRho: 0.15, poissonWeight: 0.55 },
    2019: { eloHomeAdv: 60, dixonColesRho: 0.17, poissonWeight: 0.50 },
    2015: { eloHomeAdv: 75, dixonColesRho: 0.14, poissonWeight: 0.55 },
    2022: { eloHomeAdv: 100, dixonColesRho: 0.15, poissonWeight: 0.55 },
    2023: { eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.50 },
    2024: { eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.50 },
    2025: { eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.50 },
    2026: { eloHomeAdv: 0, dixonColesRho: 0.15, poissonWeight: 0.50 },
};

// ====== 状态 ======
const state = {
    leagues: [],
    teams: [],
    teamsById: {},
    teamNames: { cn_to_en: {}, en_to_cn: {} },
    currentLeagueId: null,
    currentMatches: [],
    currentTeamList: [],
    homeTeam: null,
    awayTeam: null,
};

// ====== 缓存 ======
function cacheGet(key) {
    try {
        const raw = localStorage.getItem('fc_' + key);
        if (!raw) return null;
        const item = JSON.parse(raw);
        if (Date.now() - item.ts > CONFIG.CACHE_TTL) return null;
        return item.data;
    } catch { return null; }
}
function cacheSet(key, data) {
    try { localStorage.setItem('fc_' + key, JSON.stringify({ ts: Date.now(), data })); } catch {}
}

// ====== 数据加载 ======
async function fetchJSON(url) {
    const cached = cacheGet(url);
    if (cached) return cached;
    const resp = await fetch(url + '?_=' + Date.now());
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (JSON.stringify(data).length > 1024) cacheSet(url, data);
    return data;
}

async function loadLeagues() {
    const data = await fetchJSON(`${CONFIG.DATA_PATH}/leagues.json`);
    state.leagues = data;
    for (const l of data) {
        const m = LEAGUE_META[l.id];
        if (m) { l.abbr = m.abbr; l.code = m.code; }
    }
    return data;
}

async function loadTeams() {
    const data = await fetchJSON(`${CONFIG.DATA_PATH}/teams.json`);
    state.teams = data;
    state.teamsById = {};
    for (const t of data) state.teamsById[t.id] = t;
    return data;
}

async function loadTeamNames() {
    try { state.teamNames = await fetchJSON(`${CONFIG.DATA_PATH}/team_names.json`); }
    catch { state.teamNames = { cn_to_en: {}, en_to_cn: {} }; }
}

async function loadMatches(leagueId) {
    return fetchJSON(`${CONFIG.DATA_PATH}/matches_${leagueId}.json`);
}

// ====== 工具 ======
function cnName(eng) { return (state.teamNames.en_to_cn || {})[eng] || null; }
function teamDisplay(id) {
    const t = state.teamsById[id];
    if (!t) return `Team ${id}`;
    const c = cnName(t.n);
    return c ? `${c}（${t.n}）` : t.n;
}
function teamShort(id) {
    const t = state.teamsById[id];
    if (!t) return `Team ${id}`;
    return cnName(t.n) || t.n;
}

function searchTeams(query, teamList) {
    if (!query || query.length < 1) return [];
    const q = query.toLowerCase().trim();
    const results = [];
    for (const t of teamList) {
        const en = t.name.toLowerCase();
        const cn = (t.cnName || '').toLowerCase();
        if (en === q || cn === q) { results.unshift(t); continue; }
        if (en.includes(q) || cn.includes(q)) { results.push(t); continue; }
        if (q.length >= 2) {
            if (en.replace(/[^a-z]/g, '').includes(q) || cn.replace(/\s/g, '').includes(q)) results.push(t);
        }
    }
    return results.slice(0, 8);
}

// ====== 联赛选择 ======
function fillLeagueSelect() {
    const sel = document.getElementById('leagueSelect');
    sel.innerHTML = '<option value="">-- 请选择联赛 --</option>';
    for (const l of state.leagues) {
        const opt = document.createElement('option');
        opt.value = l.id;
        opt.textContent = `${l.abbr || ''} - ${l.name}`;
        sel.appendChild(opt);
    }
}

async function onLeagueChange() {
    const leagueId = parseInt(document.getElementById('leagueSelect').value);
    document.getElementById('inputArea').style.display = 'none';
    document.getElementById('result').style.display = 'none';
    state.homeTeam = state.awayTeam = null;
    document.getElementById('predictBtn').disabled = true;

    if (!leagueId) return;

    const league = state.leagues.find(l => l.id === leagueId);
    const info = document.getElementById('leagueInfo');
    info.style.display = 'block';
    info.textContent = `⏳ 加载数据...`;

    try {
        state.currentLeagueId = leagueId;
        state.currentMatches = await loadMatches(leagueId);

        const teamIds = new Set();
        for (const m of state.currentMatches) {
            teamIds.add(m.home_team_id);
            teamIds.add(m.away_team_id);
        }
        state.currentTeamList = [];
        for (const tid of teamIds) {
            const t = state.teamsById[tid];
            if (t) {
                const c = cnName(t.n);
                state.currentTeamList.push({ id: tid, name: t.n, cnName: c || '', display: c ? `${c}（${t.n}）` : t.n });
            }
        }
        state.currentTeamList.sort((a, b) => (a.cnName || a.name).localeCompare(b.cnName || b.name, 'zh'));

        info.textContent = `✅ ${league ? league.name : ''} — ${state.currentTeamList.length} 支球队，${state.currentMatches.length} 场比赛`;
        document.getElementById('inputArea').style.display = 'block';
        document.getElementById('homeInput').value = '';
        document.getElementById('awayInput').value = '';
        document.getElementById('homeSuggestions').classList.remove('show');
        document.getElementById('awaySuggestions').classList.remove('show');
    } catch (e) {
        info.textContent = '❌ 加载失败: ' + e.message;
    }
}

// ====== 球队搜索 ======
function setupTeamInput(inputId, sugId, onSelect) {
    const input = document.getElementById(inputId);
    const sug = document.getElementById(sugId);
    let idx = -1;

    input.addEventListener('input', () => {
        const q = input.value;
        if (q.length < 1) { sug.classList.remove('show'); onSelect(null); return; }
        const results = searchTeams(q, state.currentTeamList);
        sug.innerHTML = '';
        if (!results.length) { sug.classList.remove('show'); return; }
        idx = -1;
        for (const r of results) {
            const d = document.createElement('div');
            d.className = 'suggestion-item';
            d.innerHTML = `<span class="cn-name">${r.cnName || r.name}</span><span class="en-name">${r.cnName ? r.name : ''}</span>`;
            d.onclick = () => { input.value = r.display || r.name; sug.classList.remove('show'); onSelect(r); };
            sug.appendChild(d);
        }
        sug.classList.add('show');
    });

    input.addEventListener('keydown', (e) => {
        const items = sug.querySelectorAll('.suggestion-item');
        if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(idx + 1, items.length - 1); items.forEach((el, i) => el.classList.toggle('active', i === idx)); }
        if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(idx - 1, 0); items.forEach((el, i) => el.classList.toggle('active', i === idx)); }
        if (e.key === 'Enter' && idx >= 0 && items[idx]) { e.preventDefault(); items[idx].click(); }
    });
    input.addEventListener('blur', () => setTimeout(() => sug.classList.remove('show'), 200));
    input.addEventListener('focus', () => { if (sug.querySelector('.suggestion-item')) sug.classList.add('show'); });
}

function initInputs() {
    setupTeamInput('homeInput', 'homeSuggestions', (t) => { state.homeTeam = t; updateBtn(); });
    setupTeamInput('awayInput', 'awaySuggestions', (t) => { state.awayTeam = t; updateBtn(); });
}
function updateBtn() {
    document.getElementById('predictBtn').disabled = !(state.homeTeam && state.awayTeam && state.homeTeam.id !== state.awayTeam.id);
}

// ====== 预测 ======
async function doPredict() {
    if (!state.homeTeam || !state.awayTeam) return;
    if (state.homeTeam.id === state.awayTeam.id) { showError('主队和客队不能相同'); return; }

    const odds = {
        home: parseFloat(document.getElementById('oddsHome').value),
        draw: parseFloat(document.getElementById('oddsDraw').value),
        away: parseFloat(document.getElementById('oddsAway').value),
    };
    if (!odds.home || !odds.draw || !odds.away || odds.home < 1 || odds.draw < 1 || odds.away < 1) {
        showError('请输入有效赔率（≥1.01）'); return;
    }

    showLoading('🔮 计算预测中...');
    await new Promise(r => setTimeout(r, 50));

    try {
        const avg = PoissonPredictor.calcLeagueAvgGoals(state.currentMatches);
        const ht = state.teamsById[state.homeTeam.id];
        const at = state.teamsById[state.awayTeam.id];

        const ps = new PredictionService({
            leagueParams: LEAGUE_PARAMS,
            defaultEloHomeAdv: 100, defaultRho: 0.15, defaultPoissonWeight: 0.55,
        });
        const r = ps.predict({
            homeTeamId: state.homeTeam.id, awayTeamId: state.awayTeam.id,
            homeElo: ht ? ht.elo : 1500, awayElo: at ? at.elo : 1500,
            leagueId: state.currentLeagueId, matches: state.currentMatches, leagueAvg: avg,
        });

        const homeRecent = getRecent(state.currentMatches, state.homeTeam.id, 5);
        const awayRecent = getRecent(state.currentMatches, state.awayTeam.id, 5);
        const h2h = getH2H(state.currentMatches, state.homeTeam.id, state.awayTeam.id, 5);

        hideLoading();
        renderResult({
            ...r,
            hName: teamDisplay(state.homeTeam.id), aName: teamDisplay(state.awayTeam.id),
            hShort: teamShort(state.homeTeam.id), aShort: teamShort(state.awayTeam.id),
            homeRecent, awayRecent, h2h, odds,
            avg: Math.round(avg * 100) / 100,
        });
    } catch (e) { hideLoading(); showError('预测失败: ' + e.message); console.error(e); }
}

function getRecent(matches, teamId, limit) {
    const tm = matches.filter(m => (m.home_team_id === teamId || m.away_team_id === teamId) && m.status === 'FINISHED' && m.score_home != null);
    tm.sort((a, b) => a.utc_date < b.utc_date ? 1 : -1);
    return tm.slice(0, limit).map(m => {
        const h = m.home_team_id === teamId;
        const gf = h ? m.score_home : m.score_away;
        const ga = h ? m.score_away : m.score_home;
        return { date: m.utc_date ? m.utc_date.slice(5, 10) : '', opponent: h ? teamShort(m.away_team_id) : teamShort(m.home_team_id), isHome: h, gf, ga, score: `${gf}-${ga}`, result: gf > ga ? 'W' : gf < ga ? 'L' : 'D' };
    });
}
function getH2H(matches, a, b, limit) {
    const h2h = matches.filter(m => ((m.home_team_id === a && m.away_team_id === b) || (m.home_team_id === b && m.away_team_id === a)) && m.status === 'FINISHED' && m.score_home != null);
    h2h.sort((x, y) => x.utc_date < y.utc_date ? 1 : -1);
    return h2h.slice(0, limit).map(m => ({ homeName: teamShort(m.home_team_id), awayName: teamShort(m.away_team_id), homeScore: m.score_home, awayScore: m.score_away }));
}

// ====== 结果渲染 ======
function renderResult(r) {
    const c = document.getElementById('result');
    c.style.display = 'block';

    const h = r.homeWinProb, d = r.drawProb, a = r.awayWinProb, total = h + d + a;
    const hp = h / total, dp = d / total, ap = a / total;

    let html = `
    <div class="score-card">
        <div class="teams">${r.hName} vs ${r.aName}</div>
        <div class="score">${r.predictedHomeScore} : ${r.predictedAwayScore}</div>
        <div class="outcome">🎯 ${r.predictedOutcome === 'HOME' ? '主胜 ✅' : r.predictedOutcome === 'AWAY' ? '客胜 ✅' : '平局 🤝'}</div>
        <div class="confidence-text">置信度: <strong>${r.confidence}%</strong></div>
    </div>

    <div class="card">
        <div class="card-title" style="margin-bottom:4px">🎲 胜平负概率</div>
        <div class="prob-bar-3">
            <div class="seg" style="flex:${hp.toFixed(3)};background:#2ecc71;border-radius:18px 0 0 18px">${hp > 0.08 ? '🏠 ' + (h * 100).toFixed(0) + '%' : ''}</div>
            <div class="seg" style="flex:${dp.toFixed(3)};background:#95a5a6">${dp > 0.08 ? '🤝 ' + (d * 100).toFixed(0) + '%' : ''}</div>
            <div class="seg" style="flex:${ap.toFixed(3)};background:#e74c3c;border-radius:0 18px 18px 0">${ap > 0.08 ? '✈️ ' + (a * 100).toFixed(0) + '%' : ''}</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center;margin-top:8px">
            <div><strong style="color:#2ecc71;font-size:1.1rem">${(h * 100).toFixed(1)}%</strong><br><small>主胜</small></div>
            <div><strong style="color:#95a5a6;font-size:1.1rem">${(d * 100).toFixed(1)}%</strong><br><small>平局</small></div>
            <div><strong style="color:#e74c3c;font-size:1.1rem">${(a * 100).toFixed(1)}%</strong><br><small>客胜</small></div>
        </div>
        <div style="margin-top:8px;font-size:0.85rem;color:var(--text-secondary)">预期进球 (xG): ${r.hShort} ${r.poissonResult.homeXg} — ${r.aShort} ${r.poissonResult.awayXg}</div>
        <div style="font-size:0.85rem;color:var(--text-secondary)">联赛场均总进球: ${r.avg}</div>
    </div>`;

    // 比分概率
    const scores = r.poissonResult.scoreProbabilities;
    if (scores && scores.length > 0) {
        const maxP = scores[0].probability;
        html += `<div class="card"><div class="card-title">📊 比分概率分布</div><div class="score-grid-4">`;
        for (let i = 0; i < Math.min(scores.length, 8); i++) {
            const sp = scores[i];
            html += `<div class="score-grid-item"><div class="score-num">${sp.home}:${sp.away}</div>
                <div class="score-pct">${(sp.probability * 100).toFixed(1)}%</div>
                <div class="prob-bar-tiny"><div class="prob-fill" style="width:${maxP > 0 ? (sp.probability / maxP * 100) : 0}%"></div></div></div>`;
        }
        html += `</div></div>`;
    }

    // 近期成绩
    html += `<div class="card"><div class="card-title">📋 近期成绩（模型计算依据）</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
        <div><strong>🏠 ${r.hShort} 近期 5 场</strong>`;
    for (const m of r.homeRecent || []) {
        html += `<div class="form-item">${m.result === 'W' ? '✅' : m.result === 'L' ? '❌' : '➖'} <strong>${m.score}</strong> vs ${m.opponent}</div>`;
    }
    if (!r.homeRecent || !r.homeRecent.length) html += '<div style="font-size:0.8rem;color:var(--text-secondary);padding:4px 0">暂无数据</div>';
    html += `</div><div><strong>✈️ ${r.aShort} 近期 5 场</strong>`;
    for (const m of r.awayRecent || []) {
        html += `<div class="form-item">${m.result === 'W' ? '✅' : m.result === 'L' ? '❌' : '➖'} <strong>${m.score}</strong> vs ${m.opponent}</div>`;
    }
    if (!r.awayRecent || !r.awayRecent.length) html += '<div style="font-size:0.8rem;color:var(--text-secondary);padding:4px 0">暂无数据</div>';
    html += `</div></div></div>`;

    // 赔率分析
    html += `<div class="card"><div class="card-title">💰 赔率分析</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">`;
    for (const ok of [{ label: '主胜', prob: h, odds: r.odds.home }, { label: '平局', prob: d, odds: r.odds.draw }, { label: '客胜', prob: a, odds: r.odds.away }]) {
        const implied = 1 / ok.odds;
        const diff = ok.prob - implied;
        html += `<div class="odds-metric"><div class="odds-label">${ok.label}</div>
            <div class="odds-model">${(ok.prob * 100).toFixed(0)}%</div>
            <div class="odds-market">市场 ${(implied * 100).toFixed(0)}% <span class="odds-delta ${diff > 0 ? 'pos' : 'neg'}">(${diff > 0 ? '+' : ''}${(diff * 100).toFixed(0)}%)</span></div></div>`;
        const ev = ok.odds * ok.prob - 1;
        if (ev > 0) html += `<div class="value-bet" style="grid-column:1/-1"><strong>${ok.label}</strong> — 期望值 <strong>${(ev * 100).toFixed(1)}%</strong>，赔率 ${ok.odds.toFixed(2)}</div>`;
    }
    html += `</div></div>`;

    // 模型详情（可折叠）
    const lp = r.leagueParams || {};
    html += `<details class="details-expander"><summary>🔬 模型详情（Poisson + Elo）</summary><div class="details-body">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <div><strong>Poisson 模型</strong>
                <div class="metric-row"><span class="label">主胜</span><span class="value">${(r.poissonResult.homeWinProb * 100).toFixed(1)}%</span></div>
                <div class="metric-row"><span class="label">平局</span><span class="value">${(r.poissonResult.drawProb * 100).toFixed(1)}%</span></div>
                <div class="metric-row"><span class="label">客胜</span><span class="value">${(r.poissonResult.awayWinProb * 100).toFixed(1)}%</span></div>
                <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px">xG: 主 ${r.poissonResult.homeXg} / 客 ${r.poissonResult.awayXg}</div>
            </div>
            <div><strong>Elo 模型</strong>
                <div class="metric-row"><span class="label">主胜</span><span class="value">${(r.eloResult.homeWinProb * 100).toFixed(1)}%</span></div>
                <div class="metric-row"><span class="label">平局</span><span class="value">${(r.eloResult.drawProb * 100).toFixed(1)}%</span></div>
                <div class="metric-row"><span class="label">客胜</span><span class="value">${(r.eloResult.awayWinProb * 100).toFixed(1)}%</span></div>
                <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px">${r.hShort}: Elo ${Math.round(state.teamsById[state.homeTeam.id]?.elo || 1500)} | ${r.aShort}: Elo ${Math.round(state.teamsById[state.awayTeam.id]?.elo || 1500)}</div>
            </div>
        </div>
        <div style="margin-top:8px;font-size:0.8rem;color:var(--text-secondary)">融合权重: Poisson ${Math.round((r.modelWeights.poisson || 0.55) * 100)}% + Elo ${Math.round((r.modelWeights.elo || 0.45) * 100)}% ${lp.eloHomeAdv ? '| HFA=' + lp.eloHomeAdv : ''}${lp.dixonColesRho ? ' | ρ=' + lp.dixonColesRho : ''}</div>
    </div></details>`;

    // 历史交锋
    if (r.h2h && r.h2h.length > 0) {
        html += `<div class="card" style="margin-top:12px"><div class="card-title">⚔️ 历史交锋</div>`;
        for (const m of r.h2h) html += `<div class="h2h-row"><span class="h2h-home">${m.homeName}</span><span class="h2h-score">${m.homeScore}-${m.awayScore}</span><span class="h2h-away">${m.awayName}</span></div>`;
        html += `<div style="text-align:right;font-size:0.8rem;color:var(--text-secondary)">${r.h2h.length} 场</div></div>`;
    }

    html += `<div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn btn-secondary" onclick="resetPred()" style="flex:1">← 新预测</button>
    </div>`;

    c.innerHTML = html;
    c.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function resetPred() {
    state.homeTeam = state.awayTeam = null;
    document.getElementById('homeInput').value = '';
    document.getElementById('awayInput').value = '';
    document.getElementById('result').style.display = 'none';
    document.getElementById('result').innerHTML = '';
    document.getElementById('predictBtn').disabled = true;
}

// ====== UI ======
function showLoading(t) { const el = document.getElementById('loading'); if (el) { el.style.display = 'flex'; document.getElementById('loadingText').textContent = t || '计算中...'; } }
function hideLoading() { const el = document.getElementById('loading'); if (el) el.style.display = 'none'; }
function showError(msg) { const c = document.getElementById('result'); c.style.display = 'block'; c.innerHTML = `<div class="error-box">❌ ${msg}</div>`; }

// ====== 启动 ======
async function init() {
    try {
        await Promise.all([loadLeagues(), loadTeams(), loadTeamNames()]);
        fillLeagueSelect();
        initInputs();
    } catch (e) {
        console.error(e);
        document.body.innerHTML = `<div class="error-box" style="margin:2rem;padding:2rem;text-align:center"><h3>❌ 初始化失败</h3><p>${e.message}</p></div>`;
    }
}
document.addEventListener('DOMContentLoaded', init);

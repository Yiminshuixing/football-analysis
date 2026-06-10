/**
 * ⚽ 足彩泊松分析 — 主应用逻辑
 * Streamlit 风格界面
 */

// ==============================
// 配置
// ==============================
const CONFIG = {
    ODDS_API_KEY: 'efc0bf96ed9d8255c706f2185a15e42e',
    DATA_PATH: 'data',
    CACHE_TTL: 6 * 60 * 60 * 1000,
};

const LEAGUE_META = {
    2021: { code: 'PL', name: '英格兰超级联赛', abbr: '英超', sportKey: 'soccer_epl' },
    2002: { code: 'BL1', name: '德国超级联赛', abbr: '德甲', sportKey: 'soccer_germany_bundesliga' },
    2014: { code: 'PD', name: '西班牙超级联赛', abbr: '西甲', sportKey: 'soccer_spain_la_liga' },
    2019: { code: 'SA', name: '意大利超级联赛', abbr: '意甲', sportKey: 'soccer_italy_serie_a' },
    2015: { code: 'FL1', name: '法国超级联赛', abbr: '法甲', sportKey: 'soccer_france_ligue_one' },
    2022: { code: 'CN1', name: '中国超级联赛', abbr: '中超', sportKey: 'soccer_china_superleague' },
    2023: { code: 'WCQ', name: '世界杯预选赛', abbr: '世预赛', sportKey: null },
    2024: { code: 'WC2014', name: '2014世界杯', abbr: '2014世界杯', sportKey: null },
    2025: { code: 'WC2018', name: '2018世界杯', abbr: '2018世界杯', sportKey: null },
    2026: { code: 'WC2022', name: '2022世界杯', abbr: '2022世界杯', sportKey: null },
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

// ==============================
// 状态
// ==============================
const state = {
    leagues: [],
    teams: [],
    teamsById: {},
    teamNames: { cn_to_en: {}, en_to_cn: {} },

    // 当前加载的联赛数据
    currentLeagueId: null,
    currentMatches: [],
    currentTeamList: [], // [{id, name, cnName, display}]

    // 选择的球队
    homeTeam: null,  // { id, name }
    awayTeam: null,

    // 缓存
};

// ==============================
// 缓存
// ==============================
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
    try {
        localStorage.setItem('fc_' + key, JSON.stringify({ ts: Date.now(), data }));
    } catch { /* ignore */ }
}

// ==============================
// 数据加载
// ==============================
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
    for (const league of data) {
        const meta = LEAGUE_META[league.id];
        if (meta) {
            league.abbr = meta.abbr;
            league.code = meta.code;
            league.sportKey = meta.sportKey;
        } else {
            league.abbr = league.name.slice(0, 4);
        }
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
    try {
        state.teamNames = await fetchJSON(`${CONFIG.DATA_PATH}/team_names.json`);
    } catch { state.teamNames = { cn_to_en: {}, en_to_cn: {} }; }
}

async function loadMatches(leagueId) {
    return fetchJSON(`${CONFIG.DATA_PATH}/matches_${leagueId}.json`);
}

// ==============================
// 工具函数
// ==============================
function getCNName(engName) {
    return (state.teamNames.en_to_cn || {})[engName] || null;
}

function getTeamDisplay(teamId) {
    const t = state.teamsById[teamId];
    if (!t) return `Team ${teamId}`;
    const cn = getCNName(t.n);
    return cn ? `${cn}（${t.n}）` : t.n;
}

function getTeamShort(teamId) {
    const t = state.teamsById[teamId];
    if (!t) return `Team ${teamId}`;
    return getCNName(t.n) || t.n;
}

/** 搜索球队（中英文） */
function searchTeams(query, teamList) {
    if (!query || query.length < 1) return [];
    const q = query.toLowerCase().trim();
    const results = [];

    for (const t of teamList) {
        const enLower = t.name.toLowerCase();
        const cnLower = (t.cnName || '').toLowerCase();

        // 精确匹配优先
        if (enLower === q || cnLower === q) {
            results.unshift(t);
            continue;
        }
        // 包含匹配
        if (enLower.includes(q) || cnLower.includes(q)) {
            results.push(t);
            continue;
        }
        // 拼音/部分匹配
        if (q.length >= 2) {
            if (enLower.replace(/[^a-z]/g, '').includes(q) ||
                cnLower.replace(/\s/g, '').includes(q)) {
                results.push(t);
            }
        }
    }

    return results.slice(0, 8);
}

// ==============================
// Tab 切换
// ==============================
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn =>
        btn.classList.toggle('active', btn.dataset.tab === tab));
    document.querySelectorAll('.page-section').forEach(s =>
        s.classList.toggle('active', s.id === 'page-' + tab));
}

// ==============================
// 首页
// ==============================
function renderHomePage() {
    const grid = document.getElementById('leagueGrid');
    grid.innerHTML = '';
    for (const league of state.leagues) {
        const btn = document.createElement('button');
        btn.className = 'league-btn';
        btn.innerHTML = `
            <span class="league-name">${league.abbr || league.name.slice(0, 4)}</span>
            <span class="league-code">${league.code || ''}</span>`;
        btn.onclick = () => {
            // 切到预测页，自动选中该联赛
            document.getElementById('predLeagueSelect').value = league.id;
            onPredLeagueChange();
            switchTab('predict');
        };
        grid.appendChild(btn);
    }
}

// ==============================
// 预测页
// ==============================
function fillLeagueSelects() {
    const selects = ['predLeagueSelect', 'stdLeagueSelect', 'teamLeagueSelect'];
    for (const id of selects) {
        const sel = document.getElementById(id);
        if (!sel) continue;
        sel.innerHTML = '<option value="">-- 请选择联赛 --</option>';
        for (const league of state.leagues) {
            const opt = document.createElement('option');
            opt.value = league.id;
            opt.textContent = `${league.abbr || ''} - ${league.name}`;
            sel.appendChild(opt);
        }
    }
}

async function onPredLeagueChange() {
    const leagueId = parseInt(document.getElementById('predLeagueSelect').value);
    document.getElementById('predInputArea').style.display = 'none';
    document.getElementById('predResult').style.display = 'none';
    state.homeTeam = null;
    state.awayTeam = null;
    document.getElementById('predictBtn').disabled = true;

    if (!leagueId) return;

    const league = state.leagues.find(l => l.id === leagueId);
    const info = document.getElementById('predLeagueInfo');
    info.style.display = 'block';
    info.textContent = `⏳ 正在加载 ${league ? league.name : ''} 数据...`;

    try {
        state.currentLeagueId = leagueId;
        state.currentMatches = await loadMatches(leagueId);

        // 构建球队列表
        const teamIds = new Set();
        for (const m of state.currentMatches) {
            teamIds.add(m.home_team_id);
            teamIds.add(m.away_team_id);
        }
        state.currentTeamList = [];
        for (const tid of teamIds) {
            const t = state.teamsById[tid];
            if (t) {
                const cn = getCNName(t.n);
                state.currentTeamList.push({
                    id: tid,
                    name: t.n,
                    cnName: cn || '',
                    display: cn ? `${cn}（${t.n}）` : t.n,
                });
            }
        }
        state.currentTeamList.sort((a, b) => {
            const an = (a.cnName || a.name).toLowerCase();
            const bn = (b.cnName || b.name).toLowerCase();
            return an.localeCompare(bn, 'zh');
        });

        info.textContent = `✅ ${league ? league.name : ''} — ${state.currentTeamList.length} 支球队，${state.currentMatches.length} 场比赛`;
        document.getElementById('predInputArea').style.display = 'block';

        // 清空输入
        document.getElementById('homeInput').value = '';
        document.getElementById('awayInput').value = '';
        document.getElementById('homeSuggestions').classList.remove('show');
        document.getElementById('awaySuggestions').classList.remove('show');
    } catch (e) {
        info.textContent = '❌ 数据加载失败: ' + e.message;
    }
}

// ====== 球队搜索自动完成 ======
function setupTeamInput(inputId, suggestionsId, onSelect) {
    const input = document.getElementById(inputId);
    const sug = document.getElementById(suggestionsId);
    let activeIdx = -1;

    input.addEventListener('input', () => {
        const q = input.value;
        if (q.length < 1) {
            sug.classList.remove('show');
            onSelect(null);
            return;
        }
        const results = searchTeams(q, state.currentTeamList);
        sug.innerHTML = '';
        if (results.length === 0) {
            sug.classList.remove('show');
            return;
        }
        activeIdx = -1;
        for (const r of results) {
            const div = document.createElement('div');
            div.className = 'suggestion-item';
            div.innerHTML = `<span class="cn-name">${r.cnName || r.name}</span><span class="en-name">${r.cnName ? r.name : ''}</span>`;
            div.onclick = () => {
                input.value = r.display || r.name;
                sug.classList.remove('show');
                onSelect(r);
            };
            sug.appendChild(div);
        }
        sug.classList.add('show');
    });

    input.addEventListener('keydown', (e) => {
        const items = sug.querySelectorAll('.suggestion-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIdx = Math.min(activeIdx + 1, items.length - 1);
            items.forEach((el, i) => el.classList.toggle('active', i === activeIdx));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIdx = Math.max(activeIdx - 1, 0);
            items.forEach((el, i) => el.classList.toggle('active', i === activeIdx));
        } else if (e.key === 'Enter' && activeIdx >= 0 && items[activeIdx]) {
            e.preventDefault();
            items[activeIdx].click();
        }
    });

    input.addEventListener('blur', () => {
        setTimeout(() => sug.classList.remove('show'), 200);
    });

    input.addEventListener('focus', () => {
        if (sug.querySelector('.suggestion-item')) sug.classList.add('show');
    });
}

function initTeamInputs() {
    setupTeamInput('homeInput', 'homeSuggestions', (team) => {
        state.homeTeam = team;
        updatePredictBtn();
    });
    setupTeamInput('awayInput', 'awaySuggestions', (team) => {
        state.awayTeam = team;
        updatePredictBtn();
    });
}

function updatePredictBtn() {
    const btn = document.getElementById('predictBtn');
    btn.disabled = !(state.homeTeam && state.awayTeam &&
        state.homeTeam.id !== state.awayTeam.id);
}

// ====== 执行预测 ======
async function doPredict() {
    if (!state.homeTeam || !state.awayTeam) return;
    if (state.homeTeam.id === state.awayTeam.id) {
        showError('主队和客队不能相同');
        return;
    }

    const odds = {
        home: parseFloat(document.getElementById('oddsHome').value),
        draw: parseFloat(document.getElementById('oddsDraw').value),
        away: parseFloat(document.getElementById('oddsAway').value),
    };
    if (!odds.home || !odds.draw || !odds.away || odds.home < 1 || odds.draw < 1 || odds.away < 1) {
        showError('请输入有效的赔率（≥1.01）');
        return;
    }

    showLoading('🔮 计算预测中...');
    await new Promise(r => setTimeout(r, 50));

    try {
        const leagueAvg = PoissonPredictor.calcLeagueAvgGoals(state.currentMatches);

        const homeTeam = state.teamsById[state.homeTeam.id];
        const awayTeam = state.teamsById[state.awayTeam.id];

        const predService = new PredictionService({
            leagueParams: LEAGUE_PARAMS,
            defaultEloHomeAdv: 100, defaultRho: 0.15, defaultPoissonWeight: 0.55,
        });

        const result = predService.predict({
            homeTeamId: state.homeTeam.id,
            awayTeamId: state.awayTeam.id,
            homeElo: homeTeam ? homeTeam.elo : 1500,
            awayElo: awayTeam ? awayTeam.elo : 1500,
            leagueId: state.currentLeagueId,
            matches: state.currentMatches,
            leagueAvg,
        });

        // 近期比赛
        const homeRecent = getRecentMatches(state.currentMatches, state.homeTeam.id, 5);
        const awayRecent = getRecentMatches(state.currentMatches, state.awayTeam.id, 5);
        const h2h = getHeadToHead(state.currentMatches, state.homeTeam.id, state.awayTeam.id, 5);

        hideLoading();
        renderResult({
            ...result,
            homeName: getTeamDisplay(state.homeTeam.id),
            awayName: getTeamDisplay(state.awayTeam.id),
            homeShort: getTeamShort(state.homeTeam.id),
            awayShort: getTeamShort(state.awayTeam.id),
            homeRecent, awayRecent, h2h,
            odds,
            leagueAvg: Math.round(leagueAvg * 100) / 100,
        });
    } catch (e) {
        hideLoading();
        showError('预测失败: ' + e.message);
        console.error(e);
    }
}

function getRecentMatches(matches, teamId, limit) {
    const tm = matches.filter(m =>
        (m.home_team_id === teamId || m.away_team_id === teamId) &&
        m.status === 'FINISHED' && m.score_home != null);
    tm.sort((a, b) => a.utc_date < b.utc_date ? 1 : -1);
    return tm.slice(0, limit).map(m => {
        const isHome = m.home_team_id === teamId;
        const gf = isHome ? m.score_home : m.score_away;
        const ga = isHome ? m.score_away : m.score_home;
        return {
            date: m.utc_date ? m.utc_date.slice(5, 10) : '',
            opponent: isHome ? getTeamShort(m.away_team_id) : getTeamShort(m.home_team_id),
            isHome,
            gf, ga,
            score: `${gf}-${ga}`,
            result: gf > ga ? 'W' : (gf < ga ? 'L' : 'D'),
        };
    });
}

function getHeadToHead(matches, teamA, teamB, limit) {
    const h2h = matches.filter(m =>
        ((m.home_team_id === teamA && m.away_team_id === teamB) ||
         (m.home_team_id === teamB && m.away_team_id === teamA)) &&
        m.status === 'FINISHED' && m.score_home != null);
    h2h.sort((a, b) => a.utc_date < b.utc_date ? 1 : -1);
    return h2h.slice(0, limit).map(m => ({
        homeName: getTeamShort(m.home_team_id),
        awayName: getTeamShort(m.away_team_id),
        homeScore: m.score_home,
        awayScore: m.score_away,
    }));
}

// ====== 结果渲染（Streamlit 风格） ======
function renderResult(r) {
    const c = document.getElementById('predResult');
    c.style.display = 'block';

    let html = `<div class="score-card">
        <div class="teams">${r.homeName} vs ${r.awayName}</div>
        <div class="score">${r.predictedHomeScore} : ${r.predictedAwayScore}</div>
        <div class="outcome">🎯 ${
            r.predictedOutcome === 'HOME' ? '主胜 ✅' :
            r.predictedOutcome === 'AWAY' ? '客胜 ✅' : '平局 🤝'
        }</div>
        <div class="confidence-text">置信度: <strong>${r.confidence}%</strong></div>
    </div>`;

    // 概率条
    const h = r.homeWinProb, d = r.drawProb, a = r.awayWinProb;
    const total = h + d + a;
    if (total > 0) {
        const hp = h / total, dp = d / total, ap = a / total;
        html += `<div class="card">
            <div class="card-title" style="margin-bottom:4px">🎲 胜平负概率</div>
            <div class="prob-bar-3">
                <div class="seg" style="flex:${hp.toFixed(3)};background:#2ecc71;border-radius:18px 0 0 18px">
                    ${hp > 0.08 ? '🏠 ' + (h * 100).toFixed(0) + '%' : ''}
                </div>
                <div class="seg" style="flex:${dp.toFixed(3)};background:#95a5a6">
                    ${dp > 0.08 ? '🤝 ' + (d * 100).toFixed(0) + '%' : ''}
                </div>
                <div class="seg" style="flex:${ap.toFixed(3)};background:#e74c3c;border-radius:0 18px 18px 0">
                    ${ap > 0.08 ? '✈️ ' + (a * 100).toFixed(0) + '%' : ''}
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center;margin-top:8px">
                <div><strong style="color:#2ecc71;font-size:1.1rem">${(h * 100).toFixed(1)}%</strong><br><small>主胜</small></div>
                <div><strong style="color:#95a5a6;font-size:1.1rem">${(d * 100).toFixed(1)}%</strong><br><small>平局</small></div>
                <div><strong style="color:#e74c3c;font-size:1.1rem">${(a * 100).toFixed(1)}%</strong><br><small>客胜</small></div>
            </div>
            <div style="margin-top:8px;font-size:0.85rem;color:var(--text-secondary)">
                预期进球 (xG): ${r.homeShort} ${r.poissonResult.homeXg} — ${r.awayShort} ${r.poissonResult.awayXg}
            </div>
            <div style="font-size:0.85rem;color:var(--text-secondary)">
                联赛场均总进球: ${r.leagueAvg}
            </div>
        </div>`;
    }

    // 比分概率分布（Top 8）
    const scores = r.poissonResult.scoreProbabilities;
    if (scores && scores.length > 0) {
        const maxP = scores[0].probability;
        html += `<div class="card">
            <div class="card-title">📊 比分概率分布</div>
            <div class="score-grid-4">`;
        for (let i = 0; i < Math.min(scores.length, 8); i++) {
            const sp = scores[i];
            const pct = maxP > 0 ? (sp.probability / maxP * 100) : 0;
            html += `<div class="score-grid-item">
                <div class="score-num">${sp.home}:${sp.away}</div>
                <div class="score-pct">${(sp.probability * 100).toFixed(1)}%</div>
                <div class="prob-bar-tiny"><div class="prob-fill" style="width:${pct}%"></div></div>
            </div>`;
        }
        html += `</div></div>`;
    }

    // 近期主客场成绩
    html += `<div class="card">
        <div class="card-title">📋 近期成绩（模型计算依据）</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">`;

    // 主队近期
    html += `<div><strong>🏠 ${r.homeShort} 近期 5 场主场比赛</strong>`;
    const homeForm = r.homeRecent || [];
    if (homeForm.length > 0) {
        for (const m of homeForm) {
            const emoji = m.result === 'W' ? '✅' : (m.result === 'L' ? '❌' : '➖');
            html += `<div class="form-item">${emoji} <strong>${m.score}</strong> vs ${m.opponent}</div>`;
        }
    } else {
        html += '<div style="font-size:0.8rem;color:var(--text-secondary);padding:4px 0">暂无主场比赛数据</div>';
    }
    html += `</div>`;

    // 客队近期
    html += `<div><strong>✈️ ${r.awayShort} 近期 5 场客场比赛</strong>`;
    const awayForm = r.awayRecent || [];
    if (awayForm.length > 0) {
        for (const m of awayForm) {
            const emoji = m.result === 'W' ? '✅' : (m.result === 'L' ? '❌' : '➖');
            html += `<div class="form-item">${emoji} <strong>${m.score}</strong> vs ${m.opponent}</div>`;
        }
    } else {
        html += '<div style="font-size:0.8rem;color:var(--text-secondary);padding:4px 0">暂无客场比赛数据</div>';
    }
    html += `</div></div></div>`;

    // 赔率对比分析
    html += `<div class="card">
        <div class="card-title">💰 赔率分析（用户输入 vs 模型预测）</div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">`;

    const oddsKeys = [
        { key: 'home', label: '主胜', prob: r.homeWinProb, odds: r.odds.home },
        { key: 'draw', label: '平局', prob: r.drawProb, odds: r.odds.draw },
        { key: 'away', label: '客胜', prob: r.awayWinProb, odds: r.odds.away },
    ];

    for (const ok of oddsKeys) {
        const implied = OddsUtils.impliedProb(ok.odds);
        const diff = ok.prob - implied;
        const diffPct = (diff * 100).toFixed(0);
        const diffClass = diff > 0 ? 'pos' : 'neg';
        const ev = OddsUtils.expectedValue(ok.odds, ok.prob);
        const isValue = ev > 0;

        html += `<div class="odds-metric">
            <div class="odds-label">${ok.label}</div>
            <div class="odds-model">${(ok.prob * 100).toFixed(0)}%</div>
            <div class="odds-market">市场 ${(implied * 100).toFixed(0)}%
                <span class="odds-delta ${diffClass}">(${diff > 0 ? '+' : ''}${diffPct}%)</span>
            </div>
        </div>`;

        if (isValue) {
            html += `<div class="value-bet" style="grid-column:1/-1">
                <strong>${ok.label}</strong> — 期望值 <strong>${(ev * 100).toFixed(1)}%</strong>，
                赔率 ${ok.odds.toFixed(2)}，模型 ${(ok.prob * 100).toFixed(1)}% vs 市场 ${(implied * 100).toFixed(1)}%
            </div>`;
        }
    }

    html += `</div></div>`;

    // 模型详情（折叠）
    const lp = r.leagueParams || {};
    html += `<details class="details-expander">
        <summary>🔬 模型详情（Poisson + Elo 分解）</summary>
        <div class="details-body">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
                <div>
                    <strong>Poisson 模型</strong>
                    <div class="metric-row"><span class="label">主胜</span><span class="value">${(r.poissonResult.homeWinProb * 100).toFixed(1)}%</span></div>
                    <div class="metric-row"><span class="label">平局</span><span class="value">${(r.poissonResult.drawProb * 100).toFixed(1)}%</span></div>
                    <div class="metric-row"><span class="label">客胜</span><span class="value">${(r.poissonResult.awayWinProb * 100).toFixed(1)}%</span></div>
                    <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px">xG: 主 ${r.poissonResult.homeXg} / 客 ${r.poissonResult.awayXg}</div>
                </div>
                <div>
                    <strong>Elo 模型</strong>
                    <div class="metric-row"><span class="label">主胜</span><span class="value">${(r.eloResult.homeWinProb * 100).toFixed(1)}%</span></div>
                    <div class="metric-row"><span class="label">平局</span><span class="value">${(r.eloResult.drawProb * 100).toFixed(1)}%</span></div>
                    <div class="metric-row"><span class="label">客胜</span><span class="value">${(r.eloResult.awayWinProb * 100).toFixed(1)}%</span></div>
                    <div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px">
                        ${r.homeShort}: Elo ${Math.round(state.teamsById[state.homeTeam.id]?.elo || 1500)} |
                        ${r.awayShort}: Elo ${Math.round(state.teamsById[state.awayTeam.id]?.elo || 1500)}
                    </div>
                </div>
            </div>
            <div style="margin-top:8px;font-size:0.8rem;color:var(--text-secondary)">
                融合权重: Poisson ${Math.round((r.modelWeights.poisson || 0.55) * 100)}% + Elo ${Math.round((r.modelWeights.elo || 0.45) * 100)}%
                ${lp.eloHomeAdv ? `| 主场优势 HFA=${lp.eloHomeAdv}` : ''}
                ${lp.dixonColesRho ? `| Dixon-Coles ρ=${lp.dixonColesRho}` : ''}
            </div>
        </div>
    </details>`;

    // 历史交锋
    if (r.h2h && r.h2h.length > 0) {
        html += `<div class="card" style="margin-top:12px">
            <div class="card-title">⚔️ 历史交锋</div>`;
        for (const m of r.h2h) {
            html += `<div class="h2h-row">
                <span class="h2h-home">${m.homeName}</span>
                <span class="h2h-score">${m.homeScore}-${m.awayScore}</span>
                <span class="h2h-away">${m.awayName}</span>
            </div>`;
        }
        html += `<div style="text-align:right;font-size:0.8rem;color:var(--text-secondary)">${r.h2h.length} 场交锋</div>`;
        html += `</div>`;
    }

    // 开始新预测按钮
    html += `<button class="btn btn-secondary" onclick="resetPrediction()" style="margin-top:4px">← 新预测</button>`;

    c.innerHTML = html;
    c.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function resetPrediction() {
    state.homeTeam = null;
    state.awayTeam = null;
    document.getElementById('homeInput').value = '';
    document.getElementById('awayInput').value = '';
    document.getElementById('predResult').style.display = 'none';
    document.getElementById('predictBtn').disabled = true;
    document.getElementById('predResult').innerHTML = '';
}

// ==============================
// 积分榜
// ==============================
async function onStdLeagueChange() {
    const leagueId = parseInt(document.getElementById('stdLeagueSelect').value);
    const container = document.getElementById('standingsContent');
    container.innerHTML = '';

    if (!leagueId) return;

    const league = state.leagues.find(l => l.id === leagueId);
    container.innerHTML = `<div class="loading"><div class="spinner"></div><span>加载中...</span></div>`;

    try {
        const matches = await loadMatches(leagueId);
        const standings = calcStandings(matches);
        renderStandings(standings, league ? league.name : '');
    } catch (e) {
        container.innerHTML = `<div class="error-box">加载失败: ${e.message}</div>`;
    }
}

function renderStandings(standings, leagueName) {
    const container = document.getElementById('standingsContent');
    if (!standings.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无比赛数据</div></div>';
        return;
    }

    let html = `<div class="card"><div class="card-title">📊 ${leagueName} 积分榜</div>
        <div class="info-box">基于本地比赛数据计算</div>
        <table class="standings-table">
            <thead><tr><th>#</th><th>球队</th><th>赛</th><th>胜</th><th>平</th><th>负</th><th>进</th><th>失</th><th>净</th><th>积分</th></tr></thead><tbody>`;

    for (const s of standings) {
        const name = getTeamDisplay(s.teamId);
        html += `<tr>
            <td>${s.position}</td>
            <td class="team-name">${name}</td>
            <td>${s.played}</td>
            <td>${s.won}</td>
            <td>${s.drawn}</td>
            <td>${s.lost}</td>
            <td>${s.gf}</td>
            <td>${s.ga}</td>
            <td>${s.gd > 0 ? '+' : ''}${s.gd}</td>
            <td><strong>${s.pts}</strong></td>
        </tr>`;
    }

    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

// ==============================
// 球队分析
// ==============================
async function onTeamLeagueChange() {
    const leagueId = parseInt(document.getElementById('teamLeagueSelect').value);
    const teamSelect = document.getElementById('teamSelect');
    teamSelect.innerHTML = '<option value="">-- 加载中... --</option>';
    document.getElementById('teamAnalyzeBtn').disabled = true;
    document.getElementById('teamResult').style.display = 'none';

    if (!leagueId) {
        teamSelect.innerHTML = '<option value="">-- 请选择联赛 --</option>';
        return;
    }

    try {
        const matches = await loadMatches(leagueId);
        const teamIds = new Set();
        for (const m of matches) teamIds.add(m.home_team_id) && teamIds.add(m.away_team_id);

        const teams = [];
        for (const tid of teamIds) {
            const t = state.teamsById[tid];
            if (t) teams.push(t);
        }
        teams.sort((a, b) => {
            const ac = getCNName(a.n) || a.n;
            const bc = getCNName(b.n) || b.n;
            return ac.toLowerCase().localeCompare(bc.toLowerCase(), 'zh');
        });

        teamSelect.innerHTML = '<option value="">-- 请选择球队 --</option>';
        for (const t of teams) {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = getTeamDisplay(t.id);
            teamSelect.appendChild(opt);
        }

        state._teamPageMatches = matches;
        state._teamPageLeagueId = leagueId;
    } catch (e) {
        teamSelect.innerHTML = '<option value="">加载失败</option>';
    }
}

function onTeamSelectChange() {
    const tid = parseInt(document.getElementById('teamSelect').value);
    document.getElementById('teamAnalyzeBtn').disabled = !tid;
    document.getElementById('teamResult').style.display = 'none';
}

async function analyzeTeam() {
    const teamId = parseInt(document.getElementById('teamSelect').value);
    const matches = state._teamPageMatches;
    if (!teamId || !matches) return;

    const team = state.teamsById[teamId];
    if (!team) return;

    const container = document.getElementById('teamResult');
    container.style.display = 'block';
    container.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载中...</span></div>';
    await new Promise(r => setTimeout(r, 50));

    const recent = getRecentMatches(matches, teamId, 10);

    const homeMatches = matches.filter(m => m.home_team_id === teamId && m.status === 'FINISHED' && m.score_home != null);
    const awayMatches = matches.filter(m => m.away_team_id === teamId && m.status === 'FINISHED' && m.score_home != null);

    const homeStats = {
        played: homeMatches.length,
        won: homeMatches.filter(m => m.score_home > m.score_away).length,
        drawn: homeMatches.filter(m => m.score_home === m.score_away).length,
        lost: homeMatches.filter(m => m.score_home < m.score_away).length,
        gf: homeMatches.reduce((s, m) => s + m.score_home, 0),
        ga: homeMatches.reduce((s, m) => s + m.score_away, 0),
    };
    const awayStats = {
        played: awayMatches.length,
        won: awayMatches.filter(m => m.score_away > m.score_home).length,
        drawn: awayMatches.filter(m => m.score_away === m.score_home).length,
        lost: awayMatches.filter(m => m.score_away < m.score_home).length,
        gf: awayMatches.reduce((s, m) => s + m.score_away, 0),
        ga: awayMatches.reduce((s, m) => s + m.score_home, 0),
    };

    const formStr = recent.slice(0, 5).map(m => m.result === 'W' ? '✅' : (m.result === 'L' ? '❌' : '➖')).join(' ');

    // 进球分布
    const goalDist = {};
    for (const m of [...homeMatches, ...awayMatches]) {
        const isHome = m.home_team_id === teamId;
        const gf = isHome ? m.score_home : m.score_away;
        goalDist[gf] = (goalDist[gf] || 0) + 1;
    }

    let html = `<div class="card">
        <div class="card-title">${getTeamDisplay(teamId)}</div>
        <div class="metric-row"><span class="label">Elo 评分</span><span class="value" style="font-size:1.2rem">${Math.round(team.elo)}</span></div>
        <div class="metric-row"><span class="label">近期状态</span><span class="value">${formStr || '暂无数据'}</span></div>
    </div>`;

    html += `<div class="card">
        <div class="card-title">📊 数据统计</div>
        <table class="standings-table">
            <tr><th></th><th>赛</th><th>胜</th><th>平</th><th>负</th><th>进</th><th>失</th><th>净</th></tr>
            <tr><td class="team-name">🏠 主场</td><td>${homeStats.played}</td><td>${homeStats.won}</td><td>${homeStats.drawn}</td><td>${homeStats.lost}</td>
                <td>${homeStats.gf}</td><td>${homeStats.ga}</td><td>${homeStats.gf - homeStats.ga}</td></tr>
            <tr><td class="team-name">✈️ 客场</td><td>${awayStats.played}</td><td>${awayStats.won}</td><td>${awayStats.drawn}</td><td>${awayStats.lost}</td>
                <td>${awayStats.gf}</td><td>${awayStats.ga}</td><td>${awayStats.gf - awayStats.ga}</td></tr>
            <tr style="font-weight:700"><td class="team-name">合计</td>
                <td>${homeStats.played + awayStats.played}</td>
                <td>${homeStats.won + awayStats.won}</td>
                <td>${homeStats.drawn + awayStats.drawn}</td>
                <td>${homeStats.lost + awayStats.lost}</td>
                <td>${homeStats.gf + awayStats.gf}</td>
                <td>${homeStats.ga + awayStats.ga}</td>
                <td>${(homeStats.gf + awayStats.gf) - (homeStats.ga + awayStats.ga)}</td></tr>
        </table>
    </div>`;

    if (recent.length > 0) {
        html += `<div class="card"><div class="card-title">📋 近期比赛</div>`;
        for (const m of recent) {
            const emoji = m.result === 'W' ? '✅' : (m.result === 'L' ? '❌' : '➖');
            html += `<div class="form-item">${emoji} ${m.date} ${m.isHome ? '主场' : '客场'} vs ${m.opponent} <strong>${m.score}</strong></div>`;
        }
        html += `</div>`;
    }

    const goalKeys = Object.keys(goalDist).sort((a, b) => a - b);
    if (goalKeys.length > 0) {
        const totalG = Object.values(goalDist).reduce((s, v) => s + v, 0);
        html += `<div class="card"><div class="card-title">🎯 单场进球分布</div>`;
        for (const g of goalKeys) {
            const pct = (goalDist[g] / totalG * 100).toFixed(1);
            html += `<div class="metric-row"><span class="label">${g} 球</span><span class="value">${goalDist[g]} 场 (${pct}%)</span></div>`;
        }
        html += `</div>`;
    }

    container.innerHTML = html;
}

// ==============================
// UI 工具
// ==============================
function showLoading(text) {
    const el = document.getElementById('predLoading');
    if (el) {
        el.style.display = 'flex';
        document.getElementById('predLoadingText').textContent = text || '计算中...';
    }
}

function hideLoading() {
    const el = document.getElementById('predLoading');
    if (el) el.style.display = 'none';
}

function showError(msg) {
    const c = document.getElementById('predResult');
    c.style.display = 'block';
    c.innerHTML = `<div class="error-box">❌ ${msg}</div>`;
}

// ==============================
// 初始化
// ==============================
async function init() {
    try {
        await Promise.all([loadLeagues(), loadTeams(), loadTeamNames()]);

        renderHomePage();
        fillLeagueSelects();
        initTeamInputs();

        // 首页联赛点击 → 切到预测页
        document.getElementById('leagueGrid').querySelectorAll('.league-btn').forEach(btn => {
            // already handled in renderHomePage
        });

    } catch (e) {
        console.error('初始化失败:', e);
        document.body.innerHTML = `<div class="error-box" style="margin:2rem;padding:2rem;text-align:center">
            <h3>❌ 初始化失败</h3><p>${e.message}</p>
            <button class="btn btn-primary" onclick="location.reload()" style="margin-top:1rem">重新加载</button>
        </div>`;
    }
}

document.addEventListener('DOMContentLoaded', init);

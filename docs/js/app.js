/**
 * ⚽ 足彩泊松分析 — 主应用逻辑
 */

// ==============================
// 配置
// ==============================
const CONFIG = {
    // The Odds API Key (user's existing key)
    ODDS_API_KEY: 'efc0bf96ed9d8255c706f2185a15e42e',
    DATA_PATH: 'data',
    CACHE_TTL: 6 * 60 * 60 * 1000,  // 6 hours
};

// 联赛信息（包含显示名、代码、ID映射）
const LEAGUE_META = {
    2021: { code: 'PL', name: '英格兰超级联赛（英超）', abbr: '英超', sportKey: 'soccer_epl' },
    2002: { code: 'BL1', name: '德国超级联赛（德甲）', abbr: '德甲', sportKey: 'soccer_germany_bundesliga' },
    2014: { code: 'PD', name: '西班牙超级联赛（西甲）', abbr: '西甲', sportKey: 'soccer_spain_la_liga' },
    2019: { code: 'SA', name: '意大利超级联赛（意甲）', abbr: '意甲', sportKey: 'soccer_italy_serie_a' },
    2015: { code: 'FL1', name: '法国超级联赛（法甲）', abbr: '法甲', sportKey: 'soccer_france_ligue_one' },
    2022: { code: 'CN1', name: '中国超级联赛（中超）', abbr: '中超', sportKey: 'soccer_china_superleague' },
    2023: { code: 'WCQ', name: '世界杯预选赛', abbr: '世预赛', sportKey: null },
    2024: { code: 'WC2014', name: '2014 世界杯', abbr: '2014世界杯', sportKey: null },
    2025: { code: 'WC2018', name: '2018 世界杯', abbr: '2018世界杯', sportKey: null },
    2026: { code: 'WC2022', name: '2022 世界杯', abbr: '2022世界杯', sportKey: null },
};

// 联赛特定参数（同 Python config.py）
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
// 全局状态
// ==============================
const state = {
    leagues: [],
    teams: [],
    teamNames: { cn_to_en: {}, en_to_cn: {} },
    teamsById: {},

    // 当前选中的联赛数据
    currentLeagueId: null,
    currentMatches: [],
    currentTeams: [],

    // 预测流程
    predLeagueId: null,
    homeTeamId: null,
    awayTeamId: null,
    odds: null,

    // 缓存 { key: { ts, data } }
    cache: {},
};

// ==============================
// 缓存工具
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
    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${url}`);
    const data = await resp.json();

    // 仅缓存大于 1KB 的响应
    if (JSON.stringify(data).length > 1024) {
        cacheSet(url, data);
    }
    return data;
}

async function loadLeagues() {
    try {
        const data = await fetchJSON(`${CONFIG.DATA_PATH}/leagues.json`);
        state.leagues = data;
        // 注入 meta 信息
        for (const league of state.leagues) {
            const meta = LEAGUE_META[league.id];
            if (meta) {
                league.abbr = meta.abbr;
                league.code = meta.code;
                league.sportKey = meta.sportKey;
            } else {
                league.abbr = league.name.slice(0, 4);
                league.code = league.code || '';
                league.sportKey = null;
            }
        }
        return data;
    } catch (e) {
        console.error('联赛加载失败:', e);
        showToast('联赛数据加载失败', 'error');
        return [];
    }
}

async function loadTeams() {
    try {
        const data = await fetchJSON(`${CONFIG.DATA_PATH}/teams.json`);
        state.teams = data;
        state.teamsById = {};
        for (const t of data) {
            state.teamsById[t.id] = t;
        }
        return data;
    } catch (e) {
        console.error('球队加载失败:', e);
        return [];
    }
}

async function loadTeamNames() {
    try {
        const data = await fetchJSON(`${CONFIG.DATA_PATH}/team_names.json`);
        state.teamNames = data;
    } catch (e) {
        console.error('球队名映射加载失败:', e);
    }
}

async function loadMatches(leagueId) {
    const url = `${CONFIG.DATA_PATH}/matches_${leagueId}.json`;
    const data = await fetchJSON(url);
    return data;
}

// ==============================
// 球队名显示工具
// ==============================
function getCNName(engName) {
    const map = state.teamNames.en_to_cn || {};
    return map[engName] || null;
}

function getTeamDisplayName(teamId) {
    const team = state.teamsById[teamId];
    if (!team) return `Team ${teamId}`;
    const cn = getCNName(team.n);
    return cn ? `${cn}（${team.n}）` : team.n;
}

function getTeamShortDisplay(teamId) {
    const team = state.teamsById[teamId];
    if (!team) return `Team ${teamId}`;
    const cn = getCNName(team.n);
    return cn || team.n;
}

// ==============================
// Tab 切换
// ==============================
function switchTab(tab) {
    // 更新标签栏
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    // 更新页面
    document.querySelectorAll('.page-section').forEach(section => {
        section.classList.toggle('active', section.id === 'page-' + tab);
    });
}

// ==============================
// 首页
// ==============================
function renderLeagueGrid(containerId, onClick) {
    const grid = document.getElementById(containerId);
    if (!grid) return;
    grid.innerHTML = '';

    for (const league of state.leagues) {
        const btn = document.createElement('button');
        btn.className = 'league-btn';
        btn.type = 'button';
        btn.innerHTML = `
            <span class="league-name">${league.abbr || league.name.slice(0, 4)}</span>
            <span class="league-code">${league.code || ''}</span>
        `;
        btn.onclick = () => onClick(league.id);
        grid.appendChild(btn);
    }
}

function initHomePage() {
    renderLeagueGrid('leagueGrid', (leagueId) => {
        // 选择联赛后切换到分析页并自动选中
        state.predLeagueId = leagueId;
        switchTab('predict');
        initPredictionFlow();
    });
}

// ==============================
// 预测流程
// ==============================
async function initPredictionFlow() {
    // 隐藏所有步骤
    hide('predStep1');
    hide('predStep2');
    hide('predStep3');
    hide('predResult');
    hide('predLoading');

    if (!state.predLeagueId) {
        // 第1步：选择联赛
        show('predStep1');
        renderLeagueGrid('predLeagueGrid', async (leagueId) => {
            state.predLeagueId = leagueId;
            showLoading('正在加载比赛数据...');
            try {
                state.currentMatches = await loadMatches(leagueId);
                show('predStep2');
                hide('predStep1');
                hide('predStep3');
                hide('predResult');
                populateTeamSelects(leagueId);
            } catch (e) {
                showToast('数据加载失败: ' + e.message, 'error');
            } finally {
                hideLoading();
            }
        });
    } else {
        // 已经有联赛选择，直接到第2步
        show('predStep2');
        const league = state.leagues.find(l => l.id === state.predLeagueId);
        if (league) {
            document.getElementById('predSeasonLabel').textContent = `${league.name}`;
        }
        if (state.currentMatches.length === 0) {
            showLoading('加载比赛数据...');
            try {
                state.currentMatches = await loadMatches(state.predLeagueId);
            } catch (e) {
                showToast('数据加载失败', 'error');
            } finally {
                hideLoading();
            }
        }
        populateTeamSelects(state.predLeagueId);
    }
}

function populateTeamSelects(leagueId) {
    // 收集该联赛中的球队
    const teamIds = new Set();
    for (const m of state.currentMatches) {
        teamIds.add(m.home_team_id);
        teamIds.add(m.away_team_id);
    }

    const teams = [];
    for (const tid of teamIds) {
        const t = state.teamsById[tid];
        if (t) teams.push(t);
    }
    teams.sort((a, b) => a.n.localeCompare(b.n, 'zh'));

    state.currentTeams = teams;

    const league = state.leagues.find(l => l.id === leagueId);
    document.getElementById('predSeasonLabel').textContent = league ? league.name : '';

    const homeSelect = document.getElementById('homeTeam');
    const awaySelect = document.getElementById('awayTeam');

    homeSelect.innerHTML = '<option value="">-- 请选择主队 --</option>';
    awaySelect.innerHTML = '<option value="">-- 请选择客队 --</option>';

    for (const t of teams) {
        const label = getTeamDisplayName(t.id);
        const val = t.id;

        const opt1 = document.createElement('option');
        opt1.value = val;
        opt1.textContent = label;
        homeSelect.appendChild(opt1);

        const opt2 = document.createElement('option');
        opt2.value = val;
        opt2.textContent = label;
        awaySelect.appendChild(opt2);
    }

    hide('predStep1');
    show('predStep2');
    hide('predStep3');
    hide('predResult');
}

function onTeamChange() {
    const home = parseInt(document.getElementById('homeTeam').value);
    const away = parseInt(document.getElementById('awayTeam').value);
    state.homeTeamId = home;
    state.awayTeamId = away;
    document.getElementById('goToOddsBtn').disabled = !home || !away || home === away;
}

function goToOddsStep() {
    hide('predStep2');
    show('predStep3');
    hide('manualOddsInput');
    state.odds = null;
}

function backToLeagueSelect() {
    state.predLeagueId = null;
    state.currentMatches = [];
    state.odds = null;
    hide('predStep2');
    hide('predStep3');
    hide('predResult');
    show('predStep1');
    renderLeagueGrid('predLeagueGrid', async (leagueId) => {
        state.predLeagueId = leagueId;
        showLoading('加载比赛数据...');
        try {
            state.currentMatches = await loadMatches(leagueId);
            show('predStep2');
            hide('predStep1');
            hide('predStep3');
            hide('predResult');
            populateTeamSelects(leagueId);
        } catch (e) {
            showToast('加载失败: ' + e.message, 'error');
        } finally {
            hideLoading();
        }
    });
}

function backToTeamSelect() {
    state.odds = null;
    hide('predStep3');
    hide('predResult');
    show('predStep2');
}

function backToHomeFromResult() {
    state.predLeagueId = null;
    state.currentMatches = [];
    state.odds = null;
    hide('predStep2');
    hide('predStep3');
    hide('predResult');
    show('predStep1');
    switchTab('home');
}

// ====== 赔率 ======
async function fetchOdds() {
    const leagueId = state.predLeagueId;
    const meta = LEAGUE_META[leagueId];
    if (!meta || !meta.sportKey) {
        showToast('该联赛暂不支持自动赔率拉取，请手动输入', 'warning');
        return;
    }

    const homeTeam = state.teamsById[state.homeTeamId];
    const awayTeam = state.teamsById[state.awayTeamId];
    if (!homeTeam || !awayTeam) return;

    showLoading('正在拉取赔率...');
    try {
        const url = `https://api.the-odds-api.com/v4/sports/${meta.sportKey}/odds/?apiKey=${CONFIG.ODDS_API_KEY}&regions=eu&markets=h2h&oddsFormat=decimal`;
        const resp = await fetch(url);
        const remaining = resp.headers.get('x-requests-remaining') || '?';
        const data = await resp.json();

        if (!Array.isArray(data)) {
            showToast('赔率 API 返回异常: ' + JSON.stringify(data), 'error');
            hideLoading();
            return;
        }

        // 解析赔率
        const homeName = homeTeam.n;
        const awayName = awayTeam.n;
        let found = null;

        for (const game of data) {
            const ht = game.home_team || '';
            const at = game.away_team || '';
            // 尝试匹配
            if ((ht.includes(homeName) || homeName.includes(ht)) &&
                (at.includes(awayName) || awayName.includes(at))) {
                let best = { home: null, draw: null, away: null };
                for (const bk of game.bookmakers || []) {
                    for (const m of bk.markets || []) {
                        if (m.key !== 'h2h') continue;
                        for (const o of m.outcomes || []) {
                            const name = o.name || '';
                            const price = o.price || 0;
                            // The Odds API returns the home/draw/away names exactly
                            if (name === ht || name.includes(homeName)) {
                                if (best.home === null || price > best.home) best.home = price;
                            } else if (name === 'Draw') {
                                if (best.draw === null || price > best.draw) best.draw = price;
                            } else if (name === at || name.includes(awayName)) {
                                if (best.away === null || price > best.away) best.away = price;
                            }
                        }
                    }
                }
                if (best.home && best.draw && best.away) {
                    found = best;
                    found.time = game.commence_time || '';
                    found.remaining = remaining;
                    break;
                }
            }
        }

        if (found) {
            state.odds = found;
            showToast(`✅ 已自动拉取赔率（余 ${found.remaining} 次请求）`, 'success');
            hide('predStep3');
            hideLoading();
            await runAnalysis();
        } else {
            showToast('⚠️ 未匹配到该比赛的赔率，请手动输入', 'warning');
            hideLoading();
            showManualOdds();
        }
    } catch (e) {
        showToast('赔率获取失败: ' + e.message + '，请手动输入', 'error');
        hideLoading();
        showManualOdds();
    }
}

function showManualOdds() {
    document.getElementById('manualOddsInput').style.display = 'block';
    document.getElementById('oddsBtnGroup').style.display = 'none';
}

function submitManualOdds() {
    const h = parseFloat(document.getElementById('oddsHome').value);
    const d = parseFloat(document.getElementById('oddsDraw').value);
    const a = parseFloat(document.getElementById('oddsAway').value);
    if (!h || !d || !a) {
        showToast('请完整输入三个赔率', 'warning');
        return;
    }
    state.odds = { home: h, draw: d, away: a };
    hide('predStep3');
    runAnalysis();
}

function skipOdds() {
    state.odds = null;
    hide('predStep3');
    runAnalysis();
}

// ====== 核心分析 ======
async function runAnalysis() {
    showLoading('正在计算分析结果...');

    // 小延迟让 UI 更新
    await new Promise(r => setTimeout(r, 50));

    try {
        const leagueId = state.predLeagueId;
        const homeTeamId = state.homeTeamId;
        const awayTeamId = state.awayTeamId;
        const matches = state.currentMatches;

        const homeTeam = state.teamsById[homeTeamId];
        const awayTeam = state.teamsById[awayTeamId];
        if (!homeTeam || !awayTeam) {
            showToast('球队数据异常', 'error');
            hideLoading();
            return;
        }

        // 联赛场均进球
        const leagueAvg = PoissonPredictor.calcLeagueAvgGoals(matches);

        // 创建预测服务
        const predService = new PredictionService({
            leagueParams: LEAGUE_PARAMS,
            defaultEloHomeAdv: 100,
            defaultRho: 0.15,
            defaultPoissonWeight: 0.55,
        });

        const result = predService.predict({
            homeTeamId,
            awayTeamId,
            homeElo: homeTeam.elo || 1500,
            awayElo: awayTeam.elo || 1500,
            leagueId,
            matches,
            leagueAvg,
        });

        // 获取近期比赛详情用于展示
        const homeRecent = getRecentMatches(matches, homeTeamId, 5);
        const awayRecent = getRecentMatches(matches, awayTeamId, 5);

        // 历史交锋
        const h2h = getHeadToHead(matches, homeTeamId, awayTeamId, 5);

        // 渲染结果
        renderResult({
            ...result,
            homeTeam: getTeamDisplayName(homeTeamId),
            awayTeam: getTeamDisplayName(awayTeamId),
            homeTeamShort: getTeamShortDisplay(homeTeamId),
            awayTeamShort: getTeamShortDisplay(awayTeamId),
            homeRecent,
            awayRecent,
            h2h,
            leagueName: (state.leagues.find(l => l.id === leagueId) || {}).name,
            odds: state.odds,
            leagueAvg: Math.round(leagueAvg * 100) / 100,
        });

        hideLoading();
        show('predResult');
    } catch (e) {
        showToast('分析失败: ' + e.message, 'error');
        hideLoading();
        console.error(e);
    }
}

function getRecentMatches(matches, teamId, limit) {
    const teamMatches = matches.filter(m =>
        (m.home_team_id === teamId || m.away_team_id === teamId) &&
        m.status === 'FINISHED' && m.score_home != null
    );
    teamMatches.sort((a, b) => {
        if (a.utc_date < b.utc_date) return 1;
        if (a.utc_date > b.utc_date) return -1;
        return 0;
    });

    return teamMatches.slice(0, limit).map(m => {
        const isHome = m.home_team_id === teamId;
        const gf = isHome ? m.score_home : m.score_away;
        const ga = isHome ? m.score_away : m.score_home;
        const opponent = isHome ? getTeamShortDisplay(m.away_team_id) : getTeamShortDisplay(m.home_team_id);
        return {
            date: m.utc_date ? m.utc_date.slice(5, 10) : '',
            opponent,
            isHome,
            gf, ga,
            result: gf > ga ? 'W' : (gf < ga ? 'L' : 'D'),
        };
    });
}

function getHeadToHead(matches, teamA, teamB, limit) {
    const h2h = matches.filter(m =>
        ((m.home_team_id === teamA && m.away_team_id === teamB) ||
         (m.home_team_id === teamB && m.away_team_id === teamA)) &&
        m.status === 'FINISHED' && m.score_home != null
    );
    h2h.sort((a, b) => {
        if (a.utc_date < b.utc_date) return 1;
        if (a.utc_date > b.utc_date) return -1;
        return 0;
    });
    return h2h.slice(0, limit).map(m => {
        const homeName = getTeamShortDisplay(m.home_team_id);
        const awayName = getTeamShortDisplay(m.away_team_id);
        return {
            date: m.utc_date ? m.utc_date.slice(5, 10) : '',
            homeName,
            awayName,
            homeScore: m.score_home,
            awayScore: m.score_away,
        };
    });
}

// ====== 结果渲染 ======
function renderResult(r) {
    const c = document.getElementById('resultContent');
    if (!c) return;

    let html = '';

    // 结果头部
    html += `<div class="card result-header">
        <div class="match-teams">${r.homeTeam} vs ${r.awayTeam}</div>
        <div class="match-meta">${r.leagueName || ''}</div>
        <div class="predicted-score">${r.predictedHomeScore} - ${r.predictedAwayScore}</div>
        <div>最可能比分</div>
    </div>`;

    // 置信度
    const confColor = r.confidence >= 70 ? 'var(--accent)' : (r.confidence >= 50 ? 'var(--warning)' : 'var(--danger)');
    html += `<div class="card">
        <div class="metric-row">
            <span class="label">置信度</span>
            <span class="value" style="color:${confColor}">${r.confidence}%</span>
        </div>
        <div class="confidence-bar">
            <div class="confidence-fill" style="width:${r.confidence}%;background:${confColor}"></div>
        </div>
        <div class="metric-row">
            <span class="label">预测结果</span>
            <span class="value">${r.predictedOutcome === 'HOME' ? '🏠 主胜' : r.predictedOutcome === 'AWAY' ? '✈️ 客胜' : '🤝 平局'}</span>
        </div>
        <div class="metric-row">
            <span class="label">联赛场均总进球</span>
            <span class="value">${r.leagueAvg}</span>
        </div>
    </div>`;

    // 期望进球
    html += `<div class="card">
        <div class="card-title">🎯 期望进球（λ）</div>
        <div class="metric-row">
            <span class="label">${r.homeTeamShort}</span>
            <span class="value">${r.poissonResult.homeXg}</span>
        </div>
        <div class="metric-row">
            <span class="label">${r.awayTeamShort}</span>
            <span class="value">${r.poissonResult.awayXg}</span>
        </div>
    </div>`;

    // 概率预测
    const outcomes = [
        { label: '主胜', prob: r.homeWinProb, color: '#1a73e8' },
        { label: '平局', prob: r.drawProb, color: '#fbbc05' },
        { label: '客胜', prob: r.awayWinProb, color: '#ea4335' },
    ];
    html += `<div class="card">
        <div class="card-title">📈 概率预测</div>
        <div class="prob-grid">`;
    for (const o of outcomes) {
        html += `<div class="prob-cell">
            <div class="pct" style="color:${o.color}">${(o.prob * 100).toFixed(1)}%</div>
            <div class="label">${o.label}</div>
        </div>`;
    }
    for (const o of outcomes) {
        html += `<div class="prob-bar-bg">
            <div class="prob-bar-fill" style="width:${Math.max(o.prob * 100, 2)}%;background:${o.color}">${(o.prob * 100).toFixed(1)}%</div>
        </div>`;
    }
    html += `</div>`;

    // 总进球
    const totalGoalsProb = r.poissonResult.scoreProbabilities
        .reduce((s, sp) => s + sp.probability * (sp.home + sp.away), 0);
    html += `<div class="metric-row">
            <span class="label">预期总进球</span>
            <span class="value">${totalGoalsProb.toFixed(2)}</span>
        </div>`;

    // 大球/小球
    let over25 = 0, under25 = 0;
    for (const sp of r.poissonResult.scoreProbabilities) {
        if (sp.home + sp.away >= 3) over25 += sp.probability;
        else if (sp.home + sp.away <= 1) under25 += sp.probability;
    }
    // More precise: sum all probs
    over25 = 0; under25 = 0;
    for (let h = 0; h <= 10; h++) {
        for (let a = 0; a <= 10; a++) {
            const p = poissonPMF(h, r.poissonResult.homeXg) * poissonPMF(a, r.poissonResult.awayXg);
            if (h + a >= 3) over25 += p;
            else if (h + a <= 2) under25 += p;
        }
    }
    const totalP = over25 + under25;
    if (totalP > 0) { over25 /= totalP; under25 /= totalP; }
    html += `<div class="metric-row">
            <span class="label">大球（≥3）</span>
            <span class="value">${(over25 * 100).toFixed(1)}%</span>
        </div>
        <div class="metric-row">
            <span class="label">小球（≤2）</span>
            <span class="value">${(under25 * 100).toFixed(1)}%</span>
        </div>`;

    // 模型对比
    html += `<div class="card" style="margin-top:0">
        <div class="card-title">🧠 模型细节</div>
        <div class="metric-row">
            <span class="label">Poisson 权重</span>
            <span class="value">${(r.modelWeights.poisson * 100).toFixed(0)}%</span>
        </div>
        <div class="metric-row">
            <span class="label">Elo 权重</span>
            <span class="value">${(r.modelWeights.elo * 100).toFixed(0)}%</span>
        </div>
        <div class="metric-row">
            <span class="label">Poisson 主胜</span>
            <span class="value">${(r.poissonResult.homeWinProb * 100).toFixed(1)}%</span>
        </div>
        <div class="metric-row">
            <span class="label">Elo 主胜</span>
            <span class="value">${(r.eloResult.homeWinProb * 100).toFixed(1)}%</span>
        </div>
    </div>`;

    // 赔率与价值
    if (r.odds) {
        html += `<div class="card">
            <div class="card-title">🏦 赔率与价值</div>`;
        const oddsItems = [
            { label: '主胜', odds: r.odds.home, prob: r.homeWinProb },
            { label: '平局', odds: r.odds.draw, prob: r.drawProb },
            { label: '客胜', odds: r.odds.away, prob: r.awayWinProb },
        ];
        for (const item of oddsItems) {
            const implied = OddsUtils.impliedProb(item.odds);
            const value = OddsUtils.valueRatio(item.prob, implied);
            const kelly = OddsUtils.kellyFraction(item.odds - 1, item.prob);
            const ev = OddsUtils.expectedValue(item.odds, item.prob);

            let valueTag = '';
            if (value > 1.1) valueTag = '<span class="value-badge value-strong">✅ 高价值</span>';
            else if (value > 1.05) valueTag = '<span class="value-badge value-good">有价</span>';
            else valueTag = '<span class="value-badge value-bad">❌</span>';

            html += `<div class="metric-row">
                <span class="label">${item.label} @ ${item.odds.toFixed(2)}</span>
                <span class="value">${valueTag} 模型${(item.prob * 100).toFixed(1)}% / 隐含${(implied * 100).toFixed(1)}%</span>
            </div>`;
            if (kelly > 0) {
                html += `<div class="metric-row" style="border:none">
                    <span class="label">凯利</span>
                    <span class="value" style="color:var(--accent)">${(kelly * 100).toFixed(2)}% 可投</span>
                </div>`;
            }
        }
        if (r.odds.time) {
            html += `<div class="info-box">🕐 赔率获取于 ${r.odds.time.slice(0, 19)}</div>`;
        }
        html += `</div>`;
    }

    // Top 5 比分概率
    html += `<div class="card">
        <div class="card-title">📊 最可能比分</div>
        <div class="score-matrix">
            <table>
                <tr><th>排名</th><th>主队</th><th>客队</th><th>概率</th></tr>`;
    for (let i = 0; i < Math.min(r.poissonResult.scoreProbabilities.length, 5); i++) {
        const sp = r.poissonResult.scoreProbabilities[i];
        html += `<tr>
            <td>#${i + 1}</td>
            <td><strong>${sp.home}</strong></td>
            <td><strong>${sp.away}</strong></td>
            <td><strong>${(sp.probability * 100).toFixed(1)}%</strong></td>
        </tr>`;
    }
    html += `</table></div></div>`;

    // 近期战绩
    if (r.homeRecent && r.homeRecent.length > 0) {
        html += `<div class="card">
            <div class="card-title">🏠 ${r.homeTeamShort} 近5场</div>
            <ul class="recent-list">`;
        for (const m of r.homeRecent) {
            const cls = m.result === 'W' ? 'score-w' : (m.result === 'L' ? 'score-l' : 'score-d');
            const label = m.result === 'W' ? '胜' : (m.result === 'L' ? '负' : '平');
            html += `<li>
                <span class="date">${m.date}</span>
                <span class="opponent">${m.isHome ? '' : '✈️'} ${m.opponent}</span>
                <span class="score ${cls}">${m.gf}-${m.ga} ${label}</span>
            </li>`;
        }
        html += `</ul></div>`;
    }

    if (r.awayRecent && r.awayRecent.length > 0) {
        html += `<div class="card">
            <div class="card-title">✈️ ${r.awayTeamShort} 近5场</div>
            <ul class="recent-list">`;
        for (const m of r.awayRecent) {
            const cls = m.result === 'W' ? 'score-w' : (m.result === 'L' ? 'score-l' : 'score-d');
            const label = m.result === 'W' ? '胜' : (m.result === 'L' ? '负' : '平');
            html += `<li>
                <span class="date">${m.date}</span>
                <span class="opponent">${m.isHome ? '' : '✈️'} ${m.opponent}</span>
                <span class="score ${cls}">${m.gf}-${m.ga} ${label}</span>
            </li>`;
        }
        html += `</ul></div>`;
    }

    // 历史交锋
    if (r.h2h && r.h2h.length > 0) {
        html += `<div class="card">
            <div class="card-title">⚔️ 历史交锋</div>`;
        for (const m of r.h2h) {
            html += `<div class="h2h-row">
                <span class="h2h-home">${m.homeName}</span>
                <span class="h2h-score">${m.homeScore}-${m.awayScore}</span>
                <span class="h2h-away">${m.awayName}</span>
            </div>`;
        }
        html += `<div style="text-align:right"><small>${r.h2h.length} 场交锋</small></div>`;
        html += `</div>`;
    }

    c.innerHTML = html;
}

// ==============================
// 积分榜
// ==============================
function initStandingsPage() {
    renderLeagueGrid('stdLeagueGrid', async (leagueId) => {
        document.getElementById('standingsLeagueSelect').style.display = 'none';
        document.getElementById('standingsContent').style.display = 'block';

        const league = state.leagues.find(l => l.id === leagueId);
        document.getElementById('stdLeagueTitle').textContent = `📊 ${league ? league.name : ''} 积分榜`;

        // 加载比赛数据
        const container = document.getElementById('standingsTableWrap');
        container.innerHTML = '<div class="loading"><div class="spinner"></div><span>加载中...</span></div>';

        try {
            const matches = await loadMatches(leagueId);
            const standings = calcStandings(matches);
            renderStandingsTable(standings);
        } catch (e) {
            container.innerHTML = `<div class="error-box">加载失败: ${e.message}</div>`;
        }
    });
}

function backToStdLeagueSelect() {
    document.getElementById('standingsLeagueSelect').style.display = 'block';
    document.getElementById('standingsContent').style.display = 'none';
}

function renderStandingsTable(standings) {
    const container = document.getElementById('standingsTableWrap');
    if (!container) return;

    if (standings.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无比赛数据</div></div>';
        return;
    }

    let html = `<table class="standings-table">
        <thead><tr>
            <th>#</th><th>球队</th><th>赛</th><th>胜</th><th>平</th><th>负</th>
            <th>进</th><th>失</th><th>净</th><th>积分</th>
        </tr></thead><tbody>`;

    for (const s of standings) {
        const posClass = s.position <= 3 ? 'pos-' + s.position : '';
        const name = getTeamDisplayName(s.teamId);
        html += `<tr class="${posClass}">
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

    html += `</tbody></table>`;
    container.innerHTML = html;
}

// ==============================
// 球队分析
// ==============================
function initTeamsPage() {
    const leagueSelect = document.getElementById('teamLeagueSelect');
    leagueSelect.innerHTML = '<option value="">-- 选择联赛 --</option>';
    for (const league of state.leagues) {
        const opt = document.createElement('option');
        opt.value = league.id;
        opt.textContent = `${league.abbr || league.name} - ${league.name}`;
        leagueSelect.appendChild(opt);
    }
}

async function onTeamLeagueChange() {
    const leagueId = parseInt(document.getElementById('teamLeagueSelect').value);
    const teamSelect = document.getElementById('teamSelect');
    const btn = document.getElementById('teamAnalyzeBtn');

    teamSelect.innerHTML = '<option value="">-- 加载中... --</option>';
    btn.disabled = true;
    document.getElementById('teamResult').style.display = 'none';

    if (!leagueId) {
        teamSelect.innerHTML = '<option value="">-- 请选择联赛 --</option>';
        return;
    }

    try {
        const matches = await loadMatches(leagueId);

        // 收集球队
        const teamIds = new Set();
        for (const m of matches) {
            teamIds.add(m.home_team_id);
            teamIds.add(m.away_team_id);
        }

        const teams = [];
        for (const tid of teamIds) {
            const t = state.teamsById[tid];
            if (t) teams.push(t);
        }
        teams.sort((a, b) => a.n.localeCompare(b.n, 'zh'));

        teamSelect.innerHTML = '<option value="">-- 请选择球队 --</option>';
        for (const t of teams) {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = getTeamDisplayName(t.id);
            teamSelect.appendChild(opt);
        }

        // 缓存比赛数据
        state._teamPageMatches = matches;
        state._teamPageLeagueId = leagueId;
    } catch (e) {
        teamSelect.innerHTML = '<option value="">加载失败: ' + e.message + '</option>';
    }
}

function onTeamSelectChange() {
    const teamId = parseInt(document.getElementById('teamSelect').value);
    document.getElementById('teamAnalyzeBtn').disabled = !teamId;
    document.getElementById('teamResult').style.display = 'none';
}

async function analyzeTeam() {
    const teamId = parseInt(document.getElementById('teamSelect').value);
    const matches = state._teamPageMatches;
    const leagueId = state._teamPageLeagueId;

    if (!teamId || !matches) return;

    const team = state.teamsById[teamId];
    if (!team) return;

    const container = document.getElementById('teamResult');
    container.style.display = 'block';
    container.innerHTML = '<div class="loading"><div class="spinner"></div><span>计算中...</span></div>';

    // 小延迟
    await new Promise(r => setTimeout(r, 50));

    // 球队近期比赛
    const recent = getRecentMatches(matches, teamId, 10);

    // 统计
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

    // 最近状态条
    const formStr = recent.slice(0, 5).map(m => m.result).join(' ');

    // 频率分布（该队比赛的总进球数分布）
    const goalDist = {};
    for (const m of [...homeMatches, ...awayMatches]) {
        const isHome = m.home_team_id === teamId;
        const gf = isHome ? m.score_home : m.score_away;
        goalDist[gf] = (goalDist[gf] || 0) + 1;
    }

    let html = '';

    // 基本信息
    const league = state.leagues.find(l => l.id === leagueId);
    html += `<div class="card">
        <div class="card-title">${getTeamDisplayName(teamId)}</div>
        <div class="metric-row">
            <span class="label">联赛</span>
            <span class="value">${league ? league.name : ''}</span>
        </div>
        <div class="metric-row">
            <span class="label">Elo 评分</span>
            <span class="value" style="font-size:1.2rem">${Math.round(team.elo)}</span>
        </div>
        <div class="metric-row">
            <span class="label">近期状态</span>
            <span class="value">${formStr || '暂无数据'}</span>
        </div>
    </div>`;

    // 主客场统计
    html += `<div class="card">
        <div class="card-title">📊 数据统计</div>
        <table class="standings-table">
            <tr><th></th><th>赛</th><th>胜</th><th>平</th><th>负</th><th>进</th><th>失</th><th>净</th></tr>
            <tr>
                <td class="team-name">🏠 主场</td>
                <td>${homeStats.played}</td>
                <td>${homeStats.won}</td>
                <td>${homeStats.drawn}</td>
                <td>${homeStats.lost}</td>
                <td>${homeStats.gf}</td>
                <td>${homeStats.ga}</td>
                <td>${homeStats.gf - homeStats.ga}</td>
            </tr>
            <tr>
                <td class="team-name">✈️ 客场</td>
                <td>${awayStats.played}</td>
                <td>${awayStats.won}</td>
                <td>${awayStats.drawn}</td>
                <td>${awayStats.lost}</td>
                <td>${awayStats.gf}</td>
                <td>${awayStats.ga}</td>
                <td>${awayStats.gf - awayStats.ga}</td>
            </tr>
            <tr style="font-weight:700">
                <td class="team-name">合计</td>
                <td>${homeStats.played + awayStats.played}</td>
                <td>${homeStats.won + awayStats.won}</td>
                <td>${homeStats.drawn + awayStats.drawn}</td>
                <td>${homeStats.lost + awayStats.lost}</td>
                <td>${homeStats.gf + awayStats.gf}</td>
                <td>${homeStats.ga + awayStats.ga}</td>
                <td>${(homeStats.gf + awayStats.gf) - (homeStats.ga + awayStats.ga)}</td>
            </tr>
        </table>
    </div>`;

    // 近期比赛详细
    if (recent.length > 0) {
        html += `<div class="card">
            <div class="card-title">📋 近期比赛</div>
            <ul class="recent-list">`;
        for (const m of recent) {
            const cls = m.result === 'W' ? 'score-w' : (m.result === 'L' ? 'score-l' : 'score-d');
            const label = m.result === 'W' ? '胜' : (m.result === 'L' ? '负' : '平');
            html += `<li>
                <span class="date">${m.date}</span>
                <span class="opponent">${m.isHome ? '主场' : '客场'} vs ${m.opponent}</span>
                <span class="score ${cls}">${m.gf}-${m.ga} ${label}</span>
            </li>`;
        }
        html += `</ul></div>`;
    }

    // 进球分布
    const goalKeys = Object.keys(goalDist).sort((a, b) => a - b);
    if (goalKeys.length > 0) {
        html += `<div class="card">
            <div class="card-title">🎯 单场进球分布</div>`;
        const totalGames = Object.values(goalDist).reduce((s, v) => s + v, 0);
        for (const g of goalKeys) {
            const pct = (goalDist[g] / totalGames * 100);
            html += `<div class="metric-row">
                <span class="label">${g} 球</span>
                <span class="value">${goalDist[g]} 场 (${pct.toFixed(1)}%)</span>
            </div>`;
        }
        html += `</div>`;
    }

    container.innerHTML = html;
}

// ==============================
// UI 工具函数
// ==============================
function $(id) { return document.getElementById(id); }
function show(id) { const el = $(id); if (el) el.style.display = 'block'; }
function hide(id) { const el = $(id); if (el) el.style.display = 'none'; }

function showLoading(text) {
    const el = document.getElementById('predLoading');
    if (el) {
        el.style.display = 'flex';
        const textEl = document.getElementById('predLoadingText');
        if (textEl) textEl.textContent = text || '加载中...';
    }
}

function hideLoading() {
    const el = document.getElementById('predLoading');
    if (el) el.style.display = 'none';
}

function showToast(msg, type) {
    const container = document.getElementById('resultContent');
    if (!container) return;

    const typeMap = {
        success: 'success-box',
        error: 'error-box',
        warning: 'warn-box',
        info: 'info-box',
    };
    const cls = typeMap[type] || 'info-box';
    container.innerHTML = `<div class="${cls}">${msg}</div>`;
}

// ==============================
// 初始化
// ==============================
async function init() {
    try {
        // 加载基础数据
        await Promise.all([
            loadLeagues(),
            loadTeams(),
            loadTeamNames(),
        ]);

        // 首页
        initHomePage();

        // 预分析步骤1
        show('predStep1');
        renderLeagueGrid('predLeagueGrid', async (leagueId) => {
            state.predLeagueId = leagueId;
            showLoading('正在加载比赛数据...');
            try {
                state.currentMatches = await loadMatches(leagueId);
                show('predStep2');
                hide('predStep1');
                hide('predStep3');
                hide('predResult');
                populateTeamSelects(leagueId);
            } catch (e) {
                showToast('数据加载失败: ' + e.message, 'error');
            } finally {
                hideLoading();
            }
        });

        // 积分榜
        initStandingsPage();

        // 球队分析
        initTeamsPage();

    } catch (e) {
        console.error('初始化失败:', e);
        document.body.innerHTML = `<div class="error-box" style="margin:2rem;padding:2rem;text-align:center">
            <h3>❌ 初始化失败</h3>
            <p>${e.message}</p>
            <button class="btn btn-primary" onclick="location.reload()" style="margin-top:1rem">重新加载</button>
        </div>`;
    }
}

// ==============================
// 启动
// ==============================
document.addEventListener('DOMContentLoaded', init);

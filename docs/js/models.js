/**
 * ⚽ 足彩预测模型 — Poisson 分布 + Elo 评分 + 融合模型
 *
 * 纯 JavaScript 实现，浏览器端运行
 * 移植自 Python backend/models/* + backend/services/prediction_service.py
 */

// ==============================
// 1. 工具函数
// ==============================
function factorial(n) {
    if (n <= 1) return 1;
    let r = 1;
    for (let i = 2; i <= n; i++) r *= i;
    return r;
}

function poissonPMF(k, lambda) {
    if (lambda < 0 || k < 0) return 0;
    return Math.pow(lambda, k) * Math.exp(-lambda) / factorial(k);
}

// ==============================
// 2. Poisson 预测器（含 Dixon-Coles 校正）
// ==============================
class PoissonPredictor {
    /**
     * @param {Object} options
     * @param {number} options.recentMatches - 考虑近期场次数 (default: 5)
     * @param {number} options.rho - Dixon-Coles ρ 参数 (default: 0.15)
     * @param {number} options.leagueAvgGoals - 联赛场均总进球 (default: 2.5)
     */
    constructor(options = {}) {
        this.recentMatches = options.recentMatches || 5;
        this.rho = options.rho != null ? options.rho : 0.15;
        this.leagueAvgGoals = options.leagueAvgGoals || 2.5;
    }

    /**
     * 计算球队加权场均进球/失球
     * @param {Array} matches - 球队参与的比赛（已过滤）
     * @param {number} teamId - 球队 ID
     * @param {string|null} venue - 'home' | 'away' | null
     * @returns {{ scored: number, conceded: number }}
     */
    calcTeamWeightedGoals(matches, teamId, venue = null) {
        let filtered = matches;
        if (venue === 'home') {
            filtered = matches.filter(m => m.home_team_id === teamId);
        } else if (venue === 'away') {
            filtered = matches.filter(m => m.away_team_id === teamId);
        }

        // 取最近 N 场，按时间降序
        const sorted = [...filtered].sort((a, b) => {
            if (a.utc_date < b.utc_date) return 1;
            if (a.utc_date > b.utc_date) return -1;
            return 0;
        }).slice(0, this.recentMatches);

        if (sorted.length === 0) return { scored: 1.2, conceded: 1.2 };

        // 指数衰减权重（半衰期=5场）
        const halfLife = 5.0;
        const decay = Math.log(2) / halfLife;

        let totalWeightScored = 0;
        let totalWeightConceded = 0;
        let totalWeight = 0;

        for (let i = 0; i < sorted.length; i++) {
            const m = sorted[i];
            const weight = Math.exp(-decay * i);
            if (m.home_team_id === teamId) {
                totalWeightScored += weight * (m.score_home || 0);
                totalWeightConceded += weight * (m.score_away || 0);
            } else {
                totalWeightScored += weight * (m.score_away || 0);
                totalWeightConceded += weight * (m.score_home || 0);
            }
            totalWeight += weight;
        }

        if (totalWeight === 0) return { scored: 1.2, conceded: 1.2 };

        return {
            scored: totalWeightScored / totalWeight,
            conceded: totalWeightConceded / totalWeight,
        };
    }

    /**
     * 计算联赛场均进球
     * @param {Array} matches - 所有比赛
     * @returns {number}
     */
    static calcLeagueAvgGoals(matches) {
        const finished = matches.filter(m => m.status === 'FINISHED' && m.score_home != null);
        if (finished.length === 0) return 2.5;
        const total = finished.reduce((s, m) => s + m.score_home + m.score_away, 0);
        return total / finished.length;
    }

    /**
     * Dixon-Coles 校正
     */
    dixonColesAdjust(scoreProbs, homeXg, awayXg) {
        const rho = this.rho;
        const adjusted = {};

        for (const [key, prob] of Object.entries(scoreProbs)) {
            const [h, a] = key.split('-').map(Number);
            let tau = 1.0;

            if (h <= 2 && a <= 2) {
                if (h === 0 && a === 0) {
                    tau = 1.0 - homeXg * awayXg * rho;
                } else if (h === 0 && a === 1) {
                    tau = 1.0 + homeXg * rho;
                } else if (h === 1 && a === 0) {
                    tau = 1.0 + awayXg * rho;
                } else if (h === 1 && a === 1) {
                    tau = 1.0 - rho;
                } else if (h === 0 && a === 2) {
                    tau = 1.0 - 0.5 * homeXg * rho;
                } else if (h === 2 && a === 0) {
                    tau = 1.0 - 0.5 * awayXg * rho;
                } else if (h === 2 && a === 1) {
                    tau = 1.0 + 0.5 * rho;
                } else if (h === 1 && a === 2) {
                    tau = 1.0 + 0.5 * rho;
                }
                tau = Math.max(tau, 0.01);
            }

            adjusted[key] = prob * tau;
        }

        return adjusted;
    }

    /**
     * 预测一场比赛
     * @param {number} homeTeamId - 主队 ID
     * @param {number} awayTeamId - 客队 ID
     * @param {Array} allMatches - 联赛所有比赛
     * @param {Object} [options]
     * @param {number} [options.leagueAvg] - 联赛场均进球
     * @param {number} [options.rho] - Dixon-Coles ρ
     * @returns {Object} 预测结果
     */
    predictMatch(homeTeamId, awayTeamId, allMatches, options = {}) {
        const leagueAvg = options.leagueAvg || this.leagueAvgGoals;
        const rho = options.rho != null ? options.rho : this.rho;
        this.rho = rho;

        // 筛选主客队比赛（按主客场）
        const homeMatches = allMatches.filter(m =>
            m.home_team_id === homeTeamId || m.away_team_id === homeTeamId
        );
        const awayMatches = allMatches.filter(m =>
            m.home_team_id === awayTeamId || m.away_team_id === awayTeamId
        );

        // 主队只看其主场表现，客队只看其客场表现
        const homeStats = this.calcTeamWeightedGoals(homeMatches, homeTeamId, 'home');
        const awayStats = this.calcTeamWeightedGoals(awayMatches, awayTeamId, 'away');

        // 计算攻击/防守系数
        const homeAttackStr = leagueAvg > 0 ? homeStats.scored / leagueAvg : 1.0;
        const awayDefenseStr = leagueAvg > 0 ? awayStats.conceded / leagueAvg : 1.0;
        const awayAttackStr = leagueAvg > 0 ? awayStats.scored / leagueAvg : 1.0;
        const homeDefenseStr = leagueAvg > 0 ? awayStats.conceded / leagueAvg : 1.0;

        // 预期进球
        let homeXg = leagueAvg * homeAttackStr * awayDefenseStr;
        let awayXg = leagueAvg * awayAttackStr * homeDefenseStr;

        // 防止极端值
        homeXg = Math.max(0.3, Math.min(homeXg, 5.0));
        awayXg = Math.max(0.3, Math.min(awayXg, 5.0));

        // Poisson 分布计算比分概率
        const maxGoals = 10;
        const rawProbs = {};

        for (let h = 0; h <= maxGoals; h++) {
            for (let a = 0; a <= maxGoals; a++) {
                const prob = poissonPMF(h, homeXg) * poissonPMF(a, awayXg);
                if (prob > 0.0005) {
                    rawProbs[`${h}-${a}`] = prob;
                }
            }
        }

        // Dixon-Coles 校正
        const adjustedProbs = this.dixonColesAdjust(rawProbs, homeXg, awayXg);

        // 归一化
        let totalProb = 0;
        for (const p of Object.values(adjustedProbs)) totalProb += p;

        if (totalProb > 0) {
            for (const key of Object.keys(adjustedProbs)) {
                adjustedProbs[key] /= totalProb;
            }
        }

        // 胜平负概率
        let homeWinProb = 0, drawProb = 0, awayWinProb = 0;
        let bestScore = '0-0', bestProb = 0;

        for (const [key, p] of Object.entries(adjustedProbs)) {
            const [h, a] = key.split('-').map(Number);
            if (h > a) homeWinProb += p;
            else if (h === a) drawProb += p;
            else awayWinProb += p;
            if (p > bestProb) { bestProb = p; bestScore = key; }
        }

        // Top 10 比分
        const sortedScores = Object.entries(adjustedProbs)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([key, p]) => {
                const [h, a] = key.split('-').map(Number);
                return { home: h, away: a, probability: Math.round(p * 10000) / 10000 };
            });

        const [predH, predA] = bestScore.split('-').map(Number);

        return {
            homeWinProb: Math.round(homeWinProb * 10000) / 10000,
            drawProb: Math.round(drawProb * 10000) / 10000,
            awayWinProb: Math.round(awayWinProb * 10000) / 10000,
            predictedHomeScore: predH,
            predictedAwayScore: predA,
            homeXg: Math.round(homeXg * 100) / 100,
            awayXg: Math.round(awayXg * 100) / 100,
            scoreProbabilities: sortedScores,
            model: 'poisson_v2',
            // 附加数据用于展示
            homeStats: {
                scored: Math.round(homeStats.scored * 100) / 100,
                conceded: Math.round(homeStats.conceded * 100) / 100,
                attackStr: Math.round(homeAttackStr * 1000) / 1000,
                defenseStr: Math.round(homeDefenseStr * 1000) / 1000,
            },
            awayStats: {
                scored: Math.round(awayStats.scored * 100) / 100,
                conceded: Math.round(awayStats.conceded * 100) / 100,
                attackStr: Math.round(awayAttackStr * 1000) / 1000,
                defenseStr: Math.round(awayDefenseStr * 1000) / 1000,
            },
        };
    }
}

// ==============================
// 3. Elo 评分系统
// ==============================
class EloRating {
    constructor(options = {}) {
        this.kFactor = options.kFactor || 32;
        this.homeAdvantage = options.homeAdvantage || 100;
        this.initialRating = options.initialRating || 1500;
    }

    expectedScore(ratingA, ratingB) {
        return 1.0 / (1.0 + Math.pow(10, (ratingB - ratingA) / 400.0));
    }

    /**
     * 更新 Elo 评分
     * @returns {{ newHome: number, newAway: number }}
     */
    updateRatings(homeRating, awayRating, homeScore, awayScore) {
        const homeEffective = homeRating + this.homeAdvantage;

        const expectedHome = this.expectedScore(homeEffective, awayRating);
        const expectedAway = 1.0 - expectedHome;

        // 实际结果
        let actualHome, actualAway;
        if (homeScore > awayScore) { actualHome = 1.0; actualAway = 0.0; }
        else if (homeScore < awayScore) { actualHome = 0.0; actualAway = 1.0; }
        else { actualHome = 0.5; actualAway = 0.5; }

        // 大比分调整
        const goalDiff = Math.abs(homeScore - awayScore);
        let goalFactor = 1.0;
        if (goalDiff >= 3) goalFactor = 1.5;
        else if (goalDiff >= 2) goalFactor = 1.25;

        const newHome = homeRating + this.kFactor * goalFactor * (actualHome - expectedHome);
        const newAway = awayRating + this.kFactor * goalFactor * (actualAway - expectedAway);

        return { newHome, newAway };
    }

    /**
     * 基于 Elo 预测比赛概率
     * @param {number} homeRating
     * @param {number} awayRating
     * @returns {{ homeWinProb: number, drawProb: number, awayWinProb: number }}
     */
    predictMatchProbs(homeRating, awayRating) {
        const homeEffective = homeRating + this.homeAdvantage;
        const expectedHome = this.expectedScore(homeEffective, awayRating);
        const expectedAway = 1.0 - expectedHome;

        const ratingDiff = Math.abs(homeEffective - awayRating);
        const drawBase = 0.34 * Math.exp(-ratingDiff / 400.0);

        let homeWin = expectedHome * (1.0 - drawBase) + drawBase * 0.5;
        let awayWin = expectedAway * (1.0 - drawBase) + drawBase * 0.5;
        const drawProb = drawBase;

        const total = homeWin + drawProb + awayWin;
        return {
            homeWinProb: Math.round((homeWin / total) * 10000) / 10000,
            drawProb: Math.round((drawProb / total) * 10000) / 10000,
            awayWinProb: Math.round((awayWin / total) * 10000) / 10000,
        };
    }

    /**
     * 批量计算所有球队 Elo 评分
     * @param {Array} matches - 所有比赛（需按时间升序）
     * @param {Object} initialRatings - { teamId: rating }
     * @returns {Object} { teamId: rating }
     */
    recalculateAll(matches, initialRatings = {}) {
        const ratings = { ...initialRatings };
        const finished = matches
            .filter(m => m.status === 'FINISHED' && m.score_home != null && m.score_away != null)
            .sort((a, b) => {
                if (a.utc_date < b.utc_date) return -1;
                if (a.utc_date > b.utc_date) return 1;
                return 0;
            });

        for (const m of finished) {
            const hRating = ratings[m.home_team_id] || this.initialRating;
            const aRating = ratings[m.away_team_id] || this.initialRating;

            const { newHome, newAway } = this.updateRatings(
                hRating, aRating,
                m.score_home, m.score_away
            );
            ratings[m.home_team_id] = newHome;
            ratings[m.away_team_id] = newAway;
        }

        return ratings;
    }
}

// ==============================
// 4. 融合预测服务 (Poisson + Elo)
// ==============================
class PredictionService {
    /**
     * @param {Object} options
     * @param {Object} options.leagueParams - 联赛参数 { [leagueId]: { eloHomeAdv, dixonColesRho, poissonWeight } }
     * @param {number} options.defaultEloHomeAdv - 默认主场优势
     * @param {number} options.defaultRho - 默认 Dixon-Coles ρ
     * @param {number} options.defaultPoissonWeight - 默认 Poisson 权重
     */
    constructor(options = {}) {
        this.leagueParams = options.leagueParams || {};
        this.defaultEloHomeAdv = options.defaultEloHomeAdv || 100;
        this.defaultRho = options.defaultRho || 0.15;
        this.defaultPoissonWeight = options.defaultPoissonWeight || 0.55;
    }

    _getLeagueParams(leagueId) {
        return this.leagueParams[leagueId] || {};
    }

    /**
     * 综合预测
     * @param {Object} data
     * @param {number} data.homeTeamId
     * @param {number} data.awayTeamId
     * @param {number} data.homeElo
     * @param {number} data.awayElo
     * @param {number} data.leagueId
     * @param {Array} data.matches - 该联赛所有比赛
     * @param {number} [data.leagueAvg] - 联赛场均进球
     * @returns {Object} 预测结果
     */
    predict(data) {
        const lp = this._getLeagueParams(data.leagueId);
        const eloHfa = lp.eloHomeAdv || this.defaultEloHomeAdv;
        const rho = lp.dixonColesRho || this.defaultRho;
        const poissonWeight = lp.poissonWeight || this.defaultPoissonWeight;

        // Poisson 预测
        const leagueAvg = data.leagueAvg || PoissonPredictor.calcLeagueAvgGoals(data.matches);
        const poissonPred = new PoissonPredictor({ leagueAvgGoals: leagueAvg, rho });
        const poissonResult = poissonPred.predictMatch(
            data.homeTeamId, data.awayTeamId, data.matches, { leagueAvg, rho }
        );

        // Elo 预测
        const eloPred = new EloRating({ homeAdvantage: eloHfa });
        const eloResult = eloPred.predictMatchProbs(data.homeElo, data.awayElo);

        // 融合
        const eloWeight = 1.0 - poissonWeight;
        let homeWin = poissonResult.homeWinProb * poissonWeight + eloResult.homeWinProb * eloWeight;
        let draw = poissonResult.drawProb * poissonWeight + eloResult.drawProb * eloWeight;
        let awayWin = poissonResult.awayWinProb * poissonWeight + eloResult.awayWinProb * eloWeight;

        const total = homeWin + draw + awayWin;
        homeWin /= total;
        draw /= total;
        awayWin /= total;

        // 预测结果
        let predictedOutcome = 'DRAW';
        if (homeWin > draw && homeWin > awayWin) predictedOutcome = 'HOME';
        else if (awayWin > homeWin && awayWin > draw) predictedOutcome = 'AWAY';

        // 置信度
        const maxProb = Math.max(homeWin, draw, awayWin);
        const poissonOutcome = poissonResult.homeWinProb > poissonResult.drawProb && poissonResult.homeWinProb > poissonResult.awayWinProb ? 'HOME'
            : poissonResult.awayWinProb > poissonResult.homeWinProb && poissonResult.awayWinProb > poissonResult.drawProb ? 'AWAY'
            : 'DRAW';
        const eloOutcome = eloResult.homeWinProb > eloResult.drawProb && eloResult.homeWinProb > eloResult.awayWinProb ? 'HOME'
            : eloResult.awayWinProb > eloResult.homeWinProb && eloResult.awayWinProb > eloResult.drawProb ? 'AWAY'
            : 'DRAW';
        const modelAgreement = poissonOutcome === eloOutcome ? 1.0 : 0.5;
        const confidence = Math.min(95, Math.round((maxProb * 0.7 + modelAgreement * 0.3) * 100 * 10) / 10);

        return {
            homeWinProb: Math.round(homeWin * 10000) / 10000,
            drawProb: Math.round(draw * 10000) / 10000,
            awayWinProb: Math.round(awayWin * 10000) / 10000,
            predictedHomeScore: poissonResult.predictedHomeScore,
            predictedAwayScore: poissonResult.predictedAwayScore,
            predictedOutcome,
            confidence,
            poissonResult,
            eloResult,
            modelWeights: { poisson: poissonWeight, elo: eloWeight },
            leagueParams: { eloHomeAdv: eloHfa, dixonColesRho: rho, poissonWeight },
        };
    }
}

// ==============================
// 5. 赔率分析工具
// ==============================
const OddsUtils = {
    impliedProb(odds) { return odds > 0 ? 1 / odds : 0; },

    valueRatio(modelProb, impliedProb) {
        return impliedProb > 0 ? modelProb / impliedProb : 0;
    },

    kellyFraction(b, p, factor = 0.25) {
        const q = 1 - p;
        const f = b > 0 ? (b * p - q) / b : 0;
        return Math.max(0, Math.min(f, 1)) * factor;
    },

    expectedValue(odds, prob) {
        return odds * prob - 1;
    },
};

// ==============================
// 6. 积分榜计算
// ==============================
function calcStandings(matches) {
    const stats = {};
    const finished = matches.filter(m => m.status === 'FINISHED' && m.score_home != null);

    for (const m of finished) {
        for (const { teamId, teamName, gf, ga, isHome } of [
            { teamId: m.home_team_id, teamName: m.home_team_name, gf: m.score_home, ga: m.score_away, isHome: true },
            { teamId: m.away_team_id, teamName: m.away_team_name, gf: m.score_away, ga: m.score_home, isHome: false },
        ]) {
            if (!stats[teamId]) {
                stats[teamId] = { teamId, teamName: teamName || `Team ${teamId}`, played: 0, won: 0, drawn: 0, lost: 0, gf: 0, ga: 0, pts: 0 };
            }
            const s = stats[teamId];
            s.played++;
            s.gf += gf;
            s.ga += ga;
            if (gf > ga) { s.won++; s.pts += 3; }
            else if (gf < ga) s.lost++;
            else { s.drawn++; s.pts += 1; }
        }
    }

    return Object.values(stats).sort((a, b) => {
        if (b.pts !== a.pts) return b.pts - a.pts;
        const gdA = a.gf - a.ga, gdB = b.gf - b.ga;
        if (gdB !== gdA) return gdB - gdA;
        return b.gf - a.gf;
    }).map((s, i) => ({ ...s, position: i + 1, gd: s.gf - s.ga }));
}

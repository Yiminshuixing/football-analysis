# ⚽ 足彩分析系统

基于 **Poisson 分布** + **Elo 评分** 融合模型的足球比赛预测系统。覆盖英超、德甲、西甲、意甲、法甲五大联赛 + 中超 + 世界杯。

## 🌐 在线版本

**静态前端版**（可直接部署到 GitHub Pages）:
- 纯 HTML/CSS/JS，浏览器端运行
- 数据从本地 JSON 文件加载
- 所有计算（Poisson、Elo、融合模型）在浏览器中完成
- 移动端优化，PWA 支持

> 📁 静态版本位于 `docs/` 文件夹
> 
> 部署方式: GitHub → Settings → Pages → Source: `main` branch → `/docs` folder

在线 Demo: [https://yiminshuixing.github.io/football-analysis/](https://yiminshuixing.github.io/football-analysis/)（部署后可用）

## 📸 截图

> （待补充）

## ✨ 功能

- **🎯 比赛预测** — 输入主客队名称（中/英文）和博彩赔率，系统自动计算比分概率
- **📥 数据更新** — 自动从 Football-Data.co.uk 下载 CSV 导入，或手动上传文件
- **🧮 双模型融合** — Poisson 分布（进球率模型）+ Elo 评分（实力差模型），Dixon-Coles ρ 低分平局校正
- **💹 赔率分析** — 对比模型概率 vs 市场赔率，标注价值投注机会
- **📊 近期战绩** — 提取近5场主/客场成绩作为计算依据，清晰展示
- **📱 移动端适配** — 响应式布局，手机访问同样友好

## 🏗 技术栈

| 层 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| 前端框架 | Streamlit |
| 数据库 | SQLite (SQLAlchemy) |
| 预测模型 | Poisson 回归 + Elo 评分系统 |
| 数据源 | Football-Data.co.uk (免费 CSV) |

## 🚀 快速开始

### 本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/football-analysis.git
cd football-analysis

# 2. 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 一键启动
chmod +x start.sh
./start.sh
```

启动后访问:
- 前端页面: http://localhost:8501
- API 文档: http://localhost:8000/docs

### Docker 部署

```bash
docker build -t football-analysis .
docker run -p 8000:8000 -p 8501:8501 football-analysis
```

### Streamlit Cloud 部署

1. 将代码推送到 GitHub
2. 在 [Streamlit Community Cloud](https://streamlit.io/cloud) 选择该仓库
3. 部署配置:
   - 主文件: `app.py`
   - Python 版本: 3.11
   - 启动命令: `streamlit run app.py`
4. 后端需要单独部署到 Railway / Render 等服务

## 📁 项目结构

```
football-analysis/
├── app.py                       # Streamlit 主入口
├── backend/
│   ├── main.py                  # FastAPI 应用
│   ├── database.py              # 数据库模型
│   ├── routers/                 # API 路由
│   │   ├── matches.py           # 比赛数据
│   │   ├── predictions.py       # 预测接口
│   │   ├── teams.py             # 球队查询
│   │   └── backtest.py          # 回测
│   ├── models/                  # 预测模型
│   │   ├── poisson.py           # Poisson 分布
│   │   └── elo.py               # Elo 评分
│   └── services/                # 业务逻辑
│       └── prediction_service.py
├── frontend/
│   ├── pages/
│   │   ├── prediction.py        # 预测页面
│   │   └── data_update.py       # 数据更新页面
│   ├── utils.py                 # API 调用工具
│   └── team_names.py            # 中英球队名映射
├── data/                        # SQLite 数据库
├── requirements.txt
├── Dockerfile
└── start.sh
```

## 📖 使用说明

### 比赛预测

1. 主页点击 **🎯 开始预测**
2. 输入主队名称（中文或英文，如"曼城"或"Manchester City")
3. 输入客队名称
4. 填写从机构查询到的胜/平/负赔率
5. 点击 **🔮 开始预测**

结果页面包含：
- 比分预测 + 置信度
- 胜平负概率条
- Top 8 比分概率格子
- 近5场主/客场战绩
- 模型概率 vs 市场赔率对比
- 价值投注建议

### 数据更新

- **自动更新**: 从 Football-Data.co.uk 自动下载最新 CSV 并导入（显示每联赛新增/跳过明细）
- **手动上传**: 下载 CSV 文件后手动上传导入

## 📊 预测模型

### Poisson 模型
- 分别计算主队进攻力、防守力，客队进攻力、防守力
- 主场球队使用近5场主场数据，客场球队使用近5场客场数据
- 指数衰减权重（半衰期5场），近期比赛权重更高
- Dixon-Coles ρ 校正低比分平局概率

### Elo 模型
- 初始分 1500，K=32
- 考虑主客场优势（HFA）
- 净胜球加权（1球=1x，2球=1.5x，3+球=11/8x）

### 融合策略
- Poisson 和 Elo 按联赛特定权重融合
- 五大联赛各有独立参数（HFA、ρ、融合权重）

## 📄 数据来源

[Football-Data.co.uk](https://www.football-data.co.uk/data.php) 免费 CSV 数据，包含：

- 比赛结果和比分
- 博彩赔率（Bet365、威廉希尔等十余家公司）
- 统计数据（射门、控球率等，部分联赛）

## ⚖️ 免责声明

本系统仅供学习和研究使用，不构成任何投注建议。足球比赛结果受多种因素影响，预测模型无法保证准确率。

## 📜 许可证

MIT License

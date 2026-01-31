# Coauthor Tracking System

基于 OpenAlex 数据源的论文合作者关系追踪与分析系统。

## 功能特性

- **数据爬取**: 从 OpenAlex API 增量爬取论文和作者数据
- **作者去重**: 自动合并同姓名、同机构的作者记录
- **合作分析**: 使用 GraphSAGE 和加权算法计算作者关系强度
- **网络指标**: 机构内计算的网络中心性指标（度中心性、PageRank、中介中心性等）
- **机构排名**: 按机构展示作者论文数和引用排名
- **可视化**: 合作网络图谱可视化
- **API查询**: RESTful API 进行作者搜索和关系查询
- **Web前端**: React 前端界面，支持搜索、排名、网络图可视化
- **自动调度**: 支持定时自动爬取和分析更新

## 快速开始

### 1. 安装后端依赖

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置

复制配置文件并修改:

```bash
cp .env.example .env
```

主要配置项:
- `COAUTHOR_SCOPE__INSTITUTION_IDS`: 机构ID列表（在 [OpenAlex](https://openalex.org/) 搜索机构获取）
- `COAUTHOR_SCOPE__CONCEPT_IDS`: 学科领域ID列表
- `COAUTHOR_SCOPE__FROM_DATE`: 数据起始日期

### 3. 初始化数据库

```bash
python scripts/init_db.py
```

### 4. 运行爬虫

```bash
# 增量爬取(默认)
python scripts/run_crawl.py

# 完整爬取
python scripts/run_crawl.py --full

# 限制数量
python scripts/run_crawl.py --max=1000
```

### 5. 作者去重

```bash
python scripts/deduplicate_authors.py
```

### 6. 运行分析（可选）

```bash
python scripts/run_analysis.py
```

### 7. 启动后端 API 服务

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

API 文档: http://localhost:8000/api/docs

### 8. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端访问: http://localhost:3000

## 前端页面

| 页面 | 路径 | 功能 |
|------|------|------|
| 首页 | `/` | 系统统计概览、作者搜索 |
| 作者详情 | `/author/:id` | 作者信息、合作者列表、网络指标 |
| 机构排名 | `/ranking` | 按机构的作者论文/引用排名 |
| 合作网络 | `/network/:id` | 作者合作关系网络可视化 |

## API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/authors/search?q=` | 作者名称搜索 |
| GET | `/api/v1/authors/{id}` | 获取作者详情 |
| GET | `/api/v1/authors/{id}/top-relations` | Top-K 关系查询 |
| GET | `/api/v1/authors/{id}/network-metrics` | 网络中心性指标（机构内） |
| GET | `/api/v1/authors/{id}/collaborators` | 直接合作者列表 |
| GET | `/api/v1/authors/{id}/collaboration-graph` | 合作网络图数据 |
| GET | `/api/v1/authors/institution/{id}/ranking` | 机构内作者排名 |
| GET | `/api/v1/system/status` | 系统状态 |
| GET | `/api/v1/system/stats` | 详细统计 |
| POST | `/api/v1/system/crawl/trigger` | 触发爬取 |
| POST | `/api/v1/system/analysis/trigger` | 触发分析 |

## 使用示例

### 搜索作者

```bash
curl "http://localhost:8000/api/v1/authors/search?q=王明&limit=10"
```

### 获取 Top-20 关系

```bash
curl "http://localhost:8000/api/v1/authors/A1234567890/top-relations?k=20"
```

### 获取网络指标（机构内计算）

```bash
curl "http://localhost:8000/api/v1/authors/A1234567890/network-metrics"
```

返回示例:
```json
{
  "author_id": "A1234567890",
  "metrics": {
    "institution_name": "Peking University",
    "institution_author_count": 3500,
    "degree_centrality": 0.025,
    "pagerank": 0.0048,
    "betweenness_centrality": 0.039
  }
}
```

## 定时任务

启动调度器以自动执行任务:

```bash
python scripts/start_scheduler.py
```

默认调度:
- 每日 2:00 - 增量爬取
- 每周日 4:00 - GNN 分析

## 合作权重算法

```
Weight = BaseWeight * PositionFactor * TimeFactor

PositionFactor:
- 一作+通讯: 1.0
- 一作: 0.8
- 通讯(非一作): 0.7
- 末位作者: 0.6
- 中间作者: 递减

TimeFactor = 0.5^(days_since_pub / 730)  # 2年半衰期
```

## 项目结构

```
CoauthorTracking/
├── config/
│   └── settings.py          # 配置管理
├── src/
│   ├── crawler/             # 数据爬取模块
│   ├── database/            # 数据库模型和仓库
│   ├── analysis/            # 分析和 GNN 模块
│   ├── api/                 # FastAPI 接口
│   └── scheduler/           # 定时任务
├── frontend/                # React 前端
│   ├── src/
│   │   ├── components/      # 可复用组件
│   │   ├── pages/           # 页面组件
│   │   └── api/             # API 客户端
│   └── package.json
├── tests/                   # 单元测试
├── scripts/                 # 运维脚本
└── data/                    # 数据目录
```

## 技术栈

**后端:**
- 数据源: OpenAlex API
- 数据库: SQLite + Redis
- GNN 框架: PyTorch Geometric (GraphSAGE)
- Web 框架: FastAPI
- 调度器: APScheduler

**前端:**
- 框架: React + Vite
- 样式: Tailwind CSS
- 网络可视化: vis-network
- 路由: React Router

## 许可证

MIT License

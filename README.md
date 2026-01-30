# Coauthor Tracing System

基于OpenAlex数据源的论文合作者关系追踪与分析系统。

## 功能特性

- **数据爬取**: 从OpenAlex API增量爬取论文和作者数据
- **合作分析**: 使用GraphSAGE和加权算法计算作者关系强度
- **API查询**: 提供RESTful API进行作者搜索和关系查询
- **自动调度**: 支持定时自动爬取和分析更新

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制配置文件并修改:

```bash
cp .env.example .env
```

主要配置项:
- `COAUTHOR_SCOPE__INSTITUTION_IDS`: 机构ID列表
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

### 5. 运行分析

```bash
python scripts/run_analysis.py
```

### 6. 启动API服务

```bash
python scripts/start_server.py
```

API文档: http://localhost:8000/api/docs

## API端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/authors/search?q=` | 作者名称搜索 |
| GET | `/api/v1/authors/{id}` | 获取作者详情 |
| GET | `/api/v1/authors/{id}/top-relations` | Top-K关系查询 |
| GET | `/api/v1/authors/{id}/network-metrics` | 网络中心性指标 |
| GET | `/api/v1/authors/{id}/collaborators` | 直接合作者列表 |
| GET | `/api/v1/system/status` | 系统状态 |
| GET | `/api/v1/system/stats` | 详细统计 |
| POST | `/api/v1/system/crawl/trigger` | 触发爬取 |
| POST | `/api/v1/system/analysis/trigger` | 触发分析 |

## 使用示例

### 搜索作者

```bash
curl "http://localhost:8000/api/v1/authors/search?q=张三&limit=10"
```

### 获取Top-20关系

```bash
curl "http://localhost:8000/api/v1/authors/A1234567890/top-relations?k=20"
```

### 获取网络指标

```bash
curl "http://localhost:8000/api/v1/authors/A1234567890/network-metrics"
```

## 定时任务

启动调度器以自动执行任务:

```bash
python scripts/start_scheduler.py
```

默认调度:
- 每日 2:00 - 增量爬取
- 每周日 4:00 - GNN分析

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
coauthor-tracing/
├── config/
│   └── settings.py          # 配置管理
├── src/
│   ├── crawler/             # 数据爬取模块
│   ├── database/            # 数据库模型和仓库
│   ├── analysis/            # 分析和GNN模块
│   ├── api/                 # FastAPI接口
│   └── scheduler/           # 定时任务
├── tests/                   # 单元测试
├── scripts/                 # 运维脚本
└── data/                    # 数据目录
```

## 技术栈

- **数据源**: OpenAlex API
- **数据库**: SQLite + Redis
- **GNN框架**: PyTorch Geometric (GraphSAGE)
- **Web框架**: FastAPI
- **调度器**: APScheduler

## 许可证

MIT License

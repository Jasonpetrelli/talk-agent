# talk-agent

电商运营 Agent，支持自然语言查询和修改商品价格、客户信息、运费规则等。

## 功能

- **商品报价** - 查询/修改商品底价
- **客户管理** - 查询/修改客户定价系数
- **运费规则** - 查询/修改各地区运费
- **GMV 统计** - 查看今日/昨日/本周销售额
- **人工介入** - 查看待处理的异常订单

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
python init_db.py
```

### 3. 启动服务

```bash
# 启动后端 API（端口 8000）
uvicorn backend_api:app --host 0.0.0.0 --port 8000 --reload

# 启动适配器服务（端口 8080）
uvicorn adapter:app --host 0.0.0.0 --port 8080 --reload
```

## 使用示例

```
查 ABC-100 的价格
把 ABC-100 底价改成 13.5 元
查客户 凌晨公司
把 凌晨公司 定价系数改成 1.2
江浙沪的运费
江浙沪首重改成 6 元
今天卖了多少钱
有没有待处理的人工介入
```

## 技术栈

- Python 3.10+
- FastAPI
- SQLite
- requests

## 项目结构

```
talk-agent/
├── ops_agent.py       # 核心业务逻辑（意图识别）
├── backend_api.py     # 后端数据服务
├── adapter.py         # OpenAI 兼容接口
├── init_db.py         # 数据库初始化
├── requirements.txt   # 依赖
└── data.db           # SQLite 数据库
```

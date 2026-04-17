# MEMORY.md - 多市场在线选股看板

## 项目概述

- **项目名称：** 多市场在线选股看板
- **项目路径：** `D:\Projects\zaixian\`
- **当前版本：** V1.1.0
- **最后更新：** 2026-04-18

## 项目背景

基于 Python 的多市场在线选股看板，提供 A 股、港股、美股三大市场的实时行情筛选与技术分析。**V1.1.0 起接入东方财富真实行情 API。**

## 功能说明

### 核心功能
- **多市场切换：** A股 / 港股 / 美股，一键切换
- **行情筛选：** 涨跌幅范围、换手率阈值
- **技术指标筛选：** MACD 金叉、均线多头排列、RSI 适中区间
- **财务筛选：** 市盈率 (PE) 范围、ROE 最低值
- **图表展示：** 涨跌幅柱状图、行业分布饼图、换手率折线图（Chart.js）
- **股票详情弹窗：** 展示技术指标图表 + 20日K线走势
- **搜索与排序：** 按代码/名称搜索，多字段排序

### 技术指标说明
- **MACD：** 简化版金叉/死叉判断（基于涨跌幅方向）
- **MA：** 简化版多头/空头判断（基于涨跌幅方向）
- **RSI：** 简化估算值（基于涨跌幅）
- **注：** 真实技术指标需对接历史K线数据计算，当前为降级估算

## 技术架构

```
D:\Projects\zaixian\
├── frontend/
│   └── index.html          # 主页面（Tailwind CDN + Chart.js CDN）
└── backend/
    └── main.py             # FastAPI 后端（调用东方财富API）
```

### 前端技术栈
- 单页 HTML（无需构建）
- Tailwind CSS via CDN
- Chart.js v4.4.0 via CDN
- 纯 JavaScript（无框架依赖）
- API 降级机制：后端离线时自动回退到模拟数据

### 后端技术栈
- FastAPI + Uvicorn
- requests（调用东方财富 API）
- CORS 已配置（允许跨域）

## 东方财富 API 接入

### 数据接口
| 用途 | URL |
|------|-----|
| 股票列表 | `https://datacenter-web.eastmoney.com/api/qt/clist/get` |
| 实时行情 | `https://push2.eastmoney.com/api/qt/stock/get` |
| 历史K线 | `https://push2.eastmoney.com/api/qt/stock/kline/get` |

### 市场代码映射
| 市场 | East Money fs 参数 |
|------|-------------------|
| A股（上交所+深交所+科创板+创业板） | `m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23` |
| 港股（主板+创业板） | `m:116+t:0,m:115+t:0` |
| 美股（中概股+美股） | `m:105+t:0,m:106+t:0` |

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stocks/{market}` | 获取市场股票列表（支持 a/hk/us） |
| GET | `/api/quote/{market}/{code}` | 获取单只股票实时行情 |
| GET | `/api/history/{market}/{code}` | 获取历史K线（用于技术指标计算） |

## 启动方式

### 后端
```bash
cd D:\Projects\zaixian\backend
pip install -r requirements.txt
python main.py
# 服务地址: http://localhost:8000
```

### 前端
直接用浏览器打开 `D:\Projects\zaixian\frontend\index.html`

> ⚠️ 注意：跨域问题（浏览器直接打开 HTML 调用 localhost:8000）
> - 方案1：后端添加 CORS 支持（已配置）
> - 方案2：前端部署到 http://localhost:8000 同源
> - 方案3：Chrome 启动时加 `--disable-web-security`（仅开发用）

## 注意事项

- **API 限制：** 东方财富 API 无需 key，但有频率限制，请勿高频刷新
- **数据源：** 东方财富为公开行情数据，仅供学习研究使用
- **技术指标：** 当前为简化估算，真实 MACD/RSI/MA 需用历史K线计算
- **港股/美股：** 财务数据（PE、ROE）可能为空值，筛选时应做空值判断
- **CORS：** 已配置 `allow_origins=["*"]`，开发环境无跨域限制

## 更新日志

### V1.1.0 (2026-04-18)
- **重大更新：** 接入东方财富真实行情 API
- 后端新增 `/api/stocks/{market}` 接口（支持 A股/港股/美股）
- 后端新增 `/api/quote/{market}/{code}` 单票行情接口
- 后端新增 `/api/history/{market}/{code}` 历史K线接口
- 前端增加 API 离线降级机制（自动回退 Mock 数据）
- 前端增加连接状态标识（REAL / OFFLINE）
- 修复前端字段名不匹配问题（`priceChange` 替代 `change`）

### V1.0.0 (2026-04-18)
- 完成基础前端框架搭建
- 实现多市场切换功能
- 实现三大筛选模块（行情、技术、财务）
- 集成 Chart.js 图表（柱状图/饼图/折线图）
- 实现股票详情弹窗（含走势图表）
- 实现搜索、排序、重置筛选功能

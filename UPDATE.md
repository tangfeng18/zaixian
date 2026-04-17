# 更新日志

## V1.1.0 (2026-04-18)

### 新增内容
- 前端页面添加真实 API 调用逻辑
- 添加股票筛选表单（PE-TTM、ROE、涨跌幅、MACD金叉、均线多头）
- 添加股票列表展示区域
- 添加股票详情展示
- 添加加载状态处理（loading spinner）
- 添加错误状态和空状态处理
- 添加 API 连接状态指示器
- 后端实现东方财富行情 API 集成
- 后端实现股票筛选接口 `/api/stock/screener`
- 后端实现实时行情接口 `/api/market/quote/{market}/{code}`
- 后端实现技术指标接口 `/api/indicator/{code}`
- 添加演示数据功能（API 未连接时显示示例）

### 修改内容
- 前端从静态页面改为动态数据驱动
- 后端从框架占位改为真实 API 实现

### 功能作用
- 前端可调用后端 API 获取东方财富真实行情数据
- 支持多维度筛选股票
- 展示股票列表和详情
- API 未连接时自动降级显示演示数据

### API 接口
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/stock/screener` | GET | 股票筛选 |
| `/api/market/quote/{market}/{code}` | GET | 实时行情 |
| `/api/indicator/{code}` | GET | 技术指标 |

---

## V1.0.0 (2026-04-18)

### 新增内容
- 创建项目基础结构
- 创建 MEMORY.md 项目记忆文档
- 创建前端页面框架（index.html）
- 集成 Tailwind CSS、Chart.js、Font Awesome
- 实现响应式卡片布局
- 添加技术指标图表展示区域
- 添加数据源对比表格
- 添加多维度筛选条件展示
- 添加复合策略示例展示

### 待完成
- 后端 FastAPI 服务开发
- 东方财富 API 接入
- AKShare 数据接入
- 实时数据调用功能

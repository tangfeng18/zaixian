# 多市场在线选股看板

基于 Python 的多市场在线选股系统，支持 A股、港股、美股的多维度筛选和技术指标计算。

## 功能特性

- ✅ 多市场覆盖（A股、港股、美股）
- ✅ 多维度筛选（行情、技术、财务）
- ✅ 技术指标计算（MACD、RSI、均线）
- ✅ 复合策略选股
- ✅ 响应式界面设计

## 技术栈

- **前端**：HTML5 + Tailwind CSS + Chart.js
- **后端**：Python FastAPI
- **数据源**：东方财富 API / AKShare

## 项目结构

```
zaixian/
├── frontend/           # 前端目录
│   └── index.html      # 主页面
├── backend/            # 后端目录（开发中）
│   ├── main.py         # FastAPI入口
│   └── requirements.txt # 依赖
├── MEMORY.md           # 项目记忆文档
└── UPDATE.md           # 更新日志
```

## 部署

- 前端：Vercel
- 后端：Railway

## 版本

- 当前版本：V1.0.0
- 版本管理：每次更新递增

## 提交流程

程序员提交 → 指挥官审核 → 执行者通报

## 注意事项

1. 东方财富 API 需完成注册认证
2. 日调用量超500次需提前报备
3. 仅限个人学习使用，不得用于商业用途

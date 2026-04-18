# 更新说明 - V1.0.0

**版本：** V1.0.0  
**发布日期：** 2026-04-18  
**部署平台：** Railway

---

## 🚀 部署信息

**后端访问地址：** https://pure-ambition-production-b39f.up.railway.app

**Railway 项目：** https://railway.com/project/8b52f47e-a535-4df2-a031-6650285f6aea

---

## 修改内容

1. **新增 Railway 部署配置**
   - 创建 `railway.json` — 定义构建和部署参数
   - 创建 `Procfile` — Web 进程启动命令

2. **修复依赖问题**
   - 移除不存在的 `akshare==1.13.0` 依赖（实际代码未使用）
   - 清理未使用的 `redis`、`aiohttp` 依赖

---

## 功能作用

### 后端 API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务基本信息 |
| `/api/health` | GET | 健康检查 |
| `/api/stocks/{market}` | GET | 获取市场股票列表（A/HK/US） |
| `/api/quote/{market}/{code}` | GET | 获取单只股票实时行情 |
| `/api/history/{market}/{code}` | GET | 获取股票历史K线数据 |

### 技术栈
- **框架：** FastAPI 0.109.0
- **服务器：** Uvicorn
- **数据源：** 东方财富 API（实时股票数据）
- **支持市场：** A股、港股、美股

---

## 部署配置

- **构建命令：** `pip install -r requirements.txt`
- **启动命令：** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **区域：** us-west2
- **副本数：** 1

---

## 注意事项

⚠️ **GitHub 仓库 `tangfeng18/zaixian` 不存在**  
当前部署使用本地代码直接上传。如需持续部署，请先在 GitHub 创建仓库并推送代码。

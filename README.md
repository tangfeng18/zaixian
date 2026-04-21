# 在线选股共振工具

「捕捞季节 + 神龙筹码」双指标共振筛选 API

## 快速启动

```bash
pip install -r requirements.txt
python stock_screener_api.py
```

服务启动后访问 http://127.0.0.1:5000

## 接口说明

### 查询单股信号
GET /api/stock/<code>

示例: http://127.0.0.1:5000/api/stock/000001

### 执行选股筛选
POST /api/screen

Body:
```json
{
  "version": "basic",
  "pool": "hs300",
  "limit": 20
}
```

version: basic(基础版) / advanced(进阶版)
pool: all / hs300 / zz500 / gem

## 指标说明

### 捕捞季节
- 金叉信号: DIF上穿DEA，红柱趋势
- 彩柱数 >= 2

### 神龙筹码
- 红线上穿橙线/紫线
- 红柱上升区间

## 注意事项

- 需要能够访问国内金融数据源的网络环境
- 建议使用服务器运行，避免占用本地带宽

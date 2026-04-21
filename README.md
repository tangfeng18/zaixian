# 在线选股共振工具

「捕捞季节 + 神龙筹码」双指标共振筛选 API

数据源: Tushare Pro (无需国内服务器，国内外均可访问)

## 快速启动

```bash
pip install -r requirements.txt
python stock_screener_tushare.py
```

服务启动后访问 http://127.0.0.1:5000

## 接口说明

### 查询单股信号
GET /api/stock/<code>

示例:
- http://127.0.0.1:5000/api/stock/000001 (自动识别沪深)
- http://127.0.0.1:5000/api/stock/600000.SH

### 执行选股筛选
POST /api/screen

```json
{
  "version": "basic",
  "limit": 20
}
```

version: basic(基础版) / advanced(进阶版)

### 获取股票列表
GET /api/stocklist

## 指标说明

### 捕捞季节
- 金叉信号: DIF上穿DEA，红柱趋势
- 彩柱数 >= 2 (资金活跃)

### 神龙筹码
- 红线上穿橙线/紫线 (筹码趋势转强)
- 红柱上升区间 (平均获利筹码增加)

### 基础版
同时满足:
1. 捕捞金叉 + 红柱趋势 + 彩柱数>=2
2. 神龙红线金叉 + 红柱上升

### 进阶版
基础版 + 以下全部满足:
3. 平均套牢比例 < 50%
4. 股价站上MA20，MA20向上
5. 近3日成交量均值 > 5日均量

## 注意事项

- 需要 Tushare Pro token (注册: https://tushare.pro)
- Token 已内置在代码中，基础积分用户可用
- 每次筛选约需3-5分钟 (遍历800+只股票)

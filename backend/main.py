"""
多市场在线选股看板 - FastAPI 后端服务
版本: V1.1.0
功能: 调用东方财富API获取真实股票数据
"""

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
import json
from datetime import datetime

app = FastAPI(title="多市场选股看板API", version="1.1.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 东方财富 API 配置
EM_API_BASE2 = "https://datacenter-web.eastmoney.com"
EM_PUSH_BASE = "https://push2.eastmoney.com"

# ===== 市场代码映射 =====
# East Money secid 格式: 市场代码.股票代码
# A股: 1=上交所, 0=深交所
# 港股: 116=港交所主板, 115=港交所创业板
# 美股: 105=中概股, 106=美股

MARKET_SECID = {
    "a": ["1.", "0."],   # A股 上交所+深交所
    "hk": ["116."],      # 港股
    "us": ["105.", "106."]  # 美股
}

# fs 参数: m:0+t:6 上交所主板, m:0+t:80 科创板, m:1+t:2 深交所主板, m:1+t:23 创业板
FS_MAP = {
    "a": "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23",
    "hk": "m:116+t:0,m:115+t:0",
    "us": "m:105+t:0,m:106+t:0"
}


class StockItem(BaseModel):
    code: str
    name: str
    market: str
    price: Optional[float] = None
    priceChange: Optional[float] = None   # 涨跌幅 (%)
    turnover: Optional[float] = None      # 换手率 (%)
    volume: Optional[int] = None          # 成交量
    amount: Optional[float] = None        # 成交额
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None
    pe: Optional[float] = None
    roe: Optional[float] = None
    macd: Optional[str] = None            # 金叉/死叉
    ma: Optional[str] = None              # 多头/空头
    rsi: Optional[float] = None
    sector: Optional[str] = None          # 所属行业


class ScreenerResponse(BaseModel):
    stocks: List[StockItem]
    total: int
    timestamp: str
    market: str


@app.get("/")
async def root():
    return {
        "status": "online",
        "version": "V1.1.0",
        "timestamp": datetime.now().isoformat(),
        "service": "多市场选股看板API"
    }


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "V1.1.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/stocks/{market}")
async def get_stocks(
    market: str,
    limit: int = Query(100, description="返回数量", ge=1, le=500),
    page: int = Query(1, description="页码", ge=1)
):
    """
    获取市场股票列表（东方财富真实数据）

    Args:
        market: a=A股, hk=港股, us=美股
    """
    try:
        fs = FS_MAP.get(market, FS_MAP["a"])
        params = {
            "pn": page,
            "pz": limit,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": fs,
            "fields": (
                "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,"
                "f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f62,"
                "f115,f152,f45,f46,f47,f48,f49,f50,f57,f58"
            ),
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/"
        }

        url = f"{EM_API_BASE2}/api/qt/clist/get"
        resp = requests.get(url, params=params, headers=headers, timeout=15)

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        data = resp.json()
        stocks = []

        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                try:
                    change = item.get("f3")
                    price = item.get("f2")

                    stock = StockItem(
                        code=str(item.get("f12", "")),
                        name=str(item.get("f14", "")),
                        market=market,
                        price=float(price) if price not in ("-", None, "") else None,
                        priceChange=float(change) if change not in ("-", None, "") else 0.0,
                        turnover=float(item.get("f8", 0)) if item.get("f8") not in ("-", None, "") else None,
                        volume=int(item.get("f5", 0)) if item.get("f5") not in ("-", None, "") else None,
                        amount=float(item.get("f6", 0)) if item.get("f6") not in ("-", None, "") else None,
                        high=float(item.get("f15", 0)) if item.get("f15") not in ("-", None, "") else None,
                        low=float(item.get("f16", 0)) if item.get("f16") not in ("-", None, "") else None,
                        open=float(item.get("f4", 0)) if item.get("f4") not in ("-", None, "") else None,
                        close=float(item.get("f17", 0)) if item.get("f17") not in ("-", None, "") else None,
                        pe=float(item.get("f9", 0)) if item.get("f9") not in ("-", None, "") else None,
                        roe=float(item.get("f10", 0)) if item.get("f10") not in ("-", None, "") else None,
                        sector=str(item.get("f100", "")) if item.get("f100") else None,
                    )

                    # 简化技术指标（实际生产应计算真实值）
                    stock.macd = "金叉" if (stock.priceChange or 0) > 0 else "死叉"
                    stock.ma = "多头" if (stock.priceChange or 0) > 0 else "空头"
                    stock.rsi = min(100, max(0, 50 + (stock.priceChange or 0) * 2))

                    stocks.append(stock)
                except (ValueError, TypeError):
                    continue

        return ScreenerResponse(
            stocks=stocks,
            total=len(stocks),
            timestamp=datetime.now().isoformat(),
            market=market
        )

    except Exception as e:
        print(f"[ERROR] get_stocks({market}): {e}")
        return ScreenerResponse(stocks=[], total=0, timestamp=datetime.now().isoformat(), market=market)


@app.get("/api/quote/{market}/{code}")
async def get_quote(market: str, code: str):
    """
    获取单只股票实时行情
    """
    try:
        # 构造 East Money secid
        if market == "a":
            secid = f"1.{code}" if code.startswith(("6", "5")) else f"0.{code}"
        elif market == "hk":
            secid = f"116.{code}"
        elif market == "us":
            secid = f"105.{code}"
        else:
            secid = code

        params = {
            "secid": secid,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fltt": 2,
            "invt": 2,
            "fields": (
                "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,"
                "f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f62,"
                "f115,f152,f45,f46,f47,f48,f49,f50,f57,f58"
            ),
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/"
        }

        url = f"{EM_PUSH_BASE}/api/qt/stock/get"
        resp = requests.get(url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        d = resp.json().get("data", {})
        if not d:
            return {"error": "未找到数据", "code": code, "market": market}

        change = d.get("f3", 0)
        return {
            "code": code,
            "name": d.get("f14", ""),
            "market": market,
            "price": d.get("f2"),
            "priceChange": change,
            "change": change,
            "open": d.get("f4"),
            "high": d.get("f15"),
            "low": d.get("f16"),
            "close": d.get("f17"),
            "volume": d.get("f5"),
            "amount": d.get("f6"),
            "turnover": d.get("f8"),
            "pe": d.get("f9"),
            "roe": d.get("f10"),
            "macd": "金叉" if change > 0 else "死叉",
            "ma": "多头" if change > 0 else "空头",
            "rsi": min(100, max(0, 50 + change * 2)),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {"error": str(e), "code": code, "market": market}


@app.get("/api/history/{market}/{code}")
async def get_history(
    market: str,
    code: str,
    period: str = Query("day", description="day/week/month"),
    count: int = Query(30, description="数据条数")
):
    """
    获取股票历史K线数据（用于技术指标计算）
    """
    try:
        # 构造 secid
        if market == "a":
            secid = f"1.{code}" if code.startswith(("6", "5")) else f"0.{code}"
        elif market == "hk":
            secid = f"116.{code}"
        elif market == "us":
            secid = f"105.{code}"
        else:
            secid = code

        klt = {"day": 101, "week": 102, "month": 103}[period]

        params = {
            "secid": secid,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "klt": klt,
            "fqt": 1,
            "beg": 0,
            "end": 20500101,
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://quote.eastmoney.com/"
        }

        url = f"{EM_PUSH_BASE}/api/qt/stock/kline/get"
        resp = requests.get(url, params=params, headers=headers, timeout=10)

        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}")

        d = resp.json()
        if d.get("data") and d["data"].get("klines"):
            return {
                "code": code,
                "market": market,
                "klines": d["data"]["klines"][-count:],
                "timestamp": datetime.now().isoformat()
            }

        return {"code": code, "market": market, "klines": [], "timestamp": datetime.now().isoformat()}

    except Exception as e:
        return {"error": str(e), "code": code, "market": market}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

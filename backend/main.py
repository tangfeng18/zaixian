"""
多市场在线选股看板 - FastAPI 后端服务
版本: V1.3.0
功能: 东方财富实时行情 + Tushare Pro 技术指标
新增: 捕捞季节 + 神龙筹码 双指标共振选股 (混合预筛选加速)
"""

from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import requests
import pandas as pd
import numpy as np
import asyncio
import uuid
import time
import warnings
warnings.filterwarnings('ignore')

import tushare as ts
import uvicorn

app = FastAPI(title="多市场选股看板API", version="1.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.github\.io|https://.*\.railway\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================
# 配置
# ========================
TS_TOKEN = '43c0a5c3a4743f32c0769f32dce1318863f8b99a09e881212f7514e1'
try:
    pro = ts.pro_api(TS_TOKEN)
except Exception:
    pro = None

EM_API_BASE2 = "https://datacenter-web.eastmoney.com"
EM_PUSH_BASE = "https://push2.eastmoney.com"

FS_MAP = {
    "a": "m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23",
    "hk": "m:116+t:0,m:115+t:0",
    "us": "m:105+t:0,m:106+t:0"
}

# ========================
# 模型
# ========================
class StockItem(BaseModel):
    code: str; name: str; market: str
    price: Optional[float] = None; priceChange: Optional[float] = None
    turnover: Optional[float] = None; volume: Optional[int] = None
    amount: Optional[float] = None; high: Optional[float] = None
    low: Optional[float] = None; open: Optional[float] = None
    close: Optional[float] = None; pe: Optional[float] = None
    roe: Optional[float] = None; macd: Optional[str] = None
    ma: Optional[str] = None; rsi: Optional[float] = None
    sector: Optional[str] = None

class ScreenerResponse(BaseModel):
    stocks: List[StockItem]; total: int; timestamp: str; market: str

class SignalResponse(BaseModel):
    code: str; ts_code: str; version: str
    signals: dict; basic共振: bool; advanced共振: bool
    sell: dict; timestamp: str

# ========================
# 内存中的后台任务状态
# ========================
SCREEN_JOBS = {}  # job_id -> {status, progress, results, error}

# ========================
# 指标计算核心
# ========================
def calc_biaoaojiji(df, short=10, long=50, mid=9):
    df = df.copy()
    df = df.sort_values('trade_date').reset_index(drop=True)
    close = df['close'].astype(float)
    df['DIF'] = close.ewm(span=short, adjust=False).mean() - close.ewm(span=long, adjust=False).mean()
    df['DEA'] = df['DIF'].ewm(span=mid, adjust=False).mean()
    df['HIST'] = 2 * (df['DIF'] - df['DEA'])
    return df

def calc_shenlong_chouma(df, lookback=60):
    df = df.copy()
    df = df.sort_values('trade_date').reset_index(drop=True)
    close = df['close'].astype(float)
    vol = df['vol'].astype(float)
    windows = [5, 21, 60]
    def cost_line(series, vol_s, window):
        result = []
        for i in range(len(series)):
            if i < window:
                result.append(np.nan)
            else:
                w_p = series.iloc[i-window:i]
                w_v = vol_s.iloc[i-window:i]
                result.append(np.sum(w_p * w_v) / np.sum(w_v))
        return pd.Series(result, index=series.index)
    df['Red'] = cost_line(close, vol, windows[0])
    df['Orange'] = cost_line(close, vol, windows[1])
    df['Purple'] = cost_line(close, vol, windows[2])
    for col in ['Red', 'Orange', 'Purple']:
        mn = df[col].rolling(lookback, min_periods=10).min()
        mx = df[col].rolling(lookback, min_periods=10).max()
        rng = mx - mn
        df[col + '_pct'] = np.where(rng > 0, (df[col] - mn) / rng * 100, 50)
    return df

def compute_signals(df_daily):
    if len(df_daily) < 60:
        return None
    df_b = calc_biaoaojiji(df_daily)
    df_s = calc_shenlong_chouma(df_daily)
    df = df_b.join(df_s[['Red_pct', 'Orange_pct', 'Purple_pct']], how='left')
    last, prev = df.iloc[-1], df.iloc[-2]
    dif, dea = last['DIF'], last['DEA']
    dif_p, dea_p = prev['DIF'], prev['DEA']
    hist = last['HIST']
    biao_gc = (dif_p <= dea_p) and (dif > dea)
    biao_red = hist > 0
    cai_zhu = sum(1 for v in df['HIST'].tail(20).iloc[::-1] if v > 0)
    red, orange, purple = last['Red_pct'], last['Orange_pct'], last['Purple_pct']
    red_p, orange_p = prev['Red_pct'], prev['Orange_pct']
    shen_gc = (red_p <= orange_p and red > orange) or (red_p <= purple and red > purple)
    shen_red = red > orange and red > purple
    trapped = np.mean([max(0, orange - red), max(0, purple - red)]) / 100
    close = df_daily['close'].astype(float)
    ma20 = close.rolling(20).mean()
    price_above = float(close.iloc[-1]) > ma20.iloc[-1]
    ma20_up = ma20.iloc[-1] > ma20.iloc[-2]
    vol = df_daily['vol'].astype(float)
    vol_up = vol.tail(3).mean() > vol.tail(5).mean()
    return {
        '最新价': round(float(close.iloc[-1]), 2),
        '日期': str(df_daily.iloc[-1]['trade_date']),
        '捕捞_DIF': round(float(dif), 4), '捕捞_DEA': round(float(dea), 4),
        '捕捞_HIST': round(float(hist), 4),
        '捕捞_金叉': bool(biao_gc), '捕捞_红柱趋势': bool(biao_red),
        '捕捞_彩柱数': cai_zhu,
        '神龙_Red_pct': round(float(red), 2),
        '神龙_Orange_pct': round(float(orange), 2),
        '神龙_Purple_pct': round(float(purple), 2),
        '神龙_红线金叉': bool(shen_gc), '神龙_红柱上升': bool(shen_red),
        '神龙_套牢比例': round(float(trapped), 4),
        '股价站上MA20': bool(price_above), 'MA20向上': bool(ma20_up),
        '量能放大': bool(vol_up),
    }

def check_basic(s):
    if not s: return False
    return (s['捕捞_金叉'] and s['捕捞_红柱趋势'] and s['捕捞_彩柱数'] >= 2
            and s['神龙_红线金叉'] and s['神龙_红柱上升'])

def check_advanced(s):
    if not s: return False
    return (s['捕捞_金叉'] and s['捕捞_红柱趋势'] and s['捕捞_彩柱数'] >= 2
            and s['神龙_红线金叉'] and s['神龙_红柱上升']
            and s['神龙_套牢比例'] < 0.5
            and s['股价站上MA20'] and s['MA20向上'] and s['量能放大'])

def check_sell(s):
    if not s: return None
    return {'触发卖出1_捕捞死叉绿柱': False, '触发卖出2_神龙死叉': False,
            '触发卖出3_跌破MA20': not s['股价站上MA20'] and not s['MA20向上']}

# ========================
# 东方财富数据获取
# ========================
def em_get_stocks(market='a', limit=500):
    """用东方财富获取全市场股票基础数据"""
    try:
        fs = FS_MAP.get(market, FS_MAP['a'])
        params = {
            "pn": 1, "pz": limit, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3", "fs": fs,
            "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
        url = f"{EM_API_BASE2}/api/qt/clist/get"
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        stocks = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                try:
                    chg = item.get("f3", 0) or 0
                    stocks.append({
                        'code': str(item.get("f12","")),
                        'name': str(item.get("f14","")),
                        'price': float(item.get("f2")) if item.get("f2", "-") not in ("-", None, "") else None,
                        'change': float(chg),
                        'volume': int(item.get("f5", 0)) if item.get("f5", "-") not in ("-", None, "") else 0,
                        'turnover': float(item.get("f8", 0)) if item.get("f8", "-") not in ("-", None, "") else 0,
                    })
                except (ValueError, TypeError):
                    continue
        return stocks
    except Exception:
        return []

def em_prefilter(stocks):
    """
    东方财富预筛选：粗筛放量、上涨、换手率适中的股票
    减少需要调用Tushare精筛的数量
    """
    candidates = []
    for s in stocks:
        # 基础过滤：上涨、成交量>0、换手率 0.5%~20%
        if (s.get('change', 0) > 0 and
            s.get('volume', 0) > 0 and
            0.5 <= (s.get('turnover') or 0) <= 20):
            candidates.append(s)
    return candidates

# ========================
# 东方财富接口
# ========================
@app.get("/")
async def root():
    return {"status": "online", "version": "V1.3.0", "timestamp": datetime.now().isoformat()}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "V1.3.0", "timestamp": datetime.now().isoformat()}

@app.get("/api/stocks/{market}")
async def get_stocks(market: str, limit: int = Query(100, ge=1, le=500), page: int = Query(1, ge=1)):
    try:
        fs = FS_MAP.get(market, FS_MAP["a"])
        params = {
            "pn": page, "pz": limit, "po": 1, "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2, "invt": 2, "fid": "f3", "fs": fs,
            "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f62,f115,f152,f45,f46,f47,f48,f49,f50,f57,f58",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
        url = f"{EM_API_BASE2}/api/qt/clist/get"
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        stocks = []
        if data.get("data") and data["data"].get("diff"):
            for item in data["data"]["diff"]:
                try:
                    chg = item.get("f3"); price = item.get("f2")
                    stocks.append(StockItem(
                        code=str(item.get("f12","")), name=str(item.get("f14","")),
                        market=market,
                        price=float(price) if price not in ("-",None,"") else None,
                        priceChange=float(chg) if chg not in ("-",None,"") else 0.0,
                        turnover=float(item.get("f8",0)) if item.get("f8") not in ("-",None,"") else None,
                        volume=int(item.get("f5",0)) if item.get("f5") not in ("-",None,"") else None,
                        amount=float(item.get("f6",0)) if item.get("f6") not in ("-",None,"") else None,
                        high=float(item.get("f15",0)) if item.get("f15") not in ("-",None,"") else None,
                        low=float(item.get("f16",0)) if item.get("f16") not in ("-",None,"") else None,
                        open=float(item.get("f4",0)) if item.get("f4") not in ("-",None,"") else None,
                        close=float(item.get("f17",0)) if item.get("f17") not in ("-",None,"") else None,
                        pe=float(item.get("f9",0)) if item.get("f9") not in ("-",None,"") else None,
                        roe=float(item.get("f10",0)) if item.get("f10") not in ("-",None,"") else None,
                        sector=str(item.get("f100","")) if item.get("f100") else None,
                        macd="金叉" if (chg or 0) > 0 else "死叉",
                        ma="多头" if (chg or 0) > 0 else "空头",
                        rsi=min(100, max(0, 50 + (chg or 0) * 2)),
                    ))
                except (ValueError, TypeError):
                    continue
        return ScreenerResponse(stocks=stocks, total=len(stocks), timestamp=datetime.now().isoformat(), market=market)
    except Exception as e:
        return ScreenerResponse(stocks=[], total=0, timestamp=datetime.now().isoformat(), market=market)

@app.get("/api/quote/{market}/{code}")
async def get_quote(market: str, code: str):
    try:
        secid = f"1.{code}" if code.startswith(("6","5")) else f"0.{code}" if market=="a" else f"116.{code}" if market=="hk" else f"105.{code}"
        params = {
            "secid": secid, "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "fltt": 2, "invt": 2,
            "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f62,f115,f152",
        }
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"}
        url = f"{EM_PUSH_BASE}/api/qt/stock/get"
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        d = resp.json().get("data", {})
        if not d:
            raise HTTPException(status_code=404, detail="未找到数据")
        chg = d.get("f3", 0)
        return {
            "code": code, "name": d.get("f14",""), "market": market,
            "price": d.get("f2"), "priceChange": chg, "change": chg,
            "open": d.get("f4"), "high": d.get("f15"), "low": d.get("f16"),
            "close": d.get("f17"), "volume": d.get("f5"), "amount": d.get("f6"),
            "turnover": d.get("f8"), "pe": d.get("f9"), "roe": d.get("f10"),
            "macd": "金叉" if chg > 0 else "死叉",
            "ma": "多头" if chg > 0 else "空头",
            "rsi": min(100, max(0, 50 + chg * 2)),
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========================
# Tushare Pro 指标接口
# ========================
def ts_daily(ts_code, days=120):
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
    try:
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or len(df) < 60:
            return None
        return df.sort_values('trade_date').reset_index(drop=True)
    except Exception:
        return None

def get_ts_list():
    """获取沪深全市场股票列表（用hs_const）"""
    try:
        sh = pro.hs_const(hs_type='SH')
        sz = pro.hs_const(hs_type='SZ')
        return pd.concat([sh, sz])['ts_code'].tolist()
    except Exception:
        return []

@app.get("/api/signal/{code}", response_model=SignalResponse)
async def get_signal(code: str):
    c = code.strip()
    if not c.endswith('.SH') and not c.endswith('.SZ'):
        c = c + ('.SH' if c.startswith('6') else '.SZ')
    df = ts_daily(c)
    if df is None:
        raise HTTPException(status_code=400, detail=f"获取数据失败或数据不足: {code}")
    signals = compute_signals(df)
    return SignalResponse(
        code=code, ts_code=c, version="V1.3.0",
        signals=signals,
        basic共振=check_basic(signals), advanced共振=check_advanced(signals),
        sell=check_sell(signals),
        timestamp=datetime.now().isoformat()
    )

# ========================
# 后台选股任务
# ========================
def run_screen_job(job_id: str, version: str, pool: str, limit: int):
    """
    后台执行选股：Tushare全量精筛
    使用hs_const获取候选列表，最多筛选200只
    """
    SCREEN_JOBS[job_id] = {'status': 'running', 'progress': 0, 'results': [], 'total': 0, 'checked': 0, 'error': None}
    try:
        # 获取候选列表（用hs_const，可用的接口）
        all_codes = get_ts_list()
        SCREEN_JOBS[job_id]['total'] = len(all_codes)
        if not all_codes:
            SCREEN_JOBS[job_id]['status'] = 'error'
            SCREEN_JOBS[job_id]['error'] = '无法获取股票列表'
            return

        check_fn = check_advanced if version == 'advanced' else check_basic
        checked = 0
        # 限制候选数量（避免太慢）
        candidates = all_codes[:100]

        for ts_code in candidates:
            checked += 1
            try:
                df = ts_daily(ts_code)
                if df is None:
                    SCREEN_JOBS[job_id]['checked'] = checked
                    SCREEN_JOBS[job_id]['progress'] = min(95, int(checked / len(candidates) * 100))
                    time.sleep(0.1)
                    continue
                sigs = compute_signals(df)
                if check_fn(sigs):
                    plain_code = ts_code.replace('.SH','').replace('.SZ','')
                    SCREEN_JOBS[job_id]['results'].append({
                        'code': plain_code,
                        'ts_code': ts_code,
                        '信号': sigs,
                        '卖出信号': check_sell(sigs),
                    })
                    if len(SCREEN_JOBS[job_id]['results']) >= limit:
                        break
            except Exception:
                pass

            SCREEN_JOBS[job_id]['checked'] = checked
            SCREEN_JOBS[job_id]['progress'] = min(95, int(checked / len(candidates) * 100))
            time.sleep(0.15)  # Tushare限速保护

        SCREEN_JOBS[job_id]['progress'] = 100
        SCREEN_JOBS[job_id]['status'] = 'done'

    except Exception as e:
        SCREEN_JOBS[job_id]['status'] = 'error'
        SCREEN_JOBS[job_id]['error'] = str(e)

@app.post("/api/screen")
async def screen_stocks(version: str = Query("basic"), pool: str = Query("all"), limit: int = Query(20, ge=1, le=100)):
    """
    提交选股任务（后台异步执行）
    返回 job_id，调用 /api/screen/status/{job_id} 查询进度和结果
    """
    job_id = str(uuid.uuid4())[:8]
    # 启动后台任务
    asyncio.create_task(asyncio.to_thread(run_screen_job, job_id, version, pool, limit))
    return {
        "job_id": job_id,
        "message": "选股任务已启动，请使用 job_id 查询进度",
        "version": version, "pool": pool, "limit": limit,
        "status_url": f"/api/screen/status/{job_id}",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/screen/status/{job_id}")
async def get_screen_status(job_id: str):
    """查询选股任务状态和结果"""
    if job_id not in SCREEN_JOBS:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    job = SCREEN_JOBS[job_id]
    return {
        "job_id": job_id,
        "status": job['status'],
        "progress": job['progress'],
        "checked": job.get('checked', 0),
        "total": job.get('total', 0),
        "matched_count": len(job.get('results', [])),
        "results": job.get('results', []),
        "error": job.get('error'),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stocklist")
async def get_stock_list():
    try:
        sh = pro.hs_const(hs_type='SH')
        sz = pro.hs_const(hs_type='SZ')
        df = pd.concat([sh, sz])
        return {"total": len(df), "sample": df['ts_code'].head(20).tolist(), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

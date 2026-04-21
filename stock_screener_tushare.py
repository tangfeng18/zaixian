"""
在线选股共振工具 - Flask API (Tushare Pro 数据源)
「捕捞季节 + 神龙筹码」双指标共振筛选
数据源: Tushare Pro (daily/weekly 接口)
"""

from flask import Flask, jsonify, request
import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

TOKEN = '43c0a5c3a4743f32c0769f32dce1318863f8b99a09e881212f7514e1'
pro = ts.pro_api(TOKEN)

# ============================================================
# 指标计算核心
# ============================================================

def calc_biaoaojiji(df, short=10, long=50, mid=9):
    """
    捕捞季节指标 (类MACD指标)
    DIF = EMA(close, short) - EMA(close, long)
    DEA = EMA(DIF, mid)
    """
    df = df.copy()
    df = df.sort_values('trade_date').reset_index(drop=True)
    close = df['close'].astype(float)

    ema_short = close.ewm(span=short, adjust=False).mean()
    ema_long = close.ewm(span=long, adjust=False).mean()
    df['DIF'] = ema_short - ema_long
    df['DEA'] = df['DIF'].ewm(span=mid, adjust=False).mean()
    df['HIST'] = 2 * (df['DIF'] - df['DEA'])
    return df


def calc_shenlong_chouma(df, lookback=60):
    """
    神龙筹码指标 (成本分布动量指标)
    红线 = 短期成本(5日), 橙线 = 中期(21日), 紫线 = 长期(60日)
    """
    df = df.copy()
    df = df.sort_values('trade_date').reset_index(drop=True)
    close = df['close'].astype(float)
    volume = df['vol'].astype(float)

    windows = [5, 21, 60]

    def cost_line(series, vol, window):
        result = []
        for i in range(len(series)):
            if i < window:
                result.append(np.nan)
            else:
                w_p = series.iloc[i-window:i]
                w_v = vol.iloc[i-window:i]
                cost = np.sum(w_p * w_v) / np.sum(w_v)
                result.append(cost)
        return pd.Series(result, index=series.index)

    df['Red'] = cost_line(close, volume, windows[0])
    df['Orange'] = cost_line(close, volume, windows[1])
    df['Purple'] = cost_line(close, volume, windows[2])

    for col in ['Red', 'Orange', 'Purple']:
        roll_min = df[col].rolling(lookback, min_periods=10).min()
        roll_max = df[col].rolling(lookback, min_periods=10).max()
        rng = roll_max - roll_min
        df[col + '_pct'] = np.where(rng > 0, (df[col] - roll_min) / rng * 100, 50)

    return df


def get_stock_signals(df_daily, df_weekly=None):
    """
    计算单只股票的指标信号
    """
    if len(df_daily) < 60:
        return None

    df_biao = calc_biaoaojiji(df_daily)
    df_shen = calc_shenlong_chouma(df_daily)
    df_merged = df_biao.join(df_shen[['Red', 'Orange', 'Purple', 'Red_pct', 'Orange_pct', 'Purple_pct']], how='left')

    last = df_merged.iloc[-1]
    prev = df_merged.iloc[-2]

    # ---- 捕捞季节 ----
    dif, dea = last['DIF'], last['DEA']
    dif_prev, dea_prev = prev['DIF'], prev['DEA']
    hist = last['HIST']

    biao_golden_cross = (dif_prev <= dea_prev) and (dif > dea)
    biao_red_trend = hist > 0

    hist_series = df_merged['HIST'].tail(20)
    cai_zhu_count = 0
    for v in reversed(hist_series.values):
        if v > 0:
            cai_zhu_count += 1
        else:
            break

    # ---- 神龙筹码 ----
    red, orange, purple = last['Red_pct'], last['Orange_pct'], last['Purple_pct']
    red_prev, orange_prev = prev['Red_pct'], prev['Orange_pct']

    shen_long_cross = (red_prev <= orange_prev and red > orange) or \
                       (red_prev <= purple and red > purple)
    shen_red_rising = red > orange and red > purple
    trapped_ratio = np.mean([max(0, orange - red), max(0, purple - red)]) / 100

    # ---- 均线 ----
    close = df_daily['close'].astype(float)
    ma20 = close.rolling(20).mean().iloc[-1]
    ma20_prev = close.rolling(20).mean().iloc[-2]
    price_above_ma20 = float(close.iloc[-1]) > ma20
    ma20_going_up = ma20 > ma20_prev

    # ---- 量能 ----
    vol = df_daily['vol'].astype(float)
    vol_ma3 = vol.tail(3).mean()
    vol_ma5 = vol.tail(5).mean()
    vol_increasing = vol_ma3 > vol_ma5

    return {
        '最新价': round(float(close.iloc[-1]), 2),
        '日期': str(df_daily.iloc[-1]['trade_date']),
        '捕捞_DIF': round(float(dif), 4),
        '捕捞_DEA': round(float(dea), 4),
        '捕捞_HIST': round(float(hist), 4),
        '捕捞_金叉': bool(biao_golden_cross),
        '捕捞_红柱趋势': bool(biao_red_trend),
        '捕捞_彩柱数': cai_zhu_count,
        '神龙_Red_pct': round(float(red), 2),
        '神龙_Orange_pct': round(float(orange), 2),
        '神龙_Purple_pct': round(float(purple), 2),
        '神龙_红线金叉': bool(shen_long_cross),
        '神龙_红柱上升': bool(shen_red_rising),
        '神龙_套牢比例': round(float(trapped_ratio), 4),
        '股价站上MA20': bool(price_above_ma20),
        'MA20向上': bool(ma20_going_up),
        '量能放大': bool(vol_increasing),
    }


def check_basic(signals):
    if signals is None:
        return False
    return (
        signals['捕捞_金叉'] and
        signals['捕捞_红柱趋势'] and
        signals['捕捞_彩柱数'] >= 2 and
        signals['神龙_红线金叉'] and
        signals['神龙_红柱上升']
    )


def check_advanced(signals):
    if signals is None:
        return False
    return (
        signals['捕捞_金叉'] and
        signals['捕捞_红柱趋势'] and
        signals['捕捞_彩柱数'] >= 2 and
        signals['神龙_红线金叉'] and
        signals['神龙_红柱上升'] and
        signals['神龙_套牢比例'] < 0.5 and
        signals['股价站上MA20'] and
        signals['MA20向上'] and
        signals['量能放大']
    )


def check_sell(signals):
    if signals is None:
        return None
    return {
        '触发卖出3_跌破MA20': not signals['股价站上MA20'] and not signals['MA20向上'],
    }


# ============================================================
# 数据获取
# ============================================================

def get_stock_list():
    """获取沪深全市场股票列表"""
    sh = pro.hs_const(hs_type='SH')
    sz = pro.hs_const(hs_type='SZ')
    df = pd.concat([sh, sz], ignore_index=True)
    # 过滤掉ST和新股（上市不足1年）
    return df['ts_code'].tolist()


def get_daily_data(ts_code, days=120):
    """获取日线数据"""
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
    try:
        df = pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or len(df) < 60:
            return None
        df = df.sort_values('trade_date').reset_index(drop=True)
        return df
    except Exception:
        return None


# ============================================================
# Flask 路由
# ============================================================

@app.route('/')
def index():
    return jsonify({
        'name': '在线选股共振工具 (Tushare Pro)',
        'version': '1.0',
        'endpoints': {
            'GET /': '本信息',
            'POST /api/screen': '执行选股筛选',
            'GET /api/stock/<code>': '查询单只股票信号',
            'GET /api/stocklist': '获取股票列表',
        }
    })


@app.route('/api/screen', methods=['POST'])
def screen_stocks():
    """
    POST body: {"version": "basic|advanced", "limit": 20}
    """
    body = request.get_json() or {}
    version = body.get('version', 'basic')
    limit = min(body.get('limit', 30), 100)

    results = []
    codes = get_stock_list()

    for ts_code in codes:
        if len(results) >= limit:
            break
        try:
            time.sleep(0.2)  # 避免请求过快
            df = get_daily_data(ts_code)
            if df is None:
                continue
            signals = get_stock_signals(df)
            check_fn = check_advanced if version == 'advanced' else check_basic
            if check_fn(signals):
                results.append({
                    'code': ts_code,
                    '信号': signals,
                    '卖出信号': check_sell(signals),
                })
        except Exception:
            continue

    return jsonify({
        'version': version,
        'total_candidates': len(codes),
        'matched_count': len(results),
        'results': results,
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/stock/<code>')
def get_stock_signal(code):
    """
    查询单只股票信号，支持带后缀(.SH/.SZ)和不带后缀
    """
    try:
        # 自动补齐后缀
        c = code.strip()
        if not c.endswith('.SH') and not c.endswith('.SZ'):
            c = c + '.SH' if c.startswith('6') else c + '.SZ'

        df = get_daily_data(c)
        if df is None:
            return jsonify({'error': '数据不足或获取失败'}), 400

        signals = get_stock_signals(df)
        basic_ok = check_basic(signals)
        advanced_ok = check_advanced(signals)

        return jsonify({
            'code': code,
            'ts_code': c,
            '信号': signals,
            '基础版共振': basic_ok,
            '进阶版共振': advanced_ok,
            '卖出信号': check_sell(signals),
            'timestamp': datetime.now().isoformat(),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocklist')
def get_stock_list_api():
    """获取股票列表"""
    try:
        codes = get_stock_list()
        return jsonify({
            'total': len(codes),
            'sample': codes[:20]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('=' * 50)
    print('在线选股共振工具 (Tushare Pro版)')
    print('API地址: http://127.0.0.1:5000')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)

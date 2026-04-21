"""
在线选股共振工具 - Flask API
「捕捞季节 + 神龙筹码」双指标共振筛选
数据源: akshare 免费行情API
"""

from flask import Flask, jsonify, request
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

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
    df = df.sort_values('日期').reset_index(drop=True)
    close = df['收盘'].astype(float)

    ema_short = close.ewm(span=short, adjust=False).mean()
    ema_long = close.ewm(span=long, adjust=False).mean()
    df['DIF'] = ema_short - ema_long
    df['DEA'] = df['DIF'].ewm(span=mid, adjust=False).mean()
    df['HIST'] = 2 * (df['DIF'] - df['DEA'])
    return df


def calc_shenlong_chouma(df, lookback=60):
    """
    神龙筹码指标 (成本分布动量指标)
    基于价格位置与成交量加权计算筹码分布
    红线 = 主力筹码均值 (短期成本)
    橙线 = 中期筹码均值
    紫线 = 长期筹码均值
    """
    df = df.copy()
    df = df.sort_values('日期').reset_index(drop=True)
    close = df['收盘'].astype(float)
    volume = df['成交量'].astype(float)

    # 持仓天数窗口
    windows = [5, 21, 60]

    # 计算筹码成本线 (价格位置加权成交量)
    def cost_line(series, vol, window):
        result = []
        for i in range(len(series)):
            if i < window:
                result.append(np.nan)
            else:
                window_price = series.iloc[i-window:i]
                window_vol = vol.iloc[i-window:i]
                # 资金流向加权成本
                cost = np.sum(window_price * window_vol) / np.sum(window_vol)
                result.append(cost)
        return pd.Series(result, index=series.index)

    df['Red'] = cost_line(close, volume, windows[0])
    df['Orange'] = cost_line(close, volume, windows[1])
    df['Purple'] = cost_line(close, volume, windows[2])

    # 标准化到0-100区间 (相对价格位置)
    for col in ['Red', 'Orange', 'Purple']:
        rolling_min = df[col].rolling(lookback, min_periods=10).min()
        rolling_max = df[col].rolling(lookback, min_periods=10).max()
        rng = rolling_max - rolling_min
        df[col + '_pct'] = np.where(rng > 0, (df[col] - rolling_min) / rng * 100, 50)

    return df


def get_stock_signals(df):
    """
    计算单只股票的指标信号
    返回最近N个交易日的信号状态
    """
    if len(df) < 60:
        return None

    # 计算指标
    df_biao = calc_biaoaojiji(df)
    df_shen = calc_shenlong_chouma(df)

    # 合并
    df_merged = df_biao.join(df_shen[['Red', 'Orange', 'Purple', 'Red_pct', 'Orange_pct', 'Purple_pct']], how='left')

    last = df_merged.iloc[-1]
    prev = df_merged.iloc[-2]

    # ========================
    # 捕捞季节信号
    # ========================
    dif, dea = last['DIF'], last['DEA']
    dif_prev, dea_prev = prev['DIF'], prev['DEA']
    hist = last['HIST']

    # 金叉: DIF从下方穿过DEA
    biao_golden_cross = (dif_prev <= dea_prev) and (dif > dea)
    # 红柱趋势 (HIST > 0)
    biao_red_trend = hist > 0
    # 彩柱数 (HIST连续为正的天数)
    hist_series = df_merged['HIST'].tail(20)
    cai_zhu_count = 0
    for v in reversed(hist_series.values):
        if v > 0:
            cai_zhu_count += 1
        else:
            break

    # ========================
    # 神龙筹码信号
    # ========================
    red, orange, purple = last['Red_pct'], last['Orange_pct'], last['Purple_pct']
    red_prev, orange_prev = prev['Red_pct'], prev['Orange_pct']

    # 红线上穿橙线/紫线
    shen_long_cross = (red_prev <= orange_prev and red > orange) or \
                       (red_prev <= last['Purple_pct'] and red > last['Purple_pct'])
    # 红柱上升区间 (筹码集中度上升)
    shen_red_rising = red > orange and red > purple
    # 平均套牢比例 (橙线和紫线在红线上方越多，套牢越重)
    trapped_ratio = np.mean([max(0, orange - red), max(0, purple - red)]) / 100

    # ========================
    # 均线位置
    # ========================
    close = df['收盘'].astype(float)
    ma20 = close.rolling(20).mean().iloc[-1]
    ma20_prev = close.rolling(20).mean().iloc[-2]
    price_above_ma20 = close.iloc[-1] > ma20
    ma20_going_up = ma20 > ma20_prev

    # ========================
    # 量能
    # ========================
    vol = df['成交量'].astype(float)
    vol_ma3 = vol.tail(3).mean()
    vol_ma5 = vol.tail(5).mean()
    vol_increasing = vol_ma3 > vol_ma5

    return {
        # 基础数据
        '最新价': round(float(close.iloc[-1]), 2),
        '日期': str(df.iloc[-1]['日期']) if '日期' in df.columns else '',
        # 捕捞季节
        '捕捞_DIF': round(float(dif), 4),
        '捕捞_DEA': round(float(dea), 4),
        '捕捞_HIST': round(float(hist), 4),
        '捕捞_金叉': biao_golden_cross,
        '捕捞_红柱趋势': biao_red_trend,
        '捕捞_彩柱数': cai_zhu_count,
        # 神龙筹码
        '神龙_Red_pct': round(float(red), 2),
        '神龙_Orange_pct': round(float(orange), 2),
        '神龙_Purple_pct': round(float(purple), 2),
        '神龙_红线金叉': shen_long_cross,
        '神龙_红柱上升': shen_red_rising,
        '神龙_套牢比例': round(float(trapped_ratio), 4),
        # 均线
        '股价站上MA20': price_above_ma20,
        'MA20向上': ma20_going_up,
        # 量能
        '量能放大': vol_increasing,
    }


def check_basic_conditions(signals):
    """基础版选股条件"""
    if signals is None:
        return False
    return (
        signals['捕捞_金叉'] and
        signals['捕捞_红柱趋势'] and
        signals['捕捞_彩柱数'] >= 2 and
        signals['神龙_红线金叉'] and
        signals['神龙_红柱上升']
    )


def check_advanced_conditions(signals):
    """进阶版选股条件"""
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


def check_sell_conditions(signals):
    """卖出条件检测"""
    if signals is None:
        return None
    # 死叉信号在 prev 行判断
    # 这里简化处理，实际需要更完整的逻辑
    return {
        '触发卖出1_捕捞死叉绿柱放大': False,  # 需要历史数据对比
        '触发卖出2_神龙红线死叉': False,
        '触发卖出3_跌破MA20': not signals['股价站上MA20'] and not signals['MA20向上'],
    }


# ============================================================
# Flask 路由
# ============================================================

@app.route('/')
def index():
    return jsonify({
        'name': '在线选股共振工具',
        'version': '1.0',
        'endpoints': {
            '/api/screen': 'POST - 执行选股筛选',
            '/api/stock/<code>': 'GET - 查询单只股票信号',
            '/api/stocklist': 'GET - 获取股票列表',
        }
    })


@app.route('/api/screen', methods=['POST'])
def screen_stocks():
    """
    执行选股筛选
    POST body: {"version": "basic|advanced", "pool": "all|a|gem|hs300|zz500", "limit": 20}
    """
    body = request.get_json() or {}
    version = body.get('version', 'basic')  # basic or advanced
    pool = body.get('pool', 'all')  # all, a, gem, hs300, zz500
    limit = min(body.get('limit', 30), 100)

    results = []

    try:
        # 获取股票列表
        if pool == 'hs300':
            df_list = ak.stock_hs300_component_em()
            codes = df_list['代码'].tolist()[:100]
        elif pool == 'zz500':
            df_list = ak.stock_zz500_component_em()
            codes = df_list['代码'].tolist()[:100]
        elif pool == 'gem':
            # 创业板
            stock_info_a_code_name_em_df = ak.stock_info_a_code_name_em()
            codes = stock_info_a_code_name_em_df[
                stock_info_a_code_name_em_df['板块'] == '创业板'
            ]['代码'].tolist()[:200]
        else:
            # 全A股
            stock_info_a_code_name_em_df = ak.stock_info_a_code_name_em()
            codes = stock_info_a_code_name_em_df['代码'].tolist()[:500]

        matched_count = 0
        for code in codes:
            if matched_count >= limit:
                break
            try:
                symbol = code if code.startswith('6') else '0' + code
                time.sleep(0.15)  # 避免请求过快
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period='daily',
                    start_date=(datetime.now() - timedelta(days=120)).strftime('%Y%m%d'),
                    end_date=datetime.now().strftime('%Y%m%d'),
                    adjust='qfq'
                )
                if df is None or len(df) < 60:
                    continue
                df.columns = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
                signals = get_stock_signals(df)

                check_fn = check_advanced_conditions if version == 'advanced' else check_basic_conditions
                if check_fn(signals):
                    sell = check_sell_conditions(signals)
                    results.append({
                        '代码': code,
                        '信号': signals,
                        '卖出信号': sell,
                    })
                    matched_count += 1

            except Exception as e:
                continue

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'version': version,
        'pool': pool,
        'matched_count': len(results),
        'results': results,
        'timestamp': datetime.now().isoformat(),
    })


@app.route('/api/stock/<code>')
def get_stock_signal(code):
    """
    查询单只股票的详细指标信号
    """
    try:
        symbol = code if code.startswith('6') else '0' + code
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period='daily',
            start_date=(datetime.now() - timedelta(days=120)).strftime('%Y%m%d'),
            end_date=datetime.now().strftime('%Y%m%d'),
            adjust='qfq'
        )
        if df is None or len(df) < 60:
            return jsonify({'error': '数据不足'}), 400

        df.columns = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
        signals = get_stock_signals(df)
        sell = check_sell_conditions(signals)

        # 基础版 & 进阶版判定
        basic_ok = check_basic_conditions(signals)
        advanced_ok = check_advanced_conditions(signals)

        return jsonify({
            'code': code,
            '信号': signals,
            '基础版共振': basic_ok,
            '进阶版共振': advanced_ok,
            '卖出信号': sell,
            'timestamp': datetime.now().isoformat(),
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/stocklist')
def get_stock_list():
    """
    获取股票列表（简略信息）
    """
    try:
        stock_info_a_code_name_em_df = ak.stock_info_a_code_name_em()
        return jsonify({
            'total': len(stock_info_a_code_name_em_df),
            'sample': stock_info_a_code_name_em_df.head(20).to_dict('records')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print('=' * 50)
    print('在线选股共振工具已启动')
    print('API地址: http://127.0.0.1:5000')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)

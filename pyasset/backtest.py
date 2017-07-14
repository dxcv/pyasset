# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        backtest
# Purpose:     
# Author:      JFYU 
# Email:       jfyu@zju.edu.cn
# Created:     2016/8/2 15:38
#
# Copyright 2016 Jianfeng Yu
#
# -------------------------------------------------------------------------------

import numpy as np
import pandas as pd
from pyasset import analyser as als


# # get data
# DB = pd.HDFStore('DB_index.hdf')
# macro_index = DB['macro_index']
# DB.close()
#
# SHIBOR = macro_index['SHIBOR']
# SHIBOR = pow(1 + (SHIBOR / 100), 1/250) -1


class Backtest:
    def __init__(self, weight: pd.DataFrame, quote:pd.DataFrame, start_date=None, end_date=None,
                 fee_rate=0.003):
        self._quote = quote
        self._weight = weight
        self._start = start_date
        self._end = end_date
        self._fee_rate = fee_rate

        self.res_nv = None
        self.res_weight = None
        self.res_turnover = None
        self.res_report = {}


    def run(self):
        nv, wt, to = backtest_fund_index(self._weight, self._quote,self._start, self._end, self._fee_rate)
        self.res_nv = nv
        self.res_weight = wt
        self.res_turnover = to

    def analyze(self, freq='D', rf=None):
        self.run()
        annal_ret = als.cal_annal_return(self.res_nv, freq=freq)
        annal_vol = als.cal_annal_volatility(self.res_nv, freq=freq)
        max_dd, mdd_sdt, mdd_edt, mdd_range, daily_dd = als.cal_max_drawdown_info(self.res_nv)
        sharpe = als.cal_sharpe(self.res_nv, rf=rf, freq=freq)
        to_average = self.res_turnover.mean()
        max_wait_days = als.cal_max_wait_periods(self.res_nv)

        self.daily_dd = daily_dd
        self.res_report = {
            "Annal ret" : '{0:.2%}'.format(annal_ret), "Annal vol": '{0:.2%}'.format(annal_vol), "Max Drawdown": '{0:.2%}'.format(max_dd),
            "IR": '{0:.2}'.format(sharpe), "Average turnover": '{0:.2%}'.format(to_average), "Mdd_start": mdd_sdt,
            "Mdd_end": mdd_edt, "Mdd_range": '{0} Days'.format(mdd_range), "Max_wait": '{0} Days'.format(max_wait_days)
        }
        return pd.DataFrame(self.res_report, index=['value']).T.sort_index()




def backtest_fund_index(weight: pd.DataFrame, quote: pd.DataFrame,
                        start_date='2010-01-01', end_date='2016-01-01', fee_rate=0.003):
    """
    利用收益行情进行回测


    Parameters
    ----------
    weight
        调仓权重

    quote
        收益行情

    start_date
        起始日

    end_date
        终止日

    fee_rate
        手续费率

    Returns
    -------
    re, wt, to  收益、权重、换手率

    """

    # if initial_weight is None:
    #     initial_weight = np.ones(weight.shape[1])
    #     initial_weight = initial_weight / sum(initial_weight)
    #
    # elif initial_weight == 'begin':
    #     start_date = pd.datetime.strftime(weight.index[0], '%Y-%m-%d')
    # else:
    #     raise("The type of initial_weight is not supported!")

    if start_date is None:
        s_t = pd.datetime.strftime(weight.index[0], '%Y-%m-%d')
        initial_weight = weight[s_t:s_t].values[0]
    else:
        s_t = start_date
        initial_weight = np.ones(weight.shape[1])
        initial_weight = np.array(initial_weight / sum(initial_weight))

    e_t = end_date

    # 截取需要的行情
    quote_daily = quote[s_t:e_t]
    weight_daily = weight.reindex(quote_daily.index)

    quote_daily = quote_daily.T
    weight_daily = weight_daily.T

    # 先计算每日的资金权重，再乘以每日的收益，得到日收益率，再在时间序列上加总
    asset_weight = []
    re_daily = []
    turn_over = []
    for day in weight_daily.columns:

        if day == weight_daily.columns[0]: # 初始权重
            weight_tmp = initial_weight
            asset_weight.append((day, weight_tmp))
            re_daily.append((day,0))
            continue


        if weight_daily[day].count() == 0: # 不调仓
            # re_daily_tmp = weight_tmp.dot(quote_daily[day] + 1)/ np.sum(weight_tmp) - 1
            re_daily_tmp = weight_tmp.dot(quote_daily[day])

            weight_tmp = weight_tmp * (quote_daily[day] + 1) # 更新权重变化
            weight_tmp = weight_tmp / np.sum(weight_tmp)     # 将权重初始化为1

            re_daily.append((day, re_daily_tmp))
            asset_weight.append((day, np.array(weight_tmp)))

        else: # 开盘调仓
            turn_over_tmp = np.sum(np.abs(weight_tmp - weight_daily[day]))
            weight_tmp = weight_daily[day]
            re_daily_tmp = weight_tmp.dot(quote_daily[day] + 1)/ np.sum(weight_tmp) - 1

            # 扣除交易摩擦，假定千三
            re_daily_tmp = re_daily_tmp - fee_rate * turn_over_tmp

            re_daily.append((day, re_daily_tmp))
            asset_weight.append((day, np.array(weight_tmp)))
            turn_over.append((day, turn_over_tmp))

    # 组成持仓和收益 DataFrame
    re = pd.Series([a[1] for a in re_daily], index=[a[0] for a in re_daily])

    # 注意记录的权重为每日收盘权重
    wt = pd.DataFrame([a[1] for a in asset_weight], index=[a[0] for a in asset_weight], columns=weight.columns)

    to = pd.Series([a[1] for a in turn_over], index=[a[0] for a in turn_over])

    # 净值序列
    nv = (re + 1).cumprod()

    # dt_range = pd.period_range(nv.index[0], nv.index[-1])
    # annal_re = pow ( nv.ix[len(nv)-1] / nv.ix[0], 365 / len(dt_range)) - 1
    # max_dd = max_drawdown(nv)
    # IR = re.mean() / re.std() * np.sqrt(250)
    #
    # # rf = SHIBOR.reindex(re.index)
    # SHARPE = (re ).mean() / (re ).std() * np.sqrt(250)
    # Average_turn_over = to.mean()
    #
    # res = {'return': re, 'weight': wt, 'turn_over': to, 'annal_return': annal_re, 'annal_std': re.std()* np.sqrt(250),
    #        'max_dd': max_dd, 'IR': IR, 'Average_turn_over': Average_turn_over, 'Sharpe': SHARPE, 'net_value': nv}

    return nv, wt, to













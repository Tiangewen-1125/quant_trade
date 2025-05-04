from .account_statistics import * 
import pandas as pd
from datetime import datetime, time
import holidays
from get_args import args
from get_data import DataQuery


def get_trade_day(start_date,end_date):
    tradeday_list = []
    current_date = start_date
    cn_holidays = holidays.China(years = list(range(start_date.year,end_date.year + 1)))
    while current_date <= end_date:
        if current_date.weekday() not in (5,6) and current_date not in cn_holidays:
            tradeday_list.append(current_date)
        current_date += timedelta(days=1)
    return tradeday_list

def signal2dir(signal):
    sig2dir = {1.0:'long',-1.0:'short',0.0:None}
    return sig2dir[signal]

class TradeOrder:
    '''
    成交报单类
    '''
    def __init__(self,signal,prices,code,stop_loss,n_shares):
        self.signal = signal.tolist()
        time = signal.index.tolist()
        self.time = [datetime.strptime(t,'%Y-%m-%d') for t in time]
        self.prices = prices.tolist()
        self.code = code
        self.stop_loss = stop_loss
        self.shares = n_shares


class trade_simulation:
    def __init__(self,account: acc_stats,):
        # mode指回测或实盘模拟
        self.account = account

    def backtest(self,start_time,end_time,trade_order):
        # 确认需要每日结算的交易日区间
        if start_time.time() >= time(21,0,0):
            # start_time.date()无须结算balance
            start_date = start_time.date() + timedelta(days = 1)
        else:
            start_date = start_time.date()
        if end_time.time() <= time(15,0,0):
            # end_time.date()无须结算balance
            end_date = end_time.date() - timedelta(days = 1)
        else:
            end_date = end_time.date()


        # 获取[start_date,end_date]之间所有的交易日
        trade_days = get_trade_day(start_date,end_date)
    

        # 每日权益，字典，key为日期，value为当日账户权益
        daily_balances = {}

        # 交易日（结算日）的索引、交易信号的索引、交易日期（结算日期）
        no_day,index_signal = 0,0
        day = trade_days[no_day]
        # 外层按照交易日循环，便于逐日盯视
        if_stop_loss = False

        while no_day < len(trade_days):
            day = trade_days[no_day]

            # 对现有持仓止损
            if not if_stop_loss:
                data_query = DataQuery(trade_order.code, **args.query_config)
                open_price, high_price, low_price, close_price = data_query.open_price[index_signal], \
                                                                    data_query.high_price[index_signal], \
                                                                    data_query.low_price[index_signal], data_query.close_price[index_signal]

                if_stop_loss,origin_dir = self.account.do_stop_loss(trade_order.time[index_signal],trade_order.code,\
                                                                    open_price,high_price,low_price,close_price)
                
        
            # 当天发生交易
            cur_time,signal,price = trade_order.time[index_signal],trade_order.signal[index_signal],\
                trade_order.prices[index_signal]
            while cur_time.date() <= day:
                # 如果之前发生了止损，且止损时仓位方向和信号一样，跳过该交易信号不执行
                if signal != signal:
                    # 按照交易信号往前遍历
                    index_signal += 1
                    if index_signal == len(trade_order.signal):
                        break
                    cur_time,signal,price = trade_order.time[index_signal],trade_order.signal[index_signal],\
                        trade_order.prices[index_signal]
                    continue
                # 正常执行交易信号，拨回是否发生止损状态
                n,dir = self.account.get_position_by_code(trade_order.code)
                # 当前账户标的合约无持仓，且交易信号不为空仓
                if dir is None and signal and (not if_stop_loss or signal2dir(signal) != origin_dir):
                    for _ in range(trade_order.shares):
                        self.account.open_pos(trade_order.code,price,signal2dir(signal),trade_order.stop_loss,cur_time)
                    if_stop_loss = False
                # 当前持仓和信号方向不一致，一定会要先平仓，平仓方向和持仓相反；如果信号方向不是0，则开仓，开仓的方向和平仓方向一致
                elif dir != signal2dir(signal):
                    close_dir = 'long' if dir == 'short' else 'short'
                    for _ in range(n):
                        target_trade = self.account.get_target_close_trade(trade_order.code,close_dir)
                        self.account.close_pos(trade_order.code,price,close_dir,target_trade,cur_time)
                    if signal and (not if_stop_loss or signal2dir(signal) != origin_dir):
                        for _ in range(trade_order.shares):
                            self.account.open_pos(trade_order.code,price,close_dir,trade_order.stop_loss,cur_time)
                        if_stop_loss = False
                # 按照交易信号往前遍历
                index_signal += 1
                if index_signal == len(trade_order.signal):
                    break
                cur_time,signal,price = trade_order.time[index_signal],trade_order.signal[index_signal],\
                    trade_order.prices[index_signal]

            # 当天盯市结算
            self.account.MTM(args.margin_call,str(day)[:10])
            daily_balances[day] = {'balance':self.account.balance}
            no_day += 1
  
        return daily_balances

    def calc_performances(self,start_time,end_time,trade_order,n_tradeday = 250,risk_free_rate = 0.04):

        daily_balances = self.backtest(start_time,end_time,trade_order)

        pnl = pd.DataFrame.from_dict(daily_balances,orient = 'index')
        pnl.sort_index(inplace = True)
        # 根据pnl计算年化收益、夏普比率、最大回撤
        pnl['daily_profit'] = pnl['balance'].diff()
        annual_ret = pnl['daily_profit'].mean()/self.account.init_bal * n_tradeday
        annual_vol = (pnl['daily_profit']/self.account.init_bal).std() * n_tradeday ** 0.5
        sharpe_ratio = (annual_ret - risk_free_rate) / annual_vol
        max_drawdown = max(1 - pnl['balance']/pnl['balance'].cummax())
        
        # 根据所有成交单计算胜率
        n_trades,n_win_trades = 0,0 
        gain,loss = 0,0
        for code,trades in self.account.close_trade_items.items():
            n_trades += len(trades)
            for trade in trades:
                profit = trade.get_profits()
                if profit > 0:
                    n_win_trades += 1
                    gain += profit
                elif profit < 0:
                    loss -= profit
        winning_rat, profit2loss = n_win_trades/n_trades, gain/loss
        
        print(f'用户{self.account.usr}本次模拟的年化收益：{f"{annual_ret:.2%}"}，夏普：{round(sharpe_ratio,2)}，最大回撤：{f"{max_drawdown:.2%}"}，胜率：{f"{winning_rat:.2%}"}，盈亏比：{round(profit2loss,2)}')

        
                


    
           








            

            

                

                    

                    

            

        

    



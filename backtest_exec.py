from get_args import args
from core.simulation import trade_simulation, TradeOrder, acc_stats
from signals import get_signal
from get_data import DataQuery
from datetime import datetime

if __name__ == '__main__':
    ### 测试账户创建 ###
    test_account = acc_stats(args.usr_name,args.init_fund)
    print('new account successfully created')
    
    ### 根据收盘价生成的信号（当日3点后出），最早只能用开盘价交易
    data_query = DataQuery(args.code,**args.query_config)
    signal = get_signal(args.trade_strategy, args.config, data_query, )

    simu = trade_simulation(test_account)
    start_time,end_time = datetime.strptime(args.start_time,'%Y-%m-%d'),datetime.strptime(args.end_time,'%Y-%m-%d')

    trade_order = TradeOrder(signal,data_query.target_price,args.code,args.stop_loss,args.shares)
    simu.calc_performances(start_time,end_time,trade_order)

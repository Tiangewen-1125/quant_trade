import os
import logging
#LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
from collections import deque
from .utils import get_log_name
import pandas as pd
from get_args import args
from get_data import get_contract_info,DataQuery
from datetime import time,timedelta


class contracts:
    def __init__(self,code):
        ###基于合约代码构造实例####
        self.code = code
        self.contract_info = get_contract_info(code)
        for key,value in self.contract_info.items():
            setattr(self,key,value)
        
    def calc_margin(self,open_price):
        ###计算保证金占用###
        return self.margin * self.times if self.margin_type == 'fixed' else open_price * self.times * self.margin_ratio
    
    def calc_commission(self,price):
        ###计算给定金额交易下的手续费###
        return price * self.times * self.commission_rate if self.commission_type == 'float' else self.commission_fee * self.times


class trade_items:
    '''
    TODO：应该是单例？？
    '''
    def __init__(self,code:str,open_price:float,direction:str,stop_loss:tuple,open_time):
        # 生成一笔交易单号：用交易所或者自己生成
        # 记录开仓时间
        self.open_time = open_time
        # 开仓时新建一笔交易单实例
        self.code = code
        self.contract = contracts(self.code)
        self.open_price = open_price
        self.prev_set_price = open_price
        self.direction = direction
        # 保证金占用
        self.margin = self.contract.calc_margin(self.open_price)
        # 开仓手续费
        self.commission = self.get_trade_commission(open_price)
        # 交易盈利
        self.profit = 0
        # 该笔交易止损点
        type,ratio,point = stop_loss
        if type == 'fixed':
            self.stop_loss_point = point
        elif type == 'float':
            if self.direction == 'short':
                self.stop_loss_point = open_price * (1 + ratio)
            elif self.direction == 'long':
                self.stop_loss_point = open_price * (1 - ratio)
    
    def get_margin(self):
        return self.margin

    def get_trade_commission(self,price):
        ## 区分开平仓动作下的手续费，只和交易价格相关
        ## TODO:手续费可能单/双边，固定/浮动收取
        return self.contract.calc_commission(price)
    
    def get_profits(self):
        return self.profit

    def close_trade(self,close_price,direction):
        if direction == self.direction:
            raise ValueError(f'平仓方向不对：当前合约{self.code}持仓为{self.direction}，不支持{direction}的平仓动作')
        if self.direction == 'short':
            self.profit += (self.open_price - close_price) * self.contract.contract_info['times']
        elif self.direction == 'long':
            self.profit += (close_price - self.open_price) * self.contract.contract_info['times']
        # 账户中平仓动作清零保证金必须在此之前
        self.margin = 0
        self.commission += self.get_trade_commission(close_price)

        
class acc_stats:
    def __init__(self,usr_name,init_funds):
        self.usr = usr_name
        # 流动资金和权益，权益和现金的不同发生在逐日盯市和交易结算时
        self.init_bal = init_funds
        self.balance = init_funds
        self.funds = init_funds
###创建账户之后每笔交易单，字典key为合约名，value为该合约下的未平仓交易###
        self.open_trade_items = {}
###已平仓交易单
        self.close_trade_items = {}
        #记录日志
        dir = args.log_dir
        if not os.path.exists(dir):
            os.makedirs(dir)
        logging.basicConfig(filename=os.path.join(dir,get_log_name(usr_name)), level=logging.DEBUG)
        logging.info(f"用户{self.usr}已注册，初始资金为{init_funds}")
    
    def gain_by_category(self):
        gains = {}
        ### 统计各品种历史交易的盈利情况
        for contract,trade in self.close_trade_items.items():
            category = get_cat_from_contract_code(contract)
            profit = trade.get_profits()
            if category in gains:
                gains[category] += profit
            else:
                gains[category] = profit
        return gains

    def get_total_margin(self):
        '''
        账户总保证金占用
        '''
        total_margin = 0
        for _,trades in self.open_trade_items.items():
            for trade in trades:
                total_margin += trade.margin
        return total_margin
    
    def get_position_by_code(self,code):
        '''
        获取当前账户某个合约的持仓状况
        账户中不允许对同一个标的合约，同时具有多头和空头持仓
        '''
        if code not in self.open_trade_items: 
            return 0,None
        n = len(self.open_trade_items[code])
        if n == 0: 
            direction = None
        else: 
            direction = self.open_trade_items[code][0].direction
        return n,direction


    def open_pos(self,code:str,price:float,direction:str,stop_loss:tuple,time):
        # 判断能否开仓
        trade_item = trade_items(code,price,direction,stop_loss,time)
        if self.funds < (trade_item.get_margin() + trade_item.get_trade_commission(price)) :
            logging.error(f'{time}流动资金{self.funds}不足以开仓！')
            raise ValueError(f'{time}流动资金{self.funds}不足以开仓！')
        margin,commission_fee = trade_item.get_margin(),trade_item.get_trade_commission(price) 
        self.funds -= margin + commission_fee
        self.balance -= commission_fee
        if code in self.open_trade_items:
            self.open_trade_items[code].append(trade_item)
        else:
            self.open_trade_items[code] = deque([trade_item])
        ###TODO:记录日志###
        logging.info(f'交易日{time}，合约{code}开仓1手，方向为{direction}，开仓价为{price}，手续费为{commission_fee}，保证金占用{margin}')
        logging.info(f'账户权益为{self.balance}，当前账户流动资金为{self.funds}')

    def get_target_close_trade(self,code,direction):
        '''
        依据信号平仓（非止损平仓）
        找平仓单的时候，顺便就把self.open_trade_items修改了
        '''
        ### 首先找出要平仓的交易单
        if len(self.open_trade_items[code]) == 0:
            logging.error(f'当前没有合约{code}的持仓！')
            raise KeyError(f'当前没有合约{code}的持仓！')
        tmp_open_trade = self.open_trade_items[code].popleft()
        return tmp_open_trade
        

    # 平仓
    def close_pos(self,code,price,direction,target_trade,time):
        '''
        对指定的某笔交易target_trade平仓
        '''
        margin,commission_fee = target_trade.get_margin(),target_trade.get_trade_commission(price)
        self.funds += margin - commission_fee
        target_trade.close_trade(price,direction)
        profit = target_trade.get_profits()
        self.funds += profit

        if direction == 'long':
            self.balance += (target_trade.prev_set_price - price) * target_trade.contract.contract_info['times']
        elif direction == 'short':
            self.balance += (price - target_trade.prev_set_price) * target_trade.contract.contract_info['times']
            
        self.balance -= commission_fee
        if code in self.close_trade_items:
            self.close_trade_items[code].append(target_trade)
        else:
            self.close_trade_items[code] = deque([target_trade])
        
        #### 记录交易日志
        logging.info(f'交易日{time}，合约{code}平仓1手，方向为{direction}，平仓价为{price}，该笔交易盈利{profit}，手续费为{commission_fee}')
        logging.info(f'当前账户权益为{self.balance}，账户流动资金为{self.funds}')

    
    # 逐日盯市函数
    def MTM(self,limit,cur_trade_day):
        ### TODO:是否需要追加保证金判断
        for contract,trades in self.open_trade_items.items():
            data_query = DataQuery(contract,**args.query_config)
            settle_price = data_query.settle_price.loc[cur_trade_day]
            for trade in trades:
                if trade.direction == 'long':
                    self.balance += (settle_price - trade.prev_set_price) * trade.contract.contract_info['times']
                    trade.prev_set_price = settle_price
                elif trade.direction == 'short':
                    self.balance += (trade.prev_set_price - settle_price) * trade.contract.contract_info['times']
                    trade.prev_set_price = settle_price
        ###日志记录逐日盯市后结算的账户权益
        logging.info(f'交易日{cur_trade_day}的账户权益为{self.balance}，流动资金为{self.funds}，总保证金占用为{self.get_total_margin()}')
        if self.balance < limit:
            logging.warning(f'账户权益为{self.balance}，已低于最低要求{limit}，请追加保证金！')

    # 止损函数
    def do_stop_loss(self,time,contract,*ohlc):
        '''
        默认按照开盘价开仓，判断止损标准分别依据非当天的开盘价、高/低价和收盘价是否触及止损点
        '''
        open_price,high_price,low_price,close_price = ohlc

        # 之前还没信号的时候，直接跳过，不必止损
        if contract not in self.open_trade_items:
            return False,None
        # 找到当前需要止损的第一单
        tmp_trade_list, = [],
        flag,direction = False,None
        while len(self.open_trade_items[contract]):
            trade = self.open_trade_items[contract].popleft()
            
            # 检查触发多头止损
            long_stop_loss = trade.direction == 'long' and ((trade.open_time.date() < time.date() and\
                            open_price <= trade.stop_loss_point) or min(close_price,low_price) <=\
                            trade.stop_loss_point)
            
            # 检查触发空头止损
            short_stop_loss = trade.direction == 'short' and ((trade.open_time.date() < time.date() and\
                            open_price >= trade.stop_loss_point) or max(close_price,high_price) >=\
                            trade.stop_loss_point)
            
            if long_stop_loss:
                self.close_pos(contract,trade.stop_loss_point,'short',trade,time)
                while len(tmp_trade_list):
                    self.open_trade_items[contract].appendleft(tmp_trade_list.pop())
                flag,direction = True,'long'
            elif short_stop_loss:
                self.close_pos(contract,trade.stop_loss_point,'long',trade,time)
                while len(tmp_trade_list):
                    self.open_trade_items[contract].appendleft(tmp_trade_list.pop())
                flag,direction = True,'short'
            # 本单未触发止损
            else:
                tmp_trade_list.append(trade)

        while len(tmp_trade_list):
            self.open_trade_items[contract].appendleft(tmp_trade_list.pop())

        return flag,direction # 当日标的合约是否发生了止损，什么信号时发生的止损
                                            
        

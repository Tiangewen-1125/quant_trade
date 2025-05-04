import pandas as pd


# 获取合约信息、价格数据等，无论是通过本地文件还是外部接口，逻辑都独立出来
contract_info_list = {'A1301.XDCE':{'margin_type':'float','margin_ratio':0.07,'margin':None,'commission_type':'fixed','commission_fee':2.0,'commission_rate':None,'times':10}}
# 待改，需要和args抽离开，只与code相关，出于性能考虑或改为数据库逻辑
from get_args import args
price_df = pd.read_csv(args.price_csv,index_col = args.time_col)

def get_contract_info(code):
    return contract_info_list[code]

# 待改！！
def get_price_by_code(code):
    return price_df


class DataQuery:
    def __init__(self,code: str,**config):
        self.code = code  # 合约代码
        self.price = get_price_by_code(code) # 完整的单合约的价格序列，符合一般量价数据格式，包括开收高低、结算价等
        # config为一套数据查询格式，类似标的价格的列名
        self.query_config = config
        self.target_price, self.settle_price = list(map(lambda key: self._get_price_by_key(key),["target","settle"]))
        self.open_price, self.high_price, self.low_price, = list(map(lambda key: self._get_price_by_key(key).tolist(),["open","high","low",])) 
        self.close_price = self.target_price.tolist()

    def _get_price_by_key(self,key: str):
        return self.price[self.query_config.get(key,"no_this_name")]



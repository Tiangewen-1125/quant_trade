from datetime import datetime
# def is_within_same_tradeday(time1,time2):
#     # 判断两个时间点是否在同一个交易日
#     day_start_time,day_end_time,night_start_time,night_end_time = time(9,0,0),time(15,0,0),time(21,0,0),time(3,0,0)
#     date1,date2 = time1.date(),time2.date()
#     # 判断是否在同一交易日的日盘、21.-24.、0.-3.
#     if date1 == date2:
#         if (day_start_time <= time1.time() < day_end_time) and (day_start_time <= time2.time() < day_end_time):
#             return True
#         if (night_start_time <= time1.time() <= time(23,59,59)) and (night_start_time <= time2.time() <= time(23,59,59)):
#             return True
#         if (time(0,0,0) <= time1.time() < night_end_time) and (time(0,0,0) <= time2.time() < night_end_time):
#             return True
#     # 判断是否在同一交易日的夜盘
#     if date2 == date1 + timedelta(days = 1):
#         if (night_start_time <= time1.time() <= time(23,59,59)) and (time(0,0,0) <= time2.time() < night_end_time):
#             return True
#     return False

def get_log_name(usr_name):
    return 'trade-'+ str(datetime.today())[:19].replace(' ','').replace('-','').replace(':','') + '-' + usr_name +'.log'

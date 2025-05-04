#!/bin/bash

export PYTHONDONTWRITEBYTECODE=1

usr_name=demo

init_fund=1000000
open_code=A1301.XDCE

n_shares=100

# 数据读取
file_name=datasets/price.csv
open_col=open
close_col=close

log_path=logs
mkdir $log_path

python backtest_exec.py \
	--usr_name ${usr_name} \
	--init_fund $init_fund \
	--code $open_code \
	--shares $n_shares \
	--price_csv $file_name \
	--time_col 'Unnamed: 0' \
	--start_time 2011-07-15 \
	--source $close_col \
	--end_time 2013-01-16 \
	--log_dir $log_path \
	--trade_strategy dma \
	--stop_loss float 0.1 None \

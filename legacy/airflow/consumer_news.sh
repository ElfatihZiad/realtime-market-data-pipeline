#!/bin/bash
cd
cd /home/ziad/stock_data_pipeline/pipeline
python -c 'from warehouse import main_realtime_news; main_realtime_news()'


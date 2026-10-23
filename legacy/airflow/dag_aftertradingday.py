#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import datetime as dt

from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator


default_args = {
    'owner': 'airflow',
    'start_date': dt.datetime(2019, 8, 5, 10, 00, 00),
    'concurrency': 1,
    'retries': 0
}



with DAG('stock_data_pipeline',
         default_args=default_args,
         schedule_interval='0 22 * * *',
         ) as dag:
    first = BashOperator(task_id='AfterTrading',
                             bash_command='./aftertrading.sh')


first





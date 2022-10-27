# A real-time financial data streaming pipeline and visualization platform

# Introduction

This repo shows my project about real-time stock data pipeline. All the code is written in PYTHON. In this project, I play with various Data Engineering
frameworks to develop a financial data processing and visualization platform using ***Apache Kafka***, ***Apache Cassandra***, and ***Bokeh***. I used Kafka for realtime stock price and market news streaming, Cassandra for historical and realtime stock data warehousing, and Bokeh for visualization on web browsers. I also wrote a web crawler to scrape companys' financial statements and basic information from Yahoo Finance, and played with various economy data APIs. 



# Architecture

There are currently 3 tabs in the webpage:

- ***Stock: Streaming & Fundamental*** 
  - Single stock's candlestick plot, basic company & financial information;
  - Realtime S&P500 price during trading hours (*fake date* during non-trading hours)
- ***Stock: Comparison***
  - 2 user-selected stocks' price, and their statstical summay and correlation
  - 5,10,30-day moving average of adjusted close price
- ***Economy***
  - Geomap of various economy data by state
  - 4 economy indicators nationwide for comparison
  - The most recent market news 

&nbsp;


Here is the architecture of the platform.

<img src="https://github.com/ElfatihZiad/realtime-market-data-pipeline/blob/main/images/pipeline.png?raw=true" width="900" />

Please check each tab's screenshot:


**Tab 1:**

<img src="https://github.com/ElfatihZiad/realtime-market-data-pipeline/blob/main/images/tab1.gif" width="800" />


**Tab 2:**

<img src="https://github.com/ElfatihZiad/realtime-market-data-pipeline/blob/main/images/tab2.gif" width="800" />


**Tab 3:**

<img src="https://github.com/ElfatihZiad/realtime-market-data-pipeline/blob/main/images/tab3.gif" width="800" />

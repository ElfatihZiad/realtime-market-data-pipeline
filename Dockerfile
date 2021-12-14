FROM ubuntu:latest
RUN apt https_proxy=http://10.23.201.11:3128/ update 
RUN apt-get upgrade
RUN apt-get install -y wget bzip2 sudo
RUN apt-get install -y emacs nano vim default-jre
RUN apt-get install openjdk-8-jre-headless

RUN adduser --disabled-password --gecos '' ziad
RUN adduser ziad sudo
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

USER ziad
WORKDIR /home/ziad/

RUN sudo chmod a+rwx -R /home/ziad/
 
RUN wget https://repo.anaconda.com/archive/Anaconda3-2019.07-Linux-x86_64.sh
RUN bash Anaconda3-2019.07-Linux-x86_64.sh -b
RUN rm Anaconda3-2019.07-Linux-x86_64.sh
ENV PATH /home/ziad/anaconda3/bin:$PATH

RUN pip install --upgrade pip

RUN jupyter notebook --generate-config --allow-root

 
RUN wget https://archive.apache.org/dist/zookeeper/zookeeper-3.5.5/apache-zookeeper-3.5.5-bin.tar.gz
RUN tar -xvf apache-zookeeper-3.5.5-bin.tar.gz
RUN rm apache-zookeeper-3.5.5-bin.tar.gz
RUN mkdir apache-zookeeper-3.5.5-bin/data
ENV JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64

RUN wget https://archive.apache.org/dist/kafka/2.3.0/kafka_2.12-2.3.0.tgz
RUN tar -xzf kafka_2.12-2.3.0.tgz
RUN rm kafka_2.12-2.3.0.tgz

RUN wget https://archive.apache.org/dist/cassandra/3.11.4/apache-cassandra-3.11.4-bin.tar.gz
RUN tar -xvf apache-cassandra-3.11.4-bin.tar.gz
RUN rm apache-cassandra-3.11.4-bin.tar.gz
ENV PATH /home/ziad/apache-cassandra-3.11.4/bin:$PATH


RUN sudo apt-get install -y gcc
RUN pip install apache-airflow

RUN pip install Flask==1.0.4
RUN airflow db init
RUN mkdir /home/ziad/airflow/dags

ADD . /home/ziad/stock_data_pipeline
RUN sudo chmod 777 -R /home/ziad/stock_data_pipeline
RUN cp stock_data_pipeline/zoo.cfg apache-zookeeper-3.5.5-bin/conf/
RUN pip install -r stock_data_pipeline/requirements.txt

RUN sudo apt-get install -y tmux
ENV NAME stock_data_pipeline



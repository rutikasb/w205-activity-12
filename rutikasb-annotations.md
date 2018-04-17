# Annotations for assignment 12

The purpose of this assignment is to setup a web API server for a game development company. As a mobile game developer, we're interested in setting APIs to track two events, "buy a sword" and "join a guid".

We'll build a simple light-weight python based web server using flask in MIDS docker container. The API server handles requests and the business requirements. It will also log events to a kafka topic. We'll make curl requests to check the API responses, and consume messages from the Kafka topic to verify that the web server is working as expected. Messages will be consumed in 2 ways, one manually and other by using pyspark.


## Steps:

## Activity

### Step 1: Create a docker cluster with 5 containers -- zookeper, kafka, cloudera, spark, and mids

Following is the `docker-compose.yml` file to bring up the cluster

```
---
version: '2'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:latest
    environment:
      ZOOKEEPER_CLIENT_PORT: 32181
      ZOOKEEPER_TICK_TIME: 2000
    expose:
      - "2181"
      - "2888"
      - "32181"
      - "3888"
    extra_hosts:
      - "moby:127.0.0.1"

  kafka:
    image: confluentinc/cp-kafka:latest
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:32181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    expose:
      - "9092"
      - "29092"
    extra_hosts:
      - "moby:127.0.0.1"

  cloudera:
    image: midsw205/cdh-minimal:latest
    expose:
      - "8020" # nn
      - "50070" # nn http
      - "8888" # hue
    #ports:
    #- "8888:8888"
    extra_hosts:
      - "moby:127.0.0.1"

  spark:
    image: midsw205/spark-python:0.0.5
    stdin_open: true
    tty: true
    volumes:
      - ~/w205:/w205
    expose:
      - "8888"
    ports:
      - "8888:8888"
    depends_on:
      - cloudera
    environment:
      HADOOP_NAMENODE: cloudera
    extra_hosts:
      - "moby:127.0.0.1"
    command: bash

  mids:
    image: midsw205/base:0.1.9
    stdin_open: true
    tty: true
    volumes:
      - ~/w205:/w205
    expose:
      - "5000"
    ports:
      - "5000:5000"
    extra_hosts:
      - "moby:127.0.0.1"
```

Spin up the cluster with the following command:

`docker-compose up -d`

We wait for the Cloudera Hadoop and Kafka to come up successfully. We ensure this by looking at the Cloudera and Kafka logs like below:

```
docker-compose logs -f cloudera
docker-compose exec cloudera hadoop fs -ls /tmp/
docker-compose logs -f kafka
```

### Step 2: Create a Kafka topic called "events"

Create a Kafka topic called "events" with the following command:

`docker-compose exec kafka kafka-topics --create --topic events --partitions 1 --replication-factor 1 --if-not-exists --zookeeper zookeeper:32181`

After running the command, we see the following output:

`Created topic "events"`


### Step 3: Create a simple web API server

I used the python `Flask` module to setup a simple API server. Following is the python script, `game_api.py`

```
#!/usr/bin/env python
import json
from kafka import KafkaProducer
from flask import Flask, request

app = Flask(__name__)
producer = KafkaProducer(bootstrap_servers='kafka:29092')


def log_to_kafka(topic, event):
    event.update(request.headers)
    producer.send(topic, json.dumps(event).encode())


@app.route("/")
def default_response():
    default_event = {'event_type': 'default'}
    log_to_kafka('events', default_event)
    return "This is the default response!\n"


@app.route("/purchase_a_sword")
def purchase_a_sword():
    sword_type = request.args.get("sword_type")
    purchase_sword_event = {'event_type': 'purchase_sword', 'sword_type': sword_type}
    log_to_kafka('events', purchase_sword_event)
    return "Sword Purchased of type {}!\n".format(sword_type)
```

We have 2 APIs here, one is the default root API and other is an API to purchase a sword. The business logic to put a sword in user's inventroy would go here. The `/purchase_a_sword` also accepts a `sword_type` parameter which would indicate the type of sword the user is purchasing.

Everytime an API is called, along with carrying out the API logic, it also logs an event to the kafka topic `events`. 

I run the web server in the MIDS container with the following command. This will run and print output to the command line each time we make a web API call. It will hold the command line until I exit with Ctrl-C.

`docker-compose exec mids env FLASK_APP=/w205/spark-from-files/game_api.py flask run --host 0.0.0.0`

The web server is started on port 5000

### Step 4: Test the web server

In another linix command window, we start Kafkacat in the foreground so that we can see events as they are written to Kafka. Following is the command to do the same:

`docker-compose exec mids kafkacat -C -b kafka:29092 -t events -o beginning`


In yet another linux command line window, we use Apache Bench to make web API requests to the 2 APIs created in the previous step. Apache bench (or ab) is a utility designed to stress test web servers using a high volume of data in a short amount of time.

```
docker-compose exec mids ab -n 10 -H "Host: user1.comcast.com" http://localhost:5000/
docker-compose exec mids ab -n 10 -H "Host: user1.comcast.com" http://localhost:5000/purchase_a_sword?sword_type=knightly
docker-compose exec mids ab -n 10 -H "Host: user2.att.com" http://localhost:5000/
docker-compose exec mids ab -n 10 -H "Host: user2.att.com" http://localhost:5000/purchase_a_sword?sword_type=backsword
```

The -n option specifies the number of requests to perform for the benchmarking session. In the above commands we are making 10 requests of each.

Here's a sample output for one of the commands.
```
science@w205s7-crook-1:~/w205/activity-12-rutikasb$ docker-compose exec mids ab -n 10 -H "Host: user2.att.com" http://localhost:5000/purchase_a_sword?sword_type=backsword
This is ApacheBench, Version 2.3 <$Revision: 1706008 $>
Copyright 1996 Adam Twiss, Zeus Technology Ltd, http://www.zeustech.net/
Licensed to The Apache Software Foundation, http://www.apache.org/

Benchmarking localhost (be patient).....done


Server Software:        Werkzeug/0.14.1
Server Hostname:        localhost
Server Port:            5000

Document Path:          /purchase_a_sword?sword_type=backsword
Document Length:        35 bytes

Concurrency Level:      1
Time taken for tests:   0.075 seconds
Complete requests:      10
Failed requests:        0
Total transferred:      1900 bytes
HTML transferred:       350 bytes
Requests per second:    132.94 [#/sec] (mean)
Time per request:       7.522 [ms] (mean)
Time per request:       7.522 [ms] (mean, across all concurrent requests)
Transfer rate:          24.67 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.1      0       0
Processing:     4    7   3.8      6      16
Waiting:        0    5   4.6      4      16
Total:          4    7   3.8      7      16

Percentage of the requests served within a certain time (ms)
  50%      7
  66%      9
  75%     10
  80%     10
  90%     16
  95%     16
  98%     16
  99%     16
 100%     16 (longest request)
```

In the window that's running the Kafkacat we see the following events being written:
```
science@w205s7-crook-1:~/w205/activity-12-rutikasb$ docker-compose exec mids bash -c "kafkacat -C -b kafka:29092 -t events -o beginning"
{"Host": "user1.comcast.com", "event_type": "default", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user1.comcast.com", "event_type": "default", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user1.comcast.com", "event_type": "default", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
....
{"Host": "user1.comcast.com", "sword_type": "knightly", "event_type": "purchase_sword", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user1.comcast.com", "sword_type": "knightly", "event_type": "purchase_sword", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user1.comcast.com", "sword_type": "knightly", "event_type": "purchase_sword", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
....
{"Host": "user2.att.com", "event_type": "default", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user2.att.com", "event_type": "default", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user2.att.com", "event_type": "default", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
....
{"Host": "user2.att.com", "sword_type": "backsword", "event_type": "purchase_sword", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user2.att.com", "sword_type": "backsword", "event_type": "purchase_sword", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
{"Host": "user2.att.com", "sword_type": "backsword", "event_type": "purchase_sword", "Accept": "*/*", "User-Agent": "ApacheBench/2.3"}
....
```


### Step 5: Consume events from Kafka topic using spark

We will use a spark application to consume the events from Kafka topic instead of using a pyspark console. Following is the script named `just_filtering.py`. It can handles multiple schemas at a time.

```
#!/usr/bin/env python
"""Extract events from kafka and write them to hdfs
"""
import json
from pyspark.sql import SparkSession, Row
from pyspark.sql.functions import udf


@udf('boolean')
def is_purchase(event_as_json):
    event = json.loads(event_as_json)
    if event['event_type'] == 'purchase_sword':
        return True
    return False


def main():
    """main
    """
    spark = SparkSession \
        .builder \
        .appName("ExtractEventsJob") \
        .getOrCreate()

    raw_events = spark \
        .read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "events") \
        .option("startingOffsets", "earliest") \
        .option("endingOffsets", "latest") \
        .load()

    purchase_events = raw_events \
        .select(raw_events.value.cast('string').alias('raw'),
                raw_events.timestamp.cast('string')) \
        .filter(is_purchase('raw'))

    extracted_purchase_events = purchase_events \
        .rdd \
        .map(lambda r: Row(timestamp=r.timestamp, **json.loads(r.raw))) \
        .toDF()
    extracted_purchase_events.printSchema()
    extracted_purchase_events.show()


if __name__ == "__main__":
    main()
```

The above script the extracts the purchase sword events from Kafka. It uses the python pyspark module to achieve that.

A `SparkSession` can be used to create `DataFrame`, register `DataFrame` as tables, execute SQL over tables, cache tables, and read parquet files.

`SparkSession.builder.appName("ExtractEventsJob").getOrCreate()` gets an existing spark session or creates a new one if it doesn't already exist. All the events from the Kafka `events` topic are read as `raw_events`. Each raw_event value is then cast as string and then convereted to json and the ones whose event_type is 'purchase_sword' is extracted.

`spark-submit` allows one to manage spark applications and we can submit the `extract_events.py` file to spark with the following command:

`docker-compose exec spark spark-submit /w205/activity-12-rutikasb/just_filtering.py`

The above command is a short for `docker-compose exec spark spark-submit --master 'local[*]' filename.py`. Since we're not running a cluster with dedicated "master" and "workers", we set master to local. If master is not specified, it defaults to 'local[*]'



### Step 6: Add a new event (or API)

We stop the Flask server and add this piece of code to game_api.py to add an API `/purchase_a_knife`.

```
@app.route("/purchase_a_knife")
def purchase_a_knife():
    purchase_knife_event = {'event_type': 'purchase_knife',
                            'description': 'very sharp knife'}
    log_to_kafka('events', purchase_knife_event)
    return "Knife Purchased!\n"
```

We restart the web server like before.


### Step 7: Write filtered events to Hadoop HDFS

We modify the spark code in step 6 as below to write out the filtered events to Hadoop HDFS in parquet format. Following is the modified code `filtered_writes.py`:

```
#!/usr/bin/env python
"""Extract events from kafka and write them to hdfs
"""
import json
from pyspark.sql import SparkSession, Row
from pyspark.sql.functions import udf


@udf('boolean')
def is_purchase(event_as_json):
    event = json.loads(event_as_json)
    if event['event_type'] == 'purchase_sword':
        return True
    return False


def main():
    """main
    """
    spark = SparkSession \
        .builder \
        .appName("ExtractEventsJob") \
        .getOrCreate()

    raw_events = spark \
        .read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "kafka:29092") \
        .option("subscribe", "events") \
        .option("startingOffsets", "earliest") \
        .option("endingOffsets", "latest") \
        .load()

    purchase_events = raw_events \
        .select(raw_events.value.cast('string').alias('raw'),
                raw_events.timestamp.cast('string')) \
        .filter(is_purchase('raw'))

    extracted_purchase_events = purchase_events \
        .rdd \
        .map(lambda r: Row(timestamp=r.timestamp, **json.loads(r.raw))) \
        .toDF()
    extracted_purchase_events.printSchema()
    extracted_purchase_events.show()

    extracted_purchase_events \
        .write \
        .mode('overwrite') \
        .parquet('/tmp/purchases')


if __name__ == "__main__":
    main()
```

The above script is submitted to spark like before: `docker-compose exec spark spark-submit /w205/activity-12-rutikasb/filtered_writes.py`

To verify that the above script worked, I look into the `/tmp/purchases` where it was written.

```
science@w205s7-crook-1:~/w205/activity-12-rutikasb$ docker-compose exec cloudera hadoop fs -ls /tmp/
Found 3 items
drwxrwxrwt   - mapred mapred              0 2018-02-06 18:27 /tmp/hadoop-yarn
drwx-wx-wx   - root   supergroup          0 2018-04-17 00:03 /tmp/hive
drwxr-xr-x   - root   supergroup          0 2018-04-17 03:35 /tmp/purchases
science@w205s7-crook-1:~/w205/activity-12-rutikasb$ docker-compose exec cloudera hadoop fs -ls /tmp/purchases/
Found 2 items
-rw-r--r--   1 root supergroup          0 2018-04-17 03:35 /tmp/purchases/_SUCCESS
-rw-r--r--   1 root supergroup       1907 2018-04-17 03:35 /tmp/purchases/part-00000-8de659db-52db-4862-a63d-ceaf87dec360-c000.snappy.parquet
```


### Step 8: Read from the parquet files

Startup a jupyter notebook: `docker-compose exec spark env PYSPARK_DRIVER_PYTHON=jupyter PYSPARK_DRIVER_PYTHON_OPTS='notebook --no-browser --port 8888 --ip 0.0.0.0 --allow-root' pyspark`

We access it from our local browser using the IP address of the remote droplet. And run the following commands in the notebook:

```
purchases = spark.read.parquet('/tmp/purchases')
purchases.show()
+------+-----------------+---------------+--------------+----------+--------------------+
|Accept|             Host|     User-Agent|    event_type|sword_type|           timestamp|
+------+-----------------+---------------+--------------+----------+--------------------+
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
|   */*|    user2.att.com|ApacheBench/2.3|purchase_sword| backsword|2018-04-17 00:04:...|
+------+-----------------+---------------+--------------+----------+--------------------+

purchases.registerTempTable('purchases')
purchases_by_example2 = spark.sql("select * from purchases where Host = 'user1.comcast.com'")
purchases_by_example2.show()
+------+-----------------+---------------+--------------+----------+--------------------+
|Accept|             Host|     User-Agent|    event_type|sword_type|           timestamp|
+------+-----------------+---------------+--------------+----------+--------------------+
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
|   */*|user1.comcast.com|ApacheBench/2.3|purchase_sword|  knightly|2018-04-17 00:03:...|
+------+-----------------+---------------+--------------+----------+--------------------+

df = purchases_by_example2.toPandas()
df.describe()
	Accept	Host	                User-Agent	event_type	sword_type	timestamp
count	10	10	                10	        10	        10	        10
unique	1	1	                1	        1	        1	        10
top	*/*	user1.comcast.com	ApacheBench/2.3	purchase_sword	knightly	2018-04-17 00:03:44.072
freq	10	10	                10	        10	        10	        1

```


### Step 9: Bring down the docker cluster

Finally bring down the docker cluster with `docker-compose down`

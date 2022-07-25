import os
import random
import threading
import time
from datetime import datetime

from app_common_python import KafkaTopics, LoadedConfig
from flask import Flask, make_response, request
from prometheus_client import Counter, Gauge

import starter_helper

scaffolding = starter_helper.StarterHelper()
scaffolding.print_all_info()

print(f"\n\n🚀\tStarter App started at: {datetime.now()}\n")

APP = Flask(__name__)

UNSEEN_MESSAGES = Gauge("unseen_messages", "Number of unseen messages")
CONSUMED_MESSAGES = Counter("consumed_messages", "Number of consumed messages")
PRODUCED_MESSAGES = Counter("produced_messages", "Number of produced messages")
HEALTH_CALLS = Counter("health_calls", "Number of health calls")

MESSAGES = {}


def consume_messages():
    global MESSAGES
    consumer = scaffolding.kafka_consumer()
    consumer.subscribe(list(KafkaTopics))
    while True:
        messages = MESSAGES.copy()
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"Consumer error: {msg.error()}")
            continue
        # message.timestamp() might be useful as well
        # also, msg.value() is a bytes object, not a string, so decode it
        topic, value = msg.topic(), msg.value().decode("utf-8")
        if topic not in messages:
            messages[topic] = []
        messages[topic].append(value)
        MESSAGES = messages
        CONSUMED_MESSAGES.inc()
        print(f"  Consumed message: {msg.value()}")


# complementary to the consume_messages() function
@APP.route('/kafka', methods=['GET'])
def kafka_get():
    global MESSAGES
    print(f"Copying messages {MESSAGES}")
    messages_copy = MESSAGES.copy()
    MESSAGES = {}
    UNSEEN_MESSAGES.dec(len(messages_copy))
    return messages_copy


@APP.route('/kafka', methods=['PUT', 'POST'])
def kafka_put():
    producer = scaffolding.kafka_producer()
    request_data = request.args.get("message")
    # This just gets the first key it can and uses that as the topic
    producer_topic = next(iter(KafkaTopics))
    producer.produce(producer_topic, request_data)
    print(f"Produced {request_data} on topic: '{producer_topic}'")
    producer.flush()
    PRODUCED_MESSAGES.inc()
    UNSEEN_MESSAGES.inc()
    return f"In kafka_put() with request_data: {request_data}\n"


# Generate a basic file to be used as a test file, and get them all
@APP.route('/minio', methods=['GET'])
def minio_get():
    """
    Handles GET requests to the /minio endpoint. Returns object data from Minio.
    """
    print("In minio_get()")
    if not scaffolding.object_store_enabled:
        return "Minio is not enabled"
    minio_client = scaffolding.object_store_conn()
    objects = list(minio_client.list_objects("example-bucket"))
    return {
        obj.object_name: {
            "size": obj.size,
            "last_modified": obj.last_modified,
        }
        for obj in objects
    }


@APP.route('/minio', methods=['POST', 'PUT'])
def minio_put():
    """
    Handles PUT and POST requests to the /minio endpoint. Adds example files
    to an example bucket called `testbucket` with the file name as the timestamp
    and the file contents as a string of random bits.
    """
    print("In minio_put()")
    if not scaffolding.object_store_enabled:
        return "Minio is not enabled"
    minio_client = scaffolding.object_store_conn()
    # Write a file containing a random string locally as an example for Minio
    current_time = datetime.now()
    with open(f"{current_time}.txt", "w") as f:
        f.write(str(random.getrandbits(1024)))
    if not minio_client.bucket_exists("example-bucket"):
        minio_client.make_bucket("example-bucket")
    # Upload the file to Minio
    minio_client.fput_object("example-bucket", f"{current_time}.txt",
                             f"{current_time}.txt")
    # Delete the temp file
    os.remove(f"{current_time}.txt")
    return f"Inserted {current_time}.txt into Minio"


@APP.route('/redis', methods=['GET'])
def redis_get():
    """
    Handles GET requests to the /redis endpoint. Returns the value associated
    with the specified key. If the key does not exist, returns a 404.

    `key` is a required input to the request.
    """
    print("In redis_get()")
    if not scaffolding.in_memory_db_enabled:
        return "Redis is not enabled"
    key = request.args.get("key")
    if key is None:
        return make_response("No key specified", 400)
    result = scaffolding.in_memory_db_conn().get(key)
    print(f"Redis result: {result}")
    if result is None:
        return make_response("Key not found in database", 404)
    return result


@APP.route('/redis', methods=['POST', 'PUT'])
def redis_put():
    """
    Handles PUT and POST requests to the /redis endpoint. Adds a message to
    the specified key in the Redis database. If the key already exists, it is
    overwritten.

    `key` and `value` are required inputs to the request.
    """
    print("In redis_put()")

    key = request.args.get("key")
    if key is None:
        return make_response("No key provided", 400)
    value = request.args.get("value")
    if value is None:
        return make_response("No value provided", 400)
    result = scaffolding.in_memory_db_conn().set(key, value)
    if not result:
        return make_response("Failed to set properly", 500)
    return f"Set {key} to {value}"


@APP.route('/postgres', methods=['GET'])
def postgres_get():
    print("In postgres_get()")
    cursor = scaffolding.database_conn().cursor()
    SQL = "SELECT * FROM example_table;"
    cursor.execute(SQL)
    # Since we know the scheme of the table, we can build a json object from the
    # result of the query
    result = {}
    for id_value, message_value in cursor:
        print(f"  id: {id_value}, message: {message_value}")
        result[id_value] = message_value
    return result


@APP.route('/postgres', methods=['POST', 'PUT'])
def postgres_put():
    """
    Handles PUT and POST requests to the /postgres endpoint. Inserts messages
    into the database.
    """
    print("In postgres_put()")
    cursor = scaffolding.database_conn().cursor()
    # This is the approach recommended by psycopg2
    # https://www.psycopg.org/docs/usage.html#the-problem-with-the-query-parameters
    SQL = "INSERT INTO example_table (message) VALUES (%s);"
    message = (request.args.get('message'), )
    cursor.execute(SQL, message)
    return f"Inserted message {message} into database"


@APP.route('/livez', methods=['GET', 'PUT', 'POST'])
def liveness():
    print("In liveness()")
    return "In liveness()"


@APP.route('/readyz', methods=['GET', 'PUT', 'POST'])
def readiness():
    print("In readiness()")
    return 'In readiness()'


@APP.route('/healthz', methods=['GET', 'PUT', 'POST'])
def health():
    HEALTH_CALLS.inc()
    print("In health()")
    return 'In health()'


# @APP.route('/')
# def root():
#     print("In root()")
#     return 'In root()'

# 0. dummy API for liveness and readiness probes ✅ (apparently clowder built-in)
# 1. Get simple API to send/receive messages through kafka ✅
#  - At some point, I need to convert from Flask to Django
# 2. get examples for each clowder provider:
#        Web - Finished ✅
#        Minio - Finished ✅
#        In-memory db - Finished ✅
#        Kafka - Finished ✅
#        Postgres - Finished ✅
#        Metrics - Finished ✅
#        InitContainer
#        CronJob
#        CJI
#        Feature Flags - Unleash
# 3. Eventually be able to `oc process`/`oc apply` the starter app

if __name__ == '__main__':
    assert LoadedConfig is not None

    # We need to have a thread for consume_messages() to run in the background
    CONSUMER_THREAD = threading.Thread(target=consume_messages)
    CONSUMER_THREAD.start()
    print("Started consumer thread")
    postgres_conn = scaffolding.database_conn(autocommit=True)
    print("Connected to Postgres")
    SQL = "CREATE TABLE IF NOT EXISTS example_table (id SERIAL PRIMARY KEY, message VARCHAR(255));"
    with postgres_conn.cursor() as cursor:
        cursor.execute(SQL)
    print("Created example_table")
    scaffolding.start_prometheus()
    print("Started prometheus")
    PORT = LoadedConfig.publicPort
    print(f"public port: {PORT}")
    APP.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

# Build stuff
# Push to quay

# oc get service
# oc port-forward svc/starterapp-worker-service 8000
# oc port-forward svc/env-boot-minio 9000

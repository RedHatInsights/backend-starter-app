import os
import random
import threading
from datetime import datetime
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt

from app_common_python import KafkaTopics, LoadedConfig
from prometheus_client import Counter, Gauge

from . import starter_helper

scaffolding = starter_helper.StarterHelper()

UNSEEN_MESSAGES = Gauge("unseen_messages", "Number of unseen messages")
CONSUMED_MESSAGES = Counter("consumed_messages", "Number of consumed messages")
PRODUCED_MESSAGES = Counter("produced_messages", "Number of produced messages")
HEALTH_CALLS = Counter("health_calls", "Number of health calls")
READINESS_CALLS = Counter("readiness_calls", "Number of readiness calls")
LIVENESS_CALLS = Counter("liveness_calls", "Number of liveness calls")

MESSAGES = {}

# NOTE: https://docs.djangoproject.com/en/4.0/ref/csrf/
# The approaches below (and in particular the `csrf_exempt` decorator) are not
# necessarily safe to be used in a production environment


# NOTE: this is not intended to be used in production--a safer method should be
# used than saving the messages directly to memory.
def consume_messages() -> None:
    """
    This function is intended to be run in a separate thread. It will consume
    messages from the Kafka topic and save them to a dictionary. The dictionary
    is then accessible to the kafka_get() function as a global variable.
    """
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
def kafka_get(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /kafka endpoint. Returns the messages from the
    Kafka topic as specified in the clowdapp config.
    Example url: http://127.0.0.1:8000/kafka

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    global MESSAGES
    messages_copy = MESSAGES.copy()
    MESSAGES = {}
    UNSEEN_MESSAGES.dec(len(messages_copy))
    return JsonResponse(messages_copy)


def kafka_put(request: HttpRequest) -> HttpResponse:
    """
    Handles PUT and POST requests to the /kafka endpoint. Adds a message to
    the Kafka topic specified in the clowdapp config.
    Example url: http://127.0.0.1:8000/kafka?message=hello

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    producer = scaffolding.kafka_producer()
    # request.GET gives us a QueryDict, and we can grab args from that
    query_dict = request.GET
    request_data = query_dict.get("message", None)
    if request_data is None:
        return HttpResponse("No message provided", status=400)
    # This just gets the first key it can and uses that as the topic
    producer_topic = next(iter(KafkaTopics))
    producer.produce(producer_topic, request_data)
    print(f"Produced {request_data} on topic: '{producer_topic}'")
    producer.flush()
    PRODUCED_MESSAGES.inc()
    UNSEEN_MESSAGES.inc()
    return HttpResponse(f"In kafka_put() with request_data: {request_data}")


@csrf_exempt
def handle_kafka(request: HttpRequest) -> HttpResponse:
    """
    Handles GET, PUT, and POST requests to the /kafka endpoint. If kafka is
    not enabled, returns a message stating as such.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # If not enabled, return a message stating as such
    if not scaffolding.kafka_enabled:
        return HttpResponse("Kafka is not enabled", status=400)
    # Otherwise handle the request
    if request.method == 'GET':
        return kafka_get(request)
    elif request.method in ['POST', 'PUT']:
        return kafka_put(request)
    return HttpResponse("Invalid method", status_code=400)


# Generate a basic file to be used as a test file, and get them all
def minio_get(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /minio endpoint. Returns object data from Minio
    in the form of a json object made of the object names, their sizes, and the
    time they were last modified.
    Example url: http://127.0.0.1:8000/minio

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # Get the object store connection, then return objects from it
    minio_client = scaffolding.object_store_conn()
    objects = list(minio_client.list_objects("example-bucket"))
    return JsonResponse({
        obj.object_name: {
            "size": obj.size,
            "last_modified": obj.last_modified,
        }
        for obj in objects
    })


def minio_put(request: HttpRequest) -> HttpResponse:
    """
    Handles PUT and POST requests to the /minio endpoint. Adds example files
    to an example bucket called `testbucket` with the file name as the timestamp
    and the file contents as a string of random bits.
    Example url: http://127.0.0.1:8000/minio

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
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
    return HttpResponse(f"Inserted {current_time}.txt into Minio")


@csrf_exempt
def handle_minio(request: HttpRequest) -> HttpResponse:
    """
    Handles GET, PUT, and POST requests to the /minio endpoint. Returns a
    message stating that Minio is not enabled if it is not enabled.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # If not enabled, return a message stating as such
    if not scaffolding.object_store_enabled:
        return HttpResponse("Minio is not enabled", status=400)
    # Otherwise handle the request
    if request.method == 'GET':
        return minio_get(request)
    elif request.method in ['POST', 'PUT']:
        return minio_put(request)
    return HttpResponse("Invalid method", status=400)


def redis_get(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /redis endpoint. Returns the value associated
    with the specified key. If the key does not exist, returns a 404. `key` is
    a required input to the request.
    Example url: http://127.0.0.1:8000/redis?key=example_key

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # request.GET gives us a QueryDict, and we can grab args from that
    query_dict = request.GET
    key = query_dict.get("key", None)
    if key is None:
        return HttpResponse("No key specified", status=400)
    # With the key specified, get the value from the in-memory db
    result = scaffolding.in_memory_db_conn().get(key)
    if result is None:
        return HttpResponse("Key not found in database", status=404)
    return HttpResponse(result)


def redis_put(request: HttpRequest) -> HttpResponse:
    """
    Handles PUT and POST requests to the /redis endpoint. Adds a message to
    the specified key in the Redis database. If the key already exists, it is
    overwritten. `key` and `value` are required inputs to the request.
    Example url: http://127.0.0.1:8000/redis?key=example_key&value=example_value

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # request.GET gives us a QueryDict, and we can grab args from that
    query_dict = request.GET
    key = query_dict.get("key", None)
    if key is None:
        return HttpResponse("No key provided", status=400)
    value = query_dict.get("value", None)
    if value is None:
        return HttpResponse("No value provided", status=400)
    # With the key and value specified we can set the value in the in-memory db
    result = scaffolding.in_memory_db_conn().set(key, value)
    if not result:
        return HttpResponse("Failed to set properly", status=500)
    return HttpResponse("Set {key} to {value}")


@csrf_exempt
def handle_redis(request: HttpRequest) -> HttpResponse:
    """
    Handles GET, PUT, and POST requests to the /redis endpoint. Returns a
    message stating that Redis is not enabled if it is not enabled.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # If not enabled, return a message stating as such
    if not scaffolding.in_memory_db_enabled:
        return HttpResponse("Redis is not enabled", status=400)
    # Otherwise handle the request
    if request.method == 'GET':
        return redis_get(request)
    elif request.method in ['POST', 'PUT']:
        return redis_put(request)
    return HttpResponse("Invalid method", status=400)


def postgres_get(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /postgres endpoint. Returns all messages added
    with postgres_put.
    Example url: http://127.0.0.1:8000/postgres

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    cursor = scaffolding.database_conn().cursor()
    SQL = "SELECT * FROM example_table;"
    cursor.execute(SQL)
    return JsonResponse(dict(cursor))


def postgres_put(request: HttpRequest) -> HttpResponse:
    """
    Handles PUT and POST requests to the /postgres endpoint. Inserts messages
    into the database. `message` is a required input to the request.
    Example url: http://127.0.0.1:8000/postgres?message=example_message

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    cursor = scaffolding.database_conn().cursor()
    # This is the approach recommended by psycopg2
    # https://www.psycopg.org/docs/usage.html#the-problem-with-the-query-parameters
    SQL = "INSERT INTO example_table (message) VALUES (%s);"
    # request.GET gives us a QueryDict, and we can grab args from that
    query_dict = request.GET
    message = (query_dict.get("message", None), )
    cursor.execute(SQL, message)
    return HttpResponse(f"Inserted message {message} into database")


@csrf_exempt
def handle_postgres(request: HttpRequest) -> HttpResponse:
    """
    Handles GET, PUT, and POST requests to the /postgres endpoint. Returns a
    message stating that Postgres is not enabled if it is not enabled.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # If not enabled, return a message stating as such
    if not scaffolding.database_enabled:
        return HttpResponse("Postgres is not enabled", status=400)
    # Otherwise handle the request
    if request.method == 'GET':
        return postgres_get(request)
    elif request.method in ['POST', 'PUT']:
        return postgres_put(request)
    return HttpResponse("Invalid method", status=400)


def postgres_init_get(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /postgres_init endpoint.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    cursor = scaffolding.database_conn().cursor()
    SQL = "SELECT * FROM init_container;"
    cursor.execute(SQL)
    return JsonResponse(dict(cursor))


@csrf_exempt
def handle_postgres_init(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /postgres_init endpoint. Returns a message
    stating that Postgres is not enabled if it is not enabled.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # If not enabled, return a message stating as such
    if not scaffolding.database_enabled:
        return HttpResponse("Postgres is not enabled", status=400)
    # Otherwise handle the request
    if request.method == 'GET':
        return postgres_init_get(request)
    return HttpResponse("Invalid method", status=400)


@csrf_exempt
def feature_flag_get(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /featureflag endpoint. Returns the value of the
    specified feature flag. If the flag does not exist, returns False. `flag` is
    a required input to the request.
    Example url: http://127.0.0.1:8000/featureflag?flag=example_flag

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # request.GET gives us a QueryDict, and we can grab args from that
    query_dict = request.GET
    flag = query_dict.get("flag", None)
    if flag is None:
        return HttpResponse("No flag specified", status=400)
    connection = scaffolding.feature_flags_conn(refresh_interval=1)
    result = connection.is_enabled(flag)
    if result is None:
        return HttpResponse("Flag not found in database", status=404)
    return HttpResponse(result)


@csrf_exempt
def handle_feature_flag(request: HttpRequest) -> HttpResponse:
    """
    Handles GET requests to the /featureflag endpoint. Returns a message
    stating that Feature Flags is not enabled if it is not enabled.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    # If not enabled, return a message stating as such
    if not scaffolding.feature_flags_enabled:
        return HttpResponse("Feature Flags is not enabled", status=400)
    # Otherwise handle the request
    if request.method == 'GET':
        return feature_flag_get(request)
    return HttpResponse("Invalid method", status=400)


@csrf_exempt
def healthz(request: HttpRequest) -> HttpResponse:
    """
    Handles requests to the /healthz endpoint. /healthz is called by clowder
    when the readiness and liveness probes are not explicitly defined in the
    clowdapp.yaml file.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    HEALTH_CALLS.inc()
    return HttpResponse("/healthz returning ok")


@csrf_exempt
def livez(request: HttpRequest) -> HttpResponse:
    """
    Handles requests to the /livez endpoint.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    LIVENESS_CALLS.inc()
    return HttpResponse("/livez returning ok")


@csrf_exempt
def readyz(request: HttpRequest) -> HttpResponse:
    """
    Handles requests to the /readyz endpoint.

    Parameters
    ----------
    request : HttpRequest
        The request object. Handled by Django.

    Returns
    -------
    HttpResponse
        The response object. Handled by Django.
    """
    READINESS_CALLS.inc()
    return HttpResponse("/readyz returning ok")


def start_app() -> None:
    """
    Handles some startup tasks for the app, such as printing information about
    what providers are used in the clowdapp, starting kafka consumption, and
    ensuring that `example_table` exists in the database.
    """
    assert LoadedConfig is not None

    scaffolding.print_all_info()

    print(f"\n\n🚀\tStarter App started at: {datetime.now()}\n")
    if scaffolding.kafka_enabled:
        # We need a thread for consume_messages() to run in the background
        CONSUMER_THREAD = threading.Thread(target=consume_messages)
        CONSUMER_THREAD.start()
    if scaffolding.database_enabled:
        postgres_conn = scaffolding.database_conn(autocommit=True)
        SQL = ("CREATE TABLE IF NOT EXISTS example_table " +
               "(id SERIAL PRIMARY KEY, message VARCHAR(255));")
        with postgres_conn.cursor() as cursor:
            cursor.execute(SQL)

    scaffolding.start_prometheus()


# Eventually be able to `oc process`/`oc apply` the starter app
# Build stuff
# Push to quay

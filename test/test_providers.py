import requests
import time
import json

location = 'http://127.0.0.1:8000'
kafka_tests = 100
minio_tests = 10
redis_tests = 10
redis_duplicate_tests = 5
postgres_tests = 100


def test_kafka_produce():
    provider = 'kafka'
    query = 'message'
    for i in range(1, 1 + kafka_tests):
        message = f"test message {i}"
        url = f'{location}/{provider}?{query}={message}'
        response = requests.post(url)
        assert response.status_code == 200


def test_kafka_consume():
    provider = 'kafka'
    # Small sleep to allow kafka to catch up just in case
    time.sleep(0.5)
    url = f'{location}/{provider}'
    seen = 0
    response = requests.get(url)
    print(response)
    values = json.loads(response.text)['example-topic']
    seen = len(values)
    print(f"{seen} Kafka messages received successfully")
    # At *least* `kafka_tests` messages should be received
    assert seen >= kafka_tests


def test_minio_produce():
    provider = 'minio'
    for _ in range(minio_tests):
        url = f'{location}/{provider}'
        response = requests.post(url)
        assert response.status_code == 200


def test_minio_consume():
    provider = 'minio'
    url = f'{location}/{provider}'
    seen = 0
    response = requests.get(url)
    values = json.loads(response.text)
    seen = len(values)
    print(f"{seen} Minio messages received successfully")
    # At *least* `minio_tests` messages should be received
    assert seen >= minio_tests


def test_redis_produce_unique():
    provider = 'redis'
    for i in range(redis_tests):
        url = f'{location}/{provider}?key=key_{i}&value=value_{i}'
        response = requests.post(url)
        assert response.status_code == 200


def test_redis_consume_unique():
    provider = 'redis'
    for i in range(redis_tests):
        url = f'{location}/{provider}?key=key_{i}'
        response = requests.get(url)
        assert response.status_code == 200
        assert response.text == f'value_{i}'


def test_redis_produce_duplicate():
    provider = 'redis'
    for i in range(redis_duplicate_tests):
        url = f'{location}/{provider}?key=duplicate_key&value=value_{i}'
        response = requests.post(url)
        assert response.status_code == 200


def test_redis_consume_duplicate():
    provider = 'redis'
    url = f'{location}/{provider}?key=duplicate_key'
    response = requests.get(url)
    assert response.status_code == 200
    assert response.text == f'value_{redis_duplicate_tests - 1}'


def test_postgres_produce():
    provider = 'postgres'
    for i in range(postgres_tests):
        url = f'{location}/{provider}?message=message_{i}'
        response = requests.post(url)
        assert response.status_code == 200


def test_postgres_consume():
    provider = 'postgres'
    url = f'{location}/{provider}'
    response = requests.get(url)
    values = json.loads(response.text)
    assert response.status_code == 200
    assert len(values) >= postgres_tests


def test_postgres_init_consume():
    provider = 'postgres_init'
    url = f'{location}/{provider}'
    response = requests.get(url)
    values = json.loads(response.text)
    assert response.status_code == 200
    # Number of values sent is in `init_container_db_setup.py`
    assert len(values) >= 100

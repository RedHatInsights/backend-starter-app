import os
from kafka import KafkaConsumer

TEST_ENV_MESSAGE = os.environ['TEST_ENV_MESSAGE']
print("hello from consumer")
print(TEST_ENV_MESSAGE)

consumer = KafkaConsumer('quickstart-events')


for msg in consumer:
    print(msg)

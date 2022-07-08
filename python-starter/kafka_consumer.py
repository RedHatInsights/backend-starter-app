import os
from kafka import KafkaConsumer, KafkaProducer
# producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER)
# for _ in range(20):
#     num = random.randint(0, 100)
#     numstr = str(num).encode('utf-8')
#     producer.send('quickstart-events', bytes(numstr))
#     time.sleep(1)

TEST_ENV_MESSAGE = os.environ['TEST_ENV_MESSAGE']
print("hello from consumer")
print(TEST_ENV_MESSAGE)

consumer = KafkaConsumer('quickstart-events')


for msg in consumer:
    print(msg)

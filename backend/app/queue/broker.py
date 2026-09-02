import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker

broker = RedisBroker(
    url=os.environ.get("DRAMATIQ_REDIS_URL") or "redis://localhost:6379/2"
)
dramatiq.set_broker(broker)

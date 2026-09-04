import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import Middleware


class EnqueueReminderScanOnBoot(Middleware):
    def after_worker_boot(self, broker, worker) -> None:
        from app.queue.email import scan_reminder_emails

        scan_reminder_emails.send()


broker = RedisBroker(
    url=os.environ.get("DRAMATIQ_REDIS_URL") or "redis://localhost:6379/2"
)
broker.add_middleware(EnqueueReminderScanOnBoot())
dramatiq.set_broker(broker)

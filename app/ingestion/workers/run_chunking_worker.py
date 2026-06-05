"""CLI entrypoint for the RabbitMQ-backed chunking worker."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from app.config import get_settings
from app.ingestion.bootstrap import build_chunking_worker_deps
from app.ingestion.workers import QUEUE_CHUNKING
from app.ingestion.workers.runner import run_chunking_worker_channel


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the content.chunking RabbitMQ worker")
    parser.add_argument("--queue", default=QUEUE_CHUNKING)
    parser.add_argument("--rabbitmq-url", default=None)
    parser.add_argument("--prefetch", type=int, default=1)
    parser.add_argument("--max-messages", type=int, default=None)
    parser.add_argument("--no-requeue-on-error", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    rabbitmq_url = args.rabbitmq_url or settings.rabbitmq_url

    connection, channel = _open_channel(
        rabbitmq_url,
        queue=args.queue,
        prefetch_count=args.prefetch,
    )
    try:
        deps = build_chunking_worker_deps(settings)
        result = run_chunking_worker_channel(
            channel,
            deps,
            queue=args.queue,
            max_messages=args.max_messages,
            requeue_on_error=not args.no_requeue_on_error,
        )
        logging.info("chunking worker stopped: %s", result)
        return 0
    finally:
        connection.close()


def _open_channel(rabbitmq_url: str, *, queue: str, prefetch_count: int):
    import pika

    connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
    channel = connection.channel()
    channel.queue_declare(queue=queue, durable=True)
    channel.basic_qos(prefetch_count=prefetch_count)
    return connection, channel


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

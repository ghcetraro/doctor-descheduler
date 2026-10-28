import logging


def configure_logging(level: str) -> None:
    name = (level or "info").strip().lower()
    if name == "none":
        logging.disable(logging.CRITICAL)
        return
    logging.basicConfig(
        level=getattr(logging, name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

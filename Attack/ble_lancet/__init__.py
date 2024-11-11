import asyncio
from .lancet import Lancet


def lancet_main(main_func):
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main_func(*args, **kwargs))
    return wrapper

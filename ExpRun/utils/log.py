import logging
from datetime import datetime

logging.basicConfig(
    filename=f'verify_{datetime.now().strftime("%Y-%m-%d-%H-%M-%S")}.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

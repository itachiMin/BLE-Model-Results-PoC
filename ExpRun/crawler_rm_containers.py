import os
import time
import json
import platform
import requests
import threading
from tqdm import tqdm

from utils.server import Server
from utils.docker import load_image, IMAGE_NAME, IMAGE_VERSION, is_container_exist
from utils.log import logging
from utils.tamarin import parse_theory_link, parse_trace_links, parse_img_link, parse_lemma_results, parse_hardware_info, parse_time_info, lemmas_hash

RESULTS = "results"
IMG_FORMAT = "SVG"
OUTPUT_DIR = "proofs"
CRAWL_GRAPH = True
FORCE_PUSH = True

def error_write(msg: str):
    logging.error(msg)


def finished_write(msg: str):
    logging.info(msg)

class Crawler():
    def __init__(self, port: int, name: str, server: Server, num: int) -> None:
        self.num = f'container_{num}'
        self.port = port
        self.name = name
        self.server = server
        self.homeurl = f"http://{self.server.host}:{self.port}"

    def remove_container(self):
        self.server.excute(f'docker rm -f {self.name}')

if __name__ == '__main__':
    
    with open('servers.json', 'r', encoding='utf8') as f:
        servers_data = json.load(f)
    servers = []
    for s in servers_data:
        server = Server(
            s['host'], s['port'], s['username'],
            s['password'], s['workdir'],
            workers=s['workers']
        )
        server.connect()
        servers.append(server)


    # create crawlers
    crawlers = []
    for server in servers:
        for i in range(server.workers):
            port = 63001 + i
            name = f'tamarin_result-{server.host}-{port}'.replace('.', '-')
            crawler = Crawler(port, name, server, i)
            crawler.remove_container()
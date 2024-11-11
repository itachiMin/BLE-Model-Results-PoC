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

HypothesisLemmas = ["type", "SecrecyOfDHPrivateKey", "RevOOBDataAlwaysRunOOBAS"]

def error_write(msg: str):
    logging.error(msg)


def finished_write(msg: str):
    logging.info(msg)
    

finished = []
finished_lock = threading.Lock()
if os.path.exists('finished.json'):
    with open('finished.json', 'r', encoding='utf8') as f:
        finished = json.load(f)

def add_finished(file: str):
    finished_lock.acquire()
    finished.append(file)
    with open('finished.json', 'w', encoding='utf8') as f:
        json.dump(finished, f)
    finished_lock.release()

class FilePool():
    def __init__(self, files: list) -> None:
        self.files = files
        self.pbar = tqdm(total=len(files), desc="Crawling images")
        self.lock = threading.Lock()

    def pop(self):
        if len(self.files) == 0:
            return None
        self.lock.acquire()
        file = self.files.pop()
        self.lock.release()

        return file

    def push(self, file: str):
        self.lock.acquire()
        self.files.append(file)
        self.lock.release()

    def update(self, num: int):
        self.lock.acquire()
        self.pbar.update(num)
        self.lock.release()


class Crawler():
    def __init__(self, port: int, name: str, server: Server, num: int) -> None:
        self.num = f'container_{num}'
        self.port = port
        self.name = name
        self.server = server
        self.homeurl = f"http://{self.server.host}:{self.port}"

    def create_container(self, file):
        if is_container_exist(self.server, self.name):
            self.remove_container()
        filename = file.split('/')[-1]
        cmd = 'export LC_ALL=C.UTF-8 && mkdir -p /tmp/results/ && '
        cmd += f'cp /{file} /tmp/results/{filename} && '
        cmd += 'tamarin-prover interactive --derivcheck-timeout=0'
        cmd += f' --image-format={IMG_FORMAT} --interface=0.0.0.0 /tmp/results/'

        docker = 'docker run --rm -d'
        docker += f' -p {self.port}:3001'
        docker += f' -v {self.server.workdir}/results:/results'
        docker += f' --name={self.name} {IMAGE_NAME}:{IMAGE_VERSION}'
        docker += f' bash -c "{cmd}"'
        self.server.excute(docker)

    def remove_container(self):
        self.server.excute(f'docker rm -f {self.name}')

    def crawl(self, _file: str):
        if _file in finished:
            return
        
        # create container
        self.create_container(_file)
        
        casename = _file.split('/')[-2]
        file = _file.split('/')[-1]
        # waiting for tamarin start
        while True:
            try:
                r = requests.get(self.homeurl)
                break
            except:
                time.sleep(1)
                
        # get theory link
        theory_link = parse_theory_link(r.text, file)
        assert theory_link is not None, f"Can't find theory link for {file}"
        theory_link = self.homeurl + theory_link
        
        # get lemmas
        while True:
            try:
                r = requests.get(theory_link)
                break
            except:
                time.sleep(1)
        
        # get imgs    
        trace_links = parse_trace_links(r.text)
        for trace in trace_links:
            trace = self.homeurl + trace
            r = requests.get(trace)
            img_src = parse_img_link(r.json()['html'])
            if img_src is None:
                # empty trace
                continue
            img_link = self.homeurl + img_src
            name = img_src.split('/')[6]
            img_name = f'./{OUTPUT_DIR}/imgs/{casename}_{name}.{IMG_FORMAT.lower()}'
            img = requests.get(img_link)
            with open(img_name, 'wb') as f:
                f.write(img.content)
        
        add_finished(_file)

    def start_worker(self, filepool: FilePool):
        while True:
            # get file
            file = filepool.pop()
            if file is None:
                break

            finished_write(f'Start crawling {file} on ' +
                            f'{self.server.host}[{self.num}]')
            # crawl file
            try:
                star_time = time.time()
                self.crawl(file)
                time_used = time.time() - star_time
                time_used = round(time_used, 2)
                finished_write(f'Finished crawling {file} on ' +
                               f'{self.server.host}[{self.num}] using {time_used}s')
                filepool.update(1)
            except:
                error_write(f'Failed to crawl {file} on ' +
                            f'{self.server.host}[{self.num}]')
                filepool.push(file)



def does_have_trace(ltype, result):
    if ltype == "all-traces" and result == "falsified":
        return True
    elif ltype == "exists-trace" and result == "verified":
        return True
    return False


if __name__ == '__main__':
    # create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(f"{OUTPUT_DIR}/imgs", exist_ok=True)

    if not os.path.exists(f'{OUTPUT_DIR}/results.json'):
        # parse lemmas
        cases_data = {}
        spthy_with_trace_files = []
        for case in tqdm(os.listdir(RESULTS), desc="Parsing results"):
            result_file = os.path.join(RESULTS, case, "result.json")
            with open(result_file, 'r', encoding='utf8') as f:
                result_data = json.load(f)
            cases_data[case] = {}

            for f in os.listdir(os.path.join(RESULTS, case)):
                if f.endswith(".spthy"):
                    fst_result = f
                    break
            lemmas_type = {}
            with open(os.path.join(RESULTS, case, fst_result), 'r', encoding='utf8') as f:
                print(case, fst_result)
                data = f.read()
                data = data.split("summary of summaries:")[1]
                lemmas = parse_lemma_results(data)
                for lemma in lemmas:
                    lemmas_type[lemma['name']] = lemma['type']

            # crawl hypothesis lemmas
            lemma_file = f"{lemmas_hash(HypothesisLemmas)}.spthy"
            lemma_file = os.path.join(RESULTS, case, lemma_file)
            with open(lemma_file, 'r', encoding='utf8') as f:
                file_data = f.read()
                file_data = file_data.split("summary of summaries:")[1]
            consumed_time = parse_time_info(file_data)
            hardware = parse_hardware_info(file_data)
            lemma_results = parse_lemma_results(file_data)
            for lemma in HypothesisLemmas:
                lemma_result = [l for l in lemma_results if l['name'] == lemma][0]
                cases_data[case][lemma] = {
                    "time": consumed_time,
                    "hardware": hardware,
                    "type": lemma_result["type"],
                    "steps": lemma_result["steps"],
                    "result": result_data[lemma],
                }

            for lemma in result_data:
                if lemma in HypothesisLemmas:
                    continue

                if result_data[lemma] != "verified" and result_data[lemma] != "falsified":
                    cases_data[case][lemma] = {
                        "time": "0",
                        "hardware": "unknown",
                        "type": lemmas_type[lemma],
                        "steps": "0",
                        "result": result_data[lemma],
                    }
                    continue

                lemma_file = f"{lemmas_hash([lemma])}.spthy"
                lemma_file = f'{RESULTS}/{case}/{lemma_file}'
                with open(lemma_file, 'r', encoding='utf8') as f:
                    file_data = f.read()
                    file_data = file_data.split("summary of summaries:")[1]

                consumed_time = parse_time_info(file_data)
                hardware = parse_hardware_info(file_data)
                lemma_results = parse_lemma_results(file_data)
                lemma_result = [l for l in lemma_results if l['name'] == lemma][0]
                cases_data[case][lemma] = {
                    "time": consumed_time,
                    "hardware": hardware,
                    "type": lemma_result["type"],
                    "steps": lemma_result["steps"],
                    "result": result_data[lemma],
                }

                if  does_have_trace(lemma_result["type"], result_data[lemma]):
                    gpath = f'./{OUTPUT_DIR}/imgs/{case}_{lemma}.{IMG_FORMAT.lower()}'
                    cases_data[case][lemma]['graph'] = gpath
                    spthy_with_trace_files.append(lemma_file)
    else:
        with open(f'{OUTPUT_DIR}/results.json', 'r', encoding='utf8') as f:
            cases_data = json.load(f)   
        spthy_with_trace_files = []
        for case in cases_data:
            for lemma in cases_data[case]:
                if 'graph' in cases_data[case][lemma]:
                    spthy_with_trace_files.append(f'{RESULTS}/{case}/{lemmas_hash([lemma])}.spthy')

    # save cases data
    with open(f'{OUTPUT_DIR}/results.json', 'w', encoding='utf8') as f:
        json.dump(cases_data, f, indent=4)

    if not CRAWL_GRAPH:
        exit(0)

    print("Start crawling images")
    # compress results
    if not os.path.exists(f'./{RESULTS}.tar.gz'):
        print("Compressing results...")
        if 'Windows' == platform.system():
            os.system(f'wsl -e tar -czf ./{RESULTS}.tar.gz ./{RESULTS}')
        else:
            os.system(f'tar -czf ./{RESULTS}.tar.gz ./{RESULTS}')
        if not os.path.exists(f'./{RESULTS}.tar.gz'):
            print("Failed to compress results")
            exit(1)

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

        load_image(server) # load image

        # send results and uncompress it
        if not server.is_file_exist(f'./{RESULTS}.tar.gz') or FORCE_PUSH:
            server.copy_file_to_workdir(f'./{RESULTS}.tar.gz', f'{RESULTS}.tar.gz')
            server.excute(f'[ -d {RESULTS} ] && rm -rf {RESULTS}')
            server.excute(f'tar -mxzf {RESULTS}.tar.gz')

    # create crawlers
    crawlers = []
    containers_info = {}
    for server in servers:
        for i in range(server.workers):
            port = 63001 + i
            name = f'tamarin_result-{server.host}-{port}'.replace('.', '-')
            crawler = Crawler(port, name, server, i)
            crawlers.append(crawler)

    # start crawling
    threading_pool = []
    spthy_pool = FilePool(spthy_with_trace_files)
    for crawler in crawlers:
        t = threading.Thread(target=crawler.start_worker, args=(spthy_pool,))
        threading_pool.append(t)
        t.start()

    for t in threading_pool:
        t.join()

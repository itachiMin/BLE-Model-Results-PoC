import os
import time
import json
import shutil
import threading
from typing import List
from reprint import output
from argparse import ArgumentParser

from utils.log import logging
from utils.cases import case_sort
from utils.server import Server
from utils.tamarin import LemmaTraverser, tamarin_command, lemmas_hash, parse_lemma_results, parse_time_info
from utils.docker import load_image, is_container_exist, IMAGE_NAME, IMAGE_VERSION

CASES_DIR = './cases'
CONTAINER_NAME = 'tamarin_ble_verify'
OUTPUT_DIR = "./results"

LEMMAS_CONF = 'lemmas.json'
SERVER_CONF = 'servers.json'
RUNNING_CONF = "running.json"

CHECK_TIME = 10

server_case_map = {}
global_lock = threading.Lock()

class FilePool():
    def __init__(self, files: list) -> None:
        self.files = files
        self.total = len(files)
        self.progress = 0
        self.lock = threading.Lock()

    def pop(self):
        if len(self.files) == 0:
            return None
        self.lock.acquire()
        file = self.files.pop(0)
        self.lock.release()
        return file

    def push(self, file: str):
        self.lock.acquire()
        self.files.append(file)
        self.lock.release()
        
    def remove(self, file: str):
        self.lock.acquire()
        self.files.remove(file)
        self.lock.release()

    def update(self, num: int):
        self.lock.acquire()
        self.progress += num
        self.lock.release()

    def get_progress_bar(self):
        progress = self.progress
        total = self.total

        width = 50
        progress_chars = int(width * (progress / total))
        progress_percent = round((progress / total) * 100, 2)

        progress_str = '[' + '#' * progress_chars + \
            ' ' * (width - progress_chars) + ']'
        stats_str = f' {progress_percent}% ({progress}/{total})'

        return progress_str + stats_str


class Verifier():
    def __init__(self, server: Server, num: int, outdir: str) -> None:
        self.num = num
        self.outdir = outdir
        self.server = server
        self.finish_cnt = 0
        self.current_file = ""
        self.current_progress = ""
        self.container_workdir = f"{num}"
        self.container_name = f"{CONTAINER_NAME}_{num}"
        self.container_hostname = f"{self.server.host}_{num}".replace('.', '_')

    def create(self):
        self.server.excute(
            f'[ -d {self.container_workdir} ] && rm -rf {self.container_workdir}')
        self.server.excute(f'mkdir -p {self.container_workdir}/cases')
        self.server.excute(f'mkdir -p {self.container_workdir}/proofs')
        self.server.copy_file_to_workdir(
            'files/hardware.py', f'{self.container_workdir}/hardware.py')

    def process_result(self, lemmas: List[str], result: str) -> List[bool]:
        with open(result, 'r', encoding='utf8') as f:
            result_content = f.read()
            result_content = result_content.split('summary of summaries:')[1]
        raw_result = parse_lemma_results(result_content)
        raw_result = {r['name']: r for r in raw_result}
        result = []
        for lemma in lemmas:
            if lemma in raw_result:
                if 'verified' in raw_result[lemma]['result']:
                    result.append(True)
                else:
                    result.append(False)
            else:
                raise Exception(f'Failed to find verfication result of {lemma}')
        return result, parse_time_info(result_content)

    def verify_lemmas(self, modelfile: str, lemmas: List[str], outdir: str) -> List[bool]:
        filename = modelfile.split('/')[-1]
        casename = filename.split('.')[0]
        lemmahash = lemmas_hash(lemmas)
        remote_file = f"/work/cases/{filename}"
        remote_result = f"/work/proofs/{casename}_{lemmahash}.spthy"
        local_result = f"{outdir}/{lemmahash}.spthy"

        verified = False
        if os.path.exists(local_result):
            try:
                result, _ = self.process_result(lemmas, local_result)
                logging.info(f'{casename}{lemmas} has been verified.')
                verified = True
            except:
                pass

        if not verified:
            logging.info(f'Verifying {casename}{lemmas} on {self.container_hostname}')

            # verify hypothesis lemmas
            cmd = tamarin_command(remote_file, remote_result, lemmas=lemmas)
            # get hardware information
            cmd += f" && python3 /work/hardware.py >> {remote_result}"

            docker = f'docker run -d --rm --name {self.container_name}'
            docker += f' -v {self.server.workdir}/{self.container_workdir}:/work'
            docker += f' -w /work'
            docker += f' -e CONTAIN_HNAME={self.container_hostname}'
            docker += f' {IMAGE_NAME}:{IMAGE_VERSION} bash -c "{cmd}"'
            self.server.excute(docker)

            # wait
            while is_container_exist(self.server, self.container_name):
                time.sleep(CHECK_TIME)
            # get results
            remote_result = self.container_workdir + \
                f"/proofs/{casename}_{lemmahash}.spthy"
            self.server.copy_file_from_workdir(remote_result, local_result)

            result, time_used = self.process_result(lemmas, local_result)
            logging.info(f'Verified {casename}{lemmas} using {time_used}.')

        return result

    def restore_verify_lemmas(self, modelfile: str, lemmas: List[str], outdir: str) -> List[bool]:
        filename = modelfile.split('/')[-1]
        casename = filename.split('.')[0]
        lemmahash = lemmas_hash(lemmas)
        remote_result = f"/work/proofs/{casename}_{lemmahash}.spthy"
        local_result = f"{outdir}/{lemmahash}.spthy"
        
        verified = False
        if os.path.exists(local_result):
            try:
                result, _ = self.process_result(lemmas, local_result)
                logging.info(f'{casename}{lemmas} has been verified.')
                verified = True
            except:
                pass
            
        if not verified:
            logging.info(f'Restore verifying {casename}{lemmas} on {self.container_hostname}')

            # wait
            while is_container_exist(self.server, self.container_name):
                time.sleep(CHECK_TIME)
            # get results
            remote_result = self.container_workdir + \
                f"/proofs/{casename}_{lemmahash}.spthy"
            self.server.copy_file_from_workdir(remote_result, local_result)

            result, time_used = self.process_result(lemmas, local_result)
            logging.info(f'Verified {casename}{lemmas} using {time_used}.')

        return result
    
    def verify(self, modelfile: str, restore_lemmas: List[str] = []):
        filename = modelfile.split('/')[-1]
        self.current_file = filename
        remote_file = f"{self.container_workdir}/cases/{filename}"
        self.server.copy_file_to_workdir(modelfile, remote_file)

        outdir = f"{self.outdir}/{filename.split('.')[0]}"
        os.makedirs(outdir, exist_ok=True)

        traverser = LemmaTraverser(modelfile, LEMMAS_CONF)
        self.current_progress = f'{traverser.finished}/{traverser.total}'
        hypothesis_result = self.verify_lemmas(
            modelfile, traverser.hypothesis, outdir)
        if False in hypothesis_result:
            logging.error(
                f'{filename} failed to pass the hypothesis lemma verification.')
            return
        traverser.finished += len(traverser.hypothesis)

        for lemmas in traverser.traverse():
            for l in lemmas:
                self.current_progress = f'{traverser.finished}/{traverser.total}'
                
                global_lock.acquire()
                server_case_map[self.container_hostname] = (modelfile, l)
                with open(RUNNING_CONF, "w", encoding="utf8") as f:
                    json.dump(server_case_map, f)
                global_lock.release()
                
                if [l] == restore_lemmas:
                    r = self.restore_verify_lemmas(modelfile, [l], outdir)
                else:
                    r = self.verify_lemmas(modelfile, [l], outdir)
                    pass
                    
                traverser.mark_lemmas([l], r)
        global_lock.acquire()
        server_case_map.pop(self.container_hostname)
        with open(RUNNING_CONF, "w", encoding="utf8") as f:
            json.dump(server_case_map, f)
        global_lock.release()
        self.current_progress = f'{traverser.finished}/{traverser.total}'

        # save result
        lemmas_result = {}
        for lemma in traverser.hypothesis:
            lemmas_result[lemma] = 'verified'
        for graph in traverser.graphs:
            for node in graph.lemma_nodes_list:
                lemmas_result[node.lemma] = node.verified
        with open(f'{outdir}/result.json', 'w', encoding='utf8') as f:
            json.dump(lemmas_result, f, indent=4)

    def stop_verify(self):
        self.server.excute(f'docker rm -f {self.container_name}')

    def verify_loop(self, filepool: FilePool, running: list):
        running_file_lemma = None
        for r in running:
            if self.container_hostname == r:
                running_file_lemma = running[r]
                break
            
        while True:
            if running_file_lemma is None:
                file = filepool.pop()
                restore_lemmas = []
            else:
                file = running_file_lemma[0]
                restore_lemmas = [running_file_lemma[1]]
                running_file_lemma = None
                
            if file is None:
                break
            
            try:
                self.verify(file, restore_lemmas=restore_lemmas)
                fin = f'Finished verifying {file} on '
                fin += f'{self.server.host}[container_{self.num}]'
                logging.info(fin)
                filepool.update(1)
                self.finish_cnt += 1
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    break
                error = f'Failed to verify {file} on '
                error += f'{self.server.host}[container_{self.num}]: '
                error += str(e)
                logging.error(error)
                filepool.push(file)

                if is_container_exist(self.server, self.container_name):
                    self.stop_verify()


def main():
    parser = ArgumentParser(
        description='Script to distribute and verify BLE cases')

    parser.add_argument('-s', action='store_true', help='force stop verify')
    parser.add_argument('-f', action='store_true',
                        help='force distribute and load image')
    args = parser.parse_args()
    stop = args.s
    force = args.f

    # load servers and verifier
    with open(SERVER_CONF, 'r')as f:
        servers_data = json.load(f)
    servers = []
    verifiers = []
    for s in servers_data:
        try:
            server = Server(
                s['host'], s['port'], s['username'], s['password'], s['workdir'],
                weight=s['weight'], workers=s['workers'])
            server.try_connection()
            servers.append(server)
            for i in range(s['workers']):
                verifier = Verifier(server, i, OUTPUT_DIR)
                verifiers.append(verifier)
        except:
            err = f'Failed to create verifier '
            err += f'container on {server.host}\n'
            logging.error(err)

    # if stop, stop all verifiers
    if stop:
        for verifier in verifiers:
            print(f'Stopping verify on ' +
                  f'{verifier.server.host}[container_{verifier.num}]')
            verifier.stop_verify()
        return

    # load docker image
    for server in servers:
        load_image(server, force)

    # create verifier work env
    for verifier in verifiers:
        verifier.create()

    # create output dir
    if force and os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # restore last process
    if os.path.exists(RUNNING_CONF):
        with open(RUNNING_CONF, 'r') as f:
            running = json.load(f)
    else:
        running = []
    
    # load cases
    files = os.listdir(CASES_DIR)
    files = [f for f in files if f.endswith('.spthy')]
    cases = case_sort(files)
    cases = [f"{CASES_DIR}/{f}" for f in cases]
    cases_pool = FilePool(cases)
    
    # remove running files
    for r in running:
        cases_pool.remove(running[r][0])
        
    # start verify
    threading_pool = []
    for verifier in verifiers:
        t = threading.Thread(target=verifier.verify_loop, args=(cases_pool, running, ))
        t.start()
        threading_pool.append(t)

    def all_finished():
        for t in threading_pool:
            if t.is_alive():
                return False
        return True

    with output(output_type="list", initial_len=1+len(verifiers), interval=0) as output_list:
        while not all_finished():
            time.sleep(1)
            pbar = cases_pool.get_progress_bar()
            for ind, verifier in enumerate(verifiers):
                name = f'{verifier.server.host}[{verifier.num}]'
                out = f"{name} ({verifier.finish_cnt} finished): "
                out += f'{verifier.current_file}[{verifier.current_progress}]'
                output_list[ind] = out
            output_list[-1] = f'progress: {pbar}'


if __name__ == "__main__":
    logging.info('='*10+' Verifying Starts '+'='*10)
    main()
    logging.info('='*10+' Verifying Ends '+'='*12)

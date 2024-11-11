import os
import re
import json
from argparse import ArgumentParser

TAMARIN_PATH = "tamarin-prover"

parser = ArgumentParser(description='Script to verify BLE-SC models.')
parser.add_argument('-f', type=str, help='The file of BLE-SC model.')
parser.add_argument('-m', type=str, help='The mid file of generated BLE-SC models.')
parser.add_argument('--lemma', type=str, default="", help='The lemma to verify.')
parser.add_argument('--remote', action='store_true', help='Remote mode.')
parser.add_argument('--interactive', action='store_true', help='Interactive mode.')
parser.add_argument('--root', type=str, default="/work", help='Root directory.')



args = parser.parse_args()
if not args.interactive:
    assert args.m or args.f, "Please specify the BLE-SC models."
lemma = args.lemma
root = args.root
assert os.path.exists(root), f"Root directory {root} does not exist."

log = open("verify.log", "w")


def get_hardware_info():
    def get_cpu_info():
        cpu_info = {}

        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.strip():
                    key, value = [x.strip() for x in line.strip().split(':')]
                    if key == 'model name':
                        cpu_info['model'] = value
                    elif key == 'cpu MHz':
                        cpu_info['frequency'] = value
                    elif key == 'cpu cores':
                        cpu_info['pcores'] = value
        cpu_info['lcores'] = os.sysconf("SC_NPROCESSORS_ONLN")
        return cpu_info

    def get_memory_info():
        memory_info = {}

        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.strip():
                    key, value = [x.strip() for x in line.strip().split(':')]
                    if key == 'MemTotal':
                        memory_info['total'] = re.match(r'\d+', value).group()
                    elif key == 'MemFree':
                        memory_info['free'] = re.match(r'\d+', value).group()

        return memory_info

    cpu_info = get_cpu_info()
    memory_info = get_memory_info()
    hostname = os.getenv('CONTAIN_HNAME')

    result = ""
    result += "="*15 + f" Hardware Information for {hostname} " + "="*15 + "\n"
    result += f"CPU Model: {cpu_info.get('model')}\n"
    result += f"CPU Phycial Cores: {cpu_info.get('pcores')}\n"
    result += f"CPU Logical Cores: {cpu_info.get('lcores')}\n"
    result += f"CPU Frequency: {cpu_info.get('frequency')} MHz\n"
    result += f"Total Memory: {int(memory_info.get('total')) // (1024 * 1024)} GB\n"

    return result


hardware_info = get_hardware_info()

if args.interactive:
    log.write(f"Interactive mode: {root}\n")
    os.system(f"nohup socat TCP-LISTEN:3002,fork TCP:127.0.0.1:3001 > /dev/null 2>&1 &")
    os.system(f'{TAMARIN_PATH} interactive --image=SVG --derivcheck-timeout=0 {root}')
else:
    log.write(f"Verifying BLE-SC models: {args.m}\n")
    os.makedirs("proofs", exist_ok=True)
    if args.f:
        inputs = [args.f]
    else:
        with open(args.m, "r") as f:
            inputs = json.load(f)
    for i in inputs:
        assert os.path.exists(i), f"File {i} does not exist."
    total = len(inputs)
    current = 0
    for i in inputs:
        name = i.split("/")[-1]
        o = f"proofs/proof_{name}"

        i = os.path.join(root, i)
        o = os.path.join(root, o)

        if args.remote:
            with open(f".verify.tmp", "w") as f:
                json.dump({"current": current, "total": total, "name": name, "finished": False}, f)
        else:
            print(f"Verifying [{current+1}/{total}] {name}")
        if lemma:
            log.write(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 --prove={lemma} {i} --output={o} > {o}.tmp\n')
            os.system(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 --prove={lemma} {i} --output={o} > {o}.tmp')
        else:
            log.write(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 {i} --prove --output={o} > {o}.tmp\n')
            os.system(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 {i} --prove --output={o} > {o}.tmp')
        with open(f"{o}.tmp", "r") as f:
            info = f.read()
        with open(o, 'a') as f:
            f.write(info+"\n\n")
            f.write(hardware_info)
        os.remove(f"{o}.tmp")
        current += 1

    if args.remote:
        with open(f".verify.tmp", "w") as f:
            json.dump({"current": current, "total": total, "name": "finished", "finished": True}, f)

log.close()

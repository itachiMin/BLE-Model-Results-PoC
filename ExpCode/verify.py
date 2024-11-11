import os
import json
from argparse import ArgumentParser

TAMARIN_PATH = "tamarin-prover"

parser = ArgumentParser(description='Script to verify BLE-SC models.')
parser.add_argument('-m', type=str, help='The mid file of generated BLE-SC models.')
parser.add_argument('--lemma', type=str, default="", help='The lemma to verify.')
parser.add_argument('--remote', action='store_true', help='Remote mode.')
parser.add_argument('--interactive', action='store_true', help='Interactive mode.')
parser.add_argument('--root', type=str, default="/work", help='Root directory.')


args = parser.parse_args()
if not args.interactive:
    assert args.m, "Please specify the mid file of generated BLE-SC models."
lemma = args.lemma
root = args.root
assert os.path.exists(root), f"Root directory {root} does not exist."

log = open("verify.log", "w")

if args.interactive:
    log.write(f"Interactive mode: {root}\n")
    os.system(f"nohup socat TCP-LISTEN:3002,fork TCP:127.0.0.1:3001 > /dev/null 2>&1 &")
    os.system(f'{TAMARIN_PATH} interactive --image=SVG --derivcheck-timeout=0 {root}')
else:
    log.write(f"Verifying BLE-SC models: {args.m}\n")
    os.makedirs("proofs", exist_ok=True)
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
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 --saturatio=1 --prove={lemma} {i} --output={o} > {o}.tmp\n')
            os.system(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 --saturatio=1 --prove={lemma} {i} --output={o} > {o}.tmp')
        else:
            log.write(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 --saturatio=1 {i} --output={o} > {o}.tmp\n')
            os.system(
                f'{TAMARIN_PATH} +RTS -N60 -RTS --derivcheck-timeout=0 --saturatio=1 {i} --output={o} > {o}.tmp')
        with open(f"{o}.tmp", "r") as f:
            info = f.read()
        with open(o, 'w') as f:
            f.write(info+"\n")
        os.remove(f"{o}.tmp")
        current += 1

    if args.remote:
        with open(f".verify.tmp", "w") as f:
            json.dump({"current": current, "total": total, "name": "finished", "finished": True}, f)

log.close()

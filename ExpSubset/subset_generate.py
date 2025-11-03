import os
import sys
import json

with open('./subset_cases.json', 'r') as f:
    CASES = json.load(f)
TEMPLATE = 'main.m4'
OUTPUT_DIR = 'cases'

WORKSPACE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ExpCode'))
os.chdir(WORKSPACE)
sys.path.insert(0, WORKSPACE)

from generate import BLE_SC_Feature, generate_case

if __name__ == '__main__':
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for case in CASES:
        i_features = BLE_SC_Feature(*case['init'])
        r_features = BLE_SC_Feature(*case['resp'])
        generate_case(TEMPLATE, i_features, r_features, OUTPUT_DIR)

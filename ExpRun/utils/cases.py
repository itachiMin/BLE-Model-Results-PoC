from typing import List

def case_sort(files: List[str]):
    def num(f):
        if "NoOOB" not in f:
            return 0
        if "NoOOB" in f and "NoAuthReq" not in f:
            return 1
        return 2
    return sorted(files, key=num)

import re
import os
import json
import hashlib
from bs4 import BeautifulSoup
from typing import Generator, List, Tuple

from .log import logging


class LemmaNode(object):
    def __init__(self, lemma: str) -> None:
        self.lemma = lemma
        self.depth = -1
        self.marked = False
        self.verified = None
        self.parents = []
        self.children = []

    def add_parent(self, parent):
        self.parents.append(parent)

    def add_child(self, child):
        self.children.append(child)

    def mark(self, result: str):
        self.marked = True
        self.verified = result

    def mark_children(self, result: str, suffix='') -> int:
        if suffix == '':
            suffix = f'implied by {self.lemma}'
        else:
            suffix =  f'{suffix[:11]}{self.lemma} <- {suffix[11:]}' 

        mark_number = 0
        for child in self.children:
            if not child.marked:
                child.marked = True
                child.verified = f'{result} ({suffix})'
                mark_number += 1
                mark_number += child.mark_children(result, suffix)
        return mark_number

    def mark_parents(self, result: str, suffix='') -> int:
        if suffix == '':
            suffix = f'implies {self.lemma}'
        else:
            suffix =  f'{suffix[:8]}{self.lemma} -> {suffix[8:]}' 

        mark_number = 0
        for parent in self.parents:
            if not parent.marked:
                parent.marked = True
                parent.verified = f'{result} ({suffix})'
                mark_number += 1
                mark_number += parent.mark_parents(result, suffix)
        return mark_number


class LemmaGraph(object):
    def __init__(self, base_lemma: str, implied_rules: list, all_lemmas: list) -> None:
        self.direction = True  # True for top-down, False for bottom-up
        self.lemma_nodes_list = []
        self.lemma_nodes_map = {}

        base_node = LemmaNode(base_lemma)
        self.lemma_nodes_list.append(base_node)
        self.lemma_nodes_map[base_lemma] = base_node
        all_lemmas.remove(base_lemma)

        for rule in implied_rules:
            lemma_name = rule['name'].replace('*', base_lemma)

            if not lemma_name in all_lemmas:
                continue

            new_node = LemmaNode(lemma_name)
            self.lemma_nodes_list.append(new_node)
            self.lemma_nodes_map[lemma_name] = new_node
            all_lemmas.remove(lemma_name)

            for implied_by in rule['impliedby']:
                implied_name = implied_by.replace('*', base_lemma)
                if implied_name in self.lemma_nodes_map:
                    self.lemma_nodes_map[implied_name].add_child(new_node)
                    new_node.add_parent(self.lemma_nodes_map[implied_name])
                else:
                    logging.warning(f'{implied_name} not found in the graph.')

        self.top_ptr = 0
        self.bottom_ptr = len(self.lemma_nodes_list) - 1
        self.dfs_set_depth(base_node, 0)
        self.lemma_nodes_list.sort(key=lambda x: x.depth)

    def is_tranversed(self) -> bool:
        while self.top_ptr <= self.bottom_ptr and self.lemma_nodes_list[self.top_ptr].marked:
            self.top_ptr += 1
        while self.bottom_ptr >= self.top_ptr and self.lemma_nodes_list[self.bottom_ptr].marked:
            self.bottom_ptr -= 1
        return self.top_ptr > self.bottom_ptr

    def find_node(self, lemma: str) -> LemmaNode:
        return self.lemma_nodes_map.get(lemma, None)

    def dfs_set_depth(self, node: LemmaNode, depth: int):
        if node.depth != -1:
            return
        node.depth = depth
        for child in node.children:
            self.dfs_set_depth(child, depth + 1)

    def top_pop(self) -> str:
        lemma = None
        if not self.is_tranversed():
            lemma = self.lemma_nodes_list[self.top_ptr].lemma
            self.top_ptr += 1
        return lemma

    def bottom_pop(self) -> str:
        lemma = None
        if not self.is_tranversed():
            lemma = self.lemma_nodes_list[self.bottom_ptr].lemma
            self.bottom_ptr -= 1
        return lemma

    def pop(self) -> str:
        if self.direction:
            return self.top_pop()
        else:
            return self.bottom_pop()


class LemmaTraverser(object):
    def __init__(self, model_file: str, config_file: str):
        if not os.path.exists(model_file):
            err = f"Model file {model_file} not found."
            logging.error(err)
            raise FileNotFoundError(err)
        if not os.path.exists(config_file):
            err = f"Configuration file{config_file} not found."
            logging.error(err)
            raise FileNotFoundError(err)

        with open(model_file, 'r', encoding='utf8') as f:
            lemmas = self.parse_model_lemmas(f.read())
        with open(config_file, 'r', encoding='utf8') as f:
            config = json.load(f)

        self.total = len(lemmas)
        self.finished = 0

        self.hypothesis = []
        for h in config['HypothesisLemmas']:
            if h in lemmas:
                self.hypothesis.append(h)
                lemmas.remove(h)
            else:
                logging.warning(f"{h} not found in the model.")

        # build lemma graphs according to the configuration
        self.graphs = []
        for base_lemma in config['BaseLemmas']:
            graph = LemmaGraph(base_lemma, config['ImpliedRules'], lemmas)
            self.graphs.append(graph)

        # build graphs which contains only one node for the remaining lemmas
        while len(lemmas) > 0:
            graph = LemmaGraph(lemmas[0], [], lemmas)
            self.graphs.append(graph)

    def parse_model_lemmas(self, text):
        lemmas = []
        lines = text.split('\n')
        for line in lines:
            if '//' in line:
                continue
            
            if 'lemma' in line:
                lemma = re.findall(r'lemma(.+):', line)
                if len(lemma) == 0:
                    continue
                lemma = lemma[0].strip().strip(':').split(' ')[0]
                lemmas.append(lemma)
        return lemmas

    def traverse(self) -> Generator[List[str], None, None]:
        graphs = self.graphs.copy()
        while len(graphs) > 0:
            yield [g.pop() for g in graphs]
            graphs = [g for g in graphs if not g.is_tranversed()]

    def find_graph_node(self, lemma: str) -> Tuple[LemmaGraph, LemmaNode]:
        for g in self.graphs:
            node = g.find_node(lemma)
            if node is not None:
                return g, node

    def mark_lemma_verified(self, lemma: str):
        graph, lemma_node = self.find_graph_node(lemma)
        assert graph is not None

        lemma_node.mark('verified')
        self.finished += 1
        if graph.direction:
            self.finished += lemma_node.mark_children('verified')
        else:
            graph.direction = True

    def mark_lemma_falsified(self, lemma: str):
        graph, lemma_node = self.find_graph_node(lemma)
        assert graph is not None

        lemma_node.mark('falsified')
        self.finished += 1
        if not graph.direction:
            self.finished += lemma_node.mark_parents('falsified')
        else:
            graph.direction = False

    def mark_lemmas(self, lemmas: List[str], results: List[bool]):
        for i, r in enumerate(results):
            if r:
                self.mark_lemma_verified(lemmas[i])
            else:
                self.mark_lemma_falsified(lemmas[i])

    def get_lemmas_result(self):
        data = {}
        for graph in self.graphs:
            for node in graph.lemma_nodes_list:
                data[node.lemma] = node.verified
        return data


def tamarin_command(i: str, o: str, tamarin='tamarin-prover', lemmas=[]):
    # tamarin-prover --stop-on-trace=SEQDFS --prove=ASConsistency_UserNotReusePasskey_UserNotUseGuessablePasskey_UserNotConfusePENC --derivcheck-timeout=0 --quiet ./cases/BLE-SC_I[KeyboardDisplay_NoOOB_AuthReq_KeyHigh]_R[KeyboardDisplay_NoOOB_AuthReq_KeyHigh].spthy --output=./cases/ASConsistency.spthy
    lemma_opt = ' '.join([f'--prove={l}' for l in lemmas])
    cmd = 'export LC_ALL=C.UTF-8'
    cmd += f' && {tamarin} +RTS -N6 -RTS --stop-on-trace=SEQDFS --derivcheck-timeout=0'
    cmd += f' {i} {lemma_opt} --output={o} > {o}.tmp'
    cmd += f' && echo "" >> {o} && cat {o}.tmp >> {o} && rm {o}.tmp'
    return cmd


def lemmas_hash(lemmas: List[str]) -> str:
    lemmas.sort()
    lemmas = '-'.join(lemmas)
    return hashlib.md5(lemmas.encode()).hexdigest()[:16]


def parse_theory_link(html: str, file: str):
    soup = BeautifulSoup(html, 'html.parser')
    trs = soup.find_all('tr')
    for tr in trs:
        tds = tr.find_all('td')
        if tds[2].text == 'Original' and \
                tds[3].text.split('/')[-1] == file:
            return tds[0].find('a', href=True)['href']
    return None


def parse_trace_links(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    trace_spans = soup.find_all('span', text='// trace found')
    trace_links = [s.parent['href'] for s in trace_spans]
    return trace_links


def parse_img_link(html: str):
    soup = BeautifulSoup(html, 'html.parser')
    img = soup.find('img')
    if img is None:
        return None
    else:
        return img['src'].strip()


def parse_lemma_results(text: str):
    lemmas = []
    pattern = r'(.+?) \((.+?)\): (.+?) \((.+?) steps\)'
    matches = re.findall(pattern, text)
    for m in matches:
        lemmas.append({
            "name": m[0].strip(),
            "type": m[1].strip(),
            "result": m[2].strip(),
            "steps": m[3].strip()
        })
    return lemmas


def parse_hardware_info(text: str):
    return {
        "CPU Model": re.findall(r'CPU Model: (.+)', text)[0].strip(),
        "CPU Phycial Cores": re.findall(r'CPU Phycial Cores: (.+)', text)[0].strip(),
        "CPU Logical Cores": re.findall(r'CPU Logical Cores: (.+)', text)[0].strip(),
        "CPU Frequency": re.findall(r'CPU Frequency: (.+)', text)[0].strip(),
        "Total Memory": re.findall(r'Total Memory: (.+)', text)[0].strip()
    }


def parse_time_info(text: str):
    return re.findall(r'processing time: (.+)', text)[0].strip()

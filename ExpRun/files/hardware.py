import os
import re


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
    memory = int(memory_info.get('total')) // (1024 * 1024)

    head = "="*15 + f" Hardware Information for {hostname} " + "="*20
    result = f"CPU Model: {cpu_info.get('model')}\n"
    result += f"CPU Phycial Cores: {cpu_info.get('pcores')}\n"
    result += f"CPU Logical Cores: {cpu_info.get('lcores')}\n"
    result += f"CPU Frequency: {cpu_info.get('frequency')} MHz\n"
    result += f"Total Memory: {memory} GB\n"
    tail = "="*len(head)
    result = head + "\n" + result + tail + "\n"

    return result


print(get_hardware_info())

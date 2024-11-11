from .server import Server


IMAGE_FILE = './files/tamarin-container_1.8.0.tar'
IMAGE_NAME = 'tamarin-container'
IMAGE_VERSION = '1.8.0'


def parse_docker_info(text: str):
    text = text.strip()
    def get_continus_space_index(text):
        indexs = []
        for i in range(1, len(text)-1):
            if text[i-1] == ' ' and text[i] == ' ':
                if len(indexs) != 0 and indexs[-1] == i-1:
                    indexs[-1] = i
                else:
                    indexs.append(i)
        return indexs
    
    split_point = get_continus_space_index(text.split('\n')[0])
    data = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        items = []
        start = 0
        for end in split_point:
            items.append(line[start:end].strip())
            start = end
        items.append(line[start:].strip())
        data.append(items)
    
    # zip data
    headers = data[0]
    data = data[1:]
    data = [dict(zip(headers, item)) for item in data]
            
    return data


def is_image_loaded(server: Server, image_name, image_version=None):
    stdout, stderr = server.excute('docker images')
    images = parse_docker_info(stdout)
    for image in images:
        if image['REPOSITORY'] == image_name:
            if image_version is None or image['TAG'] == image_version:
                return True
    return False

def is_container_exist(server: Server, container_name):
    stdout, stderr = server.excute('docker ps -a')
    containers = parse_docker_info(stdout)
    for container in containers:
        if container['NAMES'] == container_name:
            return True
    return False


def load_image(server: Server, force=False):
    loaded = is_image_loaded(server, IMAGE_NAME, IMAGE_VERSION)

    if loaded and not force:
        print(f'Image {IMAGE_NAME} already loaded to {server.host}')
        return
    else:
        print(f'Loading image {IMAGE_NAME} to {server.host}')
        server.copy_file_to_workdir(IMAGE_FILE, f'{IMAGE_NAME}.tar')
        server.excute(f'docker load -i {IMAGE_NAME}.tar')


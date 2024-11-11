import paramiko
import threading
import time
from .log import logging

class Server(object):
    def __init__(self, host, port, username, password, workdir, workers=1, weight=1) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.workdir = workdir
        self.workers = workers
        self.weight = weight
        self.finished = True
        self.ssh = None
        self.sftp = None
        self.cases = []
        self.lock = threading.Lock()
        self.max_retry_times = 5
        
    def connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.host, self.port, self.username, self.password)
        self.ssh = ssh
        self.sftp = ssh.open_sftp()
        self.ssh.exec_command(f'mkdir -p {self.workdir}')

    def is_connected(self):
        if self.ssh is None:
            return False
        
        transport = self.ssh.get_transport()
        if transport is not None and transport.is_active():
            return True
        else:
            return False

    def close(self):
        self.ssh.close()
        self.sftp.close()

    def try_connection(self):
        failed = False
        if not self.is_connected():
            self.lock.acquire()
            try:    
                self.connect()
            except:
                failed = True
            self.lock.release()
        if failed:
            raise Exception(f'{self.host} connection failed')

    def excute(self, command):
        self.try_connection()
        # excute command
        command = f'cd {self.workdir}; {command}'
        self.lock.acquire()
        retry = self.max_retry_times
        error = None
        while True:
            try:
                stdin, stdout, stderr = self.ssh.exec_command(command)
                break
            except Exception as e:
                retry -= 1
                if retry < 0:
                    error = e
                    break
                time.sleep(self.max_retry_times - retry)
        self.lock.release()
        if error:
            raise error
        stdout = stdout.read().decode('utf-8')
        stderr = stderr.read().decode('utf-8')
        if stderr:
            error = f'{self.host}: {stderr}'.strip()
            logging.error(error)
            print(f"[ERROR] {error}")
        return stdout, stderr

    def copy_file_to_workdir(self, local, remote):
        self.try_connection()
        remote = f"{self.workdir}/{remote}"
        self.lock.acquire()
        retry = self.max_retry_times
        error = None
        while True:
            try:
                self.sftp.put(local, remote)
                break
            except Exception as e:
                retry -= 1
                if retry < 0:
                    error = e
                    break
                time.sleep(self.max_retry_times - retry)
        self.lock.release()
        if error:
            raise error

    def copy_file_from_workdir(self, remote, local):
        self.try_connection()
        remote = f"{self.workdir}/{remote}"
        self.lock.acquire()
        retry = self.max_retry_times
        error = None
        while True:
            try:
                self.sftp.get(remote, local)
                break
            except Exception as e:
                retry -= 1
                if retry < 0:
                    error = e
                    break
                time.sleep(self.max_retry_times - retry)
        self.lock.release()
        if error:
            raise error
        
    def is_file_exist(self, remote):
        self.try_connection()
        remote = f"{self.workdir}/{remote}"
        self.lock.acquire()
        try:
            self.sftp.stat(remote)
            exists = True
        except:
            exists = False
        self.lock.release()
        return exists
        

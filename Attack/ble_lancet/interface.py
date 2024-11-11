import os
import queue
import asyncio
from scapy.utils import PcapWriter
from scapy.data import DLT_BLUETOOTH_LE_LL, DLT_BLUETOOTH_HCI_H4_WITH_PHDR
from .packet import LANCET_HEADER, HCI_PHDR_Hdr, BTLE_WITH_CTE


class Interface(object):
    __rfile__ = None
    
    def __init__(self) -> None:
        self.__buffer__ = queue.Queue()

    def put_data(self, data):
        self.record(data)
        self.__buffer__.put(data)

    def get_data(self):
        return self.__buffer__.get()

    async def generator(self):
        while True:
            if not self.__buffer__.empty():
                yield self.__buffer__.get()
            else:
                await asyncio.sleep(0.01)

    def record(self, data):
        if self.__rfile__ == None:
            return
        else:
            self.__rfile__.write(data)

    def enable_record(self, rfile):
        if not isinstance(rfile, InterfaceRecordFile):
            raise Exception("rfile must be an instance of InterfaceRecordFile")
        self.__rfile__ = rfile

    def disable_record(self):
        self.__rfile__ = None


class InterfaceRecordFile(object):
    def __init__(self, rtype: str, layer: str, filename: str):
        assert rtype in ['text', 'pcap', 'pipe']
        assert layer in ['link', 'hci']
        assert filename != None or filename != ""

        self.rtype = rtype
        self.layer = layer
        self.filename = filename
        self.file = self.create_file()

    def create_file(self):
        if self.rtype == 'text':
            return open(self.filename, "w")
        elif self.rtype == 'pcap':
            if self.layer == 'link':
                return PcapWriter(self.filename, append=True, sync=True, linktype=DLT_BLUETOOTH_LE_LL)
            elif self.layer == 'hci':
                return PcapWriter(self.filename, append=True, sync=True, linktype=DLT_BLUETOOTH_HCI_H4_WITH_PHDR)
        elif self.rtype == 'pipe':
            if not os.path.exists(self.filename):
                os.mkfifo(self.filename)
            # use wireshark to open the pipe
            os.system(f"wireshark -k -i {self.filename} &")
            if self.rtype == 'link':
                return PcapWriter(self.filename, linktype=DLT_BLUETOOTH_LE_LL)
            elif self.rtype == 'hci':
                return PcapWriter(self.filename, linktype=DLT_BLUETOOTH_HCI_H4_WITH_PHDR)
        else:
            raise Exception("rtype must be text, pcap or pipe")

    def close(self):
        self.file.close()

    def write(self, data):
        if not isinstance(data, LANCET_HEADER):
            raise Exception("data must be an instance of LANCET_HEADER")

        if self.rtype == 'text':
            self.file.write(data.show(dump=True))
        elif self.rtype == 'pcap' or self.rtype == 'pipe':
            if self.layer == 'hci':
                assert isinstance(data.payload, HCI_PHDR_Hdr)
                self.file.write(data.payload.build())
            else:
                assert isinstance(data.payload, BTLE_WITH_CTE)
                data = data.payload.remove_cte()
                self.file.write(data.build())

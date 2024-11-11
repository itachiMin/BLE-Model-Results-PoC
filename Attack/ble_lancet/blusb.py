import usb.core
import usb.util
import asyncio
import threading

from .interface import Interface
from .packet import LANCET_HEADER, LANCET_MAGIC


class BLancetUSB(object):
    tasks = []
    read_ep = None
    write_ep = None
    interval = 0.01
    read_itf = Interface()
    write_itf = Interface()

    def __init__(self, idVendor, idProduct, interval=0.1):
        self.interval = interval
        self.idVendor = idVendor
        self.idProduct = idProduct

    async def start(self):
        dev = await self.__wait_for_device(self.idVendor, self.idProduct)
        assert dev is not None
        print(f"Found device {self.idVendor:04x}:{self.idProduct:04x}")

        cfg = dev.get_active_configuration()
        assert cfg is not None

        intf = cfg[(1, 0)]
        assert intf is not None

        def find_enpoint(direction): return usb.util.find_descriptor(
            intf,
            custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) == direction
        )

        self.read_ep = find_enpoint(usb.util.ENDPOINT_IN)
        assert self.read_ep is not None
        self.write_ep = find_enpoint(usb.util.ENDPOINT_OUT)
        assert self.write_ep is not None
        print(
            f"Found endpoints 0x{self.read_ep.bEndpointAddress:02x} and 0x{self.write_ep.bEndpointAddress:02x}")

        # start the read thread
        # self.tasks.append(asyncio.create_task(self.__read()))
        threading.Thread(target=self.__read_thread).start()
        # start the write thread
        self.tasks.append(asyncio.create_task(self.__write()))

    async def __wait_for_device(self, idVendor, idProduct):
        print(f"Waiting for device {idVendor:04x}:{idProduct:04x} ...")
        while True:
            dev = usb.core.find(idVendor=idVendor, idProduct=idProduct)
            if dev is not None:
                return dev
            await asyncio.sleep(self.interval)

    def __read_thread(self):
        buffer = b''
        while True:
            while True:
                try:
                    data = self.read_ep.read(64)
                    break
                except usb.core.USBError as e:
                    if e.errno != 110:
                        raise e
                    continue
            buffer += data

            drop_cnt = 0
            while buffer[0] != LANCET_MAGIC:
                buffer = buffer[1:]
                drop_cnt += 1
            if drop_cnt > 0:
                print(f'[WARNING] dropped {drop_cnt} bytes')

            if len(buffer) >= LANCET_HEADER.size:
                hdr = LANCET_HEADER(buffer)
                pkt_length = hdr.size + hdr.len
                if len(buffer) >= pkt_length:
                    data = buffer[:pkt_length]
                    self.read_itf.put_data(LANCET_HEADER(data))
                    buffer = buffer[pkt_length:]


    async def __write(self):
        async for pkt in self.write_itf.generator():
            assert isinstance(pkt, LANCET_HEADER)
            self.write_ep.write(pkt.build())

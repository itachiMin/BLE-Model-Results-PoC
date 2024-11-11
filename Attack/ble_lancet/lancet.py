import asyncio
import struct
from enum import Enum
from scapy.packet import Raw
from .blusb import BLancetUSB
from .engine import HijkerEngine
from .interface import Interface
from .packet import (
    Packet,
    LANCET_HEADER,
    BTLE_WITH_CTE,
    BTLE_DATA_WITH_CTE,
    HCI_PHDR_Hdr,
    HCI_Hdr,
)


class LancetItfID(Enum):
    Local2Lancet = 0
    Lancet2Local = 1
    Remote2Lancet = 2
    Lancet2Remote = 3


class LancetLayer(Enum):
    HCI = 0
    HLL = 1
    LLL = 2


class LancetMode(Enum):
    Monitor = 0
    Manipulate = 1


class ControlCode(Enum):
    BM_CTRL_SET_MODE = 0x01
    BM_CTRL_GET_ADDR = 0x02
    BM_CTRL_SET_PUB_ADDR = 0x03
    BM_CTRL_RET_ADDR = 0x81


INCOMING_IFS = [LancetItfID.Local2Lancet, LancetItfID.Remote2Lancet]
OUTGOING_IFS = [LancetItfID.Lancet2Local, LancetItfID.Lancet2Remote]


class Lancet:
    tasks = []
    local_addr = None
    remote_addr = None
    usb = BLancetUSB(0x2FE3, 0x000B)
    interfaces = {
        LancetItfID.Local2Lancet: Interface(),
        LancetItfID.Lancet2Local: Interface(),
        LancetItfID.Remote2Lancet: Interface(),
        LancetItfID.Lancet2Remote: Interface(),
    }
    engine_links = {LancetItfID.Local2Lancet: None, LancetItfID.Remote2Lancet: None}

    def __init__(self, layer: LancetLayer, mode: LancetMode):
        # listen all the interfaces
        for lif_id in OUTGOING_IFS:
            self.tasks.append(asyncio.create_task(self.oif_listener(lif_id)))

        self.layer = layer
        self.mode = mode

    async def oif_listener(self, lif_id):
        # process the outgoing packet of the lancet interface
        itf = self.interfaces[lif_id]
        async for pkt in itf.generator():
            if self.layer == LancetLayer.HCI:
                pkt.payload = pkt.payload[HCI_Hdr]
            else:
                pkt.payload = pkt.payload[BTLE_DATA_WITH_CTE]

            if isinstance(pkt.payload, Packet):
                pkt.len = len(pkt.payload.build())
            self.usb.write_itf.put_data(pkt)

    async def usb_listener(self):
        # process the incoming packet of the usb interface
        async for pkt in self.usb.read_itf.generator():
            if isinstance(pkt, LANCET_HEADER):
                if pkt.Control == 1:
                    payload = pkt.payload.load
                    ctrl_code = ControlCode(pkt.extra[0])
                    if ctrl_code == ControlCode.BM_CTRL_RET_ADDR:
                        assert len(payload) == 14
                        self.local_addr = payload[:7]
                        self.remote_addr = payload[7:]
                    continue

                if pkt.Debug == 1:
                    flags = pkt.extra
                    DBG_MAP = {
                        0: "plain",
                        1: "crypt",
                        2: "ccm",
                        4: "ltk",
                        5: "skd",
                        6: "sk",
                    }
                    msg = pkt.payload.load
                    BM_DBG_FLAG_STRING = 0x01
                    BM_DBG_FLAG_BINARY = 0x02
                    if BM_DBG_FLAG_STRING == flags[0]:
                        print(f"[DEBUG] {''.join([chr(b) for b in msg])}")
                    elif BM_DBG_FLAG_BINARY == flags[0]:
                        if flags[1] in DBG_MAP:
                            print(
                                f"[{DBG_MAP[flags[1]]}] {''.join([f'{b:02x}' for b in msg])}"
                            )
                        else:
                            print(f"[BINARY] {''.join([f'{b:02x}' for b in msg])}")

                    continue

                if self.layer == LancetLayer.HCI:
                    phdr_hdr = HCI_PHDR_Hdr()
                    phdr_hdr.direction = 1 - pkt.Direction
                    pkt.payload = phdr_hdr / HCI_Hdr(pkt.payload.load)
                else:
                    pkt.payload = BTLE_WITH_CTE(pkt.payload.load)

                if pkt.Direction == 0:
                    # TX Direction from local device
                    itf = self.interfaces[LancetItfID.Local2Lancet]
                    itf.put_data(pkt)
                else:
                    # RX Direction from remote device
                    itf = self.interfaces[LancetItfID.Remote2Lancet]
                    itf.put_data(pkt)
            else:
                raise Exception("Unknown packet type")

    def send_remote(self, packet):
        if self.layer == LancetLayer.HCI:
            assert packet.haslayer(HCI_Hdr)
        else:
            assert packet.haslayer(BTLE_DATA_WITH_CTE)

        hdr = LANCET_HEADER()
        hdr.Direction = 0
        self.interfaces[LancetItfID.Lancet2Remote].put_data(hdr / packet)

    def send_local(self, packet):
        if self.layer == LancetLayer.HCI:
            assert packet.haslayer(HCI_Hdr)
        else:
            assert packet.haslayer(BTLE_DATA_WITH_CTE)
        
        hdr = LANCET_HEADER()
        hdr.Direction = 1
        self.interfaces[LancetItfID.Lancet2Local].put_data(hdr / packet)

    def set_mode(self) -> None:
        """
        Set the work mode.
        """
        MODE_CTRL_DATA = {
            (LancetLayer.LLL, LancetMode.Monitor): 0x10,
            (LancetLayer.LLL, LancetMode.Manipulate): 0x11,
            (LancetLayer.HLL, LancetMode.Monitor): 0x20,
            (LancetLayer.HLL, LancetMode.Manipulate): 0x21,
            (LancetLayer.HCI, LancetMode.Monitor): 0x40,
            (LancetLayer.HCI, LancetMode.Manipulate): 0x41,
        }
        hdr = LANCET_HEADER()
        hdr.Control = 1

        data = struct.pack("<B", MODE_CTRL_DATA[(self.layer, self.mode)])
        hdr.len = len(data)

        hdr.extra_size = 4
        hdr.extra = bytes([ControlCode.BM_CTRL_SET_MODE.value, 0, 0, 0])

        self.usb.write_itf.put_data(hdr / Raw(data))

        print(f"Set work mode to {self.layer.name} {self.mode.name}")

    def set_pub_addr(self, addr: bytes) -> None:
        """
        Set the public address of the local device.
        """
        assert len(addr) == 6
        hdr = LANCET_HEADER()
        hdr.Control = 1

        data = addr
        hdr.len = len(data)

        hdr.extra_size = 4
        hdr.extra = bytes([ControlCode.BM_CTRL_SET_PUB_ADDR.value, 0, 0, 0])

        self.usb.write_itf.put_data(hdr / Raw(data))

        print(f"Set public address to {addr.hex()}")

    def set_engine_link(self, iif_id, oif_id, *engines):
        """
        This function will tell Lancet, which engines need to process the packets from
        a certain incoming interface and which outgoing interface the processed packets
        need to be sent to.

        iif_id: incoming interface id
        oif_id: outgoing interface id
        engines: a list of engines or None, if None, the default HijkerEngine will be used
        """
        assert iif_id in INCOMING_IFS
        assert oif_id in OUTGOING_IFS
        iif = self.interfaces[iif_id]
        oif = self.interfaces[oif_id]

        for engine in engines:
            if not isinstance(engine, HijkerEngine):
                raise Exception("engine must be an instance of HijkerEngine")

        if len(engines) == 0:
            engines = [HijkerEngine()]

        engines[0].set_incoming_if(iif)
        for i in range(len(engines) - 1):
            engines[i + 1].set_incoming_if(Interface())
            engines[i].set_next_engine(engines[i + 1])
            self.tasks.append(asyncio.create_task(engines[i].run()))
        engines[-1].set_outgoing_if(oif)
        self.tasks.append(asyncio.create_task(engines[-1].run()))
        self.engine_links[iif_id] = engines[0]

    def print_engine_links(self):
        pass

    def add_task(self, task_func):
        if not asyncio.iscoroutinefunction(task_func):
            raise Exception("task_func must be a coroutine function")
        task = asyncio.create_task(task_func())
        self.tasks.append(task)

    async def start(self) -> list[asyncio.Task]:
        # start the usb interface
        await self.usb.start()

        # check if the engine links are set
        for iif_id in INCOMING_IFS:
            if self.engine_links[iif_id] is None:
                raise Exception(
                    f"Engine link for {iif_id} is not set, please call set_engine_link() first"
                )

        # set the work mode
        self.set_mode()

        # start the usb listener
        self.tasks.append(asyncio.create_task(self.usb_listener()))
        return self.tasks + self.usb.tasks

    async def start_and_wait(self) -> None:
        tasks = await self.start()
        await asyncio.gather(*tasks)


class LancetClient:
    # LancetClient enables user to control the lancet interactively
    def __init__(self, lancet: Lancet):
        self.lancet = lancet

    # TODO: implement the LancetClient

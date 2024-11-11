import inspect
import asyncio
from .utils import Frag
from .interface import Interface
from .vsm import BT_ROLE, BT_IOCAP, VirtualSecurityManager
from .packet import (
    Packet,
    LANCET_HEADER,
    SM_Hdr,
    BTLE_WITH_CTE,
    BTLE_DATA_WITH_CTE,
    L2CAP_Hdr,
)


class HijkerEngine:
    """
    HijkerEngine is the base class for all the engines.
    It does nothing but pass the packet from incoming interface to outgoing interface
    You can override the process method to process the packet
    """

    def __init__(self) -> None:
        # incoming_if is a Interface object which provides the incoming packets
        self.incoming_if = None
        # outgoing_if is a Interface object where the outgoing packets are sent
        self.outgoing_if = None
        # next_engine is a HijkerEngine object which will process the packets after this engine
        self.next_engine = None

        self.stop = False
        self.standby = False

    async def process(self, packet) -> list[Packet]:
        yield packet

    async def run(self) -> None:
        if self.incoming_if == None or self.outgoing_if == None:
            raise Exception("incoming_if and outgoing_if must be set")

        async for packet in self.incoming_if.generator():
            while self.stop:
                if packet is None:
                    self.incoming_if.put_data(packet)
                else:
                    packet = None
                await asyncio.sleep(0.1)

            if self.standby:
                self.outgoing_if.put_data(packet)
                continue

            async for pkt in self.process(packet):
                self.outgoing_if.put_data(pkt)

    def set_incoming_if(self, incoming_if) -> None:
        if not isinstance(incoming_if, Interface):
            raise Exception("incoming_if must be an instance of Interface")
        self.incoming_if = incoming_if

    def set_outgoing_if(self, outgoing_if) -> None:
        if not isinstance(outgoing_if, Interface):
            raise Exception("outgoing_if must be an instance of Interface")
        self.outgoing_if = outgoing_if

    def set_next_engine(self, engine) -> None:
        if not isinstance(engine, HijkerEngine):
            raise Exception("engine must be an instance of HijkerEngine")
        self.next_engine = engine
        self.set_outgoing_if(engine.incoming_if)


class RuleEngine(HijkerEngine):
    """
    RuleEngine will process the packet according to the rules
    """

    def __init__(self) -> None:
        super().__init__()
        self.rules = []

    def add_rule(self, rule) -> None:
        """
        rule is a function which takes a packet as input and returns a packet or a list of packets
        """
        if not callable(rule):
            raise Exception("rule must be a function")
        self.rules.append(rule)

    async def process(self, packet) -> list[Packet]:
        for rule in self.rules:
            if inspect.iscoroutinefunction(rule):
                packet = await rule(packet)
            else:
                packet = rule(packet)

        if packet is None:
            return
        
        if isinstance(packet, Packet):
            yield packet
        elif isinstance(packet, list):
            for pkt in packet:
                yield pkt
        else:
            raise Exception("rule must return a packet or a list of packets")


class ImposterEngine(HijkerEngine):
    """
    ImposterEngine has a virtual security manager and
    it can make valid responses to every SMP packet it receives
    """

    def __init__(self, iocap: BT_IOCAP, role: BT_ROLE) -> None:
        super().__init__()
        self.frag = Frag()
        self.vsm = VirtualSecurityManager(iocap, role, 16)

    async def process(self, packet):
        assert isinstance(packet, Packet)
        assert packet.haslayer(BTLE_WITH_CTE)

        ble_pkt = self.frag.ressemble(packet[BTLE_WITH_CTE])
        if ble_pkt is None:
            return
        elif ble_pkt == packet:
            yield packet
            return

        if ble_pkt.haslayer(SM_Hdr):
            async for smp_rsp in self.vsm.response_generator(ble_pkt[SM_Hdr]):
                ble_rsp = BTLE_WITH_CTE() / BTLE_DATA_WITH_CTE() / L2CAP_Hdr() / smp_rsp
                ble_rsp.access_addr = ble_pkt[BTLE_WITH_CTE].access_addr
                for fragment in self.frag.fragment(ble_rsp):
                    rsp = packet.copy()
                    rsp.payload = fragment
                    rsp.Direction = 1 - rsp.Direction
                    yield rsp
        else:
            for fragment in self.frag.fragment(ble_pkt):
                rsp = packet.copy()
                rsp.payload = fragment
                yield rsp

    async def send_pair_request(self, templete) -> None:
        assert isinstance(templete, LANCET_HEADER)
        assert self.vsm.role == BT_ROLE.INITIATOR

        async for pkt in self.vsm.response_generator(None):
            p = templete.copy()
            p[L2CAP_Hdr].payload = pkt
            self.outgoing_if.put_data(p)

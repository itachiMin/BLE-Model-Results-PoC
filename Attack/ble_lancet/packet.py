import struct
from scapy.compat import orb, chb
from scapy.packet import Packet, bind_layers
from scapy.layers.bluetooth import *
from scapy.layers.bluetooth4LE import *
from scapy.fields import BitField, BitEnumField, ByteField, StrLenField, XLEIntField, X3BytesField

LANCET_MAGIC = 0xAC


class LANCET_HEADER(Packet):
    # """
    # +--------------------------------------------------------------------------------------------------------+
    # |                                          Lancet Header                                                 |
    # +--------+---------+-------+-----------+----------+---------------+--------------+-----------------------+
    # |  Magic | Control | Debug | Direction | Reserved | Packet Length |  Extra Size  |       Extra Data      |
    # +--------+---------+-------+-----------+----------+---------------+--------------+-----------------------+
    # | 8 bits |  1 bit  | 1 bit |   1 bit   |  5 bits  |    8 bits     |    8 bits    |   [Extra Size] bytes  |
    # +--------+---------+-------+-----------+----------+---------------+--------------+-----------------------+
    # """
    name = "Lancet Header"
    size = 8
    fields_desc = [
        ByteField("Magic", LANCET_MAGIC),
        BitEnumField("Control", 0, 1, {0: "no", 1: "yes"}),
        BitEnumField("Debug", 0, 1, {0: "no", 1: "yes"}),
        BitEnumField("Direction", 0, 1, {0: "tx", 1: "rx"}),
        BitField("reserved", 0, 5),
        ByteField("len", 0),
        ByteField("extra_size", 4),
        StrLenField("extra", b'\x00\x00\x00\x00', length_from=lambda pkt: pkt.extra_size)
    ]


class BTLE_DATA_WITH_CTE(Packet):
    name = "BTLE data header with cte"
    fields_desc = [
        BitField("RFU", 0, 3),
        BitField("MD", 0, 1),
        BitField("SN", 0, 1),
        BitField("NESN", 0, 1),
        BitEnumField("LLID", 0, 2, {1: "continue", 2: "start", 3: "control"}),

        ByteField("len", None),
        ByteField("cte_info", 0),
    ]

    def remove_cte(self) -> BTLE_DATA:
        ble_data = BTLE_DATA()
        ble_data.RFU = self.RFU
        ble_data.MD = self.MD
        ble_data.SN = self.SN
        ble_data.NESN = self.NESN
        ble_data.LLID = self.LLID
        ble_data.len = self.len
        ble_data.payload = self.payload
        return ble_data

    def post_build(self, p, pay):
        if self.len is None:
            p = p[:-2] + chb(len(pay)) + chb(0)
        return p + pay


bind_layers(BTLE_DATA_WITH_CTE, L2CAP_Hdr, LLID=2)
bind_layers(BTLE_DATA_WITH_CTE, BTLE_CTRL, LLID=3)
bind_layers(BTLE_DATA_WITH_CTE, BTLE_EMPTY_PDU, {'len': 0, 'LLID': 1})


class BTLE_WITH_CTE(Packet):
    name = "BT4LE with CTE"
    fields_desc = [
        XLEIntField("access_addr", 0x8E89BED6),
        X3BytesField("crc", None)
    ]

    def remove_cte(self) -> BTLE:
        btle = BTLE()
        btle.access_addr = self.access_addr
        btle.crc = self.crc

        if isinstance(self.payload, BTLE_DATA_WITH_CTE):
            btle.payload = self.payload.remove_cte()
        else:
            btle.payload = self.payload

        return btle

    @staticmethod
    def compute_crc(pdu, init=0x555555):
        def swapbits(a):
            v = 0
            if a & 0x80 != 0:
                v |= 0x01
            if a & 0x40 != 0:
                v |= 0x02
            if a & 0x20 != 0:
                v |= 0x04
            if a & 0x10 != 0:
                v |= 0x08
            if a & 0x08 != 0:
                v |= 0x10
            if a & 0x04 != 0:
                v |= 0x20
            if a & 0x02 != 0:
                v |= 0x40
            if a & 0x01 != 0:
                v |= 0x80
            return v

        state = swapbits(init & 0xff) + (swapbits((init >> 8) & 0xff) << 8) + (swapbits((init >> 16) & 0xff) << 16)  # noqa: E501
        lfsr_mask = 0x5a6000
        for i in (orb(x) for x in pdu):
            for j in range(8):
                next_bit = (state ^ i) & 1
                i >>= 1
                state >>= 1
                if next_bit:
                    state |= 1 << 23
                    state ^= lfsr_mask
        return struct.pack("<L", state)[:-1]

    def post_build(self, p, pay):
        # Switch payload and CRC
        crc = p[-3:]
        p = p[:-3] + pay
        p += crc if self.crc is not None else self.compute_crc(p[4:])
        return p

    def post_dissect(self, s):
        self.raw_packet_cache = None  # Reset packet to allow post_build
        return s

    def pre_dissect(self, s):
        # move crc
        return s[:4] + s[-3:] + s[4:-3]

    def hashret(self):
        return struct.pack("!L", self.access_addr)


bind_layers(BTLE_WITH_CTE, BTLE_DATA_WITH_CTE)


def btle_data_add_cte(btle_data: BTLE_DATA) -> BTLE_DATA_WITH_CTE:
    btle_data_cte = BTLE_DATA_WITH_CTE()
    btle_data_cte.RFU = btle_data.RFU
    btle_data_cte.MD = btle_data.MD
    btle_data_cte.SN = btle_data.SN
    btle_data_cte.NESN = btle_data.NESN
    btle_data_cte.LLID = btle_data.LLID
    btle_data_cte.len = btle_data.len
    btle_data_cte.payload = btle_data.payload
    return btle_data_cte


def btle_add_cte(btle: BTLE) -> BTLE_WITH_CTE:
    btle_cte = BTLE_WITH_CTE()
    btle_cte.access_addr = btle.access_addr
    btle_cte.crc = btle.crc

    if isinstance(btle.payload, BTLE_DATA):
        btle_cte.payload = btle_data_add_cte(btle.payload)
    else:
        btle_cte.payload = btle.payload

    return btle_cte

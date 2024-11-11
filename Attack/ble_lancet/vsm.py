import asyncio
from enum import Enum
from typing import Callable
from random import getrandbits
from binascii import hexlify
from scapy.layers.bluetooth import (SM_Hdr, SM_Pairing_Request,
                                    SM_Pairing_Response, SM_Public_Key, SM_Confirm, SM_Random, SM_DHKey_Check)
from Crypto.PublicKey import ECC
from .crypto import f4, f5, f6, g2, P256


def random_bytes(n: int) -> bytes:
    return getrandbits(8 * n).to_bytes(n, byteorder='big')


class BT_IOCAP(Enum):
    """
    Bluetooth IO Capability
    """
    DISPLAY_ONLY = 0
    DISPLAY_YES_NO = 1
    KEYBOARD_ONLY = 2
    NO_INPUT_NO_OUTPUT = 3
    KEYBOARD_DISPLAY = 4


class BT_ROLE(Enum):
    """
    Bluetooth Role
    """
    INITIATOR = 0
    RESPONDER = 1


class BT_KEY_GENERATION_METHOD(Enum):
    """
    Bluetooth Key Generation Method
    """
    JUST_WORKS = 0
    PASSKEY_ENTRY = 1
    NUMERIC_COMPARISON = 2


KEY_GENERATION_METHOD_TABLE = {
    (BT_IOCAP.DISPLAY_ONLY, BT_IOCAP.DISPLAY_ONLY): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.DISPLAY_ONLY, BT_IOCAP.DISPLAY_YES_NO): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.DISPLAY_ONLY, BT_IOCAP.KEYBOARD_ONLY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.DISPLAY_ONLY, BT_IOCAP.NO_INPUT_NO_OUTPUT): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.DISPLAY_ONLY, BT_IOCAP.KEYBOARD_DISPLAY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,

    (BT_IOCAP.DISPLAY_YES_NO, BT_IOCAP.DISPLAY_ONLY): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.DISPLAY_YES_NO, BT_IOCAP.DISPLAY_YES_NO): BT_KEY_GENERATION_METHOD.NUMERIC_COMPARISON,
    (BT_IOCAP.DISPLAY_YES_NO, BT_IOCAP.KEYBOARD_ONLY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.DISPLAY_YES_NO, BT_IOCAP.NO_INPUT_NO_OUTPUT): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.DISPLAY_YES_NO, BT_IOCAP.KEYBOARD_DISPLAY): BT_KEY_GENERATION_METHOD.NUMERIC_COMPARISON,

    (BT_IOCAP.KEYBOARD_ONLY, BT_IOCAP.DISPLAY_ONLY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.KEYBOARD_ONLY, BT_IOCAP.DISPLAY_YES_NO): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.KEYBOARD_ONLY, BT_IOCAP.KEYBOARD_ONLY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.KEYBOARD_ONLY, BT_IOCAP.NO_INPUT_NO_OUTPUT): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.KEYBOARD_ONLY, BT_IOCAP.KEYBOARD_DISPLAY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,

    (BT_IOCAP.NO_INPUT_NO_OUTPUT, BT_IOCAP.DISPLAY_ONLY): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.NO_INPUT_NO_OUTPUT, BT_IOCAP.DISPLAY_YES_NO): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.NO_INPUT_NO_OUTPUT, BT_IOCAP.KEYBOARD_ONLY): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.NO_INPUT_NO_OUTPUT, BT_IOCAP.NO_INPUT_NO_OUTPUT): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.NO_INPUT_NO_OUTPUT, BT_IOCAP.KEYBOARD_DISPLAY): BT_KEY_GENERATION_METHOD.JUST_WORKS,

    (BT_IOCAP.KEYBOARD_DISPLAY, BT_IOCAP.DISPLAY_ONLY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.KEYBOARD_DISPLAY, BT_IOCAP.DISPLAY_YES_NO): BT_KEY_GENERATION_METHOD.NUMERIC_COMPARISON,
    (BT_IOCAP.KEYBOARD_DISPLAY, BT_IOCAP.KEYBOARD_ONLY): BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY,
    (BT_IOCAP.KEYBOARD_DISPLAY, BT_IOCAP.NO_INPUT_NO_OUTPUT): BT_KEY_GENERATION_METHOD.JUST_WORKS,
    (BT_IOCAP.KEYBOARD_DISPLAY, BT_IOCAP.KEYBOARD_DISPLAY): BT_KEY_GENERATION_METHOD.NUMERIC_COMPARISON,
}


class VirtualSecurityManager(object):
    """
    A implementation of the Security Manager.
    Currently only support the SC pairing.
    # TODO: support the legacy pairing
    """

    def __init__(self, iocap: BT_IOCAP, role: BT_ROLE, max_key_size: int) -> None:
        self.iocap = iocap
        self.role = role
        self.max_key_size = max_key_size
        self.key = ECC.generate(curve='P-256')
        self.local_addr = bytes([0x00]*7)

        self.remote_iocap = BT_IOCAP.KEYBOARD_DISPLAY
        self.remote_max_key_size = 16
        self.remote_pk = None
        self.remote_addr = bytes([0x00]*7)

        self.method = None
        self.display_or_entry = None

        self.dhkey = None
        self.ltk = None
        self.sk = None

        self.paring_stage = 1
        self.local_IOCAPs = bytes([self.iocap.value, 0, 0x2d])
        self.remote_IOCAPs = None

        self.__passkey_cb = None
        self.__numeric_cb = None

        self.isPaired = False

    def set_passkey_cb(self, cb: Callable[[None], int]) -> None:
        self.__passkey_cb = cb

    def set_numeric_cb(self, cb: Callable[[int], None]) -> None:
        self.__numeric_cb = cb

    def set_address(self, local_addr: bytes, remote_addr) -> None:
        assert len(local_addr) == 7
        assert len(remote_addr) == 7
        self.local_addr = local_addr[::-1]
        self.remote_addr = remote_addr[::-1]

    def pairing_request(self) -> SM_Hdr:
        """
        Generate a pairing request packet. Only used in the initiator role.
        """
        assert self.role == BT_ROLE.INITIATOR
        req = SM_Pairing_Request()
        req.iocap = self.iocap.value
        req.oob = 0
        req.authentication = 0x2d
        req.max_key_size = self.max_key_size
        req.initiator_key_distribution = 0x07
        req.responder_key_distribution = 0x05
        return SM_Hdr() / req

    def pairing_response(self) -> SM_Hdr:
        """
        Generate a pairing response packet. Only used in the responder role.
        """
        assert self.role == BT_ROLE.RESPONDER
        rsp = SM_Pairing_Response()
        rsp.iocap = self.iocap.value
        rsp.oob = 0
        rsp.authentication = 0x2d
        rsp.max_key_size = self.max_key_size
        rsp.initiator_key_distribution = 0x07
        rsp.responder_key_distribution = 0x05
        return SM_Hdr() / rsp

    def pairing_public_key(self) -> SM_Hdr:
        """
        Generate a pairing public key packet.
        """
        pk = SM_Public_Key()
        pk.key_x = self.key.pointQ.x.to_bytes(32, byteorder='little')
        pk.key_y = self.key.pointQ.y.to_bytes(32, byteorder='little')
        return SM_Hdr() / pk

    def pairing_confirm(self, confirm: bytes) -> SM_Hdr:
        """
        Generate a pairing confirm packet.
        """
        assert len(confirm) == 16
        cf = SM_Confirm()
        cf.confirm = confirm[::-1]
        return SM_Hdr() / cf

    def pairing_random(self, rand: bytes) -> SM_Hdr:
        """
        Generate a pairing random packet.
        """
        assert len(rand) == 16
        rd = SM_Random()
        rd.random = rand[::-1]
        return SM_Hdr() / rd

    def pairing_dhkey_check(self, check: bytes) -> SM_Hdr:
        """
        Generate a pairing DHKey check packet.
        """
        assert len(check) == 16
        ck = SM_DHKey_Check()
        ck.dhkey_check = check
        return SM_Hdr() / ck

    def recv_pairing_request(self, smp: SM_Pairing_Request) -> None:
        """
        Receive a pairing request packet. Only used in the responder role.
        """
        assert self.role == BT_ROLE.RESPONDER
        self.remote_iocap = BT_IOCAP(smp.iocap)
        self.remote_max_key_size = smp.max_key_size
        self.remote_IOCAPs = bytes([smp.iocap, smp.oob, smp.authentication])

    def recv_pairing_response(self, smp: SM_Pairing_Response) -> None:
        """
        Receive a pairing response packet. Only used in the initiator role.
        """
        assert self.role == BT_ROLE.INITIATOR
        self.remote_iocap = BT_IOCAP(smp.iocap)
        self.remote_max_key_size = smp.max_key_size
        self.remote_IOCAPs = bytes([smp.iocap, smp.oob, smp.authentication])

    def recv_pairing_public_key(self, smp: SM_Public_Key) -> None:
        """
        Receive a pairing public key packet.
        """
        self.remote_pk = ECC.EccPoint(
            int.from_bytes(smp.key_x, byteorder='little'),
            int.from_bytes(smp.key_y, byteorder='little')
        )

    def recv_pairing_confirm(self, smp: SM_Confirm) -> None:
        """
        Receive a pairing confirm packet.
        """
        self.remote_confirm = smp.confirm[::-1]

    def recv_pairing_random(self, smp: SM_Random) -> None:
        """
        Receive a pairing random packet.
        """
        self.remote_rand = smp.random[::-1]

    def decide_which_method(self) -> None:
        """
        Decide which method to use for key generation.
        """
        if self.role == BT_ROLE.INITIATOR:
            self.method = KEY_GENERATION_METHOD_TABLE[(self.iocap, self.remote_iocap)]
        else:
            self.method = KEY_GENERATION_METHOD_TABLE[(self.remote_iocap, self.iocap)]

        print(f"{self.role}: {self.method}")

    async def get_passkey(self) -> int:
        """
        Get a passkey from the user.
        """
        if self.__passkey_cb is not None:
            pk = self.__passkey_cb()
            while pk < 0 or pk > 999999:
                asyncio.sleep(0.1)
                pk = self.__passkey_cb()
            return pk
        else:
            pk = -1
            while pk < 0 or pk > 999999:
                pk = int(input("Enter passkey: "))
            return pk

    def show_numeric(self, num: int) -> None:
        """
        Show a numeric value to the user.
        """
        if self.__numeric_cb is not None:
            self.__numeric_cb(num)
        else:
            print(f"Numeric value: {num}")

    def paring_phase1(self, smp: SM_Hdr) -> SM_Hdr:
        if smp is None and self.role == BT_ROLE.INITIATOR:
            return self.pairing_request()
        elif smp.sm_command == 1 and self.role == BT_ROLE.RESPONDER:
            self.recv_pairing_request(smp[SM_Pairing_Request])
            return self.pairing_response()
        elif smp.sm_command == 2 and self.role == BT_ROLE.INITIATOR:
            self.recv_pairing_response(smp[SM_Pairing_Response])
            return self.pairing_public_key()
        elif smp.sm_command == 0x0c and self.role == BT_ROLE.RESPONDER:
            self.recv_pairing_public_key(smp[SM_Public_Key])
            self.paring_phase2_init()
            return self.pairing_public_key()
        elif smp.sm_command == 0x0c and self.role == BT_ROLE.INITIATOR:
            self.recv_pairing_public_key(smp[SM_Public_Key])
            self.paring_phase2_init()
            return None
        else:
            return None

    def paring_phase2_init(self) -> None:
        self.paring_stage = 2
        self.decide_which_method()

        self.remote_rand = None
        self.remote_confirm = None
        self.local_rand = random_bytes(16)

        if self.method == BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY:
            self.rab = -1
            self.pe_round = 0
            self.is_new_round = True
        else:
            self.rab = 0

        if self.role == BT_ROLE.INITIATOR:
            self.pka = self.key.pointQ.x.to_bytes(32, byteorder='big')
            self.pkb = self.remote_pk.x.to_bytes(32, byteorder='big')
        else:
            self.pka = self.remote_pk.x.to_bytes(32, byteorder='big')
            self.pkb = self.key.pointQ.x.to_bytes(32, byteorder='big')

    def paring_phase2_jw_nc(self, smp: SM_Hdr) -> SM_Hdr:
        """
        Phase 2 of pairing process for Just Works and Numeric Comparison.
        """
        if smp.sm_command == 0x0c and self.role == BT_ROLE.INITIATOR:
            return None
        elif smp.sm_command == 0x0c and self.role == BT_ROLE.RESPONDER:
            Cb = f4(self.pkb, self.pka, self.local_rand, bytes([0x00]))
            return self.pairing_confirm(Cb)
        elif smp.sm_command == 3 and self.role == BT_ROLE.INITIATOR:
            self.recv_pairing_confirm(smp[SM_Confirm])
            return self.pairing_random(self.local_rand)
        elif smp.sm_command == 4 and self.role == BT_ROLE.RESPONDER:
            self.recv_pairing_random(smp[SM_Random])
            Vb = g2(self.pka, self.pkb, self.remote_rand, self.local_rand)
            self.show_numeric(Vb)
            self.paring_phase3_init()
            return self.pairing_random(self.local_rand)
        elif smp.sm_command == 4 and self.role == BT_ROLE.INITIATOR:
            self.recv_pairing_random(smp[SM_Random])
            Cb = f4(self.pkb, self.pka, self.remote_rand, bytes([0x00]))
            if self.method == BT_KEY_GENERATION_METHOD.NUMERIC_COMPARISON and Cb != self.remote_confirm:
                raise Exception('Pairing failed: confirm value mismatch')
            else:
                Va = g2(self.pka, self.pkb, self.local_rand, self.remote_rand)
                self.show_numeric(Va)
                self.paring_phase3_init()
                return None
        else:
            return None

    async def paring_phase2_pe(self, smp: SM_Hdr) -> SM_Hdr:
        """
        Phase 2 of pairing process for Passkey Entry.
        """
        self.rab = self.rab if self.rab != -1 else await self.get_passkey()
        ri = bytes([((self.rab >> self.pe_round) & 0x01) | 0x80])
        if self.is_new_round and self.role == BT_ROLE.INITIATOR:
            self.is_new_round = False
            assert self.rab >= 0 and self.rab <= 999999
            cai = f4(self.pka, self.pkb, self.local_rand, ri)
            return self.pairing_confirm(cai)
        elif smp.sm_command == 3 and self.role == BT_ROLE.RESPONDER:
            self.recv_pairing_confirm(smp[SM_Confirm])
            cbi = f4(self.pkb, self.pka, self.local_rand, ri)
            return self.pairing_confirm(cbi)
        elif smp.sm_command == 3 and self.role == BT_ROLE.INITIATOR:
            self.recv_pairing_confirm(smp[SM_Confirm])
            return self.pairing_random(self.local_rand)
        elif smp.sm_command == 4 and self.role == BT_ROLE.RESPONDER:
            self.recv_pairing_random(smp[SM_Random])
            cai = f4(self.pka, self.pkb, self.remote_rand, ri)
            if cai != self.remote_confirm:
                raise Exception('Pairing failed: confirm value mismatch')
            self.pe_round += 1
            return self.pairing_random(self.local_rand)
        elif smp.sm_command == 4 and self.role == BT_ROLE.INITIATOR:
            self.recv_pairing_random(smp[SM_Random])
            cbi = f4(self.pkb, self.pka, self.remote_rand, ri)
            if cbi != self.remote_confirm:
                raise Exception('Pairing failed: confirm value mismatch')
            self.pe_round += 1
            if self.pe_round < 20:
                self.is_new_round = True
                return await self.paring_phase2_pe(None)
            else:
                return None
        else:
            return None

    async def paring_phase2(self, smp: SM_Hdr) -> SM_Hdr:
        if self.method == BT_KEY_GENERATION_METHOD.JUST_WORKS or \
                self.method == BT_KEY_GENERATION_METHOD.NUMERIC_COMPARISON:
            return self.paring_phase2_jw_nc(smp)
        elif self.method == BT_KEY_GENERATION_METHOD.PASSKEY_ENTRY:
            rsp = await self.paring_phase2_pe(smp)
            if self.pe_round >= 20:
                self.paring_phase3_init()
            return rsp

    def paring_phase3_init(self) -> None:
        self.paring_stage = 3

        # generate DHKey
        self.dhkey = P256(self.key.d, self.remote_pk)

        # generate LTK and MACKey
        k = None
        if self.role == BT_ROLE.INITIATOR:
            k = f5(self.dhkey, self.local_rand, self.remote_rand, self.local_addr, self.remote_addr)
        else:
            k = f5(self.dhkey, self.remote_rand, self.local_rand, self.remote_addr, self.local_addr)

        self.mackey = k[0:16]
        self.ltk = k[16:32]
        print(self.role, 'MAC: ', hexlify(self.mackey))
        print(self.role, 'LTK: ', hexlify(self.ltk))

    def paring_phase3(self, smp: SM_Hdr) -> SM_Hdr:
        if self.role == BT_ROLE.INITIATOR and (smp.sm_command == 3 or smp.sm_command == 4):
            ea = f6(self.mackey, self.local_rand, self.remote_rand, self.rab.to_bytes(16, byteorder='big'),
                    self.local_IOCAPs[::-1], self.local_addr, self.remote_addr)
            return self.pairing_dhkey_check(ea[::-1])
        elif self.role == BT_ROLE.RESPONDER and smp.sm_command == 0x0d:
            ea = f6(self.mackey, self.remote_rand, self.local_rand, self.rab.to_bytes(16, byteorder='big'),
                    self.remote_IOCAPs[::-1], self.remote_addr, self.local_addr)
            if ea[::-1] != smp[SM_DHKey_Check].dhkey_check:
                raise Exception('Pairing failed: DHKey check mismatch')
            else:
                eb = f6(self.mackey, self.local_rand, self.remote_rand, self.rab.to_bytes(16, byteorder='big'),
                        self.local_IOCAPs[::-1], self.local_addr, self.remote_addr)
                print(self.role, 'Pairing successful')
                return self.pairing_dhkey_check(eb[::-1])
        elif self.role == BT_ROLE.INITIATOR and smp.sm_command == 0x0d:
            eb = f6(self.mackey, self.remote_rand, self.local_rand, self.rab.to_bytes(16, byteorder='big'),
                    self.remote_IOCAPs[::-1], self.remote_addr, self.local_addr)
            if eb[::-1] != smp[SM_DHKey_Check].dhkey_check:
                raise Exception('Pairing failed: DHKey check mismatch')
            else:
                print(self.role, 'Pairing successful')
                self.paring_stage = 0
                self.isPaired = True
                return None

    async def response_generator(self, smp: SM_Hdr) -> SM_Hdr:
        if self.paring_stage == 1:
            rsp = self.paring_phase1(smp)
            if rsp is not None:
                yield rsp

        if self.paring_stage == 2:
            rsp = await self.paring_phase2(smp)
            if rsp is not None:
                yield rsp

        if self.paring_stage == 3:
            rsp = self.paring_phase3(smp)
            if rsp is not None:
                yield rsp

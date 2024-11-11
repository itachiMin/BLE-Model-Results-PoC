import copy
from scapy.packet import Raw
from typing import Generator
from scapy.layers.bluetooth import L2CAP_Hdr
from .packet import BTLE_WITH_CTE, BTLE_DATA_WITH_CTE


class Frag:
    """
    Fragment and ressemble L2CAP packets.
    """

    def __init__(self, MTU=27) -> None:
        self.MTU = MTU
        self.__frag_flag = False
        self.__fragments = []
        self.__fragments_count = 0
        self.__fragments_total = 0


    def ressemble(self, pkt: BTLE_WITH_CTE) -> BTLE_WITH_CTE or None:
        """
        Ressemble fragmented L2CAP packets.
        """
        isFragBeg = not self.__frag_flag \
            and BTLE_DATA_WITH_CTE in pkt and L2CAP_Hdr in pkt \
            and pkt[BTLE_DATA_WITH_CTE].LLID == 0b10 \
            and pkt[BTLE_DATA_WITH_CTE].len < pkt[L2CAP_Hdr].len

        if isFragBeg:
            self.__frag_flag = True
            self.__fragments.append(pkt)
            self.__fragments_total = pkt[L2CAP_Hdr].len
            self.__fragments_count = pkt[BTLE_DATA_WITH_CTE].len - 4

        if self.__frag_flag and BTLE_DATA_WITH_CTE in pkt and pkt[BTLE_DATA_WITH_CTE].LLID == 0x01:
            self.__fragments.append(pkt)
            self.__fragments_count += pkt[BTLE_DATA_WITH_CTE].len

        if self.__frag_flag:
            if self.__fragments_count == self.__fragments_total:
                # a complete packet, process it
                pkt = copy.copy(self.__fragments[0])
                total_len = pkt[BTLE_DATA_WITH_CTE].len
                total_raw = pkt[L2CAP_Hdr].original
                for frag in self.__fragments[1:]:
                    total_raw += frag[BTLE_DATA_WITH_CTE].payload.load
                    total_len += frag[BTLE_DATA_WITH_CTE].len
                pkt[BTLE_DATA_WITH_CTE].len = total_len
                pkt[BTLE_DATA_WITH_CTE].payload = L2CAP_Hdr(total_raw)

                self.__frag_flag = False
                self.__fragments = []
                self.__fragments_count = 0
                self.__fragments_total = 0

                return pkt
            else:
                # not a complete packet, return None
                return None
        else:
            return pkt

    def fragment(self, pkt: BTLE_WITH_CTE) -> Generator[BTLE_WITH_CTE, None, None]:
        """
        Fragment a packet.
        """
        raw_l2cap = pkt[BTLE_DATA_WITH_CTE].payload.build()
        l2cap_len = len(raw_l2cap)
        if l2cap_len <= self.MTU:
            yield pkt
            return

        for i in range(0, l2cap_len, self.MTU):
            frag = copy.deepcopy(pkt)
            if i == 0:
                frag[BTLE_DATA_WITH_CTE].len = self.MTU
                frag[BTLE_DATA_WITH_CTE].MD = 1
                frag[BTLE_DATA_WITH_CTE].LLID = 0b10
                frag[BTLE_DATA_WITH_CTE].payload = L2CAP_Hdr(raw_l2cap[i:i+self.MTU])
            elif i + self.MTU >= l2cap_len:
                frag[BTLE_DATA_WITH_CTE].len = l2cap_len - i
                frag[BTLE_DATA_WITH_CTE].MD = 0
                frag[BTLE_DATA_WITH_CTE].LLID = 0b01
                frag[BTLE_DATA_WITH_CTE].payload = Raw(raw_l2cap[i:])
            else:
                frag[BTLE_DATA_WITH_CTE].len = self.MTU
                frag[BTLE_DATA_WITH_CTE].MD = 1
                frag[BTLE_DATA_WITH_CTE].LLID = 0b01
                frag[BTLE_DATA_WITH_CTE].payload = Raw(raw_l2cap[i:i+self.MTU])
            yield frag


class Console(object):
    commands = {}

    def __init__(self, name='Lancet'):
        self.name = name

    def log(self, message):
        print(f"[{self.name}] {message}")

    def register_command(self, command, callback, help_message):
        # register command in console and bind callback
        self.commands[command] = (callback, help_message)

    def print_help(self):
        # print help message for all commands
        print("Available commands:")
        for command, (_, help_message) in self.commands.items():
            print(f"{command}: {help_message}")

    def execute_command(self, command, *args):
        # execute command with args
        if command in self.commands:
            callback, _ = self.commands[command]
            callback(*args)
        else:
            self.log("Unknown command. Type 'help' to see available commands.")

    def interactive(self):
        # start interactive console
        self.log("Welcome to the console! Type 'help' to see available commands.")

        while True:
            user_input = input(f"{self.name}> ")

            if user_input == "help":
                self.print_help()
            elif user_input == "exit":
                self.log("Exiting the console.")
                break
            else:
                command_parts = user_input.split()
                command = command_parts[0]
                args = command_parts[1:]
                self.execute_command(command, *args)

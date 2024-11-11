import os
import json
from argparse import ArgumentParser

IOCapabilitys = [
    "NoInputNoOutput", "DisplayOnly", "KeyboardOnly",
    "DisplayYesNo", "KeyboardDisplay"
]
OOBCaps = ["OOBSendRev", "OOBSend", "OOBRev", "NoOOB"]
AuthReqs = ["AuthReq", "NoAuthReq"]
KeySize = ["KeyHigh", "KeyLow"]


class BLE_SC_Feature(object):
    def __init__(self, io: str, oob: str, auth: str, keysize: str) -> None:
        self.io = io
        self.oob = oob
        self.auth = auth
        self.keysize = keysize

    def __str__(self) -> str:
        return f"[{self.io}_{self.oob}_{self.auth}_{self.keysize}]"
    
    def define(self, prefix:str):
        return f"-D{prefix}{self.io} -D{prefix}{self.oob} -D{prefix}{self.auth} -D{prefix}{self.keysize}"


def featrue_filter(i_feature: BLE_SC_Feature, r_feature: BLE_SC_Feature) -> bool:
    """
    Filter out the cases that do not satisfy the abilities of initiator and responder.

    Parameters:
    i_feature: initiator's feature.
    r_feature: responder's feature.

    Returns:
    True if the case satisfies the abilities of initiator and responder.
    """
    # if not(
    #     (i_feature.oob == "OOBSend" and r_feature.oob == "OOBRev") or 
    #     (i_feature.oob == "OOBRev" and r_feature.oob == "OOBSend") or 
    #     (i_feature.oob == "OOBSendRev" and r_feature.oob == "OOBSendRev") or
    #     (i_feature.oob == "NoOOB" and r_feature.oob == "NoOOB")
    # ):
    #     return False

    # Filter out OOB Capabilities
    # <"OOBSendRev","NoOOB"> equals to <"NoOOB","NoOOB">
    # <"OOBSend","NoOOB"> equals to <"NoOOB","NoOOB">
    # <"OOBRev","NoOOB"> equals to <"NoOOB","NoOOB">
    if "NoOOB" in [i_feature.oob, r_feature.oob] and i_feature.oob != r_feature.oob:
        return False

    # <"OOBSend","OOBSend"> equals to <"NoOOB","NoOOB">
    # <"OOBRev","OOBRev"> equals to <"NoOOB","NoOOB">
    if i_feature.oob == r_feature.oob and i_feature.oob != "NoOOB" and i_feature.oob != "OOBSendRev":
        return False

    # <"OOBSend","OOBSendRev"> equals to <"OOBSend","OOBRev">
    # <"OOBRev","OOBSendRev"> equals to <"OOBSend","OOBRev">
    if "OOBSendRev" in [i_feature.oob, r_feature.oob] and i_feature.oob != r_feature.oob:
        return False
    
    # Filter out the devices that do not have either OOB or IO capabilities but require authentication.
    if i_feature.io == "NoInputNoOutput" and i_feature.auth == "AuthReq" and i_feature.oob == "NoOOB":
        return False
    if r_feature.io == "NoInputNoOutput" and r_feature.auth == "AuthReq" and r_feature.oob == "NoOOB":
        return False
    
    # Filter out the OOB decives whose IO capabilities are not "KeyboardDisplay".
    if i_feature.oob != "NoOOB" and (i_feature.io != "KeyboardDisplay" or r_feature.io != "KeyboardDisplay"):
        return False
    
    # Filter out the OOB decives which do not require authentication.
    if i_feature.oob != "NoOOB" and "NoAuthReq" in [i_feature.auth, r_feature.auth]:
        return False

    return True


def generate_case(templete: str, i_feature: BLE_SC_Feature, r_feature: BLE_SC_Feature, outdir: str) -> str:
    """
    Generate a case of BLE-SC model.

    Parameters:
    templete: templete file of BLE-SC model.
    i_feature: initiator's feature.
    r_feature: responder's feature.

    Returns:
    The path of generated case.
    """
    assert os.path.exists(
        templete), f"Templete file {templete} does not exist."
    assert os.path.isdir(outdir), f"Output directory {outdir} does not exist."

    outfilename = f"BLE-SC_I{i_feature}_R{r_feature}.spthy"
    outpath = os.path.join(outdir, outfilename)

    defines = f'{i_feature.define("I")} {r_feature.define("R")}'
    os.system(f"m4 {defines} {templete} > {outpath}")

    return outpath


if __name__ == '__main__':
    parser = ArgumentParser(description='Script to generate BLE-SC models.')

    parser.add_argument('--io', type=str, default=",".join(IOCapabilitys),
                        help=f'IO Capability of BLE device, like \'DisplayOnly,DisplayYesNo\',  must be in {IOCapabilitys}.')
    parser.add_argument('--oob', type=str, default=",".join(OOBCaps),
                        help=f'OOB Capability of BLE device, like \'OOBSendRev,NoOOB\' , must be in {OOBCaps}.')
    parser.add_argument('--auth',  type=str, default=",".join(AuthReqs),
                        help=f'Authentication Requirement of BLE device, like \'AuthReq,NoAuthReq\' , must be in {AuthReqs}.')
    parser.add_argument('--keysize',  type=str, default=",".join(KeySize),
                        help=f'Key Size of BLE device, like \'KeyHigh,KeyLow\' , must be in {KeySize}.')
    
    parser.add_argument('--device-i', type=str, default="",
                        help=f'Capabilities of BLE initiator device, like \'DisplayYesNo,NoOOB,AuthReq,KeyHigh\'. \
                            \'--io\', \'--oob\', \'--auth\' and \'--keysize\' will be ignored if this set')
    parser.add_argument('--device-r', type=str, default="",
                        help=f'Capabilities of BLE responder device, like \'DisplayYesNo,NoOOB,AuthReq,KeyHigh\'. \
                            \'--io\', \'--oob\', \'--auth\' and \'--keysize\' will be ignored if this set')

    parser.add_argument('--templete', type=str, default="new.m4",
                        help='Templete file of BLE-SC model.')
    parser.add_argument('--outdir', type=str, default="cases",
                        help='Output directory of BLE-SC model.')
    parser.add_argument('--middle' , type=str, default="",
                        help='Middle Config file of BLE-SC model.')

    args = parser.parse_args()
    assert args.io and args.oob and args.auth and args.keysize
    def parse_list_arg(x): return [a.strip() for a in x.split(',')]
    def check_list_arg(x, y, prompt):
        assert x and all(elem in y for elem in x), prompt

    if args.device_i and args.device_r:
        def check_caps(caps):
            try:
                assert len(caps) == 4
                assert caps[0] in IOCapabilitys
                assert caps[1] in OOBCaps
                assert caps[2] in AuthReqs
                assert caps[3] in KeySize
            except:
                print(f"Invalid capabilities {caps}.")
                print("Capabilities must be [IOCapabilitys],[OOBCaps],[AuthReqs],[KeySize].")
                exit(-1)
        device_i_caps = parse_list_arg(args.device_i)
        device_r_caps = parse_list_arg(args.device_r)
        check_caps(device_i_caps)
        check_caps(device_r_caps)
        initiator_features = [BLE_SC_Feature(*device_i_caps)]
        responder_features = [BLE_SC_Feature(*device_r_caps)]

    elif args.device_i or args.device_r:
        print(f"'--device-i' and '--device-r' must be set both")
        exit(-1)

    else:
        io = parse_list_arg(args.io)
        check_list_arg(io, IOCapabilitys,f"IO Capabilitys must be in {IOCapabilitys}")
        oob = parse_list_arg(args.oob)
        check_list_arg(oob, OOBCaps, f"OOB Capabilitys must be in {OOBCaps}")
        auth = parse_list_arg(args.auth)
        check_list_arg(auth, AuthReqs,f"Authentication Requirement must be in {AuthReqs}")
        keysize = parse_list_arg(args.keysize)
        check_list_arg(keysize, KeySize, f"Key Size must be in {KeySize}")

        initiator_features = [BLE_SC_Feature(i, o, a, k)
                        for i in io for o in oob for a in auth for k in keysize]
        responder_features = [BLE_SC_Feature(i, o, a, k)
                            for i in io for o in oob for a in auth for k in keysize]

    templete = args.templete
    outdir = args.outdir
    middle = args.middle
    assert templete and outdir
    os.makedirs(outdir, exist_ok=True)
    outfiles = []

    print(f"Total: {len(initiator_features) * len(responder_features)} cases will be generated.")

    filtered_counter = 0
    generated_counter = 0
    for i_feature in initiator_features:
        for r_feature in responder_features:
            if featrue_filter(i_feature, r_feature):
                outpath = generate_case(templete, i_feature, r_feature, outdir)
                # print(f"Generate case {i_feature} {r_feature}.")
                outfiles.append(outpath)
                generated_counter += 1
            else:
                # print(f"Filter out case {i_feature} {r_feature}.")
                filtered_counter += 1
    print(f"Total: {filtered_counter + generated_counter}, Filtered: {filtered_counter}, Generated: {generated_counter}.")
    if middle:
        with open(middle, "w") as f:
            json.dump(outfiles, f, indent=4)

from Crypto.Hash import CMAC
from Crypto.Cipher import AES
from Crypto.PublicKey import ECC


def P256(u: int, V: ECC.EccPoint) -> bytes:
    """
    The function P256 is defined as follows. Given an integer u, 0 < u < r, and a
    point V on the curve E, the value P256(u,V) is computed as the x-coordinate of
    the uth multiple uV of the point V
    """
    point = V * u
    return point.x.to_bytes(32, byteorder="big")


def AES_CMAC(key: bytes, data: bytes) -> bytes:
    """
    AES-CMAC function
    """
    assert len(key) == 16
    cmac = CMAC.new(key, ciphermod=AES)
    cmac.update(data)
    return cmac.digest()


def f4(u: bytes, v: bytes, x: bytes, z: bytes) -> bytes:
    """
    F4 function
    """
    assert len(u) == 32
    assert len(v) == 32
    assert len(x) == 16
    assert len(z) == 1
    return AES_CMAC(x, u + v + z)


def f5(w: bytes, n1: bytes, n2: bytes, a1: bytes, a2: bytes) -> bytes:
    """
    F5 function
    """
    assert len(w) == 32
    assert len(n1) == 16
    assert len(n2) == 16
    assert len(a1) == 7
    assert len(a2) == 7
    Length = bytes([0x01, 0x00])
    keyID = bytes([0x62, 0x74, 0x6C, 0x65])

    salt = bytes.fromhex("6C888391AAF5A53860370BDB5A6083BE")
    t = AES_CMAC(salt, w)

    # AES-CMACT (Counter = 0 || keyID ||N1 || N2|| A1|| A2|| Length = 256)
    m = bytes([0x00]) + keyID + n1 + n2 + a1 + a2 + Length
    r1 = AES_CMAC(t, m)

    # AES-CMACT (Counter = 1 || keyID || N1 || N2|| A1|| A2 || Length = 256)
    m = bytes([0x01]) + keyID + n1 + n2 + a1 + a2 + Length
    r2 = AES_CMAC(t, m)

    return r1 + r2


def f6(
    W: bytes, N1: bytes, N2: bytes, R: bytes, IOcap: bytes, A1: bytes, A2: bytes
) -> bytes:
    """
    F6 function

    """
    assert len(W) == 16
    assert len(N1) == 16
    assert len(N2) == 16
    assert len(R) == 16
    assert len(IOcap) == 3
    assert len(A1) == 7
    assert len(A2) == 7

    m = N1 + N2 + R + IOcap + A1 + A2
    return AES_CMAC(W, m)


def g2(u: bytes, v: bytes, x: bytes, y: bytes) -> int:
    """
    G2 function
    """
    assert len(u) == 32
    assert len(v) == 32
    assert len(x) == 16
    assert len(y) == 16
    mac = AES_CMAC(x, u + v + y)
    mac_int = int.from_bytes(mac, byteorder="big")
    mac_mod = (mac_int & 0xFFFFFFFF) % 1000000
    return mac_mod


def h6(w: bytes, keyID: bytes) -> bytes:
    """
    H6 function
    """
    assert len(w) == 32
    assert len(keyID) == 4
    return AES_CMAC(w, keyID)


def h7(salt: bytes, w: bytes) -> bytes:
    """
    H7 function
    """
    assert len(salt) == 16
    assert len(w) == 16
    return AES_CMAC(salt, w)

# https://github.com/rfjakob/eme
# Converted with: https://codepal.ai/language-translator/go-to-python
#
# Used by:
#  https://github.com/rclone/rclone/blob/master/cmd/cryptdecode/cryptdecode.go
#    [cryptDecode()]
#  https://github.com/rclone/rclone/blob/master/backend/crypt/crypt.go
#  https://github.com/rclone/rclone/blob/master/backend/crypt/cipher.go
#    [decryptFilename(), decryptSegment()]

import logging
from enum import Enum

class DirectionConst(Enum):
    # Encrypt "inputData"
    DIRECTION_ENCRYPT = True
    # Decrypt "inputData"
    DIRECTION_DECRYPT = False


def multByTwo(out, in):
    if len(in) != 16:
        raise Exception("len must be 16")
    tmp = [0] * 16

    tmp[0] = 2 * in[0]
    if in[15] >= 128:
        tmp[0] = tmp[0] ^ 135
    for j in range(1, 16):
        tmp[j] = 2 * in[j]
        if in[j-1] >= 128:
            tmp[j] += 1
    out[:] = tmp[:]

def xorBlocks(out, in1, in2):
    if len(in1) != len(in2):
        log.Panicf("len(in1)=%d is not equal to len(in2)=%d", len(in1), len(in2))
    for i in range(len(in1)):
        out[i] = in1[i] ^ in2[i]

def aesTransform(dst, src, direction, bc):
    if direction == DirectionEncrypt:
        bc.Encrypt(dst, src)
        return
    elif direction == DirectionDecrypt:
        bc.Decrypt(dst, src)
        return

def tabulateL(bc, m):
    eZero = [0] * 16
    Li = [0] * 16
    bc.Encrypt(Li, eZero)

    LTable = [[0] * 16 for i in range(m)]
    pool = [0] * (m * 16)
    for i in range(m):
        multByTwo(Li, Li)
        LTable[i] = pool[i * 16 : (i + 1) * 16]
        LTable[i] = Li[:]
    return LTable

def Transform(bc, tweak, inputData, direction):
    T = tweak
    P = inputData

    if bc.BlockSize() != 16:
        log.Panicf("Using a block size other than 16 is not implemented")
    if len(T) != 16:
        log.Panicf("Tweak must be 16 bytes long, is %d", len(T))
    if len(P) % 16 != 0:
        log.Panicf("Data P must be a multiple of 16 long, is %d", len(P))
    m = len(P) // 16
    if m == 0 or m > 16 * 8:
        log.Panicf("EME operates on 1 to %d block-cipher blocks, you passed %d", 16 * 8, m)

    C = bytearray(len(P))

    LTable = tabulateL(bc, m)

    PPj = bytearray(16)
    for j in range(m):
        Pj = P[j * 16:(j + 1) * 16]
        # PPj = 2**(j-1)*L xor Pj
        xorBlocks(PPj, Pj, LTable[j])
        # PPPj = AESenc(K; PPj)
        aesTransform(C[j * 16:(j + 1) * 16], PPj, direction, bc)

    # MP =(xorSum PPPj) xor T
    MP = bytearray(16)
    xorBlocks(MP, C[0:16], T)
    for j in range(1, m):
        xorBlocks(MP, MP, C[j * 16:(j + 1) * 16])

    # MC = AESenc(K; MP)
    MC = bytearray(16)
    aesTransform(MC, MP, direction, bc)

    # M = MP xor MC
    M = bytearray(16)
    xorBlocks(M, MP, MC)
    CCCj = bytearray(16)
    for j in range(1, m):
        multByTwo(M, M)
        # CCCj = 2**(j-1)*M xor PPPj
        xorBlocks(CCCj, C[j * 16:(j + 1) * 16], M)
        C[j * 16:(j + 1) * 16] = CCCj

    # CCC1 = (xorSum CCCj) xor T xor MC
    CCC1 = bytearray(16)
    xorBlocks(CCC1, MC, T)
    for j in range(1, m):
        xorBlocks(CCC1, CCC1, C[j * 16:(j + 1) * 16])
    C[0:16] = CCC1

    for j in range(m):
        # CCj = AES-enc(K; CCCj)
        aesTransform(C[j * 16:(j + 1) * 16], C[j * 16:(j + 1) * 16], direction, bc)
        # Cj = 2**(j-1)*L xor CCj
        xorBlocks(C[j * 16:(j + 1) * 16], C[j * 16:(j + 1) * 16], LTable[j])

    return C

class EMECipher:
    def __init__(self, bc):
        self.bc = bc
        if self.bc.block_size != 16:
            raise ValueError("bc must have a block size of 16")

    def encrypt(self, tweak, input_data):
        return Transform(self.bc, tweak, input_data, DirectionEncrypt)

    def decrypt(self, tweak, input_data):
        return Transform(self.bc, tweak, input_data, DirectionDecrypt)

from .lowlevel import SuperMarioHeader, ConfigInfo

import struct

import os
from os import path

from . import dispatcher


PAD = b'kc' * 100

CONFIGINFO_TEMPLATE = """
ROMImageBaseOffset=                 # [28] Offset of Base of total ROM image
ROMImageSize=                       # [2C] Number of bytes in ROM image
ROMImageVersion=                    # [30] ROM Version number for entire ROM

                                    #  ROM component Info (offsets are from base of ConfigInfo page)
Mac68KROMOffset=                    # [34] Offset of base of Macintosh 68K ROM
Mac68KROMSize=                      # [38] Number of bytes in Macintosh 68K ROM

ExceptionTableOffset=               # [3C] Offset of base of PowerPC Exception Table Code
ExceptionTableSize=                 # [40] Number of bytes in PowerPC Exception Table Code

HWInitCodeOffset=                   # Offset of base of Hardware Init Code
HWInitCodeSize=                     # [48] Number of bytes in Hardware Init Code

KernelCodeOffset=                   # [4C] Offset of base of NanoKernel Code
KernelCodeSize=                     # [50] Number of bytes in NanoKernel Code

EmulatorCodeOffset=                 # [54] Offset of base of Emulator Code
EmulatorCodeSize=                   # [58] Number of bytes in Emulator Code

OpcodeTableOffset=                  # [5C] Offset of base of Opcode Table
OpcodeTableSize=                    # [60] Number of bytes in Opcode Table

                                    #  Offsets within the Emulator Data Page.
BootstrapVersion=                   # [64] Bootstrap loader version info
############## VALUES SPECIFIC TO THIS 68K EMULATOR VERSION ##############
BootVersionOffset=                  # [74] offset within EmulatorData of BootstrapVersion
ECBOffset=                          # [78] offset within EmulatorData of ECB
IplValueOffset=                     # [7C] offset within EmulatorData of IplValue

                                    #  Offsets within the Emulator Code.
EmulatorEntryOffset=                # [80] offset within Emulator Code of entry point
KernelTrapTableOffset=              # [84] offset within Emulator Code of KernelTrapTable

                                    #  Interrupt Passing Masks.
TestIntMaskInit=                    # [88] initial value for test interrupt mask
ClearIntMaskInit=                   # [8C] initial value for clear interrupt mask
PostIntMaskInit=                    # [90] initial value for post interrupt mask
##################### END OF EMULATOR-SPECIFIC VALUES ####################
LA_InterruptCtl=                    # [94] logical address of Interrupt Control I/O page
InterruptHandlerKind=               # [98] kind of handler to use

LA_InfoRecord=                      # [9C] logical address of InfoRecord page
LA_KernelData=                      # [A0] logical address of KernelData page
LA_EmulatorData=                    # [A4] logical address of EmulatorData page
LA_DispatchTable=                   # [A8] logical address of Dispatch Table
LA_EmulatorCode=                    # [AC] logical address of Emulator Code

                                    #  Address Space Mapping.
PageAttributeInit=                  # [B4] default WIMG/PP settings for PTE creation

                                    #  Only needed for Smurf
SharedMemoryAddr=                   # [35C] physical address of Mac/Smurf shared message mem

PA_RelocatedLowMemInit=             # [360] physical address of RelocatedLowMem

OpenFWBundleOffset=                 # [364] Offset of base of OpenFirmware PEF Bundle
OpenFWBundleSize=                   # [368] Number of bytes in OpenFirmware PEF Bundle

LA_OpenFirmware=                    # [36C] logical address of Open Firmware
PA_OpenFirmware=                    # [370] physical address of Open Firmware
LA_HardwarePriv=                    # [374] logical address of HardwarePriv callback
""".strip()


def extract_and_zero(binary, start, stop):
    ret = binary[start:stop]
    binary[start:stop] = bytes(stop - start)
    return ret


def find_configinfo(binary):
    # Find a ConfigIngo struct by checking every possible
    # place for a valid checksum. Ugly but quick.

    byte_lanes = [sum(binary[i::8]) for i in range(8)]

    for i in range(0, len(binary), 0x100):
        zeroed_byte_lanes = list(byte_lanes)
        for j in range(i, i+40):
            zeroed_byte_lanes[j % 8] -= binary[j]

        sum32 = [lane % (1<<32) for lane in zeroed_byte_lanes]

        sum64 = sum(lane << (k * 8) for (k, lane) in enumerate(reversed(zeroed_byte_lanes)))
        sum64 %= 1 << 64

        allsums = b''.join(x.to_bytes(4, byteorder='big') for x in sum32)
        allsums += sum64.to_bytes(8, byteorder='big')

        if binary[i:i+len(allsums)] == allsums:
            break
    else:
        return

    # Which structs share the BootstrapVersion signature?
    for j in range(0, len(binary), 0x100):
        if binary[i+0x64:i+0x74] == binary[j+0x64:j+0x74]:
            yield j


def dump_configinfo(binary, offset, push_line):
    s = ConfigInfo.unpack_from(binary, offset)

    # First section (no [header]):
    # Raw key=value lines not resembling the struct in PCCInfoRecordsPriv.h
    for line in CONFIGINFO_TEMPLATE.split('\n'):
        if '=' in line:
            key, _, remainder = line.partition('=')
            raw_value = getattr(s, key)
            if key == 'InterruptHandlerKind':
                value = '0x%02X' % raw_value
            elif key == 'BootstrapVersion':
                value = repr(raw_value)[1:]
            elif key.endswith('Offset') and key.startswith(('Mac68KROM', 'ExceptionTable', 'HWInitCode', 'KernelCode', 'EmulatorCode', 'OpcodeTable', 'OpenFWBundle')):
                if getattr(s, key.replace('Offset', 'Size')) == 0:
                    value = '0x00000000'
                else:
                    value = 'BASE0x%+X' % (raw_value - s.ROMImageBaseOffset)
            else:
                value = '0x%08X' % raw_value

            value = value.replace('0x-', '-0x').replace('0x+', '+0x')

            nuline = key + '=' + value
            while remainder.startswith(' ') and len(nuline) + len(remainder) > len(line):
                remainder = remainder[1:]
            nuline += remainder
            line = nuline

        push_line(line)

    push_line('')

    # Now dump the more structured parts of the ConfigInfo
    mapnames = ['sup', 'usr', 'cpu', 'ovl']

    segmaps = [[],[],[],[]]
    for i, blob in enumerate((s.SegMap32SupInit, s.SegMap32UsrInit, s.SegMap32CPUInit, s.SegMap32OvlInit)):
        for j in range(0, len(blob), 8):
            tpl = struct.unpack_from('>LL', blob, j)
            segmaps[i].append(tpl)

    def print_seg_ptrs_for_offset(segmap_offset):
        for header, list16 in zip(mapnames, segmaps):
            for seg_i, (seg_offset, seg_reg) in enumerate(list16):
                if seg_offset == segmap_offset:
                    push_line('segment_ptr_here=0x%X map=%s segment_register=0x%08X' % (seg_i, header, seg_reg))

    batmaps = [[],[],[],[]]
    for i, blob in enumerate((s.BatMap32SupInit, s.BatMap32UsrInit, s.BatMap32CPUInit, s.BatMap32OvlInit)):
        for j in reversed(range(0, 32, 4)):
            batmaps[i].append(((blob >> j) & 0xF) * 8)

    last_used_batmap = max(y for x in batmaps for y in x)

    def print_bat_ptrs_for_offset(batmap_offset):
        for header, list8 in zip(mapnames, batmaps):
            for bat_offset, bat_name in zip(list8, ['ibat0', 'ibat1', 'ibat2', 'ibat3', 'dbat0', 'dbat1', 'dbat2', 'dbat3']):
                if bat_offset == batmap_offset:
                    push_line('bat_ptr_here=%s map=%s' % (bat_name, header))

    lowmem = []
    lmoffset = s.MacLowMemInitOffset
    while any(binary[offset+lmoffset:][:4]):
        key, val = struct.unpack_from('>LL', binary, offset+lmoffset)
        lowmem.append((key, val))
        lmoffset += 8

    push_line('[LowMemory]')
    for key, val in lowmem:
        push_line('address=0x%08X value=0x%08X' % (key, val))
    push_line('')

    push_line('[PageMappingInfo]')
    if s.PageMapInitSize or any(s.SegMap32SupInit + s.SegMap32UsrInit + s.SegMap32CPUInit + s.SegMap32OvlInit):
        push_line('# Constants: PMDT_InvalidAddress = 0xA00, PMDT_Available = 0xA01')

        pagemapinit = binary[offset:][s.PageMapInitOffset:][:s.PageMapInitSize]

        for i in range(0, len(pagemapinit), 8):
            print_seg_ptrs_for_offset(i)

            pgidx, pgcnt, word2 = struct.unpack_from('>HHL', pagemapinit, i)
            attr = word2 & 0xFFF

            if attr == 0xA00:
                attr_s = 'PMDT_InvalidAddress'
            elif attr == 0xA01:
                attr_s = 'PMDT_Available'
            else:
                attr_s = '0x%03X' % attr

            paddr = word2 >> 12
            if 'Rel' in attr_s:
                paddr_s = 'BASE+0x%05X' % ((paddr + offset) & 0xFFFFF)
            else:
                paddr_s = '0x%05X' % paddr

            if i == s.PageMapIRPOffset: push_line('special_pmdt=irp')
            if i == s.PageMapKDPOffset: push_line('special_pmdt=kdp')
            if i == s.PageMapEDPOffset: push_line('special_pmdt=edp')

            push_line('pmdt_page_offset=0x%04X pages_minus_1=0x%04X phys_page=%s attr=%s' % (pgidx, pgcnt, paddr_s, attr_s))

    push_line('')

    push_line('[BatMappingInfo]')
    if any(s.BATRangeInit) or s.BatMap32SupInit or s.BatMap32UsrInit or s.BatMap32CPUInit or s.BatMap32OvlInit:
        for i in range(0, len(s.BATRangeInit), 8):
            if i > last_used_batmap * 8: break

            print_bat_ptrs_for_offset(i)

            u, l = struct.unpack_from('>LL', s.BATRangeInit, i)

            is_relative = l & 0x200
            if is_relative:
                l = (offset + l) & 0xFFFFFFFF - is_relative

            bepi = u >> 17
            bl = (u >> 2) & 0x7FF
            vs = (u >> 1) & 1
            vp = u & 1

            brpn = l >> 17
            wimg = [(l > 6) & 1, (l > 5) & 1, (l > 4) & 1, (l > 3) & 1]
            pp = [(l > 1) & 1, l & 1]

            bl_s = '0b' + bin(bl)[2:].zfill(11)

            if is_relative:
                brpn_s = 'BASE+0x%06X' % (brpn << 17)
            else:
                brpn_s = '0x%08X' % (brpn << 17)

            push_line('bepi=0x%08X bl=%s vs=%s vp=%d brpn=%s wimg=0b%d%d%d%d pp=0b%d%d' % (bepi << 17, bl_s, vs, vp, brpn_s, *wimg, *pp))

    push_line('')



def is_powerpc(binary):
    return (len(binary) == 0x400000) and (PAD in binary[:0x300000])


def get_nk_version(nk):
    if nk.startswith(b'\x48\x00\x00\x0C'):
        # v2 NK has structured header
        return 'v%02X.%02X' % (nk[4], nk[5])

    for i in range(0, len(nk) - 8, 4):
        if nk[i:i+2] == b'\x39\x80': # li r12, ???
            if nk[i+4:i+8] == b'\xB1\x81\x0F\xE4': # sth r12, 0xFE4(r1)
                return 'v%02X.%02X' % (nk[i+2], nk[i+3]) # return the ???


def extract_plausible_thing(binary, start):
    stop = binary.find(bytes(1024), start) # check, because kernel is often absent or wrong size
    if stop > start:
        while stop % 4 != 0: stop += 1
        return extract_and_zero(binary, start, stop)


def dump(binary, dest_dir):
    if not is_powerpc(binary): raise dispatcher.WrongFormat

    os.makedirs(dest_dir, exist_ok=True)

    cioffsets = list(find_configinfo(binary))

    # We will zero out parts as we go along extracting them
    binary = bytearray(binary)

    for i, cioffset in enumerate(cioffsets, 1):
        filename = 'Configfile'
        if len(cioffsets) > 1: filename += '-' + str(i)

        with open(path.join(dest_dir, filename), 'w') as f:
            push_line = lambda x: print(x, file=f)
            dump_configinfo(binary, cioffset, push_line)

    best_cioffset = cioffsets[0]
    best_ci = ConfigInfo.unpack_from(binary, best_cioffset)

    for cioffset in cioffsets:
        extract_and_zero(binary, cioffset, cioffset + 0x1000)

    supermario = extract_and_zero(binary,
        best_cioffset + best_ci.Mac68KROMOffset,
        best_cioffset + best_ci.Mac68KROMOffset + best_ci.Mac68KROMSize)
    dispatcher.dump(supermario, path.join(dest_dir, 'Mac68KROM'))

    xtbl = extract_and_zero(binary,
        best_cioffset + best_ci.ExceptionTableOffset,
        best_cioffset + best_ci.ExceptionTableOffset + best_ci.ExceptionTableSize)
    if any(xtbl):
        # xtbl_len = len(xtbl)
        # while not any(xtbl[xtbl_len-4:xtbl_len]): xtbl_len -= 4
        # xtbl = xtbl[xtbl_len:]
        with open(path.join(dest_dir, 'ExceptionTable'), 'wb') as f:
            f.write(xtbl)

    nk = extract_plausible_thing(binary, min(0x310000, best_cioffset + best_ci.KernelCodeOffset))
    if nk:
        name = 'NanoKernel'
        vers = get_nk_version(nk)
        if vers: name += '-' + vers

        with open(path.join(dest_dir, name), 'wb') as f:
            f.write(nk)

    hwinit = extract_plausible_thing(binary, best_cioffset + best_ci.HWInitCodeOffset)
    if hwinit:
        with open(path.join(dest_dir, 'HWInit'), 'wb') as f:
            f.write(hwinit)

    openfw = extract_plausible_thing(binary, best_cioffset + best_ci.OpenFWBundleOffset)
    if openfw:
        with open(path.join(dest_dir, 'OpenFW'), 'wb') as f:
            f.write(openfw)

    with open(path.join(dest_dir, 'EverythingElse'), 'wb') as f:
        f.write(binary)
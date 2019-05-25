from .stringstruct import StringStruct
from .namedtuplestruct import NamedTupleStruct

class MyParcelStruct(NamedTupleStruct, StringStruct):
    pass

MAGIC = b'prcl\x01\x00\x00\x00'

def pad(offset, align):
    x = offset + align - 1
    x -= x % align
    return x

PrclNodeStruct = MyParcelStruct('>I 4s I I I I 32s 32s', name='PrclNodeStruct',
    fields=['link', 'ostype', 'hdr_size', 'flags', 'n_children', 'child_size', 'a', 'b'])

PrclChildStruct = MyParcelStruct('>4s I 4s I I I I 32s', name='PrclChildStruct',
    fields=['ostype', 'flags', 'compress', 'unpackedlen', 'cksum', 'packedlen', 'ptr', 'name'])

SuperMarioHeader = NamedTupleStruct('>I I B B I I H B B L L L L L L B B 4L L L L L', name='SuperMarioHeader',
    fields=['CheckSum', 'ResetPC', 'MachineNumber', 'ROMVersion',
    'ReStartJMP', 'BadDiskJMP', 'ROMRelease', 'PatchFlags', 'unused1',
    'ForeignOSTbl', 'RomRsrc', 'EjectJMP', 'DispTableOff',
    'CriticalJMP', 'ResetEntryJMP', 'RomLoc', 'unused2', 'CheckSum0',
    'CheckSum1', 'CheckSum2', 'CheckSum3', 'RomSize', 'EraseIconOff',
    'InitSys7ToolboxOff', 'SubVers'])

SuperMarioForeignOS = NamedTupleStruct('>7I', name='SuperMarioForeignOS',
    fields=['InitDispatcher', 'EMT1010', 'BadTrap', 'StartSDeclMgr',
    'InitMemVect', 'SwitchMMU', 'InitRomVectors'])

COMBO_FIELDS = {
    0x40 << 56: 'AppleTalk1',
    0x20 << 56: 'AppleTalk2',
    0x30 << 56: 'AppleTalk2_NetBoot_FPU',
    0x08 << 56: 'AppleTalk2_NetBoot_NoFPU',
    0x10 << 56: 'NetBoot',
    0x78 << 56: 'AllCombos',
}

ResHeader = NamedTupleStruct('>L B B H H 6x', name='ResHeader',
    fields=['offsetToFirst', 'maxValidIndex', 'comboFieldSize',
    'comboVersion', 'headerSize'])

ResEntry = NamedTupleStruct('>Q L L 4s h B 256p', name='ResEntry',
    fields=['combo', 'offsetToNext', 'offsetToData', 'rsrcType',
    'rsrcID', 'rsrcAttr', 'rsrcName'])

def ResEntry_padded_len(entry_tuple):
    return pad(ResEntry.size - 256 + len(entry_tuple.rsrcName), 16)

FakeMMHeader = NamedTupleStruct('>4s L L L', name='FakeMMHeader', 
    fields=['MagicKurt', 'MagicC0A00000', 'dataSizePlus12', 'bogusOff'])

ConfigInfo = NamedTupleStruct('>40x lLL lL lL lL lL lL lL 16sLLL LL LLLLbxxx LLLLL L LLLLLL 128s128s128s128s 128s LLLL L L lL LLL', name='ConfigInfo',
    fields=['ROMImageBaseOffset', 'ROMImageSize', 'ROMImageVersion',
    'Mac68KROMOffset', 'Mac68KROMSize', 'ExceptionTableOffset',
    'ExceptionTableSize', 'HWInitCodeOffset', 'HWInitCodeSize',
    'KernelCodeOffset', 'KernelCodeSize', 'EmulatorCodeOffset',
    'EmulatorCodeSize', 'OpcodeTableOffset', 'OpcodeTableSize',
    'BootstrapVersion', 'BootVersionOffset', 'ECBOffset',
    'IplValueOffset', 'EmulatorEntryOffset', 'KernelTrapTableOffset',
    'TestIntMaskInit', 'ClearIntMaskInit', 'PostIntMaskInit',
    'LA_InterruptCtl', 'InterruptHandlerKind', 'LA_InfoRecord',
    'LA_KernelData', 'LA_EmulatorData', 'LA_DispatchTable',
    'LA_EmulatorCode', 'MacLowMemInitOffset', 'PageAttributeInit',
    'PageMapInitSize', 'PageMapInitOffset', 'PageMapIRPOffset',
    'PageMapKDPOffset', 'PageMapEDPOffset', 'SegMap32SupInit', 'SegMap32UsrInit', 'SegMap32CPUInit', 'SegMap32OvlInit', 'BATRangeInit',
    'BatMap32SupInit', 'BatMap32UsrInit', 'BatMap32CPUInit',
    'BatMap32OvlInit', 'SharedMemoryAddr', 'PA_RelocatedLowMemInit',
    'OpenFWBundleOffset', 'OpenFWBundleSize', 'LA_OpenFirmware',
    'PA_OpenFirmware', 'LA_HardwarePriv'])

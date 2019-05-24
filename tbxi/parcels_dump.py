from collections import defaultdict, Counter
import os
from os import path
from shlex import quote
import struct

from . import dispatcher

from .slow_lzss import decompress
from .lowlevel import PrclNodeStruct, PrclChildStruct

def walk_tree(binary):
    """Get low level representation of tree

    e.g. [(prclnodetuple, [prclchildtuple, ...]), ...]
    """

    prclnode = None

    parents = []
    for i in iter(lambda: prclnode.link if prclnode else struct.unpack_from('>12xI', binary)[0], 0):
        prclnode = PrclNodeStruct.unpack_from(binary, offset=i)
        
        children = []
        for j in range(i + PrclNodeStruct.size, i + prclnode.hdr_size, prclnode.child_size):
            prclchild = PrclChildStruct.unpack_from(binary, offset=j)

            children.append(prclchild)

        parents.append((prclnode, children))

    return parents


def unique_binary_tpl(prclchild):
    return (prclchild.ptr, prclchild.packedlen, prclchild.compress)


def suggest_names_to_dump(parent, child, code_name):
    # We yield heaps of suggested filenames, and the shortest non-empty unique one gets chosen

    if parent.ostype == child.ostype == 'rom ':
        yield 'MacROM'
        return

    if 'AAPL,MacOS,PowerPC' in child.name and code_name == 'PowerMgrPlugin':
        if parent.a == 'cuda' and parent.b == 'via-cuda':
            yield 'PowerMgrPlugin.CUDA'
        elif parent.a == 'pmu' and parent.b == 'power-mgt':
            yield 'PowerMgrPlugin.PMU'
        elif parent.a == 'via-pmu-99' and parent.b == 'power-mgt':
            yield 'PowerMgrPlugin.PMU99'
        elif parent.a == 'via-pmu-2000' and parent.b == 'power-mgt':
            yield 'PowerMgrPlugin.PMU2000'
        elif parent.a == 'bal' and parent.b == 'power-mgt':
            yield 'PowerMgrPlugin.BlueBox'

    if ',' not in child.name: # All property names except driver,AAPL,MacOS,pef et al
        yield child.name

    if child.flags & 0x80: # special-node stuff
        yield child.name
        yield squish_name(child.name, parent.a, parent.b)

    if 'AAPL,MacOS,PowerPC' in child.name:
        if code_name:
            yield squish_name(code_name, parent.a, parent.b)
        else:
            yield squish_name(parent.a, parent.b)


def squish_name(*parts):
    squeeze = lambda x: x.lower().replace('-', '').replace('_', '')

    parts = list(parts)
    keepmask = [True] * len(parts)

    for i in range(len(parts)):
        for j in range(len(parts)):
            if i == j: continue
            if squeeze(parts[j]) == squeeze(parts[i]):
                if j > i: keepmask[j] = False
            elif squeeze(parts[j]) in squeeze(parts[i]):
                keepmask[j] = False

    truelist = []
    for i in range(len(parts)):
        if keepmask[i]: truelist.append(parts[i])

    return '.'.join(truelist)


def settle_name_votes(vote_dict):
    # Forbid duplicate names
    duplicate_names = set([''])
    for ka, va in vote_dict.items():
        for kb, vb in vote_dict.items():
            if ka is kb: continue

            for x in va:
                if x in vb:
                    duplicate_names.add(x)

    # Pick the shortest non-duplicate name
    decision = {}
    for k, v in vote_dict.items():
        allowed_names = [x for x in v if x not in duplicate_names]
        if allowed_names:
            decision[k] = min(allowed_names, key=len)

    return decision


def is_parcels(binary):
    return binary.startswith(b'prcl')


def dump(binary, dest_dir):
    if not binary.startswith(b'prcl'): raise dispatcher.WrongFormat

    os.makedirs(dest_dir, exist_ok=True)

    basic_structure = walk_tree(binary)

    # Decompress everything
    unpacked_dict = {}
    binary_counts = Counter()
    for prclnode, children in basic_structure:
        for prclchild in children:
            binary_counts[unique_binary_tpl(prclchild)] += 1

            data = binary[prclchild.ptr:prclchild.ptr+prclchild.packedlen]
            if prclchild.compress == 'lzss': data = decompress(data)

            unpacked_dict[unique_binary_tpl(prclchild)] = data

    # Suggest possible filenames for each blob
    name_vote_dict = defaultdict(list)
    for prclnode, children in basic_structure:
        # is there a prop that gives contextual name information?
        for check_child in children:
            if check_child.name == 'code,AAPL,MacOS,name':
                code_name = unpacked_dict[unique_binary_tpl(check_child)].rstrip(b'\0').decode('ascii')
                break
        else:
            code_name = None

        # now use that name to suggest names for all the children
        for prclchild in children:
            if prclchild.ostype in ('cstr', 'csta'): continue
            votes = suggest_names_to_dump(prclnode, prclchild, code_name)
            if unpacked_dict[unique_binary_tpl(prclchild)].startswith(b'Joy!'):
                votes = [v + '.pef' for v in votes]
            name_vote_dict[unique_binary_tpl(prclchild)].extend(votes)

    # Decide on filenames
    decision = settle_name_votes(name_vote_dict)

    # Dump blobs to disk
    for tpl, filename in decision.items():
        keep_this = True

        data = unpacked_dict[tpl]
        dispatcher.dump(data, path.join(dest_dir, filename))


    # Get printing!!!
    with open(path.join(dest_dir, 'Parcelfile'), 'w') as f:
        for prclnode, children in basic_structure:
            line = quote(prclnode.ostype)
            line += ' flags=0x%05x' % prclnode.flags
            if prclnode.a: line += ' a=%s' % quote(prclnode.a)
            if prclnode.b: line += ' b=%s' % quote(prclnode.b)

            print(line, file=f)

            for prclchild in children:
                line = '\t%s' % quote(prclchild.ostype)
                line += ' flags=0x%05x' % prclchild.flags
                if prclchild.name: line += ' name=%s' % quote(prclchild.name)

                if prclchild.ostype not in ('cstr', 'csta'):
                    filename = decision[unique_binary_tpl(prclchild)]
                    if prclchild.compress == 'lzss': filename += '.lzss'
                    line += ' src=%s' % filename

                if binary_counts[unique_binary_tpl(prclchild)] > 1:
                    line += ' deduplicate=1'

                print(line, file=f)

                if prclchild.ostype in ('cstr', 'csta'):
                    strangs = unpacked_dict[unique_binary_tpl(prclchild)].split(b'\0')[:-1]
                    for s in strangs:
                        line = '\t\t%s' % quote(s.decode('ascii'))

                        print(line, file=f)

            print(file=f)

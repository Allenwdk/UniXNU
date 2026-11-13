"""Route Foundation through an adapter that re-exports it, without moving code.

Only the Foundation dependency's name is changed. Chained fixups, authenticated
pointers, instructions, sections and the original code signature stay in place;
the caller must re-sign the resulting copy.
"""
import hashlib
import struct


def require_reexport(data, name):
    """Check the produced library's forwarding contract before it is signed."""
    if len(data) < 32:
        raise ValueError('truncated adapter Mach-O header')
    magic, cpu, subtype, kind, count, size, flags, _ = struct.unpack_from('<8I', data)
    if (magic, cpu, subtype & 0xffffff, kind) != (0xfeedfacf, 0x100000c, 2, 6):
        raise ValueError('expected an arm64e MH_DYLIB adapter')
    if flags & 0x100000:  # MH_NO_REEXPORTED_DYLIBS
        raise ValueError('adapter declares no re-exported libraries')
    at, end, found = 32, 32 + size, []
    if end > len(data):
        raise ValueError('truncated adapter load commands')
    for _ in range(count):
        if at + 8 > end:
            raise ValueError('truncated adapter load command')
        command, length = struct.unpack_from('<II', data, at)
        if length < 8 or length % 8 or at + length > end:
            raise ValueError('invalid adapter load command')
        if command in (0xc, 0x80000018, 0x8000001f, 0x80000023):
            if length < 24:
                raise ValueError('truncated adapter dependency')
            offset = struct.unpack_from('<I', data, at + 8)[0]
            if not 24 <= offset < length or b'\0' not in data[at + offset:at + length]:
                raise ValueError('invalid adapter dependency name')
            if data[at + offset:at + length].split(b'\0', 1)[0] == name.encode():
                found.append(command)
        at += length
    if at != end or found != [0x8000001f]:
        raise ValueError('adapter must actually LC_REEXPORT_DYLIB ' + name)


def add_dylib(data, name, expected_sha256):
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('OS executable does not match the 24A446 source pin')
    if len(data) < 32:
        raise ValueError('truncated Mach-O header')
    magic, cpu, subtype, kind, count, size = struct.unpack_from('<6I', data)
    if (magic, cpu, subtype, kind) != (0xfeedfacf, 0x100000c, 0x80000002, 2):
        raise ValueError('expected an arm64e MH_EXECUTE image')
    end = 32 + size
    if end > len(data):
        raise ValueError('truncated load commands')
    at, replacements = 32, []
    foundation = b'/System/Library/Frameworks/Foundation.framework/Foundation'
    for _ in range(count):
        if at + 8 > end:
            raise ValueError('truncated load command')
        command, length = struct.unpack_from('<II', data, at)
        if length < 8 or length % 8 or at + length > end:
            raise ValueError('invalid load command size')
        if command in (0xc, 0x80000018, 0x8000001f, 0x80000023):
            if length < 24:
                raise ValueError('truncated dependency')
            offset = struct.unpack_from('<I', data, at + 8)[0]
            if not 24 <= offset < length:
                raise ValueError('invalid dependency name offset')
            if data[at + offset:at + length].split(b'\0', 1)[0] == name.encode():
                raise ValueError('dependency already present')
            if data[at + offset:at + length].split(b'\0', 1)[0] == foundation:
                if command != 0xc:
                    raise ValueError('Foundation is not a required dependency')
                replacements.append((at + offset, length - offset))
        at += length
    if at != end:
        raise ValueError('load command count differs from size')
    raw = name.encode() + b'\0'
    if len(replacements) != 1:
        raise ValueError('expected exactly one Foundation dependency')
    start, length = replacements[0]
    if len(raw) > length:
        raise ValueError('adapter path does not fit the dependency command')
    result = bytearray(data)
    result[start:start + length] = raw.ljust(length, b'\0')
    return bytes(result)


def append_dylib(data, name, expected_sha256):
    """Add an owner dependency in verified empty header padding.

    Preserve every original dependency and ordinal, so executable imports never
    depend on an adapter's re-export contract. Never relocate sections or fixups.
    The caller must re-sign and retain the original identifier/entitlements.
    """
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('OS executable does not match the 24A446 source pin')
    if len(data) < 32:
        raise ValueError('truncated Mach-O header')
    magic, cpu, subtype, kind, count, size = struct.unpack_from('<6I', data)
    if (magic, cpu, subtype, kind) != (0xfeedfacf, 0x100000c, 0x80000002, 2):
        raise ValueError('expected an arm64e MH_EXECUTE image')
    if not name.startswith('/') or '\0' in name:
        raise ValueError('dependency must be an absolute path without NUL')
    end, at, first_section = 32 + size, 32, len(data)
    if end > len(data):
        raise ValueError('truncated load commands')
    for _ in range(count):
        if at + 8 > end:
            raise ValueError('truncated load command')
        command, length = struct.unpack_from('<II', data, at)
        if length < 8 or length % 8 or at + length > end:
            raise ValueError('invalid load command size')
        if command in (0xc, 0x80000018, 0x8000001f, 0x80000023):
            if length < 24:
                raise ValueError('truncated dependency')
            offset = struct.unpack_from('<I', data, at + 8)[0]
            if not 24 <= offset < length:
                raise ValueError('invalid dependency name offset')
            if data[at + offset:at + length].split(b'\0', 1)[0] == name.encode():
                raise ValueError('dependency already present')
        if command == 0x19:
            if length < 72:
                raise ValueError('truncated segment')
            sections = struct.unpack_from('<I', data, at + 64)[0]
            if 72 + 80 * sections > length:
                raise ValueError('truncated section table')
            for index in range(sections):
                section = at + 72 + 80 * index
                section_size, fileoff = struct.unpack_from('<QI', data, section + 40)
                if fileoff and section_size:
                    if fileoff < end or fileoff + section_size > len(data):
                        raise ValueError('invalid section extent')
                    first_section = min(first_section, fileoff)
        at += length
    if at != end or first_section == len(data):
        raise ValueError('invalid command count or absent file sections')
    raw = name.encode() + b'\0'
    length = (24 + len(raw) + 7) & ~7
    if end + length > first_section or any(data[end:end + length]):
        raise ValueError('no verified empty header padding for dependency')
    command = struct.pack('<6I', 0xc, length, 24, 0, 0x10000, 0x10000)
    command += raw.ljust(length - 24, b'\0')
    result = bytearray(data)
    result[end:end + length] = command
    struct.pack_into('<II', result, 16, count + 1, size + length)
    return bytes(result)

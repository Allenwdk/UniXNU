"""Bounded ADT defaults for the explicitly migrated UniXNU driver arguments.

The matching kernel allowlist is in uke-adt-driver-args.patch. The device
regression test compares both lists; original XNU keys are never accepted here.
"""
import re

from .util import Error

DRIVER_KEYS = (
    'sheng-touch', 'sheng-touch-hid', 'sheng-buttons', 'sheng-backlight',
    'sheng-touch-split', 'sheng-touch-poll', 'offline-legacy-register',
    'offline-legacy-gop', 'offline-legacy-unit-scale', 'offline-legacy-pm',
    'offline-legacy-validate', 'offline-legacy-transfer', 'offline-legacy-cpu-present',
    'offline-legacy-phase', 'offline-legacy-noconsole', 'sheng-dpu-scanout',
    'sheng-vsync', 'sheng-vsync-fixed',
)
DRIVER_ALIASES = {key.removeprefix('sheng-'): key for key in DRIVER_KEYS}
PROPERTY = 'unixnu-driver-args'
MAX_BYTES = 4096
READER_ABI = b'unixnu-driver-args-v1\0'


def validate(value):
    if not isinstance(value, str) or not value.isascii() or '\0' in value:
        raise Error('ADT driver arguments must be an ASCII string without NUL')
    if len(value.encode()) + 1 > MAX_BYTES:
        raise Error('ADT driver arguments exceed the independent 4096-byte limit')
    if any(c.isspace() and c not in ' \t' for c in value):
        raise Error('ADT driver arguments allow only space or tab separators')
    seen = set()
    for token in value.split():
        name, separator, number = token.partition('=')
        normalized = DRIVER_ALIASES.get(name.removeprefix('sheng-'))
        if normalized is None or not separator:
            raise Error(f'unsupported ADT driver argument: {token}')
        if normalized in seen:
            raise Error(f'duplicate ADT driver argument: {name}')
        if not re.fullmatch(r'(?:0|[1-9][0-9]*|0x[0-9a-fA-F]+)', number):
            raise Error(f'ADT driver argument requires canonical decimal or hexadecimal u32: {token}')
        if int(number, 16 if number.startswith('0x') else 10) > 0xffffffff:
            raise Error(f'ADT driver argument exceeds u32: {token}')
        seen.add(normalized)
    return value


def from_config(config):
    chosen = config.get('adt', {}).get('chosen', {})
    for kind, values in chosen.items():
        if kind != 'string' and isinstance(values, dict) and PROPERTY in values:
            raise Error('unixnu-driver-args must be one ADT string property')
    return validate(chosen.get('string', {}).get(PROPERTY, ''))


def require_kernel_reader(kernel_data, adt_args):
    if validate(adt_args) and READER_ABI not in kernel_data:
        raise Error('ADT driver arguments require a kernel with unixnu-driver-args-v1 support')


def report(command_line, adt_args):
    """Record configured values and provenance, preserving CLI last-match wins."""
    values = {}
    for source, text in [('adt', validate(adt_args)), ('command_line', command_line)]:
        for token in text.split():
            name, separator, value = token.partition('=')
            normalized = DRIVER_ALIASES.get(name.removeprefix('sheng-'))
            if normalized is not None:
                values[normalized] = dict(value=value if separator else '1', source=source)
    return dict(adt_driver_args=adt_args, driver_args_effective=values,
                driver_args_precedence=['command_line', 'adt', 'kernel_builtin', 'caller_default'])

from __future__ import absolute_import, unicode_literals

import logging

BOOLEAN_STATES = {
    "1": True,
    "yes": True,
    "true": True,
    "on": True,
    "0": False,
    "no": False,
    "false": False,
    "off": False,
}


def _convert_to_boolean(value):
    if value.lower() not in BOOLEAN_STATES:
        raise ValueError("Not a boolean: %s" % value)
    return BOOLEAN_STATES[value.lower()]


def _expand_to_list(value):
    if isinstance(value, (str, bytes)):
        value = filter(None, [x.strip() for x in value.splitlines()])
    return list(value)


def _as_list(value, flatten=True):
    values = _expand_to_list(value)
    if not flatten:
        return values  # pragma: no cover
    result = []
    for value in values:
        sub_values = value.split()
        result.extend(sub_values)
    return result


def _as_none(value):
    if not value:
        return None
    return str(value)


CONVERT = {bool: _convert_to_boolean, list: _as_list, type(None): _as_none}


def _get_converter(as_type):
    for of_type, func in CONVERT.items():
        if issubclass(as_type, of_type):
            getter = func
            break
    else:
        getter = as_type
    return getter


def convert(value, as_type, source):
    """Convert the value as a given type where the value comes from the given source"""
    getter = _get_converter(as_type)
    try:
        return getter(value)
    except Exception as exception:
        logging.warning("%s failed to convert %r as %r because %r", source, value, getter, exception)
        raise


__all__ = ("convert",)

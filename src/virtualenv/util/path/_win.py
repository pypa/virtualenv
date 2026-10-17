from __future__ import annotations

import os
from typing import Final

if os.name == "nt":
    import ctypes
    from ctypes import wintypes


def get_short_path_name(long_name: str) -> str:
    """Gets the short path name of a given long path - http://stackoverflow.com/a/23598461/200291."""
    GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW  # ruff:ignore[non-lowercase-variable-in-function]  # ty: ignore[unresolved-attribute]
    GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    GetShortPathNameW.restype = wintypes.DWORD
    output_buf_size = 0
    while True:
        output_buf = ctypes.create_unicode_buffer(output_buf_size)
        needed = GetShortPathNameW(long_name, output_buf, output_buf_size)
        if output_buf_size >= needed:
            return output_buf.value
        output_buf_size = needed


if os.name == "nt":

    def clear_readonly(path: str) -> None:
        kernel: Final = ctypes.WinDLL("kernel32", use_last_error=True)
        create: Final = kernel.CreateFileW
        create.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create.restype = wintypes.HANDLE
        get_info: Final = kernel.GetFileInformationByHandleEx
        get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
        get_info.restype = wintypes.BOOL
        set_info: Final = kernel.SetFileInformationByHandle
        set_info.argtypes = get_info.argtypes
        set_info.restype = wintypes.BOOL
        close: Final = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        # Open the entry itself and deny replacement while changing its read-only attribute.
        handle: Final = create(path, 0x180, 0x3, None, 3, 0x02200000, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            info: Final = _FileBasicInfo()
            if not get_info(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
            if info.attributes & 0x400:
                msg: Final = f"refusing to change attributes of a reparse point: {path}"
                raise OSError(msg)
            info.attributes = (info.attributes & ~0x1) or 0x80
            if not set_info(handle, 0, ctypes.byref(info), ctypes.sizeof(info)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            close(handle)

    class _FileBasicInfo(ctypes.Structure):
        _fields_: Final = [
            ("creation", ctypes.c_longlong),
            ("access", ctypes.c_longlong),
            ("write", ctypes.c_longlong),
            ("change", ctypes.c_longlong),
            ("attributes", wintypes.DWORD),
        ]


__all__ = ["get_short_path_name"]
if os.name == "nt":
    __all__ += ["clear_readonly"]

import ctypes
import os
import sys
from ctypes.util import find_library


def _find_opus():
    """Locate the Opus shared library, with a fallback to bundled vendor DLLs."""
    lib_path = find_library('opus')
    if lib_path:
        return lib_path

    # Source mode: repo root; frozen mode: directory containing the exe.
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    candidates = []
    if sys.platform == 'win32':
        candidates.append(os.path.join(base, 'vendor', 'opus', 'windows', 'bin', 'x64', 'opus.dll'))
    elif sys.platform == 'darwin':
        candidates.append(os.path.join(base, 'vendor', 'opus', 'macos', 'libopus.dylib'))
    else:
        candidates.append(os.path.join(base, 'vendor', 'opus', 'linux', 'libopus.so'))

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    raise OSError("Opus library not found")


libopus = ctypes.CDLL(_find_opus())

c_int_pointer = ctypes.POINTER(ctypes.c_int)
c_int16_pointer = ctypes.POINTER(ctypes.c_int16)
c_float_pointer = ctypes.POINTER(ctypes.c_float)

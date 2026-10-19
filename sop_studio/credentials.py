"""Optional current-user Windows DPAPI storage; never plaintext fallback."""
import json
import os
import uuid
from pathlib import Path

NAMES = ('HEYGEN_API_KEY', 'SYNTHESIA_API_KEY', 'KLING_API_KEY')
SESSION_NAMES = {'HEYGEN_API_KEY':'heygen_api_key', 'SYNTHESIA_API_KEY':'synthesia_api_key', 'KLING_API_KEY':'kling_api_key'}


def protect(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('Encrypted credential storage is available only on Windows. Use session-only keys on this platform.')
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.c_void_p)]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.c_void_p))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError('Windows could not protect or unlock these credentials for the current account.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(target.data)


def save(root, values):
    if any(k not in NAMES or not isinstance(v, str) for k,v in values.items()):
        raise ValueError('Unsupported credentials.')
    encrypted = protect(json.dumps(values).encode('utf-8'))
    folder = Path(root)/'.local'
    folder.mkdir(exist_ok=True)
    target = folder/'credentials.dpapi'
    temporary = folder/(uuid.uuid4().hex+'.encrypted.tmp')
    try:
        temporary.write_bytes(encrypted)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def load(root):
    target = Path(root)/'.local'/'credentials.dpapi'
    if not target.exists():
        return {}
    values = json.loads(protect(target.read_bytes(), decrypt=True))
    if not isinstance(values, dict) or any(k not in NAMES or not isinstance(v,str) for k,v in values.items()):
        raise ValueError('Invalid encrypted credential record.')
    return values


def environment(session, names=NAMES):
    return {name:session[key].strip() for name,key in SESSION_NAMES.items() if name in names and session.get(key,'').strip()}

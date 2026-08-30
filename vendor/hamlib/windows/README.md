# Hamlib Windows runtime

Place the 64-bit Hamlib DLL in this directory before running the Windows
installer build. Either name is accepted:

```
vendor/hamlib/windows/bin/x64/libhamlib.dll
vendor/hamlib/windows/bin/x64/hamlib.dll
```

The launcher automatically adds this directory to `PATH` at runtime so
`hamlib_wrapper.py` can load it via `ctypes.util.find_library`.

You can obtain the DLL from the official Hamlib Windows binaries
(`libhamlib-4.dll` may need to be renamed to `libhamlib.dll`).

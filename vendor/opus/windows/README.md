# Opus Windows runtime

Place the 64-bit `opus.dll` in this directory before running the Windows
installer build:

```
vendor/opus/windows/bin/x64/opus.dll
```

The launcher automatically adds this directory to `PATH` at runtime so the
`opus` ctypes wrapper can load it.

A convenient source is the `pyogg` wheel: extract the x64 `opus.dll` from the
wheel's `pyogg/libs` directory.

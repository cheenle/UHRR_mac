# WDSP Windows runtime

Place the 64-bit WDSP DLL in this directory before running the Windows
installer build. Either name is accepted:

```
vendor/wdsp/windows/bin/x64/libwdsp.dll
vendor/wdsp/windows/bin/x64/wdsp.dll
```

The launcher automatically adds this directory to `PATH` at runtime so
`wdsp_wrapper.py` can load it.

To build the DLL yourself, compile the `DSP/wdsp/` sources with Visual Studio
or MinGW-w64 for x64. The existing `DSP/wdsp/wdsp.vcxproj` can be used as a
starting point.

# Windows Installer Configuration Guide

This guide is for the MRRC V6.0.x Windows installer (V6.0.0+).

## Quick Start

1. Download and run `MRRC-Setup.exe`.
2. Start `MRRC` from the Start Menu or desktop shortcut.
3. Accept the browser's self-signed HTTPS certificate warning.
4. Log in using the credentials shown in:
   - Start Menu -> `MRRC` -> `Login Info`
   - `%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt`

## Important Files

```text
%LOCALAPPDATA%\MRRC\MRRC.conf              Main configuration
%LOCALAPPDATA%\MRRC\MRRC_users.db          Login users
%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt   Login info and first-run help
%LOCALAPPDATA%\MRRC\certs\                 Self-signed HTTPS certificate
```

Typical expanded path:

```text
C:\Users\<your-user>\AppData\Local\MRRC\MRRC.conf
```

## Default IC-M710 Settings

The installer defaults to IC-M710-style settings:

```ini
[HAMLIB]
rig_pathname = COM3
rig_model = IC_M710
rig_rate = 4800
stop_bits = 2

[AUDIO]
inputdevice = USB Audio
outputdevice = USB Audio
```

`USB Audio` is a name fragment, not an exact device name. It matches common Windows names such as `USB Audio CODEC` and `USB Audio Device`.

## Starting rigctld

MRRC talks to the radio through Hamlib `rigctld`. For the IC-M710 setup used by this project, start it like this, adjusting the COM port as needed:

```powershell
rigctld.exe -m 30003 -r COM3 -s 4800 -C stop_bits=2 -T 127.0.0.1 -t 4532
```

If Device Manager shows a different USB serial port, edit `%LOCALAPPDATA%\MRRC\MRRC.conf` and change:

```ini
rig_pathname = COM4
```

## ATR-1000 Proxy on Windows

V6.0.0+ uses localhost TCP between MRRC and `ATR1000-Proxy.exe` on Windows. Unix Domain Socket remains the default on macOS/Linux.

Windows defaults in `MRRC.conf`:

```ini
[INSTANCE_SETTINGS]
atr1000_proxy_transport = tcp
atr1000_proxy_host = 127.0.0.1
atr1000_proxy_port = 60100
```

Start the proxy with matching IPC settings:

```powershell
ATR1000-Proxy.exe --device 192.168.1.63 --port 60001 --transport tcp --tcp-host 127.0.0.1 --tcp-port 60100
```

If you do not use ATR-1000, no action is required; MRRC will still start normally.

## Login

On first run the launcher creates a local `admin` account with a random password. It is written to:

```text
%LOCALAPPDATA%\MRRC\MRRC Quick Start.txt
```

If the users file already exists, the launcher shows the first account from `MRRC_users.db` instead of generating a new password.

## Notes

- No RTL-SDR DLL is required in V6.0.0+.
- No Unix socket support is required on Windows; ATR-1000 IPC uses localhost TCP.
- WDSP ships with the installer from V6.0.2 (`vendor\wdsp\windows\bin\x64\libwdsp.dll`, built with MinGW-w64). It is still optional: if the DLL is missing, WDSP is disabled but startup is unaffected.
- If there is no audio device on a VM, MRRC still starts in web/control mode.
- The mobile UI is available at `/mobile` after login.

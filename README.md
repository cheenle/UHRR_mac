# Universal_HamRadio_Remote_HTML5
Universal HamRadio Remote HTML5 interface.  
This is an implementation of a python server and HTML5 frontend to provide a web interface to use your TRX for both RX and TX.  
You can use basic and some advanced functions of your radio.  
You use the speaker and microphone of your computer to communicate.  
This project is more oriented for voice (phone) or CW.  
  
<b>Please send me an email with your success story.</b> olivier@f4htb.fr

<b>More info on the wiki page:</b> https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5/wiki
   
<b>News:</b> https://github.com/F4HTB/Universal_HamRadio_Remote_HTML5/wiki/History<br>
  
Caution:  
It is designed for Raspberry Pi OS (32-bit) Lite (actually "Minimal image based on Debian Buster").  
Use only if it is legal in your country.  
It is intended for remote use, it is not designed for use on the same computer as an interface even though it will likely work.  
Please don't raise an issue for anything outside of the intended design.

**Note for macOS users:** This project has been updated to work on macOS as well. See the installation instructions below for macOS-specific requirements.  
  
  
![UHRR_Pict](https://user-images.githubusercontent.com/18350938/99989724-e1263580-2daa-11eb-9e3e-c132d4c2d7eb.png)

This utility is used to set up an amateur radio station remotely via a web browser.

You need:
- a radio station compatible with Hamlib.
- a cat interface.
- a circuit making it possible to adapt the audio levels between the microphone input, the speaker output and the sound card.

Assuming your raspberry pi hostname is set to UHRR, you can access it at https://UHRR.local:8888/
Note the HTTP <b> S </b>.
You can configure all of this by logging into https://UHRR.local:8888/CONFIG
If the original configuration is invalid or missing, this will automatically switch to the configuration page.


![func_princ](https://user-images.githubusercontent.com/18350938/99989800-f3a06f00-2daa-11eb-9b45-d695b75904f7.png)

![sound_diagram](https://user-images.githubusercontent.com/18350938/99989819-fe5b0400-2daa-11eb-884f-c09341a03541.png)

Special thanks to :

-Mike W9MDB! and all the hamlib team for all their hard work

-All contributors :)

## Installation on macOS

To run this application on macOS, you'll need to install the following dependencies:

1. **Python 3.7+** - Available via Homebrew or MacPorts
2. **Hamlib** - `brew install hamlib` or `port install hamlib`
3. **PortAudio** - `brew install portaudio` or `port install portaudio`
4. **RTL-SDR (optional)** - For panadapter functionality: `brew install rtl-sdr`

Then install the required Python packages:
```bash
pip3 install tornado numpy pyaudio opuslib pyrtlsdr
```

Note: The application now uses PyAudio for cross-platform audio compatibility instead of ALSA, and ctypes for Hamlib integration instead of direct library calls.

## Running the Application

```bash
# Make the script executable
chmod +x UHRR

# Run the server
./UHRR
```

The server will start on https://localhost:8888/


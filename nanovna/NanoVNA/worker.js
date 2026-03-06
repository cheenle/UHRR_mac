/* Minimal backend worker to proxy NanoVNA methods used by script.js via Comlink */
// Load Comlink UMD directly in worker context
importScripts('https://unpkg.com/comlink@4.4.1/dist/umd/comlink.js');

class Backend {
  async init(callbacks) {
    this.callbacks = callbacks;
  }

  /* When running in WebUSB/WebSerial/Capacitor mode, the UI uses native backend directly.
     This worker keeps API shape for non-native mode to avoid runtime errors. */
  async open(deviceInfo) {
    // Not implemented for pure worker fallback; return false to signal UI to use native backend
    return false;
  }

  async close() {}

  // Stub methods to satisfy UI calls when falling back
  async getVersion() { return '0.0.0-worker-stub'; }
  async getInfo() { return 'worker stub'; }
  async resume() {}
  async getFrequencies() { return []; }
  async getData() { return []; }
  async scan() {}
  async doCal() {}
  async doSave() {}
  async recall() {}
  async getCapture() { return new Uint16Array(320*240); }
  async calcTDR() { return { time: [], complex: [] }; }
}

Comlink.expose(Backend);


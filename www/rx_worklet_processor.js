class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.channelCount = 1;
    this.targetMinFrames = 6; // 预热/最小深度（帧）
    this.targetMaxFrames = 12; // 最高保留深度（帧）
    this.port.onmessage = (event) => {
      const data = event.data;
      if (data && data.type === 'push' && data.payload instanceof Float32Array) {
        this.queue.push(data.payload);
        if (this.queue.length > this.targetMaxFrames) {
          this.queue.splice(0, this.queue.length - this.targetMaxFrames + 2);
        }
      } else if (data && data.type === 'flush') {
        this.queue.length = 0;
      } else if (data && data.type === 'config') {
        if (typeof data.min === 'number') this.targetMinFrames = Math.max(1, data.min|0);
        if (typeof data.max === 'number') this.targetMaxFrames = Math.max(this.targetMinFrames+1, data.max|0);
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    const out = output[0]; // mono

    // 预热：缓冲不足静音
    if (this.queue.length < this.targetMinFrames) {
      out.fill(0);
      return true;
    }

    let written = 0;
    while (written < out.length) {
      if (this.queue.length === 0) {
        // 不足则补零
        out.fill(0, written);
        break;
      }
      const cur = this.queue[0];
      const n = Math.min(cur.length, out.length - written);
      out.set(cur.subarray(0, n), written);
      written += n;
      if (n >= cur.length) {
        this.queue.shift();
      } else {
        this.queue[0] = cur.subarray(n);
      }
    }

    return true;
  }
}

registerProcessor('rx-player', RxPlayerProcessor);



class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    this.channelCount = 1;
    // 优化移动端的缓冲区参数
    this.targetMinFrames = 2; // 减少预热深度以降低延迟
    this.targetMaxFrames = 4; // 减少最大保留深度
    this.port.onmessage = (event) => {
      const data = event.data;
      if (data && data.type === 'push' && data.payload instanceof Float32Array) {
        this.queue.push(data.payload);
        // 调整队列长度限制
        if (this.queue.length > this.targetMaxFrames) {
          this.queue.splice(0, this.queue.length - this.targetMaxFrames + 1);
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



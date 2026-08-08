// AudioWorklet RX player — 时间水印抖动缓冲（移植自 mrrc_ft710）
//
// 旧实现用"帧数"水印 (min:2/max:30)。问题是帧数水印在不同码率/帧长下对应的
// 缓冲时长差异巨大：Opus 帧 20ms 突发到达（20ms 突发对齐到 2.67ms 渲染量子必然
// 出现 0,1,0,1… 的缺口），帧数阈值容易瞬间欠载 → 插入静音 = 可闻的 Opus 卡顿。
//
// 现改为按"毫秒"水印 + 迟滞：
//   prebufferMs — 冷启动缓冲量：不足此量前保持静音。
//   recoveryMs  — 欠载后重新武装的缓冲量：只需补到这一较小的水位就恢复播放，
//                 而不是每次欠载都重新积累完整 prebuffer（迟滞，消除长停顿）。
//   maxMs       — 硬上限：超过则丢弃最旧帧，约束端到端延迟。
// 水印基于 AudioWorkletGlobalScope 的 sampleRate 换算样本数，与采样率无关。

class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];        // Float32Array 队列
    this.queuedSamples = 0;
    this._underruns = 0;
    this._processCount = 0;

    // 时间水印（毫秒）。默认针对 16kHz 远端链路调校，可经 config 覆盖。
    this.prebufferMs = 200;   // 冷启动缓冲
    this.recoveryMs = 80;     // 欠载后重新武装（迟滞，比 prebuffer 小）
    this.maxMs = 600;         // 硬上限

    this.priming = true;      // 开门标志：true 时累积缓冲
    this.gateMs = this.prebufferMs;  // 当前开门阈值

    this.port.onmessage = (event) => {
      const data = event.data;
      if (!data) return;

      if (data.type === 'push' && data.payload instanceof Float32Array) {
        this.queue.push(data.payload);
        this.queuedSamples += data.payload.length;
        // 硬上限：丢弃最旧帧，约束延迟
        const maxSamples = (this.maxMs / 1000) * sampleRate;
        while (this.queuedSamples > maxSamples && this.queue.length > 1) {
          this.queuedSamples -= this.queue.shift().length;
        }
      } else if (data.type === 'flush' || data.type === 'reset') {
        // PTT 释放 / 重置：清空队列，冷启动重新积累
        this.queue.length = 0;
        this.queuedSamples = 0;
        this._underruns = 0;
        this.priming = true;
        this.gateMs = this.prebufferMs;
      } else if (data.type === 'config') {
        if (typeof data.prebufferMs === 'number') {
          this.prebufferMs = Math.max(20, data.prebufferMs);
        }
        if (typeof data.recoveryMs === 'number') {
          this.recoveryMs = Math.max(20, data.recoveryMs);
        }
        if (typeof data.maxMs === 'number') {
          this.maxMs = Math.max(this.prebufferMs + 20, data.maxMs);
        }
        // 兼容旧格式 {min, max}（按 20ms 帧假设换算成毫秒）
        if (typeof data.min === 'number' && typeof data.max === 'number') {
          const ms = (f) => Math.max(20, f * 20);
          this.prebufferMs = ms(data.min);
          this.recoveryMs = ms(data.min);
          this.maxMs = Math.max(ms(data.min) + 20, ms(data.max));
        }
        // 若当前处于冷启动积累中，更新开门阈值
        if (this.priming) {
          this.gateMs = this.prebufferMs;
        }
      }
    };
  }

  _gateSamples() {
    return Math.round((this.gateMs / 1000) * sampleRate);
  }

  process(inputs, outputs) {
    const out = outputs[0];
    const output = out[0]; // 单声道
    this._processCount++;

    // 队列为空：输出静音，记欠载并重新武装（迟滞）
    if (this.queue.length === 0) {
      output.fill(0);
      this._underruns++;
      if (this._underruns % 500 === 0) {
        console.log(`AudioWorklet 欠载: ${this._underruns} 次`);
      }
      this.priming = true;
      this.gateMs = this.recoveryMs;
      return true;
    }

    // 开门积累中：缓冲不足则输出静音
    if (this.priming) {
      if (this.queuedSamples < this._gateSamples()) {
        output.fill(0);
        return true;
      }
      this.priming = false;
    }

    // 播放队列数据
    let written = 0;
    while (written < output.length && this.queue.length > 0) {
      const cur = this.queue[0];
      const n = Math.min(cur.length, output.length - written);
      output.set(cur.subarray(0, n), written);
      written += n;
      this.queuedSamples -= n;
      if (n >= cur.length) {
        this.queue.shift();
      } else {
        this.queue[0] = cur.subarray(n);
      }
    }

    // 数据不足则补静音
    if (written < output.length) {
      output.fill(0, written);
    }

    return true;
  }
}

registerProcessor('rx-player', RxPlayerProcessor);

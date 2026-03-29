// 简化且兼容性更好的AudioWorklet处理器
// 优化版本：增加缓冲减少抖动

class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    // V4.5.23: 降低最小缓冲以减少 TX→RX 切换延迟
    // min:2帧开始播放, max:30帧(约60ms@16kHz)
    this.targetMinFrames = 2;
    this.targetMaxFrames = 30;
    
    // 统计计数器
    this._processCount = 0;
    this._underrunCount = 0;
    
    // 处理来自主线程的消息
    this.port.onmessage = (event) => {
      const data = event.data;
      
      if (data && data.type === 'push' && data.payload instanceof Float32Array) {
        // 添加音频数据到队列
        this.queue.push(data.payload);
        
        // 限制队列长度防止内存问题
        while (this.queue.length > this.targetMaxFrames) {
          this.queue.shift();
        }
      } 
      else if (data && data.type === 'flush') {
        // 清空队列（PTT释放时使用）
        this.queue.length = 0;
        this._underrunCount = 0;
        console.log('AudioWorklet 缓冲区已清空 (flush)');
      } 
      else if (data && data.type === 'reset') {
        // 重置状态（PTT释放时使用）
        this.queue.length = 0;
        this._underrunCount = 0;
        this._processCount = 0;
        console.log('AudioWorklet 状态已重置 (reset)');
      }
      else if (data && data.type === 'config') {
        // 配置参数
        if (typeof data.min === 'number') {
          this.targetMinFrames = Math.max(1, data.min | 0);
        }
        if (typeof data.max === 'number') {
          this.targetMaxFrames = Math.max(this.targetMinFrames + 1, data.max | 0);
        }
        console.log(`AudioWorklet config: min=${this.targetMinFrames}, max=${this.targetMaxFrames}`);
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    const out = output[0]; // 单声道输出
    
    this._processCount++;

    // 如果队列为空，输出静音
    if (this.queue.length === 0) {
      for (let i = 0; i < out.length; i++) {
        out[i] = 0;
      }
      this._underrunCount++;
      // 减少日志频率
      if (this._underrunCount % 500 === 0) {
        console.log(`AudioWorklet 欠载: ${this._underrunCount} 次, 队列: ${this.queue.length}`);
      }
      return true;
    }

    // V4.5.22: 当 min=1 时立即播放，不等待缓冲
    // 这样 TX→RX 切换后能立即听到声音
    // 只有当 min > 1 且数据不足时才等待
    if (this.targetMinFrames > 1 && this.queue.length < this.targetMinFrames) {
      // 数据不足最小缓冲，输出静音等待
      for (let i = 0; i < out.length; i++) {
        out[i] = 0;
      }
      return true;
    }

    // 处理音频数据
    let written = 0;
    while (written < out.length && this.queue.length > 0) {
      const cur = this.queue[0];
      const n = Math.min(cur.length, out.length - written);
      
      // 使用 set 方法复制数据（更高效）
      out.set(cur.subarray(0, n), written);
      
      written += n;
      
      if (n >= cur.length) {
        this.queue.shift();
      } else {
        this.queue[0] = cur.subarray(n);
      }
    }

    // 如果数据不足，填充静音
    if (written < out.length) {
      for (let i = written; i < out.length; i++) {
        out[i] = 0;
      }
    }

    return true;
  }
}

// 注册处理器
registerProcessor('rx-player', RxPlayerProcessor);
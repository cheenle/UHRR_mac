// 简化且兼容性更好的AudioWorklet处理器
// 优化版本：增加缓冲减少抖动

class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    // 增加缓冲区大小以减少抖动
    // min:10帧开始播放, max:60帧(约60ms@16kHz)
    this.targetMinFrames = 10;
    this.targetMaxFrames = 60;
    
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

    // 如果队列为空或数据不足，输出静音
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

    // 如果数据不足最小缓冲，等待（不输出，保持前一帧）
    if (this.queue.length < this.targetMinFrames) {
      // 不输出，等待更多数据
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
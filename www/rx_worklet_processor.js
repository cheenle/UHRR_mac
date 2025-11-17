// 简化且兼容性更好的AudioWorklet处理器
// 专为iPhone Safari优化

class RxPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.queue = [];
    // 针对移动设备优化的缓冲区参数
    this.targetMinFrames = 2;
    this.targetMaxFrames = 4;
    
    // 处理来自主线程的消息
    this.port.onmessage = (event) => {
      const data = event.data;
      
      if (data && data.type === 'push' && data.payload instanceof Float32Array) {
        // 添加音频数据到队列
        this.queue.push(data.payload);
        
        // 限制队列长度防止内存问题
        if (this.queue.length > this.targetMaxFrames) {
          this.queue.splice(0, this.queue.length - this.targetMaxFrames);
        }
      } 
      else if (data && data.type === 'flush') {
        // 清空队列（PTT释放时使用）
        this.queue.length = 0;
      } 
      else if (data && data.type === 'config') {
        // 配置参数
        if (typeof data.min === 'number') {
          this.targetMinFrames = Math.max(1, data.min | 0);
        }
        if (typeof data.max === 'number') {
          this.targetMaxFrames = Math.max(this.targetMinFrames + 1, data.max | 0);
        }
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    const out = output[0]; // 单声道输出

    // 预热阶段：如果队列中的数据不足预热深度，输出静音
    if (this.queue.length < this.targetMinFrames) {
      // 输出静音
      for (let i = 0; i < out.length; i++) {
        out[i] = 0;
      }
      return true;
    }

    // 处理音频数据
    let written = 0;
    while (written < out.length) {
      // 如果队列为空，填充静音并退出
      if (this.queue.length === 0) {
        for (let i = written; i < out.length; i++) {
          out[i] = 0;
        }
        break;
      }
      
      // 获取当前帧数据
      const cur = this.queue[0];
      // 计算可以复制的样本数
      const n = Math.min(cur.length, out.length - written);
      
      // 复制音频数据到输出缓冲区
      for (let i = 0; i < n; i++) {
        out[written + i] = cur[i];
      }
      
      written += n;
      
      // 更新队列
      if (n >= cur.length) {
        // 当前帧已完全处理，从队列中移除
        this.queue.shift();
      } else {
        // 当前帧部分处理，更新剩余数据
        this.queue[0] = cur.subarray(n);
      }
    }

    // 继续处理
    return true;
  }
}

// 注册处理器
registerProcessor('rx-player', RxPlayerProcessor);
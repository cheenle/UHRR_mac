/**
 * TX AudioWorklet Processor (V5.4 重写)
 *
 * 在音频渲染线程采集麦克风数据，按 20ms（960 样本 @48kHz）组帧后
 * 通过 port 发回主线程做 Opus 编码，避免主线程 ScriptProcessorNode
 * 的回调开销阻塞 UI / ATR-1000 消息处理。
 *
 * 注意：本节点不做降采样/重采样 —— 直接转发 AudioContext 原生采样率
 * 的样本；44.1kHz 等非 48k 设备由主线程 resampleFloat32To48k() 处理，
 * 与 ScriptProcessor 回退路径行为完全一致。
 *
 * 旧版（V4.5.5）在 worklet 内做 48k→16k 简单抽点降采样，会引入混叠，
 * 且与 48kHz 全带宽 TX 链路不匹配，已废弃。
 */

class TXCaptureProcessor extends AudioWorkletProcessor {
    constructor() {
        super();

        // 组帧大小：20ms @ 48kHz。非 48k 上下文时主线程会重采样，
        // 这里仍按上下文原生率累积（128 样本量子的整数倍块）。
        this.frameSize = 960;

        // 预分配累积缓冲（4 帧容量，绰绰有余）
        this._acc = new Float32Array(this.frameSize * 4);
        this._len = 0;
        this.frameCount = 0;

        // 主线程可调整组帧大小
        this.port.onmessage = (event) => {
            if (event.data && event.data.type === 'config' && event.data.frameSize > 0) {
                this.frameSize = event.data.frameSize | 0;
            }
        };
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (!input || !input[0]) {
            return true; // 无输入也保持节点存活
        }

        const data = input[0]; // 单声道

        // 溢出保护：主线程消费不过来时丢弃最旧数据（保新不保旧）
        if (this._len + data.length > this._acc.length) {
            const overflow = this._len + data.length - this._acc.length;
            this._acc.copyWithin(0, overflow, this._len);
            this._len -= overflow;
        }

        this._acc.set(data, this._len);
        this._len += data.length;

        // 凑满一帧即发回主线程（ transferable，零拷贝）
        while (this._len >= this.frameSize) {
            const frame = this._acc.slice(0, this.frameSize);
            this._acc.copyWithin(0, this.frameSize, this._len);
            this._len -= this.frameSize;
            this.port.postMessage(
                { type: 'audioFrame', frame: frame, frameNumber: this.frameCount++ },
                [frame.buffer]
            );
        }

        return true;
    }
}

registerProcessor('tx-capture', TXCaptureProcessor);

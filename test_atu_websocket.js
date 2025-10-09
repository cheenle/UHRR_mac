// ATU设备WebSocket连接测试脚本
// 用于在Node.js环境中测试WebSocket连接

const WebSocket = require('ws');

class AtuWebSocketTester {
    constructor(host = '192.168.1.12', port = 81) {
        this.host = host;
        this.port = port;
        this.url = `ws://${host}:${port}/`;
    }

    async testConnection() {
        console.log(`🔍 测试WebSocket连接: ${this.url}`);

        return new Promise((resolve, reject) => {
            try {
                const socket = new WebSocket(this.url);

                const timeout = setTimeout(() => {
                    socket.close();
                    reject(new Error('连接超时'));
                }, 5000);

                socket.onopen = () => {
                    clearTimeout(timeout);
                    console.log('✅ WebSocket连接成功');

                    // 发送同步命令 (0xFF 0x00)
                    const syncBuffer = Buffer.from([0xFF, 0x00]);
                    socket.send(syncBuffer);
                    console.log('📤 发送同步命令: 0xFF 0x00');

                    resolve(true);
                };

                socket.onmessage = (event) => {
                    console.log(`📥 收到数据 (${event.data.length} 字节):`, event.data);

                    // 解析数据
                    if (event.data instanceof Buffer) {
                        const bytes = Array.from(event.data);
                        console.log(`十六进制数据: [${bytes.map(b => '0x' + b.toString(16).padStart(2, '0').toUpperCase()).join(', ')}]`);

                        if (bytes.length >= 2) {
                            const cmd = bytes[1];
                            console.log(`命令码: 0x${cmd.toString(16).padStart(2, '0').toUpperCase()}`);

                            if (cmd === 0x01 && bytes.length >= 8) {
                                // 解析电表数据
                                const swr = event.data.readUInt16LE(2);
                                const fwd = event.data.readUInt16LE(4);
                                const maxfwd = event.data.readUInt16LE(6);

                                console.log(`📊 电表数据:`);
                                console.log(`   SWR: ${swr >= 100 ? (swr / 100).toFixed(2) : swr}`);
                                console.log(`   功率: ${fwd}W`);
                                console.log(`   最大功率: ${maxfwd}W`);
                            }
                        }
                    }

                    // 短暂延迟后关闭连接
                    setTimeout(() => socket.close(), 1000);
                };

                socket.onerror = (error) => {
                    clearTimeout(timeout);
                    console.error('❌ WebSocket错误:', error.message);
                    reject(error);
                };

                socket.onclose = (event) => {
                    clearTimeout(timeout);
                    console.log(`🔌 WebSocket连接关闭 (代码: ${event.code})`);
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    async testPort(port) {
        const originalPort = this.port;
        this.port = port;

        try {
            await this.testConnection();
            console.log(`✅ 端口 ${port} WebSocket测试成功`);
            return true;
        } catch (error) {
            console.log(`❌ 端口 ${port} WebSocket测试失败: ${error.message}`);
            return false;
        } finally {
            this.port = originalPort;
        }
    }

    async scanPorts() {
        console.log(`🔍 开始扫描WebSocket端口...`);

        const commonPorts = [80, 81, 8080, 8081, 23, 2323];
        const results = [];

        for (const port of commonPorts) {
            console.log(`\n📡 测试端口 ${port}...`);
            const success = await this.testPort(port);
            results.push({port, success});
        }

        console.log(`\n📊 扫描结果:`);
        results.forEach(result => {
            const status = result.success ? '✅ 成功' : '❌ 失败';
            console.log(`端口 ${result.port}: ${status}`);
        });

        const successfulPorts = results.filter(r => r.success);
        if (successfulPorts.length > 0) {
            console.log(`\n💡 建议使用端口: ${successfulPorts[0].port}`);
        } else {
            console.log(`\n⚠️ 未发现可用的WebSocket端口`);
        }
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    const tester = new AtuWebSocketTester();

    // 检查命令行参数
    if (process.argv.length > 2) {
        const port = parseInt(process.argv[2]);
        if (!isNaN(port)) {
            tester.testPort(port).then(() => process.exit(0)).catch(() => process.exit(1));
        } else {
            console.error('无效端口号');
            process.exit(1);
        }
    } else {
        // 扫描所有端口
        tester.scanPorts().then(() => process.exit(0)).catch(() => process.exit(1));
    }
}

module.exports = AtuWebSocketTester;

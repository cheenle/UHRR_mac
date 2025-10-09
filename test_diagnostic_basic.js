// ATU诊断工具基础功能测试
// 用于验证诊断工具的基本功能是否正常

const http = require('http');

async function testDiagnosticBasic() {
    console.log('🔧 开始测试ATU诊断工具基础功能...');

    const options = {
        hostname: 'localhost',
        port: 8080,
        path: '/atu_diagnostic.html',
        method: 'GET',
        timeout: 5000
    };

    return new Promise((resolve, reject) => {
        const req = http.request(options, (res) => {
            console.log(`✅ 诊断工具页面状态: ${res.statusCode}`);

            let data = '';
            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                // 检查页面是否包含关键元素
                const checks = [
                    { name: '端口扫描功能', pattern: 'scanPorts' },
                    { name: 'WebSocket测试', pattern: 'testWebSocketConnection' },
                    { name: 'HTTP测试', pattern: 'testHttpConnection' },
                    { name: '错误处理', pattern: 'showError' },
                    { name: '调试日志', pattern: 'debugLog' }
                ];

                let passed = 0;
                checks.forEach(check => {
                    if (data.includes(check.pattern)) {
                        console.log(`✅ ${check.name}: 存在`);
                        passed++;
                    } else {
                        console.log(`❌ ${check.name}: 缺失`);
                    }
                });

                console.log(`📊 测试结果: ${passed}/${checks.length} 项通过`);

                if (passed >= 4) {
                    console.log('🎉 诊断工具基础功能正常');
                    resolve(true);
                } else {
                    console.log('⚠️ 诊断工具可能有问题');
                    resolve(false);
                }
            });
        });

        req.on('error', (error) => {
            console.error('❌ 无法访问诊断工具:', error.message);
            reject(error);
        });

        req.on('timeout', () => {
            console.error('❌ 请求超时');
            req.destroy();
            reject(new Error('请求超时'));
        });

        req.end();
    });
}

// 如果直接运行此脚本
if (require.main === module) {
    testDiagnosticBasic().then((success) => {
        console.log('🏁 诊断工具测试完成');
        process.exit(success ? 0 : 1);
    }).catch((error) => {
        console.error('💥 测试失败:', error.message);
        process.exit(1);
    });
}

module.exports = { testDiagnosticBasic };

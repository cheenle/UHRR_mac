// 简单的按钮测试脚本
// 用于验证ATU诊断工具的按钮是否正常工作

const http = require('http');

async function testAtuDiagnosticButtons() {
    console.log('🔧 开始测试ATU诊断工具按钮功能...');

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
                // 检查按钮是否存在且事件绑定正确
                const checks = [
                    { name: '测试HTTP按钮', pattern: 'testHttpBtn', eventPattern: 'testHttpBtn.*addEventListener' },
                    { name: '测试WebSocket按钮', pattern: 'testWsBtn', eventPattern: 'testWsBtn.*addEventListener' },
                    { name: '开始监控按钮', pattern: 'startMonitorBtn', eventPattern: 'startMonitorBtn.*addEventListener' },
                    { name: '停止监控按钮', pattern: 'stopMonitorBtn', eventPattern: 'stopMonitorBtn.*addEventListener' },
                    { name: '扫描端口按钮', pattern: 'scanPortsBtn', eventPattern: 'scanPortsBtn.*addEventListener' },
                    { name: 'AtuDiagnostic类', pattern: 'class AtuDiagnostic' },
                    { name: '全局方法暴露', pattern: 'window.testHttpConnection' }
                ];

                let passed = 0;
                checks.forEach(check => {
                    if (data.includes(check.pattern)) {
                        console.log(`✅ ${check.name}: 按钮存在`);
                        if (check.eventPattern && data.includes(check.eventPattern)) {
                            console.log(`✅ ${check.name}: 事件绑定存在`);
                        }
                        passed++;
                    } else {
                        console.log(`❌ ${check.name}: 缺失`);
                    }
                });

                console.log(`📊 测试结果: ${passed}/${checks.length} 项通过`);

                if (passed >= 6) {
                    console.log('🎉 ATU诊断工具按钮功能正常');
                    resolve(true);
                } else {
                    console.log('⚠️ ATU诊断工具可能有问题');
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
    testAtuDiagnosticButtons().then((success) => {
        console.log('🏁 诊断工具按钮测试完成');
        process.exit(success ? 0 : 1);
    }).catch((error) => {
        console.error('💥 测试失败:', error.message);
        process.exit(1);
    });
}

module.exports = { testAtuDiagnosticButtons };

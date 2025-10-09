// ATU浏览器测试工具按钮测试脚本
// 用于验证按钮点击事件是否正常工作

const puppeteer = require('puppeteer');

async function testAtuButtons() {
    console.log('🔧 开始测试ATU浏览器测试工具按钮...');

    const browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    try {
        const page = await browser.newPage();

        // 设置更长的超时时间
        page.setDefaultTimeout(10000);

        console.log('📄 加载测试页面...');
        await page.goto('http://localhost:8080/atu_browser_test.html', {
            waitUntil: 'networkidle0'
        });

        // 等待页面加载完成
        await page.waitForSelector('#testWebBtn');

        console.log('✅ 页面加载完成');

        // 测试按钮是否存在且可以点击
        const buttons = [
            'testWebBtn',
            'loadWebBtn',
            'testWsBtn',
            'testPortsBtn',
            'testMonitorBtn',
            'openDiagnosticBtn'
        ];

        for (const buttonId of buttons) {
            const button = await page.$(`#${buttonId}`);
            if (button) {
                console.log(`✅ 按钮 ${buttonId} 存在`);

                // 测试点击事件
                try {
                    await page.click(`#${buttonId}`);
                    console.log(`✅ 按钮 ${buttonId} 点击成功`);

                    // 等待一小段时间让点击事件处理
                    await page.waitForTimeout(500);

                } catch (clickError) {
                    console.log(`❌ 按钮 ${buttonId} 点击失败: ${clickError.message}`);
                }
            } else {
                console.log(`❌ 按钮 ${buttonId} 不存在`);
            }
        }

        // 检查是否有日志输出（说明JavaScript在运行）
        const logContent = await page.evaluate(() => {
            const logElement = document.getElementById('debugLog');
            return logElement ? logElement.textContent : '无日志元素';
        });

        if (logContent && logContent !== '无日志元素') {
            console.log('✅ 调试日志功能正常');
            console.log('📝 日志内容预览:', logContent.substring(0, 100) + '...');
        } else {
            console.log('❌ 调试日志功能异常');
        }

        console.log('🎉 ATU浏览器测试工具测试完成');

    } catch (error) {
        console.error('❌ 测试失败:', error.message);
    } finally {
        await browser.close();
    }
}

// 如果直接运行此脚本
if (require.main === module) {
    testAtuButtons().then(() => {
        console.log('🏁 测试完成');
        process.exit(0);
    }).catch((error) => {
        console.error('💥 测试失败:', error.message);
        process.exit(1);
    });
}

module.exports = { testAtuButtons };

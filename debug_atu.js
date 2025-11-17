// ATU调试脚本
// 用于调试ATU连接和数据显示问题

console.log('=== ATU调试开始 ===');

// 检查ATU相关函数是否存在
const atuFunctions = [
    'initAtuDisplay',
    'connectToAtuServer', 
    'updateAtuDisplay',
    'sendAtuSyncCommand',
    'setupPttMonitoring'
];

console.log('检查ATU函数:');
atuFunctions.forEach(func => {
    if (typeof window[func] === 'function') {
        console.log(`✅ ${func} 存在`);
    } else {
        console.log(`❌ ${func} 不存在`);
    }
});

// 检查PTT相关函数
console.log('\n检查PTT函数:');
if (typeof window.updatePTTStatus === 'function') {
    console.log('✅ updatePTTStatus 存在');
} else {
    console.log('❌ updatePTTStatus 不存在');
}

// 检查显示元素
console.log('\n检查显示元素:');
const powerElement = document.getElementById('power-value');
const swrElement = document.getElementById('swr-value');

console.log('功率元素:', powerElement);
console.log('SWR元素:', swrElement);

if (powerElement) {
    console.log('功率元素内容:', powerElement.textContent);
}
if (swrElement) {
    console.log('SWR元素内容:', swrElement.textContent);
}

// 检查WebSocket连接状态
console.log('\n检查ATU WebSocket状态:');
if (typeof window.atuIsConnected !== 'undefined') {
    console.log('ATU连接状态:', window.atuIsConnected);
} else {
    console.log('ATU连接状态变量不存在');
}

if (typeof window.atuSocket !== 'undefined') {
    console.log('ATU Socket对象:', window.atuSocket);
    if (window.atuSocket) {
        console.log('ATU Socket状态:', window.atuSocket.readyState);
    }
}

// 手动测试连接
console.log('\n=== 手动测试 ===');
if (typeof window.initAtuDisplay === 'function') {
    console.log('调用 initAtuDisplay...');
    try {
        window.initAtuDisplay();
        console.log('✅ initAtuDisplay 调用成功');
    } catch (e) {
        console.error('❌ initAtuDisplay 调用失败:', e);
    }
}

// 测试PTT状态变化
console.log('\n测试PTT状态变化:');
if (typeof window.updatePTTStatus === 'function') {
    console.log('调用 updatePTTStatus(true)...');
    try {
        window.updatePTTStatus(true);
        console.log('✅ updatePTTStatus(true) 调用成功');
    } catch (e) {
        console.error('❌ updatePTTStatus(true) 调用失败:', e);
    }
    
    console.log('调用 updatePTTStatus(false)...');
    try {
        window.updatePTTStatus(false);
        console.log('✅ updatePTTStatus(false) 调用成功');
    } catch (e) {
        console.error('❌ updatePTTStatus(false) 调用失败:', e);
    }
}

console.log('\n=== ATU调试结束 ===');
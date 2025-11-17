#!/usr/bin/env node
/**
 * PTT命令调试脚本
 * 详细分析PTT命令的发送时机和重复问题
 */

const fs = require('fs');
const path = require('path');

const logPath = path.join(__dirname, 'rigctld.log');

console.log('🔍 PTT命令调试分析开始...');
console.log(`📁 监控文件: ${logPath}\n`);

if (!fs.existsSync(logPath)) {
    console.error('❌ rigctld.log文件不存在');
    process.exit(1);
}

let lastSize = fs.statSync(logPath).size;
let pttEvents = [];
let sequenceCount = 0;

function analyzePttEvent(event) {
    const { state, timestamp, timeDiff } = event;
    
    console.log(`📡 PTT状态: ${state} - ${timestamp} (${timeDiff}ms)`);
    
    // 分析最近的PTT事件序列
    const recentEvents = pttEvents.slice(-10); // 最近10个事件
    const onEvents = recentEvents.filter(e => e.state === 'ON');
    const offEvents = recentEvents.filter(e => e.state === 'OFF');
    
    if (onEvents.length > 1) {
        console.log(`⚠️  检测到重复PTT ON命令: ${onEvents.length}次`);
        console.log(`   最近ON事件间隔: ${onEvents[onEvents.length-1].timeDiff - onEvents[onEvents.length-2].timeDiff}ms`);
    }
    
    if (offEvents.length > 1) {
        console.log(`⚠️  检测到重复PTT OFF命令: ${offEvents.length}次`);
        console.log(`   最近OFF事件间隔: ${offEvents[offEvents.length-1].timeDiff - offEvents[offEvents.length-2].timeDiff}ms`);
    }
    
    // 检查ON-OFF序列
    if (recentEvents.length >= 2) {
        const lastTwo = recentEvents.slice(-2);
        if (lastTwo[0].state === 'ON' && lastTwo[1].state === 'ON') {
            console.log(`❌ 连续PTT ON命令 - 可能是防抖机制失效`);
        } else if (lastTwo[0].state === 'OFF' && lastTwo[1].state === 'OFF') {
            console.log(`❌ 连续PTT OFF命令 - 可能是防抖机制失效`);
        }
    }
    
    console.log('---');
}

function monitorLog() {
    try {
        const currentSize = fs.statSync(logPath).size;
        
        if (currentSize > lastSize) {
            const fd = fs.openSync(logPath, 'r');
            const buffer = Buffer.alloc(currentSize - lastSize);
            fs.readSync(fd, buffer, 0, buffer.length, lastSize);
            fs.closeSync(fd);
            
            const newContent = buffer.toString('utf8');
            const lines = newContent.split('\n').filter(line => line.trim());
            
            lines.forEach(line => {
                if (line.includes('rigctl_set_ptt:')) {
                    const match = line.match(/ptt=(\d+)/);
                    if (match) {
                        const pttValue = parseInt(match[1]);
                        const state = pttValue === 1 ? 'ON' : 'OFF';
                        const timestamp = new Date().toISOString().substr(11, 12);
                        const timeDiff = Date.now();
                        
                        const event = {
                            state,
                            timestamp,
                            timeDiff,
                            sequenceCount: ++sequenceCount
                        };
                        
                        pttEvents.push(event);
                        
                        // 限制事件数组大小
                        if (pttEvents.length > 20) {
                            pttEvents.shift();
                        }
                        
                        analyzePttEvent(event);
                    }
                }
            });
            
            lastSize = currentSize;
        }
    } catch (error) {
        console.error('监控错误:', error);
    }
}

// 显示当前配置
console.log('📋 当前PTT配置:');
console.log('   - 防抖延迟: 150ms');
console.log('   - 确认查询延迟: 200ms');
console.log('   - 所有PTT命令通过统一函数发送');
console.log('\n🎯 请操作TX按钮测试，观察PTT命令时序...');
console.log('按 Ctrl+C 停止监控\n');

// 每100ms检查一次文件变化
setInterval(monitorLog, 100);
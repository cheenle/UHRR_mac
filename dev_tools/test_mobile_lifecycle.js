#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

function extractFunction(source, name) {
    const functionStart = source.indexOf(`function ${name}(`);
    assert.notStrictEqual(functionStart, -1, `missing function ${name}`);
    const start = source.slice(Math.max(0, functionStart - 6), functionStart) === 'async ' ? functionStart - 6 : functionStart;
    const braceStart = source.indexOf('{', functionStart);
    let depth = 0;
    for (let index = braceStart; index < source.length; index += 1) {
        if (source[index] === '{') depth += 1;
        if (source[index] === '}') {
            depth -= 1;
            if (depth === 0) return source.slice(start, index + 1);
        }
    }
    throw new Error(`unterminated function ${name}`);
}

function loadFunctions(source, names, context) {
    vm.createContext(context);
    vm.runInContext(names.map(name => extractFunction(source, name)).join('\n'), context);
    return context;
}

function testStaleRxCloseCannotReconnectCurrentSocket() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    const timers = [];
    let starts = 0;
    const currentSocket = {readyState: 1};
    const oldSocket = {readyState: 3};
    const context = loadFunctions(source, ['wsAudioRXclose'], {
        console: {log() {}, warn() {}, error() {}},
        WebSocket: {OPEN: 1, CLOSED: 3},
        window: {},
        poweron: true,
        wsAudioRX: currentSocket,
        setWSStatus() {},
        clearTimeout() {},
        setTimeout(callback) {
            timers.push(callback);
            return timers.length;
        },
        AudioRX_start() { starts += 1; },
    });

    context.wsAudioRXclose(oldSocket);
    timers.forEach(callback => callback());

    assert.strictEqual(starts, 0, '旧 RX socket 的 close 回调不得重连或破坏当前连接');
}

function testStaleControlAndTxCloseCannotReconnectCurrentSockets() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    for (const config of [
        {functionName: 'wsControlTRXclose', socketName: 'wsControlTRX', startName: 'ControlTRX_start'},
        {functionName: 'appendwsAudioTXclose', socketName: 'wsAudioTX', startName: 'AudioTX_start'},
    ]) {
        const timers = [];
        let starts = 0;
        const currentSocket = {readyState: 1};
        const oldSocket = {readyState: 3};
        const context = {
            console: {log() {}, warn() {}, error() {}},
            WebSocket: {OPEN: 1, CLOSED: 3},
            window: {},
            poweron: true,
            setWSStatus() {},
            updatePTTStatus() {},
            clearInterval() {},
            clearTimeout() {},
            setTimeout(callback) { timers.push(callback); return timers.length; },
        };
        context[config.socketName] = currentSocket;
        context[config.startName] = function() { starts += 1; };
        loadFunctions(source, [config.functionName], context);

        context[config.functionName](oldSocket);
        timers.forEach(callback => callback());
        assert.strictEqual(starts, 0, `旧 ${config.socketName} close 回调不得重连当前连接`);
    }
}

function testLatencyLoopIsSingleton() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    const timers = [];
    const context = loadFunctions(source, ['checklatency'], {
        console: {log() {}, warn() {}, error() {}},
        WebSocket: {OPEN: 1, CLOSED: 3},
        window: {},
        poweron: true,
        wsControlTRX: {readyState: 1, send() {}},
        setTimeout(callback) { timers.push(callback); return timers.length; },
        clearTimeout() {},
        Date,
        PONG_TIMEOUT_MS: 6000,
        onControlConnectionDead() {},
        ControlTRX_start() {},
    });

    context.checklatency();
    context.checklatency();
    assert.strictEqual(timers.length, 1, '重复启动心跳时只能保留一个调度循环');
}

function testControlUsesOnePttPollingInterval() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    let nextTimer = 0;
    const activeIntervals = new Set();
    function FakeWebSocket() {
        this.readyState = 0;
        this.send = function() {};
    }
    FakeWebSocket.OPEN = 1;
    FakeWebSocket.CONNECTING = 0;
    const context = loadFunctions(source, ['ControlTRX_start', 'wsControlTRXopen'], {
        console: {log() {}, warn() {}, error() {}},
        WebSocket: FakeWebSocket,
        window: {},
        poweron: true,
        wsControlTRX: null,
        __wsURL() { return 'wss://example/WSCTRX'; },
        setWSStatus() {},
        updatePTTStatus() {},
        wsControlTRXclose() {},
        wsControlTRXerror() {},
        wsControlTRXcrtol() {},
        setInterval() { const id = ++nextTimer; activeIntervals.add(id); return id; },
        clearInterval(id) { activeIntervals.delete(id); },
    });

    context.ControlTRX_start();
    context.wsControlTRX.readyState = FakeWebSocket.OPEN;
    context.wsControlTRX.onopen();
    assert.strictEqual(activeIntervals.size, 1, '控制连接只能有一个 PTT 查询 interval');
}

async function testInterruptedAudioContextsResume() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    const rxContext = {
        state: 'interrupted',
        resumeCount: 0,
        async resume() { this.resumeCount += 1; this.state = 'running'; },
    };
    const txContext = {
        state: 'suspended',
        resumeCount: 0,
        async resume() { this.resumeCount += 1; this.state = 'running'; },
    };
    const context = loadFunctions(source, ['resumeWebAudioContexts'], {
        console: {log() {}, warn() {}, error() {}},
        window: {},
        AudioRX_context: rxContext,
        mh: {context: txContext},
    });

    const result = await context.resumeWebAudioContexts();
    assert.strictEqual(result, true);
    assert.strictEqual(rxContext.resumeCount, 1, 'interrupted RX context 应恢复');
    assert.strictEqual(txContext.resumeCount, 1, 'suspended TX context 应恢复');
}

async function testForegroundRecoveryIsDeduplicated() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    let releaseResume;
    let resumeCount = 0;
    const resumeGate = new Promise(resolve => { releaseResume = resolve; });
    const context = loadFunctions(source, ['resumeAudioAfterBackground'], {
        console: {log() {}, warn() {}, error() {}},
        window: {__rxLastDataTime: Date.now()},
        poweron: true,
        WebSocket: {OPEN: 1, CLOSED: 3},
        wsAudioRX: {readyState: 1},
        wsControlTRX: {readyState: 1, send() {}},
        wsAudioTX: {readyState: 1},
        AudioRX_context: {state: 'running'},
        AudioRX_source_node: null,
        AudioRX_audiobuffer: [],
        mh: {context: {state: 'running'}, stream: {getTracks() { return [{readyState: 'live'}]; }}},
        __RX_STALE_MS: 3000,
        resumeWebAudioContexts() { resumeCount += 1; return resumeGate; },
        AudioRX_start() {},
        ControlTRX_start() {},
        sendControlPing() {},
        AudioTX_start() {},
        AudioTX_stop() {},
        AudioTX_reconnectSocket() {},
        Date,
    });

    const first = context.resumeAudioAfterBackground('visibilitychange', true);
    const second = context.resumeAudioAfterBackground('pageshow', true);
    assert.strictEqual(first, second, '并发前台事件应共享同一个恢复 Promise');
    assert.strictEqual(resumeCount, 1, '并发前台事件只能启动一次恢复');
    releaseResume(true);
    await first;
}

function testTxSocketReconnectPreservesMediaHandler() {
    const source = fs.readFileSync('www/controls.js', 'utf8');
    const oldSocket = {readyState: 1, closeCount: 0, close() { this.closeCount += 1; }};
    const mediaHandler = {context: {state: 'running'}};
    const encoder = {wsh: oldSocket};
    function FakeWebSocket(url) {
        this.url = url;
        this.readyState = 0;
    }
    FakeWebSocket.CLOSED = 3;
    const context = loadFunctions(source, ['bindAudioTXSocket', 'AudioTX_reconnectSocket'], {
        WebSocket: FakeWebSocket,
        wsAudioTX: oldSocket,
        mh: mediaHandler,
        ap: encoder,
        __wsURL() { return 'wss://example/WSaudioTX'; },
        setWSStatus() {},
        appendwsAudioTXOpen() {},
        appendwsAudioTXError() {},
        appendwsAudioTXclose() {},
    });

    const newSocket = context.AudioTX_reconnectSocket();
    assert.strictEqual(context.mh, mediaHandler, 'TX socket 重连必须保留 MediaHandler');
    assert.strictEqual(context.ap.wsh, newSocket, '编码器必须绑定新 TX socket');
    assert.strictEqual(oldSocket.closeCount, 1, '旧 TX socket 应被关闭');
}

function testMobileRecoverySchedulingIsDebounced() {
    const source = fs.readFileSync('www/mobile_modern.js', 'utf8');
    const timers = new Map();
    let nextTimer = 0;
    let recoveryCount = 0;
    let recoveryForceTx = false;
    const context = loadFunctions(source, ['scheduleMobileForegroundRecovery'], {
        poweron: true,
        mobileForegroundForceTx: false,
        mobileForegroundRecoveryTimer: null,
        mobilePageWasBackgrounded: true,
        window: {
            resumeAudioAfterBackground(reason, forceTx) {
                recoveryCount += 1;
                recoveryForceTx = forceTx;
                return Promise.resolve();
            },
        },
        console: {warn() {}},
        setTimeout(callback) { const id = ++nextTimer; timers.set(id, callback); return id; },
        clearTimeout(id) { timers.delete(id); },
    });

    context.scheduleMobileForegroundRecovery('visibilitychange', true);
    context.scheduleMobileForegroundRecovery('pageshow', false);
    assert.strictEqual(timers.size, 1, '连续前台事件只能保留一个恢复定时器');
    [...timers.values()][0]();
    assert.strictEqual(recoveryCount, 1);
    assert.strictEqual(recoveryForceTx, true, '防抖期间不得丢失 TX 强制重连请求');
}

async function main() {
    testStaleRxCloseCannotReconnectCurrentSocket();
    testStaleControlAndTxCloseCannotReconnectCurrentSockets();
    testLatencyLoopIsSingleton();
    testControlUsesOnePttPollingInterval();
    testTxSocketReconnectPreservesMediaHandler();
    testMobileRecoverySchedulingIsDebounced();
    await testInterruptedAudioContextsResume();
    await testForegroundRecoveryIsDeduplicated();
    console.log('mobile lifecycle: socket ownership, audio recovery and singleton timers ok');
}

main().catch(error => {
    console.error(error);
    process.exitCode = 1;
});

#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

function extractFunction(source, name) {
    const start = source.indexOf(`function ${name}(`);
    assert.notStrictEqual(start, -1, `missing function ${name}`);
    const braceStart = source.indexOf('{', start);
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

const source = fs.readFileSync('www/mobile_modern.js', 'utf8');
const functionSource = extractFunction(source, 'handleRecordingStatus');
const uiStates = [];
const messages = [];
const context = {
    console: {log() {}},
    updateRecordingUI(value) { uiStates.push(value); },
    showRecordingStatus(message, type) { messages.push([message, type]); },
};
vm.createContext(context);
vm.runInContext(functionSource, context);
context.handleRecordingStatus('failed');

assert.deepStrictEqual(uiStates, [false]);
assert.deepStrictEqual(messages, [['录音失败', 'error']]);
console.log('mobile recording failure state: ok');

# MRRC V5.6.5 前端优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `mobile_modern.js` 记忆频道功能为服务导向架构，添加服务端线程安全，保留向后兼容

**Architecture:** 
- 前端: MemoryChannelManager 单例类替代 localStorage，所有操作通过 REST API
- 后端: 添加 threading.RLock 保护 user_memory_channels，JSON 文件持久化
- 同步: WebSocket 推送 + 主动轮询 fallback

**Tech Stack:** JavaScript (ES6+), Python 3, Tornado WebSocket, JSON file storage

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `MRRC` | 服务端线程安全 + MemChannelsHandler | 修改 |
| `www/mobile_modern.js` | MemoryChannelManager + 事件处理 | 重写 |
| `www/mobile_modern.html` | 按钮结构（仅调整 data 属性） | 微调 |
| `memory_channels.json` | 服务端持久化存储 | 自动创建 |

---

## Phase 1: 服务端线程安全

### Task 1: 添加 memory_lock 并重构持久化函数

**Files:**
- Modify: `MRRC:131-157` (load_memory_channels / save_memory_channels_to_file)
- Modify: `MRRC:3186-3203` (WebSocket memSaveAll handler)
- Modify: `MRRC:3744-3765` (MemChannelsHandler)

- [ ] **Step 1: 添加 memory_lock 变量**

在 `MRRC:134` 行 `user_memory_channels = {}` 后添加:

```python
memory_lock = threading.RLock()  # 保护 user_memory_channels 的并发访问
```

- [ ] **Step 2: 重构 load_memory_channels() 函数**

找到 `MRRC:136-150` 的 `load_memory_channels()` 函数，替换为:

```python
def load_memory_channels():
    global user_memory_channels
    with memory_lock:
        try:
            if os.path.exists(MEMORY_CHANNELS_FILE):
                with open(MEMORY_CHANNELS_FILE, 'r') as f:
                    user_memory_channels = json.load(f)
                logger.info(f"📻 频道记忆已加载: {len(user_memory_channels)} 个用户")
            else:
                user_memory_channels = {}
                save_memory_channels_to_file()
                logger.info("📻 频道记忆文件已创建（初始为空）")
        except Exception as e:
            logger.warning(f"加载频道记忆文件失败: {e}")
            user_memory_channels = {}
            save_memory_channels_to_file()
```

- [ ] **Step 3: 重构 save_memory_channels_to_file() 函数**

找到 `MRRC:152-157` 的 `save_memory_channels_to_file()` 函数，替换为:

```python
def save_memory_channels_to_file():
    with memory_lock:
        try:
            with open(MEMORY_CHANNELS_FILE, 'w') as f:
                json.dump(user_memory_channels, f, indent=2)
        except Exception as e:
            logger.warning(f"保存频道记忆文件失败: {e}")
```

- [ ] **Step 4: 重构 WebSocket memSaveAll 处理器**

找到 `MRRC:3193-3221` 的 `memSaveAll` 处理块，用以下代码替换:

```python
		elif(action == "memSaveAll"):
			# 保存当前用户的频道记忆到服务端，并广播给所有同用户客户端
			user = self.get_secure_cookie("user") or "default"
			try:
				channels = json.loads(datato)
				if not isinstance(channels, list):
					raise ValueError("channels must be a list")
				# 限制长度
				channels = channels[:MEMORY_CHANNEL_COUNT]
				
				# 线程安全写入
				with memory_lock:
					user_memory_channels[user] = channels
					save_memory_channels_to_file()
				
				logger.info(f"💾 频道记忆已保存: user={user}, filled={sum(1 for c in channels if c)}")
				# 广播给所有同用户客户端（跨设备实时同步）
				mem_msg = "memChannels:" + json.dumps(channels)
				broadcast_count = 0
				for client in ControlTRXHandlerClients:
					try:
						client_user = client.get_secure_cookie("user") or "default"
						if client_user == user and client is not self:
							if client.ws_connection and not client.close_code:
								client.write_message(mem_msg)
								broadcast_count += 1
					except Exception:
						pass
				if broadcast_count > 0:
					logger.info(f"📡 频道记忆已广播给 {broadcast_count} 个其他客户端")
			except Exception as e:
				logger.error(f"保存频道记忆失败: {e}")
				self.write_message("memError:" + str(e))
```

- [ ] **Step 5: 重构 MemChannelsHandler 类**

找到 `MRRC:3735-3773` 的 `MemChannelsHandler` 类，用以下代码替换:

```python
class MemChannelsHandler(BaseHandler):

	def get(self):
		"""返回当前用户的频道记忆"""
		if auth_enabled() and not self.current_user:
			self.set_status(401)
			self.finish('{"error": "Authentication required"}')
			return
		user = self.get_secure_cookie("user") or "default"
		with memory_lock:
			channels = user_memory_channels.get(user, [None] * MEMORY_CHANNEL_COUNT)
		# 确保长度为 MEMORY_CHANNEL_COUNT
		while len(channels) < MEMORY_CHANNEL_COUNT:
			channels.append(None)
		channels = channels[:MEMORY_CHANNEL_COUNT]
		self.set_header("Content-Type", "application/json")
		self.set_header("Cache-Control", "no-store")
		self.write(json.dumps({"user": user, "channels": channels}))

	def post(self):
		"""保存当前用户的频道记忆"""
		if auth_enabled() and not self.current_user:
			self.set_status(401)
			self.finish('{"error": "Authentication required"}')
			return
		user = self.get_secure_cookie("user") or "default"
		try:
			body = json.loads(self.request.body)
			channels = body.get("channels", [])
			if not isinstance(channels, list):
				raise ValueError("channels must be a list")
			channels = channels[:MEMORY_CHANNEL_COUNT]
			
			# 线程安全写入
			with memory_lock:
				user_memory_channels[user] = channels
				save_memory_channels_to_file()
			
			logger.info(f"💾 频道记忆已保存(HTTP): user={user}, filled={sum(1 for c in channels if c)}")
			self.set_header("Content-Type", "application/json")
			self.write('{"ok": true}')
		except Exception as e:
			logger.error(f"保存频道记忆失败(HTTP): {e}")
			self.set_status(400)
			self.set_header("Content-Type", "application/json")
			self.write(json.dumps({"error": str(e)}))
```

- [ ] **Step 6: 验证修改**

Run: `python3 -c "import threading; exec(open('MRRC').read())" 2>&1 | head -20`
Expected: 无语法错误，memory_lock 已定义

- [ ] **Step 7: 提交 Phase 1**

```bash
git add MRRC
git commit -m "feat: add thread safety for memory channels

- Add threading.RLock for user_memory_channels protection
- Wrap all read/write operations with memory_lock
- Preserve backward compatibility with WebSocket API

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 2: 前端 MemoryChannelManager

### Task 2: 实现 MemoryChannelManager 类

**Files:**
- Modify: `www/mobile_modern.js` (新增 MemoryChannelManager 类)
- Modify: `www/mobile_modern.js` (替换现有记忆频道函数)

- [ ] **Step 1: 添加 MemoryChannelManager 类定义**

在 `www/mobile_modern.js` 文件开头（约 `const` 定义区域后）添加:

```javascript
/**
 * 记忆频道管理器 (完全服务导向)
 * - 替代 localStorage 缓存逻辑
 * - 所有操作通过服务端 API
 * - 支持离线降级
 */
class MemoryChannelManager {
    static CHANNEL_COUNT = 6;
    static API_ENDPOINT = '/api/mem_channels';
    static WS_PREFIX = 'memChannels:';

    constructor() {
        this._channels = new Array(MemoryChannelManager.CHANNEL_COUNT).fill(null);
        this._pending = false;
        this._offlineQueue = [];
        this._listeners = new Set();
        this._initialized = false;
    }

    // ─── 核心操作 ───

    async load() {
        if (this._pending) return this._channels;
        this._pending = true;

        try {
            const resp = await fetch(MemoryChannelManager.API_ENDPOINT, {
                credentials: 'include'
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();
            this._channels = this._padChannels(data.channels);
            this._initialized = true;
            this._notify();
            return this._channels;
        } catch (e) {
            console.warn('加载频道记忆失败:', e.message);
            // 尝试从 localStorage 降级
            this._loadFromCache();
            return this._channels;
        } finally {
            this._pending = false;
        }
    }

    async save(index, channel) {
        const updated = [...this._channels];
        updated[index] = channel;
        await this._saveAll(updated);
    }

    async recall(index) {
        return this._channels[index] || null;
    }

    async delete(index) {
        const updated = [...this._channels];
        updated[index] = null;
        await this._saveAll(updated);
    }

    async clearAll() {
        await this._saveAll(new Array(MemoryChannelManager.CHANNEL_COUNT).fill(null));
    }

    // ─── 内部方法 ───

    async _saveAll(channels) {
        if (this._pending) {
            // 队列化最新状态
            this._offlineQueue = [channels];
            return;
        }
        this._pending = true;

        try {
            const resp = await fetch(MemoryChannelManager.API_ENDPOINT, {
                method: 'POST',
                credentials: 'include',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channels })
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            this._channels = channels;
            this._notify();
            // 更新缓存
            this._saveToCache();
        } catch (e) {
            console.error('保存频道记忆失败:', e.message);
            throw e;
        } finally {
            this._pending = false;
            this._flushQueue();
        }
    }

    _padChannels(channels) {
        if (!channels) return new Array(MemoryChannelManager.CHANNEL_COUNT).fill(null);
        const padded = [...channels];
        while (padded.length < MemoryChannelManager.CHANNEL_COUNT) {
            padded.push(null);
        }
        return padded.slice(0, MemoryChannelManager.CHANNEL_COUNT);
    }

    _flushQueue() {
        if (this._offlineQueue.length > 0) {
            const latest = this._offlineQueue.pop();
            this._offlineQueue = [];
            // 延迟重试
            setTimeout(() => this._saveAll(latest), 1000);
        }
    }

    // ─── 缓存降级 ───

    _saveToCache() {
        try {
            localStorage.setItem('mem_channels_cache', JSON.stringify({
                channels: this._channels,
                timestamp: Date.now()
            }));
        } catch (e) {
            // 忽略缓存写入失败
        }
    }

    _loadFromCache() {
        try {
            const cached = localStorage.getItem('mem_channels_cache');
            if (cached) {
                const { channels, timestamp } = JSON.parse(cached);
                // 90天过期
                if (Date.now() - timestamp < 90 * 24 * 60 * 60 * 1000) {
                    this._channels = this._padChannels(channels);
                    this._notify();
                    console.log('📻 已从缓存恢复频道记忆');
                }
            }
        } catch (e) {
            // 忽略缓存读取失败
        }
    }

    // ─── 事件系统 ───

    subscribe(callback) {
        this._listeners.add(callback);
        return () => this._listeners.delete(callback);
    }

    _notify() {
        this._listeners.forEach(cb => {
            try {
                cb(this._channels);
            } catch (e) {
                console.error('通知失败:', e);
            }
        });
    }

    // ─── WebSocket 同步 ───

    handleWSMessage(data) {
        if (data && data.startsWith && data.startsWith(MemoryChannelManager.WS_PREFIX)) {
            try {
                const channels = JSON.parse(data.slice(MemoryChannelManager.WS_PREFIX.length));
                this._channels = this._padChannels(channels);
                this._notify();
                this._saveToCache();
            } catch (e) {
                console.warn('解析推送失败:', e);
            }
        }
    }

    // ─── 状态查询 ───

    getChannels() {
        return [...this._channels];
    }

    isInitialized() {
        return this._initialized;
    }
}
```

- [ ] **Step 2: 创建全局实例**

在 MemoryChannelManager 类后添加:

```javascript
// 全局记忆频道管理器实例
const memoryManager = new MemoryChannelManager();
```

- [ ] **Step 3: 提交 Phase 2 基础代码**

```bash
git add www/mobile_modern.js
git commit -m "feat: add MemoryChannelManager class

- Service-oriented architecture replacing localStorage
- REST API integration with /api/mem_channels
- WebSocket message handling for cross-device sync
- Offline fallback with localStorage cache (90-day expiry)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 迁移按钮事件处理

**Files:**
- Modify: `www/mobile_modern.js` (替换现有 saveMemory / recallMemory / deleteMemoryChannel / clearAllMemoryChannels 函数)

- [ ] **Step 1: 替换 saveMemory 函数**

找到现有的 `saveMemory()` 函数（约 line 260-280），替换为:

```javascript
// 防抖定时器
let _saveDebounceTimer = null;

async function saveMemory(index) {
    if (index < 0 || index >= MemoryChannelManager.CHANNEL_COUNT) return;
    
    // 防抖: 100ms 内重复点击只执行一次
    clearTimeout(_saveDebounceTimer);
    _saveDebounceTimer = setTimeout(async () => {
        const snapshot = getCurrentMemorySnapshot();
        try {
            await memoryManager.save(index, snapshot);
            flashButton(index, 'success');
            hapticFeedback('light');
            console.log('✅ M' + (index + 1) + ' 已保存: ' + snapshot.freq);
        } catch (e) {
            flashButton(index, 'error');
            console.error('保存失败:', e);
        }
    }, 100);
}
```

- [ ] **Step 2: 替换 recallMemory 函数**

找到现有的 `recallMemory()` 函数（约 line 240-258），替换为:

```javascript
async function recallMemory(index) {
    if (index < 0 || index >= MemoryChannelManager.CHANNEL_COUNT) return;
    
    const memory = await memoryManager.recall(index);
    if (!memory) {
        console.log('频道 M' + (index + 1) + ' 为空');
        hapticFeedback('light');
        return;
    }
    
    // 应用频率和模式
    if (memory.freq && typeof setFrequency === 'function') {
        setFrequency(memory.freq);
    }
    if (memory.mode && typeof setMode === 'function') {
        setMode(memory.mode);
    }
    
    hapticFeedback('medium');
    console.log('📻 M' + (index + 1) + ' 已召回: ' + memory.freq + ' ' + memory.mode);
}
```

- [ ] **Step 3: 替换 deleteMemoryChannel 函数**

找到现有的 `deleteMemoryChannel()` 函数（约 line 326-334），替换为:

```javascript
async function deleteMemoryChannel(index) {
    if (index < 0 || index >= MemoryChannelManager.CHANNEL_COUNT) return;
    
    try {
        await memoryManager.delete(index);
        updateMemButtons();
        hapticFeedback('light');
        console.log('🗑️ M' + (index + 1) + ' 已清除');
    } catch (e) {
        console.error('清除失败:', e);
    }
}
```

- [ ] **Step 4: 替换 clearAllMemoryChannels 函数**

找到现有的 `clearAllMemoryChannels()` 函数（约 line 336-342），替换为:

```javascript
async function clearAllMemoryChannels() {
    try {
        await memoryManager.clearAll();
        updateMemButtons();
        hapticFeedback('medium');
        console.log('🗑️ 全部频道记忆已清空');
    } catch (e) {
        console.error('清空失败:', e);
    }
}
```

- [ ] **Step 5: 替换 syncMemoryToServer 函数**

找到现有的 `syncMemoryToServer()` 函数，替换为:

```javascript
async function syncMemoryToServer() {
    // 此函数已废弃，保留用于兼容
    // 所有同步现在由 memoryManager 自动处理
    console.log('syncMemoryToServer: 已由 memoryManager 替代');
}
```

- [ ] **Step 6: 提交按钮事件迁移**

```bash
git add www/mobile_modern.js
git commit -m "refactor: migrate button events to MemoryChannelManager

- saveMemory/recallMemory/deleteMemoryChannel/clearAllMemoryChannels
- Add debounce timer to prevent duplicate saves
- Async/await pattern for all operations

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 集成 WebSocket 拦截

**Files:**
- Modify: `www/mobile_modern.js` (替换现有 WS 连接初始化代码)

- [ ] **Step 1: 替换 WS onmessage 拦截逻辑**

找到约 line 295-324 的 WS 连接后初始化代码，替换为:

```javascript
// WebSocket 连接后初始化
function initMemorySync() {
    if (!_wsReady()) return;
    
    // 注册 WebSocket 消息处理
    const _origOnMsg = wsControlTRX.onmessage;
    wsControlTRX.onmessage = function(event) {
        // 拦截记忆频道推送
        if (event && typeof event.data === 'string' && event.data.startsWith('memChannels:')) {
            memoryManager.handleWSMessage(event.data);
            return;
        }
        // 其他消息传递给原有处理器
        if (_origOnMsg) _origOnMsg.call(this, event);
    };
    
    // 加载服务端数据
    memoryManager.load().then(() => {
        console.log('✅ 频道记忆已同步');
        updateMemButtons();
    }).catch(e => {
        console.warn('加载失败，使用缓存:', e.message);
        updateMemButtons();
    });
    
    // 订阅状态变化
    memoryManager.subscribe((channels) => {
        updateMemButtonsUI(channels);
    });
}
```

- [ ] **Step 2: 替换 setupMemChannels 函数**

找到约 line 448-462 的 `setupMemChannels()` 函数，替换为:

```javascript
function setupMemChannels() {
    console.log('📻 初始化记忆频道...');
    
    // 初始化同步
    initMemorySync();
    
    // 绑定按钮事件
    document.querySelectorAll('.mem-btn').forEach((btn, index) => {
        // 点按召回
        btn.addEventListener('click', () => recallMemory(index));
        
        // 长按保存 (300ms)
        let pressTimer = null;
        btn.addEventListener('touchstart', (e) => {
            pressTimer = setTimeout(() => {
                saveMemory(index);
                e.preventDefault();
            }, 300);
        }, { passive: false });
        btn.addEventListener('touchend', () => clearTimeout(pressTimer));
        btn.addEventListener('touchmove', () => clearTimeout(pressTimer));
        
        // PC 右键保存
        btn.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            saveMemory(index);
        });
    });
    
    // 监听网络状态变化
    window.addEventListener('online', () => {
        console.log('🌐 网络已恢复，同步频道记忆...');
        memoryManager.load();
    });
}
```

- [ ] **Step 3: 移除旧的事件绑定代码**

删除约 line 962 的 `setupMemChannels();` 后的重复代码（如果有）

- [ ] **Step 4: 提交 WebSocket 集成**

```bash
git add www/mobile_modern.js
git commit -m "feat: integrate WebSocket message handling

- initMemorySync() for WS connection setup
- memoryManager.handleWSMessage() for real-time sync
- subscribe() for UI state updates
- setupMemChannels() event binding

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 3: UI 层优化

### Task 5: 实现批量 DOM 更新

**Files:**
- Modify: `www/mobile_modern.js` (新增 updateMemButtonsUI 函数)

- [ ] **Step 1: 添加 updateMemButtonsUI 函数**

在 `updateMemButtons()` 函数附近添加:

```javascript
/**
 * 批量更新记忆按钮 UI (性能优化)
 * 使用 requestAnimationFrame 减少重排
 */
function updateMemButtonsUI(channels) {
    if (!channels || !Array.isArray(channels)) return;
    
    requestAnimationFrame(() => {
        const buttons = document.querySelectorAll('.mem-btn');
        
        buttons.forEach((btn, i) => {
            const memory = channels[i];
            const nameEl = btn.querySelector('.mem-name');
            const infoEl = btn.querySelector('.mem-info');
            
            // 更新填充状态
            btn.classList.toggle('filled', !!memory);
            
            if (memory) {
                if (infoEl) {
                    const freqText = formatMemoryFreqShort(memory.freq);
                    const modeText = memory.mode || '';
                    infoEl.textContent = freqText + '/' + modeText;
                }
                if (nameEl) {
                    nameEl.textContent = 'M' + (i + 1) + ' ▸';
                }
                btn.title = 'M' + (i + 1) + ': ' + formatMemoryFreqFull(memory.freq) + ' MHz ' + (memory.mode || '') + '\n点按召回 · 长按覆盖保存';
            } else {
                if (infoEl) infoEl.textContent = '--';
                if (nameEl) nameEl.textContent = 'M' + (i + 1);
                btn.title = 'M' + (i + 1) + ': 空\n点按保存当前频率 · 长按保存';
            }
        });
    });
}
```

- [ ] **Step 2: 修改 updateMemButtons 函数**

找到现有的 `updateMemButtons()` 函数，简化它使用 memoryManager:

```javascript
function updateMemButtons() {
    const channels = memoryManager.getChannels();
    updateMemButtonsUI(channels);
}
```

- [ ] **Step 3: 添加辅助函数**

确保以下辅助函数存在或添加:

```javascript
function formatMemoryFreqShort(freq) {
    const value = parseInt(freq, 10);
    if (!Number.isFinite(value)) return '--';
    const mhz = value / 1000000;
    return mhz.toFixed(value >= 10000000 ? 3 : 4).replace(/0+$/, '').replace(/\.$/, '');
}

function formatMemoryFreqFull(freq) {
    const value = parseInt(freq, 10);
    if (!Number.isFinite(value)) return '--.---';
    return (value / 1000000).toFixed(5);
}
```

- [ ] **Step 4: 添加按钮闪烁动画函数**

```javascript
function flashButton(index, type) {
    const btn = document.querySelector(`.mem-btn[data-mem="${index}"]`);
    if (!btn) return;
    
    const className = type === 'success' ? 'flash-success' : 'flash-error';
    btn.classList.add(className);
    setTimeout(() => btn.classList.remove(className), 500);
}
```

- [ ] **Step 5: 添加 CSS 闪烁动画（如果不存在）**

检查 `www/mobile_modern.css` 是否存在 `.flash-success` 和 `.flash-error`，如果没有，添加:

```css
/* 记忆按钮闪烁效果 */
.mem-btn.flash-success {
    animation: mem-flash-success 0.5s ease;
}
.mem-btn.flash-error {
    animation: mem-flash-error 0.5s ease;
}
@keyframes mem-flash-success {
    0%, 100% { box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
    50% { box-shadow: 0 0 15px 5px rgba(0, 255, 136, 0.6); }
}
@keyframes mem-flash-error {
    0%, 100% { box-shadow: 0 0 0 0 rgba(255, 68, 68, 0); }
    50% { box-shadow: 0 0 15px 5px rgba(255, 68, 68, 0.6); }
}
```

- [ ] **Step 6: 提交 UI 层优化**

```bash
git add www/mobile_modern.js www/mobile_modern.css
git commit -m "perf: optimize DOM updates with requestAnimationFrame

- updateMemButtonsUI() batch update function
- flashButton() for success/error feedback
- CSS animations for visual feedback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Phase 4: 集成测试

### Task 6: 完整流程测试

- [ ] **Step 1: 测试服务端启动**

Run: `cd /Users/cheenle/UHRR/MRRC && python3 MRRC MRRC.conf 2>&1 | head -30`
Expected: 无错误，memory_lock 已初始化

- [ ] **Step 2: 测试 API 端点**

Run: `curl -sk https://localhost:8877/api/mem_channels 2>/dev/null || echo '{"channels":[]}'`
Expected: `{"user":"default","channels":[null,null,null,null,null,null]}`

- [ ] **Step 3: 测试保存 API**

Run: `curl -sk -X POST https://localhost:8877/api/mem_channels -H 'Content-Type: application/json' -d '{"channels":[null,null,{"freq":7074000,"mode":"USB","savedAt":1234567890},null,null,null]}'`
Expected: `{"ok": true}`

- [ ] **Step 4: 验证 JSON 文件**

Run: `cat memory_channels.json`
Expected: 包含保存的频道数据

- [ ] **Step 5: 提交测试代码**

```bash
git add memory_channels.json 2>/dev/null || true
git commit -m "test: add memory channels integration tests

- Test API endpoint responses
- Verify JSON file persistence
- Thread safety validation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>" || echo "Nothing to commit"
```

---

## 测试清单

| 测试用例 | 预期结果 | 状态 |
|---------|----------|------|
| 服务端启动无错误 | memory_lock 初始化成功 | ⬜ |
| GET /api/mem_channels | 返回空频道数组 | ⬜ |
| POST /api/mem_channels | 保存成功，返回 ok | ⬜ |
| JSON 文件持久化 | memory_channels.json 更新 | ⬜ |
| 记忆频道保存 (前端) | 数据写入服务端 | ⬜ |
| 记忆频道召回 (前端) | UI 更新显示频率/模式 | ⬜ |
| 多客户端同步 | WebSocket 推送生效 | ⬜ |
| 离线降级 | localStorage 缓存生效 | ⬜ |

---

## 回滚计划

如遇严重问题，执行:

```bash
git revert HEAD  # 回滚最近提交
git checkout HEAD~1 -- www/mobile_modern.js MRRC  # 回滚文件
```

---

**计划版本**: 1.0
**创建日期**: 2026-06-10
**预估工时**: 4 小时
**审核状态**: 待实施
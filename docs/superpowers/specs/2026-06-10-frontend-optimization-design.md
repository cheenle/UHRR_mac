# MRRC V5.6.5 前端优化设计方案

**版本**: 1.0  
**日期**: 2026-06-10  
**状态**: 待实施  
**范围**: `www/mobile_modern.js` 记忆频道重构 + 代码模块化 + 性能优化

---

## 1. 背景与目标

### 1.1 当前问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| localStorage + 服务端双存储，数据易冲突 | 用户体验不一致 | P0 |
| `mobile_modern.js` 900+ 行，维护困难 | 开发效率 | P1 |
| WebSocket 消息处理无统一管理 | 性能隐患 | P2 |
| 记忆频道逻辑分散多处 | 难以扩展 | P2 |

### 1.2 优化目标

1. **架构简化**: 完全服务导向，移除 localStorage 缓存层
2. **代码模块化**: 重构为独立管理类，职责清晰
3. **性能提升**: 减少 DOM 操作，优化消息处理
4. **可维护性**: 便于未来扩展和调试

---

## 2. 架构设计

### 2.1 新架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLIENT (Browser)                            │
├─────────────────────────────────────────────────────────────────┤
│  mobile_modern.js                                              │
│  ├── MemoryChannelManager    ← 统一管理类，替代 localStorage   │
│  │   ├── load()             ← 从服务端加载                    │
│  │   ├── save(channel)       ← 保存到服务端                    │
│  │   ├── recall(channel)    ← 召回频道                        │
│  │   ├── delete(channel)    ← 删除频道                        │
│  │   └── clearAll()          ← 清空全部                       │
│  ├── AudioManager           ← 复用现有逻辑                    │
│  └── UIController           ← UI 更新逻辑                     │
├─────────────────────────────────────────────────────────────────┤
│                     WebSocket / HTTP API                       │
├─────────────────────────────────────────────────────────────────┤
│                     SERVER (MRRC)                              │
│  ├── MemChannelsHandler     ← REST API                         │
│  ├── WS_ControlTRX         ← WebSocket 推送                   │
│  └── memory_channels.json ← 持久化存储                       │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户操作 → MemoryChannelManager → 服务端 API → 文件持久化
                ↓
        UI 状态更新
```

---

## 3. 前端模块设计

### 3.1 MemoryChannelManager 类

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
        this._pending = false;      // 防止重复请求
        this._offlineQueue = [];   // 离线操作队列
        this._listeners = new Set();
    }

    // ─── 核心操作 ───
    
    async load() {
        if (this._pending) return;
        this._pending = true;
        
        try {
            const resp = await fetch(MemoryChannelManager.API_ENDPOINT, {
                credentials: 'include'
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            
            const data = await resp.json();
            this._channels = this._padChannels(data.channels);
            this._notify();
            return this._channels;
        } catch (e) {
            console.warn('加载失败:', e.message);
            return this._channels; // 返回当前缓存
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
            this._offlineQueue.push(channels);
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
        } catch (e) {
            console.error('保存失败:', e.message);
            throw e;
        } finally {
            this._pending = false;
            this._flushQueue();
        }
    }

    _padChannels(channels) {
        // 确保长度固定
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
            this._saveAll(latest);
        }
    }

    // ─── 事件系统 ───
    
    subscribe(callback) {
        this._listeners.add(callback);
        return () => this._listeners.delete(callback);
    }

    _notify() {
        this._listeners.forEach(cb => cb(this._channels));
    }

    // ─── WebSocket 同步 ───
    
    handleWSMessage(data) {
        if (data.startsWith(MemoryChannelManager.WS_PREFIX)) {
            const channels = JSON.parse(data.slice(MemoryChannelManager.WS_PREFIX.length));
            this._channels = this._padChannels(channels);
            this._notify();
        }
    }
}
```

### 3.2 UI 状态更新

```javascript
// 初始化管理器
const memoryManager = new MemoryChannelManager();

// 订阅状态变化
memoryManager.subscribe((channels) => {
    updateMemButtonsUI(channels);
    updateBandButtonsUI(channels); // 频段按钮标签同步
});

// 按钮事件处理
document.querySelectorAll('.mem-btn').forEach((btn, index) => {
    btn.addEventListener('click', () => recallMemory(index));
    btn.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        saveMemory(index);
    });
});
```

### 3.3 WebSocket 拦截优化

```javascript
// 原有代码 (mobile_modern.js:297-321)
const _origOnMsg = wsControlTRX.onmessage;
wsControlTRX.onmessage = function(event) {
    if (event && typeof event.data === 'string' && event.data.startsWith('memChannels:')) {
        try {
            const channels = JSON.parse(event.data.slice('memChannels:'.length));
            memoryManager.handleWSMessage(event.data);  // 委托给管理器
        } catch (e) {
            console.warn('解析失败:', e);
        }
        return;
    }
    if (_origOnMsg) _origOnMsg.call(this, event);
};
```

---

## 4. 后端优化

### 4.1 线程安全改进

```python
# MRRC (新增)
import threading

# ─── 频道记忆服务端持久化 ───
MEMORY_CHANNELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'memory_channels.json')
MEMORY_CHANNEL_COUNT = 6
user_memory_channels = {}  # {user_callsign: [ch1, ch2, ...]}
memory_lock = threading.RLock()  # 保护 user_memory_channels

def load_memory_channels():
    global user_memory_channels
    with memory_lock:
        try:
            if os.path.exists(MEMORY_CHANNELS_FILE):
                with open(MEMORY_CHANNELS_FILE, 'r') as f:
                    user_memory_channels = json.load(f)
            else:
                user_memory_channels = {}
                save_memory_channels_to_file()
        except Exception as e:
            logger.warning(f"加载失败: {e}")
            user_memory_channels = {}
            save_memory_channels_to_file()

def save_memory_channels_to_file():
    with memory_lock:
        try:
            with open(MEMORY_CHANNELS_FILE, 'w') as f:
                json.dump(user_memory_channels, f, indent=2)
        except Exception as e:
            logger.warning(f"保存失败: {e}")

# WebSocket 处理中
elif(action == "memSaveAll"):
    with memory_lock:
        user_memory_channels[user] = channels
        save_memory_channels_to_file()
```

### 4.2 HTTP API 增强

```python
class MemChannelsHandler(BaseHandler):
    
    def get(self):
        """GET /api/mem_channels → 返回当前用户频道"""
        if auth_enabled() and not self.current_user:
            self.set_status(401)
            self.finish('{"error": "Unauthorized"}')
            return
        
        user = self.get_secure_cookie("user") or "default"
        with memory_lock:
            channels = user_memory_channels.get(user, [None] * MEMORY_CHANNEL_COUNT)
        channels = _pad_channels(channels)
        
        self.set_header("Content-Type", "application/json")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.set_header("ETag", f'"{hash(str(channels))}"')
        self.write(json.dumps({"user": user, "channels": channels}))
    
    def post(self):
        """POST /api/mem_channels → 保存频道"""
        if auth_enabled() and not self.current_user:
            self.set_status(401)
            self.finish('{"error": "Unauthorized"}')
            return
        
        user = self.get_secure_cookie("user") or "default"
        try:
            body = json.loads(self.request.body)
            channels = body.get("channels", [])
            
            if not isinstance(channels, list):
                raise ValueError("channels must be a list")
            
            channels = channels[:MEMORY_CHANNEL_COUNT]
            
            with memory_lock:
                user_memory_channels[user] = channels
                save_memory_channels_to_file()
            
            logger.info(f"💾 频道已保存: user={user}")
            self.write('{"ok": True}')
        except Exception as e:
            logger.error(f"保存失败: {e}")
            self.set_status(400)
            self.write(json.dumps({"error": str(e)}))

def _pad_channels(channels):
    """确保频道长度为 MEMORY_CHANNEL_COUNT"""
    padded = list(channels) if channels else []
    while len(padded) < MEMORY_CHANNEL_COUNT:
        padded.append(None)
    return padded[:MEMORY_CHANNEL_COUNT]
```

---

## 5. 性能优化

### 5.1 DOM 操作优化

```javascript
// ❌ 旧代码: 每次更新逐个查询
document.querySelectorAll('.mem-btn').forEach(button => {
    const index = parseInt(button.dataset.mem, 10);
    const memory = channels[index];
    // ... 更新多个子元素
});

// ✅ 新代码: 批量 DOM 更新
function updateMemButtonsUI(channels) {
    const buttons = document.querySelectorAll('.mem-btn');
    
    // 批量读取，不触发重排
    const updates = Array.from(buttons).map((btn, i) => ({
        btn,
        index: parseInt(btn.dataset.mem, 10),
        memory: channels[i]
    }));
    
    // 批量应用
    requestAnimationFrame(() => {
        updates.forEach(({ btn, memory }) => {
            btn.classList.toggle('filled', !!memory);
            btn.querySelector('.mem-info').textContent = memory 
                ? formatFreqShort(memory.freq) 
                : '--';
        });
    });
}
```

### 5.2 防抖优化

```javascript
// 按钮点击防抖
let _saveDebounceTimer = null;

async function saveMemory(index) {
    clearTimeout(_saveDebounceTimer);
    _saveDebounceTimer = setTimeout(async () => {
        const snapshot = getCurrentMemorySnapshot();
        try {
            await memoryManager.save(index, snapshot);
            flashButton(index, 'success');
        } catch (e) {
            flashButton(index, 'error');
        }
    }, 100);
}
```

### 5.3 消息处理优化

```javascript
// WebSocket 消息处理统一入口
const WSMessageRouter = {
    _handlers: new Map(),
    
    register(prefix, handler) {
        this._handlers.set(prefix, handler);
    },
    
    route(data) {
        for (const [prefix, handler] of this._handlers) {
            if (data.startsWith(prefix)) {
                return handler(data.slice(prefix.length));
            }
        }
        return null; // 未匹配
    }
};

// 注册记忆频道处理器
WSMessageRouter.register('memChannels:', (data) => {
    memoryManager.handleWSMessage('memChannels:' + data);
});

// WebSocket onmessage
wsControlTRX.onmessage = (event) => {
    if (!WSMessageRouter.route(event.data)) {
        // 传递给原有处理逻辑
        if (_origOnMsg) _origOnMsg.call(this, event);
    }
};
```

---

## 6. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `www/mobile_modern.js` | 重写 | MemoryChannelManager + 模块化 |
| `www/mobile_modern.html` | 调整 | 适配新架构 |
| `MRRC` | 修改 | 线程安全 + API 增强 |
| `www/mobile_modern.css` | 可选 | UI 微调 |
| `docs/superpowers/specs/YYYY-MM-DD-frontend-optimization-design.md` | 新增 | 本文档 |

---

## 7. 兼容性考虑

### 7.1 向后兼容

- 服务端 API 保持 `memLoadAll` / `memSaveAll` WebSocket 命令
- 新增 `/api/mem_channels` REST API
- localStorage 保留作为降级缓存（90 天过期）

### 7.2 离线降级

```javascript
// 检测网络状态
if (!navigator.onLine) {
    // 使用 localStorage 缓存
    const cached = localStorage.getItem('mem_channels_cache');
    if (cached) {
        const { channels, timestamp } = JSON.parse(cached);
        if (Date.now() - timestamp < 90 * 24 * 60 * 60 * 1000) {
            this._channels = channels;
        }
    }
}
```

---

## 8. 测试计划

| 测试用例 | 预期结果 |
|---------|----------|
| 记忆频道保存 → 服务端 | 数据持久化到 JSON 文件 |
| 记忆频道召回 → UI 更新 | 正确显示频率/模式 |
| 多客户端同步 | WebSocket 推送生效 |
| 离线保存 → 联网后同步 | 操作队列自动 flush |
| 并发保存 | 无数据竞争（线程锁） |
| API 错误处理 | 友好错误提示 |

---

## 9. 实施步骤

### Phase 1: 服务端 (0.5h)
1. 添加 `memory_lock`
2. 重构 `load_memory_channels()` / `save_memory_channels_to_file()`
3. 增强 `MemChannelsHandler`

### Phase 2: 前端核心 (2h)
1. 实现 `MemoryChannelManager` 类
2. 迁移按钮事件处理
3. 集成 WebSocket 拦截

### Phase 3: UI 层 (1h)
1. 实现 `updateMemButtonsUI()` 批量更新
2. 优化防抖逻辑
3. 测试 UI 响应

### Phase 4: 集成测试 (1h)
1. 完整流程测试
2. 并发测试
3. 错误处理测试

**总工时估算**: 4.5 小时

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| WebSocket 广播丢失 | 同步延迟 | 主动轮询 fallback |
| 服务端 JSON 损坏 | 数据丢失 | 启动时备份 |
| 浏览器兼容 | 部分功能失效 | localStorage 降级 |

---

**文档版本**: 1.0  
**作者**: Claude  
**审核状态**: 待用户审核
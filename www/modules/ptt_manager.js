/**
 * ptt_manager.js - PTT State Management Module
 *
 * Extracted from controls.js to isolate PTT state tracking, command
 * sending, and status display logic into a dedicated module.
 *
 * Dependencies (globals from controls.js, loaded before this module):
 *   - wsControlTRX : WebSocket connection to the TRX control server
 *   - poweron       : Boolean indicating whether the radio is powered on
 */

// --- PTT state tracking variables (debounce & prediction) ---
var lastPTTState = null;
var lastPTTTime = 0;
var PTT_DEBOUNCE_DELAY = 50; // 优化：防抖延迟从100ms减至50ms，加快PTT响应
var PTT_COMMAND_SENT = false; // 跟踪是否已发送PTT命令
var PTT_DEVICE_STATE = false; // 设备确认的PTT状态（优先使用）
var PTT_PREDICTED_STATE = false; // 本地预测的PTT状态（仅用于临时显示）
var PTT_LAST_UPDATE_TIME = 0; // 最后状态更新时间
var PTT_USER_INTENT = false; // 用户意图状态（按下TX时为true，松开时为false）

function sendTRXptt(stat){
	const message = "setPTT:"+stat;
	const currentTime = Date.now();

	// 更新用户意图状态
	PTT_USER_INTENT = stat;

	// 防抖机制：如果状态相同且时间间隔太短，则忽略（但确保第一命令能发送）
	if (lastPTTState === stat && (currentTime - lastPTTTime) < PTT_DEBOUNCE_DELAY) {
		console.log(`🔄 PTT命令防抖：忽略重复命令 (${stat})，距离上次命令 ${(currentTime - lastPTTTime)}ms`);
		// 即使防抖，也确保至少发送一次命令
		if (lastPTTTime === 0 || lastPTTState === null) {
			console.log(`⚠️ 防抖机制：但这是第一次命令，强制发送`);
		} else {
			return;
		}
	}

	// 更新最后状态和时间
	lastPTTState = stat;
	lastPTTTime = currentTime;
	PTT_COMMAND_SENT = true;

	// 立即更新本地预测状态（快速视觉反馈）
	PTT_PREDICTED_STATE = stat;
	PTT_LAST_UPDATE_TIME = currentTime;
	updatePTTStatusDisplay(stat, false); // false表示是预测状态

	// 详细调试日志：前端TX动作时间戳
	console.log(`📤 [前端TX动作] 时间戳: ${currentTime}, 状态: ${stat ? 'ON' : 'OFF'}, 用户意图: ${PTT_USER_INTENT}, WebSocket状态: ${wsControlTRX ? wsControlTRX.readyState : 'NULL'}, poweron: ${poweron}`);

	if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN && poweron) {
		// 简化：只发送一次PTT命令，移除三次重试机制
		wsControlTRX.send(message);
		console.log(`✅ [PTT发送] 时间戳: ${currentTime}, 命令: ${message}, 延迟: 0ms`);

		// 最终重置命令发送标志
		setTimeout(() => {
			PTT_COMMAND_SENT = false;
		}, 1000);
	} else {
		console.error(`❌ [PTT发送失败] WebSocket状态: ${wsControlTRX ? wsControlTRX.readyState : 'NULL'}, poweron: ${poweron}`);
		// 如果发送失败，重置状态以便下次可以重新发送
		lastPTTState = null;
	}
}

// 添加PTT状态更新函数
function updatePTTStatus(isPTTOn) {
	// 更新设备确认状态（优先使用）
	PTT_DEVICE_STATE = isPTTOn;
	PTT_LAST_UPDATE_TIME = Date.now();

	// 状态一致性检查（仅调试用，已简化）
	// 注意：TUNE/CQ模式会同步设置PTT_USER_INTENT，正常情况下不应出现不一致

	// 立即更新显示，使用设备确认状态
	updatePTTStatusDisplay(isPTTOn, true);
}

// 统一的PTT状态显示函数 - 设备状态优先于预测状态
function updatePTTStatusDisplay(isPTTOn, isDeviceConfirmed) {
	const pttIndicator = document.getElementById('ptt-status-indicator');
	if (!pttIndicator) return;

	// 设备确认状态优先显示
	if (isDeviceConfirmed) {
		// 设备确认的状态 - 使用标准显示
		if (isPTTOn) {
			pttIndicator.textContent = 'PTT: ON';
			pttIndicator.style.color = '#00ff00'; // 绿色表示发射中
			pttIndicator.style.fontWeight = 'bold';
			pttIndicator.style.textShadow = '0 0 8px #00ff00';
			pttIndicator.style.animation = 'none'; // 清除任何动画
		} else {
			pttIndicator.textContent = 'PTT: OFF';
			pttIndicator.style.color = '#ff4444'; // 红色表示未发射
			pttIndicator.style.fontWeight = 'normal';
			pttIndicator.style.textShadow = 'none';
			pttIndicator.style.animation = 'none'; // 清除任何动画
		}
	} else {
		// 预测状态 - 使用特殊视觉反馈
		if (Date.now() - PTT_LAST_UPDATE_TIME < 3000) { // 3秒内的预测状态才显示
			if (isPTTOn) {
				pttIndicator.textContent = 'PTT: ON';
				pttIndicator.style.color = '#ffff00'; // 黄色表示预测状态
				pttIndicator.style.fontWeight = 'bold';
				pttIndicator.style.textShadow = '0 0 12px #ffff00';
				pttIndicator.style.animation = 'none';
			} else {
				pttIndicator.textContent = 'PTT: OFF';
				pttIndicator.style.color = '#ff8800'; // 橙色表示预测状态
				pttIndicator.style.fontWeight = 'normal';
				pttIndicator.style.textShadow = '0 0 8px #ff8800';
				pttIndicator.style.animation = 'none';
			}
		} else {
			// 预测状态过期，显示为未知状态
			pttIndicator.textContent = 'PTT: ?';
			pttIndicator.style.color = '#888888';
			pttIndicator.style.fontWeight = 'normal';
			pttIndicator.style.textShadow = 'none';
			pttIndicator.style.animation = 'pttBlink 2s infinite';
		}
	}
}

// 定期同步PTT状态显示，确保显示正确
function syncPTTStatusDisplay() {
	const pttIndicator = document.getElementById('ptt-status-indicator');
	if (!pttIndicator) return;

	// 如果设备状态与用户意图不一致，强制查询设备状态
	if (PTT_DEVICE_STATE !== PTT_USER_INTENT) {
		console.log(`🔄 PTT状态同步：用户意图(${PTT_USER_INTENT})与设备状态(${PTT_DEVICE_STATE})不一致，强制查询设备状态`);
		if (poweron && wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
			wsControlTRX.send("getPTT");
		}
	}

	// 始终优先显示设备状态
	updatePTTStatusDisplay(PTT_DEVICE_STATE, true);

	// 每1秒同步一次，更频繁地检查状态一致性
	setTimeout(syncPTTStatusDisplay, 1000);
}

// 启动PTT状态同步
if (typeof window !== 'undefined') {
	window.addEventListener('load', function() {
		setTimeout(syncPTTStatusDisplay, 1000); // 页面加载后1秒开始同步
	});
}

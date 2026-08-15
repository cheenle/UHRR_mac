//Mobile detection///////////////////////////////////////////////////////////////////////////
/* eslint-disable */
const IS_MOBILE = (function (a) {
  return (
	/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows ce|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i
	  .test(
		a.substr(0,4)
	  )
  )
  // @ts-ignore
})(navigator.userAgent || navigator.vendor || window.opera)
/* eslint-enable */

// M3: 统一 WebSocket URL 构造。根据页面协议选择 ws/wss，用 location.host（含端口），
// 避免 'wss://' + href.split('/')[2] 在 http 本地开发下握手失败、
// 以及在带 basic-auth URL 中误带凭据的问题。
function __wsURL(path) {
	var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	return proto + '//' + window.location.host + path;
}

// M2: 统一获取事件源元素。内联 onclick="fn()" 在被调用函数内，Firefox 已不暴露全局
// event；接受显式 evt（推荐 onclick="fn(event)"）并回退 window.event（Chrome/Safari 仍可用），
// 优先 currentTarget（绑定 handler 的元素），再回退 srcElement/target。非破坏性。
function __evtSrc(evt) {
	var e = evt || (typeof window.event !== 'undefined' ? window.event : null);
	if (!e) return null;
	return e.currentTarget || e.srcElement || e.target || null;
}

// WebSocket 状态指示器更新函数
function setWSStatus(elementId, status) {
	var el = document.getElementById(elementId);
	if (!el) return;
	
	// 移除所有状态类
	el.classList.remove('connected', 'connecting', 'error');
	
	// 更新点的样式 - 使用 .status-dot
	var dot = el.querySelector('.status-dot');
	if (dot) {
		dot.classList.remove('connected');
		if (status === 'connected') {
			dot.classList.add('connected');
			el.classList.add('connected');
		} else if (status === 'connecting') {
			el.classList.add('connecting');
		} else if (status === 'error') {
			el.classList.add('error');
		}
	} else {
		// 如果没有点，只更新元素本身的类
		if (status === 'connected') {
			el.classList.add('connected');
		} else if (status === 'connecting') {
			el.classList.add('connecting');
		} else if (status === 'error') {
			el.classList.add('error');
		}
	}
}

//Extra Generals///////////////////////////////////////////////////////////////////////////

function bodyload(){
	disableSFFC();
	checkCookie();
	if(IS_MOBILE)initformobile();
	
	// TX按钮处理由tx_button_optimized.js统一管理
	console.log('主界面加载完成');
	
}

function disableSFFC() { 
    // Get the current page scroll position 
    scrollTop = window.pageYOffset || document.documentElement.scrollTop; 
    scrollLeft = window.pageXOffset || document.documentElement.scrollLeft, 
  
	// if any scroll is attempted, set this to the previous value 
	window.onscroll = function() { 
		window.scrollTo(scrollLeft, scrollTop); 
	}; 
	
	document.addEventListener('contextmenu', event => event.preventDefault());
	document.body.style.overflow = "hidden";
		
}

//Mobiles routines///////////////////////////////////////////////////////////////////////////

	function initformobile(){
		// TX按钮处理已移至tx_button_optimized.js统一管理
		// 这里只处理其他移动端优化
		
		// 注意：不要对TX按钮调用preventLongPressMenu，会干扰tx_button_optimized.js的事件处理
		// TX按钮的长按菜单阻止由tx_button_optimized.js处理
		
		// 处理频谱缩放控件的触摸滚动
		x = document.getElementById('canBFFFT_scale_floor');
		x.addEventListener("touchstart", disableScrolling);
		x.addEventListener("touchend", enableScrolling);
		x = document.getElementById('canBFFFT_scale_multhz');
		x.addEventListener("touchstart", disableScrolling);
		x.addEventListener("touchend", enableScrolling);
		x = document.getElementById('canBFFFT_scale_multdb');
		x.addEventListener("touchstart", disableScrolling);
		x.addEventListener("touchend", enableScrolling);
		x = document.getElementById('canBFFFT_scale_start');
		x.addEventListener("touchstart", disableScrolling);
		x.addEventListener("touchend", enableScrolling);
		
		console.log('移动端初始化完成 - TX按钮由tx_button_optimized.js处理');
	}

    function absorbEvent_(event) {
      var e = event || window.event;
      e.preventDefault && e.preventDefault();
      e.stopPropagation && e.stopPropagation();
      e.cancelBubble = true;
      e.returnValue = false;
      return false;
    }

    function preventLongPressMenu(node) {
      node.ontouchstart = absorbEvent_;
      node.ontouchmove = absorbEvent_;
      node.ontouchend = absorbEvent_;
      node.ontouchcancel = absorbEvent_;
    }
	
	function disableScrolling(){
    var x=window.scrollX;
    var y=window.scrollY;
    window.onscroll=function(){window.scrollTo(x, y);};
	}

	function enableScrolling(){
		window.onscroll=function(){};
	}

//Generals routines///////////////////////////////////////////////////////////////////////////
var poweron = false;
var canvasRXsmeter = "";
var ctxRXsmeter = "";

// 网络状态 EMA 平滑变量
var _netLatency = 0, _netRxKbps = 0, _netTxKbps = 0, _netInit = false;

// 安全设置元素内容的辅助函数（兼容移动端）
function safeSetInnerHTML(elementId, htmlContent) {
	var el = document.getElementById(elementId);
	if (el) {
		el.innerHTML = htmlContent;
	}
	return el;
}

function powertogle(evt)
{
	var src = __evtSrc(evt);
	if (!src) return;
	if(src.src.replace(/^.*[\\\/]/, '')=="poweroff.png"){
		src.src="img/poweron.png";
		document.getElementById("ombre-body").style.display = "block";
		document.getElementById("pop-upspinner").style.display = "block";
		check_connected();
		AudioRX_start();
		AudioTX_start();
		ControlTRX_start();
		checklatency();
		poweron = true;

		canvasRXsmeter = document.getElementById("canRXsmeter");
		if (canvasRXsmeter) {
			ctxRXsmeter = canvasRXsmeter.getContext("2d");
			initRXSmeter();
		}

		button_light_all("div-filtershortcut");
	}
	else{
		src.src="img/poweroff.png";
		AudioRX_stop();
		AudioTX_stop();
		ControlTRX_stop();
		poweron = false;
		button_unlight_all("div-filtershortcut");
		button_unlight_all("div-mode_menu");
		document.getElementById("div-panfft").style.display = "none";
		if (typeof panfft !== 'undefined') {panfft.close();}
	}
}

window.addEventListener('beforeunload', function (e) {
	if(poweron)e.preventDefault();
    if (typeof panfft !== 'undefined') {
		panfft.close();
		e.returnValue = '';
	}
});

function check_connected() {
	// L2: 原实现 WS 连不上时每秒递归永不停；加 poweron 守卫与最大重试上限，
	// 关机后不再空转。
	if (typeof poweron === 'undefined' || !poweron) return;
	check_connected._tries = (check_connected._tries || 0) + 1;
    setTimeout(function () {
        // 放宽条件：只要控制通道和接收通道就绪，即可进入接收状态
        if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN && wsAudioRX && wsAudioRX.readyState === WebSocket.OPEN) {
            document.getElementById("ombre-body").style.display = "none";
            document.getElementById("pop-upspinner").style.display = "none";
            check_connected._tries = 0;
        } else if (poweron && check_connected._tries < 60) {
            check_connected();
        }
    }, 1000);
}

//RX Audio routines///////////////////////////////////////////////////////////////////////////

const RXinstantMeter = document.querySelector('#RXinstant meter');

var wsAudioRX = "";
var AudioRX_context = "";
var AudioRX_source_node = "";
var AudioRX_gain_node = "";
var AudioRX_biquadFilter_node = "";
var AudioRX_analyser = "";
var audiobufferready = false;
var AudioRX_audiobuffer = [];
var AudioRX_sampleRate=16000;

// 线格式 1 字节编解码标签（与后端 audio_interface.py 一致）
var AUDIO_TAG_PCM = 0x00;   // Int16 PCM
var AUDIO_TAG_OPUS = 0x01;  // Opus 帧

var audioSyncMonitor = {
	lastProcessTime: 0,
	bufferCount: 0,
	lagWarning: false
};

// RX Opus 解码器（全局变量）
var AudioRX_OpusDecoder = null;
var AudioRX_opusDecode = false;  // 是否启用 Opus 解码

function AudioRX_start(){
	// V4.9.4 修复：重连时先清理旧的 AudioContext
	// 避免旧的 AudioContext 阻塞新连接
	if (AudioRX_context && AudioRX_context.state !== 'closed') {
		console.log('🔄 关闭旧的 AudioContext...');
		try {
			AudioRX_context.close();
		} catch(e) {
			console.warn('关闭旧 AudioContext 失败:', e);
		}
		AudioRX_context = null;
		AudioRX_source_node = null;
	}
	
	// 避免重复创建连接：仅 OPEN/CONNECTING 跳过；CLOSING/CLOSED 都重建。
	// 原因：ws.close() 后先进入 CLOSING(2)，若用 `!== CLOSED` 判断会误判
	// "已在连接中"而跳过重建 → AudioContext 已被 stop() 关闭、socket 已断，
	// 音频链彻底断裂（电源开关/切后台恢复失效的关键根因之一）。
	if (wsAudioRX && (wsAudioRX.readyState === WebSocket.OPEN || wsAudioRX.readyState === WebSocket.CONNECTING)) {
		console.log('⏭️ AudioRX WebSocket已在连接中或已连接，跳过重复创建');
		return;
	}
	
	setWSStatus('status-rx', 'connecting');
	AudioRX_audiobuffer = [];var lenglitchbuf = 2;
	
	// 读取 Opus 编码复选框状态，同步到 RX 解码
	var encodeElement = document.getElementById("encode");
	if (encodeElement && encodeElement.checked) {
		AudioRX_opusDecode = true;
		console.log('📡 RX Opus 解码已启用');
	}

	wsAudioRX = new WebSocket( __wsURL('/WSaudioRX') );
	wsAudioRX.binaryType = 'arraybuffer';
	wsAudioRX.onopen = wsAudioRXopen;
	wsAudioRX.onclose = wsAudioRXclose;
	wsAudioRX.onerror = wsAudioRXerror;
	// onmessage 将在下方根据 iOS Safari/桌面端分支设置

	// 每秒更新一次码率显示（RX/TX）
	if (!window.__brTimer) {
		window.__rxBytes = 0; window.__txBytes = 0;
		window.__brTimer = setInterval(function(){
			var rxkbps = (window.__rxBytes||0) * 8 / 1000; // Kbps
			var txkbps = (window.__txBytes||0) * 8 / 1000;
			// EMA 平滑 (alpha=0.7, 快速响应)
			if (!_netInit) { _netRxKbps = rxkbps; _netTxKbps = txkbps; }
			else {
				_netRxKbps = _netRxKbps * 0.3 + rxkbps * 0.7;
				_netTxKbps = _netTxKbps * 0.3 + txkbps * 0.7;
			}
			var mode = AudioRX_opusDecode ? "Opus" : "Int16";
			// 桌面端显示
			var brEl = document.getElementById('div-bitrates');
			if (brEl) { brEl.textContent = "RX " + _netRxKbps.toFixed(1) + "K  TX " + _netTxKbps.toFixed(1) + "K  (" + mode + ")"; }
			// 移动端显示 (紧凑)
			var mobEl = document.getElementById('status-bitrates');
			if (mobEl) {
				var v = mobEl.querySelector('.stat-value');
				if (v) v.textContent = "RX" + _netRxKbps.toFixed(0) + "K TX" + _netTxKbps.toFixed(0) + "K";
			}
			window.__rxBytes = 0; window.__txBytes = 0;
		}, 1000);
	}

	// 统一的 Int16 解码函数（带音质优化）
	function decodeInt16Audio(data) {
		try {
			// 检查数据长度是否为 2 的倍数（Int16 需要）
			if (data.byteLength % 2 !== 0) {
				// 奇数字节，截断到最近的偶数长度
				console.warn('音频数据长度异常:', data.byteLength, '字节，截断到', data.byteLength - 1);
				data = data.slice(0, data.byteLength - 1);
			}
			const int16Data = new Int16Array(data);
			const float32Data = new Float32Array(int16Data.length);
			const scale = 1.0 / 32767.0;
			
			// 音质优化：使用三角抖动减少量化噪声
			// 只在低电平时添加抖动，避免影响大信号
			for (let i = 0; i < int16Data.length; i++) {
				let sample = int16Data[i] * scale;
				// 添加微小的三角抖动（约-72dB）改善低电平音质
				if (Math.abs(sample) < 0.1) {
					const dither = (Math.random() - Math.random()) * 0.00025;
					sample += dither;
				}
				float32Data[i] = sample;
			}
			return float32Data;
		} catch (e) {
			console.error('音频解码错误:', e);
			return null;
		}
	}
	
	// Opus 解码函数
	// 重要：解码器使用后端编码时的采样率，而不是 AudioContext 的实际采样率
	// 如果 AudioContext 使用不同采样率（如 iOS Safari 的 44100Hz），需要重采样
	function decodeOpusAudio(data) {
		try {
			// Opus 解码采样率：必须与后端编码器一致（16kHz，对 2.7kHz SSB 语音近无损）
			const opusDecodeRate = 16000;
			// AudioContext 实际采样率
			var contextRate = AudioRX_context ? AudioRX_context.sampleRate : AudioRX_sampleRate;
			
			// 初始化解码器（使用后端编码时的采样率）
			if (!AudioRX_OpusDecoder || AudioRX_OpusDecoder._sampleRate !== opusDecodeRate) {
				AudioRX_OpusDecoder = new OpusDecoder(opusDecodeRate, 1);
				AudioRX_OpusDecoder._sampleRate = opusDecodeRate;
				console.log('✅ RX Opus 解码器已初始化 (' + opusDecodeRate + 'Hz), AudioContext: ' + contextRate + 'Hz');
			}
			
			// 解码得到 Int16 数据（16kHz）
			const int16Data = AudioRX_OpusDecoder.decode(data);
			
			// 如果采样率匹配，直接转换
			if (contextRate === opusDecodeRate) {
				const float32Data = new Float32Array(int16Data.length);
				const scale = 1.0 / 32767.0;
				for (let i = 0; i < int16Data.length; i++) {
					float32Data[i] = int16Data[i] * scale;
				}
				return float32Data;
			}
			
			// 采样率不匹配时进行线性重采样
			// 16kHz → 44.1kHz 或 48kHz
			const ratio = opusDecodeRate / contextRate;
			const outputLength = Math.floor(int16Data.length / ratio);
			const float32Data = new Float32Array(outputLength);
			const scale = 1.0 / 32767.0;
			
			// 优化：使用简化的线性插值
			for (let i = 0; i < outputLength; i++) {
				const srcIndex = i * ratio;
				const srcIndexInt = Math.floor(srcIndex);
				const nextIndex = Math.min(srcIndexInt + 1, int16Data.length - 1);
				const fraction = srcIndex - srcIndexInt;
				
				// 线性插值
				float32Data[i] = (int16Data[srcIndexInt] * (1 - fraction) + int16Data[nextIndex] * fraction) * scale;
			}
			
			return float32Data;
		} catch (e) {
			console.error('Opus 解码错误:', e);
			return null;
		}
	}

	// 统一解码入口：按首字节标签确定性解码（0x00=PCM, 0x01=Opus）。
	// 无标签（旧服务端）时回退到字节数启发式。
	function decodeRxFrame(data) {
		if (!data || data.byteLength < 1) return null;
		var tag = new Uint8Array(data, 0, 1)[0];
		if (tag === AUDIO_TAG_OPUS) {
			return decodeOpusAudio(data.slice(1));
		}
		if (tag === AUDIO_TAG_PCM) {
			return decodeInt16Audio(data.slice(1));
		}
		// 旧服务端无标签回退：当前服务端总是带 1 字节标签，此路径不应触发。
		// 保留仅为兼容旧服务端；触发时告警一次以便排查
		if (!window.__rxUntaggedWarned) {
			window.__rxUntaggedWarned = true;
			console.warn('⚠️ 收到无标签 RX 帧（旧服务端？），回退到大小启发式解码, 长度:', data.byteLength);
		}
		// 旧服务端：<500B 视为 Opus
		if (AudioRX_opusDecode && data.byteLength < 500) {
			return decodeOpusAudio(data);
		}
		return decodeInt16Audio(data);
	}

    // L3: RX 上下文使用 16kHz（与后端 Opus 解码率一致）；TX 上下文才是 48kHz。
    // 原"显式使用 48kHz"注释与实际 AudioRX_sampleRate=16000 不符，易误导维护者。
    // iOS Safari 注意：AudioContext 创建后可能处于 suspended 状态
    // 需要在用户交互后调用 resume()
    AudioRX_context = new AudioContext({ latencyHint: "interactive", sampleRate: AudioRX_sampleRate });
    
    // iOS Safari 关键：记录 AudioContext 初始状态和实际采样率
    console.log('🔊 AudioContext 创建完成, 初始状态:', AudioRX_context.state, ', 实际采样率:', AudioRX_context.sampleRate);
    
    // 检查采样率是否匹配
    if (AudioRX_context.sampleRate !== AudioRX_sampleRate) {
        console.warn('⚠️ AudioContext 采样率不匹配! 请求:', AudioRX_sampleRate, ', 实际:', AudioRX_context.sampleRate);
    }
    
    // iOS Safari：如果处于 suspended 状态，立即尝试恢复
    // 注意：这在用户交互上下文中调用，应该可以成功
    if (AudioRX_context.state === 'suspended') {
        console.log('⚠️ AudioContext 处于 suspended 状态，立即尝试恢复...');
        AudioRX_context.resume().then(() => {
            console.log('✅ AudioContext 已自动恢复');
        }).catch(e => {
            console.log('⚠️ AudioContext 自动恢复失败，等待用户交互:', e);
            window.__audioContextNeedsResume = true;
        });
    }
    
    AudioRX_gain_node = AudioRX_context.createGain();
    AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
    AudioRX_analyser = AudioRX_context.createAnalyser();

    // 检测是否为 iOS Safari
    var isIOSSafari = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    console.log('🔊 检测到 iOS Safari:', isIOSSafari);

    // iOS Safari 优先使用 ScriptProcessor（兼容性更好）
    // 注意：iOS 14.5+ 支持 AudioWorklet，但仍有问题
    var useAudioWorklet = !isIOSSafari;
    
    // 缓冲区深度参数 - 针对 iOS Safari 优化
    // 降低最小缓冲深度以减少静音插入
    const MIN_BUFFER_DEPTH = 1;  // 只要有数据就播放
    const MAX_BUFFER_DEPTH = 20; // 增大最大缓冲，适应网络抖动
    const TARGET_BUFFER_DEPTH = 5; // 目标缓冲深度
    
    (async () => {
        if (useAudioWorklet) {
            try {
                await AudioRX_context.audioWorklet.addModule('rx_worklet_processor.js');
                const rxNode = new AudioWorkletNode(AudioRX_context, 'rx-player');
                AudioRX_source_node = rxNode;
                // 时间水印缓冲（rx_worklet_processor.js）: LAN 调参 V5.8.1
                // 冷启动100ms, 欠载恢复40ms(迟滞), 上限400ms —— 延迟减半，LAN 抖动余量仍充足
                try { rxNode.port.postMessage({ type: 'config', prebufferMs: 100, recoveryMs: 40, maxMs: 400 }); } catch(_){}
                window.__pushRxFrame = function(f32) {
                    rxNode.port.postMessage({ type: 'push', payload: f32 });
                };
                // 桌面端：设置 WebSocket 消息处理器
                wsAudioRX.onmessage = function(msg){
                    if (!window.__rxBytes) window.__rxBytes = 0;
                    if (msg && msg.data && msg.data.byteLength) window.__rxBytes += msg.data.byteLength;
                    // V5.8.4: 记录最后收到 RX 数据的时间（切后台回来半开检测用）
                    window.__rxLastDataTime = Date.now();
                    
                    // 按 1 字节编解码标签确定性解码（0x00=PCM, 0x01=Opus）
                    var float32Data = decodeRxFrame(msg.data);
                    if (float32Data) {
                        window.__pushRxFrame(float32Data);
                    }
                };
                rxNode.connect(AudioRX_biquadFilter_node);
                console.log('✅ AudioWorklet 模式已启用');
            } catch (e) {
                console.warn('⚠️ AudioWorklet 失败，回退到 ScriptProcessor:', e);
                useAudioWorklet = false;
            }
        }
        
        if (!useAudioWorklet) {
            // ScriptProcessor 模式（iOS Safari 兼容）
            // 使用 2048 帧缓冲区（约 42ms @ 48kHz），匹配 Opus 40ms 帧长
            // iOS Safari 要求缓冲区大小必须是 2 的幂次方
            const BUFF_SIZE = 2048;
            AudioRX_source_node = AudioRX_context.createScriptProcessor(BUFF_SIZE, 1, 1);
            
            // 累积缓冲区 - 用于平滑播放
            // 关键修复：暴露到 window 对象，确保 TX 释放时能正确清除
            // V5.8.3: 加入毫秒水印门控（对齐 rx_worklet_processor.js）。
            // iOS 的 WS 解码 + ScriptProcessor 渲染共用主线程：Opus 20ms 帧突发到达
            // + GC/解码抖动会让缓冲瞬间耗尽 → 补静音 = 可闻卡顿。200ms 冷启动缓冲
            // 覆盖 ~4.7 个 2048 量子（42.7ms@48kHz），欠载后只需补到 80ms 即恢复
            // （迟滞），上限 500ms 约束端到端延迟。
            window.__rxAccumulatedBuffer = [];
            window.__rxTotalSamples = 0;
            window.__rxPrebufferMs = 200;   // 冷启动缓冲
            window.__rxRecoveryMs = 80;     // 欠载后重新武装（迟滞）
            window.__rxMaxMs = 500;         // 硬上限
            window.__rxPriming = true;      // 开门标志：true 时积累缓冲
            window.__rxGateMs = window.__rxPrebufferMs; // 当前开门阈值
            var underrunCount = 0;
            
            AudioRX_source_node.onaudioprocess = function(event) {
                var out = event.outputBuffer.getChannelData(0);
                var samplesNeeded = out.length;
                var samplesWritten = 0;
                
                // 从累积缓冲区填充输出（使用 window 暴露的变量）
                var accBuf = window.__rxAccumulatedBuffer;
                var totSamples = window.__rxTotalSamples;
                
                // 开门积累中：缓冲不足则输出静音（不消耗数据）
                if (window.__rxPriming) {
                    var gateSamples = Math.round((window.__rxGateMs / 1000) * AudioRX_context.sampleRate);
                    if (totSamples < gateSamples) {
                        out.fill(0);
                        return;
                    }
                    window.__rxPriming = false;
                }
                
                while (samplesWritten < samplesNeeded && accBuf.length > 0) {
                    var cur = accBuf[0];
                    var samplesToCopy = Math.min(cur.length, samplesNeeded - samplesWritten);
                    
                    // 复制数据到输出
                    out.set(cur.subarray(0, samplesToCopy), samplesWritten);
                    samplesWritten += samplesToCopy;
                    totSamples -= samplesToCopy;
                    
                    if (samplesToCopy >= cur.length) {
                        accBuf.shift();
                    } else {
                        accBuf[0] = cur.subarray(samplesToCopy);
                    }
                }
                
                // 更新 window 变量
                window.__rxTotalSamples = totSamples;
                
                // 如果数据不足，用静音填充剩余部分
                if (samplesWritten < samplesNeeded) {
                    for (var k = samplesWritten; k < samplesNeeded; k++) {
                        out[k] = 0;
                    }
                    // 欠载：重新武装到 recovery 水位（迟滞，避免每次欠载都重新
                    // 攒满完整 prebuffer，快速恢复播放）
                    window.__rxPriming = true;
                    window.__rxGateMs = window.__rxRecoveryMs;
                    underrunCount++;
                    // 每 50 次欠载打印一次日志
                    if (underrunCount % 50 === 0) {
                        console.log('⚠️ 缓冲区欠载，累计:', underrunCount, ', 当前缓冲:', accBuf.length);
                    }
                }
            };
            AudioRX_source_node.connect(AudioRX_biquadFilter_node);
            
            // iOS Safari: 设置 WebSocket 消息处理器
            wsAudioRX.onmessage = function(msg){
                if (!window.__rxBytes) window.__rxBytes = 0;
                if (msg && msg.data && msg.data.byteLength) window.__rxBytes += msg.data.byteLength;
                // V5.8.4: 记录最后收到 RX 数据的时间（切后台回来半开检测用）
                window.__rxLastDataTime = Date.now();
                
                // 按 1 字节编解码标签确定性解码（0x00=PCM, 0x01=Opus）
                var float32Data = decodeRxFrame(msg.data);
                if (float32Data) {
                    // 使用 window 暴露的变量
                    window.__rxAccumulatedBuffer.push(float32Data);
                    window.__rxTotalSamples += float32Data.length;
                    
                    // 缓冲区管理：保持在目标范围内
                    // V5.8.3: 上限改用毫秒水印 __rxMaxMs（默认 500ms），
                    // 替代原硬编码 0.2s；按 AudioContext 实际采样率换算样本数
                    var maxSamples = Math.floor(AudioRX_context.sampleRate * (window.__rxMaxMs / 1000));
                    while (window.__rxTotalSamples > maxSamples && window.__rxAccumulatedBuffer.length > 1) {
                        var removed = window.__rxAccumulatedBuffer.shift();
                        window.__rxTotalSamples -= removed.length;
                    }
                }
            };
            console.log('✅ ScriptProcessor 模式已启用 (iOS Safari), 缓冲区:', BUFF_SIZE);
        }
    })();

    // 创建独立的S表分析器（不受音量控制影响）
    if (typeof AudioRX_smeter_analyser === 'undefined') {
        window.AudioRX_smeter_analyser = AudioRX_context.createAnalyser();
        AudioRX_smeter_analyser.fftSize = 256;
    }
    
    // 音频链：在滤波器之后、增益之前连接S表分析器
    AudioRX_biquadFilter_node.connect(AudioRX_smeter_analyser);
    AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
    AudioRX_gain_node.connect(AudioRX_analyser);
    AudioRX_gain_node.connect( AudioRX_context.destination );
	
	drawBF();
	drawRXvol();
	
	AudioRX_biquadFilter_node.type = "lowshelf";
	AudioRX_biquadFilter_node.frequency.setValueAtTime(22000, AudioRX_context.currentTime);
	AudioRX_biquadFilter_node.gain.setValueAtTime(0, AudioRX_context.currentTime);
	
	AudioRX_SetGAIN();
    
    // iOS Safari 关键：导出恢复函数供移动端调用
    window.resumeAudioContext = async function() {
        if (AudioRX_context && AudioRX_context.state === 'suspended') {
            try {
                await AudioRX_context.resume();
                console.log('✅ AudioContext 已恢复 (iOS Safari)');
                window.__audioContextNeedsResume = false;
                return true;
            } catch(e) {
                console.error('❌ AudioContext 恢复失败:', e);
                return false;
            }
        }
        return true;
    };
    
}

// V5.8.4: 页面从后台切回前台时的整体恢复。
// 切后台时浏览器（尤其 iOS Safari）会 suspend AudioContext、冻结 JS，
// WebSocket 可能变成半开（readyState 仍 OPEN 但数据进黑洞，onclose 不触发）。
// 回来时若无人恢复 → 频谱/声音/S表全停 = “全部卡死”。此函数在
// visibilitychange(visible) 时调用：恢复 AudioContext + 按数据新鲜度重连。
var __RX_STALE_MS = 3000;  // RX 数据超过 3s 未到 → 判定半开/断流
window.resumeAudioAfterBackground = async function() {
    if (typeof poweron === 'undefined' || !poweron) {
        return;  // 关机状态无需恢复
    }
    console.log('🔄 页面回到前台，执行链路恢复...');
    
    // 1) 恢复 RX AudioContext（iOS Safari 切后台必 suspend）
    if (typeof window.resumeAudioContext === 'function') {
        try { await window.resumeAudioContext(); } catch(e) { console.warn('恢复 AudioContext 失败:', e); }
    }
    
    // 2) RX 数据通道：半开/断流检测
    var rxAlive = false;
    if (wsAudioRX && wsAudioRX.readyState === WebSocket.OPEN) {
        if (typeof window.__rxLastDataTime === 'number') {
            rxAlive = (Date.now() - window.__rxLastDataTime) < __RX_STALE_MS;
        } else {
            rxAlive = true;  // 尚无时间戳，视为健康（可能刚开机会话）
        }
    }
    if (!rxAlive) {
        console.warn('🔄 wsAudioRX 判定断流/半开，重建 RX 链路...');
        try {
            if (wsAudioRX && wsAudioRX.readyState !== WebSocket.CLOSED) { wsAudioRX.close(); }
            if (AudioRX_context && AudioRX_context.state !== 'closed') {
                try { AudioRX_context.close(); } catch(e) {}
            }
            AudioRX_context = null;
            AudioRX_source_node = null;
        } catch(e) { console.warn('清理旧 RX 链路失败:', e); }
        AudioRX_start();
    }
    
    // 3) 控制通道：非 OPEN 则重建
    if (!wsControlTRX || wsControlTRX.readyState !== WebSocket.OPEN) {
        console.log('🔄 wsControlTRX 非 OPEN，重建...');
        ControlTRX_start();
    }
    
    // 4) TX 音频通道：非 OPEN 则重建
    if (!wsAudioTX || wsAudioTX.readyState !== WebSocket.OPEN) {
        console.log('🔄 wsAudioTX 非 OPEN，重建...');
        // 先清理旧 MediaHandler（释放麦克风/旧 AudioContext），再重建
        try { if (typeof AudioTX_stop === 'function') AudioTX_stop(); } catch(e) { console.warn('清理 TX 失败:', e); }
        AudioTX_start();
    }
    
    // 5) 清理 RX 缓冲（防止切回瞬间旧数据突涌造成卡顿/延迟）
    if (typeof AudioRX_audiobuffer !== 'undefined') { AudioRX_audiobuffer = []; }
    if (typeof window.__rxAccumulatedBuffer !== 'undefined') {
        window.__rxAccumulatedBuffer = [];
        window.__rxTotalSamples = 0;
        window.__rxPriming = true;
        window.__rxGateMs = window.__rxPrebufferMs;
    }
    if (typeof AudioRX_source_node !== 'undefined' && AudioRX_source_node && AudioRX_source_node.port) {
        try { AudioRX_source_node.port.postMessage({type: 'flush'}); } catch(e) {}
    }
};


function setaudiofilter(evt){
	var src = __evtSrc(evt);
	if (!src) return;
	if(poweron){
		AudioRX_biquadFilter_node.type = src.getAttribute('ft');
		AudioRX_biquadFilter_node.frequency.setValueAtTime(parseInt(src.getAttribute('frq')), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.gain.setValueAtTime(parseInt(src.getAttribute('fg')), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.Q.setValueAtTime(parseInt(src.getAttribute('fq')), AudioRX_context.currentTime);
	}
}

function setcustomaudiofilter(){
	if(poweron){
		AudioRX_biquadFilter_node.type = document.getElementById("customfilter_T").value;
		AudioRX_biquadFilter_node.frequency.setValueAtTime(parseInt(document.getElementById("customfilter_F").value), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.gain.setValueAtTime(parseInt(document.getElementById("customfilter_G").value), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.Q.setValueAtTime(parseInt(document.getElementById("customfilter_Q").value), AudioRX_context.currentTime);
	}
}

function AudioRX_SetGAIN( vol="None" ){
	var cAfElement = document.getElementById("C_af");
	if(vol == "None"){
		volumeRX = cAfElement ? cAfElement.value/100 : 0.5; // 默认值0.5如果元素不存在
		vol = volumeRX;
	}
	if(poweron && AudioRX_gain_node){
		AudioRX_gain_node.gain.setValueAtTime(vol, AudioRX_context.currentTime);
	}
}

function wsAudioRXopen(){
	console.log('DEBUG: WebSocket audio RX connection opened');
	setWSStatus('status-rx', 'connected');
	// V5.8.4: 连接建立即初始化数据时间戳（半开检测基准）
	window.__rxLastDataTime = Date.now();
	
	// 发送 Opus 编码请求到后端
	var encodeElement = document.getElementById("encode");
	if (encodeElement && encodeElement.checked && wsAudioRX && wsAudioRX.readyState === WebSocket.OPEN) {
		var opusRequest = JSON.stringify({
			action: "set_opus_encode",
			enabled: true,
			rate: 16000,  // 16kHz：对 2.7kHz SSB 语音近无损且带宽最低
			frame_dur: 20   // 20ms：Opus 甜点位，延迟减半、音质无损失
		});
		wsAudioRX.send(opusRequest);
		console.log('📡 已请求后端启用 RX Opus 编码 (16kHz / 20ms - 移动端优化)');
	}
}

function wsAudioRXclose(){
	console.log('🔌 WebSocket RX连接已关闭');
	setWSStatus('status-rx', 'error');
	// 自动重连：如果电源仍开启，尝试重连
	if (typeof poweron !== 'undefined' && poweron) {
		console.log('🔄 电源开启中，3秒后尝试重连RX WebSocket...');
		if (window._audioRXReconnectTimer) {
			clearTimeout(window._audioRXReconnectTimer);
		}
		window._audioRXReconnectTimer = setTimeout(function() {
			if (typeof poweron !== 'undefined' && poweron) {
				// V4.9.4 修复：总是调用 AudioRX_start() 重建完整音频链
				// 原因：onmessage 是异步设置的，保存 oldOnMessage 可能是 null
				// 而且 window.__pushRxFrame 引用的 AudioWorklet 可能已失效
				console.log('🔄 重建完整音频链...');
				AudioRX_start();
			}
		}, 3000);
	}
}

function wsAudioRXerror(err){
	console.error('❌ WebSocket RX连接错误:', err);
	setWSStatus('status-rx', 'error');
	// 防抖重连：避免频繁重连
	if (typeof poweron !== 'undefined' && poweron) {
		if (window._audioRXErrorReconnectTimer) {
			clearTimeout(window._audioRXErrorReconnectTimer);
		}
		window._audioRXErrorReconnectTimer = setTimeout(function() {
			if (typeof poweron !== 'undefined' && poweron) {
				// V4.9.4 修复：总是调用 AudioRX_start() 重建完整音频链
				console.log('🔄 错误后重建完整音频链...');
				AudioRX_start();
			}
		}, 1000);
	}
}

function AudioRX_stop()
{
	audiobufferready = false;
	// H16: 停止 RX 时清除频谱/音量递归定时器，避免在已关闭的 AudioContext 上持续运行
	if (__drawBFTimer) { clearTimeout(__drawBFTimer); __drawBFTimer = null; }
	if (__drawRXvolTimer) { clearTimeout(__drawRXvolTimer); __drawRXvolTimer = null; }
	if (wsAudioRX && wsAudioRX.readyState !== WebSocket.CLOSED) {
		wsAudioRX.close();
	}
	if (AudioRX_source_node) {
		AudioRX_source_node.onaudioprocess = null;
	}
	if (AudioRX_context && AudioRX_context.state !== 'closed') {
		AudioRX_context.close();
	}
}

var muteRX=false;
function toggleaudioRX(stat="None"){
	// 只有未传参数时才切换状态，传参数时直接设置
	if(stat === "None"){
		muteRX = !muteRX;
	} else {
		muteRX = stat;
	}
	if(muteRX){
		AudioRX_SetGAIN(0);
		console.log('🔇 RX音频静音');
	}
	else{
		AudioRX_SetGAIN();
		console.log('🔊 RX音频恢复');

		// 清空缓冲区，避免旧数据导致卡顿
		if (typeof AudioRX_audiobuffer !== 'undefined') {
			AudioRX_audiobuffer = [];
		}

		// 清除 AudioWorklet 缓冲区
		if (typeof AudioRX_source_node !== 'undefined' && AudioRX_source_node && AudioRX_source_node.port) {
			try {
				AudioRX_source_node.port.postMessage({type: 'flush'});
			} catch(e) {}
		}

		// 重置累积缓冲区（ScriptProcessor模式）
		if (typeof window.__rxAccumulatedBuffer !== 'undefined') {
			window.__rxAccumulatedBuffer = [];
			window.__rxTotalSamples = 0;
			// V5.8.3: 同步重置水印门控，冷启动重新积累
			window.__rxPriming = true;
			window.__rxGateMs = window.__rxPrebufferMs;
		}
	}
}




canvasBFFFT = document.getElementById("canBFFFT");
ctxFFFT = canvasBFFFT ? canvasBFFFT.getContext("2d") : null;
var Audio_analyser="";
function drawRXFFT(Audio_analyser){
if (!canvasBFFFT || !ctxFFFT) return;
Audio_analyser.fftSize = canvasBFFFT.width;
var arrayFFT = new Float32Array(Audio_analyser.frequencyBinCount);
Audio_analyser.getFloatFrequencyData(arrayFFT);
ctxFFFT.clearRect(0, 0, canvasBFFFT.width, canvasBFFFT.height);
ctxFFFT.fillStyle = 'rgb(0, 0, 0)';
ctxFFFT.fillRect(0, 0, canvasBFFFT.width, canvasBFFFT.height);
var scale_mult = Math.exp(parseInt(document.getElementById("canBFFFT_scale_multdb").value)/100);
var scale_floor = parseInt(document.getElementById("canBFFFT_scale_floor").value)*scale_mult;
var scale_hz = Math.exp(parseInt(document.getElementById("canBFFFT_scale_multhz").value)/100);
var start = (parseInt(document.getElementById("canBFFFT_scale_start").value)*Audio_analyser.frequencyBinCount/100)*scale_hz;
var largeurBarre = (canvasBFFFT.width / Audio_analyser.frequencyBinCount)*scale_hz;
var hauteurBarre;
var x = start;
  for(var i = 0; i < Audio_analyser.frequencyBinCount; i++) {
    hauteurBarre = (arrayFFT[i]*scale_mult + canvasBFFFT.height + scale_floor);
    ctxFFFT.fillStyle = 'rgb(' + Math.floor(hauteurBarre*2+100) + ',50,50)';
    ctxFFFT.fillRect(x*scale_hz, canvasBFFFT.height-hauteurBarre, largeurBarre*scale_hz, hauteurBarre);
    x += largeurBarre;
  }
}

// 移动端可能没有 canvasBFFFT 元素，需要检查
if (canvasBFFFT) {
canvasBFFFT.addEventListener('dblclick', function(evt) {
	document.getElementById("canBFFFT_scale_multdb").value=0;
	document.getElementById("canBFFFT_scale_floor").value=0;
	document.getElementById("canBFFFT_scale_multhz").value=0;
	document.getElementById("canBFFFT_scale_start").value=0;
}, false);

canvasBFFFT_coord = document.getElementById("canvasBFFFT_coord");
canvasBFFFT.addEventListener('mousemove', function(evt) {
	if(Audio_analyser){
		var rect = canvasBFFFT.getBoundingClientRect()
		scaleX = canvasBFFFT.width / rect.width;    // relationship bitmap vs. element for X
		hzperpixel=(AudioRX_sampleRate/2)/rect.width;
		
		var scale_hz = Math.exp(parseInt(document.getElementById("canBFFFT_scale_multhz").value)/100);
		var start = (parseInt(document.getElementById("canBFFFT_scale_start").value)*Audio_analyser.frequencyBinCount/100)*scale_hz;
		
		scaleY = canvasBFFFT.height / rect.height;  // relationship bitmap vs. element for Y
		var scale_mult = Math.exp(parseInt(document.getElementById("canBFFFT_scale_multdb").value)/100);
		var scale_floor = parseInt(document.getElementById("canBFFFT_scale_floor").value);
		
		canvasBFFFT_coord.innerHTML = parseInt(((((evt.clientX - rect.left)/(scale_hz*scale_hz) * scaleX ) - (start/scale_hz))* (AudioRX_sampleRate/2))/canvasBFFFT.width) + 'hz ,-' + parseInt(((evt.clientY - rect.top) * scaleY)/(scale_mult) + (scale_floor))+'dB';
	}
}, false);

canvasBFFFT.addEventListener('mouseenter', function(evt) {
	canvasBFFFT_coord.style.display="block";
}, false);

canvasBFFFT.addEventListener('mouseout', function(evt) {
	canvasBFFFT_coord.style.display="none";
}, false);

canvasBFFFT.addEventListener('click', function(evt) {
	var rect = canvasBFFFT.getBoundingClientRect()
	scaleX = canvasBFFFT.width / rect.width;
	if(document.getElementById("custom_filter_click").hasAttribute('lichecked')){
		AudioRX_biquadFilter_node.type = "bandpass";
		AudioRX_biquadFilter_node.frequency.setValueAtTime(parseInt((((evt.clientX - rect.left) * scaleX) * (AudioRX_sampleRate/2))/canvasBFFFT.width), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.gain.setValueAtTime(-100, AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.Q.setValueAtTime(50, AudioRX_context.currentTime);
	}
	else{document.getElementById("customfilter_F").value=parseInt((((evt.clientX - rect.left) * scaleX) * (AudioRX_sampleRate/2))/canvasBFFFT.width);}
}, false);
} // end if (canvasBFFFT)


function drawRXSPC(Audio_analyser){
canvasBFspc = document.getElementById("canBFSPC");
if (!canvasBFspc) return; // 移动端可能没有此元素
var arraySPC = new Float32Array(Audio_analyser.fftSize);
Audio_analyser.getFloatTimeDomainData(arraySPC);
ctxFwf = canvasBFspc.getContext("2d");
ctxFwf.clearRect(0, 0, canvasBFspc.width, canvasBFspc.height);
ctxFwf.fillStyle = 'rgb(0, 0, 0)';
ctxFwf.fillRect(0, 0, canvasBFspc.width, canvasBFspc.height);
ctxFwf.lineWidth = 2;
ctxFwf.strokeStyle = 'rgb(255, 255, 0)';
ctxFwf.beginPath();
var largeurTranche = canvasBFspc.width * 1.0 / Audio_analyser.fftSize;
var x = 0;

  for(var i = 0; i < Audio_analyser.fftSize; i++) {
    var y = canvasBFspc.height/2 + arraySPC[i] * canvasBFspc.height;
	
    if(i === 0) {
      ctxFwf.moveTo(x, y);
    } else {
      ctxFwf.lineTo(x, y);
    }
    x += largeurTranche;
  }
  ctxFwf.lineTo(canvasBFspc.width, canvasBFspc.height/2);
  ctxFwf.stroke();
}


function drawBF(){
	if(muteRX){Audio_analyser=AudioTX_analyser}else{Audio_analyser=AudioRX_analyser}
	drawRXSPC(Audio_analyser);
	drawRXFFT(Audio_analyser);
	// H16: 保存定时器 id，关机时 clearTimeout，避免在已关闭的 AudioContext 上持续运行
	__drawBFTimer = setTimeout(function(){ drawBF(); }, 200);
}

function drawRXvol(){
	var arraySPC = new Float32Array(AudioRX_analyser.fftSize);
	AudioRX_analyser.getFloatTimeDomainData(arraySPC);
	RXinstantMeter.value = Math.max.apply(null, arraySPC)*100;
	if(RXinstantMeter.value > RXinstantMeter.high){blikcritik("RX-GAIN_control")};
	// H16: 保存定时器 id，关机时清除
	__drawRXvolTimer = setTimeout(function(){ drawRXvol(); }, 300);
}

// H16: 持有递归定时器 id，供关机/停 RX 时清理
var __drawBFTimer = null;
var __drawRXvolTimer = null;

function showRXvol(){
	
}

//ControlTRX routines///////////////////////////////////////////////////////////////////////////
var wsControlTRX = "";

function ControlTRX_start(){
	// 避免重复创建连接：仅 OPEN/CONNECTING 跳过；CLOSING/CLOSED 都重建。
	// （同 AudioRX_start：close() 后的 CLOSING 态不得误判为"已连接"）
	if (wsControlTRX && (wsControlTRX.readyState === WebSocket.OPEN || wsControlTRX.readyState === WebSocket.CONNECTING)) {
		console.log('⏭️ WebSocket已在连接中或已连接，跳过重复创建');
		return;
	}
	
	setWSStatus('status-ctrl', 'connecting');
	const wsUrl = __wsURL('/WSCTRX');
	console.log('🔌 尝试连接WebSocket:', wsUrl);
	wsControlTRX = new WebSocket( wsUrl );
	wsControlTRX.onopen = wsControlTRXopen;
	wsControlTRX.onclose = wsControlTRXclose;
	wsControlTRX.onerror = wsControlTRXerror;
	wsControlTRX.onmessage = wsControlTRXcrtol;
	
	// 定期查询PTT状态，确保同步
	if (window.pttQueryInterval) {
		clearInterval(window.pttQueryInterval);
	}
	window.pttQueryInterval = setInterval(() => {
		if (wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
			wsControlTRX.send("getPTT");
		}
	}, 5000); // 每5秒查询一次，避免过于频繁
}

var SignalLevel=0;
function wsControlTRXcrtol( msg ){
	var data = String(msg.data);
	var colonIndex = data.indexOf(':');
	var action = colonIndex > 0 ? data.substring(0, colonIndex) : data;
	var param = colonIndex > 0 ? data.substring(colonIndex + 1) : '';
	
	if(action == "PONG"){
		// 半开连接检测：收到 PONG 说明控制通道往返正常，清除等待超时
		if (window._pongTimer) {
			clearTimeout(window._pongTimer);
			window._pongTimer = null;
		}
		showlatency();
	}
	else if(action == "getFreq"){showTRXfreq(param);TRXfrequency=parseInt(param);if (typeof panfft !== 'undefined') {panfft.setcenterfrequency(param);}}
	else if(action == "getMode"){showTRXmode(param);}
	else if(action == "getRFGain"){if (typeof window.updateRFGainUI === 'function') window.updateRFGainUI(param);}
	else if(action == "getAGC"){if (typeof window.updateAGCUI === 'function') window.updateAGCUI(param === "true");}
	else if(action == "getSignalLevel"){SignalLevel=param;drawRXSmeter();}
	else if(action == "getPTT"){updatePTTStatus(param === "true");}
	else if(action == "pttError"){
		console.error('🚨 PTT 错误:', param);
		if(param === "tot_timeout"){
			// TOT 超时：服务端已强制把电台收回 RX，不要把 UI 点亮成发射态。
			// 后续的 getPTT:false 广播会同步真实状态，这里只提示操作员。
			alert("⏰ 发射超时保护已触发，已自动停止发射（达到最大发射时长）。");
		} else {
			// release_failed: 服务端释放失败，电台可能仍在发射，后台正在自动重试。
			// 强制 UI 显示发射态并告警，状态恢复后会有 getPTT:false 同步回来。
			updatePTTStatus(true);
			alert("⚠️ PTT 释放失败，电台可能仍在发射！\n服务端正在自动重试收回，请检查电台/CAT 连接。");
		}
	}
	else if(action == "panfft"){document.getElementById("div-panfft").style.display = "block";}
	else if(action == "cq"){
		console.log('📻 收到CQ消息:', param);
		if(param === "complete"){
			console.log('📻 CQ播放完成，调用onCQComplete');
			onCQComplete();
		}
	}
	// WDSP 状态响应 (支持多端同步)
	else if(action == "wdspStatus" || action == "getWDSPStatus"){
        console.log('🔧 收到 WDSP 状态消息:', param ? param.substring(0, 100) + '...' : 'empty');
        if(typeof handleWDSPStatus === 'function') {
            console.log('🔧 调用 handleWDSPStatus');
            handleWDSPStatus(param);
        } else {
            console.warn('⚠️ handleWDSPStatus 函数未定义');
        }
    }
    else if(action == "setWDSPEnabled"){
        console.log('🔧 WDSP 状态:', param);
        // 更新 UI
        if(typeof window.updateWDSPEnabledUI === 'function') {
            window.updateWDSPEnabledUI(param === 'enabled' || param === 'true');
        }
        // 请求最新状态以同步 UI
        if(wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
            wsControlTRX.send("getWDSPStatus:");
        }
    }
    else if(action == "setWDSPNR2Level"){
        console.log('🔧 WDSP NR2 Level 广播:', param);
        if(typeof window.updateNR2LevelUI === 'function') {
            console.log('🔧 调用 window.updateNR2LevelUI');
            window.updateNR2LevelUI(parseInt(param));
        } else {
            console.warn('⚠️ window.updateNR2LevelUI 函数未定义');
        }
    }
    else if(action == "setWDSPNR2GainMethod"){
        console.log('🔧 WDSP NR2 GainMethod:', param);
    }
    else if(action == "setWDSPNR2NpeMethod"){
        console.log('🔧 WDSP NR2 NpeMethod:', param);
    }
    else if(action == "setWDSPNR2AeRun"){
        console.log('🔧 WDSP NR2 AeRun:', param);
    }
    else if(action == "setWDSPNB"){
        console.log('🔧 WDSP NB 广播:', param);
        if(typeof window.updateNBUI === 'function') {
            console.log('🔧 调用 window.updateNBUI');
            window.updateNBUI(param === 'true');
        } else {
            console.warn('⚠️ window.updateNBUI 函数未定义');
        }
    }
    else if(action == "setWDSPANF"){
        console.log('🔧 WDSP ANF:', param);
        if(typeof window.updateANFUI === 'function') {
            window.updateANFUI(param === 'true');
        }
    }
    else if(action == "setWDSPAGCMode" || action == "setWDSPAGC"){
        // console.log('🔧 WDSP AGC:', param);
        if(typeof window.updateAGCUI === 'function') {
            window.updateAGCUI(parseInt(param));
        }
    }
    else if(action == "setWDSPBandpass"){
        console.log('🔧 WDSP Bandpass:', param);
        if(typeof window.updateBandpassUI === 'function') {
            const parts = param.split(',');
            if(parts.length === 2) {
                window.updateBandpassUI(parseFloat(parts[0]), parseFloat(parts[1]));
            }
        }
    }
    // 录音状态消息处理
    else if(action == "recordingStatus"){
        console.log('🔴 录音状态:', param);
        if(typeof window.handleRecordingStatus === 'function') {
            window.handleRecordingStatus(param);
        }
    }
    else if(action == "recordingSaved"){
        console.log('✅ 录音已保存:', param);
        if(typeof window.handleRecordingSaved === 'function') {
            window.handleRecordingSaved(param);
        }
    }
}

function ControlTRX_stop()
{
	wsControlTRX.close();
	// 清理PTT状态查询定时器
	if (window.pttQueryInterval) {
		clearInterval(window.pttQueryInterval);
		window.pttQueryInterval = null;
	}
	// 重置PTT状态显示
	updatePTTStatus(false);
} 

function ControlTRX_getFreq(){
	if (wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("getFreq");}
}

function wsControlTRXopen(){
	console.log('✅ WebSocket控制连接成功建立');
	setWSStatus('status-ctrl', 'connected');
	wsControlTRX.send("getFreq:");
	wsControlTRX.send("getMode:");
	// 连接建立后立即查询PTT状态
	wsControlTRX.send("getPTT:");
	updatePTTStatus(false);
	// 查询 WDSP 状态以同步当前设置
	wsControlTRX.send("getWDSPStatus:");
	
	// 启动定期PTT状态检查（每5秒一次，确保状态准确性）
	if (window.pttStatusCheckInterval) {
		clearInterval(window.pttStatusCheckInterval);
	}
	window.pttStatusCheckInterval = setInterval(() => {
		if (poweron && wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
			wsControlTRX.send("getPTT:");
		}
	}, 5000); // 每5秒检查一次PTT状态
}

function wsControlTRXclose(){
	console.log('🔌 WebSocket控制连接已关闭');
	setWSStatus('status-ctrl', 'error');
	// 清理PTT状态查询定时器
	if (window.pttQueryInterval) {
		clearInterval(window.pttQueryInterval);
		window.pttQueryInterval = null;
	}
	// 清理定期状态检查定时器
	if (window.pttStatusCheckInterval) {
		clearInterval(window.pttStatusCheckInterval);
		window.pttStatusCheckInterval = null;
	}
	// 重置PTT状态显示
	updatePTTStatus(false);
	
	// 自动重连：如果电源仍开启，尝试重连
	if (typeof poweron !== 'undefined' && poweron) {
		console.log('🔄 电源开启中，3秒后尝试重连控制WebSocket...');
		if (window._controlReconnectTimer) {
			clearTimeout(window._controlReconnectTimer);
		}
		window._controlReconnectTimer = setTimeout(function() {
			if (typeof poweron !== 'undefined' && poweron) {
				console.log('🔄 正在重连控制WebSocket...');
				ControlTRX_start();
			}
		}, 3000);
	}
}

function wsControlTRXerror(err){
	console.error('❌ WebSocket控制连接错误:', err);
	setWSStatus('status-ctrl', 'error');
	// 防抖重连：避免频繁重连
	if (typeof poweron !== 'undefined' && poweron) {
		if (window._controlErrorReconnectTimer) {
			clearTimeout(window._controlErrorReconnectTimer);
		}
		window._controlErrorReconnectTimer = setTimeout(function() {
			if (typeof poweron !== 'undefined' && poweron) {
				if (!wsControlTRX || wsControlTRX.readyState === WebSocket.CLOSED) {
					console.log('🔄 错误后重连控制WebSocket...');
					ControlTRX_start();
				}
			}
		}, 1000);
	}
}

var startTime;
// 半开连接检测：每次 PING 发出后启动超时计时器，PONG_TIMEOUT 内未收到 PONG
// 判定为 TCP 半开死连接（readyState 仍是 OPEN 但数据进黑洞），强制重连。
// 这是"按了释放后还在发射"的根因防护：半开时 setPTT:false 会静默丢失。
var PONG_TIMEOUT_MS = 6000;
window._pongTimer = null;

// 半开连接确诊后的安全处理：强制关闭控制通道触发重连，并尽力通过 TX
// 音频通道（独立 socket，可能仍通）补发 s: 命令收回发射。
function onControlConnectionDead(reason) {
	console.error('🚨 控制连接判定为半开/死亡:', reason, '— 强制重连并尝试收回发射');
	// 1) 若本地认为正在发射，立即尝试通过 TX 音频通道补发 s:（关 PTT 的独立路径）
	try {
		if (typeof TXState !== 'undefined' && TXState && TXState.isPressed) {
			if (typeof wsAudioTX !== 'undefined' && wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
				wsAudioTX.send("s:");
				console.warn('🛑 已通过 TX 音频通道补发 s: 收回发射');
			}
			// 强制重置本地 TX 状态，避免 UI 残留发射态
			if (typeof TXControl === 'function') { TXControl('stop'); }
		}
	} catch (e) { console.warn('补发 s: 失败:', e); }
	// 2) 强制关闭控制通道，触发 onclose → 自动重连
	try {
		if (wsControlTRX && wsControlTRX.readyState !== WebSocket.CLOSED) {
			wsControlTRX.close();
		}
	} catch (e) { /* ignore */ }
	setWSStatus('status-ctrl', 'error');
}

function checklatency() {
	setTimeout(function () {
		// 检查 WebSocket 状态，断开时自动重连
		if (typeof poweron !== 'undefined' && poweron) {
			if (wsControlTRX) {
				if (wsControlTRX.readyState === WebSocket.OPEN) {
					startTime = Date.now();
					wsControlTRX.send("PING");
					// 启动 PONG 超时计时器：到点仍未收到 PONG → 半开死连接
					if (window._pongTimer) { clearTimeout(window._pongTimer); }
					window._pongTimer = setTimeout(function () {
						window._pongTimer = null;
						// 二次确认：若期间连接已被关闭/重连则忽略
						if (poweron && wsControlTRX && wsControlTRX.readyState === WebSocket.OPEN) {
							onControlConnectionDead('PONG 超时 ' + PONG_TIMEOUT_MS + 'ms');
						}
					}, PONG_TIMEOUT_MS);
				} else if (wsControlTRX.readyState === WebSocket.CLOSED) {
					// WebSocket 已关闭但电源仍开启，尝试重连
					console.log('🔄 心跳检测：WebSocket已关闭，尝试重连...');
					ControlTRX_start();
				}
				// CONNECTING(0) 或 CLOSING(2) 状态不做处理，等待状态变化
			} else {
				// wsControlTRX 未定义，尝试重连
				console.log('🔄 心跳检测：WebSocket未定义，尝试重连...');
				ControlTRX_start();
			}
			checklatency();
		}
	}, 2000);
}

function showlatency(){
	var raw = Date.now() - startTime;
	// EMA 平滑 (alpha=0.3)
	if (!_netInit) { _netLatency = raw; _netInit = true; }
	else { _netLatency = _netLatency * 0.3 + raw * 0.7; }
	var ms = Math.round(_netLatency);
	// 延迟质量分级
	var cls = ms < 50 ? "latency-good" : (ms < 150 ? "latency-warn" : "latency-bad");
	// 桌面端显示
	var el = document.getElementById("div-latencymeter");
	if (el) { el.textContent = ms + "ms"; el.className = "network-stat " + cls; }
	// 移动端显示
	var mobEl = document.getElementById("status-latency");
	if (mobEl) {
		var v = mobEl.querySelector(".stat-value");
		if (v) v.textContent = ms + "ms";
		mobEl.className = mobEl.className.replace(/\blatency-\w+\b/g, "");
		mobEl.classList.add(cls);
		var dot = mobEl.querySelector(".status-dot");
		if (dot) { dot.className = dot.className.replace(/\blatency-\w+\b/g, ""); dot.classList.add(cls); }
	}
}

function get_digit_freq(){
	return parseInt(
		document.getElementById("cmhz").innerHTML+
		document.getElementById("dmhz").innerHTML+
		document.getElementById("umhz").innerHTML+
		document.getElementById("ckhz").innerHTML+
		document.getElementById("dkhz").innerHTML+
		document.getElementById("ukhz").innerHTML+
		document.getElementById("chz").innerHTML+
		document.getElementById("dhz").innerHTML+
		document.getElementById("uhz").innerHTML
		);
}

freq_digit_selected="";
function freq_digit_scroll(evt) {
	if (poweron) {
		var e = evt || (typeof window.event !== 'undefined' ? window.event : null);
		if (!e || typeof e.deltaY === 'undefined') return;
		if(e.deltaY>0){toadd=-1;}else{toadd=1;}
		freq=get_digit_freq()+(freq_digit_selected.getAttribute('v')*toadd);
		if(freq>0){showTRXfreq(freq);sendTRXfreq();}
	}
}

function select_digit(evt) {
	var src = __evtSrc(evt);
	if (src) freq_digit_selected = src;
}

function clear_select_digit() {
	freq_digit_selected="";
}

function rotatefreq(evt){
	if (poweron) {
		var src = __evtSrc(evt);
		if (!src) return;
		freq=get_digit_freq()+parseInt(src.getAttribute('v'));
		if(freq>0){showTRXfreq(freq);sendTRXfreq();}
	}
}

function showTRXfreq(freq){
	var numericFreq = parseInt(freq, 10);
	if (!isNaN(numericFreq)) {
		TRXfrequency = numericFreq;
		if (typeof mobileState !== 'undefined') {
			mobileState.currentFrequency = numericFreq;
		}
	}
	freq=freq.toString();
	while (freq.length < 9){freq="0"+freq;}
	
	// 桌面版元素（cmhz, dmhz 等）
	var cmhz = document.getElementById("cmhz");
	if (cmhz) {
		cmhz.innerHTML=freq.substring(0, 1);
		var dmhz = document.getElementById("dmhz");
		if (dmhz) dmhz.innerHTML=freq.substring(1, 2);
		var umhz = document.getElementById("umhz");
		if (umhz) umhz.innerHTML=freq.substring(2, 3);
		var ckhz = document.getElementById("ckhz");
		if (ckhz) ckhz.innerHTML=freq.substring(3, 4);
		var dkhz = document.getElementById("dkhz");
		if (dkhz) dkhz.innerHTML=freq.substring(4, 5);
		var ukhz = document.getElementById("ukhz");
		if (ukhz) ukhz.innerHTML=freq.substring(5, 6);
		var chz = document.getElementById("chz");
		if (chz) chz.innerHTML=freq.substring(6, 7);
		var dhz = document.getElementById("dhz");
		if (dhz) dhz.innerHTML=freq.substring(7, 8);
		var uhz = document.getElementById("uhz");
		if (uhz) uhz.innerHTML=freq.substring(8, 9);
	}
	
	// 移动版元素 - 新版 5 位 kHz 格式（mobile_modern.html）
	var freq10mhz = document.getElementById("freq-10mhz");
	if (freq10mhz) {
		// kHz 格式：显示 5 位（如 07053 = 7053 kHz）
		var freqKhz = Math.floor(parseInt(freq) / 1000);
		var freqStr = freqKhz.toString().padStart(5, '0');
		freq10mhz.innerHTML = freqStr[0];
		var freq1mhz = document.getElementById("freq-1mhz");
		if (freq1mhz) freq1mhz.innerHTML = freqStr[1];
		var freq100khz = document.getElementById("freq-100khz");
		if (freq100khz) freq100khz.innerHTML = freqStr[2];
		var freq10khz = document.getElementById("freq-10khz");
		if (freq10khz) freq10khz.innerHTML = freqStr[3];
		var freq1khz = document.getElementById("freq-1khz");
		if (freq1khz) freq1khz.innerHTML = freqStr[4];
	}
	
	// 移动版元素 - 旧版 9 位 Hz 格式（兼容其他移动界面）
	var freq100mhz = document.getElementById("freq-100mhz");
	if (freq100mhz) {
		freq100mhz.innerHTML=freq.substring(0, 1);
		var freq10mhz_old = document.getElementById("freq-10mhz");
		if (freq10mhz_old && !freq10mhz) freq10mhz_old.innerHTML=freq.substring(1, 2);
		var freq1mhz_old = document.getElementById("freq-1mhz");
		if (freq1mhz_old && !document.getElementById("freq-1mhz")) freq1mhz_old.innerHTML=freq.substring(2, 3);
		var freq100khz_old = document.getElementById("freq-100khz");
		var freq10khz_old = document.getElementById("freq-10khz");
		var freq1khz_old = document.getElementById("freq-1khz");
		var freq100hz = document.getElementById("freq-100hz");
		if (freq100hz) freq100hz.innerHTML=freq.substring(6, 7);
		var freq10hz = document.getElementById("freq-10hz");
		if (freq10hz) freq10hz.innerHTML=freq.substring(7, 8);
		var freq1hz = document.getElementById("freq-1hz");
		if (freq1hz) freq1hz.innerHTML=freq.substring(8, 9);
	}

	if (typeof updateBandButtonLabel === 'function' && typeof getCurrentMobileBand === 'function') {
		updateBandButtonLabel(getCurrentMobileBand());
	}
}

// 全局频率更新函数
function updateFrequency(freq) {
	// ATU自动调谐模块已移除
}

function sendTRXfreq(freq=0){
	if(!freq){freq=get_digit_freq();}
		if (wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("setFreq:"+freq);}
}

// PTT 状态管理已提取到 modules/ptt_manager.js


function showTRXmode(mode){
	var cleanMode = String(mode || '').trim().toUpperCase();
	// 桌面版元素
	setAttr("div-mode_menu",cleanMode);
	
	// 移动版状态同步（mobile_modern.js 依赖该状态决定下一档模式）
	if (typeof mobileState !== 'undefined') {
		mobileState.currentMode = cleanMode;
	}
	
	// 移动版元素
	var modeIndicator = document.getElementById("mode-indicator");
	if (modeIndicator) {
		modeIndicator.innerHTML = cleanMode;
	}
	
	// 移动版模式按钮
	if (typeof updateModeButtonLabel === 'function') {
		updateModeButtonLabel(cleanMode);
	} else {
		var modeBtn = document.getElementById("mode-btn");
		if (modeBtn) {
			modeBtn.innerHTML = cleanMode;
		}
	}
}

function sendTRXmode(evt){
	var src = __evtSrc(evt);
	if (src && wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("setMode:"+src.innerHTML);}
}

function recall_hambands(evt){
	var src = __evtSrc(evt);
	if (src && wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("setFreq:"+src.getAttribute('v'));}
}

function initRXSmeter(){
	ctxRXsmeter.beginPath();
	ctxRXsmeter.lineWidth = 2;
	ctxRXsmeter.strokeStyle = '#fffb16';
	ctxRXsmeter.moveTo(SP[0], 0);
	ctxRXsmeter.lineTo(SP[0], 50);
	ctxRXsmeter.stroke();
	document.getElementById("div-smeterdigitRX").innerHTML="S0";
}

var SP = {0:0,1:25,2:37,3:50,4:62,5:73,6:84,7:98,8:110,9:123,5:134,10:144,15:154,20:164,25:172,30:180,35:191,40:202,45:212,50:221,55:231,60:240};
var RIG_LEVEL_STRENGTH = {0:-54,1:-48,2:-42,3:-36,4:-30,5:-24,6:-18,7:-12,8:-6,9:0,5:5,10:10,15:15,20:20,25:25,30:30,35:35,40:40,45:45,50:50,55:55,60:60};
function drawRXSmeter() {
	// 添加canvas元素存在性检查以兼容移动端
	if (!canvasRXsmeter || !ctxRXsmeter) {
		// 移动端：调用mobile_modern.js中的updateSMeter函数
		if (typeof updateSMeter === 'function') {
			console.log('📱 移动端S表更新:', 'SignalLevel=' + SignalLevel);
			updateSMeter(SignalLevel);
		} else {
			console.warn('⚠️ updateSMeter函数未定义');
		}
		return;
	}
	
	if(typeof(RIG_LEVEL_STRENGTH[SignalLevel])!="undefined"){  
		ctxRXsmeter.beginPath();
		ctxRXsmeter.lineWidth = 2;
		ctxRXsmeter.moveTo(SP[SignalLevel], 0);
		ctxRXsmeter.lineTo(SP[SignalLevel], 50);
		ctxRXsmeter.clearRect(0, 0, 250, 50);
		ctxRXsmeter.strokeStyle = '#fffb16';	
		ctxRXsmeter.stroke();
		
		sq=document.getElementById("SQUELCH").value*2.5;
		ctxRXsmeter.beginPath();
		ctxRXsmeter.lineWidth = 2;
		ctxRXsmeter.strokeStyle = '#deded5';
		ctxRXsmeter.moveTo(sq, 0);
		ctxRXsmeter.lineTo(sq, 50);
		ctxRXsmeter.stroke();
		
		var res = "S9";
		if(SignalLevel > 9){
			res = "S9+" + SignalLevel; 
		}
		else{res = "S" + SignalLevel;}
		document.getElementById("div-smeterdigitRX").innerHTML=res+" ("+RIG_LEVEL_STRENGTH[SignalLevel]+"dB)";
		
		if(SP[SignalLevel]>=sq && !muteRX){AudioRX_SetGAIN();}
		else{AudioRX_SetGAIN(0);}
	}
	else{
		document.getElementById("div-smeterdigitRX").innerHTML="";
		ctxRXsmeter.clearRect(0, 0, 250, 50);	
		ctxRXsmeter.stroke();
		}
}

// TX按钮处理已移至tx_button_optimized.js


// TX按钮处理已移至tx_button_optimized.js

// Cookie/设置管理已提取到 modules/settings_manager.js


//Cosmetics
function changeinputfreqstyle(e){
	var item=document.getElementById("freq_disp_input_text");
	var digit_elements = document.getElementsByClassName('freq_digit');
	ids="inline-block";
	desd="none";
	
	if (e.keyCode == 13) {
			freq=item.value.toString();
			showTRXfreq(freq);
			sendTRXfreq();
			ids="none";
			desd="inline-block";
	}
	item.style.display = ids;
	for (var i in digit_elements) {
		if (digit_elements.hasOwnProperty(i)) {
			digit_elements[i].style.display = desd;
		}
	}
}

function validateNumber(evt) {
    var e = evt || window.event;
    var key = e.keyCode || e.which;
	var item=document.getElementById("freq_disp_input_text");

	if(key == 77){item.value*=1000000;}
	if(key == 75){item.value*=1000;}

    if (!e.shiftKey && !e.altKey && !e.ctrlKey &&
    // numbers   
    key >= 48 && key <= 57 ||
    // Numeric keypad
    key >= 96 && key <= 105 ||
    // Backspace and Tab and Enter
    key == 8 || key == 9 || key == 13 ||
    // Home and End
    key == 35 || key == 36 ||
    // left and right arrows
    key == 37 || key == 39 ||
    // Del and Ins
    key == 46 || key == 45) {
        // input is VALID
    }
    else {
        // input is INVALID
        e.returnValue = false;
        if (e.preventDefault) e.preventDefault();
    }
}

function get_actualmode()
{
	var items = document.getElementById("div-mode_menu").getElementsByTagName("li");
	var mode = ""
	for (var i = 0; i < items.length; ++i) {
		if(items[i].hasAttribute('lichecked') ){
			mode = items[i].innerHTML;
		}
	}
	return mode
}

function button_pressed(item, evt)
{
	if(!item){item=__evtSrc(evt);}
	if(!item){return;}
	item.classList.remove('button_unpressed');
	item.classList.add('button_pressed');
	button_light(item);
}

function button_unpressed(item, evt)
{
	// 安全检查：如果没有item且event也不存在，直接返回
	if(!item){
		item=__evtSrc(evt);
		if(!item){return;}
	}
	item.classList.remove('button_green');
	item.classList.remove('button_pressed');
	item.classList.add('button_unpressed');
}

function button_unlight_all(iddiv){
	var items = document.getElementById(iddiv).getElementsByTagName("li");
	for (var i = 0; i < items.length; ++i) {
		items[i].classList.remove('button_green');	
	}
}

function button_light_all(iddiv)
{
	var items = document.getElementById(iddiv).getElementsByTagName("li");
	for (var i = 0; i < items.length; ++i) {
		if(items[i].hasAttribute('lichecked')){
			items[i].classList.add('button_green');
		}
	}
}


function button_light(item,color="G", evt)
{
	if(!item){item=__evtSrc(evt);if(!item){return;}}
	if(color=="G"){
		if(poweron){item.classList.add('button_green');}
		else{item.classList.remove('button_green');}
	}
	else if(color=="R"){
		if(poweron){item.classList.add('button_red');}
		else{item.classList.remove('button_red');}
	}
	else if(color=="Z"){
		item.classList.remove('button_red');
	}
}

function set_css_li_in_ul(items, tag=true)
{
	for (var i = 0; i < items.length; ++i) {
		if(items[i].hasAttribute('lichecked') && tag){
			button_pressed(items[i]);
		}else{
			button_unpressed(items[i]);
		}
	}
}

function togle_li(evt)
{
	var src = __evtSrc(evt);
	if (!src) return;
	var items = src.parentNode.getElementsByTagName("li");
	for (var i = 0; i < items.length; ++i) {
		items[i].removeAttribute('lichecked');
	}
	src.setAttribute('lichecked',"");
	set_css_li_in_ul(items);
}

function setAttr(div,mode){
	var items = document.getElementById(div).getElementsByTagName("li");
	for (var i = 0; i < items.length; ++i) {
		items[i].removeAttribute('lichecked');	
		if(items[i].innerHTML==mode){items[i].setAttribute('lichecked',"")}
		if(items[i].getAttribute('v')==mode){items[i].setAttribute('lichecked',"")}
	}
	set_css_li_in_ul(items);
}

function blikcritik(elemtID){
	var el = document.getElementById(elemtID);
	if (!el) {
		console.warn('⚠️ blikcritik: 元素不存在:', elemtID);
		return;
	}
	el.classList.add("blink");
	el.style.color="red";
	setTimeout(function(){ 
		el.classList.remove("blink"); 
		el.style.color="white";
	}, 3000);
}

//TX Audio routines///////////////////////////////////////////////////////////////////////////


// 线性重采样到 48kHz（与 mrrc_ft710/ft710_main.js 一致）。
// TX 编码固定 48kHz；麦克风 AudioContext 若为 44.1k 等其它率则重采样。
function resampleFloat32To48k(input, inRate) {
	if (!input || input.length === 0 || Math.abs(inRate - 48000) < 1) {
		return input;
	}
	var outLen = Math.max(1, Math.round((input.length * 48000) / inRate));
	var out = new Float32Array(outLen);
	var step = inRate / 48000;
	for (var i = 0; i < outLen; i++) {
		var pos = i * step;
		var idx = Math.floor(pos);
		var frac = pos - idx;
		var a = input[Math.min(idx, input.length - 1)];
		var b = input[Math.min(idx + 1, input.length - 1)];
		out[i] = a + (b - a) * frac;
	}
	return out;
}



// Opus WASM 运行时已提取到 modules/opus_wasm.js


// Opus 编解码器已提取到 modules/opus_codec.js


var OpusEncoderProcessor = function( wsh )
{
    this.wsh = wsh;
    this.bufferSize = 2048; // 优化：从4096减至2048，降低延迟约42ms
    // ========== 48kHz 全带宽 TX（对齐 mrrc_ft710）==========
    // 不再 48k→16k 降采样，直接编码 mic 原生率，保留全带宽
    this.downSample = 1;
    // Opus 编码参数（对齐 ft710：高音质优先）
    // 帧时长: 20ms（WebRTC 推荐）
    // 采样率: 48kHz 全带宽
    // 应用类型: 2048 = OPUS_APPLICATION_VOIP（语音优化）
    // 码率/复杂度: 见 modules/opus_codec.js（64kbps CBR）
    this.opusFrameDur = 20; // msec
    this.opusRate = 48000;  // Hz - 48kHz 全带宽
    this.i16arr = new Int16Array( Math.floor(this.bufferSize / this.downSample) );
    this.f32arr = new Float32Array( Math.floor(this.bufferSize / this.downSample) );
    this.opusEncoder = new OpusEncoder( this.opusRate, 1, 2048, this.opusFrameDur );
    console.log('🎵 TX Opus 编码器初始化: 48kHz/20ms, complexity=8, bitrate=64kbps CBR, frame=' + (this.opusRate * this.opusFrameDur / 1000));
}


OpusEncoderProcessor.prototype.onAudioProcess = function( e )
{
	// ScriptProcessor 回退路径入口；核心逻辑在 pushSamples（与 AudioWorklet 共用）
	this.pushSamples(e.inputBuffer.getChannelData(0));
}

// V5.4: TX 采集核心 — 从 AudioWorklet（首选）或 ScriptProcessor（回退）接收
// AudioContext 原生采样率的单声道 Float32Array，做噪声门/重采样/Opus 编码发送。
OpusEncoderProcessor.prototype.pushSamples = function( data )
{
	this.instant = 0.0;
	const that = this;

	// ====== Noise Gate (RagChew 模式) ======
	// 在音频链末端，基于信号电平控制噪声门增益
	if (isRagchewMode && AudioTX_noiseGate) {
		var gateData = data;
		var rms = 0;
		for (var g = 0; g < gateData.length; g++) {
			rms += gateData[g] * gateData[g];
		}
		rms = Math.sqrt(rms / gateData.length);

		// 噪声门阈值: -50dB (~0.003 线性)
		var gateThreshold = 0.003;
		var gateAttack = 0.01;  // 10ms 快速打开
		var gateRelease = 0.3;  // 300ms 缓慢关闭，避免断字

		if (!window._gateState) { window._gateState = 1; window._gateHold = 0; }

		if (rms > gateThreshold) {
			// 信号高于阈值：打开门
			window._gateState = 1;
			window._gateHold = Date.now();
		} else if (window._gateHold && (Date.now() - window._gateHold > gateRelease * 1000)) {
			// 持续低于阈值超过释放时间：关门
			window._gateState = 0;
		}

		var targetGain = window._gateState > 0 ? 1.0 : 0.0;
		if (Math.abs(AudioTX_noiseGate.gain.value - targetGain) > 0.01) {
			AudioTX_noiseGate.gain.linearRampToValueAtTime(targetGain, AudioTX_noiseGate.context.currentTime + gateAttack);
		}
	}

	    if( isRecording )
    {

	// ========== 48kHz 全带宽（对齐 ft710）==========
	// 若 AudioContext 采样率非 48k（如 44.1k），线性重采样到 48k 再编码
	var contextRate = mh && mh.context ? mh.context.sampleRate : 48000;
	var sourceData = data;
	if (Math.abs(contextRate - 48000) > 1) {
		sourceData = resampleFloat32To48k(data, contextRate);
	}

	// ========== 帧累积逻辑 ==========
	// Opus 帧大小 = 48000Hz * 20ms / 1000 = 960 samples
	var opusFrameSize = 960;

	// 初始化累积缓冲区（如果不存在）
	if (!this.frameAccumulator) {
		this.frameAccumulator = new Float32Array(0);
	}

	// 将新数据追加到累积缓冲区
	var newAccumulator = new Float32Array(this.frameAccumulator.length + sourceData.length);
	newAccumulator.set(this.frameAccumulator);
	newAccumulator.set(sourceData, this.frameAccumulator.length);
	this.frameAccumulator = newAccumulator;
	
	if( encode )
	{
		// 处理累积缓冲区中的完整帧
		while (this.frameAccumulator.length >= opusFrameSize)
		{
			// 取出一个完整帧
			var frame = this.frameAccumulator.slice(0, opusFrameSize);
			this.frameAccumulator = this.frameAccumulator.slice(opusFrameSize);
			
			// 编码并发送
		    var res = this.opusEncoder.encode_float(frame);

			// V4.4.22: 检查 WebSocket 状态，避免向已关闭的连接发送数据
			if (this.wsh.readyState !== WebSocket.OPEN) {
				return;
			}

		    for( var idx = 0; idx < res.length; ++idx )
			{
				// 码率统计：TX（编码后）
				if (!window.__txBytes) { window.__txBytes = 0; }
				if (res[idx] && res[idx].byteLength) { window.__txBytes += res[idx].byteLength; }
				// 线格式：1 字节标签 (0x01=Opus) + Opus 帧
				var tagArr = new Uint8Array(res[idx].byteLength + 1);
				tagArr[0] = 0x01;
				tagArr.set(new Uint8Array(res[idx]), 1);
				this.wsh.send(tagArr.buffer);
			}
		}
	}
		else
	{
		// PCM模式：同样使用帧累积确保数据对齐
		while (this.frameAccumulator.length >= opusFrameSize)
		{
			var frame = this.frameAccumulator.slice(0, opusFrameSize);
			this.frameAccumulator = this.frameAccumulator.slice(opusFrameSize);

			// 转换为 Int16
			var int16Frame = new Int16Array(opusFrameSize);
			for (var j = 0; j < opusFrameSize; j++) {
				int16Frame[j] = frame[j] * 0x7FFF; // 使用0x7FFF避免溢出
			}

			// V4.4.22: 检查 WebSocket 状态
			if (this.wsh.readyState !== WebSocket.OPEN) {
				return;
			}

		    // 码率统计：TX（PCM直发）
		    if (!window.__txBytes) { window.__txBytes = 0; }
		    window.__txBytes += int16Frame.byteLength;
		    // 线格式：1 字节标签 (0x00=PCM) + Int16 数据
		    var tagPcm = new Uint8Array(int16Frame.byteLength + 1);
		    tagPcm[0] = 0x00;
		    tagPcm.set(new Uint8Array(int16Frame.buffer, int16Frame.byteOffset, int16Frame.byteLength), 1);
		    this.wsh.send(tagPcm.buffer);
		}
	}
	
	let u;
    let sum = 0.0;
    let clipcount = 0;
    for (u = 0; u < data.length; ++u) {
      sum += data[u] * data[u];
      if (Math.abs(data[u]) > 0.99) {
        clipcount += 1;
      }
    }
	if(clipcount > 5){
		blikcritik("TX-GAIN_control");
	}
    that.instant = Math.sqrt(sum / data.length);
	TXinstantMeter.value = that.instant*100;
    }

}

var MediaHandler = function( audioProcessor )
{
    console.log('🎤 MediaHandler: 创建TX音频上下文...');
    
    var context = new (window.AudioContext||window.webkitAudioContext)();
    if( !context.createScriptProcessor )
	context.createScriptProcessor = context.createJavaScriptNode;

    console.log('🎤 MediaHandler: AudioContext状态:', context.state, '采样率:', context.sampleRate);

    if( context.sampleRate < 44000 || context.SampleRate > 50000 )
    {
	console.warn( "Unsupported sample rate: " + String( context.sampleRate ) );
    };

    // iOS Safari 关键：如果AudioContext处于suspended状态，立即恢复
    if (context.state === 'suspended') {
        console.log('🎤 MediaHandler: AudioContext suspended，尝试恢复...');
        context.resume().then(() => {
            console.log('✅ MediaHandler: AudioContext已恢复');
        }).catch(e => {
            console.error('❌ MediaHandler: AudioContext恢复失败:', e);
        });
    }
    
    this.context = context;
    this.audioProcessor = audioProcessor;
    
    // 使用现代API获取麦克风（iOS Safari兼容性更好）
    var self = this;
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        console.log('🎤 MediaHandler: 使用navigator.mediaDevices.getUserMedia...');
        navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: false,
                        noiseSuppression: false,
                        autoGainControl: false
                    },
                    video: false
                })
            .then(function(stream) {
                console.log('✅ MediaHandler: 麦克风权限获取成功');
                self.callback.bind(self)(stream);
            })
            .catch(function(err) {
                console.error('❌ MediaHandler: 麦克风权限获取失败:', err);
                self.error.bind(self)(err);
            });
    } else {
        // 回退到旧API
        console.log('🎤 MediaHandler: 使用旧版navigator.getUserMedia...');
        navigator.getUserMedia = navigator.getUserMedia || navigator.webkitGetUserMedia || navigator.mozGetUserMedia;
        var userMediaConfig = {
            "audio": {
                "mandatory": {},
                "optional": []
            }
        };
        navigator.getUserMedia( userMediaConfig, this.callback.bind( this ), this.error );
    }
}

var AudioTX_analyser = "";

////////////////////////////////////////////////////////////
// TX EQ 均衡器已提取到 modules/tx_audio_eq.js


MediaHandler.prototype.callback = function( stream )
{
    console.log( '🎤 MediaHandler.callback: 开始设置麦克风...' );

    try {
        // iOS Safari 关键：确保AudioContext处于running状态
        if (this.context.state === 'suspended') {
            console.log('🎤 MediaHandler.callback: AudioContext suspended，尝试恢复...');
            this.context.resume().then(() => {
                console.log('✅ MediaHandler.callback: AudioContext已恢复');
            }).catch(e => {
                console.error('❌ MediaHandler.callback: AudioContext恢复失败:', e);
            });
        }

        // V5.4: 保存 MediaStream 引用，AudioTX_stop 时释放麦克风硬件
        this.stream = stream;

        AudioTX_analyser = this.context.createAnalyser();
        this.gain_node = this.context.createGain();
        this.micSource = this.context.createMediaStreamSource( stream );
        // V5.4: 采集节点（AudioWorklet 优先 / ScriptProcessor 回退）在音频链
        // 搭建完成后异步接入，见下方 connectTxProcessor

        // 初始化 TX EQ
        initTX_EQ(this.context);

        // 音频链: micSource → preamp → highCut → antiAlias → antiAlias2 → eqLow → eqMid → eqHigh → midCut → presence → compressor → noiseGate → gain_node → processor
        // RagChew 专用节点在标准模式下设为直通（flat gain / bypass），不影响信号
        this.micSource.connect(AudioTX_preamp);
        AudioTX_preamp.connect(AudioTX_highCut);
        AudioTX_highCut.connect(AudioTX_antiAlias);
        AudioTX_antiAlias.connect(AudioTX_antiAlias2);
        AudioTX_antiAlias2.connect(AudioTX_eqLow);
        AudioTX_eqLow.connect(AudioTX_eqMid);
        AudioTX_eqMid.connect(AudioTX_eqHigh);
        AudioTX_eqHigh.connect(AudioTX_midCut);
        AudioTX_midCut.connect(AudioTX_presence);
        AudioTX_presence.connect(AudioTX_compressor);
        AudioTX_compressor.connect(AudioTX_noiseGate);
        AudioTX_noiseGate.connect(this.gain_node);

        // 关键：采集节点（AudioWorklet/ScriptProcessor）需要连接到输出才会被音频图拉动
        // 但直接连接 destination 会导致回声自激
        // 解决方案：连接到静音节点（gain=0），再连接到 destination
        // 这样处理器能工作，但不会有声音输出到扬声器
        this.muteNode = this.context.createGain();
        this.muteNode.gain.value = 0;  // 静音
        this.muteNode.connect(this.context.destination);

        this.gain_node.connect( AudioTX_analyser );

        // V5.4: 优先 AudioWorklet（渲染线程采集，主线程零回调开销，
        // PTT 期间不再阻塞 ATR-1000 消息/UI）；iOS Safari / 旧浏览器 /
        // 模块加载失败时回退 ScriptProcessorNode
        var self = this;
        var isIOSSafariTX = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
        var useTxWorklet = !isIOSSafariTX && !!this.context.audioWorklet && (typeof AudioWorkletNode !== 'undefined');
        var connectTxProcessor = function(proc) {
            self.processor = proc;
            self.gain_node.connect(proc);
            proc.connect(self.muteNode);
        };
        if (useTxWorklet) {
            this.context.audioWorklet.addModule('tx_worklet_processor.js').then(function() {
                var node = new AudioWorkletNode(self.context, 'tx-capture');
                node.port.onmessage = function(ev) {
                    if (ev.data && ev.data.type === 'audioFrame' && self.audioProcessor) {
                        self.audioProcessor.pushSamples(ev.data.frame);
                    }
                };
                connectTxProcessor(node);
                console.log('✅ TX AudioWorklet 采集已启用');
            }).catch(function(err) {
                console.warn('⚠️ TX AudioWorklet 加载失败，回退 ScriptProcessor:', err);
                self._setupScriptProcessor(connectTxProcessor);
            });
        } else {
            this._setupScriptProcessor(connectTxProcessor);
        }
    } catch (e) {
        console.error('❌ TX 音频链初始化失败:', e);
        this.error(e);
        return;
    }
    
    // 从Cookie恢复EQ预设，或根据设备类型自动设置
    try {
        var savedPreset = typeof getCookie === 'function' ? getCookie('TX_EQ_Preset') : '';

        if (savedPreset && TX_EQ_PRESETS[savedPreset]) {
            // 用户已保存过预设，恢复它
            setTX_EQ_Preset(savedPreset);
        } else {
            // 没有保存的预设，自动检测设备类型并应用合适的预设
            var userAgent = navigator.userAgent || '';
            var isIPhone = /iPhone|iPod/.test(userAgent);
            var isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent)
                           || (navigator.maxTouchPoints && navigator.maxTouchPoints > 2);

            if (isIPhone) {
                setTX_EQ_Preset('STRONG');
                console.log('📱 检测到 iPhone，自动应用 STRONG TX EQ 预设');
            } else if (isMobile) {
                setTX_EQ_Preset('MEDIUM');
                console.log('📱 检测到移动设备，自动应用 MEDIUM TX EQ 预设');
            } else {
                setTX_EQ_Preset('DEFAULT');
                console.log('🖥️ 检测到桌面设备，使用 DEFAULT TX EQ 预设');
            }
        }
    } catch (e) {
        console.error('❌ TX EQ 预设应用失败:', e);
        // 预设失败不影响音频链正常工作
    }

    console.log( '✅ MediaHandler.callback: 麦克风设置完成 (含TX EQ)' );
}


// V5.4: ScriptProcessor 回退路径（iOS Safari / AudioWorklet 不可用时）
MediaHandler.prototype._setupScriptProcessor = function( connectTxProcessor ) {
    var proc = this.context.createScriptProcessor( this.audioProcessor.bufferSize, 1, 1 );
    proc.onaudioprocess = this.audioProcessor.onAudioProcess.bind( this.audioProcessor );
    connectTxProcessor(proc);
    console.log('✅ TX ScriptProcessor 采集已启用（回退模式）');
};


MediaHandler.prototype.error = function( err ) {
    console.error('MediaHandler error:', err);
    // 提供更详细的错误信息
    let errorMessage = "音频设备初始化失败";
    if (err && err.name) {
        switch(err.name) {
            case "NotAllowedError":
                errorMessage += "：请允许访问麦克风";
                break;
            case "NotFoundError":
                errorMessage += "：未找到音频输入设备";
                break;
            case "NotReadableError":
                errorMessage += "：音频设备不可读";
                break;
            case "OverconstrainedError":
                errorMessage += "：音频设备参数不匹配";
                break;
            case "TypeError":
                errorMessage += "：类型错误 — " + (err.message || err);
                break;
            default:
                errorMessage += "：" + err.name + " — " + (err.message || '');
        }
    }
    alert(errorMessage);
}


var isRecording = false, encode = false;
var wsAudioTX = "";
var ap = "";
var mh = "";

const TXinstantMeter = document.querySelector('#Txinstant meter');

function AudioTX_start()
{
	// 避免重复创建连接：仅 OPEN/CONNECTING 跳过；CLOSING/CLOSED 都重建。
	// （同 AudioRX_start：close() 后的 CLOSING 态不得误判为"已连接"）
	if (wsAudioTX && (wsAudioTX.readyState === WebSocket.OPEN || wsAudioTX.readyState === WebSocket.CONNECTING)) {
		console.log('⏭️ AudioTX WebSocket已在连接中或已连接，跳过重复创建');
		return;
	}
	
	isRecording = false;
	encode = false;
	setWSStatus('status-tx', 'connecting');
	wsAudioTX = new WebSocket( __wsURL('/WSaudioTX') );
	wsAudioTX.onopen = appendwsAudioTXOpen;
	wsAudioTX.onerror = appendwsAudioTXError;
	wsAudioTX.onclose = appendwsAudioTXclose;
	ap = new OpusEncoderProcessor( wsAudioTX );
	mh = new MediaHandler( ap );
}

function appendwsAudioTXclose(){
	console.log('🔌 WebSocket TX连接已关闭');
	setWSStatus('status-tx', 'error');
	// 自动重连：如果电源仍开启，尝试重连
	if (typeof poweron !== 'undefined' && poweron) {
		console.log('🔄 电源开启中，3秒后尝试重连TX WebSocket...');
		if (window._audioTXReconnectTimer) {
			clearTimeout(window._audioTXReconnectTimer);
		}
		window._audioTXReconnectTimer = setTimeout(function() {
			if (typeof poweron !== 'undefined' && poweron) {
				if (!wsAudioTX || wsAudioTX.readyState === WebSocket.CLOSED) {
					console.log('🔄 正在重连TX WebSocket...');
					// 保存旧的引用
					var oldOnOpen = wsAudioTX ? wsAudioTX.onopen : null;
					var oldOnError = wsAudioTX ? wsAudioTX.onerror : null;
					var oldOnClose = wsAudioTX ? wsAudioTX.onclose : null;
					wsAudioTX = new WebSocket(__wsURL('/WSaudioTX'));
					wsAudioTX.onopen = appendwsAudioTXOpen;
					wsAudioTX.onerror = appendwsAudioTXError;
					wsAudioTX.onclose = appendwsAudioTXclose;
					// 重新绑定编码器
					if (typeof ap !== 'undefined' && ap) {
						// H15: 编码器使用 this.wsh（见 OpusEncoderProcessor.onAudioProcess），
						// 原代码写 ap.ws 导致重连后仍向已关闭的旧 socket 发数据、发射期间无音频上行。
						ap.wsh = wsAudioTX;
					}
				}
			}
		}, 3000);
	}
}

function appendwsAudioTXOpen(){
	setWSStatus('status-tx', 'connected');
}

function appendwsAudioTXError(err){
	console.error('❌ WebSocket TX连接错误:', err);
	setWSStatus('status-tx', 'error');
	// 防抖重连：避免频繁重连
	if (typeof poweron !== 'undefined' && poweron) {
		if (window._audioTXErrorReconnectTimer) {
			clearTimeout(window._audioTXErrorReconnectTimer);
		}
		window._audioTXErrorReconnectTimer = setTimeout(function() {
			if (typeof poweron !== 'undefined' && poweron && (!wsAudioTX || wsAudioTX.readyState === WebSocket.CLOSED)) {
				console.log('🔄 错误后重连TX WebSocket...');
				AudioTX_start();
			}
		}, 1000);
	}
}

function AudioTX_stop()
{
isRecording = false;
encode = false;
try { if (wsAudioTX && wsAudioTX.readyState !== WebSocket.CLOSED) wsAudioTX.close(); } catch(e) {}
// V5.4: 释放麦克风硬件与音频图 — 原实现只关 WebSocket、清空引用，
// 浏览器麦克风指示灯会一直亮，且每次开关机泄漏一个 AudioContext。
// 注意：兼容 mobile_high.js 的 HQ_MediaHandler（字段可能缺失，逐一防御）
try {
    if (mh) {
        if (mh.stream && mh.stream.getTracks) {
            mh.stream.getTracks().forEach(function(t){ try { t.stop(); } catch(e){} });
        }
        if (mh.processor && mh.processor.disconnect) { try { mh.processor.disconnect(); } catch(e){} }
        if (mh.micSource && mh.micSource.disconnect) { try { mh.micSource.disconnect(); } catch(e){} }
        if (mh.context && mh.context.state !== 'closed') { mh.context.close().catch(function(){}); }
    }
} catch(e) { console.warn('AudioTX_stop 清理异常:', e); }
ap = "";
mh = "";
}

function sendSettings()
{
	var encodeElement = document.getElementById("encode");
    if( encodeElement && encodeElement.checked )
	encode = 1;
    else
	encode = 0;

    // 同步更新 RX Opus 解码状态
    AudioRX_opusDecode = (encode === 1);
    console.log('📡 Opus 编码状态: TX=' + encode + ', RX解码=' + AudioRX_opusDecode);

    // TX 采样率 = mic 原生率（48k 全带宽），编码器 48k，两者一致；44.1k mic 由客户端重采样到 48k
    var rate = String( mh.context.sampleRate );
    var opusRate = String( ap.opusRate );
    var opusFrameDur = String( ap.opusFrameDur );
    // 第 5 字段 = 线格式标签模式（1= 每帧前加 1 字节 0x00 PCM / 0x01 Opus）
    var tagged = 1;

    var msg = "m:" + [ rate, encode, opusRate, opusFrameDur, tagged ].join( "," );
    console.log( msg );
    if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
		wsAudioTX.send( msg );
	}
}

function startRecord()
{
	var encodeBtn = document.getElementById("encode");
	if (encodeBtn) encodeBtn.disabled = true;
    
    // iOS Safari 关键：确保 TX AudioContext 已恢复
    if (mh && mh.context && mh.context.state === 'suspended') {
        mh.context.resume().then(() => {
            console.log('✅ TX AudioContext 已恢复');
        }).catch(e => {
            console.error('❌ TX AudioContext 恢复失败:', e);
        });
    }
    
    sendSettings();
    isRecording = true;
    console.log( 'started recording' );
}

function stopRecord()
{
	if (TXinstantMeter) TXinstantMeter.value = 0;
	
    isRecording  = false;
    var encodeBtn = document.getElementById("encode");
	if (encodeBtn) encodeBtn.disabled = false;
    console.log( 'ended recording' ); 

    // V5.4: flush 编码器尾部不完整帧 — 原实现直接丢弃 frameAccumulator 残余
    // 和编码器内部缓冲，每次 PTT 结束最多丢失 20ms 语音（断字）。
    // 残余样本送入编码器 → encode_float_final 零填充补齐 → 带标签发出，
    // 必须在 "s:" 停止标记之前发送。
    if (encode && ap && ap.opusEncoder) {
        try {
            var tailPackets = [];
            if (ap.frameAccumulator && ap.frameAccumulator.length > 0) {
                var encRes = ap.opusEncoder.encode_float(ap.frameAccumulator);
                if (encRes && encRes.length) tailPackets = encRes;
                ap.frameAccumulator = new Float32Array(0);
            }
            var finalPacket = ap.opusEncoder.encode_float_final();
            if (finalPacket && finalPacket.byteLength > 0) {
                tailPackets.push(finalPacket);
            }
            if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
                for (var ti = 0; ti < tailPackets.length; ti++) {
                    var tagTail = new Uint8Array(tailPackets[ti].byteLength + 1);
                    tagTail[0] = 0x01; // AUDIO_TAG_OPUS
                    tagTail.set(new Uint8Array(tailPackets[ti]), 1);
                    wsAudioTX.send(tagTail.buffer);
                }
            }
        } catch(e) {
            console.warn('TX 尾帧 flush 失败（忽略）:', e);
        }
    }

    // 立即停止音频播放，不播放录制的音频
    var msg = "s:";
    console.log( msg );
    if (wsAudioTX && wsAudioTX.readyState === WebSocket.OPEN) {
		wsAudioTX.send( msg );
	}
    
    // 立即切换到接收状态，不等待音频播放完成
    console.log( '立即切换到接收状态' );
}

function AudioTX_SetGAIN( vol ){
	if(poweron && mh && mh.gain_node)mh.gain_node.gain.setValueAtTime(vol, mh.context.currentTime);
}

function toggleRecord(sendit = false)
{
    if( !sendit ){stopRecord();}
    else {if (wsAudioTX.readyState !== WebSocket.CLOSED) {startRecord();}}
}



// Tune/CQ 功能已提取到 modules/tune_cq.js

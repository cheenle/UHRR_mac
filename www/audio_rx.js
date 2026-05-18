// Audio RX functions - Audio reception and processing
// V5.2: 重写播放引擎 — 多 BufferSourceNode 调度，消除帧间间隙

const RXinstantMeter = document.querySelector('#RXinstant meter');

var wsAudioRX = "";
var AudioRX_context = "";
var AudioRX_gain_node = "";
var AudioRX_biquadFilter_node = "";
var AudioRX_analyser = "";
var AudioRX_audiobuffer = [];
var AudioRX_sampleRate=16000;

// V5.2: 调度播放状态
var _rx_nextStartTime = 0;
var _rx_scheduledCount = 0;
var _rx_maxScheduled = 3;       // 最多提前调度3帧
var _rx_nodesInitialized = false;

function AudioRX_start(){
	document.getElementById("indwsAudioRX").innerHTML='<img src="img/critsgrey.png">wsRX';
	AudioRX_audiobuffer = [];
	_rx_nextStartTime = 0;
	_rx_scheduledCount = 0;
	_rx_nodesInitialized = false;

	wsAudioRX = new WebSocket( 'wss://' + window.location.href.split( '/' )[2] + '/WSaudioRX' );
	wsAudioRX.binaryType = 'arraybuffer';
	wsAudioRX.onmessage = appendwsAudioRX;
	wsAudioRX.onopen = wsAudioRXopen;
	wsAudioRX.onclose = wsAudioRXclose;
	wsAudioRX.onerror = wsAudioRXerror;

	if (!window.__brTimer) {
		window.__rxBytes = 0; window.__txBytes = 0;
		window.__brTimer = setInterval(function(){
			var rxkbps = (window.__rxBytes||0) * 8 / 1000;
			var txkbps = (window.__txBytes||0) * 8 / 1000;
			console.log(`[码率] RX: ${rxkbps.toFixed(1)} kbps, TX: ${txkbps.toFixed(1)} kbps`);
			var brEl = document.getElementById('div-bitrates');
			if (brEl) { brEl.textContent = `bitrate RX: ${rxkbps.toFixed(1)} kbps | TX: ${txkbps.toFixed(1)} kbps`; }
			window.__rxBytes = 0; window.__txBytes = 0;
		}, 1000);
	}

	function appendwsAudioRX( msg ){
		if (!window.__rxBytes) { window.__rxBytes = 0; }
		if (msg && msg.data && msg.data.byteLength) {
			window.__rxBytes += msg.data.byteLength;
		}
		// V5.2: 限制队列深度，防止积压
		if (AudioRX_audiobuffer.length > 20) {
			AudioRX_audiobuffer.splice(0, AudioRX_audiobuffer.length - 10);
		}
		AudioRX_audiobuffer.push(msg.data);
		// 尝试调度播放
		AudioRX_scheduleNext();
	}

	// V5.2: 非递归调度播放 — 创建新 BufferSourceNode，精确时间对齐
	function AudioRX_scheduleNext(){
		// 限制并发调度数
		if (_rx_scheduledCount >= _rx_maxScheduled) return;
		if (AudioRX_audiobuffer.length === 0) return;

		var msg = AudioRX_audiobuffer.shift();
		_rx_scheduledCount++;

		// 确保 AudioContext 在用户交互后恢复
		if (AudioRX_context === "" || AudioRX_context.state === 'closed') {
			AudioRX_context = new (window.AudioContext || window.webkitAudioContext)({sampleRate:AudioRX_sampleRate});
		}
		if (AudioRX_context.state === 'suspended') {
			AudioRX_context.resume().then(function() {
				_doDecode(msg);
			}).catch(function() {
				_rx_scheduledCount--;
				AudioRX_audiobuffer.unshift(msg);
			});
		} else {
			_doDecode(msg);
		}
	}

	function _doDecode(msg) {
		AudioRX_context.decodeAudioData(msg, function(buffer) {
			// 懒初始化音频图
			if (!_rx_nodesInitialized) {
				AudioRX_gain_node = AudioRX_context.createGain();
				AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
				AudioRX_analyser = AudioRX_context.createAnalyser();
				AudioRX_analyser.fftSize = 2048;
				AudioRX_analyser.smoothingTimeConstant = 0.8;
				AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
				AudioRX_gain_node.connect(AudioRX_analyser);
				AudioRX_analyser.connect(AudioRX_context.destination);
				_rx_nodesInitialized = true;
			}

			// V5.2: 每个 buffer 创建独立的 BufferSourceNode
			var source = AudioRX_context.createBufferSource();
			source.buffer = buffer;
			source.connect(AudioRX_biquadFilter_node);

			// 精确时间对齐
			var now = AudioRX_context.currentTime;
			if (_rx_nextStartTime < now) {
				_rx_nextStartTime = now;
			}
			source.start(_rx_nextStartTime);
			_rx_nextStartTime += buffer.duration;

			source.onended = function() {
				_rx_scheduledCount--;
				// 从队列取下一帧
				if (AudioRX_audiobuffer.length > 0) {
					AudioRX_scheduleNext();
				}
			};

			// 继续预取
			if (AudioRX_audiobuffer.length > 0) {
				AudioRX_scheduleNext();
			}
		}, function(e) {
			console.log('Error decoding audio data: ' + e);
			_rx_scheduledCount--;
			// 丢包时用静默帧填充，避免时间线断裂
			if (_rx_scheduledCount === 0 && AudioRX_audiobuffer.length === 0) {
				// 没有待播放帧，时间线可能已断裂，重置
				_rx_nextStartTime = 0;
			}
			AudioRX_scheduleNext();
		});
	}
}

function setaudiofilter(){
	if(poweron){
		AudioRX_biquadFilter_node.type = event.srcElement.getAttribute('ft');
		AudioRX_biquadFilter_node.frequency.setValueAtTime(parseInt(event.srcElement.getAttribute('freq')), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.Q.setValueAtTime(parseInt(event.srcElement.getAttribute('Q')), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.gain.setValueAtTime(parseInt(event.srcElement.getAttribute('gain')), AudioRX_context.currentTime);
	}
}

function setcustomaudiofilter(){
	if(poweron){
		AudioRX_biquadFilter_node.type = document.getElementById("customfilter_T").value;
		AudioRX_biquadFilter_node.frequency.setValueAtTime(parseInt(document.getElementById("customfilter_F").value), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.Q.setValueAtTime(parseInt(document.getElementById("customfilter_Q").value), AudioRX_context.currentTime);
		AudioRX_biquadFilter_node.gain.setValueAtTime(parseInt(document.getElementById("customfilter_G").value), AudioRX_context.currentTime);
	}
}

function AudioRX_SetGAIN( vol="None" ){
	if(vol == "None"){volumeRX=document.getElementById("C_af").value/100;vol=volumeRX;}
	if(poweron){AudioRX_gain_node.gain.setValueAtTime(vol, AudioRX_context.currentTime);}
}

function wsAudioRXopen(){
	console.log('DEBUG: WebSocket audio RX connection opened');
	document.getElementById("indwsAudioRX").innerHTML='<img src="img/critsgreen.png">wsRX';
}

function wsAudioRXclose(){
	document.getElementById("indwsAudioRX").innerHTML='<img src="img/critsred.png">wsRX';
	AudioRX_stop();
}

function wsAudioRXerror(err){
	document.getElementById("indwsAudioRX").innerHTML='<img src="img/critsred.png">wsRX';
	AudioRX_stop();
}

function AudioRX_stop() {
	_rx_nextStartTime = 0;
	_rx_scheduledCount = 0;
	AudioRX_audiobuffer = [];
}

var muteRX=false;
function toggleaudioRX(stat="None"){
	muteRX=!muteRX;
	if(stat != "None"){muteRX=stat;}
}

var Audio_analyser="";
function drawRXFFT(Audio_analyser){
	Audio_analyser.fftSize = canvasBFFFT.width;
	var arrayFFT = new Float32Array(Audio_analyser.frequencyBinCount);
	Audio_analyser.getFloatFrequencyData(arrayFFT);
	ctxFFFT.clearRect(0, 0, canvasBFFFT.width, canvasBFFFT.height);

	var scale_mult = Math.exp(parseInt(document.getElementById("canBFFFT_scale_multdb").value)/100);
	var scale_floor = parseInt(document.getElementById("canBFFFT_scale_floor").value)*scale_mult;
	var scale_hz = Math.exp(parseInt(document.getElementById("canBFFFT_scale_multhz").value)/100);
	var start = (parseInt(document.getElementById("canBFFFT_scale_start").value)*Audio_analyser.frequencyBinCount/100)*scale_hz;
	var largeurBarre = (canvasBFFFT.width / Audio_analyser.frequencyBinCount)*scale_hz;
	var hauteurBarre;
	var x = start;
	for(var i = 0; i < Audio_analyser.frequencyBinCount; i++) {
		hauteurBarre = (arrayFFT[i]*scale_mult + canvasBFFFT.height + scale_floor);
		if(hauteurBarre>0){
			ctxFFFT.fillStyle = "rgb(0, 0, 0)";
			ctxFFFT.fillRect(x, canvasBFFFT.height - hauteurBarre, largeurBarre, hauteurBarre);
		}
		x += largeurBarre;
	}
}

function drawRXSPC(Audio_analyser){
	var arraySPC = new Float32Array(Audio_analyser.fftSize);
	Audio_analyser.getFloatTimeDomainData(arraySPC);
	canvasBFspc = document.getElementById("canBFSPC");
	ctxBFspc = canvasBFspc.getContext("2d");
	ctxBFspc.clearRect(0, 0, canvasBFspc.width, canvasBFspc.height);

	var largeurTranche = canvasBFspc.width * 1.0 / Audio_analyser.fftSize;
	var x = 0;
	for(var i = 0; i < Audio_analyser.fftSize; i++) {
		var v = arraySPC[i] * 128.0;
		var y = 128.0 + v;
		ctxBFspc.lineTo(x, y);
		x += largeurTranche;
	}
	ctxBFspc.stroke();
}

function drawBF(){
	if(muteRX){Audio_analyser=AudioTX_analyser}else{Audio_analyser=AudioRX_analyser}
	if(Audio_analyser){
		drawRXFFT(Audio_analyser);
		drawRXSPC(Audio_analyser);
	}
}

function drawRXvol(){
	var arraySPC = new Float32Array(AudioRX_analyser.fftSize);
	AudioRX_analyser.getFloatTimeDomainData(arraySPC);
	var sum = 0;
	for(var i = 0; i < AudioRX_analyser.fftSize; i++) {
		sum += arraySPC[i] * arraySPC[i];
	}
	var rms = Math.sqrt(sum / AudioRX_analyser.fftSize);
	var volume = Math.min(rms * 100, 100);
	RXinstantMeter.value = volume;
	document.querySelector('#RXinstant .value').textContent = volume.toFixed(0);
}

function showRXvol(){
	
}

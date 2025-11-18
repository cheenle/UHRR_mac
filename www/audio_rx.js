// Audio RX functions - Audio reception and processing

// 避免重复声明 - 使用全局变量或检查是否存在
if (typeof RXinstantMeter === 'undefined') {
    var RXinstantMeter = document.querySelector('#RXinstant meter');
}

var wsAudioRX = "";
var AudioRX_context = "";
var AudioRX_source_node = "";
var AudioRX_gain_node = "";
var AudioRX_biquadFilter_node = "";
var AudioRX_analyser = "";
var audiobufferready = false;
var AudioRX_audiobuffer = [];
var AudioRX_sampleRate=16000;
var audioSyncMonitor = {
	lastProcessTime: 0,
	bufferCount: 0,
	lagWarning: false
};

function AudioRX_start(){
	document.getElementById("indwsAudioRX").innerHTML='<img src="img/critsgrey.png">wsRX';
	AudioRX_audiobuffer = [];var lenglitchbuf = 2;

	wsAudioRX = new WebSocket( 'wss://' + window.location.href.split( '/' )[2] + '/WSaudioRX' );
	wsAudioRX.binaryType = 'arraybuffer';
	wsAudioRX.onmessage = appendwsAudioRX;
	wsAudioRX.onopen = wsAudioRXopen;
	wsAudioRX.onclose = wsAudioRXclose;
	wsAudioRX.onerror = wsAudioRXerror;

	// 每秒打印一次码率（RX/TX）
	if (!window.__brTimer) {
		window.__rxBytes = 0; window.__txBytes = 0;
		window.__brTimer = setInterval(function(){
			var rxkbps = (window.__rxBytes||0) * 8 / 1000; // Kbps
			var txkbps = (window.__txBytes||0) * 8 / 1000;
			console.log(`[码率] RX: ${rxkbps.toFixed(1)} kbps, TX: ${txkbps.toFixed(1)} kbps`);
			var brEl = document.getElementById('div-bitrates');
			if (brEl) { brEl.textContent = `bitrate RX: ${rxkbps.toFixed(1)} kbps | TX: ${txkbps.toFixed(1)} kbps`; }
			window.__rxBytes = 0; window.__txBytes = 0;
		}, 1000);
	}

	function appendwsAudioRX( msg ){
		console.log('DEBUG: Received audio data message');
		// 码率统计：RX
		if (!window.__rxBytes) { window.__rxBytes = 0; }
		if (msg && msg.data && msg.data.byteLength) {
			window.__rxBytes += msg.data.byteLength;
		}
		// 限制缓冲区大小，防止累积过多音频数据
		if (AudioRX_audiobuffer.length > 10) {
			AudioRX_audiobuffer.shift();
		}
		AudioRX_audiobuffer.push(msg.data);
		if (!audiobufferready) {
			audiobufferready = true;
			AudioRX_process();
		}
	}

	function AudioRX_process(){
		if (AudioRX_audiobuffer.length > 0) {
			var msg = AudioRX_audiobuffer.shift();
			if (AudioRX_context === "") {
				AudioRX_context = new AudioContext({sampleRate:AudioRX_sampleRate});
				AudioRX_source_node = AudioRX_context.createBufferSource();
				AudioRX_gain_node = AudioRX_context.createGain();
				AudioRX_biquadFilter_node = AudioRX_context.createBiquadFilter();
				AudioRX_analyser = AudioRX_context.createAnalyser();
				AudioRX_analyser.fftSize = 2048;
				AudioRX_analyser.smoothingTimeConstant = 0.8;
				AudioRX_source_node.connect(AudioRX_biquadFilter_node);
				AudioRX_biquadFilter_node.connect(AudioRX_gain_node);
				AudioRX_gain_node.connect(AudioRX_analyser);
				AudioRX_analyser.connect(AudioRX_context.destination);
				AudioRX_source_node.start();
			}
			AudioRX_context.decodeAudioData(msg, function(buffer) {
				AudioRX_source_node.buffer = buffer;
				AudioRX_process();
			}, function(e) {
				console.log('Error with decoding audio data' + e.err);
				AudioRX_process();
			});
		} else {
			audiobufferready = false;
		}
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

function AudioRX_stop()
{
	audiobufferready = false;
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
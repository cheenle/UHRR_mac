// Control TRX functions - Radio control and frequency management

var wsControlTRX = "";
function ControlTRX_start(){
	document.getElementById("indwsControlTRX").innerHTML='<img src="img/critsgrey.png">wsCtrl';

	wsControlTRX = new WebSocket( 'wss://' + window.location.href.split( '/' )[2] + '/WScontrolTRX' );
	wsControlTRX.onmessage = wsControlTRXcrtol;
	wsControlTRX.onopen = wsControlTRXopen;
	wsControlTRX.onclose = wsControlTRXclose;
	wsControlTRX.onerror = wsControlTRXerror;
}

var SignalLevel=0;
function wsControlTRXcrtol( msg ){
	words = String(msg.data).split(':');
	if(words[0]=='freq'){
		showTRXfreq(words[1]);
	}
	if(words[0]=='mode'){
		button_light_all("div-mode_menu");
		button_light(document.getElementById("button_"+words[1]));
	}
	if(words[0]=='filter'){
		button_light_all("div-filtershortcut");
		button_light(document.getElementById("button_"+words[1]));
	}
	if(words[0]=='ptt'){
		PTT_DEVICE_STATE = (words[1] === 'true');
		PTT_LAST_UPDATE_TIME = Date.now();
		PTT_COMMAND_SENT = false;
		updatePTTDisplay();
	}
	if(words[0]=='signal'){
		SignalLevel=words[1];
		if(poweron)drawRXsMeter();
	}
}

function ControlTRX_stop()
{
	
}

function ControlTRX_getFreq(){
	if (wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("getFreq");}
}

function wsControlTRXopen(){
	console.log('✅ WebSocket控制连接成功建立');
	document.getElementById("indwsControlTRX").innerHTML='<img src="img/critsgreen.png">wsCtrl';
	ControlTRX_getFreq();
}

function wsControlTRXclose(){
	document.getElementById("indwsControlTRX").innerHTML='<img src="img/critsred.png">wsCtrl';
}

function wsControlTRXerror(err){
	console.error('❌ WebSocket控制连接错误:', err);
}

var startTime;
function checklatency() {
	setTimeout(function () {
		startTime = Date.now();
		if (wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("ping");}
	}, 1000);
}

function showlatency(){
	latency = Date.now() - startTime;
}

function get_digit_freq(){
	return parseInt(
		  document.getElementById("digit_cmhz").innerHTML
		+ document.getElementById("digit_dmhz").innerHTML
		+ document.getElementById("digit_umhz").innerHTML
		+ document.getElementById("digit_ckhz").innerHTML
		+ document.getElementById("digit_dkhz").innerHTML
		+ document.getElementById("digit_ukhz").innerHTML
		+ document.getElementById("digit_chz").innerHTML
		+ document.getElementById("digit_dhz").innerHTML
		+ document.getElementById("digit_uhz").innerHTML
	);
}

function freq_digit_scroll() {
	if (poweron) {
		if (freq_digit_selected) {
			var digit = freq_digit_selected.getAttribute("digit");
			var v = parseInt(freq_digit_selected.getAttribute("v"));
			var current_freq = get_digit_freq();
			var new_freq = current_freq + v;
			sendTRXfreq(new_freq);
		}
	}
}

function select_digit() {
	freq_digit_selected=event.srcElement;
}

function clear_select_digit() {
	freq_digit_selected="";
}

function rotatefreq(){
	if (poweron) {
		if (freq_digit_selected) {
			var digit = freq_digit_selected.getAttribute("digit");
			var v = parseInt(freq_digit_selected.getAttribute("v"));
			var current_freq = get_digit_freq();
			var new_freq = current_freq + v;
			sendTRXfreq(new_freq);
		}
	}
}

function showTRXfreq(freq){
	freq=freq.toString();
	while(freq.length<9)freq="0"+freq;
	document.getElementById("digit_cmhz").innerHTML=freq[0];
	document.getElementById("digit_dmhz").innerHTML=freq[1];
	document.getElementById("digit_umhz").innerHTML=freq[2];
	document.getElementById("digit_ckhz").innerHTML=freq[3];
	document.getElementById("digit_dkhz").innerHTML=freq[4];
	document.getElementById("digit_ukhz").innerHTML=freq[5];
	document.getElementById("digit_chz").innerHTML=freq[6];
	document.getElementById("digit_dhz").innerHTML=freq[7];
	document.getElementById("digit_uhz").innerHTML=freq[8];
}

function sendTRXfreq(freq=0){
	if(!freq){freq=get_digit_freq();}
	if (wsControlTRX.readyState === WebSocket.OPEN) {wsControlTRX.send("freq:"+freq);}
}

var lastPTTState = null;
var lastPTTTime = 0;
var PTT_DEBOUNCE_DELAY = 100; // 防抖延迟改回100ms
var PTT_COMMAND_SENT = false; // 跟踪是否已发送PTT命令
var PTT_DEVICE_STATE = false; // 设备确认的PTT状态（优先使用）
var PTT_PREDICTED_STATE = false; // 本地预测的PTT状态（仅用于临时显示）
var PTT_LAST_UPDATE_TIME = 0; // 最后状态更新时间
var PTT_USER_INTENT = false; // 用户意图状态（按下TX时为true，松开时为false）
function sendTRXptt(stat){
	var currentTime = Date.now();
	
	// 更新用户意图状态
	PTT_USER_INTENT = stat;
	
	// 防抖处理：如果距离上次状态改变时间太短，忽略
	if (currentTime - lastPTTTime < PTT_DEBOUNCE_DELAY) {
		return;
	}
	
	// 如果用户意图与设备状态一致，不需要发送命令
	if (PTT_USER_INTENT === PTT_DEVICE_STATE) {
		PTT_COMMAND_SENT = false;
		return;
	}
	
	// 如果已经发送过命令但设备状态未更新，等待设备响应
	if (PTT_COMMAND_SENT && currentTime - PTT_LAST_UPDATE_TIME < 500) {
		console.log('等待设备PTT状态更新...');
		return;
	}
	
	// 发送PTT命令
	if (wsControlTRX.readyState === WebSocket.OPEN) {
		PTT_COMMAND_SENT = true;
		lastPTTTime = currentTime;
		wsControlTRX.send("ptt:"+stat);
		console.log('发送PTT命令:', stat);
	}
}

function updatePTTDisplay() {
	// 优先使用设备确认的状态，如果没有则使用预测状态
	var displayState = PTT_DEVICE_STATE !== null ? PTT_DEVICE_STATE : PTT_PREDICTED_STATE;
	
	if (displayState) {
		document.getElementById("button_TX").style.backgroundColor = "red";
		document.getElementById("indTX").innerHTML='<img src="img/critsred.png">TX';
	} else {
		document.getElementById("button_TX").style.backgroundColor = "";
		document.getElementById("indTX").innerHTML='<img src="img/critsgreen.png">TX';
	}
}
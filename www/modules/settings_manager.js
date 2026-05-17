/**
 * settings_manager.js
 *
 * Cookie and settings management module extracted from controls.js.
 * Handles reading/writing browser cookies for persisting user preferences
 * (callsign, audio levels, squelch, saved frequencies, etc.).
 *
 * DOM dependencies (from index.html):
 *   #callsign, #C_af, #SQUELCH, #C_mg, #selectpersonalfrequency,
 *   .freq_digit elements (cmhz, dmhz, umhz, ckhz, dkhz, ukhz, chz, dhz, uhz)
 *
 * External dependencies:
 *   get_actualmode()          – defined in controls.js
 *   wsControlTRX (WebSocket)  – defined in controls.js
 */

// ---------------------------------------------------------------------------
// Core cookie helpers
// ---------------------------------------------------------------------------

function setCookie(cname, cvalue, exdays) {
  var d = new Date();
  d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
  var expires = "expires=" + d.toGMTString();
  document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getCookie(cname) {
  var name = cname + "=";
  var decodedCookie = decodeURIComponent(document.cookie);
  var ca = decodedCookie.split(';');
  for (var i = 0; i < ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

// ---------------------------------------------------------------------------
// Startup / session check
// ---------------------------------------------------------------------------

function checkCookie() {
  var callsign = getCookie("callsign");
  if (callsign != "") {
    alert("Welcome " + callsign);
    labelcalls = document.getElementById("callsign");
    labelcalls.innerHTML = callsign;
    if (getCookie("autha")) labelcalls.innerHTML += '&ensp;<a href="/logout" id="logout"><img src="img/logout.png"></a>';
  } else {
    callsign = prompt("Please enter your Call Sign:", "");
    if (callsign != "" && callsign != null) {
      setCookie("callsign", callsign, 180);
    }
  }
  var vol = getCookie("C_af");
  if (vol != "") { document.getElementById("C_af").value = vol; }
  var sql = getCookie("SQUELCH");
  if (sql != "") { document.getElementById("SQUELCH").value = sql; }
  var mg = getCookie("C_mg");
  if (mg != "") { document.getElementById("C_mg").value = mg; }
  get_freqfromcokkies();
}

// ---------------------------------------------------------------------------
// Personal frequency bookmarks (cookie-backed)
// ---------------------------------------------------------------------------

function get_freqfromcokkies(itemselected) {
  if (typeof itemselected === "undefined") { itemselected = ""; }

  // Defensive check: skip if the element does not exist
  var x = document.getElementById("selectpersonalfrequency");
  if (!x) {
    console.log('\u26a0\ufe0f selectpersonalfrequency element not found, skipping frequency load');
    return;
  }

  var freqs = getCookie("freqs").replace("//", '/').split("/").sort();
  var length = x.options.length;
  for (var i = length - 1; i >= 0; i--) {
    x.options[i] = null;
  }

  for (var i in freqs) {
    var option = document.createElement("option");
    if (freqs[i] != "") {
      var freq = freqs[i].split(",")[0];
      var mode = freqs[i].split(",")[1];
      option.text = parseInt(freq) + " in " + mode;
      option.value = freqs[i];
      if (option.value == itemselected) { option.selected = true; }
      x.add(option);
    }
  }
}

function save_freqtocokkies() {
  var freq = (
    document.getElementById("cmhz").innerHTML +
    document.getElementById("dmhz").innerHTML +
    document.getElementById("umhz").innerHTML +
    document.getElementById("ckhz").innerHTML +
    document.getElementById("dkhz").innerHTML +
    document.getElementById("ukhz").innerHTML +
    document.getElementById("chz").innerHTML +
    document.getElementById("dhz").innerHTML +
    document.getElementById("uhz").innerHTML
  );
  var mode = get_actualmode();
  var freqs = getCookie("freqs").replace("//", '/');
  var val = freq.toString() + "," + mode;
  if (!freqs.includes(val)) {
    freqs = freqs + val + "/";
    setCookie("freqs", freqs, 180);
    get_freqfromcokkies(val);
  }
}

function delete_freqfromcokkies() {
  var e = document.getElementById("selectpersonalfrequency");
  var freq = e.options[e.selectedIndex].value;
  var freqs = getCookie("freqs").replace(freq + "/", '').replace("//", '/');
  setCookie("freqs", freqs, 180);
  get_freqfromcokkies();
}

function recall_freqfromcokkies() {
  var e = document.getElementById("selectpersonalfrequency");
  var freq = e.options[e.selectedIndex].value.split(",")[0];
  var mode = e.options[e.selectedIndex].value.split(",")[1];
  if (wsControlTRX.readyState === WebSocket.OPEN) {
    wsControlTRX.send("setFreq:" + freq);
    wsControlTRX.send("setMode:" + mode);
  }
}

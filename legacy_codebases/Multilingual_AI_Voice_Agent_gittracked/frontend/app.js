// Clerk Publishable Key will be fetched dynamically from backend
let CLERK_PUBLISHABLE_KEY = "";

// ── Environment-aware backend URL ────────────────────────────────────────────
// Automatically switches between local dev and the deployed Render service.
// ✏️  Replace the production URL below with your Render service URL after deployment.
const BACKEND_URL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://localhost:8000"
    : "https://multilingual-ai-voice-agent-backend.onrender.com"; //<- render deploy url

const WS_URL = BACKEND_URL.startsWith("https")
    ? BACKEND_URL.replace("https://", "wss://") + "/ws/audio"
    : BACKEND_URL.replace("http://", "ws://") + "/ws/audio";
//test_audio_server.py
//const WS_URL = "ws://localhost:8765"; // Point to the test server

const MIC_RATE = 16000;
const TTS_RATE = 22050;
let ws, micCtx, micNode, micStream, playCtx, playerNode;
let isMuted = false;
const PREBUFFER_CHUNKS = 3;   // absorb ~3 chunks (~280ms @ 22050Hz/4096B) of jitter before first playback
let prebuffered = [];
let playbackStarted = false;

function logSys(msg) {
    const logs = document.getElementById("sys-logs");
    const time = new Date().toLocaleTimeString();
    logs.innerHTML += `<div class="log-entry"><span class="log-time">[${time}]</span><span class="log-content">${msg}</span></div>`;
    
    // Scroll the parent .panel-body element which holds the scrollbar settings
    if (logs.parentElement) {
        logs.parentElement.scrollTop = logs.parentElement.scrollHeight;
    }
}

let currentUserMsgDiv = null;

function handleTextData(data) {
    try {
        const payload = JSON.parse(data);

        if (payload.type === "transcript") {
            const tBox = document.getElementById("transcripts");

            if (payload.speaker === "ai") {
                tBox.innerHTML += `<div class="msg ai"><div class="speaker-label">VERTEX // AI</div>${payload.text}</div>`;
                currentUserMsgDiv = null;
            }
            else if (payload.speaker === "user") {
                if (!currentUserMsgDiv) {
                    currentUserMsgDiv = document.createElement("div");
                    currentUserMsgDiv.className = "msg user";
                    tBox.appendChild(currentUserMsgDiv);
                }
                const styleClass = payload.is_final ? "" : "partial";
                currentUserMsgDiv.innerHTML = `<div class="speaker-label">USER // VOICE</div><span class="${styleClass}">${payload.text}</span>`;
                if (payload.is_final) currentUserMsgDiv = null;
            }
            tBox.scrollTop = tBox.scrollHeight;
        }
        else if (payload.type === "metric") {
            if (payload.name.includes("STT")) {
                document.querySelector("#m-stt .metric-val").textContent = payload.value;
            } else if (payload.name.includes("LLM")) {
                document.querySelector("#m-llm .metric-val").textContent = payload.value;
            } else if (payload.name.includes("TTS")) {
                document.querySelector("#m-tts .metric-val").textContent = payload.value;
            } else if (payload.name.includes("Total")) {
                document.querySelector("#m-total .metric-val").textContent = payload.value;
            }
            logSys(`Metric: ${payload.name} = ${payload.value}`);
        }
        else if (payload.type === "error") {
            logSys(`⚠️ SYSTEM ERROR: ${payload.message}`);
            const tBox = document.getElementById("transcripts");
            if (tBox) {
                tBox.innerHTML += `<div class="msg ai" style="border-color: rgba(244, 63, 94, 0.4); background: rgba(244, 63, 94, 0.1);"><div class="speaker-label" style="color: #f43f5e;">SYSTEM // ERROR</div>${payload.message}</div>`;
                tBox.scrollTop = tBox.scrollHeight;
            }
        }
        // ---> NEW BARGE-IN LOGIC <---
        else if (payload.type === "control" && payload.action === "barge_in") {
            logSys("Barge-in detected! Stopping current AI audio.");

            // 1. Tell the Worklet to drop all buffered audio
            if (playerNode) {
                playerNode.port.postMessage({ flush: true });
            }

            // 2. Clear any pre-buffered chunks waiting to play
            prebuffered = [];
            playbackStarted = false;
        }
    } catch (e) {
        logSys("Error parsing WS JSON: " + e.message);
    }
}

const workletCode = `
class MicProcessor extends AudioWorkletProcessor {
  constructor() { super(); this._ratio = sampleRate / ${MIC_RATE}; this._acc = 0; }
  process(inputs) {
    const input = inputs[0][0]; if (!input) return true;
    const out = [];
    for (let i = 0; i < input.length; i++) {
      this._acc += 1;
      if (this._acc >= this._ratio) {
        this._acc -= this._ratio;
        const s = Math.max(-1, Math.min(1, input[i]));
        out.push(s < 0 ? s * 0x8000 : s * 0x7fff);
      }
    }
    if (out.length) { 
        const buf = new Int16Array(out); 
        this.port.postMessage(buf.buffer, [buf.buffer]); 
    }
    return true;
  }
}
registerProcessor("mic-processor", MicProcessor);

class PCMPlayerProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._buf = new Float32Array(0);
        this.port.onmessage = (e) => {
            if (e.data && e.data.flush) {
                this._buf = new Float32Array(0);
            } else if (e.data) {
                const chunk = e.data;
                const newBuf = new Float32Array(this._buf.length + chunk.length);
                newBuf.set(this._buf);
                newBuf.set(chunk, this._buf.length);
                this._buf = newBuf;
            }
        };
    }
    
  process(_inputs, outputs) {
    const out = outputs[0][0];
    if (this._buf.length >= out.length) {
      out.set(this._buf.subarray(0, out.length));
      this._buf = this._buf.subarray(out.length);
    } else {
      out.set(this._buf);
      for (let i = this._buf.length; i < out.length; i++) out[i] = 0; // silence pad, never garbage
      if (this._buf.length > 0 || this._underruns === 0) {
        this._underruns++;
        this.port.postMessage({ underrun: this._underruns });
      }
      this._buf = new Float32Array(0);
    }
    return true;
  }
}
registerProcessor("pcm-player", PCMPlayerProcessor);`;

async function startCall() {
    document.getElementById("sys-logs").innerHTML = "";
    document.getElementById("transcripts").innerHTML = "";
    document.querySelectorAll(".metric-val").forEach(el => el.textContent = "-- ms");
    logSys("Connecting to Orchestrator...");

    ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";

    playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: TTS_RATE });
    const playerUrl = URL.createObjectURL(new Blob([workletCode], { type: "application/javascript" }));
    await playCtx.audioWorklet.addModule(playerUrl);
    playerNode = new AudioWorkletNode(playCtx, "pcm-player");

    // AI Analyser Node for 3D Visualizer
    const aiAnalyser = playCtx.createAnalyser();
    aiAnalyser.fftSize = 256;
    playerNode.connect(aiAnalyser);
    aiAnalyser.connect(playCtx.destination);

    playerNode.port.onmessage = (e) => {
        if (e.data?.underrun) console.warn("Playback underrun:", e.data.underrun);
    };
    playbackStarted = false;
    prebuffered = [];

    ws.onmessage = (evt) => {
        if (typeof evt.data === "string") {
            handleTextData(evt.data);
        } else {
            feedPlayback(evt.data);
        }
    };
    ws.onclose = () => {
        logSys("WebSocket Disconnected.");
        if (window.VoiceVisualizer) {
            window.VoiceVisualizer.setCallActive(false);
        }
        document.getElementById("status-indicator").classList.remove("connected");
        document.getElementById("status-indicator-text").textContent = "Disconnected";
    };

    micStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    });

    micCtx = new (window.AudioContext || window.webkitAudioContext)();
    await micCtx.audioWorklet.addModule(playerUrl); // same module, registers mic-processor too

    const src = micCtx.createMediaStreamSource(micStream);
    micNode = new AudioWorkletNode(micCtx, "mic-processor");
    micNode.port.onmessage = (e) => { if (ws.readyState === WebSocket.OPEN) ws.send(e.data); };
    src.connect(micNode);

    // Mic Analyser Node for 3D Visualizer
    const micAnalyser = micCtx.createAnalyser();
    micAnalyser.fftSize = 256;
    src.connect(micAnalyser);

    document.getElementById("startBtn").disabled = true;
    document.getElementById("stopBtn").disabled = false;
    document.getElementById("micBtn").disabled = false;
    isMuted = false;
    document.getElementById("micBtn").textContent = "🎤 Mute";
    document.getElementById("micBtn").classList.remove("muted");

    // Initialize visualizer with active analysers
    if (window.VoiceVisualizer) {
        window.VoiceVisualizer.setCallActive(true);
        window.VoiceVisualizer.setAnalysers(micAnalyser, aiAnalyser);
        window.VoiceVisualizer.setMuted(false);
    }

    document.getElementById("status-indicator").classList.add("connected");
    document.getElementById("status-indicator-text").textContent = "Live Stream";

    logSys("Live — Listening for speech...");
}

const toggleMic = () => {
    if (!micStream) return;
    const audioTrack = micStream.getAudioTracks()[0];
    isMuted = !isMuted;
    audioTrack.enabled = !isMuted;

    const btn = document.getElementById("micBtn");
    if (isMuted) {
        btn.textContent = "🔇 Unmute";
        btn.classList.add("muted");
        logSys("Microphone muted.");
    } else {
        btn.textContent = "🎤 Mute";
        btn.classList.remove("muted");
        logSys("Microphone unmuted. Listening...");
    }

    if (window.VoiceVisualizer) {
        window.VoiceVisualizer.setMuted(isMuted);
    }
};

function decodeInt16(arrayBuffer) {
    const int16 = new Int16Array(arrayBuffer);
    const f32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        f32[i] = int16[i] / (int16[i] < 0 ? 0x8000 : 0x7fff);
    }
    return f32;
}

function feedPlayback(arrayBuffer) {
    const f32 = decodeInt16(arrayBuffer);
    if (!playbackStarted) {
        prebuffered.push(f32);
        if (prebuffered.length < PREBUFFER_CHUNKS) return;

        playbackStarted = true;
        for (const chunk of prebuffered) {
            playerNode.port.postMessage(chunk, [chunk.buffer]);
        }
        prebuffered = [];
        return;
    }
    playerNode.port.postMessage(f32, [f32.buffer]);
}

function stopCall() {
    if (micStream) micStream.getTracks().forEach(t => t.stop());
    if (micNode) micNode.disconnect();
    if (playerNode) playerNode.disconnect();
    if (micCtx) micCtx.close();
    if (playCtx) playCtx.close();
    if (ws) ws.close();

    document.getElementById("startBtn").disabled = false;
    document.getElementById("stopBtn").disabled = true;
    document.getElementById("micBtn").disabled = true;

    if (window.VoiceVisualizer) {
        window.VoiceVisualizer.setCallActive(false);
    }
    document.getElementById("status-indicator").classList.remove("connected");
    document.getElementById("status-indicator-text").textContent = "Disconnected";

    logSys("Call stopped by user.");
}

let isWaking = false;

async function checkBackendStatus() {
    const wakeBtn = document.getElementById("wake-btn");
    try {
        const response = await fetch(`${BACKEND_URL}/`);
        if (response.ok) {
            if (wakeBtn) {
                wakeBtn.style.display = "inline-flex";
                wakeBtn.className = "btn-control online";
                wakeBtn.textContent = "Server Online";
                wakeBtn.disabled = true;
            }
            return true;
        }
    } catch (e) {
        if (wakeBtn) {
            wakeBtn.style.display = "inline-flex";
            wakeBtn.className = "btn-control";
            wakeBtn.textContent = "Wake Server";
            wakeBtn.disabled = false;
        }
        logSys("Notice: Deployed backend is offline or sleeping. Click 'Wake Server' to activate it.");
    }
    return false;
}

async function wakeBackend() {
    if (isWaking) return;
    isWaking = true;

    const wakeBtn = document.getElementById("wake-btn");
    wakeBtn.className = "btn-control waking";
    wakeBtn.disabled = true;

    logSys("Initiating wake request to Render... Please wait (this can take 30-50s).");

    let attempts = 0;
    const maxAttempts = 20;

    const poll = async () => {
        attempts++;
        wakeBtn.textContent = `Waking (${attempts})`;

        try {
            const response = await fetch(`${BACKEND_URL}/`);
            if (response.ok) {
                logSys("Success! Backend has woken up.");
                wakeBtn.className = "btn-control online";
                wakeBtn.textContent = "Server Online";
                isWaking = false;
                initClerk();
                return;
            }
        } catch (e) {
            // Try again on subsequent tick
        }

        if (attempts < maxAttempts) {
            setTimeout(poll, 3000);
        } else {
            logSys("Error: Wake up timed out. Please try again or verify Render service status.");
            wakeBtn.className = "btn-control";
            wakeBtn.textContent = "Wake Server";
            wakeBtn.disabled = false;
            isWaking = false;
        }
    };

    poll();
}

async function initClerk() {
    logSys("Clerk Auth: Bypassed for local development/testing.");
    const startBtn = document.getElementById("startBtn");
    if (startBtn) {
        startBtn.disabled = false;
    }
    const authContainer = document.getElementById("auth-container");
    if (authContainer) {
        authContainer.innerHTML = '<span style="color: var(--cyan-accent); font-family: var(--font-telemetry); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em;">Auth Bypassed (Dev Mode)</span>';
    }
}

function updateAuthState(clerk) {
    const authContainer = document.getElementById("auth-container");
    const startBtn = document.getElementById("startBtn");

    if (clerk.user) {
        // User is signed in
        authContainer.innerHTML = '<div id="user-button"></div>';
        try {
            clerk.mountUserButton(document.getElementById("user-button"));
        } catch (mountError) {
            console.error("Clerk mountUserButton error:", mountError);
        }

        // Enable starting calls
        startBtn.disabled = false;

        // Safe email fallback lookup to prevent TypeErrors in dynamic transitions
        const userEmail = clerk.user.primaryEmailAddress?.emailAddress
            || (clerk.user.emailAddresses && clerk.user.emailAddresses[0]?.emailAddress)
            || clerk.user.username
            || "User";

        logSys(`Authenticated as ${userEmail}. Access granted.`);
    } else {
        // User is signed out
        authContainer.innerHTML = '<button id="signin-btn" class="btn-control">Sign In</button>';

        // Disable starting calls
        startBtn.disabled = true;

        const signInBtn = document.getElementById("signin-btn");
        if (signInBtn) {
            signInBtn.onclick = () => {
                try {
                    // In-website login flow (Modal pop-up)
                    clerk.openSignIn({
                        signInForceRedirectUrl: window.location.href,
                        signUpForceRedirectUrl: window.location.href
                    });

                    // To revert to hosted sign-in page redirect, comment out openSignIn above and uncomment below:
                    /*
                    clerk.redirectToSignIn({
                        redirectUrl: window.location.href
                    });
                    */
                } catch (err) {
                    logSys("Error during sign in action: " + err.message);
                }
            };
        }

        logSys("Verification required: Please Sign In to access the Voice Agent console.");
    }
}

// Bind handlers when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
    if (window.VoiceVisualizer) {
        window.VoiceVisualizer.init('visualizer-canvas');
    }

    document.getElementById("startBtn").onclick = startCall;
    document.getElementById("stopBtn").onclick = stopCall;
    document.getElementById("micBtn").onclick = toggleMic;

    const wakeBtn = document.getElementById("wake-btn");
    if (wakeBtn) {
        wakeBtn.onclick = wakeBackend;
    }

    // Check backend first. If online, initialize Clerk, otherwise wait for wake-btn click
    checkBackendStatus().then(online => {
        if (online) {
            initClerk();
        }
    });
});

/**
 * 3D Particle Wave Visualizer - VERTEX/studio Edition
 * Renders a glowing 3D perspective grid of particles that breathes and
 * reacts dynamically to microphone input and AI audio stream.
 */

window.VoiceVisualizer = (function() {
    let canvas, ctx;
    let animationFrameId = null;
    
    // Grid settings
    const COLS = 35;
    const ROWS = 20;
    const focalLength = 300;
    
    // Physics & Wave States
    let time = 0;
    let state = 'idle'; // 'idle', 'listening', 'speaking'
    let isCallActive = false;
    let isMuted = false;
    
    // Audio Analysers
    let micAnalyser = null;
    let aiAnalyser = null;
    let micData = null;
    let aiData = null;
    
    // Grid coordinates cache
    const particles = [];
    
    function init(canvasId) {
        canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        ctx = canvas.getContext('2d');
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        
        // Setup initial particles
        particles.length = 0;
        for (let r = 0; r < ROWS; r++) {
            for (let c = 0; c < COLS; c++) {
                particles.push({
                    u: c / (COLS - 1) - 0.5, // -0.5 to 0.5
                    v: r / (ROWS - 1),       // 0 to 1 (depth)
                    y: 0
                });
            }
        }
        
        startAnimation();
    }
    
    function resizeCanvas() {
        if (!canvas) return;
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width * window.devicePixelRatio;
        canvas.height = rect.height * window.devicePixelRatio;
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }
    
    function setAnalysers(mic, ai) {
        micAnalyser = mic;
        aiAnalyser = ai;
        if (micAnalyser) {
            micData = new Uint8Array(micAnalyser.frequencyBinCount);
        }
        if (aiAnalyser) {
            aiData = new Uint8Array(aiAnalyser.frequencyBinCount);
        }
    }
    
    function setMuted(muted) {
        isMuted = muted;
    }
    
    function setCallActive(active) {
        isCallActive = active;
        if (!active) {
            state = 'idle';
            micAnalyser = null;
            aiAnalyser = null;
            micData = null;
            aiData = null;
        }
    }
    
    function getAverageVolume(array) {
        let values = 0;
        let length = array.length;
        for (let i = 0; i < length; i++) {
            values += array[i];
        }
        return values / length;
    }
    
    function updateAudioState() {
        if (!isCallActive) {
            state = 'idle';
            return;
        }
        
        let micVolume = 0;
        let aiVolume = 0;
        
        if (micAnalyser && micData && !isMuted) {
            micAnalyser.getByteFrequencyData(micData);
            micVolume = getAverageVolume(micData) / 255;
        }
        
        if (aiAnalyser && aiData) {
            aiAnalyser.getByteFrequencyData(aiData);
            aiVolume = getAverageVolume(aiData) / 255;
        }
        
        // Determine state based on signal strengths
        if (aiVolume > 0.02) {
            state = 'speaking';
        } else if (micVolume > 0.02) {
            state = 'listening';
        } else {
            state = 'idle';
        }
        
        // Update HTML container speaking classes
        const panel = document.querySelector('.visualizer-panel');
        if (panel) {
            panel.classList.remove('listening', 'speaking');
            if (state === 'listening') {
                panel.classList.add('listening');
            } else if (state === 'speaking') {
                panel.classList.add('speaking');
            }
        }
        
        // Update indicator text in UI
        const stateText = document.getElementById('visualizer-state-text');
        if (stateText) {
            if (!isCallActive) {
                stateText.textContent = 'STANDBY';
            } else if (state === 'listening') {
                stateText.textContent = 'LISTENING';
            } else if (state === 'speaking') {
                stateText.textContent = 'SPEAKING';
            } else {
                stateText.textContent = 'LIVE';
            }
        }
    }
    
    function draw() {
        if (!canvas || !ctx) return;
        
        const w = canvas.width / window.devicePixelRatio;
        const h = canvas.height / window.devicePixelRatio;
        
        // Clear canvas with Void Black
        ctx.fillStyle = '#000000';
        ctx.fillRect(0, 0, w, h);
        
        updateAudioState();
        
        // Animation variables
        const speed = state === 'listening' ? 0.08 : state === 'speaking' ? 0.05 : 0.02;
        time += speed;
        
        const centerX = w / 2;
        const centerY = h / 2 + 60; // offset down for perspective
        
        // VERTEX Color Theme Config
        let colorTheme;
        if (state === 'listening') {
            // User speaking: VERTEX Cyan Accent & Electric Blue glow
            colorTheme = {
                r: 0, g: 198, b: 255,   // #00c6ff
                r2: 0, g2: 112, b2: 243  // #0070f3
            };
        } else if (state === 'speaking') {
            // AI speaking: VERTEX Violet Depth & Rose Accent
            colorTheme = {
                r: 121, g: 40, b: 202,  // #7928ca
                r2: 255, g2: 0, b2: 128  // #ff0080
            };
        } else {
            // Standby / Idle: Subdued Slate Cyan
            colorTheme = {
                r: 71, g: 85, b: 105,    // #475569
                r2: 0, g2: 198, b2: 255  // #00c6ff
            };
        }
        
        // 1. Calculate heights & project to 2D
        const projectedPoints = [];
        
        particles.forEach((p, idx) => {
            const col = idx % COLS;
            const row = Math.floor(idx / COLS);
            
            // Core wave mathematics
            let baseY = Math.sin(p.u * 6 + time) * Math.cos(p.v * 5 - time * 0.8) * 15;
            baseY += Math.sin(p.u * 12 - time * 1.5) * 5;
            
            let audioHeight = 0;
            
            if (state === 'listening' && micData) {
                const centerCol = (COLS - 1) / 2;
                const normalizedDist = Math.abs(col - centerCol) / centerCol;
                
                const binIndex = Math.floor(normalizedDist * 14) + 1; 
                const amp = (micData[binIndex] / 255) * 65;
                
                const envelope = Math.cos(normalizedDist * Math.PI / 2);
                audioHeight = Math.sin(p.v * Math.PI + time * 3.5) * amp * envelope;
            } else if (state === 'speaking' && aiData) {
                const centerCol = (COLS - 1) / 2;
                const normalizedDist = Math.abs(col - centerCol) / centerCol;
                
                const binIndex = Math.floor(normalizedDist * 14) + 1;
                const amp = (aiData[binIndex] / 255) * 75;
                
                const envelope = Math.cos(normalizedDist * Math.PI / 2);
                audioHeight = Math.cos(p.v * Math.PI + time * 2.5) * amp * envelope;
            } else if (isCallActive) {
                baseY *= 1.2;
            }
            
            const totalY = baseY + audioHeight;
            
            const x3d = p.u * 500;
            const z3d = p.v * 300 + 80;
            const y3d = totalY;
            
            // Perspective projection
            const scale = focalLength / (focalLength + z3d);
            const screenX = centerX + x3d * scale;
            const screenY = centerY - y3d * scale;
            
            projectedPoints.push({
                x: screenX,
                y: screenY,
                scale: scale,
                depth: p.v
            });
        });
        
        // 2. Draw connections (Grid lines) for tech wireframe effect
        ctx.lineWidth = 0.5;
        
        for (let r = 0; r < ROWS; r++) {
            for (let c = 0; c < COLS; c++) {
                const idx = r * COLS + c;
                const p1 = projectedPoints[idx];
                
                const depthAlpha = (1 - p1.depth) * 0.6;
                const alpha = p1.scale * depthAlpha * 0.18;
                
                ctx.strokeStyle = `rgba(${colorTheme.r}, ${colorTheme.g}, ${colorTheme.b}, ${alpha})`;
                
                if (c < COLS - 1) {
                    const p2 = projectedPoints[idx + 1];
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
                
                if (r < ROWS - 1) {
                    const p2 = projectedPoints[idx + COLS];
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        }
        
        // 3. Draw particles (Glowing circles)
        projectedPoints.forEach((p) => {
            const depthFactor = 1 - p.depth;
            const size = p.scale * (1.5 + depthFactor * 2);
            
            const baseAlpha = p.scale * depthFactor * 0.85;
            
            // Outer glow
            ctx.fillStyle = `rgba(${colorTheme.r2}, ${colorTheme.g2}, ${colorTheme.b2}, ${baseAlpha * 0.25})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, size * 2.5, 0, Math.PI * 2);
            ctx.fill();
            
            // Inner core
            ctx.fillStyle = `rgba(${colorTheme.r}, ${colorTheme.g}, ${colorTheme.b}, ${baseAlpha})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            ctx.fill();
        });
        
        animationFrameId = requestAnimationFrame(draw);
    }
    
    function startAnimation() {
        if (!animationFrameId) {
            draw();
        }
    }
    
    function stopAnimation() {
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
        }
    }
    
    return {
        init: init,
        setAnalysers: setAnalysers,
        setMuted: setMuted,
        setCallActive: setCallActive,
        start: startAnimation,
        stop: stopAnimation
    };
})();

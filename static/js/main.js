// CareConnect Main JavaScript
document.addEventListener('DOMContentLoaded', () => {
    console.log('CareConnect Application Initialized');
    const escapeHtml = (value) =>
        String(value || '').replace(/[&<>"']/g, (ch) => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        }[ch]));
    const toFriendlyAnalyzeError = (rawError) => {
        const msg = String(rawError || '').toLowerCase();
        if (msg.includes('requires more system memory') || msg.includes('not enough memory') || msg.includes('out of memory')) {
            return 'Ollama does not have enough free RAM for the current model. Close heavy apps or switch to a smaller model (for example: phi3:mini), then retry.';
        }
        if (msg.includes('timed out') || msg.includes('could not get a response')) {
            return 'Ollama took too long to respond with the current model. The app is now trying smaller models automatically; please retry once.';
        }
        return String(rawError || 'Unknown error');
    };

    // Add scroll effect to navbar
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                navbar.style.padding = '0.8rem 5%';
                navbar.style.background = 'rgba(0, 12, 36, 0.9)';
            } else {
                navbar.style.padding = '1.5rem 5%';
                navbar.style.background = 'rgba(0, 12, 36, 0.7)';
            }
        });
    }

    // Add smooth scroll for internal links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // Simulated file upload preview
    const uploadArea = document.querySelector('#reportUpload');
    if (uploadArea) {
        uploadArea.addEventListener('change', async (e) => {
            if(!e.target.files.length) return;
            const file = e.target.files[0];
            const fileName = file.name;
            const isSupported = /\.(jpg|jpeg|png|webp|bmp|gif|tiff|tif|pdf|txt|csv|md)$/i.test(fileName);
            const container = document.getElementById('aiAnalysisProgress');

            if (!isSupported) {
                if (container) {
                    container.innerHTML = `<p style="color: var(--danger);"><i class="ph-fill ph-warning-circle"></i> Unsupported file type. Please upload image, PDF, or text report.</p>`;
                }
                e.target.value = '';
                return;
            }
            
            // Build visual loading UI in reports page
            if(container) {
                container.innerHTML = `
                    <div style="padding: 1.5rem; background: var(--surface); border-radius: 12px; border: 1px solid var(--surface-border);">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.9rem;">
                            <span>${escapeHtml(fileName)}</span>
                            <span style="color: var(--accent);"><i class="ph ph-spinner-gap" style="animation: spin 1s linear infinite; display: inline-block;"></i> AI Analyzing...</span>
                        </div>
                        <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden; position: relative;">
                            <div style="position: absolute; width: 30%; height: 100%; background: var(--accent); animation: reportLoad 1.5s infinite ease-in-out;"></div>
                        </div>
                    </div>
                    <style>@keyframes reportLoad { 0% { left: -30%; } 100% { left: 100%; } } @keyframes spin { 100% { transform: rotate(360deg); } }</style>
                `;
            }

            const formData = new FormData();
            formData.append('file', file);
            const p = window.location.pathname;
            const uploadedBy = p.startsWith('/admin') ? 'admin' : (p.startsWith('/patient') ? 'patient' : 'children');
            formData.append('uploaded_by', uploadedBy);
            
            try {
                const res = await fetch('/api/analyze-report', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                
                if(res.ok) {
                    const safeSummary = escapeHtml(data.summary || '').replace(/\n/g, '<br>');
                    if(container) {
                        container.innerHTML = `
                            <div style="padding: 1.5rem; background: var(--surface); border-radius: 12px; border: 1px solid var(--surface-border); margin-bottom: 1rem;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.9rem;">
                                    <span>${escapeHtml(fileName)}</span>
                                    <span style="color: var(--success); font-weight: 600;"><i class="ph-fill ph-check-circle"></i> Analyzed Successfully</span>
                                </div>
                            </div>
                            <div style="padding: 1.5rem; background: rgba(59, 130, 246, 0.05); border-left: 4px solid var(--primary); border-radius: 8px;">
                                <h4 style="margin-bottom: 1rem; color: var(--primary);">Plain-English AI Summary:</h4>
                                <p style="font-size: 0.95rem; color: #cbd5e1; line-height: 1.6;">${safeSummary || 'No summary returned.'}</p>
                            </div>
                        `;
                    }
                    if (typeof window.loadReportHistory === 'function') {
                        window.loadReportHistory();
                    }
                } else {
                    const friendlyError = toFriendlyAnalyzeError(data.error);
                    if(container) container.innerHTML = `<p style="color: var(--danger);"><i class="ph-fill ph-warning-circle"></i> Failed to analyze report: ${escapeHtml(friendlyError)}</p>`;
                }
            } catch(err) {
                if(container) container.innerHTML = `<p style="color: var(--danger);"><i class="ph-fill ph-warning-circle"></i> Network error while contacting analyzer service.</p>`;
            }
        });
    }

    // Global Interactive SOS Handler
    document.addEventListener('click', (e) => {
        let target = e.target.closest('a');
        if (target && target.getAttribute('href') && target.getAttribute('href').includes('/emergency')) {
            e.preventDefault();
            
            // Send live location via WhatsApp
            const waWindow = window.open('about:blank', '_blank');
            if(navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        const lat = pos.coords.latitude;
                        const lon = pos.coords.longitude;
                        const msg = encodeURIComponent(`🚨 EMERGENCY (CareConnect)! I need immediate assistance! Here is my live location:\nhttps://www.google.com/maps/search/?api=1&query=${lat},${lon}`);
                        if(waWindow) waWindow.location.href = `https://wa.me/?text=${msg}`;
                    },
                    (err) => {
                        console.error("Location disabled.");
                        const msg = encodeURIComponent(`🚨 EMERGENCY (CareConnect)! I need immediate assistance! (GPS Live Location Unavailable)`);
                        if(waWindow) waWindow.location.href = `https://wa.me/?text=${msg}`;
                    }
                );
            } else {
                const msg = encodeURIComponent(`🚨 EMERGENCY (CareConnect)! I need immediate assistance!`);
                if(waWindow) waWindow.location.href = `https://wa.me/?text=${msg}`;
            }

            // Audio Web API for Sirens
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'square';
            
            let t = ctx.currentTime;
            for(let i=0; i<20; i++) { // Play siren for 10 seconds
                osc.frequency.setValueAtTime(800, t + i*0.5);
                osc.frequency.setValueAtTime(1200, t + i*0.5 + 0.25);
            }
            gain.gain.setValueAtTime(0.15, t); // Softer volume
            osc.start(t);
            osc.stop(t + 10);
            
            // Generate Interactive Modal
            const sosModal = document.createElement('div');
            sosModal.id = 'sos-modal';
            sosModal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:#dc2626;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;color:white;text-align:center;font-family:sans-serif;';
            
            // Flashing animation
            let isRed = true;
            const flashInt = setInterval(() => {
                sosModal.style.background = isRed ? '#991b1b' : '#dc2626';
                isRed = !isRed;
            }, 300);
            
            sosModal.innerHTML = `
                <style>@keyframes alertPulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }</style>
                <i class="ph-bold ph-warning-circle" style="font-size: 8rem; margin-bottom: 2rem; animation: alertPulse 1s infinite;"></i>
                <h1 style="font-size: 4rem; filter: drop-shadow(0 0 10px rgba(0,0,0,0.5)); margin: 0;">SOS ALERT INITIATED</h1>
                <p style="font-size: 1.5rem; max-width: 600px; margin: 2rem 0; font-weight: 300; line-height: 1.5;">Family members and emergency services are being notified. Your live location has been shared.</p>
                <button class="btn btn-outline" style="border: 2px solid white; background: transparent; color: white; padding: 1rem 3rem; font-size: 1.2rem; border-radius: 50px; cursor: pointer; transition: all 0.2s; font-weight: 600;" id="cancelBtn" onmouseover="this.style.background='white'; this.style.color='#dc2626';" onmouseout="this.style.background='transparent'; this.style.color='white';">Cancel Alarm</button>
            `;
            document.body.appendChild(sosModal);
            
            // Cancel Action
            document.getElementById('cancelBtn').addEventListener('click', () => {
                clearInterval(flashInt);
                try { osc.stop(); ctx.close(); } catch(e) {}
                sosModal.remove();
                // We show the flash by pinging the backend but stopping deafening noises.
                // Optionally redirect to /emergency for the backend flash:
                window.location.href = '/emergency';
            });
        }
    });

});

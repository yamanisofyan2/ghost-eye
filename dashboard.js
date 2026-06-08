// SIEM Dashboard Javascript Logic
document.addEventListener("DOMContentLoaded", () => {
    
    // --- 1. INITIALIZE LEAFLET MAP ---
    const map = L.map('map', {
        zoomControl: true,
        attributionControl: false
    }).setView([20, 0], 2);

    // CartoDB Dark Matter tile layer for dark styling
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    const markerGroup = L.layerGroup().addTo(map);

    // --- 2. INITIALIZE CHART.JS VISUALIZERS ---
    // Threat Level Doughnut Chart
    const ctxThreat = document.getElementById('threatChart').getContext('2d');
    const threatChart = new Chart(ctxThreat, {
        type: 'doughnut',
        data: {
            labels: ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
            datasets: [{
                data: [0, 0, 0, 0, 0],
                backgroundColor: [
                    '#a4b0be', // INFO
                    '#2ed573', // LOW
                    '#ffa502', // MEDIUM
                    '#ff4757', // HIGH
                    '#ff2e44'  // CRITICAL
                ],
                borderWidth: 1,
                borderColor: '#070a13'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#a4b0be',
                        font: { size: 10, family: 'Inter' }
                    }
                }
            },
            cutout: '65%'
        }
    });

    // Trend Line Chart
    const ctxTrend = document.getElementById('trendChart').getContext('2d');
    const trendChart = new Chart(ctxTrend, {
        type: 'line',
        data: {
            labels: [], // Timestamps
            datasets: [{
                label: 'Kompilasi / Minit',
                data: [],
                borderColor: '#00bfff',
                backgroundColor: 'rgba(0, 191, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#a4b0be', font: { size: 9 }, maxTicksLimit: 6 }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#a4b0be', font: { size: 10 }, stepSize: 1, beginAtZero: true }
                }
            }
        }
    });

    // --- 3. AJAX POLLING & STATS REFRESHER ---
    let lastLogCount = 0;
    let lastLatestLogId = null;

    async function fetchStatsAndLogs() {
        const refreshIndicator = document.getElementById("refresh-indicator");
        refreshIndicator.style.opacity = "1";

        try {
            // Fetch stats
            const statsRes = await fetch("/api/stats");
            if (statsRes.ok) {
                const stats = await statsRes.json();
                
                // Update top cards values
                document.getElementById("stats-total-compiles").textContent = stats.total_compiles;
                document.getElementById("stats-active-countries").textContent = Object.keys(stats.country_counts).length;
                
                const criticalAndHigh = (stats.threat_counts["CRITICAL"] || 0) + (stats.threat_counts["HIGH"] || 0);
                document.getElementById("stats-critical-alerts").textContent = criticalAndHigh;

                // Update Threat Chart
                threatChart.data.datasets[0].data = [
                    stats.threat_counts["INFO"] || 0,
                    stats.threat_counts["LOW"] || 0,
                    stats.threat_counts["MEDIUM"] || 0,
                    stats.threat_counts["HIGH"] || 0,
                    stats.threat_counts["CRITICAL"] || 0
                ];
                threatChart.update();
            }

            // Fetch logs
            const logsRes = await fetch("/api/logs?limit=30");
            if (logsRes.ok) {
                const logs = await logsRes.json();
                
                // Track synced offline logs count
                const syncedCount = logs.filter(l => l.is_offline_log === 1).length;
                document.getElementById("stats-synced-logs").textContent = syncedCount;

                // Populate logs table
                const tbody = document.getElementById("logs-tbody");
                
                if (logs.length === 0) {
                    tbody.innerHTML = `
                        <tr class="no-logs-row">
                            <td colspan="5" class="text-center">No logs received yet. Click Compile on the Agent or use God Mode!</td>
                        </tr>
                    `;
                    markerGroup.clearLayers();
                    updateTrendChart([]);
                    lastLogCount = 0;
                    lastLatestLogId = null;
                    return;
                }

                // If log count changes or new logs arrive, update map markers
                const isNewLog = lastLatestLogId !== logs[0].id;
                
                if (logs.length !== lastLogCount || isNewLog) {
                    markerGroup.clearLayers();
                    
                    let tableHtml = "";
                    let latestMarker = null;

                    logs.forEach((log, idx) => {
                        // Plot map marker
                        if (log.latitude && log.longitude) {
                            const isCritical = log.threat_level === "CRITICAL" || log.threat_level === "HIGH";
                            const pulseClass = isCritical ? 'custom-map-marker level-critical' : 'custom-map-marker';
                            
                            const customIcon = L.divIcon({
                                className: pulseClass,
                                iconSize: [12, 12],
                                iconAnchor: [6, 6]
                            });

                            const popupContent = `
                                <div style="font-family: 'Inter', sans-serif; font-size: 11px; color:#333;">
                                    <b>${log.filename}</b> (${log.threat_level})<br>
                                    📍 ${log.city}, ${log.country}<br>
                                    👤 User: ${log.username}<br>
                                    ⏰ Time: ${formatDate(log.timestamp)}
                                </div>
                            `;

                            const marker = L.marker([log.latitude, log.longitude], { icon: customIcon })
                                .bindPopup(popupContent)
                                .addTo(markerGroup);

                            // Save reference to the latest marker if it's new
                            if (idx === 0) {
                                latestMarker = marker;
                            }
                        }

                        // Build table row HTML
                        const timeStr = formatDate(log.timestamp);
                        const sizeKb = (log.filesize / 1024).toFixed(1) + " KB";
                        const syncedLabel = currentLang === 'en' ? 'SYNCED' : 'DISEGERAK';
                        const offlineTag = log.is_offline_log ? `<span class="sync-badge"><i class="fa-solid fa-cloud-arrow-down"></i> ${syncedLabel}</span>` : '';
                        
                        tableHtml += `
                            <tr>
                                <td class="time-col">${timeStr} ${offlineTag}</td>
                                <td>
                                    <div class="file-info">
                                         <span class="file-name" title="${log.filename}">${truncateText(log.filename, 22)}</span>
                                         <span class="file-size">${sizeKb} | SHA-256: ${log.filehash_sha256.substring(0, 8)}... | MD5: ${log.filehash_md5.substring(0, 8)}...</span>
                                     </div>
                                </td>
                                <td>
                                    <div class="sys-info">
                                        <span class="sys-user"><i class="fa-solid fa-user-ninja"></i> ${log.username}</span>
                                        <span class="sys-host"><i class="fa-solid fa-laptop-code"></i> ${log.hostname} (${log.os_info.split(" ")[0]})</span>
                                    </div>
                                </td>
                                <td>
                                    <div class="ip-info">
                                        <span class="ip-addr">${log.ip}</span>
                                        <span class="country-lbl">${getCountryFlag(log.country)} ${log.country}</span>
                                    </div>
                                </td>
                                <td>
                                    <span class="badge level-${log.threat_level.toLowerCase()}">${log.threat_level}</span>
                                </td>
                            </tr>
                        `;
                    });

                    tbody.innerHTML = tableHtml;
                    lastLogCount = logs.length;
                    
                    // Auto-focus and open popup bubble on latest log if it's new
                    if (isNewLog && logs[0].latitude && logs[0].longitude) {
                        map.flyTo([logs[0].latitude, logs[0].longitude], 4, { 
                            animate: true, 
                            duration: 1.2 
                        });
                        
                        // Open popup bubble slightly after map starts flying
                        setTimeout(() => {
                            if (latestMarker) {
                                latestMarker.openPopup();
                            }
                        }, 800);
                    }
                    
                    lastLatestLogId = logs[0].id;
                    
                    // Update the trend chart
                    updateTrendChart(logs);
                }
            }
        } catch (err) {
            console.error("Error updating dashboard:", err);
        } finally {
            setTimeout(() => {
                refreshIndicator.style.opacity = "0.5";
            }, 500);
        }
    }

    // Process logs to group by minutes for trend chart
    function updateTrendChart(logs) {
        if (!logs || logs.length === 0) {
            trendChart.data.labels = [];
            trendChart.data.datasets[0].data = [];
            trendChart.update();
            return;
        }

        // Group events by minute
        const minuteBuckets = {};
        
        // Take recent logs and bucket them
        logs.slice().reverse().forEach(log => {
            try {
                // Parse timestamp and extract hour:minute
                // Support format like '2026-05-23T22:40:57.1234'
                const t = new Date(log.timestamp);
                if (isNaN(t.getTime())) return;
                
                const timeLabel = t.toTimeString().substring(0, 5); // "HH:MM"
                minuteBuckets[timeLabel] = (minuteBuckets[timeLabel] || 0) + 1;
            } catch (e) {}
        });

        const labels = Object.keys(minuteBuckets);
        const data = Object.values(minuteBuckets);

        trendChart.data.labels = labels;
        trendChart.data.datasets[0].data = data;
        trendChart.update();
    }

    // Helper functions
    function formatDate(isoStr) {
        try {
            const date = new Date(isoStr);
            if (isNaN(date.getTime())) return isoStr;
            return date.toLocaleTimeString() + " " + date.toLocaleDateString();
        } catch (e) {
            return isoStr;
        }
    }

    // Truncate long strings
    function truncateText(text, maxLen) {
        if (text.length > maxLen) {
            return text.substring(0, maxLen - 3) + "...";
        }
        return text;
    }

    // Flags mapping
    function getCountryFlag(country) {
        const flags = {
            "Malaysia": "🇲🇾",
            "Russia": "🇷🇺",
            "China": "🇨🇳",
            "United States": "🇺🇸",
            "North Korea": "🇰🇵",
            "Germany": "🇩🇪",
            "Iran": "🇮🇷",
            "Brazil": "🇧🇷"
        };
        return flags[country] || "🌐";
    }

    // --- 4. GOD MODE HANDLERS ---
    const countryIPs = {
        "Malaysia": "1.9.0.1",
        "Russia": "95.213.255.1",
        "China": "1.1.1.1",
        "United States": "8.8.8.8",
        "North Korea": "175.45.176.1",
        "Germany": "82.165.1.1",
        "Iran": "5.160.1.1",
        "Brazil": "200.221.2.1"
    };

    const mockFiles = [
        "ransom_crypt.exe", "keylogger_srv.cpp", "process_injector.py", "shell_loader.bin",
        "reverse_shell.c", "credential_stealer.py", "sys_backdoor.cpp", "rootkit.sys",
        "calc_payload.exe", "http_ddos_bot.py"
    ];

    const mockUsers = ["admin", "root", "dev_mal", "tester", "build_agent", "cyber_attacker"];
    const mockHosts = ["WS-DEV-01", "LINUX-BUILD-SRV", "TEST-BOX-WIN10", "PROD-SERVER-04", "LAPTOP-HACKER"];
    const mockOS = ["Windows 11 Pro", "Ubuntu 22.04 LTS", "Kali Linux 2024.1", "Windows Server 2022", "macOS Sonoma"];

    // Trigger Single Mock Log
    document.getElementById("btn-trigger-single").addEventListener("click", async () => {
        const country = document.getElementById("god-country").value;
        const threat = document.getElementById("god-threat").value;
        const filename = document.getElementById("god-filename").value.trim() || "simulated_compile.cpp";
        const status = document.getElementById("god-status").value;

        // Generate mock payload
        const randomUser = mockUsers[Math.floor(Math.random() * mockUsers.length)];
        const randomHost = mockHosts[Math.floor(Math.random() * mockHosts.length)];
        const randomOS = mockOS[Math.floor(Math.random() * mockOS.length)];
        const randomSHA256 = Array.from({length: 64}, () => Math.floor(Math.random()*16).toString(16)).join('');
        const randomMD5 = Array.from({length: 32}, () => Math.floor(Math.random()*16).toString(16)).join('');
        const randomSize = Math.floor(Math.random() * 50000) + 1024;
        
        let ip = "127.0.0.1";
        if (country !== "auto" && countryIPs[country]) {
            ip = countryIPs[country];
        }

        const payload = {
            timestamp: new Date().toISOString(),
            filename: filename,
            filesize: randomSize,
            filehash_sha256: randomSHA256,
            filehash_md5: randomMD5,
            compiler_flags: "-O2 -Wall -static",
            ip: ip,
            hostname: randomHost,
            username: randomUser,
            os_info: randomOS,
            is_offline_log: false,
            status: status,
            threat_level: threat,
            mocked_country: country,
            mocked_ip: ip
        };

        try {
            const res = await fetch("/api/telemetry", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "X-GhostEye-Token": "gho_secret_auth_token_2026"
                },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                // Refresh dashboard immediately
                await fetchStatsAndLogs();
            } else {
                alert(translations[currentLang]["alert-failed-send"]);
            }
        } catch (e) {
            console.error(e);
            alert("Error: " + e.message);
        }
    });

    // Bulk Simulation (10 Logs)
    document.getElementById("btn-trigger-bulk").addEventListener("click", () => {
        const btn = document.getElementById("btn-trigger-bulk");
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${translations[currentLang]["btn-bulk-simulating"]}`;

        let count = 0;
        const total = 10;
        
        function sendMockLog() {
            if (count >= total) {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-bolt"></i> <span data-i18n="btn-bulk">${translations[currentLang]["btn-bulk"]}</span>`;
                return;
            }

            // Pick random country from keys, excluding "auto"
            const countries = Object.keys(countryIPs);
            const country = countries[Math.floor(Math.random() * countries.length)];
            const ip = countryIPs[country];
            
            const threats = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
            const threatWeights = ["INFO", "LOW", "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL"];
            const threat = threatWeights[Math.floor(Math.random() * threatWeights.length)];
            
            const filename = mockFiles[Math.floor(Math.random() * mockFiles.length)];
            const status = Math.random() > 0.1 ? "SUCCESS" : "FAILED";
            const randomUser = mockUsers[Math.floor(Math.random() * mockUsers.length)];
            const randomHost = mockHosts[Math.floor(Math.random() * mockHosts.length)];
            const randomOS = mockOS[Math.floor(Math.random() * mockOS.length)];
            const randomSHA256 = Array.from({length: 64}, () => Math.floor(Math.random()*16).toString(16)).join('');
            const randomMD5 = Array.from({length: 32}, () => Math.floor(Math.random()*16).toString(16)).join('');
            const randomSize = Math.floor(Math.random() * 85000) + 2048;

            const timeOffsetMs = (total - count) * 60 * 1000;
            const timestamp = new Date(Date.now() - timeOffsetMs).toISOString();

            const payload = {
                timestamp: timestamp,
                filename: filename,
                filesize: randomSize,
                filehash_sha256: randomSHA256,
                filehash_md5: randomMD5,
                compiler_flags: "-O3 -s",
                ip: ip,
                hostname: randomHost,
                username: randomUser,
                os_info: randomOS,
                is_offline_log: Math.random() > 0.8,
                status: status,
                threat_level: threat,
                mocked_country: country,
                mocked_ip: ip
            };

            fetch("/api/telemetry", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "X-GhostEye-Token": "gho_secret_auth_token_2026"
                },
                body: JSON.stringify(payload)
            }).then(() => {
                fetchStatsAndLogs();
                count++;
                setTimeout(sendMockLog, 450);
            }).catch(err => {
                console.error(err);
                count++;
                sendMockLog();
            });
        }

        sendMockLog();
    });

    // Reset Database
    document.getElementById("btn-reset-db").addEventListener("click", async () => {
        if (confirm(translations[currentLang]["confirm-clear"])) {
            try {
                const res = await fetch("/api/reset", { method: "POST" });
                if (res.ok) {
                    await fetchStatsAndLogs();
                } else {
                    alert(translations[currentLang]["alert-failed-clear"]);
                }
            } catch (e) {
                alert("Error: " + e.message);
            }
        }
    });

    // --- 5. BILINGUAL / LOCALIZATION ENGINE ---
    const translations = {
        en: {
            subtitle: "Compiler-Level Threat Intelligence & Telemetry Dashboard",
            "stats-total": "Total Compilations",
            "stats-critical": "Critical & High Alerts",
            "stats-countries": "Countries Detected",
            "stats-offline": "Synced Logs (Offline)",
            "map-title": "Global Compilation Telemetry Map (GeoIP)",
            "threat-title": "Threat Classification",
            "trend-title": "Activity Trends",
            "god-title": "God Mode Control Panel (PoC Simulator)",
            "god-desc": "Use this panel to instantly simulate compiler telemetry from various parts of the world without writing code.",
            "god-country": "Simulate Country",
            "god-country-auto": "Auto (Use Real IP)",
            "god-threat": "Threat Level",
            "god-threat-info": "INFO (Normal)",
            "god-threat-high": "HIGH (Danger)",
            "god-threat-critical": "CRITICAL",
            "god-filename": "Source File Name",
            "god-status": "Compilation Status",
            "btn-single": "Send Single Log",
            "btn-bulk": "Bulk Simulation (10 Logs)",
            "btn-reset": "Clear GhostEye Database",
            "table-title": "Recent Telemetry Logs Feed",
            "table-status": "Monitoring...",
            "th-time": "Timestamp",
            "th-file": "File Metadata",
            "th-sys": "Build System",
            "th-ip": "IP / Country",
            "th-threat": "Threat",
            "no-logs": "No logs received yet. Click Compile on the Agent or use God Mode!",
            "alert-failed-send": "Failed to send mock telemetry.",
            "btn-bulk-simulating": "Simulating...",
            "confirm-clear": "Are you sure you want to clear all logs from the GhostEye database?",
            "alert-failed-clear": "Failed to clear database.",
            "system-active": "SYSTEM ACTIVE"
        },
        bm: {
            subtitle: "Dashboard Pencerobohan Telemetri & Risik Ancaman Peringkat Kompilator",
            "stats-total": "Jumlah Kompilasi",
            "stats-critical": "Alert Kritikal & Tinggi",
            "stats-countries": "Negara Dikesan",
            "stats-offline": "Log Disegerak (Offline)",
            "map-title": "Peta Telemetri Kompilasi Global (GeoIP)",
            "threat-title": "Klasifikasi Ancaman",
            "trend-title": "Trend Aktiviti",
            "god-title": "Panel Kawalan God Mode (Simulator PoC)",
            "god-desc": "Gunakan panel ini untuk mensimulasikan telemetri kompilasi dari pelbagai pelusuk dunia secara serta-merta tanpa menulis kod.",
            "god-country": "Simulasi Negara",
            "god-country-auto": "Auto (Guna IP Sebenar)",
            "god-threat": "Tahap Ancaman",
            "god-threat-info": "INFO (Biasa)",
            "god-threat-high": "HIGH (Bahaya)",
            "god-threat-critical": "CRITICAL (Kritikal)",
            "god-filename": "Nama Fail Kod",
            "god-status": "Status Kompilasi",
            "btn-single": "Hantar Log Tunggal",
            "btn-bulk": "Simulasi Pukal (10 Log)",
            "btn-reset": "Kosongkan Database GhostEye",
            "table-title": "Aliran Log Telemetri Terkini",
            "table-status": "Memantau...",
            "th-time": "Masa",
            "th-file": "Maklumat Fail",
            "th-sys": "Sistem Pembina",
            "th-ip": "IP / Negara",
            "th-threat": "Ancaman",
            "no-logs": "Tiada log diterima lagi. Klik Compile pada Ejen atau guna God Mode!",
            "alert-failed-send": "Gagal menghantar mock telemetry.",
            "btn-bulk-simulating": "Mensimulasikan...",
            "confirm-clear": "Adakah anda pasti mahu memadam semua log dalam database GhostEye?",
            "alert-failed-clear": "Gagal mengosongkan database.",
            "system-active": "SISTEM AKTIF"
        }
    };

    let currentLang = localStorage.getItem('ghosteye_lang') || 'en';

    function applyLanguage(lang) {
        document.querySelectorAll("[data-i18n]").forEach(elem => {
            const key = elem.getAttribute("data-i18n");
            if (translations[lang] && translations[lang][key]) {
                elem.textContent = translations[lang][key];
            }
        });
        
        // Update language label on toggle button
        const toggleLabel = document.getElementById("lang-label");
        if (toggleLabel) {
            toggleLabel.textContent = lang === 'en' ? "English (EN)" : "Bahasa Melayu (BM)";
        }
        
        // Re-fetch stats and logs to update static text placeholders
        fetchStatsAndLogs();
    }

    // Toggle button click listener
    const toggleBtn = document.getElementById("btn-lang-toggle");
    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            currentLang = currentLang === 'en' ? 'bm' : 'en';
            localStorage.setItem('ghosteye_lang', currentLang);
            applyLanguage(currentLang);
        });
    }

    // --- 6. INITIAL REFRESH & START POLLING ---
    applyLanguage(currentLang);
    
    // Poll stats and logs every 2 seconds
    setInterval(fetchStatsAndLogs, 2000);
});

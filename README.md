# GhostEye 👁️
> **Compiler-Level Threat Intelligence & Telemetry Ingestion Simulator**

GhostEye is an experimental cybersecurity proof-of-concept (PoC) designed to demonstrate **"Shift-Left" security** in software development pipelines. Instead of relying on traditional static or dynamic analysis *after* a binary is created, GhostEye instruments the compilation process itself. 

Whenever a developer compiles code, the GhostEye Compiler Agent intercepts the event, gathers rich system/file metadata (timestamps, OS details, username, geolocation, and hash characteristics), and streams it directly to a centralized SOC SIEM Dashboard.

---

## 🏗️ System Architecture & Workflow

Here is the high-level architecture diagram showing the flow of compiler telemetry from the desktop client, through the FastAPI gateway, to the dark-mode SOC SIEM dashboard:

![GhostEye System Architecture](ghosteye_architecture.png)

### Data Stream Flow:
1. **Developer Actions:** Developer writes code in the custom C++/Python IDE and clicks **Compile**.
2. **Telemetry Extraction:** The Compiler Agent immediately captures local timestamps, user account details, system hostname, OS specifications, and scans code for suspicious Win32 API calls.
3. **Network Dispatching:** 
   * **If Online:** Dispatches telemetry via a secure HTTP POST JSON payload to the API server.
   * **If Offline:** Caches payloads locally inside `offline_cache.json` with historical timestamps preserved. Once connection is restored, a sync thread flushes the queue.
4. **FastAPI Ingestion:** The backend processes client geolocations via GeoIP APIs (with simulated offline fallbacks) and commits records to a local SQLite database.
5. **Real-time Monitoring:** The SOC Dashboard pulls logs and updates analytics widgets, panning the Leaflet.js world map to the compile source coordinates and popping details in real-time.

---

## ⚡ Key Features

- **Instrumented Mini-IDE:** A dark-themed desktop code editor that parses source code dynamically for suspicious API calls (e.g., Win32 injection signatures) during compilation.
- **Real-Time Telemetry Stream:** Seamlessly transmits compilation events to a REST API. Records compile timestamp, hostname, OS details, username, compiler flags, and external IP.
- **Offline Caching & Auto-Sync:** Fully resilient compiler agent. If compilation occurs offline, telemetry is secured inside a local cache (`offline_cache.json`) with its original timestamp preserved. Once connection is restored, a background thread syncs the pending queue back to the SIEM.
- **"God Mode" Simulation Controls:** Built-in testing panel to spoof compiler host locations (e.g., Russia, China, North Korea, USA) and trigger bulk simulated logs to demonstrate SIEM alerts.
- **SOC SIEM Dashboard:** A sleek, glassmorphic dark-mode web dashboard featuring interactive world maps (Leaflet.js) and threat analytical metrics (Chart.js).

---

## 🏗️ Tech Stack

- **Frontend:** HTML5, Vanilla CSS3 (Glassmorphism), JavaScript (ES6+), **Chart.js** (Visuals), and **Leaflet.js** (World Map).
- **Backend:** **Python 3**, **FastAPI** (asynchronous routing), and **SQLite** (file-based database).
- **Compiler Agent:** Python **Tkinter** desktop framework.

---

## 🚀 How to Run Locally

### Prerequisites
Ensure you have Python 3 installed. Install dependencies using:
```bash
pip install fastapi uvicorn requests
```

### 1. Start the SIEM Dashboard & API Backend
Run the backend web server from the project directory:
```bash
python server.py
```
Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 2. Start the Compiler Agent Client
In a new terminal window, launch the compiler editor client:
```bash
python compiler_agent.py
```
Write or paste your code, choose your network status, and click **COMPILE & TELEMETRY**!

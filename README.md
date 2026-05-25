# GhostEye 👁️
> **Compiler-Level Threat Intelligence & Telemetry Ingestion Simulator**

GhostEye is an experimental cybersecurity proof-of-concept (PoC) designed to demonstrate **"Shift-Left" security** in software development pipelines. Instead of relying on traditional static or dynamic analysis *after* a binary is created, GhostEye instruments the compilation process itself. 

Whenever a developer compiles code, the GhostEye Compiler Agent intercepts the event, gathers rich system/file metadata (timestamps, OS details, username, geolocation, and hash characteristics), and streams it directly to a centralized SOC SIEM Dashboard.

---

## 🏗️ System Architecture & Workflow

GhostEye operates with a decoupled client-server architecture containing dual signature compilation, resilient caching for offline states, token authorization, and real-time visualization.

### 📊 System Architecture Diagram

```mermaid
flowchart TD
    subgraph Client ["1. GHOSTEYE COMPILER AGENT (Desktop IDE Klien)"]
        Login["Login Window<br>(Auth Username & Token)"]
        IDE["C++ Source Code Editor"]
        StatusBar["Dynamic Status Bar<br>(Session, Host, Token, Connection Status)"]
        
        Compiler["Instrumented Compiler Pipeline<br>(Win32 API keyword scanner)"]
        HashGen["Dual Hash Generator<br>(SHA-256 & MD5 signatures)"]
        
        NetState{"Network State?"}
        
        %% Online Path
        OnlinePath["ONLINE PATHWAY<br>(X-GhostEye-Token Header)"]
        HTTPPost["HTTP POST /api/telemetry"]
        
        %% Offline Path
        OfflinePath["OFFLINE PATHWAY<br>(Local Resilient Cache)"]
        EncryptXOR["XOR + Base64 Cipher Engine"]
        CacheFile[("offline_cache.json<br>(Local Encrypted Queue)")]
        SyncThread["Background Sync Thread<br>(Pings API & flushes cache when online)"]

        Login -->|Unlock Editor| IDE
        IDE -->|⚡ Compile & Telemetry| Compiler
        IDE -.->|Display Status| StatusBar
        Compiler -->|Extract Metadata & Hashing| HashGen
        HashGen --> NetState
        
        %% Online
        NetState -->|Online Mode| OnlinePath
        OnlinePath --> HTTPPost
        
        %% Offline
        NetState -->|Offline Mode| OfflinePath
        OfflinePath --> EncryptXOR
        EncryptXOR --> CacheFile
        SyncThread -.->|Auto-ping connection| CacheFile
        SyncThread -->|Push queued logs| HTTPPost
    end

    subgraph Server ["2. GHOSTEYE INGESTION BACKEND (FastAPI Gateway)"]
        API["FastAPI Routing Engine"]
        TokenAuth{"X-GhostEye-Token valid?"}
        GeoIP["GeoIP Resolver<br>(ip-api.com & Local Mock Fallback)"]
        DB[(SQLite Database<br>telemetry.db)]

        HTTPPost --> API
        API --> TokenAuth
        TokenAuth -->|Valid Token| GeoIP
        TokenAuth -->|Invalid Token| HTTP401["HTTP 401 Unauthorized"]
        GeoIP -->|Ingest Payload with MD5 + SHA-256| DB
    end

    subgraph SIEM ["3. GHOSTEYE SOC DASHBOARD (SIEM Frontend Web UI)"]
        Dashboard["SIEM Analytics Dashboard<br>(Neon Dark Glassmorphism Theme)"]
        LangToggle["Bilingual Toggle Switch<br>(EN / BM dynamically cached in LocalStorage)"]
        LeafletMap["Leaflet.js World Map<br>(Auto-flying focus and pop-up details)"]
        Charts["Chart.js Indicators<br>(Threat classifying Doughnut & Line graph trends)"]
        GodMode["God Mode Control Panel<br>(Single/Bulk spoof telemetry simulation)"]
        Poller["AJAX 2-second Poller"]

        Poller -->|Fetch Logs| API
        API -->|JSON Telemetry logs| Poller
        Dashboard --> Poller
        Dashboard -.->|Languages| LangToggle
        Dashboard -.->|Simulate logs| GodMode
        Poller -->|Fly to & Open Bubble| LeafletMap
        Poller -->|Update Trends| Charts
    end
```

### 🗃️ Database Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    TELEMETRY_LOGS {
        int id PK "Auto-increment ID"
        text timestamp "Compile event ISO-8601 UTC timestamp"
        text received_at "Server ingestion ISO-8601 UTC timestamp"
        text filename "Source code file compiled"
        int filesize "Size in bytes"
        text filehash_sha256 "SHA-256 hash representation"
        text filehash_md5 "MD5 hash representation"
        text compiler_flags "Active GCC/MSVC flags used"
        text ip "Workstation external IP"
        text country "Resolved country via GeoIP"
        text city "Resolved city via GeoIP"
        real latitude "Resolved coordinate latitude"
        real longitude "Resolved coordinate longitude"
        text hostname "Workstation host identifier"
        text username "Active system developer username"
        text os_info "OS version and processor architecture"
        int is_offline_log "Boolean (0=Online Compile, 1=Cached Sync)"
        text status "Compilation state (SUCCESS / FAILED)"
        text threat_level "Calculated priority level (INFO / LOW / MEDIUM / HIGH / CRITICAL)"
    }
```

### 🔄 System Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Developer as Developer Workstation
    participant IDE as GhostEye Compiler Agent (Tkinter GUI)
    participant Cache as Local Encrypted Cache (XOR + Base64)
    participant API as FastAPI Ingestion Gateway
    participant GeoIP as External GeoIP Service
    participant DB as SQLite Database (telemetry.db)
    participant SOC as SIEM SOC Dashboard

    Developer->>IDE: Initiate Compilation (Press Build/Run)
    IDE->>IDE: Scan source buffer for dangerous Win32 APIs
    IDE->>IDE: Compute Dual Signatures (SHA-256 & MD5 hashes)
    
    alt Network Interface Online
        IDE->>API: HTTP POST /api/telemetry (payload with X-GhostEye-Token)
    else Network Interface Offline
        IDE->>Cache: Encrypt payload using symmetric XOR + Base64
        IDE->>Cache: Append to offline_cache.json
        Note over IDE, Cache: Background Daemon thread polls connectivity status...
        Cache-->>IDE: Connection restored, decrypt logs
        IDE->>API: HTTP POST /api/telemetry (cached payloads with original timestamps)
    end
    
    API->>API: Validate X-GhostEye-Token Header
    alt Token Invalid
        API-->>IDE: 401 Unauthorized Response
    else Token Valid
        API->>GeoIP: Fetch location data for client IP address
        GeoIP-->>API: Return Country, City, Coordinates (Lat/Lon)
        API->>DB: INSERT INTO telemetry_logs
        DB-->>API: Log saved in SQLite
        API-->>IDE: 200 OK Telemetry Log Ingested
    end

    loop Periodic Fetch (Every 2 Seconds)
        SOC->>API: GET /api/logs
        API->>DB: Query records (ORDER BY timestamp DESC)
        DB-->>API: Return record list
        API-->>SOC: JSON payload response
        SOC->>SOC: Repaint Leaflet Map markers & recalculate Chart.js stats
    end
```

---

### 🔐 Security Architecture Details

#### 1. Dual Hashes Signatures (MD5 & SHA-256)
During the instrumented compilation process, the source code is passed to two independent hashing algorithms. Both signatures are generated and appended to the telemetry payload:
* **MD5 Hashing:** Captured via `hashlib.md5()` to maintain legacy compatibility and quick hash lookups in traditional databases.
* **SHA-256 Hashing:** Captured via `hashlib.sha256()` to offer cryptographic integrity and prevent signature collision attacks.

#### 2. Network Pathways: Online vs. Offline Mode

| Feature / Pathway | 🌐 Online Mode | 🔌 Offline Mode |
| :--- | :--- | :--- |
| **Transmission Destination** | Direct transmission to the FastAPI Backend Server. | Local caching in the `offline_cache.json` file. |
| **Authentication** | Validated via `X-GhostEye-Token` in the HTTP header. | Pre-validated signature; stored securely until connection is restored. |
| **Data Encryption** | Sent over HTTP (or HTTPS in production). | Cryptographically secured using an **XOR + Base64** cipher engine locally. |
| **Synchronisation** | Real-time ingest. | A background thread pings the API server and auto-flushes/syncs logs when the network becomes online. |

### Data Stream Flow:
1. **Developer Actions:** Developer writes code in the custom C++ IDE and clicks **Compile**.
2. **Telemetry Extraction:** The Compiler Agent immediately captures local timestamps, user account details, system hostname, OS specifications, and generates dual signatures (MD5 & SHA-256).
3. **Network Dispatching:** 
   * **If Online:** Dispatches telemetry via a secure HTTP POST JSON payload to the API server.
   * **If Offline:** Encrypts telemetry via XOR + Base64 and writes it to `offline_cache.json` with historical timestamps preserved. Once connection is restored, a background sync thread automatically flushes the queue.
4. **FastAPI Ingestion:** The backend verifies the API token, resolves client geolocations via GeoIP APIs (with simulated offline fallbacks), and commits records to a local SQLite database.
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

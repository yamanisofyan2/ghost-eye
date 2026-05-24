import os
import sqlite3
import datetime
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# Initialize FastAPI app
app = FastAPI(title="GhostEye SIEM Telemetry Ingestion API", version="2.1.0")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "telemetry.db"
API_TOKEN = "gho_secret_auth_token_2026"  # Secure API token for authentication

# Pydantic schema for Telemetry Payload
class TelemetryPayload(BaseModel):
    timestamp: str  # ISO string or formatted local time of event
    filename: str
    filesize: int
    filehash_sha256: str  # Security Upgrade: SHA-256 Signature
    filehash_md5: str     # Security Upgrade: MD5 Signature
    compiler_flags: str
    ip: str
    hostname: str
    username: str
    os_info: str
    is_offline_log: bool
    status: str  # SUCCESS, FAILED
    threat_level: str  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    # Optional God Mode overrides
    mocked_country: Optional[str] = None
    mocked_ip: Optional[str] = None

# Initialize SQLite database (supporting both MD5 and SHA-256)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Drops the table if structure needs update (safe for PoC/FYP reset)
    # We alter table or drop it to ensure schema matches the new columns
    cursor.execute("DROP TABLE IF EXISTS telemetry_logs")
    
    cursor.execute("""
        CREATE TABLE telemetry_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            received_at TEXT,
            filename TEXT,
            filesize INTEGER,
            filehash_sha256 TEXT,
            filehash_md5 TEXT,
            compiler_flags TEXT,
            ip TEXT,
            country TEXT,
            city TEXT,
            latitude REAL,
            longitude REAL,
            hostname TEXT,
            username TEXT,
            os_info TEXT,
            is_offline_log INTEGER,
            status TEXT,
            threat_level TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# GeoIP Resolution Helper
def resolve_geoip(ip_addr: str, mocked_country: Optional[str] = None) -> dict:
    result = {
        "country": "Unknown",
        "city": "Unknown",
        "latitude": 0.0,
        "longitude": 0.0
    }
    
    if mocked_country and mocked_country.lower() != "auto":
        result["country"] = mocked_country
        coordinates = {
            "Russia": {"city": "Moscow", "lat": 55.7558, "lon": 37.6173},
            "China": {"city": "Beijing", "lat": 39.9042, "lon": 116.4074},
            "United States": {"city": "Washington D.C.", "lat": 38.9072, "lon": -77.0369},
            "North Korea": {"city": "Pyongyang", "lat": 39.0392, "lon": 125.7625},
            "Malaysia": {"city": "Kuala Lumpur", "lat": 3.1390, "lon": 101.6869},
            "Germany": {"city": "Berlin", "lat": 52.5200, "lon": 13.4050},
            "Iran": {"city": "Tehran", "lat": 35.6892, "lon": 51.3890},
            "Brazil": {"city": "Brasilia", "lat": -15.7938, "lon": -47.8828}
        }
        if mocked_country in coordinates:
            result.update(coordinates[mocked_country])
        return result

    private_prefixes = ["127.", "192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31."]
    if any(ip_addr.startswith(prefix) for prefix in private_prefixes) or ip_addr == "localhost":
        try:
            r = requests.get("https://ipapi.co/json/", timeout=2)
            if r.status_code == 200:
                data = r.json()
                return {
                    "country": data.get("country_name", "Malaysia"),
                    "city": data.get("city", "Kuala Lumpur"),
                    "latitude": data.get("latitude", 3.1390),
                    "longitude": data.get("longitude", 101.6869)
                }
        except:
            pass
        return {
            "country": "Malaysia",
            "city": "Kuala Lumpur",
            "latitude": 3.1390,
            "longitude": 101.6869
        }

    try:
        r = requests.get(f"http://ip-api.com/json/{ip_addr}", timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return {
                    "country": data.get("country", "Unknown"),
                    "city": data.get("city", "Unknown"),
                    "latitude": data.get("lat", 0.0),
                    "longitude": data.get("lon", 0.0)
                }
    except Exception as e:
        print(f"GeoIP Error: {e}")
        
    return result

# Endpoint to ingest telemetry (with token authorization)
@app.post("/api/telemetry")
async def ingest_telemetry(request: Request, payload: TelemetryPayload):
    # Security Check: Verify API Token
    token = request.headers.get("X-GhostEye-Token")
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing X-GhostEye-Token header")

    ip_to_resolve = payload.mocked_ip if (payload.mocked_ip and payload.mocked_ip.lower() != "auto") else payload.ip
    
    geo = resolve_geoip(ip_to_resolve, payload.mocked_country)
    received_at = datetime.datetime.utcnow().isoformat() + "Z"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO telemetry_logs (
                timestamp, received_at, filename, filesize, filehash_sha256, filehash_md5, compiler_flags, 
                ip, country, city, latitude, longitude, hostname, username, os_info, 
                is_offline_log, status, threat_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.timestamp,
            received_at,
            payload.filename,
            payload.filesize,
            payload.filehash_sha256,
            payload.filehash_md5,
            payload.compiler_flags,
            ip_to_resolve,
            geo["country"],
            geo["city"],
            geo["latitude"],
            geo["longitude"],
            payload.hostname,
            payload.username,
            payload.os_info,
            1 if payload.is_offline_log else 0,
            payload.status,
            payload.threat_level
        ))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Telemetry received and authenticated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Insertion Error: {str(e)}")

# Endpoint to fetch logs for SIEM UI
@app.get("/api/logs")
async def get_logs(limit: int = 50):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM telemetry_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to fetch real-time stats for SIEM widgets and charts
@app.get("/api/stats")
async def get_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Total compiles
        cursor.execute("SELECT COUNT(*) FROM telemetry_logs")
        total_compiles = cursor.fetchone()[0]
        
        # 2. Count by Threat Level
        cursor.execute("SELECT threat_level, COUNT(*) FROM telemetry_logs GROUP BY threat_level")
        threat_counts = dict(cursor.fetchall())
        
        for level in ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            if level not in threat_counts:
                threat_counts[level] = 0
                
        # 3. Unique countries
        cursor.execute("SELECT country, COUNT(*) FROM telemetry_logs GROUP BY country ORDER BY COUNT(*) DESC")
        country_counts = dict(cursor.fetchall())
        
        # 4. Success vs Failed
        cursor.execute("SELECT status, COUNT(*) FROM telemetry_logs GROUP BY status")
        status_counts = dict(cursor.fetchall())
        for stat in ["SUCCESS", "FAILED"]:
            if stat not in status_counts:
                status_counts[stat] = 0

        # 5. Timeline of compiles (Last 30 entries)
        cursor.execute("SELECT timestamp, country, threat_level FROM telemetry_logs ORDER BY timestamp DESC LIMIT 30")
        timeline = [{"timestamp": r[0], "country": r[1], "threat_level": r[2]} for r in cursor.fetchall()]
        
        conn.close()
        
        return {
            "total_compiles": total_compiles,
            "threat_counts": threat_counts,
            "country_counts": country_counts,
            "status_counts": status_counts,
            "timeline": timeline
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to clear all logs
@app.post("/api/reset")
async def reset_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM telemetry_logs")
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Database cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health Check Endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}

# Serve Dashboard index.html directly on root
@app.get("/")
async def serve_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    else:
        return HTMLResponse(content="<h3>SIEM Dashboard index.html not found in root workspace directory.</h3>", status_code=404)

# Serve styles.css, dashboard.js and other files if in root directory
@app.get("/styles.css")
async def serve_css():
    return FileResponse("styles.css")

@app.get("/dashboard.js")
async def serve_js():
    return FileResponse("dashboard.js")

if __name__ == "__main__":
    import uvicorn
    # Start the server on port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)

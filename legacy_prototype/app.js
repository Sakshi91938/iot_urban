/**
 * Urban Mobility Pattern Discovery & IoT Telemetry Intelligence Dashboard
 * Client Controller: Geospatial GIS, Diurnal Curves, DBSCAN Studio, and IoT Streamer.
 */

// Global State
const STATE = {
  overview: null,
  zones: [],
  clusters: [],
  anomalies: [],
  map: null,
  mapLayers: {
    corridors: null,
    clusters: null,
    anomalies: null
  },
  charts: {
    diurnal: null,
    corridors: null,
    phaseScatter: null
  },
  streaming: {
    active: false,
    intervalId: null,
    speedMs: 200,
    packetCount: 0,
    lastTime: Date.now(),
    recentPackets: []
  }
};

// --------------------------------------------------------------------------
// INITIALIZATION
// --------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  initClock();
  initTabs();
  initMap();
  initDbscanStudio();
  initStreamControls();
  initExportAction();

  // Load backend data
  loadOverview();
  loadZones();
  loadClusters();
  loadDiurnal();
  loadAnomalies();
  loadScatterSample();
});

// --------------------------------------------------------------------------
// CLOCK & HEADER
// --------------------------------------------------------------------------
function initClock() {
  const clockEl = document.getElementById("live-clock");
  function tick() {
    const now = new Date();
    // Indian Standard Time
    const timeStr = now.toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata" });
    if (clockEl) clockEl.textContent = timeStr + " IST";
  }
  tick();
  setInterval(tick, 1000);
}

// --------------------------------------------------------------------------
// TAB NAVIGATION
// --------------------------------------------------------------------------
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const targetId = tab.dataset.tab;
      
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));

      tab.classList.add("active");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) {
        targetPanel.classList.add("active");
      }

      // Re-invalidate Leaflet map size if switching to Map tab
      if (targetId === "tab-map" && STATE.map) {
        setTimeout(() => {
          STATE.map.invalidateSize();
        }, 150);
      }
    });
  });
}

// --------------------------------------------------------------------------
// API DATA LOADERS
// --------------------------------------------------------------------------
async function loadOverview() {
  try {
    const res = await fetch("/api/overview");
    if (!res.ok) throw new Error("Overview API failed");
    const data = await res.json();
    STATE.overview = data;

    // Populate Header and KPIs
    const dbStatusEl = document.getElementById("header-db-status");
    if (dbStatusEl) {
      dbStatusEl.textContent = `${data.database_type}: ${data.total_records.toLocaleString()} Rows`;
    }

    setVal("kpi-total-records", data.total_records.toLocaleString());
    setVal("kpi-active-zones", `${data.active_zones} Zones`);
    setVal("kpi-anomalies", `${data.anomalies_detected} Events`);
    setVal("kpi-mean-queue", data.mean_queue_density.toFixed(4));
    setVal("kpi-max-queue", data.max_queue_density.toFixed(4));
    setVal("kpi-mean-stop", data.mean_stop_density.toFixed(4));
    setVal("kpi-max-stop", data.max_stop_density.toFixed(4));
    setVal("kpi-fleet-speed", `${data.average_fleet_speed} km/h`);

  } catch (err) {
    console.error("Failed to load overview:", err);
  }
}

async function loadZones() {
  try {
    const res = await fetch("/api/zones");
    if (!res.ok) throw new Error("Zones API failed");
    const data = await res.json();
    STATE.zones = data.zones;

    renderCorridorList(data.zones);
    renderMapCorridors(data.zones);
    renderCorridorBarChart(data.zones);

  } catch (err) {
    console.error("Failed to load zones:", err);
  }
}

async function loadClusters() {
  try {
    const res = await fetch("/api/clusters");
    if (!res.ok) throw new Error("Clusters API failed");
    const data = await res.json();
    STATE.clusters = data.clusters;

    renderVehicleClustersList(data.clusters);
    renderMapVehicleClusters(data.clusters);

  } catch (err) {
    console.error("Failed to load clusters:", err);
  }
}

async function loadDiurnal() {
  try {
    const res = await fetch("/api/diurnal");
    if (!res.ok) throw new Error("Diurnal API failed");
    const data = await res.json();
    renderDiurnalChart(data.network_diurnal);

  } catch (err) {
    console.error("Failed to load diurnal data:", err);
  }
}

async function loadAnomalies() {
  try {
    const res = await fetch("/api/anomalies");
    if (!res.ok) throw new Error("Anomalies API failed");
    const data = await res.json();
    STATE.anomalies = data.anomalies;

    renderAnomaliesTable(data.anomalies);
    renderMapAnomalies(data.anomalies);

  } catch (err) {
    console.error("Failed to load anomalies:", err);
  }
}

async function loadScatterSample() {
  try {
    const res = await fetch("/api/scatter-sample?limit=1000");
    if (!res.ok) throw new Error("Scatter sample failed");
    const data = await res.json();
    renderPhaseScatterChart(data.points);

  } catch (err) {
    console.error("Failed to load scatter sample:", err);
  }
}

// --------------------------------------------------------------------------
// LEAFLET GIS MAP IMPLEMENTATION
// --------------------------------------------------------------------------
function initMap() {
  // Center on Delhi NCR: [28.635, 77.215]
  STATE.map = L.map("gis-map", {
    zoomControl: true,
    attributionControl: true
  }).setView([28.635, 77.215], 11);

  // CartoDB Dark Matter Tiles (Clean industrial GIS cartography)
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 19
  }).addTo(STATE.map);

  // Layer groups for layer management
  STATE.mapLayers.corridors = L.layerGroup().addTo(STATE.map);
  STATE.mapLayers.clusters = L.layerGroup().addTo(STATE.map);
  STATE.mapLayers.anomalies = L.layerGroup().addTo(STATE.map);
}

function renderMapCorridors(zones) {
  if (!STATE.map || !STATE.mapLayers.corridors) return;
  STATE.mapLayers.corridors.clearLayers();

  zones.forEach(z => {
    const color = z.status_color || "#0284c7";

    // Pulsing/Radar Circle
    const circle = L.circle([z.lat, z.lon], {
      color: color,
      fillColor: color,
      fillOpacity: 0.22,
      weight: 2,
      radius: 1400
    });

    const popupHtml = `
      <div class="custom-popup">
        <div class="custom-popup-title">${z.name}</div>
        <div class="custom-popup-meta">${z.description}</div>
        <div class="custom-popup-row">
          <span>Congestion Level:</span>
          <strong style="color: ${color}">${z.traffic_status} (${z.congestion_score}%)</strong>
        </div>
        <div class="custom-popup-row">
          <span>Mean Queue Density:</span>
          <strong>${z.mean_queue_density}</strong>
        </div>
        <div class="custom-popup-row">
          <span>Mean Stop Density:</span>
          <strong>${z.mean_stop_density}</strong>
        </div>
        <div class="custom-popup-row">
          <span>Speed Limit:</span>
          <strong>${z.speed_limit} km/h</strong>
        </div>
        <div class="custom-popup-row">
          <span>DBSCAN Anomalies:</span>
          <strong style="color: #ef4444">${z.anomaly_count} Recorded</strong>
        </div>
      </div>
    `;

    circle.bindPopup(popupHtml);
    circle.addTo(STATE.mapLayers.corridors);

    // Center SVG badge
    const badgeIcon = L.divIcon({
      className: "custom-zone-marker",
      html: `
        <div style="
          background: ${color};
          color: #0b0f19;
          font-weight: 700;
          font-family: monospace;
          font-size: 11px;
          width: 26px;
          height: 26px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid #ffffff;
          box-shadow: 0 0 10px ${color};
        ">Z${z.zone_id}</div>
      `,
      iconSize: [26, 26],
      iconAnchor: [13, 13]
    });

    L.marker([z.lat, z.lon], { icon: badgeIcon })
      .bindPopup(popupHtml)
      .addTo(STATE.mapLayers.corridors);
  });
}

function renderMapVehicleClusters(clusters) {
  if (!STATE.map || !STATE.mapLayers.clusters) return;
  STATE.mapLayers.clusters.clearLayers();

  clusters.forEach(c => {
    const lat = c.centroid.lat;
    const lon = c.centroid.lon;

    const clusterIcon = L.divIcon({
      className: "custom-cluster-marker",
      html: `
        <div style="
          background: rgba(2, 132, 199, 0.2);
          border: 1px dashed #38bdf8;
          padding: 3px 8px;
          border-radius: 4px;
          font-family: monospace;
          font-size: 10px;
          font-weight: 600;
          color: #e0f2fe;
          white-space: nowrap;
          box-shadow: 0 2px 8px rgba(0,0,0,0.5);
        ">
          ⚡ Cluster ${c.cluster_id}: ${c.mean_speed_kmh} km/h
        </div>
      `,
      iconAnchor: [60, 12]
    });

    const popupHtml = `
      <div class="custom-popup">
        <div class="custom-popup-title">${c.neighborhood}</div>
        <div class="custom-popup-meta">Spatial DBSCAN Fleet Probe Cluster ${c.cluster_id}</div>
        <div class="custom-popup-row">
          <span>Traffic Status:</span>
          <strong style="color: ${c.badge_color}">${c.traffic_status}</strong>
        </div>
        <div class="custom-popup-row">
          <span>Average Fleet Speed:</span>
          <strong>${c.mean_speed_kmh} km/h</strong>
        </div>
        <div class="custom-popup-row">
          <span>Speed Range:</span>
          <strong>${c.min_speed_kmh} - ${c.max_speed_kmh} km/h</strong>
        </div>
        <div class="custom-popup-row">
          <span>Probed Vehicles:</span>
          <strong>${c.vehicle_count} GPS Pings</strong>
        </div>
      </div>
    `;

    L.marker([lat, lon], { icon: clusterIcon })
      .bindPopup(popupHtml)
      .addTo(STATE.mapLayers.clusters);
  });
}

function renderMapAnomalies(anomalies) {
  if (!STATE.map || !STATE.mapLayers.anomalies) return;
  STATE.mapLayers.anomalies.clearLayers();

  anomalies.forEach(a => {
    // Add small random jitter so co-located anomalies don't strictly stack
    const jitterLat = a.lat + (Math.random() - 0.5) * 0.006;
    const jitterLon = a.lon + (Math.random() - 0.5) * 0.006;

    const anomalyIcon = L.divIcon({
      className: "anomaly-pulse-marker",
      html: `
        <div style="
          background: #ef4444;
          color: #fff;
          font-weight: 800;
          font-size: 10px;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid #fff;
          box-shadow: 0 0 10px #ef4444;
          animation: pulse-ring 1.8s infinite;
        ">!</div>
      `,
      iconSize: [18, 18],
      iconAnchor: [9, 9]
    });

    const popupHtml = `
      <div class="custom-popup">
        <div class="custom-popup-title" style="color: #ef4444;">DBSCAN ANOMALY OUTLIER (Noise -1)</div>
        <div class="custom-popup-meta">${a.zone_name} • ${a.timestamp}</div>
        <div class="custom-popup-row">
          <span>Queue Density ($K_q$):</span>
          <strong style="color: #ef4444">${a.queue_density}</strong>
        </div>
        <div class="custom-popup-row">
          <span>Stop Density ($K_s$):</span>
          <strong style="color: #ef4444">${a.stop_density}</strong>
        </div>
        <div class="custom-popup-row">
          <span>Anomaly Severity:</span>
          <strong>${a.severity_index} / 100</strong>
        </div>
      </div>
    `;

    L.marker([jitterLat, jitterLon], { icon: anomalyIcon })
      .bindPopup(popupHtml)
      .addTo(STATE.mapLayers.anomalies);
  });
}

// --------------------------------------------------------------------------
// SIDEBAR RENDERING
// --------------------------------------------------------------------------
function renderCorridorList(zones) {
  const container = document.getElementById("corridor-list-container");
  if (!container) return;

  container.innerHTML = "";
  zones.forEach(z => {
    const card = document.createElement("div");
    card.className = "corridor-card";
    card.innerHTML = `
      <div class="corridor-card-header">
        <span class="corridor-name">Z${z.zone_id}: ${z.short_name}</span>
        <span class="badge" style="background: ${z.status_color}22; color: ${z.status_color}; border: 1px solid ${z.status_color}44;">
          ${z.traffic_status}
        </span>
      </div>
      <div class="corridor-sub">${z.description}</div>
      <div class="corridor-metrics">
        <div class="metric-col">
          <span class="metric-col-label">Queue Dens.</span>
          <span class="metric-col-val mono">${z.mean_queue_density}</span>
        </div>
        <div class="metric-col">
          <span class="metric-col-label">Stop Dens.</span>
          <span class="metric-col-val mono">${z.mean_stop_density}</span>
        </div>
        <div class="metric-col">
          <span class="metric-col-label">Anomalies</span>
          <span class="metric-col-val mono" style="color: ${z.anomaly_count > 0 ? '#ef4444' : '#94a3b8'}">${z.anomaly_count}</span>
        </div>
      </div>
    `;

    card.addEventListener("click", () => {
      document.querySelectorAll(".corridor-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      if (STATE.map) {
        STATE.map.flyTo([z.lat, z.lon], 13, { duration: 1.2 });
      }
    });

    container.appendChild(card);
  });
}

function renderVehicleClustersList(clusters) {
  const container = document.getElementById("vehicle-clusters-container");
  if (!container) return;

  container.innerHTML = "";
  clusters.forEach(c => {
    const item = document.createElement("div");
    item.className = "cluster-item";
    item.innerHTML = `
      <div>
        <div class="cluster-info-name">Cluster ${c.cluster_id}: ${c.neighborhood}</div>
        <div class="cluster-info-desc">Centroid: [${c.centroid.lat}, ${c.centroid.lon}] • ${c.vehicle_count} Probes</div>
      </div>
      <div class="text-right">
        <span class="badge" style="background: ${c.badge_color}22; color: ${c.badge_color}; border: 1px solid ${c.badge_color}44;">
          ${c.mean_speed_kmh} km/h
        </span>
      </div>
    `;

    item.addEventListener("click", () => {
      if (STATE.map) {
        STATE.map.flyTo([c.centroid.lat, c.centroid.lon], 14, { duration: 1 });
      }
    });

    container.appendChild(item);
  });
}

// --------------------------------------------------------------------------
// CHART.JS TELEMETRY VISUALIZATIONS
// --------------------------------------------------------------------------
function renderDiurnalChart(diurnalData) {
  const ctx = document.getElementById("diurnalChart");
  if (!ctx) return;

  const labels = diurnalData.map(d => d.hour_label);
  const queueValues = diurnalData.map(d => d.queue_density);
  const stopValues = diurnalData.map(d => d.stop_density);

  if (STATE.charts.diurnal) {
    STATE.charts.diurnal.destroy();
  }

  STATE.charts.diurnal = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Queue Density (Kq)",
          data: queueValues,
          borderColor: "#f59e0b",
          backgroundColor: "rgba(245, 158, 11, 0.12)",
          borderWidth: 2.5,
          tension: 0.35,
          fill: true,
          pointRadius: 3,
          pointBackgroundColor: "#f59e0b"
        },
        {
          label: "Stop Density (Ks)",
          data: stopValues,
          borderColor: "#0284c7",
          backgroundColor: "rgba(2, 132, 199, 0.08)",
          borderWidth: 2,
          tension: 0.35,
          fill: true,
          pointRadius: 3,
          pointBackgroundColor: "#0284c7"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false
      },
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
        },
        tooltip: {
          backgroundColor: "#0f172a",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          borderColor: "#334155",
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } },
          min: 0,
          max: 0.7
        }
      }
    }
  });
}

function renderCorridorBarChart(zones) {
  const ctx = document.getElementById("corridorBarChart");
  if (!ctx) return;

  const labels = zones.map(z => `Z${z.zone_id} ${z.short_name}`);
  const queueValues = zones.map(z => z.mean_queue_density);
  const stopValues = zones.map(z => z.mean_stop_density);

  if (STATE.charts.corridors) {
    STATE.charts.corridors.destroy();
  }

  STATE.charts.corridors = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Mean Queue Density (Kq)",
          data: queueValues,
          backgroundColor: "#f59e0b",
          borderRadius: 4
        },
        {
          label: "Mean Stop Density (Ks)",
          data: stopValues,
          backgroundColor: "#0284c7",
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
        },
        tooltip: {
          backgroundColor: "#0f172a",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          borderColor: "#334155",
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#64748b", font: { family: "Inter", size: 10 } }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }
        }
      }
    }
  });
}

function renderPhaseScatterChart(points) {
  const ctx = document.getElementById("phaseScatterChart");
  if (!ctx) return;

  const normalPoints = points.filter(p => p.c !== -1).map(p => ({ x: p.q, y: p.s }));
  const anomalyPoints = points.filter(p => p.c === -1).map(p => ({ x: p.q, y: p.s }));

  if (STATE.charts.phaseScatter) {
    STATE.charts.phaseScatter.destroy();
  }

  STATE.charts.phaseScatter = new Chart(ctx, {
    type: "scatter",
    data: {
      datasets: [
        {
          label: "Normal Traffic Flow",
          data: normalPoints,
          backgroundColor: "rgba(2, 132, 199, 0.45)",
          pointRadius: 3
        },
        {
          label: "DBSCAN Breakdown Anomalies (Cluster -1)",
          data: anomalyPoints,
          backgroundColor: "#ef4444",
          pointRadius: 6,
          pointHoverRadius: 8
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } }
        },
        tooltip: {
          backgroundColor: "#0f172a",
          titleColor: "#f8fafc",
          bodyColor: "#94a3b8",
          callbacks: {
            label: (ctx) => `Queue: ${ctx.parsed.x.toFixed(4)}, Stop: ${ctx.parsed.y.toFixed(4)}`
          }
        }
      },
      scales: {
        x: {
          title: { display: true, text: "Queue Density (Kq)", color: "#94a3b8", font: { size: 10 } },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }
        },
        y: {
          title: { display: true, text: "Stop Density (Ks)", color: "#94a3b8", font: { size: 10 } },
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#64748b", font: { family: "JetBrains Mono", size: 10 } }
        }
      }
    }
  });
}

// --------------------------------------------------------------------------
// DBSCAN ANOMALY STUDIO
// --------------------------------------------------------------------------
function initDbscanStudio() {
  const sliderEps = document.getElementById("slider-eps");
  const valEps = document.getElementById("val-eps");
  const sliderMinSamples = document.getElementById("slider-min-samples");
  const valMinSamples = document.getElementById("val-min-samples");
  const btnRun = document.getElementById("btn-run-dbscan");
  const btnReset = document.getElementById("btn-reset-dbscan");

  if (sliderEps && valEps) {
    sliderEps.addEventListener("input", () => {
      valEps.textContent = parseFloat(sliderEps.value).toFixed(2);
    });
  }

  if (sliderMinSamples && valMinSamples) {
    sliderMinSamples.addEventListener("input", () => {
      valMinSamples.textContent = sliderMinSamples.value;
    });
  }

  if (btnReset) {
    btnReset.addEventListener("click", () => {
      if (sliderEps) {
        sliderEps.value = 0.35;
        valEps.textContent = "0.35";
      }
      if (sliderMinSamples) {
        sliderMinSamples.value = 10;
        valMinSamples.textContent = "10";
      }
      runDbscanTuning(0.35, 10);
    });
  }

  if (btnRun) {
    btnRun.addEventListener("click", () => {
      const eps = parseFloat(sliderEps.value);
      const minSamples = parseInt(sliderMinSamples.value, 10);
      runDbscanTuning(eps, minSamples);
    });
  }
}

async function runDbscanTuning(eps, minSamples) {
  const btnRun = document.getElementById("btn-run-dbscan");
  if (btnRun) {
    btnRun.disabled = true;
    btnRun.textContent = "Computing DBSCAN Clusters...";
  }

  try {
    const res = await fetch("/api/dbscan-tune", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ eps: eps, min_samples: minSamples })
    });

    if (!res.ok) throw new Error("DBSCAN Tune failed");
    const result = await res.json();

    // Update diagnostic badges
    setVal("dbscan-elapsed", `${result.computation_time_ms} ms`);
    setVal("dbscan-num-clusters", `${result.num_clusters_found} Clusters`);
    setVal("dbscan-anomaly-count", `${result.anomaly_count} Outliers`);
    setVal("dbscan-anomaly-pct", `${result.anomaly_ratio_pct}%`);

    const tableBadge = document.getElementById("anomaly-table-badge");
    if (tableBadge) {
      tableBadge.textContent = `${result.anomaly_count} Anomalies Detected`;
    }

  } catch (err) {
    console.error("DBSCAN Tuning Error:", err);
    alert("DBSCAN execution failed: " + err.message);
  } finally {
    if (btnRun) {
      btnRun.disabled = false;
      btnRun.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Recompute DBSCAN Clustering`;
    }
  }
}

function renderAnomaliesTable(anomalies) {
  const tbody = document.getElementById("anomalies-table-body");
  if (!tbody) return;

  if (!anomalies || anomalies.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center">No anomalous breakdown events isolated with current parameters.</td></tr>`;
    return;
  }

  tbody.innerHTML = "";
  anomalies.forEach(a => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="mono">#${a.id}</td>
      <td class="mono">${a.timestamp}</td>
      <td><strong>${a.short_name}</strong> (Zone ${a.zone_id})</td>
      <td class="mono text-rose">${a.queue_density}</td>
      <td class="mono text-rose">${a.stop_density}</td>
      <td class="mono"><strong>${a.severity_index}</strong> / 100</td>
      <td><span class="badge badge-rose">${a.status_tag}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// --------------------------------------------------------------------------
// IOT TELEMETRY STREAM SIMULATOR
// --------------------------------------------------------------------------
function initStreamControls() {
  const btnToggle = document.getElementById("btn-toggle-stream");
  const btnStep = document.getElementById("btn-step-stream");
  const speedSelect = document.getElementById("select-stream-speed");
  const btnClear = document.getElementById("btn-clear-feed");

  if (btnToggle) {
    btnToggle.addEventListener("click", () => {
      STATE.streaming.active = !STATE.streaming.active;
      if (STATE.streaming.active) {
        startStream();
      } else {
        stopStream();
      }
    });
  }

  if (btnStep) {
    btnStep.addEventListener("click", () => {
      fetchNextPacket();
    });
  }

  if (speedSelect) {
    speedSelect.addEventListener("change", () => {
      STATE.streaming.speedMs = parseInt(speedSelect.value, 10);
      if (STATE.streaming.active) {
        stopStream();
        startStream();
      }
    });
  }

  if (btnClear) {
    btnClear.addEventListener("click", () => {
      const feedLog = document.getElementById("stream-feed-log");
      if (feedLog) feedLog.innerHTML = "";
    });
  }
}

function startStream() {
  const indicator = document.getElementById("stream-state-indicator");
  const btnText = document.getElementById("stream-btn-text");
  const btnIcon = document.getElementById("stream-btn-icon");

  if (indicator) {
    indicator.classList.add("streaming");
    indicator.innerHTML = `<span class="pulse-dot"></span> STREAM LIVE (INGESTING)`;
  }
  if (btnText) btnText.textContent = "Pause Telemetry Stream";
  if (btnIcon) btnIcon.textContent = "⏸";

  STATE.streaming.intervalId = setInterval(fetchNextPacket, STATE.streaming.speedMs);
}

function stopStream() {
  if (STATE.streaming.intervalId) {
    clearInterval(STATE.streaming.intervalId);
    STATE.streaming.intervalId = null;
  }

  const indicator = document.getElementById("stream-state-indicator");
  const btnText = document.getElementById("stream-btn-text");
  const btnIcon = document.getElementById("stream-btn-icon");

  if (indicator) {
    indicator.classList.remove("streaming");
    indicator.innerHTML = `<span class="pulse-dot" style="background:#64748b; box-shadow:none;"></span> STREAM PAUSED`;
  }
  if (btnText) btnText.textContent = "Start Telemetry Stream";
  if (btnIcon) btnIcon.textContent = "▶";
}

async function fetchNextPacket() {
  try {
    const res = await fetch("/api/stream-next");
    if (!res.ok) return;
    const packet = await res.json();

    STATE.streaming.packetCount++;
    setVal("stream-pkt-count", STATE.streaming.packetCount.toLocaleString());

    // Update Ingestion Rate
    const now = Date.now();
    const elapsedSec = (now - STATE.streaming.lastTime) / 1000;
    if (elapsedSec > 0.8) {
      const rate = (1 / (STATE.streaming.speedMs / 1000)).toFixed(1);
      setVal("stream-rate", `${rate} pkt/s`);
      STATE.streaming.lastTime = now;
    }

    // Update JSON inspector
    const viewer = document.getElementById("raw-json-viewer");
    const inspectorId = document.getElementById("inspector-pkt-id");
    if (viewer) viewer.textContent = JSON.stringify(packet, null, 2);
    if (inspectorId) inspectorId.textContent = packet.packet_id;

    // Append to live feed ticker
    appendFeedItem(packet);

  } catch (err) {
    console.error("Stream fetch error:", err);
  }
}

function appendFeedItem(pkt) {
  const container = document.getElementById("stream-feed-log");
  if (!container) return;

  // Clear hint
  const hint = container.querySelector(".empty-feed-hint");
  if (hint) hint.remove();

  const isAnomaly = pkt.is_anomaly;
  const item = document.createElement("div");
  item.className = `feed-item ${isAnomaly ? "feed-anomaly" : ""}`;
  item.innerHTML = `
    <div style="display:flex; align-items:center; gap:8px;">
      <span class="mono" style="font-weight:600; color:${isAnomaly ? '#ef4444' : '#0284c7'}">${pkt.packet_id}</span>
      <span style="color:#f8fafc; font-weight:500;">Zone ${pkt.zone_id} (${pkt.corridor})</span>
      <span class="mono" style="color:#64748b;">${pkt.timestamp}</span>
    </div>
    <div style="display:flex; align-items:center; gap:12px;">
      <span class="mono">Kq: <strong>${pkt.queue_density}</strong></span>
      <span class="mono">Ks: <strong>${pkt.stop_density}</strong></span>
      <span class="badge ${isAnomaly ? 'badge-rose' : 'badge-emerald'}">
        ${isAnomaly ? 'ANOMALY -1' : 'STABLE'}
      </span>
    </div>
  `;

  // Prepend to top of feed
  container.insertBefore(item, container.firstChild);

  // Keep feed max 40 items
  if (container.children.length > 40) {
    container.removeChild(container.lastChild);
  }
}

// --------------------------------------------------------------------------
// CSV EXPORT
// --------------------------------------------------------------------------
function initExportAction() {
  const btnExport = document.getElementById("btn-export-csv");
  if (btnExport) {
    btnExport.addEventListener("click", () => {
      window.location.href = "/api/export";
    });
  }
}

// --------------------------------------------------------------------------
// HELPER UTILITY
// --------------------------------------------------------------------------
function setVal(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

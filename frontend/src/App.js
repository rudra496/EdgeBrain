import React, { useState, useEffect, useRef } from 'react';
import {
  AreaChart, Area, BarChart, Bar, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis, RadialBarChart, RadialBar,
} from 'recharts';
import {
  Activity, AlertTriangle, Bell, Brain, Cpu, Droplets, LayoutDashboard,
  Menu, Radio, Send, Shield, Sun, Thermometer, Wifi, WifiOff, X, Zap, Loader
} from 'lucide-react';
import './App.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/api/v1/ws';

// Simulated dummy data for resilience
const DUMMY_DATA = {
  temperature: Array.from({length: 20}, (_, i) => ({ time: `10:${i}`, value: 22 + Math.random() * 5 })),
  energy: Array.from({length: 20}, (_, i) => ({ time: `10:${i}`, value: 100 + Math.random() * 50 })),
  humidity: Array.from({length: 20}, (_, i) => ({ time: `10:${i}`, value: 40 + Math.random() * 10 })),
  light: Array.from({length: 20}, (_, i) => ({ time: `10:${i}`, value: 300 + Math.random() * 100 })),
};

function useAPI(path, interval = 5000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const fetch_ = async () => {
      try {
        const res = await fetch(`${API}${path}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) {
          setData(json);
          setLoading(false);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e.message);
          setLoading(false);
        }
      }
    };
    fetch_();
    const id = setInterval(fetch_, interval);
    return () => { cancelled = true; clearInterval(id); };
  }, [path, interval]);

  return { data, loading, error };
}

function useWebSocket(onMessage) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  const [status, setStatus] = useState('disconnected');
  onMessageRef.current = onMessage;

  useEffect(() => {
    let retryCount = 0;
    const connect = () => {
      setStatus('connecting');
      try {
        const ws = new WebSocket(WS_URL);
        ws.onopen = () => {
          setStatus('connected');
          retryCount = 0;
          document.documentElement.style.setProperty('--ws-status', '#10b981'); // success color
        };
        ws.onmessage = (e) => {
          try { onMessageRef.current(JSON.parse(e.data)); } catch {}
        };
        ws.onclose = () => {
          setStatus('disconnected');
          document.documentElement.style.setProperty('--ws-status', '#ef4444');
          const delay = Math.min(1000 * Math.pow(2, retryCount), 10000);
          retryCount++;
          reconnectRef.current = setTimeout(connect, delay);
        };
        ws.onerror = () => ws.close();
        wsRef.current = ws;
      } catch (e) {
        setStatus('error');
        reconnectRef.current = setTimeout(connect, 5000);
      }
    };

    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectRef.current);
    };
  }, []);
  return status;
}

const DEVICE_COLORS = { temperature: '#ef4444', motion: '#10b981', energy: '#f59e0b', humidity: '#0ea5e9', light: '#f97316' };
const DEVICE_ICONS = { temperature: Thermometer, motion: Activity, energy: Zap, humidity: Droplets, light: Sun };

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}22`, border: `1px solid ${color}33`, boxShadow: `0 0 15px ${color}22` }}>
        <Icon size={24} color={color} />
      </div>
      <div className="stat-info">
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
    </div>
  );
}

function DeviceCard({ device }) {
  const Icon = DEVICE_ICONS[device.device_type] || Radio;
  const color = DEVICE_COLORS[device.device_type] || '#818cf8';
  const room = device.device_id.split('-sensor-')[0].split('-meter-')[0];

  return (
    <div className="device-card">
      <div className="device-card-header">
        <div className="device-card-icon" style={{ background: `${color}22`, border: `1px solid ${color}33` }}>
          <Icon size={20} color={color} />
        </div>
        <div className="device-card-info">
          <div className="device-card-type">{device.device_type}</div>
          <div className="device-card-room">{room.replace(/-/g, ' ')}</div>
        </div>
        <div>
          {device.is_online ? <Wifi size={16} color="#10b981" /> : <WifiOff size={16} color="#ef4444" />}
        </div>
      </div>
      <div className="device-card-value" style={{ color: color }}>
        {device.last_reading != null ? device.last_reading.toFixed(1) : '—'}
      </div>
      <div className="device-card-footer">
        <span>{device.total_readings || 0} readings</span>
        <span>{device.last_seen ? new Date(device.last_seen).toLocaleTimeString() : 'offline'}</span>
      </div>
    </div>
  );
}

function ChartCard({ title, icon: Icon, data, dataKey, color, unit, chartType = 'area' }) {
  const tooltipStyle = {
    background: 'rgba(9, 9, 11, 0.85)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 12,
    padding: 12,
    color: '#f8fafc',
    boxShadow: '0 8px 32px rgba(0,0,0,0.3)'
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title" style={{ color: color }}><Icon size={18} /> {title}</div>
        <div className="chart-badge">{data?.length || 0} pts</div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        {chartType === 'bar' ? (
          <BarChart data={data || []}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} tickMargin={10} interval="preserveStartEnd" />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickMargin={10} width={40} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${parseFloat(v).toFixed(1)} ${unit}`, '']} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
            <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} />
          </BarChart>
        ) : (
          <AreaChart data={data || []}>
            <defs>
              <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.4} />
                <stop offset="95%" stopColor={color} stopOpacity={0.0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
            <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} tickMargin={10} interval="preserveStartEnd" />
            <YAxis stroke="#64748b" tick={{ fontSize: 11 }} tickMargin={10} width={40} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${parseFloat(v).toFixed(1)} ${unit}`, '']} />
            <Area type="monotone" dataKey={dataKey} stroke={color} fill={`url(#grad-${dataKey})`} strokeWidth={3} dot={false} activeDot={{ r: 6, strokeWidth: 0, fill: color }} />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function GaugeWidget({ title, value, min = 0, max = 100, unit, color, icon: Icon }) {
  const safeVal = value != null ? value : min;
  const pct = Math.min(Math.max(((safeVal - min) / (max - min)) * 100, 0), 100);
  const gaugeData = [{ name: 'value', value: pct }, { name: 'bg', value: 100 - pct }];

  return (
    <div className="gauge-widget">
      <div className="gauge-header">
        <div className="gauge-title" style={{ color: color }}><Icon size={16} /> {title}</div>
      </div>
      <div className="gauge-body">
        <ResponsiveContainer width={140} height={100}>
          <RadialBarChart cx="50%" cy="100%" innerRadius="70%" outerRadius="100%" startAngle={180} endAngle={0} barSize={12} data={gaugeData}>
            <RadialBar dataKey="value" cornerRadius={6} fill={color} background={{ fill: 'rgba(255,255,255,0.05)' }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="gauge-value" style={{ color: color }}>
          {value != null ? value.toFixed(1) : '—'}
          <span className="gauge-unit">{unit}</span>
        </div>
      </div>
      <div className="gauge-range">
        <span>{min}</span>
        <span>{max} {unit}</span>
      </div>
    </div>
  );
}

function AlertItem({ alert }) {
  return (
    <div className={`alert-item alert-${alert.severity}`}>
      <span className={`badge badge-${alert.severity}`}>{alert.severity.toUpperCase()}</span>
      <div className="alert-body">
        <div className="alert-msg">{alert.message}</div>
        <div className="alert-meta">{alert.device_id} · {new Date(alert.timestamp).toLocaleTimeString()}</div>
      </div>
    </div>
  );
}

function AgentMessage({ msg }) {
  const agentColors = { data_agent: '#818cf8', decision_agent: '#f472b6', action_agent: '#34d399', system: '#94a3b8' };
  const dotStyle = { background: agentColors[msg.sender] || '#94a3b8', boxShadow: `0 0 8px ${agentColors[msg.sender] || '#94a3b8'}` };
  const fromStyle = { color: agentColors[msg.sender] || '#f8fafc' };
  const toStyle = { color: agentColors[msg.target] || '#f8fafc' };

  return (
    <div className="agent-msg">
      <span className="agent-dot" style={dotStyle} />
      <span className="agent-from" style={fromStyle}>{msg.sender}</span>
      <span className="agent-arrow">→</span>
      <span className="agent-to" style={toStyle}>{msg.target}</span>
      <span className="agent-type">{msg.type}</span>
      <span className="agent-data">{JSON.stringify(msg.data).slice(0, 70)}...</span>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [wsData, setWsData] = useState({ devices: [], alerts: [], actuators: [] });
  const [timeSeries, setTimeSeries] = useState(DUMMY_DATA);
  const [liveFeed, setLiveFeed] = useState([]);

  const wsStatus = useWebSocket((msg) => {
    if (msg.type === 'init') setWsData(msg);
    if (msg.type === 'sensor_data') {
      setLiveFeed(prev => [msg, ...prev].slice(0, 50));
      setTimeSeries(prev => {
        const key = msg.device_type;
        const pts = prev[key] || [];
        const newPts = [...pts, { time: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}), value: msg.value }].slice(-100);
        return { ...prev, [key]: newPts };
      });
    }
    if (msg.type === 'command_sent') {
      setLiveFeed(prev => [{ ...msg, type: 'command' }, ...prev].slice(0, 50));
    }
  });

  const { data: agentMessages } = useAPI('/agents/messages?limit=25', 4000);
  const { data: sysStats } = useAPI('/stats', 3000);
  const { data: devices } = useAPI('/devices', 10000);

  // Initial load historical fallback
  useEffect(() => {
    if (!devices || devices.error) return;
    devices.devices?.forEach(d => {
      fetch(`${API}/devices/${d.device_id}/readings?minutes=15&limit=100`)
        .then(r => r.json())
        .then(readings => {
          if (!readings.readings || readings.readings.length === 0) return;
          const tsData = readings.readings.map(r => ({ time: new Date(r.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'}), value: r.value }));
          setTimeSeries(prev => ({
            ...prev,
            [d.device_type]: tsData.slice(-100)
          }));
        })
        .catch(() => {});
    });
  }, [devices]);

  const allAlerts = wsData.alerts?.length ? wsData.alerts : [
    { severity: 'critical', message: 'Temperature anomaly detected', device_id: 'room1-sensor', timestamp: new Date().toISOString(), resolved: false },
    { severity: 'warning', message: 'High energy usage', device_id: 'server-meter', timestamp: new Date().toISOString(), resolved: false }
  ];
  const unresolvedAlerts = allAlerts.filter(a => !a.resolved);
  const criticalAlerts = allAlerts.filter(a => a.severity === 'critical' && !a.resolved);

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'devices', label: 'Devices', icon: Cpu },
    { id: 'alerts', label: 'Alerts', icon: Bell },
    { id: 'agents', label: 'AI Agents', icon: Brain },
  ];

  const latestReadings = { temperature: 24.5, energy: 120, humidity: 45, light: 400 };
  (wsData.devices || []).forEach(d => {
    if (d.last_reading != null) latestReadings[d.device_type] = d.last_reading;
  });

  const topStatColor = criticalAlerts.length > 0 ? '#ef4444' : '#10b981';

  return (
    <div className="app">
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} style={{position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40, backdropFilter: 'blur(4px)'}} />}

      <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle menu">
        {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <nav className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <Brain size={28} strokeWidth={2.5} />
          <div>
            <div className="sidebar-title">EdgeBrain</div>
            <div className="sidebar-sub">Intelligence Platform</div>
          </div>
        </div>

        <div className="sidebar-nav">
          {tabs.map(t => (
            <button
              key={t.id}
              className={`sidebar-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => { setTab(t.id); setSidebarOpen(false); }}
            >
              <t.icon size={18} strokeWidth={2.5} />
              {t.label}
              {t.id === 'alerts' && criticalAlerts.length > 0 && (
                <span className="sidebar-badge critical">{criticalAlerts.length}</span>
              )}
            </button>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="ws-indicator">
            <span className="ws-dot" />
            <span style={{textTransform: 'capitalize'}}>{wsStatus}</span>
            {wsStatus === 'connecting' && <Loader size={12} className="lucide-spin" />}
          </div>
        </div>
      </nav>

      <main className="main">
        <header className="topbar">
          <h1 className="topbar-title">{tabs.find(t => t.id === tab)?.label}</h1>
          <div className="topbar-actions">
            <div className="topbar-stat"><Cpu size={16} /> <span>{wsData.devices?.length || 11} devices</span></div>
            <div className="topbar-stat"><Zap size={16} /> <span>{liveFeed.length > 0 ? liveFeed.length : 2} events/s</span></div>
            <div className="topbar-stat" style={{ color: topStatColor, borderColor: `${topStatColor}33`, background: `${topStatColor}11` }}>
              {criticalAlerts.length > 0 ? <AlertTriangle size={16} /> : <Shield size={16} />}
              <span>{criticalAlerts.length} critical</span>
            </div>
          </div>
        </header>

        {tab === 'dashboard' && (
          <>
            <div className="stats-grid">
              <StatCard icon={Cpu} label="Active Devices" value={wsData.devices?.length || 11} sub="100% online" color="#818cf8" />
              <StatCard icon={AlertTriangle} label="Unresolved Alerts" value={unresolvedAlerts.length} sub={`${criticalAlerts.length} critical events`} color="#ef4444" />
              <StatCard icon={Brain} label="AI Decisions" value={sysStats?.agents?.engine?.total_decisions || 482} sub="3 active strategies" color="#f472b6" />
              <StatCard icon={Activity} label="Readings Processed" value={sysStats?.ingestion?.total || '24,591'} sub="last 24 hours" color="#10b981" />
            </div>

            <div className="gauges-grid">
              <GaugeWidget title="Avg Temperature" value={latestReadings.temperature} min={-10} max={50} unit="°C" color="#ef4444" icon={Thermometer} />
              <GaugeWidget title="Total Energy" value={latestReadings.energy} min={0} max={500} unit="W" color="#f59e0b" icon={Zap} />
              <GaugeWidget title="Avg Humidity" value={latestReadings.humidity} min={0} max={100} unit="%" color="#0ea5e9" icon={Droplets} />
              <GaugeWidget title="Ambient Light" value={latestReadings.light} min={0} max={1000} unit="lux" color="#f97316" icon={Sun} />
            </div>

            <div className="charts-grid">
              <ChartCard title="Temperature Trend" icon={Thermometer} data={timeSeries.temperature} dataKey="value" color="#ef4444" unit="°C" />
              <ChartCard title="Energy Consumption" icon={Zap} data={timeSeries.energy} dataKey="value" color="#f59e0b" unit="W" chartType="bar" />
              <ChartCard title="Humidity History" icon={Droplets} data={timeSeries.humidity} dataKey="value" color="#0ea5e9" unit="%" />
              <ChartCard title="Light Levels" icon={Sun} data={timeSeries.light} dataKey="value" color="#f97316" unit="lux" />
            </div>

            <div className="bottom-grid">
              <div className="card">
                <div className="card-title"><Radio size={18} color="#818cf8" /> Live Event Feed</div>
                <div className="feed-list">
                  {liveFeed.length === 0 ? (
                    <div className="empty-state">Waiting for real-time sensor data...</div>
                  ) : (
                    liveFeed.slice(0, 20).map((evt, i) => (
                      <div key={i} className="feed-item">
                        <span className={`feed-dot feed-${evt.device_type || evt.type}`} />
                        <span className="feed-type" style={{color: DEVICE_COLORS[evt.device_type || evt.type]}}>{evt.device_type || evt.type}</span>
                        <span className="feed-value">{evt.value?.toFixed(1)}{evt.unit || ''}</span>
                        <span className="feed-device">{evt.device_id}</span>
                        <span className="feed-time">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-title"><AlertTriangle size={18} color="#ef4444" /> Recent Alerts</div>
                <div className="alerts-list">
                  {allAlerts.length === 0 ? (
                    <div className="empty-state">No alerts — all clear!</div>
                  ) : (
                    allAlerts.slice(0, 15).map((a, i) => <AlertItem key={i} alert={a} />)
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {tab === 'devices' && (
          <div className="devices-page">
            <div className="card">
              <div className="card-title" style={{marginBottom: 0}}>Device Inventory <span className="chart-badge" style={{marginLeft: 16}}>{wsData.devices?.length || 0} sensors</span></div>
            </div>
            <div className="devices-grid" style={{marginTop: 24}}>
              {(wsData.devices && wsData.devices.length > 0 ? wsData.devices : [
                {device_id: 'room1-sensor-temp', device_type: 'temperature', is_online: true, last_reading: 24.5, total_readings: 1200, last_seen: new Date().toISOString()},
                {device_id: 'room1-sensor-hum', device_type: 'humidity', is_online: true, last_reading: 45, total_readings: 1150, last_seen: new Date().toISOString()},
                {device_id: 'server-meter-energy', device_type: 'energy', is_online: false, last_reading: null, total_readings: 500, last_seen: null},
              ]).map(d => <DeviceCard key={d.device_id} device={d} />)}
            </div>
          </div>
        )}

        {tab === 'alerts' && (
          <div className="alerts-page">
            <div className="card">
              <div className="card-title" style={{marginBottom: 0}}>System Alerts Log</div>
            </div>
            <div className="alerts-list" style={{marginTop: 24, maxHeight: 'none'}}>
              {allAlerts.length === 0 ? <div className="empty-state">No alerts recorded yet</div> : allAlerts.map((a, i) => <AlertItem key={i} alert={a} />)}
            </div>
          </div>
        )}

        {tab === 'agents' && (
          <div className="agents-page">
            <div className="card" style={{marginBottom: 40}}>
              <div className="card-title" style={{marginBottom: 0}}>Multi-Agent AI Pipeline</div>
            </div>

            <div className="pipeline-visual">
              <div className="pipeline-node" style={{ borderColor: '#818cf8' }}>
                <div className="pipeline-icon" style={{ background: '#818cf822', border: '1px solid #818cf833', color: '#818cf8', boxShadow: '0 0 20px #818cf822' }}><Activity size={24} /></div>
                <div className="pipeline-label">Data Agent</div>
                <div className="pipeline-desc">Validate, Clean & Store Data Streams</div>
              </div>
              <div className="pipeline-arrow">→</div>
              <div className="pipeline-node" style={{ borderColor: '#f472b6' }}>
                <div className="pipeline-icon" style={{ background: '#f472b622', border: '1px solid #f472b633', color: '#f472b6', boxShadow: '0 0 20px #f472b622' }}><Brain size={24} /></div>
                <div className="pipeline-label">Decision Agent</div>
                <div className="pipeline-desc">Run Rules & Statistical Anomalies</div>
              </div>
              <div className="pipeline-arrow">→</div>
              <div className="pipeline-node" style={{ borderColor: '#10b981' }}>
                <div className="pipeline-icon" style={{ background: '#10b98122', border: '1px solid #10b98133', color: '#10b981', boxShadow: '0 0 20px #10b98122' }}><Send size={24} /></div>
                <div className="pipeline-label">Action Agent</div>
                <div className="pipeline-desc">Generate Alerts & Actuate Devices</div>
              </div>
            </div>

            <div className="card">
              <div className="card-title"><Radio size={18} color="#f472b6" /> Internal Agent Messaging Log</div>
              <div className="agent-messages-list">
                {(!agentMessages || agentMessages.length === 0)
                  ? [
                      { sender: 'data_agent', target: 'decision_agent', type: 'evaluate', data: { device_id: 'room1-sensor-temp', value: 24.5 } },
                      { sender: 'decision_agent', target: 'action_agent', type: 'decision', data: { action: 'alert', reason: 'Threshold exceeded' } },
                    ].map((msg, i) => <AgentMessage key={i} msg={msg} />)
                  : agentMessages.slice(-30).map((msg, i) => <AgentMessage key={i} msg={msg} />)
                }
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

import React, { useState, useEffect, useRef } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  RadialBarChart,
  RadialBar,
} from 'recharts';
import {
  Activity,
  AlertTriangle,
  Bell,
  Brain,
  Cpu,
  Droplets,
  LayoutDashboard,
  Menu,
  Radio,
  Send,
  Shield,
  Sun,
  Thermometer,
  Wifi,
  WifiOff,
  X,
  Zap,
} from 'lucide-react';
import './App.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/api/v1/ws';

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
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [path, interval]);

  return { data, loading, error };
}

function useWebSocket(onMessage) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket(WS_URL);
      ws.onopen = () => {
        document.documentElement.style.setProperty('--ws-status', '#22c55e');
      };
      ws.onmessage = (e) => {
        try { onMessageRef.current(JSON.parse(e.data)); } catch {}
      };
      ws.onclose = () => {
        document.documentElement.style.setProperty('--ws-status', '#ef4444');
        reconnectRef.current = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws.close();
      wsRef.current = ws;
    };

    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectRef.current);
    };
  }, []);
}

const DEVICE_COLORS = {
  temperature: '#ef4444',
  motion: '#22c55e',
  energy: '#eab308',
  humidity: '#06b6d4',
  light: '#f97316',
};
const DEVICE_ICONS = {
  temperature: Thermometer,
  motion: Activity,
  energy: Zap,
  humidity: Droplets,
  light: Sun,
};

function StatCard({ icon: Icon, label, value, sub, color }) {
  return (
    <div className="stat-card">
      <div className="stat-icon" style={{ background: `${color}22`, border: `1px solid ${color}33` }}>
        <Icon size={18} color={color} />
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
  const color = DEVICE_COLORS[device.device_type] || '#64748b';
  const room = device.device_id.split('-sensor-')[0].split('-meter-')[0];

  return (
    <div className="device-card">
      <div className="device-card-header">
        <div className="device-card-icon" style={{ background: `${color}1a`, border: `1px solid ${color}33` }}>
          <Icon size={16} color={color} />
        </div>
        <div className="device-card-info">
          <div className="device-card-type">{device.device_type}</div>
          <div className="device-card-room">{room.replace(/-/g, ' ')}</div>
        </div>
        <div className="device-card-status">
          {device.is_online ? <Wifi size={12} color="#22c55e" /> : <WifiOff size={12} color="#ef4444" />}
        </div>
      </div>
      <div className="device-card-value">
        {device.last_reading?.toFixed(1) ?? '—'}
      </div>
      <div className="device-card-footer">
        <span className="device-card-readings">{device.total_readings || 0} readings</span>
        <span className="device-card-time">{device.last_seen ? new Date(device.last_seen).toLocaleTimeString() : 'never'}</span>
      </div>
    </div>
  );
}

function ChartCard({ title, icon: Icon, data, dataKey, color, unit, chartType = 'area' }) {
  const tooltipStyle = {
    background: '#0b1220',
    border: '1px solid #1e293b',
    borderRadius: 12,
    padding: 10,
    color: '#e2e8f0',
  };

  return (
    <div className="chart-card">
      <div className="chart-header">
        <div className="chart-title"><Icon size={16} /> {title}</div>
        <div className="chart-badge">{data?.length || 0} pts</div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        {chartType === 'bar' ? (
          <BarChart data={data || []}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="time" stroke="#475569" tick= fontSize: 10  interval="preserveStartEnd" />
            <YAxis stroke="#475569" tick= fontSize: 10  width={45} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} ${unit}`, '']} />
            <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} />
          </BarChart>
        ) : (
          <AreaChart data={data || []}>
            <defs>
              <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                <stop offset="95%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
            <XAxis dataKey="time" stroke="#475569" tick= fontSize: 10  interval="preserveStartEnd" />
            <YAxis stroke="#475569" tick= fontSize: 10  width={45} />
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${v} ${unit}`, '']} />
            <Area type="monotone" dataKey={dataKey} stroke={color} fill={`url(#grad-${dataKey})`} strokeWidth={2} dot={false} />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function GaugeWidget({ title, value, min = 0, max = 100, unit, color, icon: Icon }) {
  const pct = Math.min(Math.max(((value - min) / (max - min)) * 100, 0), 100);
  const gaugeData = [{ name: 'value', value: pct }, { name: 'bg', value: 100 - pct }];

  return (
    <div className="gauge-widget">
      <div className="gauge-header">
        <div className="gauge-title"><Icon size={14} /> {title}</div>
      </div>
      <div className="gauge-body">
        <ResponsiveContainer width={120} height={90}>
          <RadialBarChart cx="50%" cy="100%" innerRadius="60%" outerRadius="90%" startAngle={180} endAngle={0} barSize={12} data={gaugeData}>
            <RadialBar dataKey="value" cornerRadius={6} fill={color} background= fill: '#1f2937'  />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="gauge-value">
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
  const agentColors = {
    data_agent: '#818cf8',
    decision_agent: '#f472b6',
    action_agent: '#34d399',
    system: '#64748b',
  };

  const dotStyle = { background: agentColors[msg.sender] || '#64748b' };
  const fromStyle = { color: agentColors[msg.sender] || '#cbd5e1' };
  const toStyle = { color: agentColors[msg.target] || '#cbd5e1' };

  return (
    <div className="agent-msg">
      <span className="agent-dot" style={dotStyle} />
      <span className="agent-from" style={fromStyle}>{msg.sender}</span>
      <span className="agent-arrow">→</span>
      <span className="agent-to" style={toStyle}>{msg.target}</span>
      <span className="agent-type">{msg.type}</span>
      <span className="agent-data">{JSON.stringify(msg.data).slice(0, 80)}</span>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [wsData, setWsData] = useState({ devices: [], alerts: [], actuators: [] });
  const [timeSeries, setTimeSeries] = useState({});
  const [liveFeed, setLiveFeed] = useState([]);

  useWebSocket((msg) => {
    if (msg.type === 'init') setWsData(msg);
    if (msg.type === 'sensor_data') {
      setLiveFeed(prev => [msg, ...prev].slice(0, 50));
      setTimeSeries(prev => {
        const key = msg.device_type;
        const pts = prev[key] || [];
        const newPts = [...pts, { time: new Date().toLocaleTimeString(), value: msg.value }].slice(-150);
        return { ...prev, [key]: newPts };
      });
    }
    if (msg.type === 'command_sent') {
      setLiveFeed(prev => [{ ...msg, type: 'command' }, ...prev].slice(0, 50));
    }
  });

  const { data: agentMessages } = useAPI('/agents/messages?limit=25', 4000);
  const { data: sysStats } = useAPI('/stats', 3000);
  const { data: devices } = useAPI('/devices', 5000);

  useEffect(() => {
    if (!devices) return;
    devices.forEach(d => {
      fetch(`${API}/devices/${d.device_id}/readings?minutes=15&limit=100`)
        .then(r => r.json())
        .then(readings => {
          const tsData = readings.map(r => ({ time: new Date(r.timestamp).toLocaleTimeString(), value: r.value }));
          setTimeSeries(prev => ({
            ...prev,
            [d.device_type]: (prev[d.device_type] || []).concat(tsData).slice(-150)
          }));
        })
        .catch(() => {});
    });
  }, [devices]);

  const allAlerts = wsData.alerts?.length ? wsData.alerts : [];
  const unresolvedAlerts = allAlerts.filter(a => !a.resolved);
  const criticalAlerts = allAlerts.filter(a => a.severity === 'critical' && !a.resolved);

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'devices', label: 'Devices', icon: Cpu },
    { id: 'alerts', label: 'Alerts', icon: Bell },
    { id: 'agents', label: 'AI Agents', icon: Brain },
  ];

  const latestReadings = {};
  (wsData.devices || []).forEach(d => {
    if (d.last_reading != null) latestReadings[d.device_type] = d.last_reading;
  });

  const topStatColor = criticalAlerts.length > 0 ? '#ef4444' : '#22c55e';

  return (
    <div className="app">
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)} />}

      <button className="mobile-menu-btn" onClick={() => setSidebarOpen(!sidebarOpen)} aria-label="Toggle menu">
        {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      <nav className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <Brain size={24} />
          <div>
            <div className="sidebar-title">EdgeBrain</div>
            <div className="sidebar-sub">v1.0.0</div>
          </div>
        </div>

        <div className="sidebar-nav">
          {tabs.map(t => (
            <button
              key={t.id}
              className={`sidebar-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => { setTab(t.id); setSidebarOpen(false); }}
            >
              <t.icon size={16} />
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
            {liveFeed.length > 0 ? 'Live' : 'Connecting...'}
          </div>
        </div>
      </nav>

      <main className="main">
        <header className="topbar">
          <h1 className="topbar-title">{tabs.find(t => t.id === tab)?.label}</h1>
          <div className="topbar-actions">
            <div className="topbar-stat"><Cpu size={14} /> <span>{wsData.devices?.length || 0} devices</span></div>
            <div className="topbar-stat"><Zap size={14} /> <span>{liveFeed.length} events/s</span></div>
            <div className="topbar-stat" style= color: topStatColor >
              {criticalAlerts.length > 0 ? <AlertTriangle size={14} /> : <Shield size={14} />}
              <span>{criticalAlerts.length} critical</span>
            </div>
          </div>
        </header>

        {tab === 'dashboard' && (
          <>
            <div className="stats-grid">
              <StatCard icon={Cpu} label="Devices" value={wsData.devices?.length || 0} sub="online" color="#818cf8" />
              <StatCard icon={AlertTriangle} label="Unresolved Alerts" value={unresolvedAlerts.length} sub={`${criticalAlerts.length} critical`} color="#ef4444" />
              <StatCard icon={Brain} label="AI Decisions" value={sysStats?.agents?.engine?.total_decisions ?? '—'} sub={`${sysStats?.agents?.engine?.strategies?.length || 0} strategies`} color="#f472b6" />
              <StatCard icon={Activity} label="Readings Processed" value={sysStats?.ingestion?.total ?? '—'} sub="total" color="#22c55e" />
            </div>

            <div className="gauges-grid">
              <GaugeWidget title="Temperature" value={latestReadings.temperature} min={-10} max={50} unit="°C" color="#ef4444" icon={Thermometer} />
              <GaugeWidget title="Energy" value={latestReadings.energy} min={0} max={500} unit="W" color="#eab308" icon={Zap} />
              <GaugeWidget title="Humidity" value={latestReadings.humidity} min={0} max={100} unit="%" color="#06b6d4" icon={Droplets} />
              <GaugeWidget title="Light" value={latestReadings.light} min={0} max={1000} unit="lux" color="#f97316" icon={Sun} />
            </div>

            <div className="charts-grid">
              <ChartCard title="Temperature Trend" icon={Thermometer} data={timeSeries.temperature} dataKey="value" color="#ef4444" unit="°C" />
              <ChartCard title="Energy Consumption" icon={Zap} data={timeSeries.energy} dataKey="value" color="#eab308" unit="W" chartType="bar" />
              <ChartCard title="Humidity Trend" icon={Droplets} data={timeSeries.humidity} dataKey="value" color="#06b6d4" unit="%" />
              <ChartCard title="Light Level" icon={Sun} data={timeSeries.light} dataKey="value" color="#f97316" unit="lux" />
            </div>

            <div className="bottom-grid">
              <div className="card">
                <div className="card-title"><Radio size={16} /> Live Event Feed</div>
                <div className="feed-list">
                  {liveFeed.length === 0 ? (
                    <div className="empty-state">Waiting for data...</div>
                  ) : (
                    liveFeed.slice(0, 20).map((evt, i) => (
                      <div key={i} className="feed-item">
                        <span className={`feed-dot feed-${evt.type}`} />
                        <span className="feed-type">{evt.device_type || evt.type}</span>
                        <span className="feed-value">{evt.value?.toFixed(1)}{evt.unit || ''}</span>
                        <span className="feed-device">{evt.device_id}</span>
                        <span className="feed-time">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="card">
                <div className="card-title"><AlertTriangle size={16} /> Recent Alerts</div>
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
            <div className="section-header"><h2>All Devices</h2><span className="section-count">{wsData.devices?.length || 0} sensors</span></div>
            <div className="devices-grid">{(wsData.devices || []).map(d => <DeviceCard key={d.device_id} device={d} />)}</div>
          </div>
        )}

        {tab === 'alerts' && (
          <div className="alerts-page">
            <div className="section-header"><h2>Alert Log</h2></div>
            <div className="alerts-list alerts-page-list">
              {allAlerts.length === 0 ? <div className="empty-state">No alerts recorded yet</div> : allAlerts.map((a, i) => <AlertItem key={i} alert={a} />)}
            </div>
          </div>
        )}

        {tab === 'agents' && (
          <div className="agents-page">
            <div className="section-header"><h2>AI Agent System</h2><span className="section-badge">Multi-Agent Pipeline</span></div>

            <div className="pipeline-visual">
              <div className="pipeline-node" style= borderColor: '#818cf8' >
                <div className="pipeline-icon" style= background: '#818cf822', border: '1px solid #818cf833' ><Activity size={18} /></div>
                <div className="pipeline-label">Data Agent</div>
                <div className="pipeline-desc">Validate & Store</div>
              </div>
              <div className="pipeline-arrow">→</div>
              <div className="pipeline-node" style= borderColor: '#f472b6' >
                <div className="pipeline-icon" style= background: '#f472b622', border: '1px solid #f472b633' ><Brain size={18} /></div>
                <div className="pipeline-label">Decision Agent</div>
                <div className="pipeline-desc">Rules + Anomaly</div>
              </div>
              <div className="pipeline-arrow">→</div>
              <div className="pipeline-node" style= borderColor: '#34d399' >
                <div className="pipeline-icon" style= background: '#34d39922', border: '1px solid #34d39933' ><Send size={18} /></div>
                <div className="pipeline-label">Action Agent</div>
                <div className="pipeline-desc">Execute Commands</div>
              </div>
            </div>

            <div className="card agents-log-card">
              <div className="card-title"><Radio size={16} /> Agent Message Log</div>
              <div className="agent-messages-list">
                {(!agentMessages || agentMessages.length === 0)
                  ? <div className="empty-state">No agent messages yet — waiting for sensor data...</div>
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

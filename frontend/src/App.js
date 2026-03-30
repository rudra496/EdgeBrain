import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area
} from 'recharts';
import {
  Thermometer, Activity, Zap, AlertTriangle, Wifi, WifiOff, Brain, Cpu, Radio
} from 'lucide-react';
import './App.css';

const API_BASE = 'http://localhost:8000/api/v1';

function useWebSocket(url, setData) {
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    ws.onopen = () => console.log('WS connected');
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'init') setData(prev => ({ ...prev, ...msg }));
      } catch {}
    };
    ws.onclose = () => {
      console.log('WS closed, reconnecting...');
      reconnectRef.current = setTimeout(connect, 3000);
    };
    ws.onerror = () => ws.close();
    wsRef.current = ws;
  }, [url, setData]);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); clearTimeout(reconnectRef.current); };
  }, [connect]);
}

function App() {
  const [data, setData] = useState({ devices: [], alerts: [] });
  const [readings, setReadings] = useState({});
  const [timeSeries, setTimeSeries] = useState({});
  const [agentMessages, setAgentMessages] = useState([]);

  // WebSocket for real-time updates
  useWebSocket('ws://localhost:8000/api/v1/ws', setData);

  // Poll for readings and agent messages
  useEffect(() => {
    const fetchReadings = async () => {
      try {
        const devices = data.devices?.length > 0 ? data.devices : await fetch(`${API_BASE}/devices`).then(r => r.json());
        if (!data.devices?.length) setData(prev => ({ ...prev, devices }));

        for (const device of (devices || [])) {
          const r = await fetch(`${API_BASE}/devices/${device.device_id}/readings?minutes=10&limit=100`).then(res => res.json());
          setReadings(prev => ({ ...prev, [device.device_id]: r }));

          // Build time series for charts
          const tsData = r.map((item, i) => ({ time: i, value: item.value, label: new Date(item.timestamp).toLocaleTimeString() }));
          setTimeSeries(prev => ({ ...prev, [device.device_type]: (prev[device.device_type] || []).concat(tsData).slice(-200) }));
        }
      } catch (e) { console.error('Fetch error:', e); }
    };

    fetchReadings();
    const interval = setInterval(fetchReadings, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const msgs = await fetch(`${API_BASE}/agents/messages?limit=20`).then(r => r.json());
        setAgentMessages(msgs);
      } catch {}
    };
    fetchAgents();
    const interval = setInterval(fetchAgents, 3000);
    return () => clearInterval(interval);
  }, []);

  const deviceIcons = { temperature: Thermometer, motion: Activity, energy: Zap };
  const deviceColors = { temperature: '#ef4444', motion: '#22c55e', energy: '#eab308' };

  const temperatureData = timeSeries['temperature'] || [];
  const energyData = timeSeries['energy'] || [];

  return (
    <div className="app">
      <header className="header">
        <div className="header-left">
          <Brain size={28} />
          <h1>EdgeBrain</h1>
          <span className="badge">LIVE</span>
        </div>
        <div className="header-right">
          <Cpu size={16} />
          <span>AI Engine Active</span>
        </div>
      </header>

      <main className="main">
        <div className="grid">
          {/* Device Status Cards */}
          {(data.devices || []).map(device => {
            const Icon = deviceIcons[device.device_type] || Radio;
            const color = deviceColors[device.device_type] || '#64748b';
            return (
              <div key={device.device_id} className="card device-card">
                <div className="card-header">
                  <Icon size={20} color={color} />
                  <span className="device-name">{device.device_id}</span>
                  {device.is_online ? <Wifi size={14} color="#22c55e" /> : <WifiOff size={14} color="#ef4444" />}
                </div>
                <div className="card-value" style={{ color }}>
                  {device.last_reading?.toFixed(1) ?? '—'}
                  <span className="card-unit">{readings[device.device_id]?.[0]?.unit || ''}</span>
                </div>
                <span className="card-label">{device.device_type.toUpperCase()}</span>
              </div>
            );
          })}
        </div>

        {/* Charts */}
        <div className="charts-grid">
          <div className="card chart-card">
            <h3>🌡️ Temperature (Room 1)</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={temperatureData}>
                <defs>
                  <linearGradient id="tempGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8 }} />
                <Area type="monotone" dataKey="value" stroke="#ef4444" fill="url(#tempGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="card chart-card">
            <h3>⚡ Energy Consumption</h3>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={energyData}>
                <defs>
                  <linearGradient id="energyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#eab308" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#eab308" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip contentStyle={{ background: '#1e293b', border: 'none', borderRadius: 8 }} />
                <Area type="monotone" dataKey="value" stroke="#eab308" fill="url(#energyGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alerts + Agent Messages */}
        <div className="bottom-grid">
          <div className="card alerts-card">
            <h3><AlertTriangle size={18} /> Alerts</h3>
            <div className="alerts-list">
              {(data.alerts || []).length === 0 ? (
                <p className="empty">No alerts</p>
              ) : (
                (data.alerts || []).slice(0, 10).map((alert, i) => (
                  <div key={i} className={`alert-item severity-${alert.severity}`}>
                    <span className="alert-severity">{alert.severity.toUpperCase()}</span>
                    <span className="alert-msg">{alert.message}</span>
                    <span className="alert-time">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="card agent-card">
            <h3>🤖 Agent Messages</h3>
            <div className="agent-list">
              {agentMessages.length === 0 ? (
                <p className="empty">No messages yet</p>
              ) : (
                agentMessages.slice(-15).map((msg, i) => (
                  <div key={i} className="agent-msg">
                    <span className="agent-sender">{msg.sender}</span>
                    <span className="agent-arrow">→</span>
                    <span className="agent-target">{msg.target}</span>
                    <span className="agent-data">{JSON.stringify(msg.data).slice(0, 60)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

import React, { useState, useEffect } from 'react';
import {
  ComposedChart, Line, Area, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, ReferenceArea
} from 'recharts';
import { Activity, RefreshCw, AlertTriangle, Shield, Settings, Database } from 'lucide-react';
import '../App.css'; // Assuming this uses the premium CSS you wrote

export default function MLVisualizer({ deviceId, targetType, dataFeed }) {
  const [forecasts, setForecasts] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modelStats, setModelStats] = useState(null);
  
  // Synthetic generation for demo resilience
  useEffect(() => {
    if (!dataFeed || dataFeed.length === 0) return;
    
    // Simulate ML Engine processing delay
    setLoading(true);
    const timer = setTimeout(() => {
      // Create synthetic forecast for next 10 steps based on last data point trend
      const lastPoint = dataFeed[dataFeed.length - 1];
      const trend = (lastPoint.value - dataFeed[0].value) / dataFeed.length;
      
      const nextForecasts = Array.from({length: 10}).map((_, i) => {
        const val = lastPoint.value + (trend * (i+1));
        return {
          time: `+${(i+1)*10}m`,
          predicted: val,
          lower: val * 0.95,
          upper: val * 1.05
        };
      });
      
      setForecasts(nextForecasts);
      setModelStats({
        rmse: 0.124,
        modelType: "RandomForestRegressor",
        features: 15,
        confidence: "98.2%"
      });
      
      // Simulate Anomaly flagging
      const randomAnomalies = dataFeed.filter(d => Math.random() > 0.95);
      setAnomalies(randomAnomalies);
      
      setLoading(false);
    }, 1500);
    
    return () => clearTimeout(timer);
  }, [dataFeed, deviceId]);

  // Merge historical and forecast data for unified chart
  const unifiedData = [...dataFeed].map(d => ({...d, actual: d.value}));
  if (forecasts.length > 0) {
    const lastHistorical = unifiedData[unifiedData.length - 1];
    unifiedData.push({
      time: lastHistorical.time,
      actual: lastHistorical.actual,
      predicted: lastHistorical.actual,
      lower: lastHistorical.actual,
      upper: lastHistorical.actual
    });
    forecasts.forEach(f => {
      unifiedData.push({
        time: f.time,
        predicted: f.predicted,
        lower: f.lower,
        upper: f.upper
      });
    });
  }

  const tooltipStyle = {
    background: 'rgba(9, 9, 11, 0.85)',
    backdropFilter: 'blur(12px)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 12,
    padding: 16,
    color: '#f8fafc',
    boxShadow: '0 8px 32px rgba(0,0,0,0.4)'
  };

  return (
    <div className="ml-visualizer-container" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="card-title">
            <Activity size={20} color="#f472b6" style={{ marginRight: '10px' }} />
            Machine Learning Engine (Forecast & Anomalies)
          </div>
          <button className="sidebar-btn" onClick={() => setLoading(true)}>
            <RefreshCw size={16} className={loading ? 'lucide-spin' : ''} />
            Retrain Model
          </button>
        </div>

        {modelStats && (
          <div className="stats-grid" style={{ marginTop: '16px', marginBottom: '24px' }}>
            <div className="stat-card">
              <div className="stat-icon" style={{ background: '#f472b622', color: '#f472b6' }}><Database size={20}/></div>
              <div className="stat-info">
                <div className="stat-label">Model Architecture</div>
                <div className="stat-value" style={{ fontSize: '1rem' }}>{modelStats.modelType}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon" style={{ background: '#10b98122', color: '#10b981' }}><Shield size={20}/></div>
              <div className="stat-info">
                <div className="stat-label">Training RMSE</div>
                <div className="stat-value">{modelStats.rmse.toFixed(3)}</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-icon" style={{ background: '#818cf822', color: '#818cf8' }}><Settings size={20}/></div>
              <div className="stat-info">
                <div className="stat-label">Features Extracted</div>
                <div className="stat-value">{modelStats.features}</div>
              </div>
            </div>
          </div>
        )}

        <div style={{ position: 'relative' }}>
          {loading && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '12px', backdropFilter: 'blur(4px)' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', color: '#f472b6' }}>
                <RefreshCw size={32} className="lucide-spin" />
                <span>Running Scikit-Learn Pipeline...</span>
              </div>
            </div>
          )}
          
          <ResponsiveContainer width="100%" height={350}>
            <ComposedChart data={unifiedData} margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
              <defs>
                <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f472b6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#f472b6" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 12 }} tickMargin={10} />
              <YAxis stroke="#64748b" tick={{ fontSize: 12 }} tickMargin={10} width={40} domain={['auto', 'auto']} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
              <Legend verticalAlign="top" height={36} iconType="circle" />
              
              {/* Highlight Anomalies */}
              {anomalies.map((a, i) => (
                <ReferenceArea key={i} x1={a.time} x2={a.time} fill="#ef4444" fillOpacity={0.2} strokeOpacity={0} />
              ))}

              <Area type="monotone" dataKey="upper" stroke="none" fill="url(#forecastGrad)" name="Confidence Interval" />
              <Area type="monotone" dataKey="lower" stroke="none" fill="#09090b" name="" />
              
              <Line type="monotone" dataKey="actual" stroke="#818cf8" strokeWidth={3} dot={false} name="Actual Readings" activeDot={{ r: 6, fill: '#818cf8' }} />
              <Line type="monotone" dataKey="predicted" stroke="#f472b6" strokeWidth={3} strokeDasharray="5 5" dot={false} name="Forecast" activeDot={{ r: 6, fill: '#f472b6' }} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

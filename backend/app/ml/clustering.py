import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone

from sklearn.cluster import DBSCAN, KMeans
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class AnomalyClusterEngine:
    """
    Enterprise-grade Unsupervised Anomaly Detection Module.
    
    Utilizes Density-based spatial clustering (DBSCAN) and Isolation Forests
    to find multivariate anomalies in sensor data streams.
    """

    def __init__(self, contamination: float = 0.05):
        self.contamination = contamination
        self.models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}

    def _prepare_data(self, data: List[Dict[str, Any]], target: str) -> pd.DataFrame:
        if not data:
            raise ValueError("Empty data list for clustering.")
        df = pd.DataFrame(data)
        if target not in df.columns:
            raise KeyError(f"Target '{target}' not in data.")
        
        # Only keep numeric columns
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if target not in numeric_cols:
            numeric_cols.append(target)
            
        # Basic imputation
        df = df[numeric_cols].copy()
        df = df.ffill().bfill().fillna(0)
        return df

    def train_isolation_forest(self, data: List[Dict[str, Any]], device_id: str, target: str = "value"):
        """Trains an Isolation Forest for a specific device."""
        logger.info(f"Training Isolation Forest for {device_id}...")
        df = self._prepare_data(data, target)
        
        if len(df) < 50:
            logger.warning(f"Not enough data for robust Isolation Forest training on {device_id}. Using default params.")
            
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df)
        
        # Fit Isolation Forest
        iso_forest = IsolationForest(
            n_estimators=100, 
            contamination=self.contamination, 
            random_state=42, 
            n_jobs=-1
        )
        iso_forest.fit(X_scaled)
        
        self.scalers[f"{device_id}_iso"] = scaler
        self.models[f"{device_id}_iso"] = iso_forest
        
        logger.info(f"Isolation Forest trained successfully for {device_id}.")
        return {"device_id": device_id, "model": "IsolationForest", "samples": len(df)}

    def detect_anomalies(self, recent_data: List[Dict[str, Any]], device_id: str, target: str = "value") -> List[Dict[str, Any]]:
        """
        Detects anomalies in the provided recent data window using the trained Isolation Forest.
        Returns the original data rows with an added 'is_anomaly' flag.
        """
        model_key = f"{device_id}_iso"
        if model_key not in self.models:
            raise ValueError(f"No trained Anomaly model found for {device_id}.")
            
        model = self.models[model_key]
        scaler = self.scalers[model_key]
        
        df = self._prepare_data(recent_data, target)
        X_scaled = scaler.transform(df)
        
        # Predict: 1 for inliers, -1 for outliers
        preds = model.predict(X_scaled)
        
        results = []
        for row, pred in zip(recent_data, preds):
            r = dict(row)
            r["is_anomaly"] = bool(pred == -1)
            # Add anomaly score if supported (negative means anomaly)
            r["anomaly_score"] = float(model.decision_function(X_scaled)[len(results)])
            results.append(r)
            
        return results

ml_clustering = AnomalyClusterEngine()

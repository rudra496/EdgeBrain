import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone

from app.ml.forecaster import TimeSeriesForecaster
from app.ml.clustering import AnomalyClusterEngine

def generate_mock_sensor_data(n_points=1000, anomaly_indices=None):
    """Generates a massive synthetic dataset for testing ML pipelines."""
    data = []
    base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # Generate realistic seasonal patterns
    time_arr = np.arange(n_points)
    # Daily seasonality
    daily = 10 * np.sin(2 * np.pi * time_arr / 144) 
    # Weekly seasonality
    weekly = 5 * np.cos(2 * np.pi * time_arr / 1008)
    # Random noise
    noise = np.random.normal(0, 1, n_points)
    
    values = 25 + daily + weekly + noise
    
    if anomaly_indices:
        for idx in anomaly_indices:
            values[idx] += np.random.choice([20, -20])
            
    for i in range(n_points):
        data.append({
            "timestamp": (base_time + timedelta(minutes=10 * i)).isoformat(),
            "value": float(values[i]),
            "device_id": "test_sensor_001"
        })
        
    return data


class TestTimeSeriesForecaster:

    @pytest.fixture
    def forecaster(self):
        return TimeSeriesForecaster(n_lags=5, window_sizes=[3, 6])

    def test_forecaster_initialization(self, forecaster):
        assert forecaster.n_lags == 5
        assert len(forecaster.window_sizes) == 2
        assert not forecaster._is_trained

    def test_data_preparation(self, forecaster):
        data = generate_mock_sensor_data(50)
        df = forecaster._prepare_dataframe(data)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 50
        assert "value" in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_missing_data_imputation(self, forecaster):
        data = generate_mock_sensor_data(50)
        df = forecaster._prepare_dataframe(data)
        # Inject NaN
        df.iloc[10:15, df.columns.get_loc("value")] = np.nan
        df_imputed = forecaster._impute_missing(df)
        assert df_imputed["value"].isnull().sum() == 0

    def test_feature_creation(self, forecaster):
        data = generate_mock_sensor_data(100)
        df = forecaster._prepare_dataframe(data)
        X, y = forecaster._create_features(df)
        
        # Original rows = 100, shifts max shift is 6 (window_size=6 + shift=1)
        # So we should drop around 7 rows
        assert len(X) <= 95
        assert len(y) == len(X)
        assert "value_lag_1" in X.columns
        assert "value_roll_mean_6" in X.columns

    def test_massive_training_pipeline(self, forecaster):
        data = generate_mock_sensor_data(500)
        metrics = forecaster.train(data, device_id="test_sensor_001")
        
        assert metrics["device_id"] == "test_sensor_001"
        assert "best_model" in metrics
        assert metrics["rmse"] > 0
        assert forecaster._is_trained
        assert "test_sensor_001" in forecaster.models

    def test_multi_step_prediction(self, forecaster):
        data = generate_mock_sensor_data(500)
        forecaster.train(data, device_id="test_sensor_001")
        
        # Predict 10 steps ahead using last 50 points
        recent = data[-50:]
        preds = forecaster.predict(recent, device_id="test_sensor_001", steps=10)
        
        assert len(preds) == 10
        assert "predicted_value" in preds[0]
        assert "timestamp" in preds[0]
        assert preds[0]["step"] == 1
        assert preds[9]["step"] == 10

    def test_feature_importances(self, forecaster):
        data = generate_mock_sensor_data(300)
        forecaster.train(data, device_id="test_sensor_001")
        importances = forecaster.get_feature_importances("test_sensor_001")
        
        # Some models might not have importances, but we should get a dict
        assert isinstance(importances, dict)


class TestAnomalyClustering:

    @pytest.fixture
    def cluster_engine(self):
        return AnomalyClusterEngine(contamination=0.05)

    def test_isolation_forest_training(self, cluster_engine):
        # 1000 normal points
        data = generate_mock_sensor_data(1000)
        metrics = cluster_engine.train_isolation_forest(data, device_id="test_sensor_001")
        
        assert metrics["device_id"] == "test_sensor_001"
        assert metrics["model"] == "IsolationForest"
        assert f"test_sensor_001_iso" in cluster_engine.models

    def test_anomaly_detection(self, cluster_engine):
        data = generate_mock_sensor_data(1000)
        cluster_engine.train_isolation_forest(data, device_id="test_sensor_001")
        
        # Create a new dataset with an obvious anomaly
        recent = generate_mock_sensor_data(100)
        recent[50]["value"] += 1000.0  # Massive spike
        
        results = cluster_engine.detect_anomalies(recent, device_id="test_sensor_001")
        
        assert len(results) == 100
        assert "is_anomaly" in results[0]
        assert "anomaly_score" in results[0]
        
        # The 50th point should be flagged as an anomaly
        assert results[50]["is_anomaly"] is True


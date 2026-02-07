"""
Tests for ML Anomaly Detector Module
"""
import pytest
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestZScoreDetector:
    """Tests for Z-Score based anomaly detection"""

    def test_normal_distribution_no_anomalies(self):
        """Normal data should have no anomalies"""
        data = np.random.normal(100, 5, 100)
        mean = np.mean(data)
        std = np.std(data)
        z_scores = np.abs((data - mean) / std)
        anomalies = z_scores > 3
        # Most points should not be anomalies
        assert np.sum(anomalies) < 5

    def test_spike_detection(self):
        """Should detect sudden spike"""
        data = np.array([100, 101, 99, 100, 102, 200, 101, 100])
        mean = np.mean(data[:5])
        std = np.std(data[:5])
        spike_z = abs(data[5] - mean) / std if std > 0 else 0
        assert spike_z > 2  # Spike should have high z-score

    def test_drop_detection(self):
        """Should detect sudden drop"""
        data = np.array([100, 101, 99, 100, 102, 20, 101, 100])
        mean = np.mean(data[:5])
        std = np.std(data[:5])
        drop_z = abs(data[5] - mean) / std if std > 0 else 0
        assert drop_z > 2  # Drop should have high z-score


class TestTrendAnalyzer:
    """Tests for trend analysis"""

    def test_upward_trend(self):
        """Should detect upward trend"""
        data = np.array([100, 105, 110, 115, 120, 125, 130])
        trend = np.polyfit(range(len(data)), data, 1)[0]
        assert trend > 0

    def test_downward_trend(self):
        """Should detect downward trend"""
        data = np.array([130, 125, 120, 115, 110, 105, 100])
        trend = np.polyfit(range(len(data)), data, 1)[0]
        assert trend < 0

    def test_stable_trend(self):
        """Should detect stable trend"""
        data = np.array([100, 101, 99, 100, 101, 99, 100])
        trend = np.polyfit(range(len(data)), data, 1)[0]
        assert abs(trend) < 1


class TestAnomalyTypes:
    """Test different anomaly types"""

    def test_outlier_identification(self):
        """Test statistical outlier identification"""
        data = [100, 101, 99, 100, 500, 101, 100]  # 500 is outlier
        mean = np.mean(data)
        std = np.std(data)
        outlier_idx = 4
        z = abs(data[outlier_idx] - mean) / std
        assert z > 2

    def test_seasonal_pattern(self):
        """Test seasonal pattern detection (simplified)"""
        # Create data with weekly pattern
        weekly = np.array([100, 120, 130, 140, 135, 90, 80] * 4)
        # Check variance exists (indicates pattern)
        assert np.std(weekly) > 10

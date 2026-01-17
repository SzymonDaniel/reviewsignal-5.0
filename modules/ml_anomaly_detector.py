#!/usr/bin/env python3
"""
ML ANOMALY DETECTOR - Review Pattern Analysis
System 5.0.3 - Detects anomalies in review trends for investment signals

Author: ReviewSignal Team
Version: 5.0.3
Date: January 2026
"""

import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime
import structlog

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════

class AnomalyType(Enum):
    """Types of detected anomalies"""
    SPIKE = "spike"           # Sudden increase
    DROP = "drop"             # Sudden decrease
    TREND_CHANGE = "trend_change"  # Reversal in trend
    OUTLIER = "outlier"       # Statistical outlier


class Severity(Enum):
    """Anomaly severity levels"""
    LOW = "low"           # Z-score 2-2.5
    MEDIUM = "medium"     # Z-score 2.5-3
    HIGH = "high"         # Z-score 3-4
    CRITICAL = "critical" # Z-score > 4


# ═══════════════════════════════════════════════════════════════════
# DATACLASSES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AnomalyResult:
    """Individual anomaly detection result"""
    index: int
    value: float
    anomaly_type: AnomalyType
    severity: Severity
    deviation_from_mean: float
    z_score: float
    isolation_score: float
    detected_at: str
    context: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['anomaly_type'] = self.anomaly_type.value
        data['severity'] = self.severity.value
        return data


@dataclass
class AnalysisResult:
    """Complete analysis result for a chain/location"""
    chain_name: str
    total_points: int
    anomalies_found: int
    anomaly_rate: float
    mean_value: float
    std_value: float
    trend_direction: str
    anomalies: List[AnomalyResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['anomalies'] = [a.to_dict() for a in self.anomalies]
        return data


@dataclass
class AlertConfig:
    """Configuration for anomaly alerts"""
    threshold_z_score: float = 2.5
    threshold_isolation: float = -0.5
    min_severity: Severity = Severity.MEDIUM
    notify_email: str = ""
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['min_severity'] = self.min_severity.value
        return data


# ═══════════════════════════════════════════════════════════════════
# HELPER CLASSES - DETECTORS
# ═══════════════════════════════════════════════════════════════════

class ZScoreDetector:
    """Z-Score based anomaly detector"""
    
    def __init__(self, threshold: float = 2.5):
        """
        Initialize Z-Score detector.
        
        Args:
            threshold: Z-score threshold for anomaly detection (default: 2.5)
        """
        self.threshold = threshold
    
    def detect(self, data: np.ndarray) -> List[int]:
        """
        Detect anomalies using Z-score method.
        
        Args:
            data: 1D numpy array of values
        
        Returns:
            List of indices where anomalies were detected
        """
        z_scores = self.calculate_z_scores(data)
        anomaly_indices = np.where(np.abs(z_scores) > self.threshold)[0]
        return anomaly_indices.tolist()
    
    def calculate_z_scores(self, data: np.ndarray) -> np.ndarray:
        """
        Calculate Z-scores for data.
        
        Args:
            data: 1D numpy array
        
        Returns:
            Array of Z-scores
        """
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return np.zeros_like(data)
        
        return (data - mean) / std


class IsolationForestDetector:
    """Isolation Forest based anomaly detector"""
    
    def __init__(self, contamination: float = 0.1, n_estimators: int = 100):
        """
        Initialize Isolation Forest detector.
        
        Args:
            contamination: Expected proportion of outliers (default: 10%)
            n_estimators: Number of trees in the forest (default: 100)
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.model: Optional[IsolationForest] = None
        self.scaler = StandardScaler()
    
    def fit(self, data: np.ndarray) -> None:
        """
        Fit the Isolation Forest model.
        
        Args:
            data: Training data (can be 1D or 2D)
        """
        # Reshape if 1D
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
        
        # Scale data
        data_scaled = self.scaler.fit_transform(data)
        
        # Fit model
        self.model = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=42
        )
        self.model.fit(data_scaled)
    
    def detect(self, data: np.ndarray) -> List[int]:
        """
        Detect anomalies using fitted Isolation Forest.
        
        Args:
            data: Data to analyze
        
        Returns:
            List of anomaly indices
        """
        if self.model is None:
            self.fit(data)
        
        # Reshape if 1D
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
        
        # Scale and predict
        data_scaled = self.scaler.transform(data)
        predictions = self.model.predict(data_scaled)
        
        # -1 indicates anomaly
        anomaly_indices = np.where(predictions == -1)[0]
        return anomaly_indices.tolist()
    
    def get_scores(self, data: np.ndarray) -> np.ndarray:
        """
        Get anomaly scores for data.
        
        Args:
            data: Data to score
        
        Returns:
            Array of anomaly scores (lower = more anomalous)
        """
        if self.model is None:
            self.fit(data)
        
        if len(data.shape) == 1:
            data = data.reshape(-1, 1)
        
        data_scaled = self.scaler.transform(data)
        return self.model.decision_function(data_scaled)


class TrendAnalyzer:
    """Analyze trends in time series data"""
    
    @staticmethod
    def detect_trend(data: np.ndarray) -> str:
        """
        Detect overall trend direction.
        
        Args:
            data: 1D numpy array (time series)
        
        Returns:
            'up', 'down', or 'stable'
        """
        if len(data) < 3:
            return "stable"
        
        # Linear regression
        x = np.arange(len(data))
        slope, _, r_value, p_value, _ = stats.linregress(x, data)
        
        # Check significance
        if p_value > 0.05:
            return "stable"
        
        # Determine direction based on slope
        threshold = np.std(data) * 0.1
        
        if slope > threshold:
            return "up"
        elif slope < -threshold:
            return "down"
        else:
            return "stable"
    
    @staticmethod
    def calculate_momentum(data: np.ndarray, window: int = 5) -> float:
        """
        Calculate momentum (rate of change).
        
        Args:
            data: 1D numpy array
            window: Lookback window (default: 5)
        
        Returns:
            Momentum value (positive = increasing, negative = decreasing)
        """
        if len(data) < window:
            return 0.0
        
        recent = np.mean(data[-window:])
        previous = np.mean(data[-2*window:-window]) if len(data) >= 2*window else np.mean(data[:-window])
        
        if previous == 0:
            return 0.0
        
        return (recent - previous) / abs(previous) * 100
    
    @staticmethod
    def detect_trend_change(data: np.ndarray, window: int = 5) -> Optional[int]:
        """
        Detect point where trend changes direction.
        
        Args:
            data: 1D numpy array
            window: Window for trend calculation
        
        Returns:
            Index of trend change point, or None
        """
        if len(data) < 2 * window:
            return None
        
        # Calculate rolling slopes
        slopes = []
        for i in range(len(data) - window):
            segment = data[i:i + window]
            x = np.arange(window)
            slope, _, _, _, _ = stats.linregress(x, segment)
            slopes.append(slope)
        
        slopes = np.array(slopes)
        
        # Find sign changes
        sign_changes = np.where(np.diff(np.sign(slopes)) != 0)[0]
        
        if len(sign_changes) > 0:
            # Return most recent significant change
            return int(sign_changes[-1] + window // 2)
        
        return None


# ═══════════════════════════════════════════════════════════════════
# MAIN CLASS
# ═══════════════════════════════════════════════════════════════════

class MLAnomalyDetector:
    """
    Machine Learning based Anomaly Detector.
    Combines multiple detection methods for robust anomaly detection.
    """
    
    def __init__(
        self,
        z_threshold: float = 2.5,
        isolation_contamination: float = 0.1
    ):
        """
        Initialize ML Anomaly Detector.
        
        Args:
            z_threshold: Z-score threshold (default: 2.5)
            isolation_contamination: Isolation Forest contamination (default: 10%)
        """
        self.z_detector = ZScoreDetector(threshold=z_threshold)
        self.iso_detector = IsolationForestDetector(contamination=isolation_contamination)
        self.trend_analyzer = TrendAnalyzer()
        
        logger.info(
            "anomaly_detector_initialized",
            z_threshold=z_threshold,
            iso_contamination=isolation_contamination
        )
    
    # ───────────────────────────────────────────────────────────────
    # PUBLIC METHODS
    # ───────────────────────────────────────────────────────────────
    
    def analyze(
        self,
        data: List[float],
        chain_name: str = "Unknown"
    ) -> AnalysisResult:
        """
        Perform complete anomaly analysis on data.
        
        Args:
            data: List of values (ratings, review counts, etc.)
            chain_name: Name of the chain being analyzed
        
        Returns:
            AnalysisResult with all detected anomalies
        """
        data_array = np.array(data, dtype=float)
        
        if len(data_array) < 5:
            logger.warning("insufficient_data", chain=chain_name, points=len(data_array))
            return AnalysisResult(
                chain_name=chain_name,
                total_points=len(data_array),
                anomalies_found=0,
                anomaly_rate=0.0,
                mean_value=float(np.mean(data_array)) if len(data_array) > 0 else 0.0,
                std_value=float(np.std(data_array)) if len(data_array) > 0 else 0.0,
                trend_direction="stable",
                anomalies=[]
            )
        
        # Detect anomalies
        anomalies = self.detect_anomalies(data_array)
        
        # Analyze trend
        trend_direction = self.trend_analyzer.detect_trend(data_array)
        
        result = AnalysisResult(
            chain_name=chain_name,
            total_points=len(data_array),
            anomalies_found=len(anomalies),
            anomaly_rate=len(anomalies) / len(data_array) * 100,
            mean_value=float(np.mean(data_array)),
            std_value=float(np.std(data_array)),
            trend_direction=trend_direction,
            anomalies=anomalies
        )
        
        logger.info(
            "analysis_complete",
            chain=chain_name,
            points=len(data_array),
            anomalies=len(anomalies),
            trend=trend_direction
        )
        
        return result
    
    def detect_anomalies(self, data: np.ndarray) -> List[AnomalyResult]:
        """
        Detect anomalies using combined methods.
        
        Args:
            data: 1D numpy array of values
        
        Returns:
            List of AnomalyResult objects
        """
        # Get detections from both methods
        z_anomalies = set(self.z_detector.detect(data))
        iso_anomalies = set(self.iso_detector.detect(data))
        
        # Combine (union of both methods)
        combined = self._combine_detectors(z_anomalies, iso_anomalies)
        
        # Calculate scores
        z_scores = self.z_detector.calculate_z_scores(data)
        iso_scores = self.iso_detector.get_scores(data)
        
        mean_val = np.mean(data)
        
        anomalies = []
        for idx in combined:
            # Classify anomaly type
            anomaly_type = self._classify_anomaly_type(idx, data)
            
            # Calculate severity
            severity = self._calculate_severity(
                abs(data[idx] - mean_val),
                abs(z_scores[idx])
            )
            
            anomaly = AnomalyResult(
                index=idx,
                value=float(data[idx]),
                anomaly_type=anomaly_type,
                severity=severity,
                deviation_from_mean=float(data[idx] - mean_val),
                z_score=float(z_scores[idx]),
                isolation_score=float(iso_scores[idx]),
                detected_at=datetime.utcnow().isoformat(),
                context={
                    "mean": float(mean_val),
                    "std": float(np.std(data)),
                    "in_z_detector": idx in z_anomalies,
                    "in_iso_detector": idx in iso_anomalies
                }
            )
            anomalies.append(anomaly)
        
        return sorted(anomalies, key=lambda x: abs(x.z_score), reverse=True)
    
    def analyze_reviews_trend(
        self,
        reviews_data: List[Dict]
    ) -> AnalysisResult:
        """
        Analyze trends in review count data.
        
        Args:
            reviews_data: List of dicts with 'date' and 'count' keys
        
        Returns:
            AnalysisResult
        """
        if not reviews_data:
            return AnalysisResult(
                chain_name="Reviews",
                total_points=0,
                anomalies_found=0,
                anomaly_rate=0.0,
                mean_value=0.0,
                std_value=0.0,
                trend_direction="stable",
                anomalies=[]
            )
        
        counts = [r.get('count', 0) for r in reviews_data]
        return self.analyze(counts, chain_name="Review Counts")
    
    def analyze_ratings_trend(
        self,
        ratings_data: List[Dict]
    ) -> AnalysisResult:
        """
        Analyze trends in rating data.
        
        Args:
            ratings_data: List of dicts with 'date' and 'rating' keys
        
        Returns:
            AnalysisResult
        """
        if not ratings_data:
            return AnalysisResult(
                chain_name="Ratings",
                total_points=0,
                anomalies_found=0,
                anomaly_rate=0.0,
                mean_value=0.0,
                std_value=0.0,
                trend_direction="stable",
                anomalies=[]
            )
        
        ratings = [r.get('rating', 0) for r in ratings_data]
        return self.analyze(ratings, chain_name="Ratings")
    
    def generate_alerts(
        self,
        result: AnalysisResult,
        config: AlertConfig
    ) -> List[Dict]:
        """
        Generate alerts based on analysis results.
        
        Args:
            result: AnalysisResult from analysis
            config: AlertConfig with thresholds
        
        Returns:
            List of alert dicts
        """
        alerts = []
        
        severity_order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        min_severity_idx = severity_order.index(config.min_severity)
        
        for anomaly in result.anomalies:
            # Check if meets minimum severity
            anomaly_severity_idx = severity_order.index(anomaly.severity)
            if anomaly_severity_idx < min_severity_idx:
                continue
            
            # Check z-score threshold
            if abs(anomaly.z_score) < config.threshold_z_score:
                continue
            
            alert = {
                "type": "anomaly_alert",
                "chain": result.chain_name,
                "severity": anomaly.severity.value,
                "anomaly_type": anomaly.anomaly_type.value,
                "value": anomaly.value,
                "z_score": round(anomaly.z_score, 2),
                "deviation": round(anomaly.deviation_from_mean, 2),
                "index": anomaly.index,
                "message": self._generate_alert_message(result.chain_name, anomaly),
                "timestamp": datetime.utcnow().isoformat(),
                "action_required": anomaly.severity in [Severity.HIGH, Severity.CRITICAL]
            }
            alerts.append(alert)
        
        # Add trend alert if significant
        if result.trend_direction != "stable" and result.anomaly_rate > 5:
            alerts.append({
                "type": "trend_alert",
                "chain": result.chain_name,
                "severity": "medium",
                "trend": result.trend_direction,
                "anomaly_rate": round(result.anomaly_rate, 2),
                "message": f"{result.chain_name}: {result.trend_direction}ward trend with {result.anomaly_rate:.1f}% anomaly rate",
                "timestamp": datetime.utcnow().isoformat(),
                "action_required": result.anomaly_rate > 10
            })
        
        logger.info(
            "alerts_generated",
            chain=result.chain_name,
            alert_count=len(alerts)
        )
        
        return alerts
    
    # ───────────────────────────────────────────────────────────────
    # PRIVATE METHODS
    # ───────────────────────────────────────────────────────────────
    
    def _combine_detectors(
        self,
        z_anomalies: set,
        iso_anomalies: set
    ) -> List[int]:
        """
        Combine results from multiple detectors.
        
        Uses intersection for higher confidence or union for sensitivity.
        """
        # Use union (any detector flags it)
        combined = z_anomalies | iso_anomalies
        return sorted(list(combined))
    
    def _classify_anomaly_type(
        self,
        index: int,
        data: np.ndarray
    ) -> AnomalyType:
        """
        Classify the type of anomaly based on context.
        """
        mean_val = np.mean(data)
        value = data[index]
        
        # Check if spike or drop
        if value > mean_val:
            # Check if sudden spike
            if index > 0 and data[index] > data[index-1] * 1.5:
                return AnomalyType.SPIKE
        else:
            # Check if sudden drop
            if index > 0 and data[index] < data[index-1] * 0.5:
                return AnomalyType.DROP
        
        # Check for trend change
        if index > 2 and index < len(data) - 2:
            before = np.mean(data[index-2:index])
            after = np.mean(data[index:index+2])
            if (before > mean_val and after < mean_val) or \
               (before < mean_val and after > mean_val):
                return AnomalyType.TREND_CHANGE
        
        return AnomalyType.OUTLIER
    
    def _calculate_severity(
        self,
        deviation: float,
        z_score: float
    ) -> Severity:
        """
        Calculate severity based on z-score.
        """
        abs_z = abs(z_score)
        
        if abs_z > 4:
            return Severity.CRITICAL
        elif abs_z > 3:
            return Severity.HIGH
        elif abs_z > 2.5:
            return Severity.MEDIUM
        else:
            return Severity.LOW
    
    def _generate_alert_message(
        self,
        chain_name: str,
        anomaly: AnomalyResult
    ) -> str:
        """
        Generate human-readable alert message.
        """
        direction = "above" if anomaly.deviation_from_mean > 0 else "below"
        
        if anomaly.anomaly_type == AnomalyType.SPIKE:
            return f"📈 {chain_name}: Sudden SPIKE detected! Value {anomaly.value:.2f} is {abs(anomaly.deviation_from_mean):.2f} {direction} mean (Z: {anomaly.z_score:.2f})"
        elif anomaly.anomaly_type == AnomalyType.DROP:
            return f"📉 {chain_name}: Sudden DROP detected! Value {anomaly.value:.2f} is {abs(anomaly.deviation_from_mean):.2f} {direction} mean (Z: {anomaly.z_score:.2f})"
        elif anomaly.anomaly_type == AnomalyType.TREND_CHANGE:
            return f"↩️ {chain_name}: TREND CHANGE detected at index {anomaly.index}! Value: {anomaly.value:.2f} (Z: {anomaly.z_score:.2f})"
        else:
            return f"⚠️ {chain_name}: OUTLIER detected! Value {anomaly.value:.2f} is {abs(anomaly.deviation_from_mean):.2f} {direction} mean (Z: {anomaly.z_score:.2f})"


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧠 ML ANOMALY DETECTOR - TEST RUN")
    print("="*60)
    
    # Create sample data with anomalies
    np.random.seed(42)
    
    # Normal data
    normal_data = np.random.normal(4.0, 0.3, 50)
    
    # Inject anomalies
    normal_data[10] = 5.2  # Spike
    normal_data[25] = 2.8  # Drop
    normal_data[40] = 5.5  # Spike
    
    # Initialize detector
    detector = MLAnomalyDetector(
        z_threshold=2.5,
        isolation_contamination=0.1
    )
    
    # Run analysis
    result = detector.analyze(
        data=normal_data.tolist(),
        chain_name="McDonald's NYC"
    )
    
    print(f"\n📊 Analysis Results for: {result.chain_name}")
    print(f"   Total points:    {result.total_points}")
    print(f"   Mean value:      {result.mean_value:.2f}")
    print(f"   Std deviation:   {result.std_value:.2f}")
    print(f"   Trend:           {result.trend_direction}")
    print(f"   Anomalies found: {result.anomalies_found}")
    print(f"   Anomaly rate:    {result.anomaly_rate:.1f}%")
    
    print(f"\n🚨 Detected Anomalies:")
    for a in result.anomalies:
        print(f"   [{a.index}] {a.anomaly_type.value.upper()}: "
              f"value={a.value:.2f}, z={a.z_score:.2f}, "
              f"severity={a.severity.value}")
    
    # Generate alerts
    config = AlertConfig(
        threshold_z_score=2.0,
        min_severity=Severity.MEDIUM
    )
    
    alerts = detector.generate_alerts(result, config)
    
    print(f"\n🔔 Alerts Generated: {len(alerts)}")
    for alert in alerts:
        print(f"   • {alert['message']}")
    
    print("\n" + "="*60)
    print("✅ ML Anomaly Detector test complete!")
    print("="*60)

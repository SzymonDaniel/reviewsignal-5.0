export interface DashboardStats {
  totalLocations: number;
  locationsChange: number;
  reviewsToday: number;
  reviewsChange: number;
  avgSentiment: number;
  sentimentChange: number;
  activeAlerts: number;
  alertsChange: number;
  apiCallsToday: number;
  apiCallsChange: number;
  mrr: number;
  mrrChange: number;
}

export interface ChainData {
  id: string;
  name: string;
  avgRating: number;
  reviewCount: number;
}

export interface AnomalyAlert {
  id: string;
  severity: string;
  message: string;
}

export interface TimeSeriesData {
  date: string;
  avgRating: number;
  reviewCount: number;
}

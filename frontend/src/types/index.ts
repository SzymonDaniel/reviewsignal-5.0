/**
 * ReviewSignal 7.0 - TypeScript Type Definitions
 * Comprehensive types for the entire dashboard
 */

// ============================================================================
// DASHBOARD TYPES
// ============================================================================

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
  logo?: string;
  category: string;
  locationCount: number;
  reviewCount: number;
  avgRating: number;
  ratingChange: number;
  sentiment: 'positive' | 'neutral' | 'negative';
  topLocations: LocationData[];
  alerts: number;
  lastUpdated: string;
}

export interface LocationData {
  id: string;
  placeId: string;
  name: string;
  address: string;
  city: string;
  country: string;
  latitude: number;
  longitude: number;
  rating: number;
  reviewCount: number;
  priceLevel?: number;
  isOpen?: boolean;
  chain: string;
}

export interface ReviewData {
  id: string;
  locationId: string;
  author: string;
  authorAvatar?: string;
  rating: number;
  text: string;
  language: string;
  sentiment: number;
  publishedAt: string;
  scrapedAt: string;
  keywords: string[];
}

export interface AnomalyAlert {
  id: string;
  type: 'rating_drop' | 'review_spike' | 'sentiment_shift' | 'competitor_move';
  severity: 'low' | 'medium' | 'high' | 'critical';
  chainId: string;
  chainName: string;
  locationId?: string;
  locationName?: string;
  title: string;
  description: string;
  value: number;
  expectedValue: number;
  deviation: number;
  detectedAt: string;
  acknowledged: boolean;
  acknowledgedBy?: string;
  acknowledgedAt?: string;
}

export interface TimeSeriesData {
  date: string;
  avgRating: number;
  reviewCount: number;
  sentimentScore: number;
  anomalyScore?: number;
}

// ============================================================================
// API TYPES
// ============================================================================

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  permissions: string[];
  rateLimit: number;
  lastUsedAt?: string;
  expiresAt?: string;
  createdAt: string;
}

export interface Webhook {
  id: string;
  url: string;
  events: string[];
  secret: string;
  isActive: boolean;
  lastTriggeredAt?: string;
  failureCount: number;
  createdAt: string;
}

// ============================================================================
// REPORT TYPES
// ============================================================================

export interface Report {
  id: string;
  name: string;
  type: 'chain_analysis' | 'market_overview' | 'competitor_benchmark' | 'custom';
  format: 'pdf' | 'xlsx' | 'csv' | 'json';
  status: 'pending' | 'generating' | 'completed' | 'failed';
  filters: ReportFilters;
  downloadUrl?: string;
  createdAt: string;
  completedAt?: string;
}

export interface ReportFilters {
  chains?: string[];
  cities?: string[];
  countries?: string[];
  dateFrom: string;
  dateTo: string;
  minRating?: number;
  maxRating?: number;
}

// ============================================================================
// SETTINGS TYPES
// ============================================================================

export interface NotificationSettings {
  email: {
    dailyDigest: boolean;
    weeklyReport: boolean;
    anomalyAlerts: boolean;
    systemUpdates: boolean;
  };
  slack?: {
    webhookUrl: string;
    channels: string[];
    alertSeverity: 'all' | 'high' | 'critical';
  };
  webhook?: {
    url: string;
    events: string[];
  };
}

export interface TeamMember {
  id: string;
  userId: string;
  email: string;
  name: string;
  role: 'viewer' | 'analyst' | 'manager' | 'admin';
  invitedAt: string;
  acceptedAt?: string;
  status: 'pending' | 'active' | 'deactivated';
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

export interface DateRange {
  from: Date | undefined;
  to: Date | undefined;
}

export interface SortConfig {
  key: string;
  direction: 'asc' | 'desc';
}

export interface FilterConfig {
  search?: string;
  chains?: string[];
  cities?: string[];
  countries?: string[];
  rating?: [number, number];
  sentiment?: ('positive' | 'neutral' | 'negative')[];
}

export interface PaginationConfig {
  page: number;
  limit: number;
  total: number;
  hasMore: boolean;
}

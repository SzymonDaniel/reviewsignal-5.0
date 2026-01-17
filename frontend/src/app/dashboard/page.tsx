/**
 * ReviewSignal 7.0 - Main Dashboard
 * Real-time analytics dashboard with KPIs, charts, and alerts
 * 
 * @author Claude AI for Simon
 * @version 7.0.0
 */

'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  Users,
  DollarSign,
  MapPin,
  Star,
  AlertTriangle,
  Activity,
  Globe,
  Zap,
  RefreshCw,
  Download,
  Filter,
  Calendar,
  ChevronRight,
  BarChart3,
  PieChart,
  LineChart,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, subDays, startOfDay, endOfDay } from 'date-fns';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart as RechartsPie,
  Pie,
  Cell,
  Legend,
  LineChart as RechartsLine,
  Line,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { DateRangePicker } from '@/components/ui/date-range-picker';
import { DashboardLayout } from '@/components/layouts/dashboard-layout';
import { KPICard } from '@/components/dashboard/kpi-card';
import { ChainTable } from '@/components/dashboard/chain-table';
import { AnomalyAlerts } from '@/components/dashboard/anomaly-alerts';
import { GlobalMap } from '@/components/dashboard/global-map';
import { RealtimeFeed } from '@/components/dashboard/realtime-feed';
import { useAuthStore } from '@/stores/auth-store';
import { useDashboardStore } from '@/stores/dashboard-store';
import { api } from '@/lib/api';
import { cn, formatCurrency, formatNumber, formatPercentage } from '@/lib/utils';
import type { DashboardStats, ChainData, AnomalyAlert, TimeSeriesData } from '@/types';

// ============================================================================
// CONSTANTS
// ============================================================================

const CHART_COLORS = {
  primary: '#3b82f6',
  secondary: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  purple: '#8b5cf6',
  pink: '#ec4899',
  gradient: ['#3b82f6', '#8b5cf6', '#ec4899'],
};

const REFRESH_INTERVALS = {
  stats: 30000,      // 30 seconds
  alerts: 15000,     // 15 seconds
  realtime: 5000,    // 5 seconds
  charts: 60000,     // 1 minute
};

// ============================================================================
// DASHBOARD PAGE COMPONENT
// ============================================================================

export default function DashboardPage() {
  const { user, subscription } = useAuthStore();
  const { dateRange, setDateRange, selectedChains, toggleChain } = useDashboardStore();
  const queryClient = useQueryClient();
  
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  // ==========================================================================
  // DATA FETCHING
  // ==========================================================================

  const {
    data: stats,
    isLoading: statsLoading,
    refetch: refetchStats,
  } = useQuery<DashboardStats>({
    queryKey: ['dashboard-stats', dateRange],
    queryFn: () => api.get('/api/v1/dashboard/stats', {
      params: {
        start_date: dateRange.from?.toISOString(),
        end_date: dateRange.to?.toISOString(),
      },
    }),
    refetchInterval: REFRESH_INTERVALS.stats,
    staleTime: 10000,
  });

  const {
    data: chainData,
    isLoading: chainsLoading,
  } = useQuery<ChainData[]>({
    queryKey: ['chain-performance', dateRange],
    queryFn: () => api.get('/api/v1/chains/performance', {
      params: {
        start_date: dateRange.from?.toISOString(),
        end_date: dateRange.to?.toISOString(),
        limit: 20,
      },
    }),
    refetchInterval: REFRESH_INTERVALS.charts,
  });

  const {
    data: anomalies,
    isLoading: anomaliesLoading,
  } = useQuery<AnomalyAlert[]>({
    queryKey: ['anomaly-alerts'],
    queryFn: () => api.get('/api/v1/alerts/anomalies', {
      params: { limit: 10, severity: 'all' },
    }),
    refetchInterval: REFRESH_INTERVALS.alerts,
  });

  const {
    data: timeSeriesData,
    isLoading: timeSeriesLoading,
  } = useQuery<TimeSeriesData[]>({
    queryKey: ['time-series', dateRange, selectedChains],
    queryFn: () => api.get('/api/v1/analytics/time-series', {
      params: {
        start_date: dateRange.from?.toISOString(),
        end_date: dateRange.to?.toISOString(),
        chains: selectedChains.join(','),
        granularity: 'day',
      },
    }),
    refetchInterval: REFRESH_INTERVALS.charts,
  });

  // ==========================================================================
  // HANDLERS
  // ==========================================================================

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] }),
      queryClient.invalidateQueries({ queryKey: ['chain-performance'] }),
      queryClient.invalidateQueries({ queryKey: ['anomaly-alerts'] }),
      queryClient.invalidateQueries({ queryKey: ['time-series'] }),
    ]);
    setTimeout(() => setIsRefreshing(false), 1000);
  }, [queryClient]);

  const handleExport = useCallback(async (format: 'csv' | 'json' | 'pdf') => {
    const response = await api.get('/api/v1/reports/export', {
      params: {
        format,
        start_date: dateRange.from?.toISOString(),
        end_date: dateRange.to?.toISOString(),
      },
      responseType: 'blob',
    });
    
    const url = window.URL.createObjectURL(new Blob([response]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `reviewsignal-report-${format}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  }, [dateRange]);

  // ==========================================================================
  // COMPUTED VALUES
  // ==========================================================================

  const kpiCards = useMemo(() => {
    if (!stats) return [];
    
    return [
      {
        title: 'Total Locations',
        value: formatNumber(stats.totalLocations),
        change: stats.locationsChange,
        trend: stats.locationsChange >= 0 ? 'up' : 'down',
        icon: MapPin,
        color: 'blue',
        description: 'Monitored worldwide',
      },
      {
        title: 'Reviews Today',
        value: formatNumber(stats.reviewsToday),
        change: stats.reviewsChange,
        trend: stats.reviewsChange >= 0 ? 'up' : 'down',
        icon: Star,
        color: 'yellow',
        description: 'New reviews collected',
      },
      {
        title: 'Avg Sentiment',
        value: stats.avgSentiment.toFixed(2),
        change: stats.sentimentChange,
        trend: stats.sentimentChange >= 0 ? 'up' : 'down',
        icon: Activity,
        color: stats.avgSentiment >= 4.0 ? 'green' : stats.avgSentiment >= 3.0 ? 'yellow' : 'red',
        description: 'Across all chains',
      },
      {
        title: 'Active Alerts',
        value: formatNumber(stats.activeAlerts),
        change: stats.alertsChange,
        trend: stats.alertsChange <= 0 ? 'up' : 'down',
        icon: AlertTriangle,
        color: stats.activeAlerts > 5 ? 'red' : 'green',
        description: 'Anomalies detected',
      },
      {
        title: 'API Calls',
        value: formatNumber(stats.apiCallsToday),
        change: stats.apiCallsChange,
        trend: 'neutral',
        icon: Zap,
        color: 'purple',
        description: `of ${formatNumber(subscription?.apiLimit || 0)} limit`,
      },
      {
        title: 'MRR',
        value: formatCurrency(stats.mrr, 'EUR'),
        change: stats.mrrChange,
        trend: stats.mrrChange >= 0 ? 'up' : 'down',
        icon: DollarSign,
        color: 'green',
        description: 'Monthly recurring revenue',
      },
    ];
  }, [stats, subscription]);

  const sentimentDistribution = useMemo(() => {
    if (!chainData) return [];
    
    const distribution = {
      excellent: 0,  // 4.5+
      good: 0,       // 4.0-4.5
      average: 0,    // 3.0-4.0
      poor: 0,       // <3.0
    };
    
    chainData.forEach(chain => {
      if (chain.avgRating >= 4.5) distribution.excellent++;
      else if (chain.avgRating >= 4.0) distribution.good++;
      else if (chain.avgRating >= 3.0) distribution.average++;
      else distribution.poor++;
    });
    
    return [
      { name: 'Excellent (4.5+)', value: distribution.excellent, color: '#10b981' },
      { name: 'Good (4.0-4.5)', value: distribution.good, color: '#3b82f6' },
      { name: 'Average (3.0-4.0)', value: distribution.average, color: '#f59e0b' },
      { name: 'Poor (<3.0)', value: distribution.poor, color: '#ef4444' },
    ];
  }, [chainData]);

  // ==========================================================================
  // RENDER
  // ==========================================================================

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        {/* Header */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground">
              Welcome back, {user?.name}. Here's your intelligence overview.
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <DateRangePicker
              value={dateRange}
              onChange={setDateRange}
              presets={[
                { label: 'Today', value: { from: startOfDay(new Date()), to: endOfDay(new Date()) } },
                { label: 'Last 7 days', value: { from: subDays(new Date(), 7), to: new Date() } },
                { label: 'Last 30 days', value: { from: subDays(new Date(), 30), to: new Date() } },
                { label: 'Last 90 days', value: { from: subDays(new Date(), 90), to: new Date() } },
              ]}
            />
            
            <Button
              variant="outline"
              size="icon"
              onClick={handleRefresh}
              disabled={isRefreshing}
            >
              <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
            </Button>
            
            <Button variant="outline" onClick={() => handleExport('csv')}>
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {statsLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-6">
                    <Skeleton className="h-4 w-24 mb-2" />
                    <Skeleton className="h-8 w-16 mb-1" />
                    <Skeleton className="h-3 w-20" />
                  </CardContent>
                </Card>
              ))
            : kpiCards.map((kpi, index) => (
                <motion.div
                  key={kpi.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <KPICard {...kpi} />
                </motion.div>
              ))
          }
        </div>

        {/* Main Content Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid w-full max-w-md grid-cols-4">
            <TabsTrigger value="overview">
              <BarChart3 className="mr-2 h-4 w-4" />
              Overview
            </TabsTrigger>
            <TabsTrigger value="chains">
              <PieChart className="mr-2 h-4 w-4" />
              Chains
            </TabsTrigger>
            <TabsTrigger value="trends">
              <LineChart className="mr-2 h-4 w-4" />
              Trends
            </TabsTrigger>
            <TabsTrigger value="map">
              <Globe className="mr-2 h-4 w-4" />
              Map
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-7">
              {/* Sentiment Trend Chart */}
              <Card className="lg:col-span-4">
                <CardHeader>
                  <CardTitle>Sentiment Trend</CardTitle>
                  <CardDescription>Average rating over time across all chains</CardDescription>
                </CardHeader>
                <CardContent>
                  {timeSeriesLoading ? (
                    <Skeleton className="h-[300px] w-full" />
                  ) : (
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={timeSeriesData}>
                        <defs>
                          <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={CHART_COLORS.primary} stopOpacity={0.3} />
                            <stop offset="95%" stopColor={CHART_COLORS.primary} stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis
                          dataKey="date"
                          tickFormatter={(value) => format(new Date(value), 'MMM d')}
                          className="text-xs"
                        />
                        <YAxis domain={[3.5, 5]} className="text-xs" />
                        <Tooltip
                          content={({ active, payload, label }) => {
                            if (!active || !payload?.length) return null;
                            return (
                              <div className="rounded-lg border bg-background p-3 shadow-lg">
                                <p className="font-medium">{format(new Date(label), 'MMM d, yyyy')}</p>
                                <p className="text-sm text-muted-foreground">
                                  Avg Rating: <span className="font-semibold text-foreground">{payload[0].value?.toFixed(2)}</span>
                                </p>
                              </div>
                            );
                          }}
                        />
                        <Area
                          type="monotone"
                          dataKey="avgRating"
                          stroke={CHART_COLORS.primary}
                          fill="url(#sentimentGradient)"
                          strokeWidth={2}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>

              {/* Alerts Panel */}
              <Card className="lg:col-span-3">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Active Alerts</CardTitle>
                      <CardDescription>Anomalies requiring attention</CardDescription>
                    </div>
                    <Badge variant={anomalies?.length > 5 ? 'destructive' : 'secondary'}>
                      {anomalies?.length || 0} active
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <AnomalyAlerts
                    alerts={anomalies || []}
                    isLoading={anomaliesLoading}
                    maxItems={5}
                  />
                </CardContent>
              </Card>
            </div>

            {/* Second Row */}
            <div className="grid gap-4 lg:grid-cols-2">
              {/* Sentiment Distribution */}
              <Card>
                <CardHeader>
                  <CardTitle>Sentiment Distribution</CardTitle>
                  <CardDescription>Chains by rating category</CardDescription>
                </CardHeader>
                <CardContent>
                  <ResponsiveContainer width="100%" height={250}>
                    <RechartsPie>
                      <Pie
                        data={sentimentDistribution}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {sentimentDistribution.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </RechartsPie>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              {/* Real-time Feed */}
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle>Real-time Feed</CardTitle>
                      <CardDescription>Latest reviews and updates</CardDescription>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="relative flex h-2 w-2">
                        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                        <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
                      </span>
                      <span className="text-xs text-muted-foreground">Live</span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <RealtimeFeed maxItems={5} />
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Chains Tab */}
          <TabsContent value="chains">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Chain Performance</CardTitle>
                    <CardDescription>Detailed metrics for all monitored chains</CardDescription>
                  </div>
                  <Button variant="outline" size="sm">
                    <Filter className="mr-2 h-4 w-4" />
                    Filter
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <ChainTable
                  data={chainData || []}
                  isLoading={chainsLoading}
                  selectedChains={selectedChains}
                  onToggleChain={toggleChain}
                />
              </CardContent>
            </Card>
          </TabsContent>

          {/* Trends Tab */}
          <TabsContent value="trends">
            <Card>
              <CardHeader>
                <CardTitle>Historical Trends</CardTitle>
                <CardDescription>Long-term sentiment and review patterns</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={400}>
                  <RechartsLine data={timeSeriesData}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={(value) => format(new Date(value), 'MMM d')}
                    />
                    <YAxis yAxisId="left" />
                    <YAxis yAxisId="right" orientation="right" />
                    <Tooltip />
                    <Legend />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="avgRating"
                      name="Avg Rating"
                      stroke={CHART_COLORS.primary}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="reviewCount"
                      name="Review Count"
                      stroke={CHART_COLORS.secondary}
                      strokeWidth={2}
                      dot={false}
                    />
                  </RechartsLine>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Map Tab */}
          <TabsContent value="map">
            <Card>
              <CardHeader>
                <CardTitle>Global Coverage</CardTitle>
                <CardDescription>Interactive map of all monitored locations</CardDescription>
              </CardHeader>
              <CardContent className="h-[600px]">
                <GlobalMap />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}

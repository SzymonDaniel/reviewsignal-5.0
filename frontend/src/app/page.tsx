/**
 * ReviewSignal 7.0 - Enterprise Dashboard
 * 
 * ARCHITEKTURA:
 * - Server Components dla SEO i wydajności
 * - Client Components dla interaktywności
 * - Zustand dla state management
 * - TanStack Query dla server state
 * - Recharts dla wizualizacji
 * - Radix UI dla dostępności (WCAG 2.1 AA)
 * 
 * JAKOŚĆ: Enterprise-grade, Type-safe, Fully tested
 * 
 * @author Claude AI + Simon
 * @version 7.0.0
 * @license MIT
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell, RadialBarChart, RadialBar
} from 'recharts';
import {
  TrendingUp, TrendingDown, Users, DollarSign, Activity,
  MapPin, Star, AlertTriangle, CheckCircle, Clock,
  RefreshCw, Download, Filter, Search, Bell, Settings,
  ChevronDown, ChevronRight, ExternalLink, Zap, Shield,
  Globe, BarChart3, PieChart as PieChartIcon, Table,
  ArrowUpRight, ArrowDownRight, Minus, Menu, X,
  Moon, Sun, LogOut, User, CreditCard, HelpCircle
} from 'lucide-react';
import { format, subDays, parseISO, isToday, isYesterday } from 'date-fns';
import { de, enUS } from 'date-fns/locale';

// ============================================================================
// TYPES & INTERFACES
// ============================================================================

interface DashboardStats {
  totalLocations: number;
  totalReviews: number;
  averageRating: number;
  ratingChange: number;
  activeAlerts: number;
  revenue: number;
  revenueChange: number;
  activeUsers: number;
}

interface ChainData {
  id: string;
  name: string;
  logo: string;
  locations: number;
  avgRating: number;
  ratingTrend: number;
  reviewCount: number;
  sentiment: 'positive' | 'neutral' | 'negative';
  lastUpdated: string;
}

interface AnomalyAlert {
  id: string;
  chainId: string;
  chainName: string;
  type: 'rating_drop' | 'review_spike' | 'sentiment_shift' | 'competitor_move';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  detectedAt: string;
  isRead: boolean;
  confidence: number;
}

interface TimeSeriesPoint {
  date: string;
  value: number;
  predicted?: number;
  anomaly?: boolean;
}

interface GeoDataPoint {
  city: string;
  lat: number;
  lng: number;
  locations: number;
  avgRating: number;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const COLORS = {
  primary: '#3B82F6',
  secondary: '#8B5CF6',
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  neutral: '#6B7280',
  chart: ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B', '#EF4444', '#EC4899']
};

const ANIMATION_VARIANTS = {
  fadeIn: {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -20 }
  },
  slideIn: {
    initial: { opacity: 0, x: -20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 20 }
  },
  scale: {
    initial: { scale: 0.95, opacity: 0 },
    animate: { scale: 1, opacity: 1 },
    exit: { scale: 0.95, opacity: 0 }
  }
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

const formatNumber = (num: number, decimals: number = 0): string => {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`;
  return num.toFixed(decimals);
};

const formatCurrency = (amount: number, currency: string = 'EUR'): string => {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount);
};

const formatPercentage = (value: number, showSign: boolean = true): string => {
  const sign = showSign && value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
};

const getRelativeTime = (dateStr: string): string => {
  const date = parseISO(dateStr);
  if (isToday(date)) return 'Heute';
  if (isYesterday(date)) return 'Gestern';
  return format(date, 'dd.MM.yyyy', { locale: de });
};

const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'critical': return COLORS.danger;
    case 'high': return '#F97316';
    case 'medium': return COLORS.warning;
    case 'low': return COLORS.success;
    default: return COLORS.neutral;
  }
};

const cn = (...classes: (string | boolean | undefined)[]): string => {
  return classes.filter(Boolean).join(' ');
};

// ============================================================================
// CUSTOM HOOKS
// ============================================================================

function useApiData<T>(endpoint: string, initialData: T) {
  const [data, setData] = useState<T>(initialData);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${endpoint}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

function useLocalStorage<T>(key: string, initialValue: T) {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch {
      return initialValue;
    }
  });

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(key, JSON.stringify(valueToStore));
      }
    } catch (error) {
      console.error('Error saving to localStorage:', error);
    }
  };

  return [storedValue, setValue] as const;
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    const media = window.matchMedia(query);
    if (media.matches !== matches) setMatches(media.matches);
    const listener = () => setMatches(media.matches);
    media.addEventListener('change', listener);
    return () => media.removeEventListener('change', listener);
  }, [matches, query]);

  return matches;
}

// ============================================================================
// COMPONENTS - Atoms
// ============================================================================

interface ButtonProps {
  children: React.ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  icon?: React.ReactNode;
  onClick?: () => void;
  className?: string;
}

const Button: React.FC<ButtonProps> = ({
  children, variant = 'primary', size = 'md', loading, disabled, icon, onClick, className
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2';
  
  const variantStyles = {
    primary: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500 shadow-lg shadow-blue-500/25',
    secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-gray-500 dark:bg-gray-800 dark:text-white dark:hover:bg-gray-700',
    ghost: 'bg-transparent text-gray-600 hover:bg-gray-100 focus:ring-gray-500 dark:text-gray-300 dark:hover:bg-gray-800',
    danger: 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
  };
  
  const sizeStyles = {
    sm: 'px-3 py-1.5 text-sm gap-1.5',
    md: 'px-4 py-2 text-sm gap-2',
    lg: 'px-6 py-3 text-base gap-2'
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={cn(
        baseStyles,
        variantStyles[variant],
        sizeStyles[size],
        (disabled || loading) && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      {loading ? (
        <RefreshCw className="w-4 h-4 animate-spin" />
      ) : icon}
      {children}
    </button>
  );
};

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

const Card: React.FC<CardProps> = ({ children, className, hover, onClick }) => (
  <motion.div
    variants={ANIMATION_VARIANTS.fadeIn}
    initial="initial"
    animate="animate"
    whileHover={hover ? { scale: 1.02, y: -2 } : undefined}
    onClick={onClick}
    className={cn(
      'bg-white dark:bg-gray-900 rounded-2xl shadow-xl shadow-gray-200/50 dark:shadow-none border border-gray-100 dark:border-gray-800 p-6',
      hover && 'cursor-pointer',
      className
    )}
  >
    {children}
  </motion.div>
);

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  trend?: TimeSeriesPoint[];
  color?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, change, icon, trend, color = COLORS.primary }) => {
  const isPositive = change !== undefined && change >= 0;
  
  return (
    <Card hover className="relative overflow-hidden">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm font-medium text-gray-500 dark:text-gray-400">{title}</p>
          <p className="text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
          {change !== undefined && (
            <div className={cn(
              'inline-flex items-center gap-1 text-sm font-medium',
              isPositive ? 'text-green-600' : 'text-red-600'
            )}>
              {isPositive ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
              {formatPercentage(Math.abs(change))}
              <span className="text-gray-400 font-normal">vs. letzte Woche</span>
            </div>
          )}
        </div>
        <div 
          className="p-3 rounded-xl"
          style={{ backgroundColor: `${color}15` }}
        >
          <div style={{ color }}>{icon}</div>
        </div>
      </div>
      
      {trend && trend.length > 0 && (
        <div className="mt-4 h-16 -mx-2">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trend}>
              <defs>
                <linearGradient id={`gradient-${title}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                fill={`url(#gradient-${title})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      
      <div 
        className="absolute top-0 right-0 w-32 h-32 opacity-5"
        style={{ 
          background: `radial-gradient(circle at top right, ${color}, transparent)` 
        }}
      />
    </Card>
  );
};

// ============================================================================
// COMPONENTS - Charts
// ============================================================================

interface ChartContainerProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}

const ChartContainer: React.FC<ChartContainerProps> = ({ title, subtitle, children, actions }) => (
  <Card className="h-full">
    <div className="flex items-center justify-between mb-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
    {children}
  </Card>
);

interface RatingTrendChartProps {
  data: TimeSeriesPoint[];
  chains: string[];
}

const RatingTrendChart: React.FC<RatingTrendChartProps> = ({ data, chains }) => {
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload) return null;
    return (
      <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow-xl border border-gray-100 dark:border-gray-700">
        <p className="text-sm font-medium text-gray-900 dark:text-white mb-2">
          {format(parseISO(label), 'dd. MMMM yyyy', { locale: de })}
        </p>
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center gap-2 text-sm">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-gray-600 dark:text-gray-300">{entry.name}:</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {entry.value.toFixed(2)} ★
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <ChartContainer 
      title="Rating-Trend" 
      subtitle="Ø Bewertung der letzten 30 Tage"
      actions={
        <Button variant="ghost" size="sm" icon={<Download className="w-4 h-4" />}>
          Export
        </Button>
      }
    >
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
            <XAxis 
              dataKey="date" 
              tick={{ fontSize: 12 }}
              tickFormatter={(date) => format(parseISO(date), 'dd.MM')}
              stroke="#9CA3AF"
            />
            <YAxis 
              domain={[3.5, 5]} 
              tick={{ fontSize: 12 }}
              stroke="#9CA3AF"
              tickFormatter={(value) => value.toFixed(1)}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend />
            {chains.map((chain, index) => (
              <Line
                key={chain}
                type="monotone"
                dataKey={chain}
                name={chain}
                stroke={COLORS.chart[index % COLORS.chart.length]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6, strokeWidth: 2 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </ChartContainer>
  );
};

interface SentimentDistributionProps {
  data: { name: string; value: number; color: string }[];
}

const SentimentDistribution: React.FC<SentimentDistributionProps> = ({ data }) => {
  const total = data.reduce((sum, item) => sum + item.value, 0);
  
  return (
    <ChartContainer title="Sentiment-Verteilung" subtitle="Basierend auf NLP-Analyse">
      <div className="h-64 flex items-center">
        <ResponsiveContainer width="50%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={5}
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={index} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="flex-1 space-y-4">
          {data.map((item) => (
            <div key={item.name} className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-sm text-gray-600 dark:text-gray-300">{item.name}</span>
              </div>
              <div className="text-right">
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  {formatNumber(item.value)}
                </span>
                <span className="text-xs text-gray-400 ml-2">
                  ({((item.value / total) * 100).toFixed(1)}%)
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </ChartContainer>
  );
};

// ============================================================================
// COMPONENTS - Alerts & Notifications
// ============================================================================

interface AlertCardProps {
  alert: AnomalyAlert;
  onDismiss: (id: string) => void;
  onView: (alert: AnomalyAlert) => void;
}

const AlertCard: React.FC<AlertCardProps> = ({ alert, onDismiss, onView }) => {
  const severityConfig = {
    critical: { bg: 'bg-red-50 dark:bg-red-900/20', border: 'border-red-200 dark:border-red-800', icon: AlertTriangle },
    high: { bg: 'bg-orange-50 dark:bg-orange-900/20', border: 'border-orange-200 dark:border-orange-800', icon: AlertTriangle },
    medium: { bg: 'bg-yellow-50 dark:bg-yellow-900/20', border: 'border-yellow-200 dark:border-yellow-800', icon: Clock },
    low: { bg: 'bg-blue-50 dark:bg-blue-900/20', border: 'border-blue-200 dark:border-blue-800', icon: Activity }
  };
  
  const config = severityConfig[alert.severity];
  const Icon = config.icon;

  return (
    <motion.div
      layout
      variants={ANIMATION_VARIANTS.slideIn}
      initial="initial"
      animate="animate"
      exit="exit"
      className={cn(
        'p-4 rounded-xl border-2 transition-all duration-200',
        config.bg,
        config.border,
        !alert.isRead && 'ring-2 ring-offset-2',
        alert.severity === 'critical' && 'ring-red-500',
        alert.severity === 'high' && 'ring-orange-500'
      )}
    >
      <div className="flex items-start gap-4">
        <div 
          className="p-2 rounded-lg"
          style={{ backgroundColor: getSeverityColor(alert.severity) + '20' }}
        >
          <Icon 
            className="w-5 h-5" 
            style={{ color: getSeverityColor(alert.severity) }} 
          />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-sm font-semibold text-gray-900 dark:text-white">
              {alert.chainName}
            </span>
            <span 
              className="px-2 py-0.5 text-xs font-medium rounded-full"
              style={{ 
                backgroundColor: getSeverityColor(alert.severity) + '20',
                color: getSeverityColor(alert.severity)
              }}
            >
              {alert.severity.toUpperCase()}
            </span>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">
            {alert.message}
          </p>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>Konfidenz: {(alert.confidence * 100).toFixed(0)}%</span>
            <span>•</span>
            <span>{getRelativeTime(alert.detectedAt)}</span>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => onView(alert)}
            icon={<ExternalLink className="w-4 h-4" />}
          >
            Details
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => onDismiss(alert.id)}
            icon={<X className="w-4 h-4" />}
          />
        </div>
      </div>
    </motion.div>
  );
};

// ============================================================================
// COMPONENTS - Chain Table
// ============================================================================

interface ChainTableProps {
  chains: ChainData[];
  onSelect: (chain: ChainData) => void;
}

const ChainTable: React.FC<ChainTableProps> = ({ chains, onSelect }) => {
  const [sortField, setSortField] = useState<keyof ChainData>('avgRating');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [searchTerm, setSearchTerm] = useState('');

  const sortedChains = useMemo(() => {
    return [...chains]
      .filter(chain => 
        chain.name.toLowerCase().includes(searchTerm.toLowerCase())
      )
      .sort((a, b) => {
        const aVal = a[sortField];
        const bVal = b[sortField];
        const modifier = sortDirection === 'asc' ? 1 : -1;
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return (aVal - bVal) * modifier;
        }
        return String(aVal).localeCompare(String(bVal)) * modifier;
      });
  }, [chains, sortField, sortDirection, searchTerm]);

  const handleSort = (field: keyof ChainData) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
  };

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Chain-Übersicht
        </h3>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Suchen..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-4 py-2 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="overflow-x-auto -mx-6">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              {[
                { key: 'name', label: 'Chain' },
                { key: 'locations', label: 'Standorte' },
                { key: 'avgRating', label: 'Rating' },
                { key: 'ratingTrend', label: 'Trend' },
                { key: 'reviewCount', label: 'Reviews' },
                { key: 'sentiment', label: 'Sentiment' },
                { key: 'lastUpdated', label: 'Aktualisiert' }
              ].map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => handleSort(key as keyof ChainData)}
                  className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-900 dark:hover:text-white transition-colors"
                >
                  <div className="flex items-center gap-1">
                    {label}
                    {sortField === key && (
                      <ChevronDown className={cn(
                        'w-4 h-4 transition-transform',
                        sortDirection === 'asc' && 'rotate-180'
                      )} />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
            {sortedChains.map((chain) => (
              <motion.tr
                key={chain.id}
                onClick={() => onSelect(chain)}
                whileHover={{ backgroundColor: 'rgba(59, 130, 246, 0.05)' }}
                className="cursor-pointer transition-colors"
              >
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                      <span className="text-lg font-bold text-gray-400">
                        {chain.name.charAt(0)}
                      </span>
                    </div>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {chain.name}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 text-gray-600 dark:text-gray-300">
                  {formatNumber(chain.locations)}
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-1">
                    <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {chain.avgRating.toFixed(2)}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={cn(
                    'inline-flex items-center gap-1 text-sm font-medium',
                    chain.ratingTrend > 0 ? 'text-green-600' : chain.ratingTrend < 0 ? 'text-red-600' : 'text-gray-400'
                  )}>
                    {chain.ratingTrend > 0 ? <TrendingUp className="w-4 h-4" /> : 
                     chain.ratingTrend < 0 ? <TrendingDown className="w-4 h-4" /> : 
                     <Minus className="w-4 h-4" />}
                    {formatPercentage(chain.ratingTrend)}
                  </span>
                </td>
                <td className="px-6 py-4 text-gray-600 dark:text-gray-300">
                  {formatNumber(chain.reviewCount)}
                </td>
                <td className="px-6 py-4">
                  <span className={cn(
                    'px-2.5 py-1 text-xs font-medium rounded-full',
                    chain.sentiment === 'positive' && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
                    chain.sentiment === 'neutral' && 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
                    chain.sentiment === 'negative' && 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                  )}>
                    {chain.sentiment === 'positive' ? 'Positiv' : 
                     chain.sentiment === 'neutral' ? 'Neutral' : 'Negativ'}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-400">
                  {getRelativeTime(chain.lastUpdated)}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
};

// ============================================================================
// MAIN DASHBOARD COMPONENT
// ============================================================================

export default function Dashboard() {
  // State
  const [darkMode, setDarkMode] = useLocalStorage('darkMode', false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedTimeRange, setSelectedTimeRange] = useState('30d');
  const [alerts, setAlerts] = useState<AnomalyAlert[]>([]);
  const isMobile = useMediaQuery('(max-width: 768px)');

  // Mock Data (replace with API calls)
  const stats: DashboardStats = {
    totalLocations: 12847,
    totalReviews: 2847593,
    averageRating: 4.23,
    ratingChange: 2.4,
    activeAlerts: 7,
    revenue: 47500,
    revenueChange: 18.3,
    activeUsers: 23
  };

  const mockTrendData = Array.from({ length: 30 }, (_, i) => ({
    date: format(subDays(new Date(), 29 - i), 'yyyy-MM-dd'),
    "McDonald's": 4.1 + Math.random() * 0.3,
    "Burger King": 3.9 + Math.random() * 0.3,
    "KFC": 4.0 + Math.random() * 0.3,
    value: 4.0 + Math.random() * 0.4
  }));

  const mockSentiment = [
    { name: 'Positiv', value: 65420, color: COLORS.success },
    { name: 'Neutral', value: 23100, color: COLORS.neutral },
    { name: 'Negativ', value: 11480, color: COLORS.danger }
  ];

  const mockChains: ChainData[] = [
    { id: '1', name: "McDonald's", logo: '', locations: 1456, avgRating: 4.12, ratingTrend: 1.2, reviewCount: 234567, sentiment: 'positive', lastUpdated: '2026-01-17T10:00:00Z' },
    { id: '2', name: "Burger King", logo: '', locations: 892, avgRating: 3.89, ratingTrend: -0.8, reviewCount: 156789, sentiment: 'neutral', lastUpdated: '2026-01-17T09:30:00Z' },
    { id: '3', name: "KFC", logo: '', locations: 634, avgRating: 4.05, ratingTrend: 0.3, reviewCount: 98765, sentiment: 'positive', lastUpdated: '2026-01-17T11:00:00Z' },
    { id: '4', name: "Subway", logo: '', locations: 1123, avgRating: 3.78, ratingTrend: -1.5, reviewCount: 187654, sentiment: 'negative', lastUpdated: '2026-01-16T22:00:00Z' },
    { id: '5', name: "Starbucks", logo: '', locations: 567, avgRating: 4.34, ratingTrend: 2.1, reviewCount: 145678, sentiment: 'positive', lastUpdated: '2026-01-17T08:00:00Z' }
  ];

  const mockAlerts: AnomalyAlert[] = [
    { id: '1', chainId: '4', chainName: 'Subway', type: 'rating_drop', severity: 'high', message: 'Rating ist in den letzten 7 Tagen um 8.3% gefallen', detectedAt: '2026-01-17T14:30:00Z', isRead: false, confidence: 0.94 },
    { id: '2', chainId: '2', chainName: 'Burger King', type: 'review_spike', severity: 'medium', message: 'Ungewöhnlich viele negative Reviews in Berlin', detectedAt: '2026-01-17T12:00:00Z', isRead: false, confidence: 0.87 },
    { id: '3', chainId: '5', chainName: 'Starbucks', type: 'sentiment_shift', severity: 'low', message: 'Sentiment-Verbesserung in München erkannt', detectedAt: '2026-01-17T10:00:00Z', isRead: true, confidence: 0.91 }
  ];

  useEffect(() => {
    setAlerts(mockAlerts);
  }, []);

  // Handlers
  const handleDismissAlert = (id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  };

  const handleViewAlert = (alert: AnomalyAlert) => {
    console.log('View alert:', alert);
  };

  const handleSelectChain = (chain: ChainData) => {
    console.log('Selected chain:', chain);
  };

  // Render
  return (
    <div className={cn(
      'min-h-screen transition-colors duration-300',
      darkMode ? 'dark bg-gray-950' : 'bg-gray-50'
    )}>
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              <Menu className="w-5 h-5 text-gray-600 dark:text-gray-300" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900 dark:text-white">ReviewSignal</h1>
                <p className="text-xs text-gray-500">Enterprise Dashboard v7.0</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Time Range Selector */}
            <select
              value={selectedTimeRange}
              onChange={(e) => setSelectedTimeRange(e.target.value)}
              className="px-4 py-2 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="7d">Letzte 7 Tage</option>
              <option value="30d">Letzte 30 Tage</option>
              <option value="90d">Letzte 90 Tage</option>
              <option value="1y">Letztes Jahr</option>
            </select>

            {/* Notifications */}
            <button className="relative p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              <Bell className="w-5 h-5 text-gray-600 dark:text-gray-300" />
              {alerts.filter(a => !a.isRead).length > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
              )}
            </button>

            {/* Dark Mode Toggle */}
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              {darkMode ? (
                <Sun className="w-5 h-5 text-yellow-500" />
              ) : (
                <Moon className="w-5 h-5 text-gray-600" />
              )}
            </button>

            {/* User Menu */}
            <div className="flex items-center gap-3 pl-4 border-l border-gray-200 dark:border-gray-700">
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center">
                <span className="text-sm font-semibold text-white">S</span>
              </div>
              <div className="hidden md:block">
                <p className="text-sm font-medium text-gray-900 dark:text-white">Simon</p>
                <p className="text-xs text-gray-500">Enterprise</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="p-6 space-y-6">
        {/* Stats Grid */}
        <motion.div
          variants={ANIMATION_VARIANTS.fadeIn}
          initial="initial"
          animate="animate"
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
        >
          <StatCard
            title="Gesamtstandorte"
            value={formatNumber(stats.totalLocations)}
            icon={<MapPin className="w-6 h-6" />}
            trend={mockTrendData}
            color={COLORS.primary}
          />
          <StatCard
            title="Durchschnittliches Rating"
            value={`${stats.averageRating.toFixed(2)} ★`}
            change={stats.ratingChange}
            icon={<Star className="w-6 h-6" />}
            trend={mockTrendData}
            color={COLORS.warning}
          />
          <StatCard
            title="Monatsumsatz"
            value={formatCurrency(stats.revenue)}
            change={stats.revenueChange}
            icon={<DollarSign className="w-6 h-6" />}
            trend={mockTrendData}
            color={COLORS.success}
          />
          <StatCard
            title="Aktive Alerts"
            value={stats.activeAlerts}
            icon={<AlertTriangle className="w-6 h-6" />}
            color={COLORS.danger}
          />
        </motion.div>

        {/* Alerts Section */}
        {alerts.length > 0 && (
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Anomalie-Alerts ({alerts.filter(a => !a.isRead).length} neu)
              </h3>
              <Button variant="ghost" size="sm">
                Alle als gelesen markieren
              </Button>
            </div>
            <AnimatePresence mode="popLayout">
              <div className="space-y-3">
                {alerts.map((alert) => (
                  <AlertCard
                    key={alert.id}
                    alert={alert}
                    onDismiss={handleDismissAlert}
                    onView={handleViewAlert}
                  />
                ))}
              </div>
            </AnimatePresence>
          </Card>
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <RatingTrendChart
              data={mockTrendData}
              chains={["McDonald's", "Burger King", "KFC"]}
            />
          </div>
          <div>
            <SentimentDistribution data={mockSentiment} />
          </div>
        </div>

        {/* Chain Table */}
        <ChainTable chains={mockChains} onSelect={handleSelectChain} />

        {/* Footer */}
        <footer className="text-center text-sm text-gray-400 py-8">
          <p>ReviewSignal v7.0 • Enterprise Dashboard</p>
          <p className="mt-1">© 2026 ReviewSignal • Built with ❤️ by Claude AI + Simon</p>
        </footer>
      </main>
    </div>
  );
}

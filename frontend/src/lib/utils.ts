export function cn(...classes: any[]) {
  return classes.filter(Boolean).join(' ');
}

export function formatCurrency(value: number, currency: string) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value);
}

export function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US').format(value);
}

export function formatPercentage(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export function KPICard({ title, value, change, trend, icon, color, description }: any) {
  return <div className="kpi-card">{title}: {value}</div>;
}

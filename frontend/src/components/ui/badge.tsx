export function Badge({ children, variant, ...props }: any) {
  return <span className={`badge ${variant}`} {...props}>{children}</span>;
}

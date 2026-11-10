interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  label: string;
}

/** Tiny hand-drawn SVG trend line; the lowest point gets a dot. */
export function Sparkline({ values, width = 140, height = 36, label }: SparklineProps) {
  if (values.length < 2) return <span className="sparkline sparkline--empty" />;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pad = 3;
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - pad * 2);
  const y = (v: number) => pad + (1 - (v - min) / range) * (height - pad * 2);
  const points = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const lowIndex = values.lastIndexOf(min);

  return (
    <svg
      className="sparkline"
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={label}
    >
      <polyline points={points} fill="none" />
      <circle cx={x(lowIndex)} cy={y(min)} r={2.5} />
    </svg>
  );
}

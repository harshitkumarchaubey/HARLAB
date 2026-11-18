import React from "react";

interface LineChartProps {
  title: string;
  data: { x: number; y: number | null; y2?: number | null }[];
  primaryLabel: string;
  secondaryLabel?: string;
  unit?: string;
}

export const LineSeriesChart: React.FC<LineChartProps> = ({
  title,
  data,
  primaryLabel,
  secondaryLabel,
  unit = "",
}) => {
  const validPrimary = data.filter((d): d is { x: number; y: number; y2?: number | null } => d.y !== null);
  if (validPrimary.length < 2) {
    return (
      <div className="panel">
        <h3 className="panel-title">{title}</h3>
        <p className="muted">Insufficient computed points to plot.</p>
      </div>
    );
  }

  const allVals: number[] = [];
  for (const pt of validPrimary) {
    allVals.push(pt.y);
    if (pt.y2 !== undefined && pt.y2 !== null) allVals.push(pt.y2);
  }
  const minY = Math.min(...allVals);
  const maxY = Math.max(...allVals);
  const spanY = maxY - minY || 1e-6;
  const minX = validPrimary[0].x;
  const maxX = validPrimary[validPrimary.length - 1].x;
  const spanX = maxX - minX || 1;

  const W = 560;
  const H = 190;
  const padL = 56;
  const padR = 14;
  const padT = 14;
  const padB = 26;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const sx = (x: number) => padL + ((x - minX) / spanX) * plotW;
  const sy = (y: number) => padT + plotH - ((y - minY) / spanY) * plotH;

  const pathPrimary = validPrimary
    .map((p, idx) => `${idx === 0 ? "M" : "L"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`)
    .join(" ");

  const validSecondary = data.filter(
    (d): d is { x: number; y: number | null; y2: number } => d.y2 !== undefined && d.y2 !== null
  );
  const pathSecondary = validSecondary
    .map((p, idx) => `${idx === 0 ? "M" : "L"}${sx(p.x).toFixed(1)},${sy(p.y2).toFixed(1)}`)
    .join(" ");

  return (
    <div className="panel">
      <div className="panel-header">
        <h3 className="panel-title">{title}</h3>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-secondary)" }}>
          <span style={{ color: "#58a6ff" }}>■ {primaryLabel}</span>
          {secondaryLabel ? (
            <span style={{ color: "#d29922", marginLeft: 12 }}>■ {secondaryLabel}</span>
          ) : null}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        {[0, 0.5, 1].map((frac) => {
          const val = minY + frac * spanY;
          const yPos = sy(val);
          return (
            <g key={frac}>
              <line x1={padL} x2={W - padR} y1={yPos} y2={yPos} stroke="#243040" strokeDasharray="3,3" />
              <text x={padL - 6} y={yPos + 4} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">
                {val.toFixed(2)}{unit}
              </text>
            </g>
          );
        })}
        <path d={pathPrimary} fill="none" stroke="#58a6ff" strokeWidth="1.8" />
        {pathSecondary ? (
          <path d={pathSecondary} fill="none" stroke="#d29922" strokeWidth="1.3" strokeDasharray="4,2" />
        ) : null}
        <text x={padL} y={H - 6} fontSize="10" fill="#8b949e" className="mono">Step {minX}</text>
        <text x={W - padR} y={H - 6} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">Step {maxX}</text>
      </svg>
    </div>
  );
};

export const ImbalanceBarChart: React.FC<{
  title: string;
  data: { step: number; value: number | null }[];
}> = ({ title, data }) => {
  const pts = data.filter((d): d is { step: number; value: number } => d.value !== null);
  if (pts.length === 0) {
    return (
      <div className="panel">
        <h3 className="panel-title">{title}</h3>
        <p className="muted">No imbalance observations available.</p>
      </div>
    );
  }
  const W = 560;
  const H = 170;
  const padL = 44;
  const padR = 12;
  const midY = H / 2;
  const maxBarH = H / 2 - 18;
  const barW = Math.max(1.5, (W - padL - padR) / pts.length);

  return (
    <div className="panel">
      <h3 className="panel-title" style={{ marginBottom: 10 }}>{title}</h3>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        <line x1={padL} x2={W - padR} y1={midY} y2={midY} stroke="#324256" />
        <text x={padL - 6} y={20} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">+1.0</text>
        <text x={padL - 6} y={midY + 4} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">0.0</text>
        <text x={padL - 6} y={H - 12} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">-1.0</text>
        {pts.map((p, idx) => {
          const h = Math.abs(p.value) * maxBarH;
          const y = p.value >= 0 ? midY - h : midY;
          return (
            <rect
              key={p.step}
              x={padL + idx * barW}
              y={y}
              width={Math.max(1, barW - 0.5)}
              height={Math.max(1, h)}
              fill={p.value >= 0 ? "#2ea043" : "#f85149"}
              opacity="0.85"
            />
          );
        })}
      </svg>
    </div>
  );
};

export const ScatterPlot: React.FC<{
  title: string;
  xLabel: string;
  yLabel: string;
  points: { x: number; y: number }[];
}> = ({ title, xLabel, yLabel, points }) => {
  if (points.length < 3) {
    return (
      <div className="panel">
        <h3 className="panel-title">{title}</h3>
        <p className="muted">Not enough out-of-sample observations to plot.</p>
      </div>
    );
  }
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;

  const W = 520;
  const H = 200;
  const padL = 52;
  const padR = 16;
  const padT = 14;
  const padB = 30;
  const sx = (x: number) => padL + ((x - minX) / spanX) * (W - padL - padR);
  const sy = (y: number) => padT + (H - padT - padB) - ((y - minY) / spanY) * (H - padT - padB);

  return (
    <div className="panel">
      <h3 className="panel-title" style={{ marginBottom: 8 }}>{title}</h3>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
        {minY < 0 && maxY > 0 ? (
          <line x1={padL} x2={W - padR} y1={sy(0)} y2={sy(0)} stroke="#324256" strokeDasharray="3,3" />
        ) : null}
        {minX < 0 && maxX > 0 ? (
          <line x1={sx(0)} x2={sx(0)} y1={padT} y2={H - padB} stroke="#324256" strokeDasharray="3,3" />
        ) : null}
        {points.map((p, idx) => (
          <circle key={idx} cx={sx(p.x)} cy={sy(p.y)} r="3" fill="#58a6ff" opacity="0.75" />
        ))}
        <text x={W / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="#8b949e" className="mono">
          {xLabel} [{minX.toFixed(2)} .. {maxX.toFixed(2)}]
        </text>
        <text x={padL - 6} y={padT + 8} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">
          {maxY.toFixed(1)}
        </text>
        <text x={padL - 6} y={H - padB} textAnchor="end" fontSize="10" fill="#8b949e" className="mono">
          {minY.toFixed(1)}
        </text>
        <text x={padL + 6} y={padT + 10} fontSize="10" fill="#8b949e" className="mono">
          {yLabel}
        </text>
      </svg>
    </div>
  );
};

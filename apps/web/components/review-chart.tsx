"use client";
import type { BaseReview } from "@/lib/types";

export function ReviewChart({
  base,
  compact = false,
}: {
  base: BaseReview;
  compact?: boolean;
}) {
  const total = base.compatible + base.missing_icms + base.other_difference;
  const percent = total ? (base.compatible / total) * 100 : 0;
  const segments = [
    {
      label: "Compatíveis com a fórmula",
      value: base.compatible,
      color: "#1a493b",
    },
    {
      label: "ICMS não descontado",
      value: base.missing_icms,
      color: "#a9c943",
    },
    {
      label: "Outra diferença de base",
      value: base.other_difference,
      color: "#bd744d",
    },
  ];
  return (
    <div className={`review-chart ${compact ? "compact" : ""}`}>
      <div className="donut-wrap">
        <svg
          viewBox="0 0 160 160"
          role="img"
          aria-label={`${base.compatible} de ${total} linhas compatíveis com a fórmula da base de PIS e COFINS`}
        >
          <circle
            cx="80"
            cy="80"
            r="62"
            fill="none"
            stroke="#edf0e8"
            strokeWidth="16"
          />
          {segments.map((s, index) => {
            const before = segments
              .slice(0, index)
              .reduce((sum, r) => sum + r.value, 0);
            return (
              <circle
                key={s.label}
                cx="80"
                cy="80"
                r="62"
                fill="none"
                stroke={s.color}
                strokeWidth="16"
                pathLength="100"
                strokeDasharray={`${total ? (s.value / total) * 100 : 0} 100`}
                strokeDashoffset={total ? (-before / total) * 100 : 0}
                transform="rotate(-90 80 80)"
                className="chart-ring"
              />
            );
          })}
        </svg>
        <div className="donut-label">
          <strong>
            {total
              ? `${percent.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`
              : "—"}
          </strong>
          <span>compatíveis</span>
        </div>
      </div>
      <div className="chart-legend">
        {segments.map((s) => (
          <div key={s.label}>
            <span className="legend-dot" style={{ background: s.color }} />
            <span>{s.label}</span>
            <strong>{s.value.toLocaleString("pt-BR")}</strong>
          </div>
        ))}
        <p>
          {total.toLocaleString("pt-BR")} linhas comparadas · PIS e COFINS, CST
          01 e 02
          {base.unassessed > 0
            ? ` · ${base.unassessed} sem comparação completa`
            : ""}
          . Este gráfico não mede conformidade fiscal geral.
        </p>
      </div>
    </div>
  );
}

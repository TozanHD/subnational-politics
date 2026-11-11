import { useMemo } from 'react';
import { chamberLayout, type ChamberConfig } from '../chamber';
import type { Segment } from '../data';

interface Props {
  segments: Segment[];
  /** 定数（合計との差を白抜きで描く） */
  fixed: number;
  /** 議場の形 */
  chamber: ChamberConfig;
  /** 白抜きの席の説明（ツールチップ） */
  emptyLabel?: string;
  /** 席のツールチップと「議長席」の文字を出すか（一覧の小さい図では省略） */
  detailed?: boolean;
  label: string;
}

/** 議場の形に合わせた議席の模式図。 */
export default function Chamber({ segments, fixed, chamber, detailed = false, label, emptyLabel = '欠員' }: Props) {
  const total = segments.reduce((a, s) => a + s.count, 0);
  const fills = useMemo(() => {
    const list: { party: string | null; color: string }[] = [];
    for (const s of segments) for (let i = 0; i < s.count; i++) list.push({ party: s.name, color: s.color });
    for (let i = total; i < fixed; i++) list.push({ party: null, color: 'none' });
    return list;
  }, [segments, fixed, total]);
  const lay = useMemo(() => chamberLayout(fills.length, chamber), [fills.length, chamber]);
  const { seats, r, podium, label: lb } = lay;

  // 図全体の大きさ（席の並びの幅を基準に文字や議長席の大きさを決める）
  const xs = seats.map((s) => s.x);
  const ys = seats.map((s) => s.y);
  let minX = Math.min(...xs, 0) - r;
  let maxX = Math.max(...xs, 0) + r;
  let minY = Math.min(...ys, 0) - r;
  let maxY = Math.max(...ys, 0) + r;
  const u = (maxX - minX) / 2; // 半円形の半径 1 に相当する長さ
  const pw = podium?.vertical ? 0.07 * u : 0.3 * u;
  const ph = podium?.vertical ? 0.3 * u : 0.07 * u;
  if (podium) {
    minX = Math.min(minX, podium.x - pw / 2);
    minY = Math.min(minY, podium.y - ph / 2 - (detailed && !podium.vertical ? 0.1 * u : 0));
    if (detailed && podium.vertical) minX -= 0.09 * u;
  }
  const below = lb.place === 'below';
  const fsTotal = (below ? 0.16 : 0.22) * u;
  const fsSub = 0.075 * u;
  if (below) maxY = Math.max(maxY, lb.y + fsTotal * 1.05);
  else maxY = Math.max(maxY, lb.y + fsSub * 2);
  const pad = 0.02 * u;

  return (
    <svg
      className="hemicycle"
      viewBox={`${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`}
      role="img"
      aria-label={label}
    >
      {podium && (
        <g className="podium">
          <rect x={podium.x - pw / 2} y={podium.y - ph / 2} width={pw} height={ph} rx={Math.min(pw, ph) * 0.3} />
          {detailed &&
            (podium.vertical ? (
              <text
                x={podium.x - pw / 2 - 0.035 * u}
                y={podium.y}
                fontSize={0.055 * u}
                textAnchor="middle"
                transform={`rotate(-90 ${podium.x - pw / 2 - 0.035 * u} ${podium.y})`}
              >
                議長席
              </text>
            ) : (
              <text x={podium.x} y={podium.y - ph / 2 - 0.03 * u} fontSize={0.055 * u} textAnchor="middle">
                議長席
              </text>
            ))}
        </g>
      )}
      {seats.map((s, i) => {
        const f = fills[i];
        return (
          <circle
            key={i}
            cx={s.x}
            cy={s.y}
            r={r}
            fill={f.party ? f.color : 'none'}
            className={f.party ? undefined : 'seat-vacant'}
            strokeWidth={f.party ? 0 : r * 0.25}
          >
            {detailed && <title>{f.party ?? emptyLabel}</title>}
          </circle>
        );
      })}
      {below ? (
        <text x={lb.x} y={lb.y + fsTotal * 0.8} textAnchor="middle" fontSize={fsTotal} className="hemicycle-total">
          {total}
          <tspan fontSize={fsSub} dx={0.04 * u} fontWeight="400" className="hemicycle-sub">
            定数 {fixed}
          </tspan>
        </text>
      ) : (
        <>
          <text x={lb.x} y={lb.y} textAnchor="middle" fontSize={fsTotal} className="hemicycle-total">
            {total}
          </text>
          <text x={lb.x} y={lb.y + 0.09 * u} textAnchor="middle" fontSize={fsSub} className="hemicycle-sub">
            定数 {fixed}
          </text>
        </>
      )}
    </svg>
  );
}

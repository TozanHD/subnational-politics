import { useMemo } from 'react';
import type { Segment } from '../data';

interface Seat {
  x: number;
  y: number;
  angle: number;
}

/** n 議席を半円状に並べる座標を計算する（外側の列ほど多くの席を置く）。 */
function layout(n: number): { seats: Seat[]; r: number } {
  if (n <= 0) return { seats: [], r: 0 };
  const rows = Math.min(10, Math.max(2, Math.ceil(Math.sqrt(n / 3.2))));
  const inner = rows <= 2 ? 0.6 : 0.47;
  const radii = Array.from({ length: rows }, (_, i) => inner + ((1 - inner) * i) / (rows - 1));
  const sumR = radii.reduce((a, b) => a + b, 0);
  const counts = radii.map((r) => Math.max(1, Math.floor((n * r) / sumR)));
  // 端数は外側の列から順に配る
  for (let i = rows - 1, rest = n - counts.reduce((a, b) => a + b, 0); rest > 0; i = (i - 1 + rows) % rows, rest--) counts[i]++;
  for (let i = 0, over = counts.reduce((a, b) => a + b, 0) - n; over > 0; i = (i + 1) % rows) {
    if (counts[i] > 1) {
      counts[i]--;
      over--;
    }
  }
  const seats: Seat[] = [];
  radii.forEach((r, i) => {
    const k = counts[i];
    for (let j = 0; j < k; j++) {
      const angle = k === 1 ? Math.PI / 2 : Math.PI - (j * Math.PI) / (k - 1);
      seats.push({ x: r * Math.cos(angle), y: r * Math.sin(angle), angle });
    }
  });
  // 左から右へ、同じ角度なら外側から
  seats.sort((a, b) => b.angle - a.angle || Math.hypot(b.x, b.y) - Math.hypot(a.x, a.y));
  const spacing = Math.min(...radii.map((r, i) => (counts[i] > 1 ? (Math.PI * r) / (counts[i] - 1) : 1)), (1 - inner) / Math.max(1, rows - 1));
  return { seats, r: Math.min(0.08, spacing * 0.42) };
}

interface Props {
  segments: Segment[];
  /** 定数（現員との差を欠員として白抜きで描く） */
  fixed: number;
  /** 席のツールチップを出すか（一覧の小さい図では省略） */
  detailed?: boolean;
  label: string;
}

export default function Hemicycle({ segments, fixed, detailed = false, label }: Props) {
  const total = segments.reduce((a, s) => a + s.count, 0);
  const fills = useMemo(() => {
    const list: { party: string | null; color: string }[] = [];
    for (const s of segments) for (let i = 0; i < s.count; i++) list.push({ party: s.name, color: s.color });
    for (let i = total; i < fixed; i++) list.push({ party: null, color: 'none' });
    return list;
  }, [segments, fixed, total]);
  const { seats, r } = useMemo(() => layout(fills.length), [fills.length]);

  const pad = r + 0.02;
  return (
    <svg
      className="hemicycle"
      viewBox={`${-1 - pad} ${-1 - pad} ${2 + 2 * pad} ${1 + 2 * pad}`}
      role="img"
      aria-label={label}
    >
      {seats.map((s, i) => {
        const f = fills[i];
        return (
          <circle
            key={i}
            cx={s.x}
            cy={-s.y}
            r={r}
            fill={f.party ? f.color : 'none'}
            className={f.party ? undefined : 'seat-vacant'}
            strokeWidth={f.party ? 0 : r * 0.25}
          >
            {detailed && <title>{f.party ?? '欠員'}</title>}
          </circle>
        );
      })}
      <text x="0" y={-0.09} textAnchor="middle" fontSize={0.22} className="hemicycle-total">
        {total}
      </text>
      <text x="0" y={0.0} textAnchor="middle" fontSize={0.075} className="hemicycle-sub">
        定数 {fixed}
      </text>
    </svg>
  );
}

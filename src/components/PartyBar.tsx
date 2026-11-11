import { pct, type Segment } from '../data';

/** 構成を 100% 積み上げ横棒で表示する。 */
export default function PartyBar({ segments, showLegend = true }: { segments: Segment[]; showLegend?: boolean }) {
  const total = segments.reduce((a, s) => a + s.count, 0);
  return (
    <div className="party-bar-wrap">
      <div className="party-bar" role="img" aria-label={segments.map((s) => `${s.name} ${s.count}`).join('、')}>
        {segments.map((s) => (
          <span key={s.name} style={{ flexGrow: s.count, background: s.color }} title={`${s.name} ${s.count}人 (${pct(s.count, total)})`} />
        ))}
      </div>
      {showLegend && (
        <ul className="legend">
          {segments.map((s) => (
            <li key={s.name}>
              <i style={{ background: s.color }} />
              {s.short} <b>{s.count.toLocaleString()}</b>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

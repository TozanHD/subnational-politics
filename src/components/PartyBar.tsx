import { partyColor, partyEntries, pct, shortName } from '../data';
import type { Body } from '../types';

/** 政党別の構成を 100% 積み上げ横棒で表示する。 */
export default function PartyBar({ body, showLegend = true }: { body: Body; showLegend?: boolean }) {
  const entries = partyEntries(body);
  const total = body.total[2];
  return (
    <div className="party-bar-wrap">
      <div className="party-bar" role="img" aria-label={entries.map(([p, c]) => `${p} ${c[2]}`).join('、')}>
        {entries.map(([p, c]) => (
          <span key={p} style={{ flexGrow: c[2], background: partyColor(p) }} title={`${p} ${c[2]}人 (${pct(c[2], total)})`} />
        ))}
      </div>
      {showLegend && (
        <ul className="legend">
          {entries.map(([p, c]) => (
            <li key={p}>
              <i style={{ background: partyColor(p) }} />
              {shortName(p)} <b>{c[2].toLocaleString()}</b>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

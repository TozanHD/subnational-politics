import { useMemo, useState } from 'react';
import { REGIONS, bodySegments, dataset, largestParty, pct, regionOf, shortName, partyColor, sumBodies } from '../data';
import Hemicycle from './Hemicycle';
import PartyBar from './PartyBar';

type SortKey = 'code' | 'seats' | 'women' | 'ldp';

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'code', label: '都道府県順' },
  { key: 'seats', label: '定数の多い順' },
  { key: 'women', label: '女性比率の高い順' },
  { key: 'ldp', label: '自民の比率が高い順' },
];

export default function Home() {
  const [region, setRegion] = useState<string>('すべて');
  const [sort, setSort] = useState<SortKey>('code');
  const national = useMemo(() => sumBodies(dataset.prefectures.map((p) => p.assembly)), []);

  const prefs = useMemo(() => {
    const list = dataset.prefectures.filter((p) => region === 'すべて' || regionOf(p.code) === region);
    const share = (n: number, d: number) => (d ? n / d : 0);
    const key: Record<SortKey, (p: (typeof list)[number]) => number> = {
      code: (p) => -p.code,
      seats: (p) => p.assembly.fixed,
      women: (p) => share(p.assembly.total[1], p.assembly.total[2]),
      ldp: (p) => share(p.assembly.parties['自由民主党']?.[2] ?? 0, p.assembly.total[2]),
    };
    return [...list].sort((a, b) => key[sort](b) - key[sort](a));
  }, [region, sort]);

  const women = national.total[1];
  return (
    <>
      <section className="card summary">
        <h2>全国の都道府県議会</h2>
        <div className="stats">
          <Stat label="議員数" value={national.total[2].toLocaleString()} note={`定数 ${national.fixed.toLocaleString()}・欠員 ${national.vacant}`} />
          <Stat label="女性議員" value={pct(women, national.total[2])} note={`${women.toLocaleString()} 人`} />
          <Stat
            label="最大党派"
            value={shortName(largestParty(national)?.[0] ?? '—')}
            note={pct(largestParty(national)?.[1][2] ?? 0, national.total[2])}
          />
          <Stat
            label="無所属の知事"
            value={`${dataset.prefectures.filter((p) => p.governor?.party === '無所属').length} / 47`}
            note="総務省の届出上の所属"
            hidden={!dataset.prefectures[0].governor}
          />
        </div>
        <PartyBar segments={bodySegments(national)} />
      </section>

      <section>
        <div className="toolbar">
          <div className="chips" role="tablist" aria-label="地方で絞り込み">
            {['すべて', ...REGIONS.map((r) => r.name)].map((r) => (
              <button key={r} role="tab" aria-selected={region === r} className={region === r ? 'chip on' : 'chip'} onClick={() => setRegion(r)}>
                {r}
              </button>
            ))}
          </div>
          <label className="sort">
            並び替え
            <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid">
          {prefs.map((p) => {
            const top = largestParty(p.assembly);
            return (
              <a key={p.code} className="card pref-card" href={`#/pref/${encodeURIComponent(p.name)}`}>
                <div className="pref-head">
                  <h3>{p.name}</h3>
                  <span className="muted">{regionOf(p.code)}</span>
                </div>
                <Hemicycle segments={bodySegments(p.assembly)} fixed={p.assembly.fixed} label={`${p.name}議会 ${p.assembly.total[2]}人`} />
                <PartyBar segments={bodySegments(p.assembly)} showLegend={false} />
                <dl className="facts">
                  <div>
                    <dt>最大</dt>
                    <dd>
                      {top ? (
                        <>
                          <i className="dot" style={{ background: partyColor(top[0]) }} />
                          {shortName(top[0])} {pct(top[1][2], p.assembly.total[2], 0)}
                        </>
                      ) : (
                        '—'
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt>女性</dt>
                    <dd>{pct(p.assembly.total[1], p.assembly.total[2], 0)}</dd>
                  </div>
                  {p.governor !== undefined && (
                    <div>
                      <dt>知事</dt>
                      <dd>{p.governor ? shortName(p.governor.party) : '—'}</dd>
                    </div>
                  )}
                </dl>
              </a>
            );
          })}
        </div>
      </section>
    </>
  );
}

function Stat({ label, value, note, hidden }: { label: string; value: string; note?: string; hidden?: boolean }) {
  if (hidden) return null;
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {note && <span className="stat-note">{note}</span>}
    </div>
  );
}

import { dataset, formatDate, partyColor, pct, shortName, sumBodies, type Segment } from '../data';
import {
  DPJ,
  DPJ_SUCCESSORS,
  HISTORY_ENABLED,
  historyTotal,
  pickSnapshot,
  sumHistory,
  useCompare,
  useHistoryData,
  type HistoryBody,
  type HistorySnapshot,
} from '../history';
import type { Body, Prefecture } from '../types';
import PartyBar from './PartyBar';

/** 民主党政権期と比べるカード。pref を省略すると全国（47 都道府県議会の合計）。 */
export default function DpjCompare({ pref }: { pref?: Prefecture }) {
  const { on, year, setOn, setYear } = useCompare();
  const data = useHistoryData(on);
  if (!on) return null;

  const head = (
    <div className="compare-head">
      <h3>民主党政権期との比較</h3>
      <button type="button" className="link-button" onClick={() => setOn(false)}>
        比較を隠す
      </button>
    </div>
  );
  if (!data) {
    return (
      <section className="card compare">
        {head}
        <p className="muted small">読み込み中…</p>
      </section>
    );
  }

  const snap = pickSnapshot(data, year);
  const then: HistoryBody = pref
    ? snap.prefectures[pref.name].assembly
    : sumHistory(Object.values(snap.prefectures).map((p) => p.assembly));
  const now: Body = pref ? pref.assembly : sumBodies(dataset.prefectures.map((p) => p.assembly));
  const thenTotal = historyTotal(then);
  const nowTotal = now.total[2];
  const rows = mergedParties(snap, then, now);
  const dpjThen = then.parties[DPJ] ?? 0;
  const succNow = DPJ_SUCCESSORS.reduce((a, p) => a + (now.parties[p]?.[2] ?? 0), 0);
  const where = pref ? `${pref.name}議会` : '全国の都道府県議会';

  return (
    <section className="card compare">
      {head}
      <div className="chips tabs" role="tablist" aria-label="比べる時点">
        {data.snapshots.map((s) => (
          <button key={s.id} role="tab" aria-selected={s.id === snap.id} className={s.id === snap.id ? 'chip on' : 'chip'} onClick={() => setYear(s.id)}>
            {s.label}
          </button>
        ))}
      </div>

      <p className="compare-lead">
        {where}の民主党は <b>{dpjThen}人</b>（{pct(dpjThen, thenTotal)}）。現在の立憲民主党と国民民主党は合わせて <b>{succNow}人</b>（{pct(succNow, nowTotal)}）。
      </p>

      <div className="compare-bars">
        <span className="muted">{snap.asOf.slice(0, 4)}年末</span>
        <PartyBar segments={toSegments(rows, (p) => then.parties[p] ?? 0)} showLegend={false} />
        <span className="muted">現在</span>
        <PartyBar segments={toSegments(rows, (p) => now.parties[p]?.[2] ?? 0)} showLegend={false} />
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>党派</th>
              <th className="num">{snap.asOf.slice(0, 4)}年末</th>
              <th className="num">現在</th>
              <th className="num">増減 (pt)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const a = then.parties[p] ?? 0;
              const b = now.parties[p]?.[2] ?? 0;
              const d = share(b, nowTotal) - share(a, thenTotal);
              return (
                <tr key={p}>
                  <td>
                    <i className="dot" style={{ background: partyColor(p) }} />
                    {p}
                  </td>
                  <Cell n={a} total={thenTotal} />
                  <Cell n={b} total={nowTotal} />
                  <td className={`num ${d > 0.05 ? 'up' : d < -0.05 ? 'down' : 'muted'}`}>{signed(d)}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td>合計</td>
              <td className="num">
                {thenTotal.toLocaleString()}
                <span className="muted share">定数 {then.fixed.toLocaleString()}</span>
              </td>
              <td className="num">
                {nowTotal.toLocaleString()}
                <span className="muted share">定数 {now.fixed.toLocaleString()}</span>
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      {pref ? <GovernorThenNow snap={snap} pref={pref} /> : <NationalExtras snap={snap} />}

      <p className="muted small">
        出典：総務省「地方公共団体の議会の議員及び長の所属党派別人員調等」
        <a href={snap.source.pageUrl} target="_blank" rel="noopener noreferrer">
          {formatDate(snap.asOf)}現在
        </a>
        （{snap.cabinet}）と{formatDate(dataset.asOf)}現在。議員が選挙管理委員会に届け出た所属党派で、議会内の会派とは一致しないことがあります。
        民主党の後継として立憲民主党・国民民主党を並べていますが、議員の移り先はこの 2 党に限りません。
      </p>
    </section>
  );
}

function Cell({ n, total }: { n: number; total: number }) {
  return (
    <td className="num">
      {n ? n.toLocaleString() : '—'}
      {n > 0 && <span className="muted share">{pct(n, total)}</span>}
    </td>
  );
}

function GovernorThenNow({ snap, pref }: { snap: HistorySnapshot; pref: Prefecture }) {
  const then = snap.prefectures[pref.name].governor;
  const now = pref.governor?.party;
  if (!then && !now) return null;
  return (
    <p className="small">
      知事の所属党派（届出）：{snap.asOf.slice(0, 4)}年末 {then ?? '—'} → 現在 {now ?? '—'}
    </p>
  );
}

function NationalExtras({ snap }: { snap: HistorySnapshot }) {
  const local = (key: 'cityAssembly' | 'townAssembly') =>
    sumHistory(Object.values(snap.prefectures).flatMap((p) => (p[key] ? [p[key]!] : [])));
  const thenLocal = sumHistory([local('cityAssembly'), local('townAssembly')]);
  const nowLocal = sumBodies(dataset.prefectures.flatMap((p) => [p.cityAssembly, p.townAssembly].filter((b): b is Body => !!b)));
  const dpj = thenLocal.parties[DPJ] ?? 0;
  const succ = DPJ_SUCCESSORS.reduce((a, p) => a + (nowLocal.parties[p]?.[2] ?? 0), 0);
  const govThen = Object.entries(snap.prefectures)
    .filter(([, p]) => p.governor && p.governor !== '無所属')
    .map(([name, p]) => `${name}（${p.governor}）`);
  const govNow = dataset.prefectures
    .filter((p) => p.governor && p.governor.party !== '無所属')
    .map((p) => `${p.name}（${p.governor!.party}）`);
  return (
    <ul className="small compare-extra">
      <li>
        市区町村議会：民主党 {dpj.toLocaleString()}人（{pct(dpj, historyTotal(thenLocal))}）→ 立憲民主党＋国民民主党 {succ.toLocaleString()}人（
        {pct(succ, nowLocal.total[2])}）
      </li>
      <li>
        政党に所属する知事（届出）：{snap.asOf.slice(0, 4)}年末 {govThen.join('・') || 'なし'} → 現在 {govNow.join('・') || 'なし'}
      </li>
    </ul>
  );
}

/** フッターに置く「比較を表示する」ボタン（隠したあとに戻す場所）。 */
export function CompareToggle() {
  const { on, setOn } = useCompare();
  if (!HISTORY_ENABLED || on) return null;
  return (
    <p>
      <button type="button" className="link-button" onClick={() => setOn(true)}>
        民主党政権期（2009〜2011年）との比較を表示する
      </button>
    </p>
  );
}

// ---------------------------------------------------------------------------

const share = (n: number, d: number) => (d ? (n / d) * 100 : 0);
const signed = (d: number) => (Math.abs(d) < 0.05 ? '±0' : `${d > 0 ? '+' : '−'}${Math.abs(d).toFixed(1)}`);

/** 当時と現在の政党を 1 つの並びにする。民主党は後継政党の前に置き、諸派・無所属は最後。 */
function mergedParties(snap: HistorySnapshot, then: HistoryBody, now: Body): string[] {
  const head = ['自由民主党', DPJ, ...DPJ_SUCCESSORS];
  const tail = ['諸派', '無所属'];
  const order = [...head, ...dataset.parties, ...snap.parties].filter((p, i, a) => a.indexOf(p) === i);
  const used = (p: string) => (then.parties[p] ?? 0) > 0 || (now.parties[p]?.[2] ?? 0) > 0;
  return [...order.filter((p) => !tail.includes(p)), ...tail].filter(used);
}

function toSegments(rows: string[], count: (p: string) => number): Segment[] {
  return rows.map((p) => ({ name: p, short: shortName(p), count: count(p), color: partyColor(p) })).filter((s) => s.count > 0);
}

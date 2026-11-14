import { useState } from 'react';
import GovernorCard from './GovernorCard';
import { bodySegments, dataset, formatDate, kaihaOf, kaihaSegments, partyColor, partyEntries, pct, regionOf, sumBodies } from '../data';
import type { Body, Prefecture } from '../types';
import { CHAMBER_LABEL, chamberOf } from '../chamber';
import Chamber from './Chamber';
import PartyBar from './PartyBar';
import DpjCompare from './DpjCompare';
import { historySegments, pickSnapshot, useCompare, useHistoryData, yearOf } from '../history';

export default function PrefPage({ pref }: { pref: Prefecture }) {
  const national = sumBodies(dataset.prefectures.map((p) => p.assembly));
  const a = pref.assembly;
  const idx = dataset.prefectures.indexOf(pref);
  const prev = dataset.prefectures[idx - 1];
  const next = dataset.prefectures[idx + 1];
  const kaiha = kaihaOf(pref.name);
  const chamber = chamberOf(pref.name);
  const compare = useCompare();
  const hist = useHistoryData(compare.on);
  const snap = compare.on && hist ? pickSnapshot(hist, compare.year) : null;
  const thenBody = snap?.prefectures[pref.name]?.assembly;
  const [picked, setView] = useState<'kaiha' | 'party' | 'then'>(kaiha ? 'kaiha' : 'party');
  // 比較をやめたら「当時」のタブは消えるので、元の表示に戻す
  const view = picked === 'then' && !thenBody ? (kaiha ? 'kaiha' : 'party') : picked;
  const segments =
    view === 'then' && snap && thenBody ? historySegments(snap, thenBody) : view === 'kaiha' && kaiha ? kaihaSegments(kaiha) : bodySegments(a);
  const fixed = view === 'then' && thenBody ? thenBody.fixed : a.fixed;
  const tabs: { key: typeof picked; label: string }[] = [
    ...(kaiha ? [{ key: 'kaiha' as const, label: '会派別' }, { key: 'party' as const, label: '所属党派別' }] : []),
    ...(snap && thenBody
      ? [...(kaiha ? [] : [{ key: 'party' as const, label: '所属党派別（現在）' }]), { key: 'then' as const, label: `${yearOf(snap)}年末（${snap.cabinet}）` }]
      : []),
  ];

  return (
    <>
      <nav className="crumbs">
        <a href="#/">← 全国</a>
        <span className="muted">{regionOf(pref.code)}</span>
      </nav>
      <h2 className="pref-title">{pref.name}議会</h2>

      <section className="card">
        {tabs.length > 1 && (
          <div className="chips tabs" role="tablist" aria-label="表示の切り替え">
            {tabs.map((t) => (
              <button key={t.key} role="tab" aria-selected={view === t.key} className={view === t.key ? 'chip on' : 'chip'} onClick={() => setView(t.key)}>
                {t.label}
              </button>
            ))}
          </div>
        )}
        <Chamber
          chamber={chamber.config}
          segments={segments}
          fixed={fixed}
          emptyLabel={view === 'kaiha' && kaiha ? '欠員・会派なし等' : '欠員'}
          detailed
          label={`${pref.name}議会の${view === 'then' && snap ? `${yearOf(snap)}年末の所属党派` : view === 'kaiha' ? '会派' : '所属党派'}別議席（定数${fixed}）`}
        />
        <PartyBar segments={segments} />
        <p className="muted small">
          {view === 'then' && snap && thenBody ? (
            <>
              出典：総務省（{formatDate(snap.asOf)}現在・{snap.cabinet}）。当時の定数 {thenBody.fixed}・欠員 {thenBody.vacant}。議場の形は現在のものです。
            </>
          ) : view === 'kaiha' && kaiha ? (
            <>
              出典：
              <a href={kaiha.url} target="_blank" rel="noopener noreferrer">
                {pref.name}議会の公式サイト
              </a>
              （{formatDate(kaiha.fetchedAt)}取得{kaiha.stale ? '・最新の取得に失敗したため前回のデータです' : ''}）。定数 {a.fixed} は総務省のデータです。
            </>
          ) : (
            <>
              出典：総務省（{formatDate(dataset.asOf)}現在）。定数 {a.fixed}・現員 {a.total[2]}・欠員 {a.vacant}。
            </>
          )}{' '}
          {view === 'kaiha' && kaiha ? '白抜きの席は、欠員または名簿で会派を確認できなかった議席です。' : '白抜きの席は欠員です。'}
          {chamber.config.desks ? ' 点線の丸は、机はあるものの使われていない席です。' : ''}
          {chamber.isDefault ? (
            ` 議場の形は未確認のため、標準の形（${CHAMBER_LABEL[chamber.config.type]}）で描いています。`
          ) : (
            <>
              {' '}図は{pref.name}議会の議場の形（{CHAMBER_LABEL[chamber.config.type]}）に合わせた図です{chamber.config.seats ? '。列ごと・ブロックごとの席数は議席図のとおりですが、' : '。席の数と並びは模式的なもので、'}どの席にどの会派が座るかは実際と異なります
              {chamber.config.source && (
                <>
                  （
                  <a href={chamber.config.source} target="_blank" rel="noopener noreferrer">
                    {chamber.config.basis ?? '資料'}
                  </a>
                  をもとに設定）
                </>
              )}
              。{chamber.config.note}
            </>
          )}
        </p>
      </section>

      <section className="card">
        <h3>所属党派別の内訳（総務省）</h3>
        <PartyTable body={a} national={national} />
        <p className="muted small">
          ※ 議員が選挙管理委員会に届け出ている所属党派です。議会内の「会派」とは一致しないことがあります。地域政党は「諸派」に含まれます。
        </p>
      </section>

      <DpjCompare pref={pref} />

      <GovernorCard pref={pref} />

      <div className="two-col">
        {pref.cityAssembly && <SubBody title="県内の市区議会（合計）" body={pref.cityAssembly} />}
        {pref.townAssembly && <SubBody title="県内の町村議会（合計）" body={pref.townAssembly} />}
      </div>

      <section className="card links">
        <h3>関連リンク</h3>
        <ul>
          <li>
            <a href={`https://ja.wikipedia.org/wiki/${encodeURIComponent(pref.name + '議会')}`} target="_blank" rel="noopener noreferrer">
              Wikipedia「{pref.name}議会」
            </a>
          </li>
          <li>
            <a
              href={`https://www.google.com/search?q=${encodeURIComponent(pref.name + '議会 会派別 議員名簿')}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {pref.name}議会の会派・議員名簿を検索
            </a>
          </li>
        </ul>
      </section>

      <nav className="pager">
        {prev ? <a href={`#/pref/${encodeURIComponent(prev.name)}`}>← {prev.name}</a> : <span />}
        {next ? <a href={`#/pref/${encodeURIComponent(next.name)}`}>{next.name} →</a> : <span />}
      </nav>
    </>
  );
}

function PartyTable({ body, national }: { body: Body; national: Body }) {
  const t = body.total[2];
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>党派</th>
            <th className="num">議席</th>
            <th className="num">割合</th>
            <th className="num">うち女性</th>
            <th className="num">全国の割合</th>
          </tr>
        </thead>
        <tbody>
          {partyEntries(body).map(([p, c]) => (
            <tr key={p}>
              <td>
                <i className="dot" style={{ background: partyColor(p) }} />
                {p}
              </td>
              <td className="num">{c[2]}</td>
              <td className="num">{pct(c[2], t)}</td>
              <td className="num">{c[1]}</td>
              <td className="num muted">{pct(national.parties[p]?.[2] ?? 0, national.total[2])}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td>合計</td>
            <td className="num">{t}</td>
            <td className="num">100%</td>
            <td className="num">{body.total[1]}</td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function SubBody({ title, body }: { title: string; body: Body }) {
  return (
    <section className="card">
      <h3>{title}</h3>
      <p className="muted small">
        議員 {body.total[2].toLocaleString()} 人（女性 {pct(body.total[1], body.total[2])}）
      </p>
      <PartyBar segments={bodySegments(body)} />
    </section>
  );
}

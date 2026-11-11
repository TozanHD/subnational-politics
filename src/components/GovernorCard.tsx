import { formatDate, governorOf, partyColor } from '../data';
import type { Prefecture } from '../types';

/** 知事: 現在の所属党派（総務省）と、ウィキペディアから取得した経歴・当選時の推薦・支持。 */
export default function GovernorCard({ pref }: { pref: Prefecture }) {
  const g = governorOf(pref.name);
  const official = pref.governor;
  if (official === undefined && !g) return null;

  return (
    <section className="card governor">
      <h3>知事</h3>
      <p className="big">
        {g ? (
          g.url ? (
            <a href={g.url} target="_blank" rel="noopener noreferrer">
              {g.name}
            </a>
          ) : (
            g.name
          )
        ) : official ? (
          '—'
        ) : (
          '欠員'
        )}
        {official?.female && <span className="tag">女性</span>}
        {g?.since && (
          <span className="muted small-inline">
            {formatDate(g.since)}就任{g.term ? `・${g.term}期目` : ''}
          </span>
        )}
      </p>

      <dl className="gov-facts">
        {official && (
          <div>
            <dt>所属党派</dt>
            <dd>
              <i className="dot" style={{ background: partyColor(official.party) }} />
              {official.party}
              <span className="muted">（総務省・選挙管理委員会への届出）</span>
            </dd>
          </div>
        )}
        {g?.partyHistory && (
          <div>
            <dt>政党・派閥の経歴</dt>
            <dd>{g.partyHistory}</dd>
          </div>
        )}
        {g?.election && (
          <div>
            <dt>当選時の推薦・支持</dt>
            <dd>
              {g.election.support || <span className="muted">記載なし</span>}
              <span className="muted">
                （
                <a href={g.election.url} target="_blank" rel="noopener noreferrer">
                  {g.election.title}
                </a>
                ）
              </span>
            </dd>
          </div>
        )}
        {g && g.career.length > 0 && (
          <div>
            <dt>主な前職</dt>
            <dd>{g.career.join('、')}</dd>
          </div>
        )}
      </dl>
      {g && (
        <p className="muted small">
          経歴・推薦・支持の出典：ウィキペディア（
          <a href={g.url ?? 'https://ja.wikipedia.org/'} target="_blank" rel="noopener noreferrer">
            {g.name}
          </a>
          {g.election && (
            <>
              、
              <a href={g.election.url} target="_blank" rel="noopener noreferrer">
                {g.election.title}
              </a>
            </>
          )}
          ）。推薦・支持は直近に当選した知事選挙のものです。
        </p>
      )}
    </section>
  );
}

import { useEffect, useState } from 'react';
import { SOUMU_INDEX_URL, dataset, findPrefecture, formatDate } from './data';
import Home from './components/Home';
import PrefPage from './components/PrefPage';

/** ハッシュ方式のルーティング（静的ホスティングの設定なしで直リンクが動く）。 */
function useRoute(): string {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    // 旧サイトの URL (/prefecture/東京都) からの移行
    const legacy = window.location.pathname.match(/^\/prefecture\/([^/]+)/);
    if (legacy) window.history.replaceState(null, '', `/#/pref/${legacy[1]}`);
    const onChange = () => {
      setHash(window.location.hash);
      window.scrollTo(0, 0);
    };
    onChange();
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return hash;
}

export default function App() {
  const hash = useRoute();
  const m = hash.match(/^#\/pref\/(.+)$/);
  const pref = m ? findPrefecture(decodeURIComponent(m[1])) : undefined;

  useEffect(() => {
    document.title = pref ? `${pref.name}議会の党派構成` : '都道府県議会の党派構成';
  }, [pref]);

  return (
    <div className="page">
      <header className="site-header">
        <a href="#/" className="brand">
          都道府県議会の党派構成
        </a>
        <span className="asof">{formatDate(dataset.asOf)} 現在</span>
      </header>

      <main>
        {m && !pref ? (
          <section className="card">
            <p>「{decodeURIComponent(m[1])}」は見つかりませんでした。</p>
            <a href="#/">全国の一覧へ</a>
          </section>
        ) : pref ? (
          <PrefPage pref={pref} />
        ) : (
          <Home />
        )}
      </main>

      <footer className="site-footer">
        <p>
          出典：総務省「
          <a href={dataset.source.pageUrl || SOUMU_INDEX_URL} target="_blank" rel="noopener noreferrer">
            地方公共団体の議会の議員及び長の所属党派別人員調等
          </a>
          」（{formatDate(dataset.asOf)}現在）
          {dataset.source.xlsxUrl && (
            <>
              ・
              <a href={dataset.source.xlsxUrl} target="_blank" rel="noopener noreferrer">
                元データ (Excel)
              </a>
            </>
          )}
        </p>
        <p className="muted">
          総務省は毎年12月31日時点の集計を翌年3月ごろに公表します。本サイトは公表データを毎週自動で確認し、新しい年次が出ると自動的に更新されます。
        </p>
      </footer>
    </div>
  );
}

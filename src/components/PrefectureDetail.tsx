import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import AssemblyLayout from './AssemblyLayout';
import '../styles/components.css';

// 県ごとの物理的なブロック構成（列数）を定義するヘルパー
// 不明な県は定数に応じて適当なブロックに分割する
const getLayoutConfigForPrefecture = (name: string, totalSeats: number) => {
  switch (name) {
    case '東京都': return { blocks: [6, 8, 6] }; // 124 seats, 20 cols
    case '神奈川県': return { blocks: [5, 6, 5] }; // 105 seats, 16 cols
    case '埼玉県': return { blocks: [4, 6, 4] }; // 93 seats, 14 cols
    case '千葉県': return { blocks: [4, 6, 4] }; // 95 seats, 14 cols
    case '茨城県': return { blocks: [3, 4, 3] }; // 62 seats, 10 cols
    case '栃木県': return { blocks: [3, 4, 3] }; // 50 seats, 10 cols
    case '群馬県': return { blocks: [3, 4, 3] }; // 50 seats, 10 cols
    default:
      // デフォルト: 12列を4ブロックに分けるなど
      return { blocks: [3, 3, 3, 3] };
  }
};

const PrefectureDetail: React.FC = () => {
  const { name } = useParams<{ name: string }>();
  const [prefData, setPrefData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/data.json');
        const jsonData = await res.json();
        const found = jsonData.prefectures.find((p: any) => p.name === name);
        setPrefData(found);
      } catch (err) {
        console.error("Failed to load data", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [name]);

  if (loading) return <div className="loader-container"><div className="spinner"></div></div>;
  if (!prefData) return <div className="error-container"><h2>{name}のデータが見つかりません。</h2><Link to="/">戻る</Link></div>;

  return (
    <div className="app-container">
      <header className="dashboard-header">
        <h1>{prefData.name}議会 詳細ページ</h1>
        <Link to="/" style={{ color: 'var(--brand-primary)', textDecoration: 'none' }}>← ダッシュボードに戻る</Link>
      </header>

      <main className="dashboard-content">
        {/* データソースの明記 */}
        {prefData.sourceUrl && (
          <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '0.75rem 1rem', borderRadius: '8px', color: '#93c5fd', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '1.2rem' }}>🔗</span>
            <div>
              <strong>データ取得元 (公式情報): </strong>
              <a href={prefData.sourceUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'underline' }}>
                {prefData.sourceUrl}
              </a>
              <div style={{ fontSize: '0.8rem', opacity: 0.8, marginTop: '0.25rem' }}>※ 公式サイトの議員名簿・議会時報などの情報を参照し、当サイトにてレイアウト図を生成しています。</div>
            </div>
          </div>
        )}

        <section className="glass-card" style={{ marginBottom: '2rem' }}>
          <h2 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>議場レイアウト (議席配置)</h2>
          <AssemblyLayout 
            parties={prefData.parties} 
            totalSeats={prefData.totalSeats} 
            layoutConfig={getLayoutConfigForPrefecture(prefData.name, prefData.totalSeats)} 
          />
        </section>

        <section className="glass-card">
          <h2 style={{ color: 'var(--text-primary)', marginBottom: '1rem' }}>会派別 議席構成</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', color: 'var(--text-primary)' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--glass-border)', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem' }}>カラー</th>
                <th style={{ padding: '0.75rem' }}>会派名</th>
                <th style={{ padding: '0.75rem' }}>議席数</th>
                <th style={{ padding: '0.75rem' }}>与野党</th>
              </tr>
            </thead>
            <tbody>
              {prefData.parties.map((party: any, index: number) => (
                <tr key={index} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <td style={{ padding: '0.75rem' }}>
                    <div style={{ width: '16px', height: '16px', backgroundColor: party.color, borderRadius: '50%' }}></div>
                  </td>
                  <td style={{ padding: '0.75rem' }}>
                    <div style={{ fontWeight: 'bold' }}>{party.name}</div>
                  </td>
                  <td style={{ padding: '0.75rem', fontWeight: 'bold' }}>{party.total}</td>
                  <td style={{ padding: '0.75rem' }}>{party.isRulingParty ? '与党' : '野党・他'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="glass-card" style={{ marginTop: '2rem' }}>
          <h2 style={{ color: 'var(--text-primary)', marginBottom: '1.5rem' }}>公式情報・選挙結果へのリンク</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            
            {(prefData.seatingChartUrl || prefData.sourceUrl) && (
              <a 
                href={prefData.seatingChartUrl || prefData.sourceUrl} 
                target="_blank" 
                rel="noopener noreferrer" 
                style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.5rem', backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', borderRadius: '8px', color: '#93c5fd', textDecoration: 'none', transition: 'background-color 0.2s' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.1)'}
              >
                <span style={{ fontSize: '1.5rem' }}>📄</span>
                <div>
                  <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>公式 議席図・議員名簿を見る</div>
                  <div style={{ fontSize: '0.85rem', opacity: 0.8, marginTop: '0.2rem' }}>各都道府県議会の公式サイト（別タブで開きます）</div>
                </div>
              </a>
            )}

            {prefData.officialElectionUrl && (
              <a 
                href={prefData.officialElectionUrl} 
                target="_blank" 
                rel="noopener noreferrer" 
                style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.5rem', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '8px', color: '#6ee7b7', textDecoration: 'none', transition: 'background-color 0.2s' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(16, 185, 129, 0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(16, 185, 129, 0.1)'}
              >
                <span style={{ fontSize: '1.5rem' }}>🏛️</span>
                <div>
                  <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>公式 選挙結果を見る</div>
                  <div style={{ fontSize: '0.85rem', opacity: 0.8, marginTop: '0.2rem' }}>都道府県選挙管理委員会の発表資料（別タブで開きます）</div>
                </div>
              </a>
            )}

            {prefData.senkyoComUrl && (
              <a 
                href={prefData.senkyoComUrl} 
                target="_blank" 
                rel="noopener noreferrer" 
                style={{ display: 'flex', alignItems: 'center', gap: '1rem', padding: '1rem 1.5rem', backgroundColor: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '8px', color: '#fcd34d', textDecoration: 'none', transition: 'background-color 0.2s' }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(245, 158, 11, 0.2)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(245, 158, 11, 0.1)'}
              >
                <span style={{ fontSize: '1.5rem' }}>📊</span>
                <div>
                  <div style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>選挙ドットコムで結果を見る</div>
                  <div style={{ fontSize: '0.85rem', opacity: 0.8, marginTop: '0.2rem' }}>go2senkyo.com の詳細な選挙データベース（別タブで開きます）</div>
                </div>
              </a>
            )}

          </div>
        </section>
      </main>
    </div>
  );
};

export default PrefectureDetail;

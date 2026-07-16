import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import PrefectureCard from './PrefectureCard';
import '../styles/components.css';

const Dashboard: React.FC = () => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/data.json');
      if (!res.ok) throw new Error('ローカルデータの取得に失敗しました');
      const jsonData = await res.json();
      setData(jsonData);
    } catch (err: any) {
      setError(err.message || 'データの取得に失敗しました。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="app-container">
      <header className="dashboard-header">
        <h1>JP Subnational Politics</h1>
        <div className="header-actions">
          <button onClick={loadData} disabled={loading}>
            {loading ? '更新中...' : 'Wikidataから再取得'}
          </button>
        </div>
      </header>

      <main className="dashboard-content">
        {loading && (
          <div className="loader-container">
            <div className="spinner"></div>
            <p style={{ color: 'var(--text-secondary)' }}>AIが集計した最新データをロード中...</p>
          </div>
        )}

        {error && !loading && (
          <div className="error-container">
            <h3>エラーが発生しました</h3>
            <p>{error}</p>
            <button onClick={loadData} style={{ marginTop: '1rem', padding: '0.5rem 1rem', cursor: 'pointer' }}>再試行</button>
          </div>
        )}

        {!loading && data && (
          <>
            {/* 情報ソースと注意書き */}
            <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '1rem 1.5rem', borderRadius: '8px', color: '#93c5fd' }}>
              <strong>※ データソースについて（AIエージェント収集）</strong>
              <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.9rem', lineHeight: '1.5' }}>
                本ページのデータは、自律型AIサブエージェント群がWeb上の各都道府県議会・選挙管理委員会の公式サイトや最新情報を自律的にクロールし、抽出し・集計したものです。<br/>
                現在はPoC（概念実証）として<strong>関東地方（1都6県）</strong>のデータを表示しています。
              </p>
            </div>

            {/* 全国サマリー */}
            <section className="glass-card">
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', color: 'var(--text-secondary)' }}>関東地方議会 サマリー（AI集計値）</h2>
              <div className="summary-grid">
                <div className="stat-card">
                  <span className="stat-label">登録確認済み 総議員数</span>
                  <span className="stat-value">{data.totalMembers.toLocaleString()}</span>
                </div>
                
                {(() => {
                  const ldp = data.overallParties['自由民主党']?.total || 0;
                  const komei = data.overallParties['公明党']?.total || 0;
                  const rulingTotal = ldp + komei;
                  const percentage = data.totalMembers > 0 ? ((rulingTotal / data.totalMembers) * 100).toFixed(1) : '0.0';
                  return (
                    <div className="stat-card ruling-highlight">
                      <span className="stat-label">与党会派 (自公) 議席</span>
                      <span className="stat-value">{rulingTotal.toLocaleString()} <span style={{fontSize: '1rem', color: 'var(--text-secondary)'}}>({percentage}%)</span></span>
                    </div>
                  );
                })()}

                <div className="stat-card">
                  <span className="stat-label">最大野党 (立憲民主党)</span>
                  <span className="stat-value">{data.overallParties['立憲民主党']?.total || 0}</span>
                </div>
              </div>
            </section>

            {/* 都道府県ごとの一覧 */}
            <section>
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.2rem', color: 'var(--text-secondary)' }}>各都道府県の構成（登録データのみ）</h2>
              <div className="prefectures-grid">
                {data.prefectures.map((pref: any) => (
                  <Link to={`/prefecture/${pref.name}`} key={pref.name} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <PrefectureCard data={pref} />
                  </Link>
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
};

export default Dashboard;

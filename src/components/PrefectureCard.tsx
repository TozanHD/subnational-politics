import React from 'react';
import { Doughnut } from 'react-chartjs-2';
import { PrefectureData } from '../services/wikidataService';
import { Chart, registerables } from 'chart.js';

Chart.register(...registerables);

interface Props {
  data: PrefectureData;
}

const PrefectureCard: React.FC<Props> = ({ data }) => {
  const chartData = {
    labels: data.parties.map(p => p.name),
    datasets: [
      {
        data: data.parties.map(p => p.total),
        backgroundColor: data.parties.map(p => p.color),
        borderWidth: 2,
        borderColor: '#1e293b', // Match card background slightly for gap effect
        hoverOffset: 4,
      },
    ],
  };

  const options = {
    rotation: -90,
    circumference: 180,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (context: any) => {
            const label = context.label || '';
            const value = context.parsed || 0;
            return `${label}: ${value}議席`;
          }
        }
      }
    },
    maintainAspectRatio: false,
    animation: { duration: 1200, easing: 'easeOutQuart' as const },
    cutout: '70%',
  };

  const rulingSeats = data.parties.filter(p => p.isRulingParty).reduce((acc, curr) => acc + curr.total, 0);
  const oppositionSeats = data.totalSeats - rulingSeats;

  return (
    <div className="glass-card pref-card">
      <div className="pref-title">{data.name}</div>
      
      <div className="pref-chart-container">
        <Doughnut data={chartData} options={options} />
        <div className="pref-total-seats">
          {data.totalSeats} 議席
        </div>
      </div>

      <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', paddingBottom: '0.5rem', borderBottom: '1px solid var(--glass-border)' }}>
          <span><span style={{ color: 'var(--ruling-party-border)' }}>●</span> 与党 (自公): {rulingSeats}</span>
          <span>野党・他: {oppositionSeats}</span>
        </div>
        
        {data.sourceUrl && (
          <div style={{ marginBottom: '0.5rem', textAlign: 'center' }}>
            <a 
              href={data.sourceUrl} 
              target="_blank" 
              rel="noopener noreferrer" 
              style={{ color: '#60a5fa', textDecoration: 'none', fontSize: '0.8rem' }}
              onClick={(e) => e.stopPropagation()}
            >
              🔗 公式情報を見る
            </a>
          </div>
        )}

        {/* 将来拡張用のプレースホルダー */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', opacity: 0.6, fontSize: '0.75rem' }}>
          <div>👤 知事: (データ準備中)</div>
          <div>🏛️ 選出・国会議員: (データ準備中)</div>
          <div>🗺️ 選挙区割り: (データ準備中)</div>
        </div>
      </div>
    </div>
  );
};

export default PrefectureCard;

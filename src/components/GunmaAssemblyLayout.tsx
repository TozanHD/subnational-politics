import React from 'react';

interface Party {
  name: string;
  total: number;
  color: string;
  isRulingParty: boolean;
}

interface Props {
  parties: Party[];
  totalSeats: number;
}

const GunmaAssemblyLayout: React.FC<Props> = ({ parties, totalSeats }) => {
  // Sort parties: non-ruling first (left side), then ruling (right side)
  // Usually, smaller opposition parties sit on the far left, largest ruling on the far right.
  const sortedParties = [...parties].sort((a, b) => {
    if (a.isRulingParty && !b.isRulingParty) return 1;
    if (!a.isRulingParty && b.isRulingParty) return -1;
    return a.total - b.total; // smaller first within the group
  });

  // Generate individual seat array
  const seats: { id: number; color: string; partyName: string }[] = [];
  let currentSeat = 1;

  sortedParties.forEach((party) => {
    for (let i = 0; i < party.total; i++) {
      seats.push({
        id: currentSeat++,
        color: party.color,
        partyName: party.name,
      });
    }
  });

  // Gunma layout (PoC): 50 seats. 
  // We'll render a rectangular block layout common in Japanese local assemblies.
  // 5 rows x 10 columns. Divided into 3 blocks: Left (3), Center (4), Right (3).
  // Total 10 seats per row.
  
  const rows = 5;
  const cols = 10;
  const seatRadius = 12;
  const gap = 10;
  const blockGap = 20; // extra gap between blocks

  const getSeatPosition = (index: number) => {
    const row = Math.floor(index / cols);
    const col = index % cols;
    
    // Reverse row so front row is at the bottom (or top depending on view). 
    // Usually speaker is at the top, front row is below it.
    const y = 80 + row * (seatRadius * 2 + gap);
    
    let x = 50 + col * (seatRadius * 2 + gap);
    // Add block gaps
    if (col >= 3) x += blockGap;
    if (col >= 7) x += blockGap;

    return { x, y };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '2rem 0' }}>
      <svg width="600" height="300" viewBox="0 0 600 300" style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
        {/* 議長席 (Speaker's Seat) */}
        <rect x="250" y="20" width="100" height="30" fill="#334155" rx="4" />
        <text x="300" y="40" fill="#94a3b8" fontSize="14" textAnchor="middle" fontWeight="bold">議長席</text>

        {/* 座席 */}
        {seats.map((seat, i) => {
          const { x, y } = getSeatPosition(i);
          return (
            <g key={seat.id} className="seat-group">
              <title>{`議席番号: ${seat.id}\n会派: ${seat.partyName}`}</title>
              <circle 
                cx={x} 
                cy={y} 
                r={seatRadius} 
                fill={seat.color}
                stroke="#1e293b"
                strokeWidth="2"
                style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
                onMouseEnter={(e) => {
                  (e.target as SVGCircleElement).setAttribute('stroke', '#fff');
                }}
                onMouseLeave={(e) => {
                  (e.target as SVGCircleElement).setAttribute('stroke', '#1e293b');
                }}
              />
              <text x={x} y={y + 4} fill="#fff" fontSize="10" textAnchor="middle" style={{ pointerEvents: 'none' }}>
                {seat.id}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        ※ マウスオーバーで詳細表示。最前列左から順に議席番号を割り当てたPoCレイアウトです。
      </div>
    </div>
  );
};

export default GunmaAssemblyLayout;

import React from 'react';

interface Party {
  name: string;
  total: number;
  color: string;
  isRulingParty: boolean;
}

interface LayoutConfig {
  blocks: number[]; // e.g. [3, 4, 3] means 3 columns, gap, 4 columns, gap, 3 columns
  seatRadius?: number;
  gap?: number;
  blockGap?: number;
}

interface Props {
  parties: Party[];
  totalSeats: number;
  layoutConfig: LayoutConfig;
}

const AssemblyLayout: React.FC<Props> = ({ parties, totalSeats, layoutConfig }) => {
  const { blocks, seatRadius = 12, gap = 10, blockGap = 20 } = layoutConfig;
  const cols = blocks.reduce((a, b) => a + b, 0);

  // Sort parties: non-ruling first (left side), then ruling (right side)
  const sortedParties = [...parties].sort((a, b) => {
    if (a.isRulingParty && !b.isRulingParty) return 1;
    if (!a.isRulingParty && b.isRulingParty) return -1;
    return a.total - b.total;
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

  const getSeatPosition = (index: number) => {
    const row = Math.floor(index / cols);
    const col = index % cols;
    
    const y = 100 + row * (seatRadius * 2 + gap);
    
    let x = 50 + col * (seatRadius * 2 + gap);
    // Add block gaps
    let currentCols = 0;
    for (let i = 0; i < blocks.length - 1; i++) {
      currentCols += blocks[i];
      if (col >= currentCols) {
        x += blockGap;
      }
    }
    return { x, y };
  };

  const maxRows = Math.ceil(totalSeats / cols);
  const svgHeight = 150 + maxRows * (seatRadius * 2 + gap);
  
  // Calculate SVG Width dynamically based on blocks
  const totalBlockGaps = (blocks.length - 1) * blockGap;
  const svgWidth = 100 + (cols * (seatRadius * 2 + gap)) + totalBlockGaps;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', margin: '2rem 0', overflowX: 'auto', width: '100%' }}>
      <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`} style={{ background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
        {/* 議長席 */}
        <rect x={(svgWidth / 2) - 50} y="30" width="100" height="30" fill="#334155" rx="4" />
        <text x={svgWidth / 2} y="50" fill="#94a3b8" fontSize="14" textAnchor="middle" fontWeight="bold">議長席</text>

        {/* 演壇など */}
        <rect x={(svgWidth / 2) - 30} y="70" width="60" height="15" fill="#1e293b" rx="2" />

        {/* 座席 */}
        {seats.map((seat, i) => {
          if (i >= totalSeats) return null; // Safety
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
    </div>
  );
};

export default AssemblyLayout;

import raw from './data/chambers.json';

export type ChamberType = 'hemicycle' | 'fan' | 'classroom' | 'facing' | 'horseshoe';

export interface ChamberConfig {
  type: ChamberType;
  /** 列の数（対面型では片側の奥行き） */
  rows?: number;
  /** 扇形の開き角度（度） */
  span?: number;
  /** 教室型: 通路で区切られた各ブロックの横の席数 */
  blocks?: number[];
  /** 形を判断した根拠 */
  basis?: string;
  /** 補足（県別ページに表示） */
  note?: string;
  /** 参照した県議会サイトのページ */
  source?: string;
}

export const CHAMBER_LABEL: Record<ChamberType, string> = {
  hemicycle: '半円形',
  fan: '扇形',
  classroom: '教室型',
  facing: '対面型',
  horseshoe: '馬蹄形',
};

const TYPES = Object.keys(CHAMBER_LABEL);
const cfg = raw as unknown as { default: ChamberConfig; prefectures: Record<string, ChamberConfig> };

/** 都道府県の議場設定。設定が無い・type が不正な場合は標準の形にする。 */
export function chamberOf(pref: string): { config: ChamberConfig; isDefault: boolean } {
  const c = cfg.prefectures[pref];
  if (c && TYPES.includes(c.type)) return { config: c, isDefault: false };
  return { config: TYPES.includes(cfg.default?.type) ? cfg.default : { type: 'hemicycle' }, isDefault: true };
}

export interface Point {
  x: number;
  y: number;
}

export interface ChamberLayout {
  /** 塗る順（会派の並び順）に並んだ席。y は下向きが正。 */
  seats: Point[];
  /** 席の半径 */
  r: number;
  /** 議長席の位置と向き（横長か縦長か）。中央に人数を書く形では省略。 */
  podium?: Point & { vertical?: boolean };
  /** 人数を書く位置。center: 席に囲まれた中心 / below: 図の下 */
  label: Point & { place: 'center' | 'below' };
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/**
 * 同心の弧に席を並べる（半円形・扇形・馬蹄形の共通処理）。
 * 議長席は図の上側（弧の中心）に置き、席がそちらを向く。leg は弧の両端から議長席の側（上）へ伸ばす直線部分の長さ。
 */
function arcs(n: number, spanDeg: number, leg: number, rowsOpt?: number): ChamberLayout {
  const span = (clamp(spanDeg, 40, 180) * Math.PI) / 180;
  const density = 3.2 * (span / Math.PI) + leg * 2.2;
  const rows = clamp(Math.round(rowsOpt ?? Math.ceil(Math.sqrt(n / density))), 2, 10);
  const inner = rows <= 2 ? 0.6 : 0.47;
  const radii = Array.from({ length: rows }, (_, i) => inner + ((1 - inner) * i) / (rows - 1));
  const lengths = radii.map((rad) => rad * span + 2 * leg);
  const sum = lengths.reduce((a, b) => a + b, 0);
  const counts = lengths.map((l) => Math.max(1, Math.floor((n * l) / sum)));
  // 端数は外側の列から順に配る
  for (let i = rows - 1, rest = n - counts.reduce((a, b) => a + b, 0); rest > 0; i = (i - 1 + rows) % rows, rest--) counts[i]++;
  for (let i = 0, over = counts.reduce((a, b) => a + b, 0) - n; over > 0; i = (i + 1) % rows) {
    if (counts[i] > 1) {
      counts[i]--;
      over--;
    }
  }
  const a0 = Math.PI / 2 + span / 2; // 左端の角度
  const pts: (Point & { t: number; rad: number })[] = [];
  let spacing = (1 - inner) / Math.max(1, rows - 1);
  radii.forEach((rad, i) => {
    const k = counts[i];
    const len = lengths[i];
    if (k > 1) spacing = Math.min(spacing, len / (k - 1));
    for (let j = 0; j < k; j++) {
      const s = k === 1 ? len / 2 : (j * len) / (k - 1); // 左端からの道のり
      let x: number, y: number;
      if (s < leg) {
        x = rad * Math.cos(a0);
        y = rad * Math.sin(a0) - (leg - s);
      } else if (s <= leg + rad * span) {
        const a = a0 - (s - leg) / rad;
        x = rad * Math.cos(a);
        y = rad * Math.sin(a);
      } else {
        x = rad * Math.cos(a0 - span);
        y = rad * Math.sin(a0 - span) - (s - leg - rad * span);
      }
      pts.push({ x, y, t: s / len, rad });
    }
  });
  // 左から右へ、同じ位置なら外側から
  pts.sort((p, q) => p.t - q.t || q.rad - p.rad);
  return {
    seats: pts,
    r: Math.min(0.08, spacing * 0.42),
    podium: { x: 0, y: -leg - 0.08 },
    label: { x: 0, y: 0.2, place: 'center' },
  };
}

/** 教室型: 議長席（上）に向かって横に並ぶ。会派は左から縦の帯になる。 */
function classroom(n: number, c: ChamberConfig): ChamberLayout {
  let blocks = c.blocks?.filter((b) => b > 0);
  let cols: number;
  if (blocks?.length) {
    cols = blocks.reduce((a, b) => a + b, 0);
  } else {
    cols = c.rows ? Math.ceil(n / c.rows) : Math.max(3, Math.ceil(Math.sqrt(2 * n)));
    const side = Math.max(1, Math.round(cols * 0.3));
    blocks = cols >= 6 ? [side, cols - 2 * side, side] : [cols];
  }
  const rows = Math.max(1, Math.ceil(n / cols));
  const aisle = 0.7;
  const xs: number[] = [];
  let x = 0;
  blocks.forEach((b, i) => {
    for (let j = 0; j < b; j++) xs.push(x++);
    if (i < blocks!.length - 1) x += aisle;
  });
  const width = xs[xs.length - 1];
  const seats: Point[] = [];
  // 列ごと（左から）に前から後ろへ。端数は各列の後ろを空ける。
  const perCol = xs.map((_, i) => Math.floor(n / cols) + (i < n % cols ? 1 : 0));
  xs.forEach((cx, i) => {
    for (let j = 0; j < perCol[i]; j++) seats.push({ x: cx - width / 2, y: j });
  });
  return { seats, r: 0.4, podium: { x: 0, y: -1.5 }, label: { x: 0, y: rows + 0.5, place: 'below' } };
}

/** 対面型: 中央の通路をはさんで 2 つの議席群が向かい合う。議長席は左端。 */
function facing(n: number, c: ChamberConfig): ChamberLayout {
  const depth = clamp(Math.round(c.rows ?? Math.sqrt(n / 8) - 0.4), 1, 6);
  const top = Math.ceil(n / 2);
  const len = Math.max(1, Math.ceil(top / depth));
  const aisle = 1.6;
  const seats: Point[] = [];
  for (const [count, dir] of [[top, -1], [n - top, 1]] as const) {
    // 議長席に近い側から、通路側 → 奥へ
    for (let i = 0; i < count; i++) {
      const col = Math.floor(i / depth);
      const d = i % depth;
      seats.push({ x: col, y: dir * (aisle / 2 + d) });
    }
  }
  return {
    seats: seats.map((s) => ({ x: s.x - (len - 1) / 2, y: s.y })),
    r: 0.4,
    podium: { x: -(len - 1) / 2 - 1.6, y: 0, vertical: true },
    label: { x: 0, y: aisle / 2 + depth + 0.3, place: 'below' },
  };
}

export function chamberLayout(n: number, c: ChamberConfig): ChamberLayout {
  if (n <= 0) return { seats: [], r: 0.05, label: { x: 0, y: 0, place: 'center' } };
  switch (c.type) {
    case 'fan':
      return arcs(n, c.span ?? 110, 0, c.rows);
    case 'horseshoe':
      return arcs(n, 180, 0.45, c.rows);
    case 'classroom':
      return classroom(n, c);
    case 'facing':
      return facing(n, c);
    default:
      return arcs(n, 180, 0, c.rows);
  }
}

import raw from './data/chambers.json';

export type ChamberType = 'hemicycle' | 'fan' | 'classroom' | 'facing' | 'horseshoe';

export interface ChamberConfig {
  type: ChamberType;
  /** 列の数（対面型では片側の奥行き） */
  rows?: number;
  /** 扇形の開き角度（度） */
  span?: number;
  /** 教室型: 通路で区切られた各ブロックの横の席数。半円形・扇形・馬蹄形: 放射状の通路で区切った各ブロックの幅の比 */
  blocks?: number[];
  /**
   * 議席図どおりの席の並び。前の列から順に、各列の「ブロックごとの席数」を書く（議長席を上にして左のブロックから）。
   * 例: [[4,7,4],[6,8,6]] = 1 列目は左 4・中央 7・右 4 席、2 列目は 6・8・6 席。
   * 指定すると rows / blocks より優先する。span を併せて指定すると列が議長席を囲む弧になる。
   */
  seats?: number[][];
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
 * blocks を指定すると、放射状の通路で席をブロックに分ける（値は各ブロックの幅の比）。
 * 席の間隔はすべての列・ブロックで同じにし、通路の幅も内側の列から外側の列まで一定にする。
 */
function arcs(n: number, spanDeg: number, leg: number, rowsOpt?: number, blocksOpt?: number[]): ChamberLayout {
  const span = (clamp(spanDeg, 40, 180) * Math.PI) / 180;
  const density = 3.2 * (span / Math.PI) + leg * 2.2;
  const rows = clamp(Math.round(rowsOpt ?? Math.ceil(Math.sqrt(n / density))), 2, 10);
  const raw = (blocksOpt ?? []).filter((w) => w > 0);
  const weights = raw.length > 1 ? raw : [1];
  const nb = weights.length;
  const wsum = weights.reduce((a, b) => a + b, 0);
  const solve = (inner: number) => {
    const radii = Array.from({ length: rows }, (_, i) => inner + ((1 - inner) * i) / (rows - 1));
    const lengths = radii.map((rad) => rad * span + 2 * leg);
    // 通路の幅は席の間隔の 0.9 倍（席 1 つ分ほどの隙間に見える）。どの列でも同じ幅なので放射状にまっすぐ通る
    const segs = (pitch: number) =>
      lengths.map((l) => weights.map((w) => (Math.max(0, l - (nb - 1) * 0.9 * pitch) * w) / wsum));
    const capacity = (pitch: number) =>
      segs(pitch).reduce((a, row) => a + row.reduce((b, seg) => b + Math.floor(seg / pitch + 1e-9), 0), 0);
    // 全員が座れる最大の席の間隔を二分探索で求める（全列・全ブロックで同じ間隔）
    let lo = 1e-4;
    let hi = 2;
    for (let it = 0; it < 60; it++) {
      const mid = (lo + hi) / 2;
      if (capacity(mid) >= n) lo = mid;
      else hi = mid;
    }
    const pitch = lo;
    const seg = segs(pitch);
    const per = seg.map((row) => row.map((s) => Math.floor(s / pitch + 1e-9)));
    // 座れる席が余った分は、取り除いても間隔が最も広がらないブロックから 1 席ずつ減らす
    for (let excess = per.flat().reduce((a, b) => a + b, 0) - n; excess > 0; excess--) {
      let bi = -1;
      let bb = -1;
      let bestGap = Infinity;
      per.forEach((row, i) =>
        row.forEach((m, b) => {
          if (m > 1 && seg[i][b] / (m - 1) < bestGap) {
            bestGap = seg[i][b] / (m - 1);
            bi = i;
            bb = b;
          }
        }),
      );
      if (bi < 0) break;
      per[bi][bb]--;
    }
    return { inner, radii, lengths, pitch, seg, per };
  };
  // 列の間隔が席の間隔に比べて開きすぎるとまばらに見えるので、内側の半径を広げて列を詰める
  let sol = solve(rows <= 2 ? 0.6 : 0.47);
  for (let it = 0; it < 4; it++) {
    const radial = (1 - sol.inner) / Math.max(1, rows - 1);
    if (radial <= 1.5 * sol.pitch) break;
    sol = solve(Math.min(0.85, 1 - 1.5 * sol.pitch * (rows - 1)));
  }
  const { inner, radii, lengths, pitch, seg, per } = sol;
  const a0 = Math.PI / 2 + span / 2; // 左端の角度
  /** 左端からの道のり s の位置（左の直線部 → 弧 → 右の直線部） */
  const at = (rad: number, s: number): Point => {
    if (s < leg) return { x: rad * Math.cos(a0), y: rad * Math.sin(a0) - (leg - s) };
    if (s <= leg + rad * span) {
      const a = a0 - (s - leg) / rad;
      return { x: rad * Math.cos(a), y: rad * Math.sin(a) };
    }
    return { x: rad * Math.cos(a0 - span), y: rad * Math.sin(a0 - span) - (s - leg - rad * span) };
  };
  const pts: (Point & { t: number; rad: number })[] = [];
  let spacing = (1 - inner) / Math.max(1, rows - 1);
  radii.forEach((rad, i) => {
    let start = 0;
    weights.forEach((_, b) => {
      const m = per[i][b];
      const w = seg[i][b];
      if (m > 0) spacing = Math.min(spacing, w / m);
      for (let j = 0; j < m; j++) {
        const s = start + ((j + 0.5) * w) / m;
        pts.push({ ...at(rad, s), t: s / lengths[i], rad });
      }
      start += w + 0.9 * pitch;
    });
  });
  // 左から右へ、同じ位置なら外側から
  pts.sort((p, q) => p.t - q.t || q.rad - p.rad);
  return {
    seats: pts,
    r: Math.min(0.08, spacing * 0.42),
    // 議長席は最も上の席のすぐ上に置く。人数は、中央に空きがある半円形・馬蹄形では中央、細い扇形では図の下
    podium: { x: 0, y: Math.min(...pts.map((p) => p.y)) - 0.12 },
    label:
      spanDeg >= 170
        ? { x: 0, y: 0.2, place: 'center' }
        : { x: 0, y: Math.max(...pts.map((p) => p.y)) + 0.12, place: 'below' },
  };
}

/**
 * 議席図どおりの並び。各列・各ブロックの席数をそのまま置く。
 * 左側のブロックは右（通路側）に、右側のブロックは左に、中央のブロックは中央に寄せる。
 * 席数が定数より少ないときは最後列に足す（定数が増えても図が欠けないように）。
 */
function grid(n: number, c: ChamberConfig): ChamberLayout {
  const rowsIn = (c.seats ?? []).map((r) => r.map((v) => Math.max(0, Math.round(v))));
  const nb = Math.max(...rowsIn.map((r) => r.length));
  const rows = rowsIn.map((r) => Array.from({ length: nb }, (_, b) => r[b] ?? 0));
  let total = rows.flat().reduce((a, b) => a + b, 0);
  for (let b = Math.floor((nb - 1) / 2); total < n; total++) rows[rows.length - 1][b]++;
  const widths = Array.from({ length: nb }, (_, b) => Math.max(...rows.map((r) => r[b])));
  const aisle = 0.8;
  const starts: number[] = [];
  let x = 0;
  widths.forEach((w, b) => {
    starts.push(x);
    x += w + (b < nb - 1 ? aisle : 0);
  });
  const W = x - 1; // 左端の席の中心から右端の席の中心まで
  const pitchY = 1.12;
  const spanRad = c.span ? (clamp(c.span, 10, 170) * Math.PI) / 180 : 0;
  const rBack = spanRad ? Math.max(W / spanRad, (rows.length - 1) * pitchY + 3) : 0;
  const pts: (Point & { fx: number })[] = [];
  rows.forEach((r, i) => {
    r.forEach((m, b) => {
      const mid = (nb - 1) / 2;
      const off = b < mid ? widths[b] - m : b > mid ? 0 : (widths[b] - m) / 2;
      for (let j = 0; j < m; j++) {
        const fx = starts[b] + off + j - W / 2;
        if (!spanRad) {
          pts.push({ x: fx, y: i * pitchY, fx });
        } else {
          // 議長席の側を中心とする弧に曲げる（席の間隔と通路の幅は保つ）
          const rad = rBack - (rows.length - 1 - i) * pitchY;
          const a = fx / rad;
          pts.push({ x: rad * Math.sin(a), y: rad * Math.cos(a) - (rBack - (rows.length - 1) * pitchY), fx });
        }
      }
    });
  });
  // 会派は左から順に帯になるように塗る
  pts.sort((p, q) => p.fx - q.fx || p.y - q.y);
  const minY = Math.min(...pts.map((p) => p.y));
  const maxY = Math.max(...pts.map((p) => p.y));
  return { seats: pts, r: 0.4, podium: { x: 0, y: minY - 1.5 }, label: { x: 0, y: maxY + 0.9, place: 'below' } };
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
  if (c.seats?.length && c.seats.some((r) => r.some((v) => v > 0))) return grid(n, c);
  switch (c.type) {
    case 'fan':
      return arcs(n, c.span ?? 110, 0, c.rows, c.blocks);
    case 'horseshoe':
      return arcs(n, 180, 0.45, c.rows, c.blocks);
    case 'classroom':
      return classroom(n, c);
    case 'facing':
      return facing(n, c);
    default:
      return arcs(n, 180, 0, c.rows, c.blocks);
  }
}

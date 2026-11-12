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
  /** seats と同じ形で、使われていない席も含めた机の数。差の分は「使われていない席」として薄く描く */
  desks?: number[][];
  /** 教室型: 両脇のブロックを議長席のほうへ傾ける角度（度） */
  splay?: number;
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
  /** 使われていない席（机はあるが議員の席ではない） */
  ghosts?: Point[];
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
 * 両脇のブロックを議長席のほうへ傾ける。ブロック全体を回すのではなく、列ごとに通路側の端を軸に傾ける。
 * 外側の端が議長席に近づく一方、通路側の端はまっすぐ後ろへそろうので、後ろの列が中央から離れていかない
 * （実際の議席図と同じ、平行四辺形の並びになる）。
 */
function splaySides<T extends Point>(pts: (T & { b: number })[], nb: number, deg: number | undefined, innerEdge: (b: number) => number): void {
  const th = (clamp(deg ?? 0, 0, 40) * Math.PI) / 180;
  if (!th || nb < 3) return;
  for (const p of pts) {
    if (p.b !== 0 && p.b !== nb - 1) continue;
    const sign = p.b === 0 ? 1 : -1; // 左のブロックは左端が、右のブロックは右端が議長席に近づく
    const px = innerEdge(p.b);
    const dx = p.x - px;
    p.x = px + dx * Math.cos(th);
    p.y = p.y + sign * dx * Math.sin(th);
  }
}

/**
 * 議席図どおりの並び。各列・各ブロックの席数をそのまま置く。
 * 左側のブロックは右（通路側）に、右側のブロックは左に、中央のブロックは中央に寄せる。
 * 席数が定数より少ないときは最後列に足す（定数が増えても図が欠けないように）。
 */
function grid(n: number, c: ChamberConfig): ChamberLayout {
  const norm = (rs: number[][] | undefined) => (rs ?? []).map((r) => r.map((v) => Math.max(0, Math.round(v))));
  const rowsIn = norm(c.seats);
  const nb = Math.max(...rowsIn.map((r) => r.length));
  const rows = rowsIn.map((r) => Array.from({ length: nb }, (_, b) => r[b] ?? 0));
  let total = rows.flat().reduce((a, b) => a + b, 0);
  for (let b = Math.floor((nb - 1) / 2); total < n; total++) rows[rows.length - 1][b]++;
  // 机の数（使われていない席を含む）。指定が無ければ使う席と同じ
  const desksIn = norm(c.desks);
  const desks = rows.map((r, i) => r.map((m, b) => Math.max(m, desksIn[i]?.[b] ?? 0)));
  const mid = (nb - 1) / 2;
  const aisle = 0.8;
  const pitchY = 1.12;
  const pts: (Point & { fx: number; b: number })[] = [];
  const ghosts: Point[] = [];
  /** ブロック内の席の横位置（0 始まり）。両脇のブロックは通路側から、中央は真ん中から使う。 */
  const slots = (i: number, b: number, width: number): { off: number; used: boolean }[] => {
    const d = desks[i][b];
    const m = rows[i][b];
    const start = b < mid ? width - d : b > mid ? 0 : (width - d) / 2;
    const usedFrom = b < mid ? d - m : b > mid ? 0 : Math.floor((d - m) / 2);
    return Array.from({ length: d }, (_, j) => ({ off: start + j, used: j >= usedFrom && j < usedFrom + m }));
  };
  const spanRad = c.span ? (clamp(c.span, 10, 170) * Math.PI) / 180 : 0;
  if (!spanRad) {
    const widths = Array.from({ length: nb }, (_, b) => Math.max(...desks.map((r) => r[b])));
    const starts: number[] = [];
    let x = 0;
    widths.forEach((w, b) => {
      starts.push(x);
      x += w + (b < nb - 1 ? aisle : 0);
    });
    const W = x - 1; // 左端の席の中心から右端の席の中心まで
    const all: (Point & { fx: number; b: number; used: boolean })[] = [];
    rows.forEach((_, i) => {
      for (let b = 0; b < nb; b++) {
        for (const s of slots(i, b, widths[b])) {
          const fx = starts[b] + s.off - W / 2;
          all.push({ x: fx, y: i * pitchY, fx, b, used: s.used });
        }
      }
    });
    splaySides(all, nb, c.splay, (b) => (b === 0 ? starts[0] + widths[0] - 0.5 : starts[nb - 1] - 0.5) - W / 2);
    for (const p of all) (p.used ? pts : ghosts).push(p);
  } else {
    // 扇形: 列は議長席の側を中心とする弧、通路は放射状。各ブロックは決まった角度の範囲を占め、
    // 席はその範囲の中央に同じ間隔で並ぶ（後ろの列ほどブロックが広がり、両脇は外へずれる）。
    const layoutFor = (r0: number) => {
      const rad = rows.map((_, i) => r0 + i * pitchY);
      const ang = Array.from({ length: nb }, (_, b) => Math.max(...desks.map((r, i) => r[b] / rad[i])));
      const gap = aisle / (r0 + ((rows.length - 1) * pitchY) / 2);
      return { rad, ang, gap, total: ang.reduce((a, v) => a + v, 0) + gap * (nb - 1) };
    };
    let lo = 1;
    let hi = 400;
    for (let it = 0; it < 60; it++) {
      const m = (lo + hi) / 2;
      if (layoutFor(m).total > spanRad) lo = m;
      else hi = m;
    }
    const { rad, ang, gap, total: tot } = layoutFor(hi);
    const centers: number[] = [];
    let a = -tot / 2;
    ang.forEach((w) => {
      centers.push(a + w / 2);
      a += w + gap;
    });
    rows.forEach((_, i) => {
      for (let b = 0; b < nb; b++) {
        const d = desks[i][b];
        for (const s of slots(i, b, d)) {
          const t = centers[b] + (s.off - (d - 1) / 2) / rad[i];
          const p = { x: rad[i] * Math.sin(t), y: rad[i] * Math.cos(t) - rad[0], fx: t, b };
          if (s.used) pts.push(p);
          else ghosts.push(p);
        }
      }
    });
  }
  // 会派は左から順に帯になるように塗る
  pts.sort((p, q) => p.fx - q.fx || p.y - q.y);
  const allY = [...pts, ...ghosts].map((p) => p.y);
  const minY = Math.min(...allY);
  const maxY = Math.max(...allY);
  return { seats: pts, ghosts, r: 0.4, podium: { x: 0, y: minY - 1.5 }, label: { x: 0, y: maxY + 0.9, place: 'below' } };
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
  const aisle = 0.7;
  const xs: number[] = [];
  const blockOf: number[] = [];
  const edges: [number, number][] = []; // 各ブロックの左端・右端（席の中心）
  let x = 0;
  blocks.forEach((b, i) => {
    edges.push([x, x + b - 1]);
    for (let j = 0; j < b; j++) {
      xs.push(x++);
      blockOf.push(i);
    }
    if (i < blocks!.length - 1) x += aisle;
  });
  const width = xs[xs.length - 1];
  const seats: (Point & { b: number })[] = [];
  // 列ごと（左から）に前から後ろへ。端数は各列の後ろを空ける。
  const perCol = xs.map((_, i) => Math.floor(n / cols) + (i < n % cols ? 1 : 0));
  xs.forEach((cx, i) => {
    for (let j = 0; j < perCol[i]; j++) seats.push({ x: cx - width / 2, y: j, b: blockOf[i] });
  });
  const nb = blocks.length;
  splaySides(seats, nb, c.splay, (bi) => (bi === 0 ? edges[0][1] + 0.5 : edges[nb - 1][0] - 0.5) - width / 2);
  const minY = Math.min(...seats.map((p) => p.y));
  const maxY = Math.max(...seats.map((p) => p.y));
  return { seats, r: 0.4, podium: { x: 0, y: minY - 1.5 }, label: { x: 0, y: maxY + 1.5, place: 'below' } };
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

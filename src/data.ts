import raw from './data/latest.json';
import type { Body, Count, Dataset, Prefecture } from './types';

export const dataset = raw as unknown as Dataset;

export const SOUMU_INDEX_URL = 'https://www.soumu.go.jp/senkyo/senkyo_s/data/';

const KNOWN_COLORS: Record<string, string> = {
  自由民主党: '#d7033a',
  立憲民主党: '#1d4f9c',
  日本維新の会: '#3aa63a',
  公明党: '#f06a95',
  国民民主党: '#f2b200',
  れいわ新選組: '#d6007a',
  日本共産党: '#7a57d1',
  参政党: '#ec6c00',
  日本保守党: '#1c8bd6',
  社会民主党: '#14a3c7',
  みんなでつくる党: '#4fb3a4',
  諸派: '#a5876c',
  無所属: '#9aa1ab',
};

/** 既知の政党は固定色、未知の政党（新党など）は名前から決まる色を自動で割り当てる。 */
export function partyColor(name: string): string {
  const known = KNOWN_COLORS[name];
  if (known) return known;
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.codePointAt(0)!) >>> 0;
  return `hsl(${h % 360} 55% 48%)`;
}

/** 政党略称（表示幅が狭いところ用）。未知の政党は先頭4文字。 */
const SHORT: Record<string, string> = {
  自由民主党: '自民',
  立憲民主党: '立憲',
  日本維新の会: '維新',
  公明党: '公明',
  国民民主党: '国民',
  れいわ新選組: 'れいわ',
  日本共産党: '共産',
  参政党: '参政',
  日本保守党: '保守',
  社会民主党: '社民',
  みんなでつくる党: 'みんつく',
};
export const shortName = (name: string) => SHORT[name] ?? (name.length > 4 ? name.slice(0, 4) : name);

/** 政党を総務省の掲載順に並べ、0 人を除いたもの。 */
export function partyEntries(body: Body): [string, Count][] {
  const order = dataset.parties;
  return Object.entries(body.parties)
    .filter(([, c]) => c[2] > 0)
    .sort(([a], [b]) => idx(order, a) - idx(order, b));
}

const idx = (arr: string[], v: string) => {
  const i = arr.indexOf(v);
  return i === -1 ? arr.length : i;
};

export function sumBodies(bodies: Body[]): Body {
  const out: Body = { fixed: 0, vacant: 0, total: [0, 0, 0], parties: {} };
  for (const b of bodies) {
    out.fixed += b.fixed;
    out.vacant += b.vacant;
    for (let i = 0; i < 3; i++) out.total[i] += b.total[i];
    for (const [p, c] of Object.entries(b.parties)) {
      const t = (out.parties[p] ??= [0, 0, 0]);
      for (let i = 0; i < 3; i++) t[i] += c[i];
    }
  }
  return out;
}

export function largestParty(body: Body): [string, Count] | null {
  let best: [string, Count] | null = null;
  for (const e of partyEntries(body)) if (!best || e[1][2] > best[1][2]) best = e;
  return best;
}

export const pct = (n: number, d: number, digits = 1) => (d > 0 ? `${((n / d) * 100).toFixed(digits)}%` : '—');

export function formatDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return `${y}年${m}月${d}日`;
}

export function findPrefecture(name: string): Prefecture | undefined {
  return dataset.prefectures.find((p) => p.name === name);
}

export const REGIONS: { name: string; codes: [number, number] }[] = [
  { name: '北海道・東北', codes: [1, 7] },
  { name: '関東', codes: [8, 14] },
  { name: '中部', codes: [15, 23] },
  { name: '近畿', codes: [24, 30] },
  { name: '中国', codes: [31, 35] },
  { name: '四国', codes: [36, 39] },
  { name: '九州・沖縄', codes: [40, 47] },
];

export const regionOf = (code: number) => REGIONS.find((r) => code >= r.codes[0] && code <= r.codes[1])!.name;

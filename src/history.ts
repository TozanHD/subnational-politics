/**
 * 民主党政権期（2009〜2011年末）との比較。
 *
 * このサイトの本筋ではない追加機能なので、次の 2 段階で外せるようにしている。
 *   1. 閲覧者ごと（オプトアウト）: 初期状態は表示。「比較を隠す」で非表示にでき、選択はブラウザに記憶する。
 *   2. サイトごと: ビルド時に環境変数 VITE_HISTORY_COMPARE=off を指定すると、機能もデータも含めない。
 * 比較用データ（src/data/history.json）は表示するときだけ読み込む別ファイルにしている。
 */
import { useEffect, useState, useSyncExternalStore } from 'react';

export const HISTORY_ENABLED = import.meta.env.VITE_HISTORY_COMPARE !== 'off';

export interface HistoryBody {
  fixed: number;
  vacant: number;
  parties: Record<string, number>;
}

export interface HistorySnapshot {
  id: string;
  asOf: string;
  cabinet: string;
  label: string;
  source: { url: string; pageUrl: string };
  parties: string[];
  prefectures: Record<
    string,
    { assembly: HistoryBody; cityAssembly: HistoryBody | null; townAssembly: HistoryBody | null; governor: string | null }
  >;
}

export interface HistoryData {
  default: string;
  snapshots: HistorySnapshot[];
}

/** 民主党の後継として比べる政党（参考表示） */
export const DPJ = '民主党';
export const DPJ_SUCCESSORS = ['立憲民主党', '国民民主党'];

// ---------------------------------------------------------------------------
// 表示する・しない、どの年と比べるか（ブラウザに記憶し、画面内のすべての場所で共有する）
// ---------------------------------------------------------------------------

const KEY_OFF = 'compare-dpj-off';
const KEY_YEAR = 'compare-dpj-year';
const listeners = new Set<() => void>();

const read = (k: string): string | null => {
  try {
    return window.localStorage.getItem(k);
  } catch {
    return null;
  }
};
const write = (k: string, v: string | null) => {
  try {
    if (v === null) window.localStorage.removeItem(k);
    else window.localStorage.setItem(k, v);
  } catch {
    /* 記憶できなくても、この画面の中では切り替わる */
  }
};

let state = { on: read(KEY_OFF) !== '1', year: read(KEY_YEAR) };
const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};
const set = (next: Partial<typeof state>) => {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn());
};

export function useCompare() {
  const s = useSyncExternalStore(subscribe, () => state);
  return {
    on: HISTORY_ENABLED && s.on,
    year: s.year,
    setOn: (on: boolean) => {
      write(KEY_OFF, on ? null : '1');
      set({ on });
    },
    setYear: (year: string) => {
      write(KEY_YEAR, year);
      set({ year });
    },
  };
}

// ---------------------------------------------------------------------------
// データの読み込み（表示するときだけ）
// ---------------------------------------------------------------------------

let cache: HistoryData | null = null;
let loading: Promise<HistoryData> | null = null;

export function useHistoryData(active: boolean): HistoryData | null {
  const [data, setData] = useState<HistoryData | null>(cache);
  useEffect(() => {
    if (!active || !HISTORY_ENABLED || cache) return;
    loading ??= import('./data/history.json').then((m) => (cache = m.default as unknown as HistoryData));
    let alive = true;
    loading.then((d) => alive && setData(d));
    return () => {
      alive = false;
    };
  }, [active]);
  return data;
}

export function pickSnapshot(data: HistoryData, year: string | null): HistorySnapshot {
  return data.snapshots.find((s) => s.id === year) ?? data.snapshots.find((s) => s.id === data.default) ?? data.snapshots[0];
}

export const sumHistory = (bodies: HistoryBody[]): HistoryBody => {
  const out: HistoryBody = { fixed: 0, vacant: 0, parties: {} };
  for (const b of bodies) {
    out.fixed += b.fixed;
    out.vacant += b.vacant;
    for (const [p, n] of Object.entries(b.parties)) out.parties[p] = (out.parties[p] ?? 0) + n;
  }
  return out;
};

export const historyTotal = (b: HistoryBody) => Object.values(b.parties).reduce((a, n) => a + n, 0);

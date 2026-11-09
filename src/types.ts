/** [男, 女, 計]。性別非公表の議員がいると 男+女 < 計 になる。 */
export type Count = [number, number, number];

export interface Body {
  /** 定数 */
  fixed: number;
  /** 欠員 */
  vacant: number;
  total: Count;
  /** 表の並び順（総務省の掲載順）を保った政党別人数。0 人の政党は含まない。 */
  parties: Record<string, Count>;
}

export interface Prefecture {
  code: number;
  name: string;
  assembly: Body;
  cityAssembly?: Body;
  townAssembly?: Body;
  governor?: { party: string; female: boolean } | null;
}

export interface Dataset {
  schemaVersion: number;
  asOf: string;
  updatedAt?: string;
  source: { xlsxUrl?: string | null; pageUrl?: string | null };
  parties: string[];
  prefectures: Prefecture[];
}

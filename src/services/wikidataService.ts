export interface PartyData {
  name: string;
  male: number;
  female: number;
  total: number;
  isRulingParty: boolean;
  color: string;
}

export interface PrefectureData {
  name: string;
  totalSeats: number;
  sourceUrl?: string; // Legacy
  seatingChartUrl?: string;
  officialElectionUrl?: string;
  senkyoComUrl?: string;
  parties: PartyData[];
}

export interface SoumuData {
  prefectures: PrefectureData[];
  overallParties: Record<string, PartyData>;
  totalMembers: number;
}

const PARTY_COLORS: Record<string, string> = {
  '自由民主党': '#D7033A',
  '公明党': '#F55881',
  '立憲民主党': '#004098',
  '日本維新の会': '#00b300',
  '国民民主党': '#F8BC00',
  'れいわ新選組': '#e5007f',
  '日本共産党': '#7957DA',
  '参政党': '#ed6c00',
  '日本保守党': '#0a82dc',
  '社会民主党': '#01A8EC',
  'みんなでつくる党': '#60bdae',
  '無所属': '#808080',
};

const FALLBACK_COLORS = ['#4f46e5', '#06b6d4', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6'];
const RULING_PARTIES = ['自由民主党', '公明党'];

// Wikidata SPARQL query to get prefectural assembly members count by party and prefecture
const SPARQL_QUERY = `
SELECT ?prefLabel ?partyLabel (COUNT(?person) AS ?count) WHERE { 
  ?person wdt:P39 ?position . 
  ?position wdt:P279* wd:Q104525695 . 
  ?person wdt:P102 ?party . 
  ?position wdt:P1001 ?pref . 
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ja". } 
} GROUP BY ?prefLabel ?partyLabel
`;

export const fetchWikidata = async (): Promise<SoumuData> => {
  try {
    const url = "https://query.wikidata.org/sparql?query=" + encodeURIComponent(SPARQL_QUERY) + "&format=json";
    
    // Wikidata requires a descriptive User-Agent
    const response = await fetch(url, {
      headers: {
        'Accept': 'application/sparql-results+json',
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch Wikidata: ${response.statusText}`);
    }

    const data = await response.json();
    const bindings = data.results.bindings;

    const prefMap: Record<string, PrefectureData> = {};
    const overallParties: Record<string, PartyData> = {};
    let totalMembers = 0;

    bindings.forEach((b: any) => {
      const prefName = b.prefLabel?.value || '不明';
      const partyName = b.partyLabel?.value || '不明';
      const count = parseInt(b.count?.value || '0', 10);

      // Skip obvious invalid entries
      if (prefName.startsWith('Q') || partyName.startsWith('Q')) return;

      if (!prefMap[prefName]) {
        prefMap[prefName] = { name: prefName, totalSeats: 0, parties: [] };
      }

      prefMap[prefName].totalSeats += count;
      totalMembers += count;

      const isRulingParty = RULING_PARTIES.includes(partyName);
      
      prefMap[prefName].parties.push({
        name: partyName,
        male: 0, // Wikidata generic query doesn't split by gender easily in aggregate, mock as 0
        female: 0,
        total: count,
        isRulingParty,
        color: PARTY_COLORS[partyName] ?? FALLBACK_COLORS[Object.keys(prefMap[prefName].parties).length % FALLBACK_COLORS.length]
      });

      if (!overallParties[partyName]) {
        overallParties[partyName] = { 
          name: partyName, male: 0, female: 0, total: 0, 
          isRulingParty, 
          color: PARTY_COLORS[partyName] ?? '#808080' 
        };
      }
      overallParties[partyName].total += count;
    });

    const prefectures = Object.values(prefMap).map(pref => {
      // Sort ruling parties first, then by seat count
      pref.parties.sort((a, b) => {
        if (a.isRulingParty && !b.isRulingParty) return -1;
        if (!a.isRulingParty && b.isRulingParty) return 1;
        return b.total - a.total;
      });
      return pref;
    });

    // Sort prefectures roughly by JIS code or just name to keep it consistent
    prefectures.sort((a, b) => a.name.localeCompare(b.name, 'ja'));

    return {
      prefectures,
      overallParties,
      totalMembers,
    };

  } catch (error) {
    console.error('Wikidata Fetch Error:', error);
    throw error;
  }
};

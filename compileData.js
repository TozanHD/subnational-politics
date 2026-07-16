const fs = require('fs');

const rawData = [
{
  "prefecture": "栃木県",
  "seatingChartUrl": "https://www.pref.tochigi.lg.jp/kengikai/index.html",
  "officialElectionUrl": "https://www.pref.tochigi.lg.jp/kensei/senkyo/index.html",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/41662",
  "totalSeats": 50,
  "parties": [
    { "name": "とちぎ自民党議員会", "seats": 29 },
    { "name": "民主市民クラブ", "seats": 5 },
    { "name": "公明党栃木県議会議員会", "seats": 3 },
    { "name": "県民クラブ", "seats": 3 },
    { "name": "夢と希望あふれる栃木を創る会", "seats": 3 },
    { "name": "日本維新の会", "seats": 1 },
    { "name": "日本共産党栃木県議団", "seats": 1 }
  ]
},
{
  "prefecture": "群馬県",
  "seatingChartUrl": "https://www.pref.gunma.jp/site/gikai/25734.html",
  "officialElectionUrl": "https://www.pref.gunma.jp/site/senkyo/",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/21435",
  "totalSeats": 50,
  "parties": [
    { "name": "自由民主党", "seats": 30 },
    { "name": "つる舞う", "seats": 5 },
    { "name": "リベラル群馬", "seats": 4 },
    { "name": "公明党", "seats": 3 },
    { "name": "日本共産党", "seats": 2 },
    { "name": "群馬維新の会", "seats": 1 },
    { "name": "無所属", "seats": 1 },
    { "name": "欠員", "seats": 4 }
  ]
},
{
  "prefecture": "茨城県",
  "seatingChartUrl": "https://www.pref.ibaraki.jp/gikai/meibo/index.htm",
  "officialElectionUrl": "https://www.pref.ibaraki.jp/gikai/",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/19904",
  "totalSeats": 62,
  "parties": [
    { "name": "いばらき自民党", "seats": 43 },
    { "name": "公明党", "seats": 4 },
    { "name": "国民民主党", "seats": 4 },
    { "name": "茨城無所属・政策の会", "seats": 4 },
    { "name": "日本共産党", "seats": 1 },
    { "name": "市民ネットワーク", "seats": 1 },
    { "name": "日本維新の会", "seats": 1 },
    { "name": "無所属", "seats": 4 }
  ]
},
{
  "prefecture": "東京都",
  "seatingChartUrl": "https://www.gikai.metro.tokyo.lg.jp/membership/",
  "officialElectionUrl": "https://www.senkyo.metro.tokyo.lg.jp/",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/23019",
  "totalSeats": 124,
  "parties": [
    { "name": "都民ファーストの会 東京都議団", "seats": 31 },
    { "name": "東京都議会自由民主党", "seats": 22 },
    { "name": "東京都議会立憲民主党・ミライ会議・生活者ネットワーク・無所属の会", "seats": 20 },
    { "name": "都議会公明党", "seats": 19 },
    { "name": "日本共産党東京都議会議員団", "seats": 14 },
    { "name": "国民民主党東京都議団", "seats": 9 },
    { "name": "東京都議会参政党", "seats": 3 },
    { "name": "地域政党 自由を守る会", "seats": 2 },
    { "name": "無所属（やちよの会）", "seats": 1 },
    { "name": "無所属（東京・品川からやさしい未来を）", "seats": 1 },
    { "name": "無所属（新時代の八王子）", "seats": 1 },
    { "name": "無所属（グリーンな東京）", "seats": 1 }
  ]
},
{
  "prefecture": "埼玉県",
  "seatingChartUrl": "https://www.pref.saitama.lg.jp/e1601/gikai-member-kaiha.html",
  "officialElectionUrl": "https://www.pref.saitama.lg.jp/s-gikai/",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/24430",
  "totalSeats": 93,
  "parties": [
    { "name": "埼玉県議会自由民主党議員団", "seats": 52 },
    { "name": "埼玉民主フォーラム", "seats": 11 },
    { "name": "埼玉県議会公明党議員団", "seats": 9 },
    { "name": "無所属県民会議", "seats": 5 },
    { "name": "日本共産党埼玉県議会議員団", "seats": 3 },
    { "name": "無所属改革の会", "seats": 1 },
    { "name": "無所属保守さくらの会", "seats": 1 },
    { "name": "埼玉県市民ネットワーク", "seats": 1 },
    { "name": "無所属", "seats": 3 }
  ]
},
{
  "prefecture": "神奈川県",
  "seatingChartUrl": "https://www.pref.kanagawa.jp/gikai/p844152.html",
  "officialElectionUrl": "https://www.pref.kanagawa.jp/gikai/p80267.html",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/26651",
  "totalSeats": 105,
  "parties": [
    { "name": "自由民主党", "seats": 45 },
    { "name": "立憲民主党・かながわクラブ", "seats": 21 },
    { "name": "かながわ未来", "seats": 10 },
    { "name": "公明党", "seats": 8 },
    { "name": "県政会・立憲民主神奈川ネット", "seats": 4 },
    { "name": "日本共産党", "seats": 2 },
    { "name": "日本維新の会", "seats": 2 },
    { "name": "中原・高津の会", "seats": 2 },
    { "name": "わが町", "seats": 1 },
    { "name": "神奈川を変える港南の会", "seats": 1 },
    { "name": "創和会", "seats": 1 },
    { "name": "翼の会", "seats": 1 },
    { "name": "厚木愛川清川の会", "seats": 1 }
  ]
},
{
  "prefecture": "千葉県",
  "seatingChartUrl": "https://www.pref.chiba.lg.jp/gikai/giin/index.html",
  "officialElectionUrl": "https://www.pref.chiba.lg.jp/senkan/index.html",
  "senkyoComUrl": "https://go2senkyo.com/local/senkyo/20857",
  "totalSeats": 95,
  "parties": [
    { "name": "自由民主党千葉県議会議員会", "seats": 49 },
    { "name": "立憲民主党千葉県議会議員会", "seats": 13 },
    { "name": "公明党千葉県議会議員団", "seats": 8 },
    { "name": "千葉新政策議員団", "seats": 5 },
    { "name": "日本共産党千葉県議会議員団", "seats": 4 },
    { "name": "平和の党", "seats": 1 },
    { "name": "国民民主党千葉県議会議員会", "seats": 1 },
    { "name": "千葉県民の声", "seats": 1 },
    { "name": "リベラル民主", "seats": 1 },
    { "name": "市民力", "seats": 1 },
    { "name": "有志の会", "seats": 1 },
    { "name": "野田民主の会", "seats": 1 },
    { "name": "未来ちば", "seats": 1 },
    { "name": "無所属", "seats": 2 }
  ]
}
];

const PARTY_COLORS = {
  '自由民主党': '#D7033A', '公明党': '#F55881', '立憲民主党': '#004098',
  '日本維新の会': '#00b300', '国民民主党': '#F8BC00', 'れいわ新選組': '#e5007f',
  '日本共産党': '#7957DA', '参政党': '#ed6c00', '日本保守党': '#0a82dc',
  '社会民主党': '#01A8EC', 'みんなでつくる党': '#60bdae', '無所属': '#808080',
  '都民ファーストの会': '#10b981' // 都民ファーストは緑系
};
const FALLBACK_COLORS = ['#4f46e5', '#06b6d4', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6'];
const RULING_PARTIES = ['自由民主党', '公明党'];

// Helper to check if it's ruling party
function isRuling(pname) {
  return RULING_PARTIES.some(rp => pname.includes(rp) || pname.includes('自民') || pname.includes('公明'));
}

function getGlobalPartyName(pname) {
  if (pname.includes('都民ファースト')) return '都民ファーストの会';
  if (pname.includes('自民')) return '自由民主党';
  if (pname.includes('公明')) return '公明党';
  if (pname.includes('立憲民主') || pname.includes('立憲') || pname.includes('民主フォーラム')) return '立憲民主党';
  if (pname.includes('共産')) return '日本共産党';
  if (pname.includes('国民民主')) return '国民民主党';
  if (pname.includes('維新')) return '日本維新の会';
  if (pname.includes('無所属')) return '無所属';
  return pname;
}

let totalMembers = 0;
let overallParties = {};
let prefectures = [];

rawData.forEach(pref => {
  let pData = {
    name: pref.prefecture,
    totalSeats: pref.totalSeats,
    sourceUrl: pref.sourceUrl || null,
    seatingChartUrl: pref.seatingChartUrl || null,
    officialElectionUrl: pref.officialElectionUrl || null,
    senkyoComUrl: pref.senkyoComUrl || null,
    parties: []
  };
  
  pref.parties.forEach((party, idx) => {
    let seats = typeof party.seats === 'number' ? party.seats : parseInt(party.seats, 10);
    if(isNaN(seats) || seats <= 0) return;
    
    totalMembers += seats;
    let ruling = isRuling(party.name);
    let globalName = getGlobalPartyName(party.name);
    // 色は国政政党（globalName）のカラーを適用する
    let color = PARTY_COLORS[globalName] || FALLBACK_COLORS[idx % FALLBACK_COLORS.length];
    
    // 各県のデータにはローカル会派名をそのまま格納し、合算しない
    pData.parties.push({
      name: party.name,
      male: 0, female: 0, total: seats,
      isRulingParty: ruling,
      color: color
    });
    
    // 全体のサマリー（全国集計用）では国政政党ベースで合算しておく（与野党集計などのため）
    if(!overallParties[globalName]) {
      overallParties[globalName] = { name: globalName, male: 0, female: 0, total: 0, isRulingParty: ruling, color: color };
    }
    overallParties[globalName].total += seats;
  });
  
  pData.parties.sort((a,b) => {
    // 1. Non-ruling first, Ruling last (Left to Right)
    if(!a.isRulingParty && b.isRulingParty) return -1;
    if(a.isRulingParty && !b.isRulingParty) return 1;
    
    // 2. If both are non-ruling, sort by size ascending (smallest on far left)
    if(!a.isRulingParty && !b.isRulingParty) {
        return a.total - b.total;
    }
    
    // 3. If both are ruling, sort by size descending (largest on far right, meaning it comes last in rendering order of a donut chart if we want it on the right side)
    // Wait, Chart.js Doughnut starts from Top (12 o'clock) and goes clockwise. 
    // We set rotation: -90, circumference: 180.
    // So Left is the first item in array, Right is the last item.
    // Smallest non-ruling -> ... -> Largest ruling
    return a.total - b.total;
  });
  
  prefectures.push(pData);
});

const result = {
  totalMembers,
  overallParties,
  prefectures
};

fs.writeFileSync('public/data.json', JSON.stringify(result, null, 2));
console.log('Compiled data.json successfully.');

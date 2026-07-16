const https = require('https');
const http = require('http');

function fetch(url) {
    return new Promise((resolve, reject) => {
        const client = url.startsWith('https') ? https : http;
        client.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
            let data = '';
            res.on('data', chunk => data += chunk);
            res.on('end', () => resolve({ status: res.statusCode, data }));
        }).on('error', reject);
    });
}

async function findLinks(url, regexes) {
    try {
        const { status, data } = await fetch(url);
        if (status !== 200) {
            console.log(`Failed to fetch ${url}: ${status}`);
            return;
        }
        
        const links = [];
        const regex = /<a\s+(?:[^>]*?\s+)?href=(["'])(.*?)\1/gi;
        let match;
        while ((match = regex.exec(data)) !== null) {
            links.push(match[2]);
        }
        
        console.log(`Links found on ${url}:`);
        for (const link of links) {
            for (const r of regexes) {
                if (r.test(link)) {
                    console.log(`Match: ${link}`);
                }
            }
        }
    } catch (e) {
        console.error(e);
    }
}

findLinks('https://www.pref.tochigi.lg.jp/kensei/kensei/kengikai/index.html', [/meibo/i, /giin/i, /kaiha/i]);
findLinks('https://www.pref.chiba.lg.jp/gikai/', [/meibo/i, /giin/i, /kaiha/i]);

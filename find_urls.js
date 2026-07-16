const puppeteer = require('puppeteer');

async function checkUrl(url) {
    try {
        const browser = await puppeteer.launch({ headless: "new" });
        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36');
        const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        const status = response ? response.status() : 500;
        await browser.close();
        return status;
    } catch (e) {
        return e.message;
    }
}

async function searchAndGetTopResult(query) {
    try {
        const browser = await puppeteer.launch({ headless: "new" });
        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64)');
        await page.goto(`https://www.google.co.jp/search?q=${encodeURIComponent(query)}`, { waitUntil: 'domcontentloaded' });
        
        // Extract top organic result link
        const link = await page.evaluate(() => {
            const el = document.querySelector('#search a');
            return el ? el.href : null;
        });
        await browser.close();
        return link;
    } catch (e) {
        return null;
    }
}

async function main() {
    console.log("Starting search...");
    const queries = [
        "栃木県議会 会派別議員名簿",
        "栃木県議会議員選挙 令和5年 投開票結果 栃木県選挙管理委員会",
        "茨城県議会 会派別議員名簿",
        "茨城県議会議員選挙 令和4年 投開票結果 茨城県選挙管理委員会",
        "埼玉県議会 会派別議員名簿",
        "埼玉県議会議員選挙 令和5年 投開票結果 埼玉県選挙管理委員会",
        "千葉県議会 会派等別議員名簿",
        "千葉県議会議員選挙 令和5年 選挙結果 千葉県選挙管理委員会"
    ];
    for (const q of queries) {
        const link = await searchAndGetTopResult(q);
        if (link) {
            const status = await checkUrl(link);
            console.log(`[${status}] ${q} -> ${link}`);
        } else {
            console.log(`[FAILED] ${q}`);
        }
    }
}

main();

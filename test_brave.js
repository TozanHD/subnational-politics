const puppeteer = require('puppeteer');

(async () => {
    try {
        console.log("Connecting to Brave on port 9222...");
        const browser = await puppeteer.connect({ browserURL: 'http://127.0.0.1:9222' });
        const pages = await browser.pages();
        console.log("Connected! Open pages:");
        for (const page of pages) {
            console.log(" - " + await page.title() + " (" + page.url() + ")");
        }
        
        // Open a new tab to show it works
        const newPage = await browser.newPage();
        await newPage.goto('https://www.pref.tochigi.lg.jp/kengikai/index.html');
        console.log("Navigated to Tochigi assembly page.");
        
        await browser.disconnect();
    } catch (e) {
        console.error("Failed to connect:", e.message);
    }
})();

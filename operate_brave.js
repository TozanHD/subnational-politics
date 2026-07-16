const puppeteer = require('puppeteer');

(async () => {
    console.log("Braveを起動して操作を開始します...");
    const browser = await puppeteer.launch({
        executablePath: "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
        headless: false, // ユーザーに操作画面を見せる
        defaultViewport: null,
        args: ['--start-maximized']
    });

    try {
        const page = (await browser.pages())[0];
        await page.goto('https://www.pref.tochigi.lg.jp/kengikai/index.html');
        console.log("栃木県議会のページにアクセスしました。");
        await new Promise(r => setTimeout(r, 2000)); // 2秒待機して見せる

        await page.goto('https://www.pref.chiba.lg.jp/gikai/giin/index.html');
        console.log("千葉県議会のページにアクセスしました。");
        await new Promise(r => setTimeout(r, 2000)); // 2秒待機

        await page.goto('https://www.pref.ibaraki.jp/gikai/meibo/index.htm');
        console.log("茨城県議会のページにアクセスしました。");
        await new Promise(r => setTimeout(r, 2000)); // 2秒待機

        console.log("すべてのアクセス確認が完了しました。操作を終了します。");
    } catch (e) {
        console.error("エラーが発生しました:", e.message);
    } finally {
        await browser.close();
    }
})();

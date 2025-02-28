import { test, expect } from "@playwright/test";
import fs from "fs";
const { chromium } = require('playwright-extra');

function getRandomDelay(min = 3000, max = 6000) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

test.describe.parallel("Crawl Data", () => {
    const PAGE = process.env.PAGE_NUMBER || 1; 

    for (let pageNumber = 1; pageNumber <= Number(PAGE); pageNumber++) {
        test(`Crawl data from page ${pageNumber}`, async ({ page }) => {
            const url = `https://www.nhatot.com/mua-ban-bat-dong-san?page=${pageNumber}`;
            console.log(`Navigating to: ${url}`);

            await page.goto(url, { waitUntil: 'domcontentloaded' });

            await page.waitForSelector('.a13uzdlb', { timeout: 10000 });

            const data = await page.evaluate(() => {
                const links =  Array.from(document.querySelectorAll('.crd7gu7'));
                return Array.from(document.querySelectorAll('.a13uzdlb')).map((el,index) => ({
                    title: el.querySelector(".a15fd2pn")?.innerText.trim() || "",
                    details: el.querySelector(".bwq0cbs.tle2ik0")?.innerText.trim() || "",
                    price: el.querySelector(".bfe6oav:nth-child(1)")?.innerText.trim() || "",
                    areaPrice: el.querySelector(".bfe6oav:nth-child(3)")?.innerText.trim() || "",
                    totalArea: el.querySelector(".bfe6oav:nth-child(5)")?.innerText.trim() || "",
                    locationTime: el.querySelector(".c1u6gyxh.tx5yyjc")?.innerText.trim() || "",
                    link: links[index]?.href.trim() || "" 
                }));
            });

            console.log(`Extracted: ${data.length} items`);

            fs.writeFileSync(`crawled_data_page_${pageNumber}.json`, JSON.stringify(data, null, 2));
            console.log(`✅ Data saved for page ${pageNumber}`);

            await page.waitForTimeout(getRandomDelay());
        });
    }
});

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
            const url = `https://www.nhatot.com/mua-ban-bat-dong-san?f=p&page=${pageNumber}`;
            console.log(`Navigating to: ${url}`);

            await page.goto(url, { waitUntil: 'domcontentloaded' });
            await page.waitForSelector('.a13uzdlb', { timeout: 10000 });
            
            const data = await page.evaluate(() => {
                return Array.from(document.querySelectorAll('.webeqpz')).map(wrapper => ({
                    title: wrapper.querySelector(".a13uzdlb .a15fd2pn")?.innerText.trim() || "",
                    details: wrapper.querySelector(".a13uzdlb .bwq0cbs.tle2ik0")?.innerText.trim() || "",
                    price: wrapper.querySelector(".a13uzdlb .bfe6oav:nth-child(1)")?.innerText.trim() || "",
                    area_price: wrapper.querySelector(".a13uzdlb .bfe6oav:nth-child(3)")?.innerText.trim() || "",
                    total_area: wrapper.querySelector(".a13uzdlb .bfe6oav:nth-child(5)")?.innerText.trim() || "",
                    location_time: wrapper.querySelector(".a13uzdlb .c1u6gyxh.tx5yyjc")?.innerText.trim() || "",
                    link: wrapper.querySelector(".crd7gu7")?.href.trim() || "", // Assuming link is inside `.crd7gu7`,
                    user: wrapper.querySelector(".b2cylky.s1amxne5")?.innerHTML.trim() || "",
                }));
            });

            console.log(`Extracted: ${data.length} items`);

            fs.writeFileSync(`crawled_data_page_${pageNumber}.json`, JSON.stringify(data, null, 2));
            console.log(`✅ Data saved for page ${pageNumber}`);

            await page.waitForTimeout(getRandomDelay());
        });
    }
});

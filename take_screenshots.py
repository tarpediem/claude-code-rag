#!/usr/bin/env python3
"""Take screenshots of Web UI for documentation"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def take_screenshots():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        # Dashboard
        await page.goto("http://127.0.0.1:8420")
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="assets/web-dashboard.png")
        print("✓ Dashboard screenshot saved")

        # Search
        await page.click('a[href="/search"]')
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="assets/web-search.png")
        print("✓ Search screenshot saved")

        # Memories
        await page.click('a[href="/memories"]')
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="assets/web-memories.png")
        print("✓ Memories screenshot saved")

        # Index
        await page.click('a[href="/index"]')
        await page.wait_for_load_state("networkidle")
        await page.screenshot(path="assets/web-index.png")
        print("✓ Index screenshot saved")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(take_screenshots())

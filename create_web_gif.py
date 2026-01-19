#!/usr/bin/env python3
"""Create animated GIF of Web UI interactions"""
import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright

async def create_web_demo():
    """Create animated GIF demo of Web UI"""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1600, "height": 900})

        frames_dir = Path("assets/frames")
        frames_dir.mkdir(exist_ok=True)

        frame_num = 0

        # Helper to save frame
        async def save_frame(name=""):
            nonlocal frame_num
            await page.screenshot(path=f"assets/frames/frame_{frame_num:03d}_{name}.png")
            frame_num += 1

        # Start at dashboard
        await page.goto("http://127.0.0.1:8420")
        await page.wait_for_load_state("networkidle")
        await save_frame("dashboard")
        await asyncio.sleep(1)
        await save_frame("dashboard2")

        # Click search
        await page.click('a[href="/search"]')
        await page.wait_for_load_state("networkidle")
        await save_frame("search_page")
        await asyncio.sleep(0.5)

        # Type in search box
        search_input = 'input[placeholder*="Search"]'
        await page.click(search_input)
        await save_frame("search_focus")

        search_text = "GPU configuration"
        for char in search_text:
            await page.type(search_input, char, delay=100)
            if len(char) % 3 == 0:  # Save every 3rd character
                await save_frame(f"typing")

        await save_frame("search_typed")
        await asyncio.sleep(1)
        await save_frame("search_results")

        # Click memories
        await page.click('a[href="/memories"]')
        await page.wait_for_load_state("networkidle")
        await save_frame("memories_page")
        await asyncio.sleep(1)

        # Hover over a card to show delete button
        cards = await page.query_selector_all('.card')
        if cards:
            await cards[0].hover()
            await save_frame("card_hover")
            await asyncio.sleep(0.5)

        # Click index page
        await page.click('a[href="/index"]')
        await page.wait_for_load_state("networkidle")
        await save_frame("index_page")
        await asyncio.sleep(1)
        await save_frame("index_page2")

        await browser.close()

        print(f"✓ Created {frame_num} frames in assets/frames/")
        print(f"Creating GIF with ffmpeg...")

        import subprocess
        subprocess.run([
            'ffmpeg', '-y',
            '-framerate', '2',
            '-pattern_type', 'glob',
            '-i', 'assets/frames/*.png',
            '-vf', 'scale=1600:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
            'assets/demo.gif'
        ])

        print("✓ Created assets/demo.gif")

if __name__ == "__main__":
    asyncio.run(create_web_demo())

import re
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1400,'height':800})
    pg.goto('http://localhost:8070/web/login?db=t1')
    pg.fill('input[name=login]','ui_dir'); pg.fill('input[name=password]','Passw0rd!x'); pg.click('button[type=submit]')
    pg.wait_for_selector('.o_navbar', timeout=30000)
    pg.goto('http://localhost:8070/odoo' if False else 'http://localhost:8070/web')
    pg.wait_for_timeout(2500)
    pg.click('.o_navbar_apps_menu button'); pg.click('text=Lead Export'); pg.wait_for_timeout(1500)
    pg.click('.o_menu_sections >> text=Approvals'); pg.wait_for_selector('.modal', timeout=10000); pg.wait_for_timeout(1000)
    print('dialog rows:', pg.locator('.modal tbody tr.o_data_row').count())
    pg.screenshot(path='/tmp/rig/ui1.png')
    pg.click('.modal button:has-text("Reveal Code")'); pg.wait_for_timeout(2500)
    notes=[t.inner_text() for t in pg.locator('.o_notification').all()]
    print('notifications:', notes)
    print('dialog rows after:', pg.locator('.modal tbody tr.o_data_row').count())
    pg.screenshot(path='/tmp/rig/ui2.png'); b.close()

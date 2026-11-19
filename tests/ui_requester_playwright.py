import sys
from playwright.sync_api import sync_playwright
code=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={'width':1400,'height':800})
    pg.goto('http://localhost:8070/web/login?db=t1')
    pg.fill('input[name=login]','ui_req'); pg.fill('input[name=password]','Passw0rd!x'); pg.click('button[type=submit]')
    pg.wait_for_selector('.o_navbar', timeout=30000); pg.wait_for_timeout(2000)
    pg.click('.o_navbar_apps_menu button'); pg.click('text=Lead Export'); pg.wait_for_timeout(1500)
    print('menus:', [t.strip() for t in pg.locator('.o_menu_sections .dropdown-item, .o_menu_sections .o_nav_entry').all_inner_texts()])
    pg.click('.o_data_row >> nth=0'); pg.wait_for_selector('.o_form_view', timeout=10000)
    print('state:', pg.locator('.o_statusbar_status .o_arrow_button_current').inner_text() if pg.locator('.o_statusbar_status .o_arrow_button_current').count() else '?')
    pg.click('button:has-text("Enter Code")'); pg.wait_for_selector('.modal', timeout=10000)
    pg.screenshot(path='/tmp/rig/ui3.png'); pg.fill('.modal input', code); print([b.inner_text() for b in pg.locator('.modal footer button').all()]); pg.get_by_role('button',name='Unlock').click(); pg.wait_for_timeout(2500)
    print('notes:', [t.inner_text() for t in pg.locator('.o_notification').all()])
    print('modal open after:', pg.locator('.modal').count())
    b.close()

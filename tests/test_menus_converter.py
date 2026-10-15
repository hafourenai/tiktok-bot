from menus import menu_content


def test_converter_menu_has_web_link_and_back_button():
    _, markup = menu_content("converter")
    buttons = [button for row in markup.inline_keyboard for button in row]
    assert any(button.url == "https://converter-web-orcin.vercel.app" for button in buttons)
    assert any(button.callback_data == "menu:home" for button in buttons)

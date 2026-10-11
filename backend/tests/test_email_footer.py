from backend.app.services.email_service import Email, with_footer


def test_plain_text_email_gets_the_signature_once():
    out = with_footer(Email("a@example.com", "Hi", "Hello there.\n"))
    assert out.body.endswith("Regards,\nApplyXAI\nwww.applyxai.com\nBangalore\ninfo@applyxai.com")
    assert with_footer(out).body == out.body
    assert out.html == ""


def test_html_signature_goes_inside_the_body_tag():
    out = with_footer(Email("a@example.com", "Hi", "Hello", html="<html><body><p>Hello</p></body></html>"))
    assert out.html.index("info@applyxai.com") < out.html.lower().index("</body>")
    assert 'href="https://www.applyxai.com"' in out.html
    assert with_footer(out).html == out.html


def test_html_without_body_tag_is_appended():
    out = with_footer(Email("a@example.com", "Hi", "Hello", html="<p>Hello</p>"))
    assert out.html.startswith("<p>Hello</p>") and out.html.rstrip().endswith("</div>")

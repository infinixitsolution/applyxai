from backend.app.services.email_service import LOGO_URL, Email, branded


def test_plain_text_email_gets_the_signature_once():
    out = branded(Email("a@example.com", "Hi", "Hello there.\n"))
    assert out.body.endswith("Regards,\nApplyXAI\nwww.applyxai.com\nBangalore\ninfo@applyxai.com")
    assert branded(out).body == out.body


def test_plain_text_email_gets_the_branded_html_layout():
    body = "Verify your email\n\nHi Asha,\n\nConfirm your email address:\nhttps://applyxai.com/verify?token=a&b=1\n\nThanks."
    out = branded(Email("a@example.com", "Verify", body))
    assert out.html.count(LOGO_URL) == 2
    assert '<h1 style="' in out.html and ">Verify your email</h1>" in out.html
    assert ">Confirm your email address</a>" in out.html
    assert 'href="https://applyxai.com/verify?token=a&amp;b=1"' in out.html
    assert "mailto:info@applyxai.com" in out.html
    assert branded(out).html == out.html


def test_plain_text_is_escaped():
    out = branded(Email("a@example.com", "Hi", "Hello <script>x</script>"))
    assert "<script>" not in out.html and "&lt;script&gt;" in out.html


def test_custom_html_body_is_wrapped_in_the_layout():
    out = branded(Email("a@example.com", "Hi", "Hello", html="<html><head></head><body><p>Custom</p></body></html>"))
    assert "<p>Custom</p>" in out.html and out.html.count("<body") == 1
    assert out.html.index(LOGO_URL) < out.html.index("<p>Custom</p>") < out.html.rindex(LOGO_URL)


def test_html_fragment_is_wrapped_in_the_layout():
    out = branded(Email("a@example.com", "Hi", "Hello", html="<p>Fragment</p>"))
    assert "<p>Fragment</p>" in out.html and out.html.rstrip().endswith("</html>")

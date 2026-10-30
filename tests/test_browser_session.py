from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException

from modules.browser_session import session_lost


def test_session_lost_window_and_invalid_session():
    assert session_lost(NoSuchWindowException("gone"))
    assert session_lost(InvalidSessionIdException("invalid session id"))


def test_session_lost_message_markers():
    assert session_lost(WebDriverException("disconnected: not connected to DevTools"))
    assert not session_lost(WebDriverException("element click intercepted"))

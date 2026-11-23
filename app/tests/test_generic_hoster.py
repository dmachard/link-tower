import pytest
from unittest.mock import MagicMock

from app.core.hoster import GenericHoster


def _mock_session(status: int, html: str = ""):
    class _Resp:
        def __init__(self):
            self.status = status
        async def text(self, errors="replace"):
            return html
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False

    sess = MagicMock()
    sess.get = MagicMock(return_value=_Resp())
    return sess


@pytest.mark.asyncio
async def test_generic_hoster_alive_dead_error():
    gh = GenericHoster({
        "name": "rapidgator",
        "domains": ["rapidgator.net"],
        "allow_redirects": False,
        "dead_if_status": [302, 404],
        "dead_if_text": ["404 File not found"],
        "error_if_text": ["turnstile"],
        "extract-filename_regex": r"Downloading:.*?<a>([^<]+)</a>",
        "extract-size_regex": r"Size:<strong>([^<]+)</strong>",
    })

    res_alive = await gh.check(
        "https://rapidgator.net/file/abc",
        _mock_session(200, "Downloading: <a>Movie.mkv</a> Size:<strong>2.0 GB</strong>"),
    )
    assert res_alive["status"] == "alive"
    assert res_alive["filename"] == "Movie.mkv"
    assert res_alive["size"] > 0

    res_dead_status = await gh.check("https://rapidgator.net/file/abc", _mock_session(302))
    assert res_dead_status["status"] == "dead"

    res_dead_pat = await gh.check("https://rapidgator.net/file/abc", _mock_session(200, "404 File not found"))
    assert res_dead_pat["status"] == "dead"

    res_err = await gh.check("https://rapidgator.net/file/abc", _mock_session(200, "cf turnstile"))
    assert res_err["status"] == "error"


@pytest.mark.asyncio
async def test_hoster_shared_semaphore_and_delay():
    from unittest.mock import AsyncMock, patch
    from app.core.hoster import Hoster, _get_global_hoster_semaphore

    assert _get_global_hoster_semaphore() is _get_global_hoster_semaphore()

    with patch("app.core.hoster.settings") as mock_settings, \
         patch("app.core.hoster.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        mock_settings.HOSTERS = [{"name": "test", "domains": ["example.com"], "enable": True}]
        mock_settings.CONCURRENT_HOSTER_CHECKS = 2
        mock_settings.HOSTER_CHECK_DELAY_SECONDS = 1.5

        h = Hoster()
        h.direct_mappers["example.com"].check = AsyncMock(
            return_value={"status": "alive", "filename": "f.mkv", "size": 10}
        )
        res = await h.check_links(["https://example.com/1", "https://example.com/2"])
        assert len(res) == 2
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(1.5)



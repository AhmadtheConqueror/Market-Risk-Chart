from __future__ import annotations

from app.providers.news.base import NewsProvider
from app.providers.news.eia import EIANewsProvider
from app.providers.news.nnpc import NNPCNewsProvider
from app.providers.news.nuprc import NUPRCNewsProvider
from app.providers.news.opec import OPECNewsProvider


def get_news_providers() -> list[NewsProvider]:
    return [EIANewsProvider(), OPECNewsProvider(), NUPRCNewsProvider(), NNPCNewsProvider()]

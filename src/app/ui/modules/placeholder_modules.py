from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class PlaceholderModule(QWidget):
    """Generic placeholder for future modules."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #00d4ff;
                font-size: 32px;
                font-weight: bold;
                margin-bottom: 20px;
            }
        """)
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 16px;
                max-width: 600px;
            }
        """)
        layout.addWidget(desc_label)

        coming_soon = QLabel("Coming Soon...")
        coming_soon.setAlignment(Qt.AlignCenter)
        coming_soon.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 14px;
                font-style: italic;
                margin-top: 30px;
            }
        """)
        layout.addWidget(coming_soon)


class PortfolioModule(PlaceholderModule):
    """Portfolio tracking and management."""

    def __init__(self, parent=None):
        super().__init__(
            "Portfolio",
            "Track your investments, view performance metrics, and manage your positions.",
            parent,
        )


class WatchlistModule(PlaceholderModule):
    """Real-time watchlist."""

    def __init__(self, parent=None):
        super().__init__(
            "Watchlist",
            "Monitor your favorite securities with real-time price updates and alerts.",
            parent,
        )


class NewsModule(PlaceholderModule):
    """Financial news aggregator."""

    def __init__(self, parent=None):
        super().__init__(
            "News & Research",
            "Stay updated with the latest market news, earnings reports, and analyst ratings.",
            parent,
        )


class ScreenerModule(PlaceholderModule):
    """Stock screener."""

    def __init__(self, parent=None):
        super().__init__(
            "Stock Screener",
            "Filter and discover stocks based on technical indicators, fundamentals, and custom criteria.",
            parent,
        )


class AnalysisModule(PlaceholderModule):
    """Technical and fundamental analysis."""

    def __init__(self, parent=None):
        super().__init__(
            "Analysis Tools",
            "Perform in-depth technical analysis, backtesting, and quantitative research.",
            parent,
        )


class CryptoDashboardModule(PlaceholderModule):
    """Crypto portfolio and market overview."""

    def __init__(self, parent=None):
        super().__init__(
            "Crypto Dashboard",
            "Track your crypto portfolio, view market data, and monitor blockchain metrics.",
            parent,
        )


class DeFiModule(PlaceholderModule):
    """DeFi protocols and yield tracking."""

    def __init__(self, parent=None):
        super().__init__(
            "DeFi Tools",
            "Explore DeFi protocols, track staking positions, and analyze yield opportunities.",
            parent,
        )


class NFTModule(PlaceholderModule):
    """NFT portfolio tracker."""

    def __init__(self, parent=None):
        super().__init__(
            "NFT Tracker",
            "Monitor your NFT collection, track floor prices, and discover trending collections.",
            parent,
        )

from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from app.ui.hub_window import HubWindow
from app.ui.modules.chart.chart_module import ChartModule
from app.ui.modules.settings_module import SettingsModule
from app.ui.modules.placeholder_modules import (
    AnalysisModule,
    CryptoDashboardModule,
    DeFiModule,
    NFTModule,
    NewsModule,
    PortfolioModule,
    ScreenerModule,
    WatchlistModule,
)
from app.core.theme_manager import ThemeManager
from app.core.config import DEFAULT_THEME
from app.services.favorites_service import FavoritesService


def main() -> int:
    app = QApplication(sys.argv)

    # Initialize services
    FavoritesService.initialize()

    # Create centralized theme manager
    theme_manager = ThemeManager()
    theme_manager.set_theme(DEFAULT_THEME)

    # Create main hub window with theme manager
    hub = HubWindow(theme_manager)

    # Add modules (pass theme_manager to modules that need it)
    hub.add_module("charts", ChartModule(theme_manager))
    hub.add_module("crypto_dashboard", CryptoDashboardModule())
    hub.add_module("defi", DeFiModule())
    hub.add_module("nft", NFTModule())
    hub.add_module("portfolio", PortfolioModule())
    hub.add_module("watchlist", WatchlistModule())
    hub.add_module("news", NewsModule())
    hub.add_module("screener", ScreenerModule())
    hub.add_module("analysis", AnalysisModule())
    hub.add_module("settings", SettingsModule(theme_manager))

    # Show home screen on startup
    hub.show_initial_screen()

    hub.showMaximized()  # Launch in maximized window
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

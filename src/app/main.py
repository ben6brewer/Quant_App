from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from app.ui.hub_window import HubWindow
from app.core.theme_manager import ThemeManager
from app.core.config import DEFAULT_THEME
from app.services.favorites_service import FavoritesService
from app.services.preferences_service import PreferencesService


# Lazy factory functions - modules are imported only when first opened
def _create_chart_module(theme_manager):
    from app.ui.modules.chart.chart_module import ChartModule
    return ChartModule(theme_manager)


def _create_settings_module(theme_manager):
    from app.ui.modules.settings_module import SettingsModule
    return SettingsModule(theme_manager)


def _create_portfolio_construction_module(theme_manager):
    from app.ui.modules.portfolio_construction.portfolio_construction_module import PortfolioConstructionModule
    return PortfolioConstructionModule(theme_manager)


def _create_return_distribution_module(theme_manager):
    from app.ui.modules.return_distribution import ReturnDistributionModule
    return ReturnDistributionModule(theme_manager)


def _create_monte_carlo_module(theme_manager):
    from app.ui.modules.monte_carlo import MonteCarloModule
    return MonteCarloModule(theme_manager)


def _create_performance_metrics_module(theme_manager):
    from app.ui.modules.performance_metrics import PerformanceMetricsModule
    return PerformanceMetricsModule(theme_manager)


def _create_placeholder_module(class_name):
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
    modules = {
        "AnalysisModule": AnalysisModule,
        "CryptoDashboardModule": CryptoDashboardModule,
        "DeFiModule": DeFiModule,
        "NFTModule": NFTModule,
        "NewsModule": NewsModule,
        "PortfolioModule": PortfolioModule,
        "ScreenerModule": ScreenerModule,
        "WatchlistModule": WatchlistModule,
    }
    return modules[class_name]()


def main() -> int:
    app = QApplication(sys.argv)

    # Initialize services
    FavoritesService.initialize()
    PreferencesService.initialize()

    # Create centralized theme manager and load saved theme
    theme_manager = ThemeManager()
    saved_theme = PreferencesService.get_theme()
    theme_manager.set_theme(saved_theme, save_preference=False)  # Don't re-save on load

    # Create main hub window with theme manager
    hub = HubWindow(theme_manager)

    # Add modules - all use lazy factory functions (imported only when first opened)
    hub.add_module("charts", lambda: _create_chart_module(theme_manager))
    hub.add_module("crypto_dashboard", lambda: _create_placeholder_module("CryptoDashboardModule"))
    hub.add_module("defi", lambda: _create_placeholder_module("DeFiModule"))
    hub.add_module("nft", lambda: _create_placeholder_module("NFTModule"))
    hub.add_module("portfolio", lambda: _create_placeholder_module("PortfolioModule"))
    hub.add_module(
        "portfolio_construction",
        lambda: _create_portfolio_construction_module(theme_manager),
        has_own_home_button=True,
    )
    hub.add_module(
        "performance_metrics",
        lambda: _create_performance_metrics_module(theme_manager),
        has_own_home_button=True,
    )
    hub.add_module(
        "distribution_metrics",
        lambda: _create_return_distribution_module(theme_manager),
        has_own_home_button=True,
    )
    hub.add_module(
        "monte_carlo",
        lambda: _create_monte_carlo_module(theme_manager),
        has_own_home_button=True,
    )
    hub.add_module("watchlist", lambda: _create_placeholder_module("WatchlistModule"))
    hub.add_module("news", lambda: _create_placeholder_module("NewsModule"))
    hub.add_module("screener", lambda: _create_placeholder_module("ScreenerModule"))
    hub.add_module("analysis", lambda: _create_placeholder_module("AnalysisModule"))
    hub.add_module("settings", lambda: _create_settings_module(theme_manager))

    # Show home screen on startup
    hub.show_initial_screen()

    # Show window and manually maximize (critical for frameless windows on Windows)
    # DO NOT use showMaximized() - it locks geometry and prevents restore button from working
    hub.show()
    hub.maximize_on_startup()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

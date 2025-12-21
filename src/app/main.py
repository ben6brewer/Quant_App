from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui_main_window import MainWindow
from app.services.market_data import fetch_price_history


def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()

    # Default UI state (match your UI items: daily/weekly/monthly/yearly)
    win.interval_combo.setCurrentText("daily")
    win.chart_type_combo.setCurrentText("Candles")
    # win.scale_combo set in UI already; keep whatever default you want

    # Cache the last downloaded dataframe so chart-type/scale toggles don't refetch
    state = {"df": None, "ticker": None, "interval": None}

    def current_chart_type() -> str:
        return win.chart_type_combo.currentText()

    def current_interval() -> str:
        return win.interval_combo.currentText()

    def current_scale() -> str:
        return win.scale_combo.currentText()

    def render_from_cache() -> None:
        if state["df"] is None or state["ticker"] is None:
            return
        try:
            win.chart.set_prices(
                state["df"],
                ticker=state["ticker"],
                chart_type=current_chart_type(),
                scale=current_scale(),  # <-- IMPORTANT
            )
        except Exception as e:
            QMessageBox.critical(win, "Render Error", str(e))

    def load_ticker_max(ticker: str) -> None:
        ticker = (ticker or "").strip().upper()
        if not ticker:
            return

        interval = current_interval()

        try:
            win.statusBar().showMessage(f"Loading {ticker} (max, {interval})...")
            df = fetch_price_history(ticker, period="max", interval=interval)

            state["df"] = df
            state["ticker"] = ticker
            state["interval"] = interval

            render_from_cache()

            win.statusBar().showMessage(
                f"Loaded {ticker} ({interval}): {df.index.min().date()} → {df.index.max().date()} | rows={len(df)}"
            )
        except Exception as e:
            win.statusBar().showMessage("Error")
            QMessageBox.critical(win, "Load Error", str(e))

    # --- Triggers ---
    # Enter in ticker box -> download (max, selected interval) and render
    win.ticker_input.returnPressed.connect(lambda: load_ticker_max(win.ticker_input.text()))

    # Change chart type / scale -> re-render only (no refetch)
    win.chart_type_combo.currentTextChanged.connect(lambda _: render_from_cache())
    win.scale_combo.currentTextChanged.connect(lambda _: render_from_cache())

    # Change interval -> MUST refetch because bars change
    win.interval_combo.currentTextChanged.connect(lambda _: load_ticker_max(win.ticker_input.text()))

    # Auto-load initial ticker at startup
    load_ticker_max(win.ticker_input.text())

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

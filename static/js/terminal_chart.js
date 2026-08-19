/**
 * OctoMarket terminal candlestick workspace (Phase 13B).
 * Uses TradingView Lightweight Charts + Phase 13A /api/chart endpoints.
 */
(function (global) {
    'use strict';

    const UP_COLOR = '#00ff88';
    const DOWN_COLOR = '#ff4757';
    const GRID_COLOR = '#333333';
    const BG_COLOR = '#1a1a1a';
    const TEXT_COLOR = '#cccccc';

    function isIntraday(timeframe) {
        const tf = (timeframe || '1d').toLowerCase();
        return /m$/.test(tf) || /h$/.test(tf) || tf === '60m' || tf === '90m';
    }

    function toChartTime(timestamp, timeframe) {
        const dt = new Date(timestamp);
        if (isIntraday(timeframe)) {
            return Math.floor(dt.getTime() / 1000);
        }
        return dt.toISOString().slice(0, 10);
    }

    function barsFromPayload(payload) {
        const count = payload.count || 0;
        const timeframe = payload.timeframe || '1d';
        const candles = [];
        const volume = [];
        for (let i = 0; i < count; i++) {
            const t = toChartTime(payload.timestamps[i], timeframe);
            const o = payload.open[i];
            const h = payload.high[i];
            const l = payload.low[i];
            const c = payload.close[i];
            const v = payload.volume[i] || 0;
            candles.push({ time: t, open: o, high: h, low: l, close: c });
            volume.push({
                time: t,
                value: v,
                color: c >= o ? 'rgba(0,255,136,0.45)' : 'rgba(255,71,87,0.45)',
            });
        }
        return { candles, volume, timeframe };
    }

    class OctoMarketTerminalChart {
        constructor(container, options = {}) {
            this.container = typeof container === 'string'
                ? document.getElementById(container)
                : container;
            this.fetchJson = options.fetchJson || (async (url, opts) => {
                const resp = await fetch(url, {
                    headers: { 'Content-Type': 'application/json' },
                    ...opts,
                });
                return resp.json();
            });
            this.onCrosshair = options.onCrosshair || null;
            this.onClickPrice = options.onClickPrice || null;
            this.symbol = options.symbol || 'AAPL';
            this.timeframe = options.timeframe || '1d';
            this.chart = null;
            this.candleSeries = null;
            this.volumeSeries = null;
            this.priceLines = [];
            this._resizeObserver = null;
            this._initChart();
        }

        _initChart() {
            if (!this.container || !global.LightweightCharts) {
                return;
            }
            this.chart = global.LightweightCharts.createChart(this.container, {
                layout: {
                    background: { type: 'solid', color: BG_COLOR },
                    textColor: TEXT_COLOR,
                },
                grid: {
                    vertLines: { color: GRID_COLOR },
                    horzLines: { color: GRID_COLOR },
                },
                crosshair: { mode: global.LightweightCharts.CrosshairMode.Normal },
                rightPriceScale: { borderColor: GRID_COLOR },
                timeScale: {
                    borderColor: GRID_COLOR,
                    timeVisible: true,
                    secondsVisible: false,
                },
                handleScroll: { mouseWheel: true, pressedMouseMove: true },
                handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
            });

            this.candleSeries = this.chart.addCandlestickSeries({
                upColor: UP_COLOR,
                downColor: DOWN_COLOR,
                borderUpColor: UP_COLOR,
                borderDownColor: DOWN_COLOR,
                wickUpColor: UP_COLOR,
                wickDownColor: DOWN_COLOR,
            });

            this.volumeSeries = this.chart.addHistogramSeries({
                priceFormat: { type: 'volume' },
                priceScaleId: 'volume',
            });

            this.chart.priceScale('volume').applyOptions({
                scaleMargins: { top: 0.82, bottom: 0 },
            });
            this.candleSeries.priceScale().applyOptions({
                scaleMargins: { top: 0.05, bottom: 0.28 },
            });

            this.chart.subscribeCrosshairMove((param) => {
                if (!this.onCrosshair) return;
                if (!param.time || !param.seriesData.size) {
                    this.onCrosshair(null);
                    return;
                }
                const candle = param.seriesData.get(this.candleSeries);
                const vol = param.seriesData.get(this.volumeSeries);
                if (!candle) {
                    this.onCrosshair(null);
                    return;
                }
                this.onCrosshair({
                    time: param.time,
                    open: candle.open,
                    high: candle.high,
                    low: candle.low,
                    close: candle.close,
                    volume: vol ? vol.value : null,
                });
            });

            this.chart.subscribeClick((param) => {
                if (!this.onClickPrice || !param.point) return;
                const price = this.candleSeries.coordinateToPrice(param.point.y);
                if (price != null && Number.isFinite(price)) {
                    this.onClickPrice(Number(price.toFixed(2)));
                }
            });

            this._resizeObserver = new ResizeObserver(() => this.resize());
            this._resizeObserver.observe(this.container);
            this.resize();
        }

        resize() {
            if (!this.chart || !this.container) return;
            this.chart.applyOptions({
                width: this.container.clientWidth,
                height: this.container.clientHeight,
            });
        }

        clearPriceLines() {
            this.priceLines.forEach((line) => {
                try {
                    this.candleSeries.removePriceLine(line);
                } catch (_) { /* ignore */ }
            });
            this.priceLines = [];
        }

        updatePriceLines({ entry, stopLoss, takeProfit } = {}) {
            if (!this.candleSeries) return;
            this.clearPriceLines();
            const specs = [
                { price: entry, color: '#00d4ff', title: 'Entry' },
                { price: stopLoss, color: '#ff4757', title: 'SL' },
                { price: takeProfit, color: '#00ff88', title: 'TP' },
            ];
            specs.forEach(({ price, color, title }) => {
                if (price && Number.isFinite(Number(price))) {
                    const line = this.candleSeries.createPriceLine({
                        price: Number(price),
                        color,
                        lineWidth: 2,
                        lineStyle: title === 'Entry' ? 2 : 0,
                        axisLabelVisible: true,
                        title,
                    });
                    this.priceLines.push(line);
                }
            });
        }

        async syncState(patch) {
            await this.fetchJson('/api/chart/state', {
                method: 'PUT',
                body: JSON.stringify(patch),
            });
        }

        async load(symbol, timeframe) {
            this.symbol = (symbol || this.symbol).toUpperCase();
            this.timeframe = timeframe || this.timeframe;
            await this.syncState({ symbol: this.symbol, timeframe: this.timeframe });

            const url = `/api/chart/${encodeURIComponent(this.symbol)}?timeframe=${encodeURIComponent(this.timeframe)}`;
            const payload = await this.fetchJson(url);
            if (payload.error) {
                throw new Error(payload.error);
            }

            const { candles, volume } = barsFromPayload(payload);
            if (!candles.length) {
                this.candleSeries.setData([]);
                this.volumeSeries.setData([]);
                return payload;
            }

            this.candleSeries.setData(candles);
            this.volumeSeries.setData(volume);
            this.chart.timeScale().fitContent();
            return payload;
        }

        destroy() {
            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
                this._resizeObserver = null;
            }
            if (this.chart) {
                this.chart.remove();
                this.chart = null;
            }
        }
    }

    global.OctoMarketTerminalChart = OctoMarketTerminalChart;
    global.OctoMarketChartBars = { barsFromPayload, toChartTime, isIntraday };
})(typeof window !== 'undefined' ? window : globalThis);

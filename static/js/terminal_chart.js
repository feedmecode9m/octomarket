/**
 * OctoMarket terminal candlestick workspace (Phase 13B/13C).
 * Uses TradingView Lightweight Charts + Phase 13A/13C chart APIs.
 */
(function (global) {
    'use strict';

    const UP_COLOR = '#00ff88';
    const DOWN_COLOR = '#ff4757';
    const GRID_COLOR = '#333333';
    const BG_COLOR = '#1a1a1a';
    const TEXT_COLOR = '#cccccc';

    const OVERLAY_COLORS = {
        SMA20: '#ffa502',
        EMA9: '#00d4ff',
        EMA20: '#a855f7',
        EMA50: '#ff6b81',
        EMA200: '#888888',
        BB: '#6c757d',
    };

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

    function lineDataFromSeries(timestamps, values, timeframe) {
        const data = [];
        for (let i = 0; i < values.length; i++) {
            const val = values[i];
            if (val == null || Number.isNaN(val)) continue;
            data.push({ time: toChartTime(timestamps[i], timeframe), value: val });
        }
        return data;
    }

    function histogramDataFromSeries(timestamps, values, timeframe) {
        const data = [];
        for (let i = 0; i < values.length; i++) {
            const val = values[i];
            if (val == null || Number.isNaN(val)) continue;
            data.push({
                time: toChartTime(timestamps[i], timeframe),
                value: val,
                color: val >= 0 ? 'rgba(0,255,136,0.6)' : 'rgba(255,71,87,0.6)',
            });
        }
        return data;
    }

    function chartTimeToApi(time, timeframe) {
        if (typeof time === 'number') {
            return new Date(time * 1000).toISOString();
        }
        if (typeof time === 'string' && time.length === 10) {
            return `${time}T00:00:00`;
        }
        return String(time);
    }

    function baseChartOptions(height) {
        return {
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
            height,
        };
    }

    class OctoMarketTerminalChart {
        constructor(container, options = {}) {
            this.container = typeof container === 'string'
                ? document.getElementById(container)
                : container;
            this.rsiContainer = options.rsiContainer
                ? (typeof options.rsiContainer === 'string'
                    ? document.getElementById(options.rsiContainer)
                    : options.rsiContainer)
                : null;
            this.macdContainer = options.macdContainer
                ? (typeof options.macdContainer === 'string'
                    ? document.getElementById(options.macdContainer)
                    : options.macdContainer)
                : null;
            this.fetchJson = options.fetchJson || (async (url, opts) => {
                const resp = await fetch(url, {
                    headers: { 'Content-Type': 'application/json' },
                    ...opts,
                });
                return resp.json();
            });
            this.onCrosshair = options.onCrosshair || null;
            this.onClickPrice = options.onClickPrice || null;
            this.onDrawingsChange = options.onDrawingsChange || null;
            this.symbol = options.symbol || 'AAPL';
            this.timeframe = options.timeframe || '1d';
            this.activeIndicators = new Set(options.activeIndicators || []);
            this.drawingTool = null;
            this.drawings = [];
            this.drawingSeries = {};
            this.drawingPriceLines = {};
            this._pendingTrendStart = null;
            this._pendingZoneTop = null;
            this.chart = null;
            this.rsiChart = null;
            this.macdChart = null;
            this.candleSeries = null;
            this.volumeSeries = null;
            this.overlaySeries = {};
            this.rsiSeries = null;
            this.macdLineSeries = null;
            this.macdSignalSeries = null;
            this.macdHistSeries = null;
            this.priceLines = [];
            this._lastCandlePayload = null;
            this._resizeObserver = null;
            this._initChart();
        }

        _initChart() {
            if (!this.container || !global.LightweightCharts) {
                return;
            }
            this.chart = global.LightweightCharts.createChart(
                this.container,
                baseChartOptions(this.container.clientHeight || 300),
            );

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

            this._applyMainScaleMargins();

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
                this._handleChartClick(param);
            });

            this._resizeObserver = new ResizeObserver(() => this.resize());
            this._resizeObserver.observe(this.container);
            if (this.rsiContainer) this._resizeObserver.observe(this.rsiContainer);
            if (this.macdContainer) this._resizeObserver.observe(this.macdContainer);
            this.resize();
        }

        _applyMainScaleMargins() {
            const hasRsi = this.activeIndicators.has('RSI');
            const hasMacd = this.activeIndicators.has('MACD');
            let bottom = 0.28;
            if (hasRsi) bottom += 0.12;
            if (hasMacd) bottom += 0.12;
            this.chart.priceScale('volume').applyOptions({
                scaleMargins: { top: 0.82, bottom: Math.min(bottom, 0.55) },
            });
            this.candleSeries.priceScale().applyOptions({
                scaleMargins: { top: 0.05, bottom: Math.min(bottom + 0.05, 0.6) },
            });
        }

        _ensureSubChart(kind) {
            const isRsi = kind === 'rsi';
            const container = isRsi ? this.rsiContainer : this.macdContainer;
            let chart = isRsi ? this.rsiChart : this.macdChart;
            if (!container) return null;
            if (!chart) {
                chart = global.LightweightCharts.createChart(
                    container,
                    baseChartOptions(container.clientHeight || 90),
                );
                if (isRsi) {
                    this.rsiChart = chart;
                    this.rsiSeries = chart.addLineSeries({ color: '#a855f7', lineWidth: 2 });
                    this.rsiSeries.createPriceLine({ price: 70, color: '#555', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                    this.rsiSeries.createPriceLine({ price: 30, color: '#555', lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
                } else {
                    this.macdChart = chart;
                    this.macdHistSeries = chart.addHistogramSeries({
                        priceFormat: { type: 'volume' },
                        priceScaleId: 'macd-hist',
                    });
                    this.macdLineSeries = chart.addLineSeries({ color: '#00d4ff', lineWidth: 2 });
                    this.macdSignalSeries = chart.addLineSeries({ color: '#ffa502', lineWidth: 1 });
                }
                container.style.display = 'block';
            }
            return chart;
        }

        _hideSubChart(kind) {
            const isRsi = kind === 'rsi';
            const container = isRsi ? this.rsiContainer : this.macdContainer;
            const chart = isRsi ? this.rsiChart : this.macdChart;
            if (chart) {
                chart.remove();
                if (isRsi) {
                    this.rsiChart = null;
                    this.rsiSeries = null;
                } else {
                    this.macdChart = null;
                    this.macdLineSeries = null;
                    this.macdSignalSeries = null;
                    this.macdHistSeries = null;
                }
            }
            if (container) container.style.display = 'none';
        }

        _clearOverlaySeries() {
            Object.keys(this.overlaySeries).forEach((key) => {
                try {
                    this.chart.removeSeries(this.overlaySeries[key]);
                } catch (_) { /* ignore */ }
            });
            this.overlaySeries = {};
        }

        _addOverlayLine(key, data, options = {}) {
            const series = this.chart.addLineSeries({
                color: options.color || OVERLAY_COLORS[key] || '#ffa502',
                lineWidth: options.lineWidth || 2,
                lineStyle: options.lineStyle || 0,
                priceLineVisible: false,
                lastValueVisible: false,
                ...options,
            });
            series.setData(data);
            this.overlaySeries[key] = series;
        }

        resize() {
            if (this.chart && this.container) {
                this.chart.applyOptions({
                    width: this.container.clientWidth,
                    height: this.container.clientHeight,
                });
            }
            if (this.rsiChart && this.rsiContainer) {
                this.rsiChart.applyOptions({
                    width: this.rsiContainer.clientWidth,
                    height: this.rsiContainer.clientHeight,
                });
            }
            if (this.macdChart && this.macdContainer) {
                this.macdChart.applyOptions({
                    width: this.macdContainer.clientWidth,
                    height: this.macdContainer.clientHeight,
                });
            }
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

        setActiveIndicators(keys) {
            this.activeIndicators = new Set(keys);
            this._applyMainScaleMargins();
        }

        setDrawingTool(tool) {
            this.drawingTool = tool || null;
            this._pendingTrendStart = null;
            this._pendingZoneTop = null;
        }

        async _handleChartClick(param) {
            if (!param.point) return;
            const price = this.candleSeries.coordinateToPrice(param.point.y);
            if (price == null || !Number.isFinite(price)) return;

            if (this.drawingTool === 'delete') {
                await this._deleteNearestDrawing(price);
                return;
            }
            if (this.drawingTool === 'horizontal') {
                await this.createDrawing({
                    type: 'horizontal',
                    price: Number(price.toFixed(2)),
                    label: 'Level',
                    color: '#ff4757',
                });
                return;
            }
            if (this.drawingTool === 'trendline') {
                const point = {
                    time: chartTimeToApi(param.time, this.timeframe),
                    price: Number(price.toFixed(2)),
                };
                if (!this._pendingTrendStart) {
                    this._pendingTrendStart = point;
                    return;
                }
                await this.createDrawing({
                    type: 'trendline',
                    start: this._pendingTrendStart,
                    end: point,
                    label: 'Trend',
                    color: '#00d4ff',
                });
                this._pendingTrendStart = null;
                return;
            }
            if (this.drawingTool === 'zone') {
                const level = Number(price.toFixed(2));
                if (this._pendingZoneTop == null) {
                    this._pendingZoneTop = level;
                    return;
                }
                const top = Math.max(this._pendingZoneTop, level);
                const bottom = Math.min(this._pendingZoneTop, level);
                await this.createDrawing({
                    type: 'zone',
                    top,
                    bottom,
                    label: 'Zone',
                    color: 'rgba(0,212,255,0.15)',
                });
                this._pendingZoneTop = null;
                return;
            }
            if (this.onClickPrice) {
                this.onClickPrice(Number(price.toFixed(2)));
            }
        }

        async loadDrawings() {
            const url = `/api/chart/${encodeURIComponent(this.symbol)}/drawings`;
            const payload = await this.fetchJson(url);
            this.drawings = Array.isArray(payload) ? payload : [];
            this.renderDrawings();
            if (this.onDrawingsChange) this.onDrawingsChange(this.drawings);
            return this.drawings;
        }

        async createDrawing(data) {
            const url = `/api/chart/${encodeURIComponent(this.symbol)}/drawings`;
            const resp = await this.fetchJson(url, {
                method: 'POST',
                body: JSON.stringify(data),
            });
            if (resp.error) throw new Error(resp.error);
            await this.loadDrawings();
            return resp.drawing;
        }

        async deleteDrawing(id) {
            const url = `/api/chart/${encodeURIComponent(this.symbol)}/drawings/${encodeURIComponent(id)}`;
            const resp = await this.fetchJson(url, { method: 'DELETE' });
            if (resp.error) throw new Error(resp.error);
            await this.loadDrawings();
        }

        async _deleteNearestDrawing(clickPrice) {
            if (!this.drawings.length) return;
            let best = null;
            let bestDist = Infinity;
            this.drawings.forEach((d) => {
                let dist = Infinity;
                if (d.type === 'horizontal') dist = Math.abs(d.price - clickPrice);
                else if (d.type === 'zone') {
                    const mid = (d.top + d.bottom) / 2;
                    dist = Math.abs(mid - clickPrice);
                } else if (d.type === 'trendline') {
                    const mid = (d.start.price + d.end.price) / 2;
                    dist = Math.abs(mid - clickPrice);
                }
                if (dist < bestDist) {
                    bestDist = dist;
                    best = d;
                }
            });
            if (best && bestDist < clickPrice * 0.05) {
                await this.deleteDrawing(best.id);
            }
        }

        _clearDrawingRender() {
            Object.values(this.drawingSeries).forEach((series) => {
                try { this.chart.removeSeries(series); } catch (_) { /* ignore */ }
            });
            this.drawingSeries = {};
            Object.values(this.drawingPriceLines).forEach((lines) => {
                lines.forEach((line) => {
                    try { this.candleSeries.removePriceLine(line); } catch (_) { /* ignore */ }
                });
            });
            this.drawingPriceLines = {};
        }

        renderDrawings() {
            if (!this.chart || !this.candleSeries) return;
            this._clearDrawingRender();
            this.drawings.forEach((d) => {
                if (d.type === 'horizontal') {
                    const line = this.candleSeries.createPriceLine({
                        price: d.price,
                        color: d.color || '#ff4757',
                        lineWidth: 2,
                        axisLabelVisible: true,
                        title: d.label || 'Level',
                    });
                    this.drawingPriceLines[d.id] = [line];
                } else if (d.type === 'zone') {
                    const topLine = this.candleSeries.createPriceLine({
                        price: d.top,
                        color: '#00d4ff',
                        lineWidth: 1,
                        lineStyle: 2,
                        axisLabelVisible: true,
                        title: d.label ? `${d.label} top` : 'Zone top',
                    });
                    const bottomLine = this.candleSeries.createPriceLine({
                        price: d.bottom,
                        color: '#00d4ff',
                        lineWidth: 1,
                        lineStyle: 2,
                        axisLabelVisible: true,
                        title: d.label ? `${d.label} bottom` : 'Zone bottom',
                    });
                    this.drawingPriceLines[d.id] = [topLine, bottomLine];
                } else if (d.type === 'trendline') {
                    const series = this.chart.addLineSeries({
                        color: d.color || '#00d4ff',
                        lineWidth: 2,
                        priceLineVisible: false,
                        lastValueVisible: false,
                    });
                    series.setData([
                        { time: toChartTime(d.start.time, this.timeframe), value: d.start.price },
                        { time: toChartTime(d.end.time, this.timeframe), value: d.end.price },
                    ]);
                    this.drawingSeries[d.id] = series;
                }
            });
        }

        async syncState(patch) {
            await this.fetchJson('/api/chart/state', {
                method: 'PUT',
                body: JSON.stringify(patch),
            });
        }

        async loadIndicators() {
            if (!this.activeIndicators.size || !this._lastCandlePayload) {
                this._clearOverlaySeries();
                this._hideSubChart('rsi');
                this._hideSubChart('macd');
                return null;
            }
            const list = Array.from(this.activeIndicators).join(',');
            const url = `/api/chart/${encodeURIComponent(this.symbol)}/indicators?timeframe=${encodeURIComponent(this.timeframe)}&indicators=${encodeURIComponent(list)}`;
            const payload = await this.fetchJson(url);
            if (payload.error) {
                throw new Error(payload.error);
            }
            this.applyIndicatorPayload(payload);
            return payload;
        }

        applyIndicatorPayload(payload) {
            const tf = payload.timeframe || this.timeframe;
            const ts = payload.timestamps || [];
            const ind = payload.indicators || {};

            this._clearOverlaySeries();
            if (!this.activeIndicators.has('RSI')) this._hideSubChart('rsi');
            if (!this.activeIndicators.has('MACD')) this._hideSubChart('macd');
            this._applyMainScaleMargins();

            Object.keys(ind).forEach((key) => {
                const item = ind[key];
                if (!this.activeIndicators.has(key) && !this.activeIndicators.has(item.indicator)) {
                    return;
                }
                if (item.indicator === 'SMA' || item.indicator === 'EMA') {
                    const data = lineDataFromSeries(ts, item.values || [], tf);
                    this._addOverlayLine(key, data, { color: OVERLAY_COLORS[key] });
                }
                if (item.indicator === 'BB') {
                    ['upper', 'middle', 'lower'].forEach((band, idx) => {
                        const data = lineDataFromSeries(ts, item[band] || [], tf);
                        this._addOverlayLine(`${key}_${band}`, data, {
                            color: OVERLAY_COLORS.BB,
                            lineWidth: 1,
                            lineStyle: idx === 1 ? 0 : 2,
                        });
                    });
                }
            });

            if (this.activeIndicators.has('RSI') && ind.RSI) {
                const chart = this._ensureSubChart('rsi');
                const data = lineDataFromSeries(ts, ind.RSI.values || [], tf);
                if (this.rsiSeries) this.rsiSeries.setData(data);
                if (chart) chart.timeScale().fitContent();
            }

            if (this.activeIndicators.has('MACD') && ind.MACD) {
                const chart = this._ensureSubChart('macd');
                const macd = ind.MACD;
                if (this.macdLineSeries) {
                    this.macdLineSeries.setData(lineDataFromSeries(ts, macd.macd || [], tf));
                }
                if (this.macdSignalSeries) {
                    this.macdSignalSeries.setData(lineDataFromSeries(ts, macd.signal || [], tf));
                }
                if (this.macdHistSeries) {
                    this.macdHistSeries.setData(histogramDataFromSeries(ts, macd.histogram || [], tf));
                }
                if (chart) chart.timeScale().fitContent();
            }
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

            this._lastCandlePayload = payload;
            const { candles, volume } = barsFromPayload(payload);
            if (!candles.length) {
                this.candleSeries.setData([]);
                this.volumeSeries.setData([]);
                await this.loadIndicators();
                await this.loadDrawings();
                return payload;
            }

            this.candleSeries.setData(candles);
            this.volumeSeries.setData(volume);
            this.chart.timeScale().fitContent();
            await this.loadIndicators();
            await this.loadDrawings();
            return payload;
        }

        destroy() {
            this._clearDrawingRender();
            if (this._resizeObserver) {
                this._resizeObserver.disconnect();
                this._resizeObserver = null;
            }
            this._hideSubChart('rsi');
            this._hideSubChart('macd');
            if (this.chart) {
                this.chart.remove();
                this.chart = null;
            }
        }
    }

    global.OctoMarketTerminalChart = OctoMarketTerminalChart;
    global.OctoMarketChartBars = { barsFromPayload, toChartTime, isIntraday, lineDataFromSeries };
})(typeof window !== 'undefined' ? window : globalThis);

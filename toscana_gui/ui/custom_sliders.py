from __future__ import annotations

from typing import ClassVar

import panel as pn
import param


class ToscanaRangeSlider(pn.reactive.ReactiveHTML):
    """Dual-handle range slider implemented without Bokeh/noUiSlider."""

    # Using param.List because ReactiveHTML syncs JS arrays as Python lists.
    # Tuple parameter validation fails when receiving a list from the client.
    value = param.List(default=[0.0, 1.0], bounds=(2, 2))
    value_throttled = param.List(default=[0.0, 1.0], bounds=(2, 2))

    start = param.Number(default=0.0)
    end = param.Number(default=1.0)
    step = param.Number(default=1.0)

    orientation = param.ObjectSelector(default="horizontal", objects=["horizontal", "vertical"])
    label_display = param.ObjectSelector(default="none", objects=["none", "flex"])
    lower_label = param.String(default="Start")
    upper_label = param.String(default="End")
    disabled = param.Boolean(default=False)

    _template: ClassVar[str] = """
 <div id="root" class="toscana-range-slider toscana-range-slider--${orientation}" data-disabled="${disabled}">
  <div id="labels" class="toscana-range-slider__labels" style="display: ${label_display};">
    <div id="lower_text" class="toscana-range-slider__label"></div>
    <div id="upper_text" class="toscana-range-slider__label"></div>
  </div>
  <div id="track" class="toscana-range-slider__track" onpointerdown="${script('start_track_drag')}">
    <div id="connect" class="toscana-range-slider__connect"></div>
    <div id="lower_handle" class="toscana-range-slider__handle" onpointerdown="${script('start_lower_drag')}" role="slider" tabindex="0"></div>
    <div id="upper_handle" class="toscana-range-slider__handle" onpointerdown="${script('start_upper_drag')}" role="slider" tabindex="0"></div>
  </div>
</div>
"""

    _stylesheets: ClassVar[list[str]] = [
        """
:host {
  display: block;
  box-sizing: border-box;
  direction: ltr;
}

.toscana-range-slider {
  box-sizing: border-box;
  height: 100%;
  width: 100%;
  user-select: none;
  touch-action: none;
  direction: ltr;
}

.toscana-range-slider__labels {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: rgba(15, 23, 42, 0.95);
  font-family: inherit;
  font-size: 0.86rem;
  font-weight: 700;
  line-height: 1.1;
  pointer-events: none;
}

/* Hide labels container if display is 'none' to avoid layout artifacts */
.toscana-range-slider__labels[style*="display: none"] {
  display: none !important;
}

.toscana-range-slider__track {
  position: relative;
  box-sizing: border-box;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.62);
  cursor: pointer;
  touch-action: none;
}

.toscana-range-slider__connect {
  position: absolute;
  box-sizing: border-box;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.38);
  pointer-events: none;
}

.toscana-range-slider__handle {
  position: absolute;
  box-sizing: border-box;
  width: 14px;
  height: 14px;
  border-radius: 4px;
  background: rgb(31, 31, 31);
  border: 1px solid rgba(255, 255, 255, 0.92);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.22);
  cursor: grab;
  outline: none;
  touch-action: none;
  z-index: 2;
}

.toscana-range-slider__handle:active {
  cursor: grabbing;
}

.toscana-range-slider--horizontal {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.toscana-range-slider--horizontal .toscana-range-slider__labels {
  flex-direction: row;
  margin-bottom: 6px;
  width: calc(100% - 40px);
  margin-left: 14px;
  margin-right: 26px;
}

.toscana-range-slider--horizontal .toscana-range-slider__track {
  height: 3px;
  width: calc(100% - 40px);
  margin: 10px 26px 8px 14px;
}

.toscana-range-slider--horizontal .toscana-range-slider__connect {
  top: 0;
  height: 100%;
}

.toscana-range-slider--horizontal .toscana-range-slider__handle {
  top: 50%;
  transform: translate(-50%, -50%);
}

.toscana-range-slider--vertical {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
}

.toscana-range-slider--vertical .toscana-range-slider__labels {
  flex-direction: column;
  height: calc(100% - 20px);
  margin-right: 12px;
  min-width: 90px;
  align-items: flex-end;
}

.toscana-range-slider--vertical .toscana-range-slider__track {
  width: 3px;
  height: calc(100% - 20px);
  margin: 10px 0;
}

.toscana-range-slider--vertical .toscana-range-slider__connect {
  left: 0;
  width: 100%;
}

 .toscana-range-slider--vertical .toscana-range-slider__handle {
   left: 50%;
   transform: translate(-50%, -50%);
 }

 .toscana-range-slider[data-disabled="true"] .toscana-range-slider__track,
 .toscana-range-slider[data-disabled="true"] .toscana-range-slider__handle {
   pointer-events: none;
   cursor: default;
 }

 .toscana-range-slider[data-disabled="true"] {
   opacity: 0.92;
 }
 """
     ]

    _scripts: ClassVar[dict[str, str]] = {
        "render": """
          if (!state.initialized) {
            state.clamp = (v, min, max) => Math.min(Math.max(v, min), max);
            
            state.getEl = (id) => {
              try {
                if (id === 'root' && typeof root !== 'undefined') return root;
                if (id === 'track' && typeof track !== 'undefined') return track;
                if (id === 'lower_text' && typeof lower_text !== 'undefined') return lower_text;
                if (id === 'upper_text' && typeof upper_text !== 'undefined') return upper_text;
                if (id === 'lower_handle' && typeof lower_handle !== 'undefined') return lower_handle;
                if (id === 'upper_handle' && typeof upper_handle !== 'undefined') return upper_handle;
                if (id === 'connect' && typeof connect !== 'undefined') return connect;
              } catch (e) {}
              
              const container = (typeof self !== 'undefined') ? (self.node || self.el) : null;
              if (container && typeof container.querySelector === 'function') {
                return container.id === id ? container : container.querySelector(`#${id}`);
              }
              return null;
            };

            state.bounds = () => {
              const start = Number.isFinite(data.start) ? data.start : 0;
              let end = Number.isFinite(data.end) ? data.end : start + 1;
              if (end <= start) end = start + 1;
              return [start, end];
            };

            state.precision = () => {
              const text = String(data.step ?? "");
              if (!text.includes(".")) return 8;
              return Math.min(Math.max(text.split(".")[1].length, 0), 10);
            };

            state.normalizeValue = (v) => {
              const [start, end] = state.bounds();
              const step = Number.isFinite(data.step) ? data.step : 0;
              let val = state.clamp(v, start, end);
              if (step > 0) {
                val = start + Math.round((val - start) / step) * step;
              }
              return Number(state.clamp(val, start, end).toFixed(state.precision()));
            };

            state.normalizePair = (pair) => {
              const [start, end] = state.bounds();
              const raw = Array.isArray(pair) ? pair : [start, end];
              let low = state.normalizeValue(raw[0]);
              let high = state.normalizeValue(raw[1]);
              if (high < low) [low, high] = [high, low];
              return [low, high];
            };

            state.valueFromEvent = (ev) => {
              const trackEl = state.getEl('track');
              if (!trackEl) return data.start;
              const rect = trackEl.getBoundingClientRect();
              if (rect.width === 0 || rect.height === 0) return data.start;
              
              const [start, end] = state.bounds();
              let pct;
              if (data.orientation === "vertical") {
                pct = 1 - (ev.clientY - rect.top) / rect.height;
              } else {
                pct = (ev.clientX - rect.left) / rect.width;
              }
              return state.normalizeValue(start + pct * (end - start));
            };

            state.update = () => {
              const pair = state.normalizePair(data.value);
              const [low, high] = pair;
              const [start, end] = state.bounds();
              const range = end - start;
              const lowPct = range === 0 ? 0 : (low - start) / range * 100;
              const highPct = range === 0 ? 0 : (high - start) / range * 100;

              const l_text = state.getEl('lower_text');
              const u_text = state.getEl('upper_text');
              const l_handle = state.getEl('lower_handle');
              const u_handle = state.getEl('upper_handle');
              const conn = state.getEl('connect');

              const fmt = (v) => {
                const p = state.precision();
                return Number.isInteger(v) ? String(v) : v.toFixed(p);
              };

              if (l_text) l_text.textContent = `${data.lower_label}: ${fmt(low)}`;
              if (u_text) u_text.textContent = `${data.upper_label}: ${fmt(high)}`;

              if (l_handle) {
                const pos = data.orientation === 'vertical' ? (100 - lowPct) : lowPct;
                l_handle.style[data.orientation === 'vertical' ? 'top' : 'left'] = `${pos}%`;
              }
              if (u_handle) {
                const pos = data.orientation === 'vertical' ? (100 - highPct) : highPct;
                u_handle.style[data.orientation === 'vertical' ? 'top' : 'left'] = `${pos}%`;
              }
              
              if (conn) {
                if (data.orientation === 'vertical') {
                   conn.style.top = `${100 - highPct}%`;
                   conn.style.height = `${Math.max(0, highPct - lowPct)}%`;
                   conn.style.left = '0';
                   conn.style.width = '100%';
                } else {
                   conn.style.left = `${lowPct}%`;
                   conn.style.width = `${Math.max(0, highPct - lowPct)}%`;
                   conn.style.top = '0';
                   conn.style.height = '100%';
                }
              }
            };

             state.beginDrag = (ev, handleType) => {
               if (data.disabled) return;
               if (!ev) return;
               ev.preventDefault();
               ev.stopPropagation();

              const rootEl = state.getEl('root');
              if (!rootEl) return;

              const pointerId = ev.pointerId;
              if (typeof rootEl.setPointerCapture === 'function') {
                rootEl.setPointerCapture(pointerId);
              }

              state.dragging = true;
              if (handleType === "nearest") {
                const val = state.valueFromEvent(ev);
                const pair = state.normalizePair(data.value);
                state.activeHandle = Math.abs(val - pair[0]) <= Math.abs(val - pair[1]) ? "lower" : "upper";
              } else {
                state.activeHandle = handleType;
              }

              const updateFromEvent = (e) => {
                const val = state.valueFromEvent(e);
                const pair = state.normalizePair(data.value);
                if (state.activeHandle === "upper") pair[1] = Math.max(val, pair[0]);
                else pair[0] = Math.min(val, pair[1]);
                data.value = state.normalizePair(pair);
                state.update();
              };

              updateFromEvent(ev);

              const onMove = (e) => {
                if (e.pointerId !== pointerId) return;
                updateFromEvent(e);
              };

              const onUp = (e) => {
                if (e.pointerId !== pointerId) return;
                updateFromEvent(e);
                data.value_throttled = state.normalizePair(data.value);
                state.dragging = false;
                if (typeof rootEl.releasePointerCapture === 'function') {
                  rootEl.releasePointerCapture(pointerId);
                }
                rootEl.removeEventListener("pointermove", onMove);
                rootEl.removeEventListener("pointerup", onUp);
              };

              rootEl.addEventListener("pointermove", onMove);
              rootEl.addEventListener("pointerup", onUp);
            };

            state.initialized = true;
          }
          state.update();
        """,
        "after_layout": "if (state.update) state.update();",
        "value": "if (state.update && !state.dragging) state.update();",
        "start": "if (state.update) state.update();",
        "end": "if (state.update) state.update();",
        "step": "if (state.update) state.update();",
        "orientation": "if (state.update) state.update();",
        "start_lower_drag": "if (state.beginDrag) state.beginDrag(event, 'lower');",
        "start_upper_drag": "if (state.beginDrag) state.beginDrag(event, 'upper');",
        "start_track_drag": "if (state.beginDrag) state.beginDrag(event, 'nearest');",
    }

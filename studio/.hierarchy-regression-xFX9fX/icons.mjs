import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
export function Icon({ name, size = 18, style }) {
    const paths = {
        arrow: _jsx(_Fragment, { children: _jsx("path", { d: "m5 3 13 8-6 2-2 6Z" }) }),
        hand: _jsx(_Fragment, { children: _jsx("path", { d: "M8 12V6a2 2 0 0 1 4 0v5-7a2 2 0 0 1 4 0v7-5a2 2 0 0 1 4 0v9c0 4-3 7-7 7h-1c-2 0-4-1-5-3l-4-6a2 2 0 0 1 3-2l2 2" }) }),
        undo: _jsx(_Fragment, { children: _jsx("path", { d: "M3 10h11a6 6 0 0 1 0 12M3 10l5-5M3 10l5 5" }) }),
        redo: _jsx(_Fragment, { children: _jsx("path", { d: "M21 10H10a6 6 0 0 0 0 12M21 10l-5-5M21 10l-5 5" }) }),
        save: _jsxs(_Fragment, { children: [_jsx("path", { d: "M5 3h12l4 4v14H3V3h2Z" }), _jsx("path", { d: "M7 3v6h10V3M7 21v-8h10v8" })] }),
        export: _jsx(_Fragment, { children: _jsx("path", { d: "M12 16V3m-5 5 5-5 5 5M4 14v7h16v-7" }) }),
        fit: _jsxs(_Fragment, { children: [_jsx("path", { d: "M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5" }), _jsx("rect", { x: "7", y: "7", width: "10", height: "10", rx: "1" })] }),
        plus: _jsx("path", { d: "M12 5v14M5 12h14" }),
        minus: _jsx("path", { d: "M5 12h14" }),
        chevron: _jsx("path", { d: "m9 5 7 7-7 7" }),
        code: _jsx(_Fragment, { children: _jsx("path", { d: "m7 7-5 5 5 5m10-10 5 5-5 5m-3-14-4 18" }) }),
        layers: _jsx(_Fragment, { children: _jsx("path", { d: "m12 3 10 6-10 6L2 9Zm-9 10 9 5 9-5m-18 5 9 5 9-5" }) }),
        pin: _jsx(_Fragment, { children: _jsx("path", { d: "m8 3 8 0-1 6 4 4H5l4-4Zm4 10v9" }) }),
        align: _jsxs(_Fragment, { children: [_jsx("path", { d: "M5 3v18" }), _jsx("rect", { x: "8", y: "5", width: "11", height: "5", rx: "1" }), _jsx("rect", { x: "8", y: "14", width: "8", height: "5", rx: "1" })] }),
        close: _jsx("path", { d: "m6 6 12 12M18 6 6 18" }),
        check: _jsx("path", { d: "m5 12 4 4L19 6" }),
        info: _jsxs(_Fragment, { children: [_jsx("circle", { cx: "12", cy: "12", r: "9" }), _jsx("path", { d: "M12 11v6M12 7v1" })] }),
        file: _jsxs(_Fragment, { children: [_jsx("path", { d: "M5 3h9l5 5v13H5Z" }), _jsx("path", { d: "M14 3v6h5M8 13h8M8 17h6" })] }),
        message: _jsxs(_Fragment, { children: [_jsx("path", { d: "M4 4h16v12H9l-5 4Z" }), _jsx("path", { d: "M8 8h8M8 12h5" })] }),
        grid: _jsxs(_Fragment, { children: [_jsx("rect", { x: "3", y: "3", width: "7", height: "7", rx: "1" }), _jsx("rect", { x: "14", y: "3", width: "7", height: "7", rx: "1" }), _jsx("rect", { x: "3", y: "14", width: "7", height: "7", rx: "1" }), _jsx("rect", { x: "14", y: "14", width: "7", height: "7", rx: "1" })] }),
    };
    return _jsx("svg", { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.6", strokeLinecap: "round", strokeLinejoin: "round", style: style, "aria-hidden": "true", children: paths[name] ?? paths.file });
}

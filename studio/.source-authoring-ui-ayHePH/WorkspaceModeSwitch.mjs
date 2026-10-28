import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
export function WorkspaceModeSwitch({ mode, disabled, onView, onEdit }) {
    return _jsxs("div", { className: "workspace-mode-switch", role: "group", "aria-label": "\u5DE5\u4F5C\u533A\u6A21\u5F0F", children: [_jsx("button", { type: "button", "aria-pressed": mode === 'view', disabled: disabled, onClick: onView, children: "\u89C6\u56FE" }), _jsx("button", { type: "button", "aria-pressed": mode === 'edit', disabled: disabled, onClick: onEdit, children: "\u7F16\u8F91" })] });
}

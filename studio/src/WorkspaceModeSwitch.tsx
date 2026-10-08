export function WorkspaceModeSwitch({ mode, disabled, onView, onEdit }: {
  mode: 'view' | 'edit'; disabled?: boolean; onView: () => void; onEdit: () => void;
}) {
  return <div className="workspace-mode-switch" role="group" aria-label="工作区模式">
    <button type="button" aria-pressed={mode === 'view'} disabled={disabled} onClick={onView}>视图</button>
    <button type="button" aria-pressed={mode === 'edit'} disabled={disabled} onClick={onEdit}>编辑</button>
  </div>;
}

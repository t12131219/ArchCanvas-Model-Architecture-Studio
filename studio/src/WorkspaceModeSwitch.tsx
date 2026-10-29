import { t } from './i18n';
export function WorkspaceModeSwitch({ mode, disabled, onView, onEdit }: {
  mode: 'view' | 'edit'; disabled?: boolean; onView: () => void; onEdit: () => void;
}) {
  return <div className="workspace-mode-switch" role="group" aria-label={t("工作区模式")}>
    <button type="button" aria-pressed={mode === 'view'} disabled={disabled} onClick={onView}>{t("视图")}</button>
    <button type="button" aria-pressed={mode === 'edit'} disabled={disabled} onClick={onEdit}>{t("编辑")}</button>
  </div>;
}

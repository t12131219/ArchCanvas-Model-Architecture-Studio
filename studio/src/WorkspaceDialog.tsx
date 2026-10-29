import { t } from './i18n';
import type { ReactNode } from 'react';
import { useModalFocus } from './WorkspaceUI';
import { Icon } from './icons';

/** Task tools share the existing preview; opening a tool never remounts it. */
export function WorkspaceDialog({ title, description, children, onClose }: {
  title: string; description: string; children: ReactNode; onClose: () => void;
}) {
  const panel = useModalFocus<HTMLDivElement>(onClose);
  return <div className="modal-backdrop workspace-dialog-backdrop" onClick={event => {
    if (event.target === event.currentTarget) onClose();
  }}>
    <div ref={panel} className="workspace-dialog" role="dialog" aria-modal="true" aria-labelledby="workspace-dialog-title" aria-describedby="workspace-dialog-description">
      <div className="modal-heading"><div><h2 id="workspace-dialog-title">{title}</h2><p id="workspace-dialog-description">{description}</p></div>
        <button className="tool" aria-label={t("关闭{0}", {"0": title})} onClick={onClose}><Icon name="close" size={18} /></button>
      </div>
      <div className="workspace-dialog-content">{children}</div>
    </div>
  </div>;
}

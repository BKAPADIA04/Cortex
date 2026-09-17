"use client";

type ConfirmDialogProps = {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" role="alertdialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <p className="modal-title">{title}</p>
        {description && <p className="modal-description">{description}</p>}
        <div className="modal-actions">
          <button type="button" className="modal-btn" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`modal-btn ${danger ? "modal-btn-danger" : "modal-btn-primary"}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

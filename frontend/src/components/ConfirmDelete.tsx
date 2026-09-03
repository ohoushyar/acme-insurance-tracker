export function ConfirmDelete({
  label,
  warning,
  onConfirm,
  onCancel,
}: {
  label: string;
  warning?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="confirm-delete">
      {warning ? <p className="confirm-copy">{warning}</p> : null}
      <div className="card-actions">
        <button
          className="btn-quiet"
          type="button"
          aria-label={`Confirm delete ${label}`}
          onClick={() => onConfirm()}
        >
          Confirm delete
        </button>
        <button className="btn-quiet" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

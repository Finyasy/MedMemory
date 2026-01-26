import type { LocalizationBox } from '../types';

type LocalizationModalProps = {
  imageUrl: string;
  boxes: LocalizationBox[];
  onClose: () => void;
};

const LocalizationModal = ({ imageUrl, boxes, onClose }: LocalizationModalProps) => {
  return (
    <div className="modal-overlay localization-overlay" onClick={onClose}>
      <div className="modal-content localization-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Localization Preview</h2>
          <button className="modal-close" type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="localization-body">
          <div className="localization-canvas">
            <img src={imageUrl} alt="Localization source" />
            {boxes.map((box, index) => (
              <div
                key={`${box.label}-${index}`}
                className="localization-box"
                style={{
                  left: `${box.x_min_norm * 100}%`,
                  top: `${box.y_min_norm * 100}%`,
                  width: `${Math.max(0, box.x_max_norm - box.x_min_norm) * 100}%`,
                  height: `${Math.max(0, box.y_max_norm - box.y_min_norm) * 100}%`,
                }}
              >
                <span className="localization-label">
                  {box.label} · {Math.round(box.confidence * 100)}%
                </span>
              </div>
            ))}
          </div>
          {boxes.length === 0 ? (
            <p className="localization-empty">No boxes detected.</p>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default LocalizationModal;

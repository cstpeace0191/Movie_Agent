import React, { ChangeEvent, useRef } from 'react';
import { Translation } from '../i18n';

export interface PhotoItem {
  id: string;
  file: File;
  previewUrl: string;
  caption: string;
}

interface PhotoListProps {
  photos: PhotoItem[];
  onAddPhotos: (files: File[]) => void;
  onReplacePhoto: (index: number, file: File) => void;
  onUpdateCaption: (index: number, caption: string) => void;
  onRemovePhoto: (index: number) => void;
  onMovePhoto: (index: number, direction: 'up' | 'down') => void;
  onClearAll: () => void;
  t: Translation;
  secondsPerShot: number;
}

export const PhotoList: React.FC<PhotoListProps> = ({
  photos,
  onAddPhotos,
  onReplacePhoto,
  onUpdateCaption,
  onRemovePhoto,
  onMovePhoto,
  onClearAll,
  t,
  secondsPerShot,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddPhotos(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="photo-list-container" id="registered-photos-section">
      <div className="photo-list-header">
        <h3 style={{ margin: 0, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {t.photoListTitle.replace('{count}', String(photos.length))}
        </h3>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp"
            style={{ display: 'none' }}
            onChange={handleFileChange}
            id="add-photos-hidden-input"
          />
          <button
            type="button"
            className="btn-secondary"
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
            onClick={() => fileInputRef.current?.click()}
          >
            {t.addMorePhotosBtn}
          </button>
          {photos.length > 0 && (
            <button
              type="button"
              className="btn-stop"
              style={{ padding: '0.35rem 0.75rem', fontSize: '0.85rem' }}
              onClick={onClearAll}
            >
              {t.clearAllPhotosBtn}
            </button>
          )}
        </div>
      </div>

      {photos.length === 0 ? (
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', margin: '0.5rem 0' }}>
          {t.noPhotosUploaded}
        </p>
      ) : (
        <>
          <div className="photo-cards">
            {photos.map((item, idx) => (
              <div key={item.id} className="photo-card" id={`photo-card-${idx}`}>
                <div className="photo-card-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span className="photo-badge">
                      {t.photoSceneBadge.replace('{num}', String(idx + 1))}
                    </span>
                    <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                      {item.file.name}
                    </strong>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      ({formatSize(item.file.size)})
                    </span>
                  </div>

                  <div className="photo-card-actions">
                    <input
                      id={`replace-photo-input-${idx}`}
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          onReplacePhoto(idx, e.target.files[0]);
                          e.target.value = '';
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                      onClick={() => document.getElementById(`replace-photo-input-${idx}`)?.click()}
                      title={t.replacePhotoBtn}
                    >
                      🔄 {t.replacePhotoBtn}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                      disabled={idx === 0}
                      onClick={() => onMovePhoto(idx, 'up')}
                      title={t.moveUpBtn}
                    >
                      ▲ {t.moveUpBtn}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                      disabled={idx === photos.length - 1}
                      onClick={() => onMovePhoto(idx, 'down')}
                      title={t.moveDownBtn}
                    >
                      ▼ {t.moveDownBtn}
                    </button>
                    <button
                      type="button"
                      className="btn-stop"
                      style={{ padding: '0.2rem 0.5rem', fontSize: '0.75rem' }}
                      onClick={() => onRemovePhoto(idx)}
                      title={t.removePhotoBtn}
                    >
                      ✕ {t.removePhotoBtn}
                    </button>
                  </div>
                </div>

                <div className="photo-card-body">
                  <img
                    src={item.previewUrl}
                    alt={item.file.name}
                    className="photo-thumb"
                  />
                  <div className="photo-caption-box">
                    <label
                      htmlFor={`photo-caption-input-${idx}`}
                      style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 600 }}
                    >
                      💬 {t.photoCaptionLabel}
                    </label>
                    <input
                      id={`photo-caption-input-${idx}`}
                      type="text"
                      value={item.caption}
                      onChange={(e) => onUpdateCaption(idx, e.target.value)}
                      placeholder={t.photoCaptionPlaceholder}
                      maxLength={500}
                      style={{ width: '100%', boxSizing: 'border-box' }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'flex-end', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {item.caption.length} / 500
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '0.75rem', padding: '0.5rem', backgroundColor: '#0f172a', borderRadius: '4px', fontSize: '0.85rem', color: 'var(--accent)' }}>
            🎬 {t.includeAllPhotosDescTrue
              .replace('{count}', String(photos.length))
              .replace('{seconds}', String(secondsPerShot))
              .replace('{total}', (photos.length * secondsPerShot).toFixed(1))}
          </div>
        </>
      )}
    </div>
  );
};


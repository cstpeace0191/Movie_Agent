import { TRANSITIONS, CAPTION_POSITIONS, type Transition, type CaptionPosition } from '../types';
import type { Translation } from '../i18n';

export const TRANSITION_SECONDS_MIN = 0.1;
export const TRANSITION_SECONDS_MAX = 2.0;

/** Returns a text error for an invalid transition length, or '' when valid (FR-042). */
export function transitionSecondsError(value: number, t: Translation): string {
  if (!Number.isFinite(value) || value < TRANSITION_SECONDS_MIN || value > TRANSITION_SECONDS_MAX) {
    return t.transitionSecondsError;
  }
  return '';
}

interface Props {
  t: Translation;
  transition: Transition;
  transitionSeconds: number;
  captionPosition: CaptionPosition;
  onTransitionChange: (value: Transition) => void;
  onTransitionSecondsChange: (value: number) => void;
  onCaptionPositionChange: (value: CaptionPosition) => void;
}

/** Render options for scene transitions and caption positions. */
export function RenderOptions({
  t,
  transition,
  transitionSeconds,
  captionPosition,
  onTransitionChange,
  onTransitionSecondsChange,
  onCaptionPositionChange,
}: Props) {
  const secondsError = transitionSecondsError(transitionSeconds, t);
  const lengthDisabled = transition === 'none';

  return (
    <fieldset className="form-group render-options" id="render-options">
      <legend>{t.renderOptionsTitle}</legend>
      <div className="options-grid">
        <div className="form-group">
          <label htmlFor="opt-transition">{t.transitionLabel}</label>
          <select
            id="opt-transition"
            name="transition"
            value={transition}
            onChange={(e) => onTransitionChange(e.target.value as Transition)}
          >
            {TRANSITIONS.map((name) => (
              <option key={name} value={name}>
                {t.transitionNames[name]}
              </option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="opt-transition-seconds">{t.transitionSecondsLabel}</label>
          <input
            id="opt-transition-seconds"
            name="transition_seconds"
            type="number"
            step="0.1"
            min={TRANSITION_SECONDS_MIN}
            max={TRANSITION_SECONDS_MAX}
            value={transitionSeconds}
            disabled={lengthDisabled}
            aria-describedby="opt-transition-seconds-hint opt-transition-seconds-error"
            aria-invalid={secondsError ? true : undefined}
            onChange={(e) => onTransitionSecondsChange(Number(e.target.value))}
          />
          <p id="opt-transition-seconds-hint" className="hint">
            {t.transitionSecondsHint}
          </p>
          {secondsError && !lengthDisabled && (
            <p id="opt-transition-seconds-error" className="field-error" role="alert">
              {secondsError}
            </p>
          )}
        </div>
        <div className="form-group" style={{ gridColumn: '1 / -1' }}>
          <label htmlFor="opt-caption-position">{t.captionPositionLabel}</label>
          <select
            id="opt-caption-position"
            name="caption_position"
            value={captionPosition}
            onChange={(e) => onCaptionPositionChange(e.target.value as CaptionPosition)}
          >
            {CAPTION_POSITIONS.map((pos) => (
              <option key={pos} value={pos}>
                {t.captionPositions[pos] || pos}
              </option>
            ))}
          </select>
          <p id="opt-caption-position-hint" className="hint">
            {t.captionPositionHint}
          </p>
        </div>
      </div>
    </fieldset>
  );
}

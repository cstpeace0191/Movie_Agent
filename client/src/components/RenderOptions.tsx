import { TRANSITIONS, type Transition } from '../types';
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
  onTransitionChange: (value: Transition) => void;
  onTransitionSecondsChange: (value: number) => void;
}

/** Render options for feature 002, User Story 1: scene transition style and length. */
export function RenderOptions({
  t,
  transition,
  transitionSeconds,
  onTransitionChange,
  onTransitionSecondsChange,
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
      </div>
    </fieldset>
  );
}

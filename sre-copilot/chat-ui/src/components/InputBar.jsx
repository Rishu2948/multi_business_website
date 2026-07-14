/**
 * InputBar — textarea + submit button with inline validation.
 *
 * Behaviours (Requirements 6.2, 6.6, 6.7):
 *   - Rejects empty / whitespace-only input with "Message cannot be empty".
 *   - Rejects questions longer than 2000 characters with "Maximum 2000 characters".
 *   - Disables the submit button and textarea while `isLoading` is true.
 *   - Shows a LoadingIndicator inline with the submit button while loading.
 *   - Textarea auto-resizes as the user types.
 *   - Submits on Enter (without Shift) for power-user ergonomics; Shift+Enter
 *     inserts a newline.
 *
 * @param {{
 *   inputValue: string,
 *   setInputValue: (value: string) => void,
 *   submitQuestion: () => Promise<void>,
 *   isLoading: boolean,
 *   inputDisabled: boolean,
 *   validationError: string | null,
 * }} props
 */

import { useRef, useEffect, useCallback } from 'react';
import LoadingIndicator from './LoadingIndicator.jsx';
import { MAX_QUESTION_LENGTH } from '../hooks/useChat.js';

export default function InputBar({
  inputValue,
  setInputValue,
  submitQuestion,
  isLoading,
  inputDisabled,
  validationError,
}) {
  const textareaRef = useRef(null);

  // Auto-resize the textarea to fit its content as the user types.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    // Reset to 'auto' first so shrinking works correctly.
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, [inputValue]);

  // Re-focus the textarea once the input is re-enabled after submission.
  useEffect(() => {
    if (!inputDisabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [inputDisabled]);

  const handleChange = useCallback(
    (e) => setInputValue(e.target.value),
    [setInputValue]
  );

  const handleKeyDown = useCallback(
    (e) => {
      // Submit on Enter without Shift; Shift+Enter adds a newline.
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!inputDisabled) {
          submitQuestion();
        }
      }
    },
    [inputDisabled, submitQuestion]
  );

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();
      submitQuestion();
    },
    [submitQuestion]
  );

  const remaining = MAX_QUESTION_LENGTH - inputValue.length;
  const isOverLimit = remaining < 0;
  const isNearLimit = remaining >= 0 && remaining <= 100;

  // Determine the character count status for ARIA descriptions.
  const charCountId = 'input-bar-char-count';
  const validationId = 'input-bar-validation';

  return (
    <form
      className="input-bar"
      onSubmit={handleSubmit}
      aria-label="Ask a question"
      noValidate
    >
      {/* Inline validation message — shown above the input */}
      {validationError && (
        <p
          id={validationId}
          className="input-bar__validation-error"
          role="alert"
          aria-live="assertive"
        >
          {validationError}
        </p>
      )}

      <div className="input-bar__row">
        <label htmlFor="sre-question-input" className="input-bar__label sr-only">
          Ask the SRE Copilot
        </label>

        <textarea
          id="sre-question-input"
          ref={textareaRef}
          className={`input-bar__textarea${isOverLimit ? ' input-bar__textarea--error' : ''}`}
          value={inputValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask an operational question… (e.g. Why is checkout-service failing?)"
          disabled={inputDisabled}
          rows={1}
          maxLength={MAX_QUESTION_LENGTH + 200} /* Allow typing slightly over to show error */
          aria-describedby={`${charCountId}${validationError ? ` ${validationId}` : ''}`}
          aria-invalid={isOverLimit || !!validationError}
          aria-label="Question input"
        />

        <div className="input-bar__actions">
          {/* Loading indicator sits next to the submit button */}
          <LoadingIndicator isLoading={isLoading} />

          <button
            type="submit"
            className="input-bar__submit"
            disabled={inputDisabled || isOverLimit}
            aria-label={isLoading ? 'Waiting for response…' : 'Submit question'}
            aria-busy={isLoading}
          >
            {isLoading ? (
              <span aria-hidden="true">⏳</span>
            ) : (
              <span aria-hidden="true">➤</span>
            )}
            <span className="sr-only">{isLoading ? 'Sending…' : 'Send'}</span>
          </button>
        </div>
      </div>

      {/* Character counter — always rendered for screen-reader announcements */}
      <p
        id={charCountId}
        className={`input-bar__char-count${isOverLimit ? ' input-bar__char-count--error' : isNearLimit ? ' input-bar__char-count--warn' : ''}`}
        aria-live="polite"
        aria-atomic="true"
      >
        {isOverLimit
          ? `${Math.abs(remaining)} character${Math.abs(remaining) !== 1 ? 's' : ''} over the limit`
          : `${remaining} character${remaining !== 1 ? 's' : ''} remaining`}
      </p>
    </form>
  );
}

/**
 * Tests for useChat hook (Requirements 6.2, 6.3, 6.6, 6.7)
 *
 * Validates:
 *   - Initial state is correct (empty messages, not loading, etc.)
 *   - Empty and over-limit input is rejected with validation errors.
 *   - Successful submission appends user + agent messages.
 *   - On error, input is re-populated with the original question.
 *   - Messages list is capped at MAX_MESSAGES (100).
 *   - isLoading / inputDisabled are set before API call and cleared after.
 */

import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { useChat, MAX_MESSAGES, MAX_QUESTION_LENGTH } from '../hooks/useChat.js';

// ── Mock api.js so tests don't make real network calls ────────────────────────
vi.mock('../utils/api.js', () => ({
  postChat: vi.fn(),
}));
import { postChat } from '../utils/api.js';

describe('useChat — initial state', () => {
  it('starts with empty messages, not loading, no error', () => {
    const { result } = renderHook(() => useChat());
    expect(result.current.messages).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.inputDisabled).toBe(false);
    expect(result.current.inputValue).toBe('');
    expect(result.current.error).toBeNull();
  });

  it('sessionId is a non-empty string', () => {
    const { result } = renderHook(() => useChat());
    expect(typeof result.current.sessionId).toBe('string');
    expect(result.current.sessionId.length).toBeGreaterThan(0);
  });
});

describe('useChat — input validation (Requirement 6.7)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('rejects empty input with a validation error', async () => {
    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.submitQuestion();
    });
    expect(result.current.error).not.toBeNull();
    expect(result.current.error.message).toBe('Message cannot be empty.');
    expect(postChat).not.toHaveBeenCalled();
  });

  it('rejects whitespace-only input with a validation error', async () => {
    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('   '));
    await act(async () => {
      await result.current.submitQuestion();
    });
    expect(result.current.error.message).toBe('Message cannot be empty.');
    expect(postChat).not.toHaveBeenCalled();
  });

  it('rejects input exceeding MAX_QUESTION_LENGTH', async () => {
    const { result } = renderHook(() => useChat());
    const longInput = 'a'.repeat(MAX_QUESTION_LENGTH + 1);
    act(() => result.current.setInputValue(longInput));
    await act(async () => {
      await result.current.submitQuestion();
    });
    expect(result.current.error.message).toContain(`Maximum ${MAX_QUESTION_LENGTH} characters`);
    expect(postChat).not.toHaveBeenCalled();
  });

  it('accepts input exactly at MAX_QUESTION_LENGTH', async () => {
    postChat.mockResolvedValueOnce({
      response: 'ok',
      sessionId: 'abc',
      dataFreshness: null,
    });
    const { result } = renderHook(() => useChat());
    const exactInput = 'a'.repeat(MAX_QUESTION_LENGTH);
    act(() => result.current.setInputValue(exactInput));
    await act(async () => {
      await result.current.submitQuestion();
    });
    expect(postChat).toHaveBeenCalled();
    expect(result.current.error).toBeNull();
  });
});

describe('useChat — successful submission (Requirements 6.2, 6.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('appends user message immediately and agent message after response', async () => {
    postChat.mockResolvedValueOnce({
      response: 'Service is healthy.',
      sessionId: 'sess-1',
      dataFreshness: '2024-01-01T00:00:00Z',
    });

    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('How is checkout-service?'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('How is checkout-service?');
    expect(result.current.messages[1].role).toBe('agent');
    expect(result.current.messages[1].content).toBe('Service is healthy.');
  });

  it('clears the input field after submission', async () => {
    postChat.mockResolvedValueOnce({
      response: 'All good.',
      sessionId: 'sess-1',
      dataFreshness: null,
    });

    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('test question'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.inputValue).toBe('');
  });

  it('resets isLoading and inputDisabled after a successful response', async () => {
    postChat.mockResolvedValueOnce({
      response: 'Done.',
      sessionId: 'sess-1',
      dataFreshness: null,
    });

    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('something'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.inputDisabled).toBe(false);
  });

  it('passes the sessionId to postChat', async () => {
    postChat.mockResolvedValueOnce({
      response: 'ok',
      sessionId: 'sess-1',
      dataFreshness: null,
    });

    const { result } = renderHook(() => useChat());
    const sessionId = result.current.sessionId;
    act(() => result.current.setInputValue('a question'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(postChat).toHaveBeenCalledWith('a question', sessionId);
  });
});

describe('useChat — error handling (Requirement 6.6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it('sets error and restores inputValue on API failure', async () => {
    postChat.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('failing question'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.error).not.toBeNull();
    expect(result.current.error.message).toBe('Network error');
    expect(result.current.error.originalQuestion).toBe('failing question');
    expect(result.current.inputValue).toBe('failing question');
  });

  it('resets loading state on API failure', async () => {
    postChat.mockRejectedValueOnce(new Error('Server error'));

    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('question'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.inputDisabled).toBe(false);
  });

  it('clearError removes the error', async () => {
    postChat.mockRejectedValueOnce(new Error('oops'));

    const { result } = renderHook(() => useChat());
    act(() => result.current.setInputValue('q'));

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.error).not.toBeNull();

    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
  });
});

describe('useChat — message cap at MAX_MESSAGES (Requirement 6.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it(`retains only the last ${MAX_MESSAGES} messages when cap is exceeded`, async () => {
    const { result } = renderHook(() => useChat());

    // Simulate MAX_MESSAGES/2 round trips (each adds 2 messages).
    const calls = MAX_MESSAGES / 2 + 5; // 55 calls → 110 messages → should be trimmed to 100

    for (let i = 0; i < calls; i++) {
      postChat.mockResolvedValueOnce({
        response: `response ${i}`,
        sessionId: 'sess',
        dataFreshness: null,
      });
      act(() => result.current.setInputValue(`question ${i}`));
      // eslint-disable-next-line no-await-in-loop
      await act(async () => {
        await result.current.submitQuestion();
      });
    }

    expect(result.current.messages.length).toBeLessThanOrEqual(MAX_MESSAGES);
  });
});

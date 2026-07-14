/**
 * Tests for useSession hook (Requirement 6.4)
 *
 * Validates:
 *   - A UUID is generated and persisted in sessionStorage on first call.
 *   - Subsequent calls within the same tab return the same UUID.
 *   - The key used is SESSION_STORAGE_KEY.
 */

import { renderHook } from '@testing-library/react';
import { useSession, SESSION_STORAGE_KEY } from '../hooks/useSession.js';

describe('useSession', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('generates a UUID on first render', () => {
    const { result } = renderHook(() => useSession());
    expect(result.current).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    );
  });

  it('persists the session ID in sessionStorage under SESSION_STORAGE_KEY', () => {
    const { result } = renderHook(() => useSession());
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBe(result.current);
  });

  it('returns the same session ID on subsequent renders', () => {
    const { result, rerender } = renderHook(() => useSession());
    const first = result.current;
    rerender();
    expect(result.current).toBe(first);
  });

  it('reuses an existing session ID from sessionStorage', () => {
    const preset = 'aabbccdd-1234-5678-abcd-000000000000';
    sessionStorage.setItem(SESSION_STORAGE_KEY, preset);

    const { result } = renderHook(() => useSession());
    expect(result.current).toBe(preset);
  });

  it('generates different IDs for different (simulated) sessions', () => {
    const { result: r1 } = renderHook(() => useSession());
    const id1 = r1.current;

    sessionStorage.clear();
    // New renderHook simulates a fresh tab/context
    const { result: r2 } = renderHook(() => useSession());
    expect(r2.current).not.toBe(id1);
  });
});

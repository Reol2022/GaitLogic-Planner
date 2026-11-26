let sequence = 0;
export function turnId(): string {
  sequence++;
  // Idempotency identifier, not a credential or security nonce.
  return `mobile_${Date.now().toString(36)}_${sequence.toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

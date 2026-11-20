/** Browser-only encryption client. The worker owns all cryptographic keys. */

export function newEncryptedId() {
  return [...crypto.getRandomValues(new Uint8Array(16))]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

// Vue refs contain reactive Proxies, which cannot cross a Worker boundary.
export function copyAttachments(attachments) {
  return attachments.map((attachment) => ({
    id: attachment.id,
    name: attachment.name,
    dataUrl: attachment.dataUrl,
  }));
}

export class EncryptedSession {
  constructor() {
    this.worker = new Worker(new URL("./crypto.worker.js", import.meta.url), {
      type: "module",
    });
    this.nextId = 0;
    this.pending = new Map();
    this.worker.onmessage = ({ data }) => {
      const promise = this.pending.get(data.callId);
      if (!promise) return;
      this.pending.delete(data.callId);
      if (data.error) promise.reject(new Error(data.error));
      else promise.resolve(data.result);
    };
    this.worker.onerror = () => this.close();
  }

  call(operation, payload) {
    const callId = ++this.nextId;
    return new Promise((resolve, reject) => {
      this.pending.set(callId, { resolve, reject });
      this.worker.postMessage({ callId, operation, payload });
    });
  }

  create(noteId, password, title, content) {
    return this.call("create", { noteId, password, title, content });
  }

  unlock(noteId, password, ciphertext) {
    return this.call("unlock", { noteId, password, ciphertext });
  }

  viewVerifier() {
    return this.call("viewVerifier", {});
  }

  viewProof() {
    return this.call("viewProof", {});
  }

  save(title, content, attachments = []) {
    return this.call("save", { title, content, attachments: copyAttachments(attachments) });
  }

  close() {
    this.worker.terminate();
    for (const request of this.pending.values()) {
      request.reject(new Error("Note locked"));
    }
    this.pending.clear();
  }
}

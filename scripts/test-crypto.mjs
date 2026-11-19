import assert from "node:assert/strict";
import { Worker } from "node:worker_threads";

function session() {
  const worker = new Worker(new URL("./crypto-worker-test-bootstrap.mjs", import.meta.url));
  let callId = 0;
  const pending = new Map();
  worker.on("message", ({ callId, result, error }) => {
    const request = pending.get(callId);
    if (!request) return;
    pending.delete(callId);
    if (error) request.reject(new Error(error));
    else request.resolve(result);
  });
  return {
    call(operation, payload) {
      const id = ++callId;
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject });
        worker.postMessage({ callId: id, operation, payload });
      });
    },
    close() {
      return worker.terminate();
    },
  };
}

const id = "ab23cd45".repeat(4);
const title = "Confidential project name";
const content = "Private markdown with a secret value.";
const password = "long-test-password-not-shared";
const author = session();
const ciphertext = await author.call("create", { noteId: id, password, title, content });
assert.equal(JSON.parse(ciphertext).version, 1);
assert.ok(!ciphertext.includes(title));
assert.ok(!ciphertext.includes(content));
assert.ok(!ciphertext.includes(password));

const visitor = session();
await assert.rejects(
  visitor.call("unlock", { noteId: id, password: "incorrect-password", ciphertext }),
  /Invalid password/,
);
await visitor.close();

const reader = session();
const decrypted = await reader.call("unlock", { noteId: id, password, ciphertext });
assert.deepEqual(decrypted, { title, content });

const attached = [{ id: "ab12", name: "report.pdf", dataUrl: "data:application/pdf;base64,SGVsbG8=" }];
const updated = await reader.call("save", { title, content: "Updated private text", attachments: attached });
assert.ok(!updated.includes("report.pdf"));
assert.ok(!updated.includes("SGVsbG8="));
assert.notEqual(updated, ciphertext);
assert.ok(!updated.includes("Updated private text"));

const otherReader = session();
assert.deepEqual(
  await otherReader.call("unlock", { noteId: id, password, ciphertext: updated }),
  { title, content: "Updated private text", attachments: attached },
);

const modified = JSON.parse(updated);
modified.data.ciphertext = modified.data.ciphertext.slice(0, -4) + "AAAA";
const attacker = session();
await assert.rejects(
  attacker.call("unlock", { noteId: id, password, ciphertext: JSON.stringify(modified) }),
  /Invalid password/,
);

await Promise.all([author, reader, otherReader, attacker].map((worker) => worker.close()));
console.log("Argon2id/AES-GCM encryption, decryption, wrong-password, update, and tampering tests passed.");

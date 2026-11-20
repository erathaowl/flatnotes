import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

function source(path) {
  return readFileSync(new URL("../" + path, import.meta.url), "utf8");
}

const plain = source("client/views/Note.vue");
const encrypted = source("client/views/EncryptedNote.vue");
const toolbar = source("client/components/NoteToolbar.vue");
const header = source("client/components/NoteHeader.vue");
const expirationModal = source("client/components/ExpirationModal.vue");
const shareModal = source("client/components/ShareModal.vue");
const protectModal = source("client/components/ProtectModal.vue");
const button = source("client/components/CustomButton.vue");

for (const [name, view] of [["ordinary", plain], ["encrypted", encrypted]]) {
  assert.match(view, /<NoteHeader\b/, name + " uses shared title header");
  assert.match(view, /<NoteToolbar\b/, name + " uses shared actions");
  assert.match(view, /<ExpirationModal\b/, name + " uses expiration modal");
  assert.match(view, /<ShareModal\b/, name + " uses sharing modal");
  assert.match(view, /:draft="isNew(?:Note)?"/, name + " defers new-note settings");
  assert.doesNotMatch(view, /<ExpirationSelect\b/, name + " has no inline expiration selector");
  assert.match(view, /:shareActive="shareActive"/);
  assert.match(view, /:expirationActive="expirationActive"/);
}

assert.match(toolbar, /:style="shareActive \? 'active' : 'subtle'"/);
assert.match(toolbar, /:style="expirationActive \? 'active' : 'subtle'"/);
assert.match(toolbar, /label="Delete"\s+style="danger"/);
assert.match(toolbar, /<Toggle\b/);
assert.match(toolbar, /label="Protect"/);
assert.match(encrypted, /:showDelete="!publicSlug"/);
assert.match(encrypted, /:showExport="!publicSlug"/);
assert.match(button, /dark:text-white/);
assert.match(button, /style === 'active'/);
assert.match(header, /placeholder="Title"/);
assert.match(expirationModal, /if \(props\.draft\)/);
assert.match(shareModal, /if \(props\.draft\)/);
assert.match(plain, /savePublication\(data\.title, stagedShare\.value\)/);
assert.match(encrypted, /saveEncryptedPublication\(activeId\.value, stagedShare\.value\)/);
assert.match(protectModal, /saveEncryptedNote\(noteId, ciphertext, "\*", null, policy, verifier\)/);
assert.match(protectModal, /protectPlainNote\(/);

console.log("Unified editor, active action states, and deferred settings checks passed.");

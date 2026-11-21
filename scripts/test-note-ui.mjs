import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = (path) => readFileSync(new URL("../" + path, import.meta.url), "utf8");
const plain = source("client/views/Note.vue");
const encrypted = source("client/views/EncryptedNote.vue");
const toolbar = source("client/components/NoteToolbar.vue");
const share = source("client/components/ShareModal.vue");
const modal = source("client/components/Modal.vue");
const selector = source("client/components/ExpirationSelect.vue");
const protect = source("client/components/ProtectModal.vue");
const header = source("client/components/NoteHeader.vue");
const api = source("client/api.js");

for (const [name, view] of [["ordinary", plain], ["encrypted", encrypted]]) {
  assert.match(view, /<NoteHeader\b/, name + " uses shared header");
  assert.match(view, /<NoteToolbar\b/, name + " uses shared toolbar");
  assert.match(view, /<ShareModal\b/, name + " uses the shared dialog");
  assert.match(view, /:draft="isNew(?:Note)?"/, name + " stages publication before creation");
  assert.doesNotMatch(view, /<ExpirationModal\b|expirationEnabled|expirationDefault/);
}
assert.doesNotMatch(toolbar, /label="Expiration"|expirationActive|showExpiration/);
assert.match(toolbar, /:style="shareActive \? 'active' : 'subtle'"/);
assert.match(toolbar, /label="Delete"\s+style="danger"/);
assert.match(toolbar, /<Toggle\b/);
assert.doesNotMatch(toolbar, /isNew:/);
assert.match(plain, /:draft="isNewNote"/);
assert.match(encrypted, /:draft="isNew"/);
assert.match(share, /<ExpirationSelect\b/);
assert.match(modal, /items-center justify-center/);
assert.doesNotMatch(modal, /mt-\[30vh\]/);
assert.match(modal, /max-h-full/);
assert.match(modal, /overflow-y-auto/);
assert.match(share, /max-h-\[85dvh\]/);
assert.match(share, /sticky bottom-0/);
assert.match(share, /Automatically delete this note when the share expires/);
assert.match(share, /autoDeleteNote/);
assert.match(share, /props\.draft/);
assert.match(share, /<option v-if="!encryptedId" value="edit">/);
assert.match(encrypted, /const canEdit = computed\(\(\) =>\s*!props\.publicSlug &&/);
assert.match(api, /api\.put\("api\/encrypted-notes\/"/);
assert.match(selector, /first public viewing/i);
assert.match(encrypted, /props\.publicSlug && expiration\.value\.mode === "once"/);
assert.match(encrypted, /settings\.viewVerifier = await cryptoSession\.viewVerifier\(\)/);
assert.match(plain, /savePublication\(data\.title, stagedShare\.value\)/);
assert.match(protect, /settings\.viewVerifier = await cryptoSession\.viewVerifier\(\)/);
assert.match(header, /placeholder="Title"/);
console.log("Publication expiration and unified note editor checks passed.");

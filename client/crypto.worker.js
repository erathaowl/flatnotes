import { argon2id } from "hash-wasm";

const encoder = new TextEncoder();
const decoder = new TextDecoder("utf-8", { fatal: true });
const PROFILE = Object.freeze({ memorySize: 65536, iterations: 3, parallelism: 1 });
let documentKey = null;
let envelope = null;
let activeNoteId = null;

function randomBytes(length) {
  return crypto.getRandomValues(new Uint8Array(length));
}

function encode64(bytes) {
  let result = "";
  for (let offset = 0; offset < bytes.length; offset += 16384) {
    result += String.fromCharCode(...bytes.subarray(offset, offset + 16384));
  }
  return btoa(result);
}

function decode64(value) {
  if (typeof value !== "string" || value.length > 8000000) {
    throw new Error("Invalid encrypted data");
  }
  return Uint8Array.from(atob(value), (character) => character.charCodeAt(0));
}

function aad(kind, noteId) {
  return encoder.encode("flatnotes:" + kind + ":v1:" + noteId);
}

async function aesKey(bytes, operations) {
  return crypto.subtle.importKey("raw", bytes, "AES-GCM", false, operations);
}

async function derive(password, salt, parameters) {
  const result = await argon2id({
    password: encoder.encode(password),
    salt,
    memorySize: parameters.memorySize,
    iterations: parameters.iterations,
    parallelism: parameters.parallelism,
    hashLength: 32,
    outputType: "binary",
  });
  try {
    return await aesKey(result, ["encrypt", "decrypt"]);
  } finally {
    result.fill(0);
  }
}

async function encryptContent(title, content) {
  const nonce = randomBytes(12);
  const plaintext = encoder.encode(JSON.stringify({ title, content }));
  const bytes = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce, additionalData: aad("data", activeNoteId) },
    documentKey,
    plaintext,
  );
  plaintext.fill(0);
  envelope.data = { nonce: encode64(nonce), ciphertext: encode64(new Uint8Array(bytes)) };
  return JSON.stringify(envelope);
}

function validateHeader(value, id) {
  if (
    value.version !== 1 || value.noteId !== id ||
    value.kdf?.name !== "argon2id" ||
    value.kdf.memorySize !== PROFILE.memorySize ||
    value.kdf.iterations !== PROFILE.iterations ||
    value.kdf.parallelism !== PROFILE.parallelism
  ) {
    throw new Error("Unsupported encrypted note format");
  }
}

async function create(payload) {
  if (documentKey) throw new Error("An encrypted note is already unlocked");
  activeNoteId = payload.noteId;
  const salt = randomBytes(16);
  const wrapNonce = randomBytes(12);
  const rawDataKey = randomBytes(32);
  const wrappingKey = await derive(payload.password, salt, PROFILE);
  try {
    const wrapped = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: wrapNonce, additionalData: aad("key", activeNoteId) },
      wrappingKey,
      rawDataKey,
    );
    documentKey = await aesKey(rawDataKey, ["encrypt", "decrypt"]);
    envelope = {
      version: 1,
      noteId: activeNoteId,
      kdf: { name: "argon2id", ...PROFILE, salt: encode64(salt) },
      wrappedKey: { nonce: encode64(wrapNonce), ciphertext: encode64(new Uint8Array(wrapped)) },
      data: null,
    };
    return encryptContent(payload.title, payload.content);
  } finally {
    rawDataKey.fill(0);
  }
}

async function unlock(payload) {
  if (documentKey) throw new Error("An encrypted note is already unlocked");
  const parsed = JSON.parse(payload.ciphertext);
  validateHeader(parsed, payload.noteId);
  const wrappingKey = await derive(payload.password, decode64(parsed.kdf.salt), parsed.kdf);
  const rawDataKey = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: decode64(parsed.wrappedKey.nonce),
      additionalData: aad("key", payload.noteId),
    },
    wrappingKey,
    decode64(parsed.wrappedKey.ciphertext),
  );
  const keyBytes = new Uint8Array(rawDataKey);
  const contentKey = await aesKey(keyBytes, ["encrypt", "decrypt"]);
  keyBytes.fill(0);
  const clearBytes = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: decode64(parsed.data.nonce),
      additionalData: aad("data", payload.noteId),
    },
    contentKey,
    decode64(parsed.data.ciphertext),
  );
  const clear = new Uint8Array(clearBytes);
  try {
    const note = JSON.parse(decoder.decode(clear));
    if (typeof note.title !== "string" || typeof note.content !== "string") {
      throw new Error("Invalid encrypted note");
    }
    documentKey = contentKey;
    activeNoteId = payload.noteId;
    envelope = parsed;
    return note;
  } finally {
    clear.fill(0);
  }
}

self.onmessage = async ({ data: { callId, operation, payload } }) => {
  try {
    let result;
    if (operation === "create") result = await create(payload);
    else if (operation === "unlock") result = await unlock(payload);
    else if (operation === "save") {
      if (!documentKey) throw new Error("Note is locked");
      result = await encryptContent(payload.title, payload.content);
    } else throw new Error("Unsupported crypto operation");
    self.postMessage({ callId, result });
  } catch (error) {
    self.postMessage({ callId, error: "Invalid password or encrypted note data" });
  }
};

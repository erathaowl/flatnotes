import assert from "node:assert/strict";

import {
  passwordPolicyDescription,
  validateProtectionPassword,
} from "../client/passwordPolicy.js";

assert.equal(validateProtectionPassword("123456789012"), "");
assert.match(validateProtectionPassword("short"), /12 characters/);
assert.equal(validateProtectionPassword("", { encryptionPasswordMinLength: 0 }), "Enter a protection password.");

const cases = [
  ["abCD123!", 0, ""],
  ["abcdefgh", 0, ""],
  ["abCD123!", 4, ""],
  ["Abc12345", 4, "Use at least 4"],
  ["Abc12345", 3, ""],
  ["abcdef12", 3, "Use at least 3"],
  ["abcdefgh", 2, "Use at least 2"],
  ["Éclair7!", 4, ""],
  ["abcDEF!x", 3, ""],
  ["abCD12!", 0, "at least 8"],
];
for (const [password, minClasses, expected] of cases) {
  const policy = { encryptionPasswordMinLength: 8, encryptionPasswordMinClasses: minClasses };
  const error = validateProtectionPassword(password, policy);
  if (expected === "") assert.equal(error, "", password);
  else assert.ok(error.includes(expected), password + ": " + error);
}

assert.equal(
  validateProtectionPassword("a", { encryptionPasswordMinLength: 0, encryptionPasswordMinClasses: 0 }),
  "",
);
assert.match(passwordPolicyDescription({ encryptionPasswordMinLength: 8, encryptionPasswordMinClasses: 3 }), /3 of 4/);
console.log("Password length and character-category policy tests passed.");

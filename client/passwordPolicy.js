/** Validate new note passwords locally without sending them to the server. */

export function validateProtectionPassword(password, config = {}) {
  const minLength = config.encryptionPasswordMinLength ?? 12;
  const minClasses = config.encryptionPasswordMinClasses ?? 0;

  if (!password) return "Enter a protection password.";
  if ([...password].length < minLength) {
    return "Use a password of at least " + minLength + " characters.";
  }

  const classes = [
    /\p{Ll}/u,
    /\p{Lu}/u,
    /\p{Nd}/u,
    /[^\p{L}\p{N}]/u,
  ].filter((pattern) => pattern.test(password)).length;
  if (classes < minClasses) {
    return "Use at least " + minClasses +
      " of these character types: lowercase, uppercase, numbers, symbols.";
  }
  return "";
}

export function passwordPolicyDescription(config = {}) {
  const minLength = config.encryptionPasswordMinLength ?? 12;
  const minClasses = config.encryptionPasswordMinClasses ?? 0;
  const length = minLength > 0 ? "Minimum " + minLength + " characters" : "No minimum length";
  const complexity = minClasses
    ? "at least " + minClasses + " of 4 character types (lowercase, uppercase, numbers, symbols)"
    : "no character-type requirement";
  return length + "; " + complexity + ".";
}

<template>
  <Modal v-model="isVisible" class="max-w-md px-6 py-5">
    <h2 class="mb-3 text-xl">Protect note</h2>
    <p class="mb-4 text-sm text-theme-text-muted">
      Encryption occurs in your browser. Store your password securely. Lost passwords
      cannot be recovered. Original plaintext may remain in backups or storage history.
    </p>
    <p class="mb-3 text-xs text-theme-text-muted">
      {{ passwordPolicyDescription(globalStore.config) }}
    </p>
    <form @submit.prevent="protect">
      <label class="mb-1 block" for="protect-password">Protection password</label>
      <input
        id="protect-password"
        v-model="password"
        type="password"
        autocomplete="off"
        required
        class="mb-3 w-full rounded border border-theme-border bg-theme-background px-3 py-2"
      />
      <label class="mb-1 block" for="protect-confirm">Confirm password</label>
      <input
        id="protect-confirm"
        v-model="confirmation"
        type="password"
        autocomplete="off"
        required
        class="mb-3 w-full rounded border border-theme-border bg-theme-background px-3 py-2"
      />
      <p v-if="errorMessage" role="alert" class="mb-3 text-theme-danger">{{ errorMessage }}</p>
      <div class="flex justify-end gap-2">
        <CustomButton label="Cancel" @click.prevent="isVisible = false" />
        <CustomButton :label="busy ? 'Encrypting...' : 'Protect'" :disabled="busy || !password" />
      </div>
    </form>
  </Modal>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRouter } from "vue-router";
import { useGlobalStore } from "../globalStore.js";
import { passwordPolicyDescription, validateProtectionPassword } from "../passwordPolicy.js";
import { protectPlainNote } from "../api.js";
import { EncryptedSession, newEncryptedId } from "../cryptoSession.js";
import CustomButton from "./CustomButton.vue";
import Modal from "./Modal.vue";

const props = defineProps({ title: String, content: String, lastModified: Number });
const isVisible = defineModel({ type: Boolean });
const router = useRouter();
const globalStore = useGlobalStore();
const emit = defineEmits(["protected"]);
const password = ref("");
const confirmation = ref("");
const errorMessage = ref("");
const busy = ref(false);

async function protect() {
  errorMessage.value = "";
  const passwordError = validateProtectionPassword(password.value, globalStore.config);
  if (passwordError) {
    errorMessage.value = passwordError;
    return;
  }
  if (password.value !== confirmation.value) {
    errorMessage.value = "Passwords do not match.";
    return;
  }
  // Plaintext attachments cannot be reclassified as encrypted attachments.
  if (/(?:attachments\/|!\[[^\]]*\]\(https?:)/i.test(props.content || "")) {
    errorMessage.value = "Remove or embed external attachments before protecting this note.";
    return;
  }
  const cryptoSession = new EncryptedSession();
  busy.value = true;
  try {
    const noteId = newEncryptedId();
    const ciphertext = await cryptoSession.create(
      noteId, password.value, props.title, props.content || "",
    );
    await protectPlainNote(props.title, noteId, ciphertext, props.lastModified);
    password.value = "";
    confirmation.value = "";
    localStorage.removeItem(props.title);
    sessionStorage.removeItem(props.title);
    emit("protected");
    isVisible.value = false;
    await router.replace({ name: "encryptedNote", params: { id: noteId } });
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || "Unable to protect this note.";
  } finally {
    busy.value = false;
    cryptoSession.close();
  }
}

watch(isVisible, (visible) => {
  if (!visible) {
    password.value = "";
    confirmation.value = "";
    errorMessage.value = "";
  }
});
</script>

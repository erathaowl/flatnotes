<template>
  <div class="mx-auto w-full max-w-4xl flex-1">
    <ShareModal
      v-if="!publicSlug && unlocked && globalStore.config.sharingEnabled"
      v-model="showSharing"
      :encryptedId="activeId"
      :title="title"
    />

    <div v-if="loading" class="py-12 text-center">Loading encrypted note...</div>
    <p v-else-if="loadError" role="alert" class="py-8 text-theme-danger">{{ loadError }}</p>

    <div v-else-if="!unlocked" class="mx-auto max-w-md pt-12">
      <div class="mb-5 flex items-center gap-2 text-2xl font-semibold">
        <span aria-hidden="true">🔒</span>
        {{ isNew ? "Create protected note" : "Unlock protected note" }}
      </div>
      <p class="mb-4 text-sm text-theme-text-muted">
        Encryption and decryption run only inside your browser. Your password is never sent to the server.
      </p>
      <form @submit.prevent="isNew ? initializeNew() : unlock()">
        <label class="mb-1 block" for="encrypted-password">Protection password</label>
        <input
          id="encrypted-password"
          v-model="password"
          type="password"
          autocomplete="off"
          required
          class="mb-3 w-full rounded border border-theme-border bg-theme-background px-3 py-2"
        />
        <template v-if="isNew">
          <label class="mb-1 block" for="encrypted-confirm">Confirm password</label>
          <input
            id="encrypted-confirm"
            v-model="confirmation"
            type="password"
            autocomplete="off"
            required
            class="mb-3 w-full rounded border border-theme-border bg-theme-background px-3 py-2"
          />
        </template>
        <p v-if="message" role="alert" class="mb-3 text-theme-danger">{{ message }}</p>
        <CustomButton :label="busy ? 'Working...' : isNew ? 'Continue' : 'Unlock'" :disabled="busy || !password" />
      </form>
    </div>

    <template v-else>
      <header class="mb-3 flex flex-wrap items-center justify-between gap-2">
        <input
          v-if="editing && !publicSlug"
          v-model="title"
          class="min-w-0 flex-1 bg-theme-background text-2xl outline-none"
          aria-label="Note title"
        />
        <h1 v-else class="break-words text-2xl">{{ title }}</h1>
        <div class="flex flex-wrap gap-2 print:hidden">
          <CustomButton label="Lock" @click="lock" />
          <CustomButton
            v-if="!publicSlug && globalStore.config.sharingEnabled"
            label="Share"
            @click="showSharing = true"
          />
          <CustomButton
            v-if="!publicSlug"
            label="Export Markdown"
            @click="exportMarkdown"
          />
          <CustomButton
            v-if="!publicSlug"
            label="Delete"
            style="danger"
            @click="remove"
          />
          <CustomButton v-if="canEdit && editing" label="Cancel" @click="cancelEdit" />
          <CustomButton v-if="canEdit && editing" label="Save" :disabled="busy" @click="save" />
          <CustomButton v-if="canEdit && !editing" label="Edit" @click="editing = true" />
        </div>
      </header>
      <hr class="mb-4 border-theme-border" />
      <p v-if="message" role="alert" class="mb-3 text-theme-danger">{{ message }}</p>
      <ToastEditor
        v-if="editing"
        ref="editor"
        :initialValue="content"
        :initialEditType="'markdown'"
        :addImageBlobHook="addInlineImage"
        @keydown="handleKeydown"
      />
      <ToastViewer
        v-else
        :key="revision"
        :initialValue="content"
        class="toast-viewer pb-4"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  deleteEncryptedNote,
  fetchEncryptedNote,
  saveEncryptedNote,
} from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import ShareModal from "../components/ShareModal.vue";
import ToastEditor from "../components/toastui/ToastEditor.vue";
import ToastViewer from "../components/toastui/ToastViewer.vue";
import { EncryptedSession, newEncryptedId } from "../cryptoSession.js";
import { useGlobalStore } from "../globalStore.js";

const props = defineProps({ id: String, publicSlug: String });
const router = useRouter();
const globalStore = useGlobalStore();
const activeId = ref("");
const password = ref("");
const confirmation = ref("");
const title = ref("");
const content = ref("");
const ciphertext = ref("");
const revision = ref("");
const permission = ref("read");
const unlocked = ref(false);
const loading = ref(true);
const busy = ref(false);
const editing = ref(false);
const showSharing = ref(false);
const message = ref("");
const loadError = ref("");
const editor = ref(null);
let cryptoSession = null;

const isNew = computed(() => props.id === "new" && !props.publicSlug);
const canEdit = computed(() =>
  (!props.publicSlug || permission.value === "edit") &&
  globalStore.config.encryptionEnabled,
);

async function load() {
  lock();
  loading.value = true;
  loadError.value = "";
  if (isNew.value) {
    if (!globalStore.config.encryptionEnabled) {
      loadError.value = "Creating protected notes is disabled by the administrator.";
    }
    loading.value = false;
    return;
  }
  try {
    const result = await fetchEncryptedNote(props.id, props.publicSlug);
    ciphertext.value = result.ciphertext;
    activeId.value = result.noteId;
    revision.value = result.revision;
    permission.value = result.permission;
  } catch (error) {
    loadError.value = error.response?.status === 404
      ? "This encrypted note is not available."
      : "Unable to load encrypted note.";
  } finally {
    loading.value = false;
  }
}

async function unlock() {
  busy.value = true;
  message.value = "";
  cryptoSession?.close();
  cryptoSession = new EncryptedSession();
  try {
    const note = await cryptoSession.unlock(activeId.value, password.value, ciphertext.value);
    title.value = note.title;
    content.value = note.content;
    unlocked.value = true;
    password.value = "";
  } catch {
    cryptoSession.close();
    cryptoSession = null;
    message.value = "Incorrect password or damaged encrypted note.";
  } finally {
    busy.value = false;
  }
}

async function initializeNew() {
  if (password.value.length < 12) {
    message.value = "Use a password of at least 12 characters.";
    return;
  }
  if (password.value !== confirmation.value) {
    message.value = "Passwords do not match.";
    return;
  }
  // The password stays only in browser memory. The initial document is empty.
  busy.value = true;
  message.value = "";
  cryptoSession = new EncryptedSession();
  activeId.value = newEncryptedId();
  try {
    ciphertext.value = await cryptoSession.create(activeId.value, password.value, "", "");
    title.value = "";
    content.value = "";
    unlocked.value = true;
    editing.value = true;
    password.value = "";
    confirmation.value = "";
  } catch {
    message.value = "Encryption could not be initialized.";
    cryptoSession.close();
    cryptoSession = null;
  } finally {
    busy.value = false;
  }
}

async function save() {
  if (busy.value || !cryptoSession) return;
  if (!title.value.trim()) {
    message.value = "A title is required.";
    return;
  }
  busy.value = true;
  message.value = "";
  try {
    const markdown = editor.value.getMarkdown();
    const encryptedData = await cryptoSession.save(title.value.trim(), markdown);
    const result = await saveEncryptedNote(
      activeId.value, encryptedData, revision.value || "*", props.publicSlug,
    );
    content.value = markdown;
    ciphertext.value = encryptedData;
    revision.value = result.revision;
    editing.value = false;
    if (isNew.value) {
      await router.replace({ name: "encryptedNote", params: { id: activeId.value } });
    }
  } catch (error) {
    message.value = error.response?.status === 409
      ? "The note changed elsewhere. Copy your edits before reloading."
      : "Unable to save the encrypted note.";
  } finally {
    busy.value = false;
  }
}

function lock() {
  cryptoSession?.close();
  cryptoSession = null;
  title.value = "";
  content.value = "";
  password.value = "";
  confirmation.value = "";
  unlocked.value = false;
  editing.value = false;
  showSharing.value = false;
  message.value = "";
}

function cancelEdit() {
  editing.value = false;
  message.value = "";
}

async function remove() {
  if (!window.confirm("Permanently delete this encrypted note?")) return;
  try {
    await deleteEncryptedNote(activeId.value);
    lock();
    await router.push({ name: "encryptedNotes" });
  } catch {
    message.value = "Could not delete the encrypted note.";
  }
}

function exportMarkdown() {
  const file = new Blob([content.value], { type: "text/markdown;charset=utf-8" });
  const href = URL.createObjectURL(file);
  const element = document.createElement("a");
  element.href = href;
  element.download = (title.value || "note") + ".md";
  element.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

function handleKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") save();
}

function addInlineImage(blob, callback) {
  // Image bytes become part of encrypted Markdown. No plaintext upload occurs.
  const reader = new FileReader();
  reader.onload = () => callback(reader.result, blob.name || "image");
  reader.readAsDataURL(blob);
}

watch(() => [props.id, props.publicSlug], load);
onMounted(load);
onUnmounted(lock);
</script>

<template>
  <div class="mx-auto w-full max-w-4xl flex-1">
    <ShareModal
      v-if="!publicSlug && unlocked && globalStore.config.sharingEnabled"
      v-model="showSharing"
      :encryptedId="activeId"
      :title="title"
      :draft="isNew"
      :initialSettings="stagedShare"
      :getVerifier="getViewVerifier"
      @updated="onShareUpdated"
    />

    <div v-if="loading" class="py-12 text-center">Loading encrypted note...</div>
    <p v-else-if="loadError" role="alert" class="py-8 text-theme-danger">{{ loadError }}</p>

    <div v-else-if="!unlocked" class="mx-auto max-w-md pt-12">
      <div class="mb-5 flex items-center gap-2 text-2xl font-semibold">
        <SvgIcon type="mdi" :path="mdilLock" size="1.25em" class="shrink-0" />
        {{ isNew ? "Create protected note" : "Unlock protected note" }}
      </div>
      <p class="mb-4 text-sm text-theme-text-muted">
        Encryption and decryption run only inside your browser. Your password is never sent to the server.
      </p>
      <p v-if="router.currentRoute.value.query.sharingError" class="mb-3 text-sm text-theme-danger" role="alert">
        The note was protected, but its public link could not be activated. Unlock it and use Share to retry.
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
        <p v-if="isNew" class="mb-3 text-xs text-theme-text-muted">
          {{ passwordPolicyDescription(globalStore.config) }}
        </p>
        <p v-if="message" role="alert" class="mb-3 text-theme-danger">{{ message }}</p>
        <CustomButton :label="busy ? 'Working...' : isNew ? 'Continue' : 'Unlock'" :disabled="busy || !password" />
      </form>
    </div>

    <template v-else>
      <NoteHeader
        ref="noteHeader"
        v-model:title="title"
        :displayTitle="title"
        :editing="editing && !publicSlug"
        :titleError="titleError"
        @titleInput="titleError = false"
      >
        <NoteToolbar
          encrypted
          :editing="editing"
          :canModify="canEdit"
          :consumed="consumedView"
          :showExport="!publicSlug"
          :showDelete="!publicSlug"
          :showShare="!publicSlug && globalStore.config.sharingEnabled"
          :shareActive="shareActive"
          :busy="busy"
          @lock="confirmAndLock"
          @share="showSharing = true"
          @export="exportMarkdown"
          @delete="remove"
          @attach="fileInput?.click()"
          @cancel="cancelEdit"
          @save="save"
          @toggle-edit="toggleEditMode"
        />
      </NoteHeader>
      <input ref="fileInput" type="file" class="hidden" @change="attachFile" />
      <p v-if="publicSlug && expiration.mode !== 'none'" class="mb-2 text-xs text-theme-text-muted">
        {{ expiration.mode === "once"
          ? "This shared link can be viewed only once."
          : "Sharing expires " + new Date(expiration.expiresAt * 1000).toLocaleString() }}
      </p>
      <hr class="mb-4 border-theme-border" />
      <p v-if="message" role="alert" class="mb-3 text-theme-danger">{{ message }}</p>
      <div v-if="attachments.length" class="mb-4 rounded border border-theme-border p-3">
        <div class="mb-2 text-sm font-semibold">Encrypted attachments</div>
        <ul class="space-y-1">
          <li v-for="attachment in attachments" :key="attachment.id" class="flex flex-wrap items-center gap-2">
            <button type="button" class="underline" @click="downloadAttachment(attachment)">
              {{ attachment.name }}
            </button>
            <button v-if="editing && canEdit" type="button" class="text-theme-danger" @click="removeAttachment(attachment.id)">
              Remove
            </button>
          </li>
        </ul>
      </div>
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
import SvgIcon from "@jamescoyle/vue-icon";
import { mdilLock } from "@mdi/light-js";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  consumeEncryptedView,
  deleteEncryptedNote,
  fetchEncryptedNote,
  getEncryptedPublication,
  saveEncryptedPublication,
  saveEncryptedNote,
} from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import ShareModal from "../components/ShareModal.vue";
import NoteHeader from "../components/NoteHeader.vue";
import NoteToolbar from "../components/NoteToolbar.vue";
import ToastEditor from "../components/toastui/ToastEditor.vue";
import ToastViewer from "../components/toastui/ToastViewer.vue";
import { EncryptedSession, copyAttachments, newEncryptedId } from "../cryptoSession.js";
import { useGlobalStore } from "../globalStore.js";
import { passwordPolicyDescription, validateProtectionPassword } from "../passwordPolicy.js";

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
const unlocked = ref(false);
const loading = ref(true);
const busy = ref(false);
const editing = ref(false);
const showSharing = ref(false);
const stagedShare = ref(null);
const shareActive = ref(false);
const savedTitle = ref("");
const noteHeader = ref(null);
const expiration = ref({ mode: "none", policy: "none", expiresAt: null });
const consumedView = ref(false);
const message = ref("");
const loadError = ref("");
const editor = ref(null);
const titleInput = ref(null);
const titleError = ref(false);
const fileInput = ref(null);
const attachments = ref([]);
let savedAttachments = [];
let cryptoSession = null;

const isNew = computed(() => props.id === "new" && !props.publicSlug);
const canEdit = computed(() =>
  !props.publicSlug &&
  globalStore.config.authType !== "read_only" &&
  globalStore.config.encryptionEnabled &&
  !consumedView.value,
);

async function load() {
  // Retain the unlocked session after replacing /e/new with the saved note ID.
  if (unlocked.value && activeId.value && props.id === activeId.value && !props.publicSlug) {
    return;
  }
  lock();
  loading.value = true;
  loadError.value = "";
  stagedShare.value = null;
  shareActive.value = false;
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
    expiration.value = props.publicSlug ? result.expiration : { mode: "none", policy: "none", expiresAt: null };
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
    if (props.publicSlug && expiration.value.mode === "once") {
      const proof = await cryptoSession.viewProof();
      await consumeEncryptedView(props.publicSlug, proof);
      consumedView.value = true;
    }
    title.value = note.title;
    content.value = note.content;
    attachments.value = note.attachments || [];
    savedAttachments = copyAttachments(attachments.value);
    savedTitle.value = note.title;
    unlocked.value = true;
    if (!props.publicSlug && globalStore.config.sharingEnabled) {
      try {
        const publication = await getEncryptedPublication(activeId.value);
        shareActive.value = Boolean(publication?.slug && !publication?.expired);
      } catch {
        shareActive.value = false;
      }
    }
    password.value = "";
  } catch (error) {
    cryptoSession.close();
    cryptoSession = null;
    message.value = error.response?.status === 410
      ? "This single-view note has already been viewed or expired."
      : error.response?.status === 403
        ? "The server rejected the single-view unlock proof."
        : "Incorrect password or damaged encrypted note.";
  } finally {
    busy.value = false;
  }
}

async function initializeNew() {
  const passwordError = validateProtectionPassword(password.value, globalStore.config);
  if (passwordError) {
    message.value = passwordError;
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
    savedTitle.value = "";
    content.value = "";
    attachments.value = [];
    savedAttachments = [];
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
    titleError.value = true;
    await nextTick();
    noteHeader.value?.focusTitle();
    return;
  }
  busy.value = true;
  message.value = "";
  titleError.value = false;
  try {
    const firstSave = isNew.value;
    const markdown = editor.value.getMarkdown();
    const encryptedData = await cryptoSession.save(title.value.trim(), markdown, attachments.value);
    const result = await saveEncryptedNote(
      activeId.value, encryptedData, revision.value || "*",
    );
    content.value = markdown;
    savedTitle.value = title.value.trim();
    savedAttachments = copyAttachments(attachments.value);
    ciphertext.value = encryptedData;
    revision.value = result.revision;
    editing.value = false;
    if (firstSave) {
      await router.replace({ name: "encryptedNote", params: { id: activeId.value } });
      if (stagedShare.value) {
        try {
          const settings = { ...stagedShare.value };
          if (settings.expiration === "once") {
            settings.viewVerifier = await cryptoSession.viewVerifier();
          }
          const publication = await saveEncryptedPublication(activeId.value, settings);
          shareActive.value = Boolean(publication?.slug && !publication?.expired);
          stagedShare.value = null;
        } catch {
          shareActive.value = false;
          stagedShare.value = null;
          message.value = "Note saved, but sharing could not be activated. Open Share to try again.";
        }
      }
    }
  } catch (error) {
    const status = error.response?.status;
    message.value = status === 409
      ? "The note changed elsewhere. Copy your edits before reloading."
      : status === 413
        ? "The encrypted note exceeds the server size limit."
        : status === 403
          ? "Saving encrypted notes is disabled or access was denied."
          : "Unable to save the encrypted note.";
    // Log only an error category: encrypted content and passwords remain private.
    console.error("Encrypted note save failed:", error.name, status || "browser");
  } finally {
    busy.value = false;
  }
}

function lock() {
  cryptoSession?.close();
  cryptoSession = null;
  title.value = "";
  savedTitle.value = "";
  content.value = "";
  attachments.value = [];
  savedAttachments = [];
  password.value = "";
  confirmation.value = "";
  unlocked.value = false;
  editing.value = false;
  showSharing.value = false;
  stagedShare.value = null;
  shareActive.value = false;
  consumedView.value = false;
  message.value = "";
  titleError.value = false;
}

function getViewVerifier() {
  if (!cryptoSession) throw new Error("Unlock the note first");
  return cryptoSession.viewVerifier();
}

function onShareUpdated(value) {
  if (isNew.value) stagedShare.value = value;
  shareActive.value = Boolean(value?.permission && value.permission !== "private" && !value?.expired);
}

function toggleEditMode() {
  if (!canEdit.value || busy.value) return;
  if (editing.value) cancelEdit();
  else editing.value = true;
}

function confirmAndLock() {
  const unsaved = editing.value && (
    title.value !== savedTitle.value ||
    editor.value?.getMarkdown() !== content.value ||
    attachments.value.length !== savedAttachments.length
  );
  if (unsaved && !window.confirm("Discard unsaved edits and lock this note?")) return;
  lock();
}

function cancelEdit() {
  title.value = savedTitle.value;
  attachments.value = copyAttachments(savedAttachments);
  editing.value = false;
  message.value = "";
}

async function remove() {
  if (!window.confirm(isNew.value ? "Discard this unsaved protected note?" : "Permanently delete this encrypted note?")) return;
  if (isNew.value) {
    lock();
    await router.push({ name: "encryptedNotes" });
    return;
  }
  try {
    await deleteEncryptedNote(activeId.value);
    lock();
    await router.push({ name: "encryptedNotes" });
  } catch {
    message.value = "Could not delete the encrypted note.";
  }
}

function exportMarkdown() {
  const markdown = editing.value ? editor.value?.getMarkdown() || "" : content.value;
  const file = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const href = URL.createObjectURL(file);
  const element = document.createElement("a");
  element.href = href;
  element.download = (title.value || "note") + ".md";
  element.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

async function attachFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const total = attachments.value.reduce((sum, item) => sum + Math.ceil(item.dataUrl.length * 0.75), 0);
  if (file.size > 2 * 1024 * 1024 || total + file.size > 2 * 1024 * 1024) {
    message.value = "Total encrypted attachments may not exceed 2 MiB.";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    attachments.value.push({
      id: newEncryptedId(),
      name: file.name,
      dataUrl: reader.result,
    });
    message.value = "";
  };
  reader.onerror = () => {
    message.value = "Could not read the attachment.";
  };
  reader.readAsDataURL(file);
}

function removeAttachment(id) {
  attachments.value = attachments.value.filter((item) => item.id !== id);
}

function downloadAttachment(attachment) {
  try {
    const [header, encoded] = attachment.dataUrl.split(",", 2);
    if (!header.startsWith("data:") || !header.endsWith(";base64")) {
      throw new Error("Invalid encrypted attachment");
    }
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    const type = header.slice(5, -7) || "application/octet-stream";
    const link = URL.createObjectURL(new Blob([bytes], { type }));
    const element = document.createElement("a");
    element.href = link;
    element.download = attachment.name;
    element.click();
    setTimeout(() => URL.revokeObjectURL(link), 1000);
  } catch {
    message.value = "Could not decrypt the attachment.";
  }
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

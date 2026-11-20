<template>
  <!-- Confirm Deletion Modal -->
  <ConfirmModal
    v-model="isDeleteModalVisible"
    title="Confirm Deletion"
    :message="isNewNote ? 'Discard this unsaved note?' : `Are you sure you want to delete the note '${note.title}'?`"
    confirmButtonText="Delete"
    confirmButtonStyle="danger"
    @confirm="deleteConfirmedHandler"
  />

  <!-- Save Changes Modal -->
  <ConfirmModal
    v-model="isSaveChangesModalVisible"
    title="Save Changes"
    message="Do you want to save your changes?"
    confirmButtonText="Save"
    confirmButtonStyle="success"
    rejectButtonText="Discard"
    rejectButtonStyle="danger"
    @confirm="saveHandler((close = true))"
    @reject="closeNote"
  />

  <!-- Draft Modal -->
  <ConfirmModal
    v-model="isDraftModalVisible"
    title="Draft Detected"
    message="There is an unsaved draft of this note stored in this browser. Do you want to resume the draft version or delete it?"
    confirmButtonText="Resume Draft"
    confirmButtonStyle="cta"
    rejectButtonText="Delete Draft"
    rejectButtonStyle="danger"
    @confirm="setEditMode()"
    @reject="
      clearDraft();
      setEditMode();
    "
  />

  <ShareModal
    v-if="globalStore.config.sharingEnabled"
    v-model="isShareModalVisible"
    :title="note.title || newTitle"
    :draft="isNewNote"
    :initialSettings="stagedShare"
    @updated="onShareUpdated"
  />
  <ExpirationModal
    v-if="globalStore.config.expirationEnabled"
    v-model="isExpirationModalVisible"
    kind="plain"
    :noteId="note.title || ''"
    :draft="isNewNote"
    :initialPolicy="expirationPolicy"
    @updated="onExpirationUpdated"
  />
  <ProtectModal
    v-if="globalStore.config.encryptionEnabled"
    v-model="isProtectModalVisible"
    :title="protectPayload.title"
    :content="protectPayload.content"
    :sourceTitle="note.title"
    :lastModified="note.lastModified"
    :newNote="isNewNote"
    :expirationPolicy="isNewNote ? expirationPolicy : note.expiration?.policy || 'none'"
    :pendingShare="isNewNote ? stagedShare : null"
    @protected="clearProtectedDraft"
  />

  <LoadingIndicator ref="loadingIndicator" class="flex h-full flex-col">
    <NoteHeader
      ref="noteHeader"
      v-model:title="newTitle"
      :displayTitle="note.title || ''"
      :editing="editMode"
      :titleError="titleError"
      @titleInput="titleError = false"
    >
      <NoteToolbar
        :editing="editMode"
        :isNew="isNewNote"
        :canModify="canModify"
        :consumed="Boolean(note.viewToken)"
        :showShare="globalStore.config.sharingEnabled && canModify"
        :showExpiration="globalStore.config.expirationEnabled && canModify"
        :showProtect="globalStore.config.encryptionEnabled && canModify"
        :shareActive="shareActive"
        :expirationActive="expirationActive"
        :busy="saving"
        @share="isShareModalVisible = true"
        @expiration="isExpirationModalVisible = true"
        @protect="openProtect"
        @export="exportMarkdown"
        @delete="deleteHandler"
        @cancel="closeHandler"
        @save="saveHandler(false)"
        @toggle-edit="toggleEditModeHandler"
      />
    </NoteHeader>
    <p v-if="note.expiration?.mode && note.expiration.mode !== 'none'"
      class="mb-2 text-xs text-theme-text-muted">
      {{ expirationLabel(note.expiration) }}
    </p>
    <hr v-if="!editMode" class="my-4 border-theme-border" />

    <!-- Content -->
    <div class="flex-1">
      <ToastViewer
        v-if="!editMode"
        :initialValue="note.content"
        class="toast-viewer pb-4"
      />
      <ToastEditor
        v-if="editMode"
        ref="toastEditor"
        :initialValue="getInitialEditorValue()"
        :initialEditType="loadDefaultEditorMode()"
        :addImageBlobHook="addImageBlobHook"
        @change="startContentChangedTimeout"
        @keydown="keydownHandler"
      />
    </div>
  </LoadingIndicator>
</template>

<style>
/* Disable checkboxes in view mode. See https://github.com/nhn/tui.editor/issues/1087. */
.toast-viewer li.task-list-item {
  pointer-events: none;
}
.toast-viewer li.task-list-item a {
  pointer-events: auto;
}
</style>

<script setup>
import { mdiNoteOffOutline } from "@mdi/js";
import Mousetrap from "mousetrap";
import { useToast } from "primevue/usetoast";
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  apiErrorHandler,
  createAttachment,
  createNote,
  deleteNote,
  getNote,
  getPublication,
  savePublication,
  updateNote,
} from "../api.js";
import { Note } from "../classes.js";
import ConfirmModal from "../components/ConfirmModal.vue";
import CustomButton from "../components/CustomButton.vue";
import LoadingIndicator from "../components/LoadingIndicator.vue";
import ShareModal from "../components/ShareModal.vue";
import ProtectModal from "../components/ProtectModal.vue";
import ExpirationModal from "../components/ExpirationModal.vue";
import NoteToolbar from "../components/NoteToolbar.vue";
import NoteHeader from "../components/NoteHeader.vue";
import ToastEditor from "../components/toastui/ToastEditor.vue";
import ToastViewer from "../components/toastui/ToastViewer.vue";
import { authTypes } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";
import { getToastOptions } from "../helpers.js";
import { isCurrentTokenStored } from "../tokenStorage.js";

const props = defineProps({
  title: String,
});

const canModify = computed(
  () => globalStore.config.authType != authTypes.readOnly && !note.value.viewToken,
);
let contentChangedTimeout = null;
const editMode = ref(false);
const globalStore = useGlobalStore();
const isSaveChangesModalVisible = ref(false);
const isDeleteModalVisible = ref(false);
const isShareModalVisible = ref(false);
const isProtectModalVisible = ref(false);
const isExpirationModalVisible = ref(false);
const expirationPolicy = ref("none");
const stagedShare = ref(null);
const shareActive = ref(false);
const saving = ref(false);
const titleError = ref(false);
const noteHeader = ref(null);
const protectPayload = ref({ title: "", content: "" });
const expirationActive = computed(() => {
  const policy = isNewNote.value ? expirationPolicy.value : note.value.expiration?.policy;
  return Boolean(policy && policy !== "none");
});
const isDraftModalVisible = ref(false);
const isNewNote = computed(() => !props.title);
const loadingIndicator = ref();
const note = ref({});
const reservedFilenameCharacters = /[<>:"/\\|?*]/;
const router = useRouter();
const newTitle = ref();
const toast = useToast();
const toastEditor = ref();
const unsavedChanges = ref(false);

function init() {
  // Return if we already have the note e.g. When we rename a note, the route prop would change but we’d already have the note.
  if (props.title && props.title == note.value.title) {
    return;
  }

  loadingIndicator.value.setLoading();
  if (props.title) {
    getNote(props.title)
      .then((data) => {
        note.value = data;
        newTitle.value = data.title;
        refreshShareStatus(data.title);
        loadingIndicator.value.setLoaded();
      })
      .catch((error) => {
        if (error.response?.status === 410) {
          loadingIndicator.value.setFailed("Note expired or already viewed", mdiNoteOffOutline);
        } else if (error.response?.status === 404) {
          loadingIndicator.value.setFailed("Note not found", mdiNoteOffOutline);
        } else {
          loadingIndicator.value.setFailed();
          apiErrorHandler(error, toast);
        }
      });
  } else {
    newTitle.value = "";
    stagedShare.value = null;
    shareActive.value = false;
    expirationPolicy.value = globalStore.config.expirationEnabled
      ? globalStore.config.expirationDefault || "none" : "none";
    note.value = new Note();
    // Set the editMode to false to close any existing editors.
    // This ensures the editor is cleanly reinitialised in an empty state.
    // Simple fix for #266 without requiring a full re-work of the logic.
    editMode.value = false;
    nextTick(() => {
      editHandler();
      loadingIndicator.value.setLoaded();
    });
  }
}

function openProtect() {
  const title = editMode.value ? newTitle.value?.trim() : note.value.title;
  if (!title) {
    titleError.value = true;
    nextTick(() => noteHeader.value?.focusTitle());
    return;
  }
  protectPayload.value = {
    title,
    content: editMode.value ? toastEditor.value?.getMarkdown() || "" : note.value.content || "",
  };
  isProtectModalVisible.value = true;
}

function onExpirationUpdated(value) {
  if (isNewNote.value) expirationPolicy.value = value.policy;
  else note.value.expiration = value;
}

function onShareUpdated(settings) {
  if (isNewNote.value) stagedShare.value = settings;
  shareActive.value = Boolean(settings?.permission && settings.permission !== "private");
}

async function refreshShareStatus(title) {
  if (!globalStore.config.sharingEnabled || !title || note.value.viewToken) return;
  try {
    const state = await getPublication(title);
    if (note.value.title === title) shareActive.value = Boolean(state?.slug);
  } catch {
    shareActive.value = false;
  }
}

function exportMarkdown() {
  const body = editMode.value ? toastEditor.value?.getMarkdown() || "" : note.value.content || "";
  const filename = (editMode.value ? newTitle.value : note.value.title) || "note";
  const href = URL.createObjectURL(new Blob([body], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = href;
  link.download = filename + ".md";
  link.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

function expirationLabel(value) {
  if (value.mode === "once") {
    return note.value.viewToken ? "Single view consumed" : "Single view on next opening";
  }
  return value.expiresAt
    ? "Expires " + new Date(value.expiresAt * 1000).toLocaleString()
    : "";
}

// Note Editing
function toggleEditModeHandler() {
  if (editMode.value) {
    closeHandler();
  } else {
    editHandler();
  }
}

function editHandler() {
  const draftContent = loadDraft();
  if (draftContent) {
    isDraftModalVisible.value = true;
  } else {
    setEditMode();
  }
}

function setEditMode() {
  newTitle.value = note.value.title;
  unsavedChanges.value = false;
  editMode.value = true;
}

function getInitialEditorValue() {
  const draftContent = loadDraft();
  return draftContent ? draftContent : note.value.content;
}

// Note Deletion
function deleteHandler() {
  isDeleteModalVisible.value = true;
}

function deleteConfirmedHandler() {
  if (isNewNote.value) {
    clearDraft();
    router.push({ name: "home" });
    return;
  }
  deleteNote(note.value.title)
    .then(() => {
      toast.add(getToastOptions("Note deleted ✓", "Success", "success"));
      router.push({ name: "home" });
    })
    .catch((error) => {
      apiErrorHandler(error, toast);
    });
}

// Note Saving
function saveHandler(close = false) {
  // Save Default Editor Mode
  saveDefaultEditorMode();

  // Empty Title Validation
  if (!newTitle.value?.trim()) {
    titleError.value = true;
    nextTick(() => noteHeader.value?.focusTitle());
    toast.add(
      getToastOptions("Cannot save note without a title.", "Invalid", "error"),
    );
    return;
  }

  titleError.value = false;
  // Invalid Character Validation
  if (reservedFilenameCharacters.test(newTitle.value)) {
    badFilenameToast("Title");
    return;
  }

  // Save Note
  let newContent = toastEditor.value.getMarkdown();
  if (isNewNote.value) {
    saveNew(newTitle.value, newContent, close);
  } else {
    saveExisting(newTitle.value, newContent, close);
  }
}

async function saveNew(newTitle, newContent, close = false) {
  if (saving.value) return;
  saving.value = true;
  try {
    const data = await createNote(newTitle, newContent, expirationPolicy.value);
    clearDraft();
    note.value = data;
    if (stagedShare.value) {
      try {
        const published = await savePublication(data.title, stagedShare.value);
        shareActive.value = Boolean(published?.slug);
        stagedShare.value = null;
      } catch {
        shareActive.value = false;
        stagedShare.value = null;
        toast.add(getToastOptions(
          "The note was saved, but sharing could not be activated. Open Share to try again.",
          "Sharing", "error",
        ));
      }
    }
    await router.replace({ name: "note", params: { title: note.value.title } });
    noteSaveSuccess(close);
  } catch (error) {
    noteSaveFailure(error);
  } finally {
    saving.value = false;
  }
}

function saveExisting(newTitle, newContent, close = false) {
  // Return if no changes
  if (newTitle == note.value.title && newContent == note.value.content) {
    noteSaveSuccess(close);
    return;
  }

  updateNote(note.value.title, newTitle, newContent)
    .then((data) => {
      clearDraft();
      note.value = data;
      router.replace({ name: "note", params: { title: note.value.title } });
      noteSaveSuccess(close);
    })
    .catch(noteSaveFailure);
}

function noteSaveFailure(error) {
  if (error.response?.status === 409) {
    toast.add(
      getToastOptions(
        "A note with this title already exists. Please try again with a new title.",
        "Duplicate",
        "error",
      ),
    );
  } else if (error.response?.status === 413) {
    entityTooLargeToast("note");
  } else {
    apiErrorHandler(error, toast);
  }
}

function noteSaveSuccess(close = false) {
  unsavedChanges.value = false;
  editMode.value = false;
  if (close) {
    closeNote();
  }
  setBeforeUnloadConfirmation(false);
  toast.add(getToastOptions("Note saved successfully ✓", "Success", "success"));
}

// Note Closure
function closeHandler() {
  if (isContentChanged()) {
    isSaveChangesModalVisible.value = true;
  } else {
    closeNote();
  }
}

function closeNote() {
  clearDraft();
  editMode.value = false;
  if (isNewNote.value) {
    router.push({ name: "home" });
  } else {
    editMode.value = false;
  }
}

// Image Upload
function addImageBlobHook(file, callback) {
  const altTextInputValue = document.getElementById(
    "toastuiAltTextInput",
  )?.value;

  // Upload the image then use the callback to insert the URL into the editor
  postAttachment(file).then(function (data) {
    if (data) {
      // If the user has entered an alt text, use it. Otherwise, use the filename returned by the API.
      const altText = altTextInputValue ? altTextInputValue : data.filename;
      callback(data.url, altText);
    }
  });
}

function postAttachment(file) {
  // Invalid Character Validation
  if (reservedFilenameCharacters.test(file.name)) {
    badFilenameToast("Title");
    return;
  }

  // Uploading Toast
  toast.add(getToastOptions("Uploading attachment..."));

  // Upload the attachment
  return createAttachment(file)
    .then((data) => {
      // Success Toast
      toast.add(
        getToastOptions(
          "Attachment uploaded successfully ✓",
          "Success",
          "success",
        ),
      );
      return data;
    })
    .catch((error) => {
      if (error.response?.status === 409) {
        // Note: The current implementation will append a datetime to the filename if it already exists.
        // Error Toast
        toast.add(
          getToastOptions(
            "An attachment with this filename already exists.",
            "Duplicate",
            "error",
          ),
        );
      } else if (error.response?.status == 413) {
        entityTooLargeToast("attachment");
      } else {
        apiErrorHandler(error, toast);
      }
    });
}

// Content Change Watcher
function startContentChangedTimeout() {
  clearContentChangedTimeout();
  contentChangedTimeout = setTimeout(contentChangedHandler, 1000);
}

function clearContentChangedTimeout() {
  if (contentChangedTimeout != null) {
    clearTimeout(contentChangedTimeout);
  }
}

function contentChangedHandler() {
  if (isContentChanged()) {
    unsavedChanges.value = true;
    setBeforeUnloadConfirmation(true);
    saveDraft();
  } else {
    unsavedChanges.value = false;
    setBeforeUnloadConfirmation(false);
    clearDraft();
  }
}

function clearProtectedDraft() {
  clearContentChangedTimeout();
  clearDraft();
}

// Drafts
function saveDraft() {
  const content = toastEditor.value.getMarkdown();
  const userHasPersistedToken = isCurrentTokenStored();
  if (content) {
    if (userHasPersistedToken) {
      localStorage.setItem(note.value.title, content);
    } else {
      sessionStorage.setItem(note.value.title, content);
    }
  }
}

function clearDraft() {
  localStorage.removeItem(note.value.title);
  sessionStorage.removeItem(note.value.title);
}

function loadDraft() {
  const localDraft = localStorage.getItem(note.value.title);
  const sessionDraft = sessionStorage.getItem(note.value.title);
  return localDraft || sessionDraft;
}

// Keyboard Shortcuts
// 'e' to edit
Mousetrap.bind("e", () => {
  if (editMode.value === false && canModify.value) {
    editHandler();
  }
});

function keydownHandler(event) {
  // Ctrl + Enter to save
  if ((event.ctrlKey || event.metaKey) && event.key == "Enter") {
    saveHandler((close = false));
  }
  // Escape to exit edit mode
  if (event.key == "Escape") {
    closeHandler();
  }
}

// Helpers
function entityTooLargeToast(entityName) {
  toast.add(
    getToastOptions(
      `This ${entityName} is too large. Please try again with a smaller ${entityName} or adjust your server configuration.`,
      "Failure",
      "error",
    ),
  );
}

function badFilenameToast(entityName) {
  toast.add(
    getToastOptions(
      'Due to filename restrictions, the following characters are not allowed: <>:"/\\|?*',
      `Invalid ${entityName}`,
      "error",
    ),
  );
}

function setBeforeUnloadConfirmation(enable = true) {
  if (enable) {
    window.onbeforeunload = () => {
      return true;
    };
  } else {
    window.onbeforeunload = null;
  }
}

function saveDefaultEditorMode() {
  const isWysiwygMode = toastEditor.value.isWysiwygMode();
  localStorage.setItem(
    "defaultEditorMode",
    isWysiwygMode ? "wysiwyg" : "markdown",
  );
}

function loadDefaultEditorMode() {
  const defaultWysiwygMode = localStorage.getItem("defaultEditorMode");
  return defaultWysiwygMode || "markdown";
}

function isContentChanged() {
  return (
    newTitle.value != note.value.title ||
    toastEditor.value.getMarkdown() != note.value.content
  );
}

watch(() => props.title, init);
onMounted(init);
</script>

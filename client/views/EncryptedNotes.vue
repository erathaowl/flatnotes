<template>
  <div class="mx-auto w-full max-w-3xl">
    <ConfirmModal
      v-model="showDeleteConfirmation"
      title="Delete protected note"
      :message="'Permanently delete encrypted note ' + pendingDeleteId + '? This cannot be undone, even without its password.'"
      confirmButtonText="Delete"
      confirmButtonStyle="danger"
      @confirm="confirmDelete"
    />
    <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-2xl">Protected notes</h1>
      <RouterLink
        v-if="globalStore.config.encryptionEnabled && canModify"
        :to="{ name: 'encryptedNote', params: { id: 'new' } }"
      >
        <CustomButton :iconPath="mdilPlusCircle" label="New protected note" />
      </RouterLink>
    </div>
    <p class="mb-4 text-sm text-theme-text-muted">
      Titles are encrypted. Unlock a note to see its title and content.
    </p>
    <p v-if="errorMessage" role="alert" class="mb-3 text-theme-danger">{{ errorMessage }}</p>
    <p v-if="loading" class="text-theme-text-muted">Loading protected notes...</p>
    <p v-else-if="!notes.length">No protected notes.</p>
    <ul v-else class="space-y-2">
      <li v-for="note in notes" :key="note.id" class="flex items-center gap-2">
        <RouterLink
          class="flex min-w-0 flex-1 items-center gap-2 rounded border border-theme-border p-3 hover:bg-theme-background-elevated"
          :to="{ name: 'encryptedNote', params: { id: note.id } }"
          :title="note.id"
        >
          <SvgIcon type="mdi" :path="mdilLock" size="1.25em" class="shrink-0" />
          <span class="truncate">{{ note.id }}</span>
        </RouterLink>
        <CustomButton
          v-if="canModify"
          :iconPath="mdilDelete"
          style="danger"
          :disabled="Boolean(deletingId)"
          :aria-label="'Delete protected note ' + note.id"
          :title="'Delete encrypted note ' + note.id"
          @click="requestDelete(note.id)"
        />
      </li>
    </ul>
  </div>
</template>

<script setup>
import SvgIcon from "@jamescoyle/vue-icon";
import { mdilDelete, mdilLock, mdilPlusCircle } from "@mdi/light-js";
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { deleteEncryptedNote, listEncryptedNotes } from "../api.js";
import ConfirmModal from "../components/ConfirmModal.vue";
import CustomButton from "../components/CustomButton.vue";
import { authTypes } from "../constants.js";
import { useGlobalStore } from "../globalStore.js";

const globalStore = useGlobalStore();
const canModify = computed(() => globalStore.config.authType !== authTypes.readOnly);
const notes = ref([]);
const loading = ref(true);
const errorMessage = ref("");
const deletingId = ref("");
const pendingDeleteId = ref("");
const showDeleteConfirmation = ref(false);

function requestDelete(noteId) {
  pendingDeleteId.value = noteId;
  showDeleteConfirmation.value = true;
}

async function confirmDelete() {
  if (!pendingDeleteId.value || deletingId.value) return;
  const noteId = pendingDeleteId.value;
  deletingId.value = noteId;
  errorMessage.value = "";
  try {
    await deleteEncryptedNote(noteId);
    notes.value = notes.value.filter((note) => note.id !== noteId);
  } catch {
    errorMessage.value = "Could not delete the encrypted note. Please try again.";
  } finally {
    deletingId.value = "";
    pendingDeleteId.value = "";
  }
}

onMounted(async () => {
  try {
    notes.value = await listEncryptedNotes();
  } catch {
    errorMessage.value = "Unable to load the encrypted notes list.";
  } finally {
    loading.value = false;
  }
});
</script>

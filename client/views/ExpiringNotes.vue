<template>
  <div class="mx-auto w-full max-w-3xl">
    <h1 class="mb-4 text-2xl">Expiring Notes</h1>
    <p class="mb-4 text-sm text-theme-text-muted">
      These notes have a time limit or a single view. Single-view notes
      are omitted from full-text search to avoid disclosing their contents.
    </p>
    <p v-if="errorMessage" role="alert" class="text-theme-danger">{{ errorMessage }}</p>
    <p v-else-if="loading">Loading...</p>
    <p v-else-if="!notes.length">No active expiring notes.</p>
    <ul v-else class="space-y-2">
      <li v-for="note in notes" :key="note.type + note.id">
        <RouterLink
          :to="note.type === 'encrypted'
            ? { name: 'encryptedNote', params: { id: note.id } }
            : { name: 'note', params: { title: note.id } }"
          class="block rounded border border-theme-border p-3 hover:bg-theme-background-elevated"
        >
          <span class="block truncate">{{ note.type === "encrypted" ? "Protected: " : "" }}{{ note.id }}</span>
          <span class="text-xs text-theme-text-muted">
            {{ note.mode === "once" ? "Single view" : "Expires " + new Date(note.expiresAt * 1000).toLocaleString() }}
          </span>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { listExpiringNotes } from "../api.js";

const notes = ref([]);
const loading = ref(true);
const errorMessage = ref("");

onMounted(async () => {
  try {
    notes.value = await listExpiringNotes();
  } catch {
    errorMessage.value = "Unable to load expiring notes.";
  } finally {
    loading.value = false;
  }
});
</script>
